"""
Email Content Parser and Utilities

Utilities for parsing email content, extracting mesh commands,
and formatting email content for mesh network delivery.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from email.utils import parseaddr

from .models import EmailMessage, EmailAddress, EmailDirection


class EmailParser:
    """
    Email content parser for extracting mesh commands and formatting content
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Command patterns
        self.mesh_command_patterns = {
            'broadcast': re.compile(r'^(?:broadcast|bc):\s*(.+)', re.IGNORECASE | re.MULTILINE),
            'tag_send': re.compile(r'^(?:tag|tagsend):\s*(\w+)\s+(.+)', re.IGNORECASE | re.MULTILINE),
            'direct_message': re.compile(r'^(?:dm|direct):\s*(\w+)\s+(.+)', re.IGNORECASE | re.MULTILINE),
            'mesh_command': re.compile(r'^(?:mesh|cmd):\s*(.+)', re.IGNORECASE | re.MULTILINE)
        }
        
        # Content cleaning patterns
        self.quote_patterns = [
            re.compile(r'^On .+ wrote:.*$', re.MULTILINE | re.DOTALL),
            re.compile(r'^>.*$', re.MULTILINE),
            re.compile(r'^From:.*?^To:.*?^Subject:.*?^Date:.*?$', re.MULTILINE | re.DOTALL),
            re.compile(r'-----Original Message-----.*$', re.MULTILINE | re.DOTALL),
            re.compile(r'________________________________.*$', re.MULTILINE | re.DOTALL)
        ]
        
        # Signature patterns
        self.signature_patterns = [
            re.compile(r'^--\s*$.*$', re.MULTILINE | re.DOTALL),
            re.compile(r'^Sent from my .*$', re.MULTILINE),
            re.compile(r'^Best regards,.*$', re.MULTILINE | re.DOTALL),
            re.compile(r'^Sincerely,.*$', re.MULTILINE | re.DOTALL)
        ]
        
        # Footer patterns to remove
        self.footer_patterns = [
            re.compile(r'---\s*Sent via Meshtastic Gateway.*$', re.MULTILINE | re.DOTALL),
            re.compile(r'This email was sent via.*gateway.*$', re.MULTILINE | re.DOTALL | re.IGNORECASE)
        ]
    
    def extract_mesh_commands(self, email_content: str) -> List[Dict[str, Any]]:
        """
        Extract mesh commands from email content
        
        Args:
            email_content: The email body text
            
        Returns:
            List of command dictionaries
        """
        commands = []
        
        try:
            # Clean content first
            cleaned_content = self.clean_email_content(email_content)
            
            # Check for broadcast commands
            broadcast_match = self.mesh_command_patterns['broadcast'].search(cleaned_content)
            if broadcast_match:
                commands.append({
                    'type': 'broadcast',
                    'content': broadcast_match.group(1).strip(),
                    'original_match': broadcast_match.group(0)
                })
            
            # Check for tag send commands
            tag_match = self.mesh_command_patterns['tag_send'].search(cleaned_content)
            if tag_match:
                commands.append({
                    'type': 'tag_send',
                    'tag': tag_match.group(1).strip(),
                    'content': tag_match.group(2).strip(),
                    'original_match': tag_match.group(0)
                })
            
            # Check for direct message commands
            dm_match = self.mesh_command_patterns['direct_message'].search(cleaned_content)
            if dm_match:
                commands.append({
                    'type': 'direct_message',
                    'recipient': dm_match.group(1).strip(),
                    'content': dm_match.group(2).strip(),
                    'original_match': dm_match.group(0)
                })
            
            # Check for general mesh commands
            mesh_match = self.mesh_command_patterns['mesh_command'].search(cleaned_content)
            if mesh_match:
                commands.append({
                    'type': 'mesh_command',
                    'command': mesh_match.group(1).strip(),
                    'original_match': mesh_match.group(0)
                })
            
            # If no specific commands found, treat entire content as message
            if not commands:
                commands.append({
                    'type': 'message',
                    'content': cleaned_content,
                    'original_match': cleaned_content
                })
            
        except Exception as e:
            self.logger.error(f"Error extracting mesh commands: {e}")
            # Fallback to treating as simple message
            commands.append({
                'type': 'message',
                'content': email_content,
                'original_match': email_content
            })
        
        return commands
    
    def clean_email_content(self, content: str) -> str:
        """
        Clean email content by removing quotes, signatures, and footers
        
        Args:
            content: Raw email content
            
        Returns:
            Cleaned content
        """
        if not content:
            return ""
        
        try:
            cleaned = content
            
            # Remove quoted content
            for pattern in self.quote_patterns:
                cleaned = pattern.sub('', cleaned)
            
            # Remove signatures
            for pattern in self.signature_patterns:
                cleaned = pattern.sub('', cleaned)
            
            # Remove footers
            for pattern in self.footer_patterns:
                cleaned = pattern.sub('', cleaned)
            
            # Clean up whitespace
            lines = []
            for line in cleaned.split('\n'):
                line = line.strip()
                if line:  # Skip empty lines
                    lines.append(line)
            
            cleaned = '\n'.join(lines)
            
            # Limit length for mesh network
            if len(cleaned) > 500:  # Reasonable limit for mesh messages
                cleaned = cleaned[:497] + "..."
            
            return cleaned.strip()
            
        except Exception as e:
            self.logger.error(f"Error cleaning email content: {e}")
            return content[:500]  # Fallback with length limit
    
    def extract_recipient_from_subject(self, subject: str) -> Optional[str]:
        """
        Extract mesh recipient from email subject line
        
        Args:
            subject: Email subject
            
        Returns:
            Recipient ID if found, None otherwise
        """
        if not subject:
            return None
        
        try:
            # Look for patterns like "To: !12345678" or "For: NodeName"
            patterns = [
                re.compile(r'(?:to|for):\s*(![\da-f]{8})', re.IGNORECASE),
                re.compile(r'(?:to|for):\s*(\w+)', re.IGNORECASE),
                re.compile(r'\[(![\da-f]{8})\]', re.IGNORECASE),
                re.compile(r'\[(\w+)\]', re.IGNORECASE)
            ]
            
            for pattern in patterns:
                match = pattern.search(subject)
                if match:
                    return match.group(1).strip()
            
        except Exception as e:
            self.logger.error(f"Error extracting recipient from subject '{subject}': {e}")
        
        return None
    
    def extract_tags_from_subject(self, subject: str) -> List[str]:
        """
        Extract tags from email subject line
        
        Args:
            subject: Email subject
            
        Returns:
            List of tags found
        """
        tags = []
        
        if not subject:
            return tags
        
        try:
            # Look for hashtag patterns
            hashtag_pattern = re.compile(r'#(\w+)', re.IGNORECASE)
            matches = hashtag_pattern.findall(subject)
            
            for match in matches:
                tags.append(match.lower())
            
            # Look for tag: patterns
            tag_pattern = re.compile(r'tag:\s*(\w+)', re.IGNORECASE)
            matches = tag_pattern.findall(subject)
            
            for match in matches:
                if match.lower() not in tags:
                    tags.append(match.lower())
            
        except Exception as e:
            self.logger.error(f"Error extracting tags from subject '{subject}': {e}")
        
        return tags
    
    def is_broadcast_email(self, email_message: EmailMessage) -> bool:
        """
        Determine if email should be treated as broadcast
        
        Args:
            email_message: The email message
            
        Returns:
            True if should be broadcast
        """
        try:
            # Check subject for broadcast indicators
            subject = (email_message.subject or "").lower()
            broadcast_indicators = ['broadcast', 'all', 'everyone', 'network', 'mesh']
            
            if any(indicator in subject for indicator in broadcast_indicators):
                return True
            
            # Check content for broadcast commands
            commands = self.extract_mesh_commands(email_message.body_text or "")
            return any(cmd['type'] == 'broadcast' for cmd in commands)
            
        except Exception as e:
            self.logger.error(f"Error checking if email is broadcast: {e}")
            return False
    
    def is_authorized_sender(self, email_address: str, authorized_senders: List[str], 
                           authorized_domains: List[str]) -> bool:
        """
        Check if email sender is authorized
        
        Args:
            email_address: Sender email address
            authorized_senders: List of authorized email addresses
            authorized_domains: List of authorized domains
            
        Returns:
            True if sender is authorized
        """
        if not email_address:
            return False
        
        try:
            email_lower = email_address.lower()
            
            # Check exact email match
            if email_lower in [addr.lower() for addr in authorized_senders]:
                return True
            
            # Check domain match
            if '@' in email_address:
                domain = email_address.split('@')[1].lower()
                if domain in [d.lower() for d in authorized_domains]:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking sender authorization for '{email_address}': {e}")
            return False
    
    def detect_spam_content(self, content: str, spam_keywords: List[str]) -> Tuple[bool, List[str]]:
        """
        Detect spam content based on keywords
        
        Args:
            content: Email content to check
            spam_keywords: List of spam keywords
            
        Returns:
            Tuple of (is_spam, matched_keywords)
        """
        if not content or not spam_keywords:
            return False, []
        
        try:
            content_lower = content.lower()
            matched_keywords = []
            
            for keyword in spam_keywords:
                if keyword.lower() in content_lower:
                    matched_keywords.append(keyword)
            
            # Consider spam if multiple keywords match
            is_spam = len(matched_keywords) >= 2
            
            return is_spam, matched_keywords
            
        except Exception as e:
            self.logger.error(f"Error detecting spam content: {e}")
            return False, []
    
    def format_email_for_mesh(self, email_message: EmailMessage, max_length: int = 200) -> str:
        """
        Format email content for mesh network delivery
        
        Args:
            email_message: The email message
            max_length: Maximum message length
            
        Returns:
            Formatted message for mesh
        """
        try:
            # Start with sender info
            sender_name = "Unknown"
            if email_message.from_address:
                sender_name = email_message.from_address.name or email_message.from_address.address
            
            # Create header
            header = f"[Email from {sender_name}]"
            
            # Add subject if available and not too long
            if email_message.subject and len(email_message.subject) < 50:
                header += f" {email_message.subject}"
            
            # Get cleaned content
            content = self.clean_email_content(email_message.body_text or "")
            
            # Calculate available space for content
            available_length = max_length - len(header) - 3  # 3 for " - "
            
            if available_length <= 0:
                return header[:max_length]
            
            # Truncate content if necessary
            if len(content) > available_length:
                content = content[:available_length - 3] + "..."
            
            # Combine header and content
            if content:
                return f"{header} - {content}"
            else:
                return header
            
        except Exception as e:
            self.logger.error(f"Error formatting email for mesh: {e}")
            return f"[Email] Error formatting message"
    
    def extract_mesh_user_mapping(self, email_content: str) -> Optional[Dict[str, str]]:
        """
        Extract mesh user mapping information from email
        
        Args:
            email_content: Email content to parse
            
        Returns:
            Dictionary with mapping info or None
        """
        try:
            # Look for mesh ID patterns in content
            mesh_id_pattern = re.compile(r'mesh\s*id:\s*(![\da-f]{8})', re.IGNORECASE)
            node_name_pattern = re.compile(r'node\s*name:\s*(\w+)', re.IGNORECASE)
            
            mesh_id_match = mesh_id_pattern.search(email_content)
            node_name_match = node_name_pattern.search(email_content)
            
            if mesh_id_match or node_name_match:
                mapping = {}
                if mesh_id_match:
                    mapping['mesh_id'] = mesh_id_match.group(1)
                if node_name_match:
                    mapping['node_name'] = node_name_match.group(1)
                return mapping
            
        except Exception as e:
            self.logger.error(f"Error extracting mesh user mapping: {e}")
        
        return None
    
    def validate_email_content(self, content: str, max_size: int = 1024 * 1024) -> Tuple[bool, Optional[str]]:
        """
        Validate email content for processing
        
        Args:
            content: Email content to validate
            max_size: Maximum content size in bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if not content:
                return False, "Empty content"
            
            # Check size
            content_bytes = content.encode('utf-8')
            if len(content_bytes) > max_size:
                return False, f"Content too large ({len(content_bytes)} bytes, max {max_size})"
            
            # Check for suspicious patterns
            suspicious_patterns = [
                re.compile(r'<script.*?</script>', re.IGNORECASE | re.DOTALL),
                re.compile(r'javascript:', re.IGNORECASE),
                re.compile(r'data:.*base64', re.IGNORECASE)
            ]
            
            for pattern in suspicious_patterns:
                if pattern.search(content):
                    return False, "Suspicious content detected"
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Error validating email content: {e}")
            return False, f"Validation error: {e}"