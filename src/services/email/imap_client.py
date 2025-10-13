"""
IMAP Client for Email Gateway

Handles incoming email monitoring with connection management,
automatic reconnection, and email parsing capabilities.
"""

import asyncio
import email
import imaplib
import logging
import ssl
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Dict, List, Optional, Any, Callable, Tuple
import socket
import re

from .models import EmailMessage, EmailAddress, EmailConfiguration, EmailDirection, EmailPriority
from .email_parser import EmailParser


class IMAPConnectionError(Exception):
    """IMAP connection related errors"""
    pass


class IMAPAuthenticationError(Exception):
    """IMAP authentication related errors"""
    pass


class IMAPFolderError(Exception):
    """IMAP folder related errors"""
    pass


class IMAPClient:
    """
    IMAP client for monitoring incoming emails with connection management
    """
    
    def __init__(self, config: EmailConfiguration):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Connection state
        self.imap_server: Optional[imaplib.IMAP4] = None
        self.is_connected = False
        self.is_monitoring = False
        self.last_connection_attempt = None
        self.connection_failures = 0
        self.max_connection_failures = 5
        self.reconnect_delay = 30  # seconds
        
        # Email processing
        self.email_parser = EmailParser()
        self.message_callbacks: List[Callable[[EmailMessage], None]] = []
        self.last_check_time = datetime.utcnow()
        self.processed_message_ids: set = set()
        
        # Statistics
        self.emails_processed = 0
        self.processing_failures = 0
        self.connection_attempts = 0
        self.last_check_time = None
        
        # Monitoring task
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Connection lock for thread safety
        self._connection_lock = asyncio.Lock()
    
    async def start(self):
        """Start the IMAP client and begin monitoring"""
        try:
            await self.connect()
            await self.start_monitoring()
            self.logger.info("IMAP client started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start IMAP client: {e}")
            raise
    
    async def stop(self):
        """Stop the IMAP client and monitoring"""
        await self.stop_monitoring()
        await self.disconnect()
        self.logger.info("IMAP client stopped")
    
    async def connect(self) -> bool:
        """
        Connect to IMAP server with authentication
        
        Returns:
            True if connection successful, False otherwise
        """
        async with self._connection_lock:
            if self.is_connected:
                return True
            
            try:
                self.connection_attempts += 1
                self.last_connection_attempt = datetime.utcnow()
                
                self.logger.info(f"Connecting to IMAP server {self.config.imap_host}:{self.config.imap_port}")
                
                # Create IMAP connection
                if self.config.imap_use_ssl:
                    context = ssl.create_default_context()
                    self.imap_server = imaplib.IMAP4_SSL(
                        self.config.imap_host,
                        self.config.imap_port,
                        ssl_context=context
                    )
                else:
                    self.imap_server = imaplib.IMAP4(
                        self.config.imap_host,
                        self.config.imap_port
                    )
                
                # Set timeout
                self.imap_server.sock.settimeout(self.config.imap_timeout)
                
                # Authenticate
                result = self.imap_server.login(
                    self.config.imap_username,
                    self.config.imap_password
                )
                
                if result[0] != 'OK':
                    raise IMAPAuthenticationError(f"Login failed: {result[1]}")
                
                # Select folder
                result = self.imap_server.select(self.config.imap_folder)
                if result[0] != 'OK':
                    raise IMAPFolderError(f"Failed to select folder {self.config.imap_folder}: {result[1]}")
                
                self.is_connected = True
                self.connection_failures = 0
                self.logger.info("IMAP connection established successfully")
                return True
                
            except imaplib.IMAP4.error as e:
                if "authentication failed" in str(e).lower():
                    self.logger.error(f"IMAP authentication failed: {e}")
                    self.connection_failures += 1
                    raise IMAPAuthenticationError(f"Authentication failed: {e}")
                else:
                    self.logger.error(f"IMAP error: {e}")
                    self.connection_failures += 1
                    raise IMAPConnectionError(f"IMAP error: {e}")
                    
            except (socket.gaierror, socket.timeout, ConnectionRefusedError, OSError) as e:
                self.logger.error(f"IMAP connection failed: {e}")
                self.connection_failures += 1
                raise IMAPConnectionError(f"Connection failed: {e}")
                
            except Exception as e:
                self.logger.error(f"Unexpected IMAP error: {e}")
                self.connection_failures += 1
                raise IMAPConnectionError(f"Unexpected error: {e}")
    
    async def disconnect(self):
        """Disconnect from IMAP server"""
        async with self._connection_lock:
            if self.imap_server:
                try:
                    self.imap_server.close()
                    self.imap_server.logout()
                except Exception as e:
                    self.logger.warning(f"Error during IMAP disconnect: {e}")
                finally:
                    self.imap_server = None
                    self.is_connected = False
                    self.logger.debug("IMAP connection closed")
    
    async def ensure_connected(self) -> bool:
        """
        Ensure IMAP connection is active, reconnect if necessary
        
        Returns:
            True if connected, False otherwise
        """
        if self.is_connected and self.imap_server:
            try:
                # Test connection with NOOP
                result = self.imap_server.noop()
                if result[0] == 'OK':
                    return True
            except Exception as e:
                self.logger.warning(f"IMAP connection test failed: {e}")
                self.is_connected = False
        
        # Check if we should attempt reconnection
        if self.connection_failures >= self.max_connection_failures:
            if (self.last_connection_attempt and 
                (datetime.utcnow() - self.last_connection_attempt).total_seconds() < self.reconnect_delay):
                return False
        
        try:
            return await self.connect()
        except Exception as e:
            self.logger.error(f"Failed to reconnect to IMAP server: {e}")
            return False
    
    def add_message_callback(self, callback: Callable[[EmailMessage], None]):
        """Add callback for processed messages"""
        self.message_callbacks.append(callback)
    
    def remove_message_callback(self, callback: Callable[[EmailMessage], None]):
        """Remove message callback"""
        if callback in self.message_callbacks:
            self.message_callbacks.remove(callback)
    
    async def start_monitoring(self):
        """Start monitoring for new emails"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Started IMAP email monitoring")
    
    async def stop_monitoring(self):
        """Stop monitoring for new emails"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
            self.monitor_task = None
        
        self.logger.info("Stopped IMAP email monitoring")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                await self._check_for_new_emails()
                await asyncio.sleep(self.config.imap_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in IMAP monitor loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _check_for_new_emails(self):
        """Check for new emails and process them"""
        if not await self.ensure_connected():
            return
        
        try:
            # Search for unread emails
            result = self.imap_server.search(None, 'UNSEEN')
            if result[0] != 'OK':
                self.logger.error(f"Failed to search for emails: {result[1]}")
                return
            
            message_ids = result[1][0].split()
            if not message_ids:
                return  # No new messages
            
            self.logger.info(f"Found {len(message_ids)} new email(s)")
            
            # Process each message
            for msg_id in message_ids:
                try:
                    await self._process_email_message(msg_id.decode())
                except Exception as e:
                    self.logger.error(f"Failed to process email {msg_id}: {e}")
                    self.processing_failures += 1
            
            self.last_check_time = datetime.utcnow()
            
        except Exception as e:
            self.logger.error(f"Error checking for new emails: {e}")
    
    async def _process_email_message(self, message_id: str):
        """Process a single email message"""
        try:
            # Fetch the email
            result = self.imap_server.fetch(message_id, '(RFC822)')
            if result[0] != 'OK':
                self.logger.error(f"Failed to fetch email {message_id}: {result[1]}")
                return
            
            # Parse the raw email
            raw_email = result[1][0][1]
            email_obj = email.message_from_bytes(raw_email)
            
            # Convert to EmailMessage
            email_message = await self._parse_email_to_message(email_obj)
            if not email_message:
                return
            
            # Check if we've already processed this message
            email_message_id = email_obj.get('Message-ID', '')
            if email_message_id in self.processed_message_ids:
                self.logger.debug(f"Skipping already processed message: {email_message_id}")
                return
            
            # Add to processed set
            self.processed_message_ids.add(email_message_id)
            
            # Limit processed message IDs to prevent memory growth
            if len(self.processed_message_ids) > 10000:
                # Remove oldest half
                self.processed_message_ids = set(list(self.processed_message_ids)[5000:])
            
            # Call callbacks
            for callback in self.message_callbacks:
                try:
                    await callback(email_message)
                except Exception as e:
                    self.logger.error(f"Error in message callback: {e}")
            
            self.emails_processed += 1
            self.logger.info(f"Processed email from {email_message.from_address}: {email_message.subject}")
            
            # Mark as read (optional - could be configurable)
            # self.imap_server.store(message_id, '+FLAGS', '\\Seen')
            
        except Exception as e:
            self.logger.error(f"Error processing email message {message_id}: {e}")
            self.processing_failures += 1
    
    async def _parse_email_to_message(self, email_obj: email.message.Message) -> Optional[EmailMessage]:
        """
        Parse email.message.Message to EmailMessage
        
        Args:
            email_obj: The email message object
            
        Returns:
            EmailMessage object or None if parsing failed
        """
        try:
            email_message = EmailMessage()
            email_message.direction = EmailDirection.EMAIL_TO_MESH
            
            # Parse headers
            email_message.from_address = self._parse_email_address(email_obj.get('From', ''))
            email_message.to_addresses = self._parse_email_addresses(email_obj.get('To', ''))
            email_message.cc_addresses = self._parse_email_addresses(email_obj.get('Cc', ''))
            email_message.reply_to = self._parse_email_address(email_obj.get('Reply-To', ''))
            
            # Subject
            subject = email_obj.get('Subject', '')
            if subject:
                email_message.subject = self._decode_header(subject)
            
            # Date
            date_str = email_obj.get('Date')
            if date_str:
                try:
                    email_message.created_at = parsedate_to_datetime(date_str)
                except Exception as e:
                    self.logger.warning(f"Failed to parse date '{date_str}': {e}")
            
            # Extract content
            await self._extract_email_content(email_obj, email_message)
            
            # Check for mesh-specific headers
            email_message.mesh_sender_id = email_obj.get('X-Mesh-Sender-ID')
            email_message.mesh_sender_name = email_obj.get('X-Mesh-Sender-Name')
            
            mesh_channel = email_obj.get('X-Mesh-Channel')
            if mesh_channel and mesh_channel.isdigit():
                email_message.mesh_channel = int(mesh_channel)
            
            email_message.mesh_interface_id = email_obj.get('X-Mesh-Interface')
            
            # Set priority based on headers
            priority_header = email_obj.get('X-Priority', '').lower()
            importance_header = email_obj.get('Importance', '').lower()
            
            if priority_header in ['1', 'high'] or importance_header == 'high':
                email_message.priority = EmailPriority.HIGH
            elif priority_header in ['5', 'low'] or importance_header == 'low':
                email_message.priority = EmailPriority.LOW
            else:
                email_message.priority = EmailPriority.NORMAL
            
            return email_message
            
        except Exception as e:
            self.logger.error(f"Failed to parse email to message: {e}")
            return None
    
    def _parse_email_address(self, address_str: str) -> Optional[EmailAddress]:
        """Parse email address string to EmailAddress object"""
        if not address_str:
            return None
        
        try:
            name, email_addr = parseaddr(address_str)
            if email_addr:
                return EmailAddress(
                    address=email_addr.strip(),
                    name=name.strip() if name else None
                )
        except Exception as e:
            self.logger.warning(f"Failed to parse email address '{address_str}': {e}")
        
        return None
    
    def _parse_email_addresses(self, addresses_str: str) -> List[EmailAddress]:
        """Parse comma-separated email addresses"""
        addresses = []
        if not addresses_str:
            return addresses
        
        try:
            # Split by comma and parse each address
            for addr_str in addresses_str.split(','):
                addr = self._parse_email_address(addr_str.strip())
                if addr:
                    addresses.append(addr)
        except Exception as e:
            self.logger.warning(f"Failed to parse email addresses '{addresses_str}': {e}")
        
        return addresses
    
    def _decode_header(self, header_value: str) -> str:
        """Decode email header value"""
        try:
            decoded_parts = decode_header(header_value)
            decoded_string = ''
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding)
                    else:
                        decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += part
            
            return decoded_string.strip()
        except Exception as e:
            self.logger.warning(f"Failed to decode header '{header_value}': {e}")
            return header_value
    
    async def _extract_email_content(self, email_obj: email.message.Message, email_message: EmailMessage):
        """Extract text and HTML content from email"""
        try:
            if email_obj.is_multipart():
                # Handle multipart messages
                for part in email_obj.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition', ''))
                    
                    # Skip attachments
                    if 'attachment' in content_disposition:
                        await self._process_attachment(part, email_message)
                        continue
                    
                    if content_type == 'text/plain':
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            email_message.body_text = payload.decode(charset, errors='ignore')
                    
                    elif content_type == 'text/html':
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            email_message.body_html = payload.decode(charset, errors='ignore')
            else:
                # Handle single part messages
                content_type = email_obj.get_content_type()
                payload = email_obj.get_payload(decode=True)
                
                if payload:
                    charset = email_obj.get_content_charset() or 'utf-8'
                    content = payload.decode(charset, errors='ignore')
                    
                    if content_type == 'text/html':
                        email_message.body_html = content
                        # Convert HTML to text for body_text
                        email_message.body_text = self._html_to_text(content)
                    else:
                        email_message.body_text = content
            
            # Clean up content
            if email_message.body_text:
                email_message.body_text = email_message.body_text.strip()
            
        except Exception as e:
            self.logger.error(f"Failed to extract email content: {e}")
    
    async def _process_attachment(self, part: email.message.Message, email_message: EmailMessage):
        """Process email attachment"""
        try:
            filename = part.get_filename()
            if not filename:
                return
            
            # Decode filename
            filename = self._decode_header(filename)
            
            # Get attachment data
            payload = part.get_payload(decode=True)
            if not payload:
                return
            
            # Check size limits
            if len(payload) > self.config.max_attachment_size:
                self.logger.warning(f"Attachment {filename} too large ({len(payload)} bytes), skipping")
                return
            
            if len(email_message.attachments) >= self.config.max_attachments:
                self.logger.warning(f"Too many attachments, skipping {filename}")
                return
            
            # Add attachment
            attachment = {
                'filename': filename,
                'data': payload,
                'content_type': part.get_content_type(),
                'size': len(payload)
            }
            
            email_message.attachments.append(attachment)
            self.logger.debug(f"Added attachment: {filename} ({len(payload)} bytes)")
            
        except Exception as e:
            self.logger.error(f"Failed to process attachment: {e}")
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text"""
        try:
            # Simple HTML to text conversion
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', html_content)
            
            # Decode HTML entities
            text = text.replace('&amp;', '&')
            text = text.replace('&lt;', '<')
            text = text.replace('&gt;', '>')
            text = text.replace('&quot;', '"')
            text = text.replace('&#39;', "'")
            text = text.replace('&nbsp;', ' ')
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            return text
        except Exception as e:
            self.logger.warning(f"Failed to convert HTML to text: {e}")
            return html_content
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get IMAP client statistics"""
        return {
            'is_connected': self.is_connected,
            'is_monitoring': self.is_monitoring,
            'emails_processed': self.emails_processed,
            'processing_failures': self.processing_failures,
            'connection_attempts': self.connection_attempts,
            'connection_failures': self.connection_failures,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'last_connection_attempt': self.last_connection_attempt.isoformat() if self.last_connection_attempt else None,
            'processed_message_count': len(self.processed_message_ids)
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test IMAP connection and return status
        
        Returns:
            Dictionary with test results
        """
        test_result = {
            'success': False,
            'error': None,
            'folder_info': None,
            'auth_success': False,
            'test_time': datetime.utcnow().isoformat()
        }
        
        try:
            # Temporarily disconnect if connected
            was_connected = self.is_connected
            if was_connected:
                await self.disconnect()
            
            # Test connection
            await self.connect()
            
            # Get folder info
            if self.imap_server:
                try:
                    result = self.imap_server.status(self.config.imap_folder, '(MESSAGES UNSEEN)')
                    if result[0] == 'OK':
                        status_info = result[1][0].decode()
                        test_result['folder_info'] = {
                            'folder': self.config.imap_folder,
                            'status': status_info
                        }
                except Exception as e:
                    self.logger.warning(f"Could not get folder info: {e}")
            
            test_result['success'] = True
            test_result['auth_success'] = True
            
            # Restore previous connection state
            if not was_connected:
                await self.disconnect()
            
        except IMAPAuthenticationError as e:
            test_result['error'] = f"Authentication failed: {e}"
            test_result['auth_success'] = False
        except IMAPConnectionError as e:
            test_result['error'] = f"Connection failed: {e}"
        except Exception as e:
            test_result['error'] = f"Unexpected error: {e}"
        
        return test_result