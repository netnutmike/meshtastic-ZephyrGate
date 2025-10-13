"""
SMTP Client for Email Gateway

Handles outgoing email sending with authentication, connection management,
and automatic reconnection capabilities.
"""

import asyncio
import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Any
import socket

from .models import EmailMessage, EmailAddress, EmailConfiguration, EmailStatus


class SMTPConnectionError(Exception):
    """SMTP connection related errors"""
    pass


class SMTPAuthenticationError(Exception):
    """SMTP authentication related errors"""
    pass


class SMTPSendError(Exception):
    """SMTP message sending related errors"""
    pass


class SMTPClient:
    """
    SMTP client for sending emails with connection management and retry logic
    """
    
    def __init__(self, config: EmailConfiguration):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Connection state
        self.smtp_server: Optional[smtplib.SMTP] = None
        self.is_connected = False
        self.last_connection_attempt = None
        self.connection_failures = 0
        self.max_connection_failures = 5
        self.reconnect_delay = 30  # seconds
        
        # Statistics
        self.emails_sent = 0
        self.send_failures = 0
        self.connection_attempts = 0
        self.last_send_time = None
        
        # Connection lock for thread safety
        self._connection_lock = asyncio.Lock()
    
    async def start(self):
        """Start the SMTP client"""
        try:
            await self.connect()
            self.logger.info("SMTP client started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start SMTP client: {e}")
            raise
    
    async def stop(self):
        """Stop the SMTP client"""
        await self.disconnect()
        self.logger.info("SMTP client stopped")
    
    async def connect(self) -> bool:
        """
        Connect to SMTP server with authentication
        
        Returns:
            True if connection successful, False otherwise
        """
        async with self._connection_lock:
            if self.is_connected:
                return True
            
            try:
                self.connection_attempts += 1
                self.last_connection_attempt = datetime.utcnow()
                
                self.logger.info(f"Connecting to SMTP server {self.config.smtp_host}:{self.config.smtp_port}")
                
                # Create SMTP connection
                if self.config.smtp_use_ssl:
                    # Use SMTP_SSL for port 465
                    context = ssl.create_default_context()
                    self.smtp_server = smtplib.SMTP_SSL(
                        self.config.smtp_host,
                        self.config.smtp_port,
                        timeout=self.config.smtp_timeout,
                        context=context
                    )
                else:
                    # Use regular SMTP for port 587 with STARTTLS
                    self.smtp_server = smtplib.SMTP(
                        self.config.smtp_host,
                        self.config.smtp_port,
                        timeout=self.config.smtp_timeout
                    )
                    
                    if self.config.smtp_use_tls:
                        # Enable TLS
                        context = ssl.create_default_context()
                        self.smtp_server.starttls(context=context)
                
                # Authenticate
                if self.config.smtp_username and self.config.smtp_password:
                    self.smtp_server.login(
                        self.config.smtp_username,
                        self.config.smtp_password
                    )
                
                self.is_connected = True
                self.connection_failures = 0
                self.logger.info("SMTP connection established successfully")
                return True
                
            except smtplib.SMTPAuthenticationError as e:
                self.logger.error(f"SMTP authentication failed: {e}")
                self.connection_failures += 1
                raise SMTPAuthenticationError(f"Authentication failed: {e}")
                
            except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, 
                    socket.gaierror, socket.timeout, ConnectionRefusedError) as e:
                self.logger.error(f"SMTP connection failed: {e}")
                self.connection_failures += 1
                raise SMTPConnectionError(f"Connection failed: {e}")
                
            except Exception as e:
                self.logger.error(f"Unexpected SMTP error: {e}")
                self.connection_failures += 1
                raise SMTPConnectionError(f"Unexpected error: {e}")
    
    async def disconnect(self):
        """Disconnect from SMTP server"""
        async with self._connection_lock:
            if self.smtp_server:
                try:
                    self.smtp_server.quit()
                except Exception as e:
                    self.logger.warning(f"Error during SMTP disconnect: {e}")
                finally:
                    self.smtp_server = None
                    self.is_connected = False
                    self.logger.debug("SMTP connection closed")
    
    async def ensure_connected(self) -> bool:
        """
        Ensure SMTP connection is active, reconnect if necessary
        
        Returns:
            True if connected, False otherwise
        """
        if self.is_connected and self.smtp_server:
            try:
                # Test connection with NOOP
                status = self.smtp_server.noop()[0]
                if status == 250:
                    return True
            except Exception as e:
                self.logger.warning(f"SMTP connection test failed: {e}")
                self.is_connected = False
        
        # Check if we should attempt reconnection
        if self.connection_failures >= self.max_connection_failures:
            if (self.last_connection_attempt and 
                (datetime.utcnow() - self.last_connection_attempt).total_seconds() < self.reconnect_delay):
                return False
        
        try:
            return await self.connect()
        except Exception as e:
            self.logger.error(f"Failed to reconnect to SMTP server: {e}")
            return False
    
    async def send_email(self, email_message: EmailMessage) -> bool:
        """
        Send an email message
        
        Args:
            email_message: The email message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Ensure connection
            if not await self.ensure_connected():
                raise SMTPConnectionError("Unable to establish SMTP connection")
            
            # Create MIME message
            mime_message = await self._create_mime_message(email_message)
            
            # Extract recipient addresses
            recipients = []
            for addr in email_message.to_addresses:
                recipients.append(addr.address)
            for addr in email_message.cc_addresses:
                recipients.append(addr.address)
            for addr in email_message.bcc_addresses:
                recipients.append(addr.address)
            
            if not recipients:
                raise SMTPSendError("No recipients specified")
            
            # Send the email
            sender_address = email_message.from_address.address if email_message.from_address else self.config.gateway_email
            
            async with self._connection_lock:
                refused = self.smtp_server.sendmail(
                    sender_address,
                    recipients,
                    mime_message.as_string()
                )
            
            # Check for refused recipients
            if refused:
                refused_list = list(refused.keys())
                self.logger.warning(f"Some recipients were refused: {refused_list}")
                email_message.add_error(f"Refused recipients: {refused_list}", "recipient_refused")
                
                # If all recipients were refused, consider it a failure
                if len(refused) == len(recipients):
                    self.send_failures += 1
                    return False
            
            # Success
            self.emails_sent += 1
            self.last_send_time = datetime.utcnow()
            email_message.processed_at = datetime.utcnow()
            
            self.logger.info(f"Email sent successfully: {email_message.id}")
            return True
            
        except SMTPConnectionError as e:
            self.logger.error(f"SMTP connection error sending email {email_message.id}: {e}")
            email_message.add_error(str(e), "connection_error")
            self.send_failures += 1
            return False
            
        except smtplib.SMTPRecipientsRefused as e:
            self.logger.error(f"All recipients refused for email {email_message.id}: {e}")
            email_message.add_error(f"All recipients refused: {e}", "recipients_refused")
            self.send_failures += 1
            return False
            
        except smtplib.SMTPSenderRefused as e:
            self.logger.error(f"Sender refused for email {email_message.id}: {e}")
            email_message.add_error(f"Sender refused: {e}", "sender_refused")
            self.send_failures += 1
            return False
            
        except smtplib.SMTPDataError as e:
            self.logger.error(f"SMTP data error for email {email_message.id}: {e}")
            email_message.add_error(f"Data error: {e}", "data_error")
            self.send_failures += 1
            return False
            
        except Exception as e:
            self.logger.error(f"Unexpected error sending email {email_message.id}: {e}")
            email_message.add_error(f"Unexpected error: {e}", "unexpected_error")
            self.send_failures += 1
            return False
    
    async def _create_mime_message(self, email_message: EmailMessage) -> MIMEMultipart:
        """
        Create MIME message from EmailMessage
        
        Args:
            email_message: The email message to convert
            
        Returns:
            MIME message ready for sending
        """
        # Create multipart message
        msg = MIMEMultipart('alternative')
        
        # Set headers
        if email_message.from_address:
            msg['From'] = str(email_message.from_address)
        else:
            msg['From'] = f"{self.config.gateway_name} <{self.config.gateway_email}>"
        
        # To addresses
        if email_message.to_addresses:
            msg['To'] = ', '.join(str(addr) for addr in email_message.to_addresses)
        
        # CC addresses
        if email_message.cc_addresses:
            msg['Cc'] = ', '.join(str(addr) for addr in email_message.cc_addresses)
        
        # Reply-To
        if email_message.reply_to:
            msg['Reply-To'] = str(email_message.reply_to)
        
        # Subject
        msg['Subject'] = email_message.subject or "Message from Meshtastic Gateway"
        
        # Date
        msg['Date'] = email_message.created_at.strftime('%a, %d %b %Y %H:%M:%S %z')
        
        # Message ID
        msg['Message-ID'] = f"<{email_message.id}@{self.config.gateway_email.split('@')[1]}>"
        
        # Add mesh metadata headers if configured
        if self.config.include_original_headers:
            if email_message.mesh_sender_id:
                msg['X-Mesh-Sender-ID'] = email_message.mesh_sender_id
            if email_message.mesh_sender_name:
                msg['X-Mesh-Sender-Name'] = email_message.mesh_sender_name
            if email_message.mesh_channel is not None:
                msg['X-Mesh-Channel'] = str(email_message.mesh_channel)
            if email_message.mesh_interface_id:
                msg['X-Mesh-Interface'] = email_message.mesh_interface_id
        
        # Create text content
        text_content = email_message.body_text
        if not text_content.endswith(self.config.email_footer):
            text_content += self.config.email_footer
        
        # Add text part
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # Add HTML part if available
        if email_message.body_html:
            html_content = email_message.body_html
            if not html_content.endswith(self.config.email_footer.replace('\n', '<br>')):
                html_content += self.config.email_footer.replace('\n', '<br>')
            
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
        
        # Add attachments
        for attachment in email_message.attachments:
            try:
                attachment_part = MIMEBase('application', 'octet-stream')
                attachment_part.set_payload(attachment.get('data', b''))
                encoders.encode_base64(attachment_part)
                
                filename = attachment.get('filename', 'attachment')
                attachment_part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}'
                )
                
                msg.attach(attachment_part)
            except Exception as e:
                self.logger.warning(f"Failed to attach file {attachment.get('filename', 'unknown')}: {e}")
        
        return msg
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get SMTP client statistics"""
        return {
            'is_connected': self.is_connected,
            'emails_sent': self.emails_sent,
            'send_failures': self.send_failures,
            'connection_attempts': self.connection_attempts,
            'connection_failures': self.connection_failures,
            'last_send_time': self.last_send_time.isoformat() if self.last_send_time else None,
            'last_connection_attempt': self.last_connection_attempt.isoformat() if self.last_connection_attempt else None
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test SMTP connection and return status
        
        Returns:
            Dictionary with test results
        """
        test_result = {
            'success': False,
            'error': None,
            'server_info': None,
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
            
            # Get server info
            if self.smtp_server:
                try:
                    # Get server capabilities
                    test_result['server_info'] = {
                        'host': self.config.smtp_host,
                        'port': self.config.smtp_port,
                        'supports_tls': self.config.smtp_use_tls,
                        'uses_ssl': self.config.smtp_use_ssl
                    }
                except Exception as e:
                    self.logger.warning(f"Could not get server info: {e}")
            
            test_result['success'] = True
            test_result['auth_success'] = True
            
            # Restore previous connection state
            if not was_connected:
                await self.disconnect()
            
        except SMTPAuthenticationError as e:
            test_result['error'] = f"Authentication failed: {e}"
            test_result['auth_success'] = False
        except SMTPConnectionError as e:
            test_result['error'] = f"Connection failed: {e}"
        except Exception as e:
            test_result['error'] = f"Unexpected error: {e}"
        
        return test_result