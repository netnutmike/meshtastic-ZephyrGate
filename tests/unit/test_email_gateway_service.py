"""
Unit tests for Email Gateway Service

Tests the core email gateway functionality including SMTP/IMAP clients,
message processing, security features, and command handling.
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json

from src.services.email.email_service import EmailGatewayService
from src.services.email.models import (
    EmailMessage, EmailAddress, EmailConfiguration, EmailDirection,
    EmailStatus, EmailPriority, BlocklistEntry, UserEmailMapping
)
from src.models.message import Message, MessageType


class TestEmailGatewayService:
    """Test cases for EmailGatewayService"""
    
    @pytest.fixture
    def email_config(self):
        """Create test email configuration"""
        return {
            'email': {
                'smtp_host': 'smtp.test.com',
                'smtp_port': 587,
                'smtp_username': 'test@test.com',
                'smtp_password': 'password',
                'smtp_use_tls': True,
                'imap_host': 'imap.test.com',
                'imap_port': 993,
                'imap_username': 'test@test.com',
                'imap_password': 'password',
                'imap_use_ssl': True,
                'gateway_email': 'gateway@test.com',
                'gateway_name': 'Test Gateway',
                'enable_blocklist': True,
                'enable_sender_verification': True,
                'authorized_senders': ['admin@test.com'],
                'authorized_domains': ['test.com'],
                'enable_broadcasts': True,
                'broadcast_authorized_senders': ['admin@test.com'],
                'enable_tag_messaging': True
            },
            'admin_users': ['!12345678']
        }
    
    @pytest.fixture
    def mock_plugin_manager(self):
        """Create mock plugin manager"""
        manager = Mock()
        manager.register_message_handler = AsyncMock()
        manager.register_command_handler = AsyncMock()
        return manager
    
    @pytest_asyncio.fixture
    async def email_service(self, email_config, mock_plugin_manager):
        """Create EmailGatewayService instance"""
        service = EmailGatewayService("email_gateway", email_config, mock_plugin_manager)
        
        # Mock the email clients to avoid actual connections
        with patch('src.services.email.email_service.SMTPClient') as mock_smtp, \
             patch('src.services.email.email_service.IMAPClient') as mock_imap:
            
            mock_smtp_instance = AsyncMock()
            mock_imap_instance = AsyncMock()
            mock_smtp.return_value = mock_smtp_instance
            mock_imap.return_value = mock_imap_instance
            
            service.smtp_client = mock_smtp_instance
            service.imap_client = mock_imap_instance
            
            await service.initialize()
            yield service
            
            if service.is_running:
                await service.stop()
            await service.cleanup()
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, email_service):
        """Test service initialization"""
        assert email_service.email_config.smtp_host == 'smtp.test.com'
        assert email_service.email_config.gateway_email == 'gateway@test.com'
        assert email_service.smtp_client is not None
        assert email_service.imap_client is not None
    
    @pytest.mark.asyncio
    async def test_service_start_stop(self, email_service):
        """Test service start and stop"""
        # Start service
        assert await email_service.start()
        assert email_service.is_running
        
        # Stop service
        assert await email_service.stop()
        assert not email_service.is_running
    
    @pytest.mark.asyncio
    async def test_user_email_management(self, email_service):
        """Test user email address management"""
        user_id = "!12345678"
        email = "user@test.com"
        
        # Set user email
        result = await email_service.set_user_email(user_id, email)
        assert "✅" in result
        assert user_id in email_service.user_mappings
        assert email_service.user_mappings[user_id].email_address == email
        
        # Clear user email
        result = await email_service.clear_user_email(user_id)
        assert "✅" in result
        assert user_id not in email_service.user_mappings
    
    @pytest.mark.asyncio
    async def test_tag_management(self, email_service):
        """Test user tag management"""
        user_id = "!12345678"
        tag = "emergency"
        
        # Add tag
        result = await email_service.add_user_tag(user_id, tag)
        assert "✅" in result
        assert user_id in email_service.user_mappings
        assert email_service.user_mappings[user_id].has_tag(tag)
        
        # Remove tag
        result = await email_service.remove_user_tag(user_id, tag)
        assert "✅" in result
        assert not email_service.user_mappings[user_id].has_tag(tag)
    
    @pytest.mark.asyncio
    async def test_email_send_command_parsing(self, email_service):
        """Test email send command parsing"""
        # Create test message
        message = Message(
            sender_id="!12345678",
            content="email/test@example.com/Test Subject/Test message body",
            message_type=MessageType.TEXT
        )
        
        # Mock SMTP client
        email_service.smtp_client.send_email = AsyncMock(return_value=True)
        
        result = await email_service.handle_email_send_command(message)
        assert "✅" in result
        assert "queued for delivery" in result
    
    @pytest.mark.asyncio
    async def test_email_send_validation(self, email_service):
        """Test email send validation"""
        user_id = "!12345678"
        
        # Test invalid email format
        is_valid, error = await email_service.validate_email_send_request(
            user_id, "invalid-email", "Subject", "Body"
        )
        assert not is_valid
        assert "Invalid email address format" in error
        
        # Test valid email
        is_valid, error = await email_service.validate_email_send_request(
            user_id, "test@example.com", "Subject", "Body"
        )
        assert is_valid
        assert error is None
    
    @pytest.mark.asyncio
    async def test_blocklist_management(self, email_service):
        """Test email blocklist management"""
        admin_user = "!12345678"  # Admin user from config
        email_to_block = "spam@example.com"
        
        # Test block command
        message = Message(
            sender_id=admin_user,
            content=f"block/{email_to_block}/Spam sender",
            message_type=MessageType.TEXT
        )
        
        result = await email_service.handle_block_command(message, admin_user)
        assert "✅" in result
        assert email_to_block in [entry.email_pattern for entry in email_service.blocklist.values()]
        
        # Test unblock command
        message = Message(
            sender_id=admin_user,
            content=f"unblock/{email_to_block}",
            message_type=MessageType.TEXT
        )
        
        result = await email_service.handle_unblock_command(message, admin_user)
        assert "✅" in result
        assert email_to_block not in [entry.email_pattern for entry in email_service.blocklist.values()]
    
    @pytest.mark.asyncio
    async def test_blocklist_security(self, email_service):
        """Test blocklist security enforcement"""
        # Add email to blocklist
        await email_service.add_to_blocklist("blocked@example.com", "Test block")
        
        # Test if email is blocked
        is_blocked = await email_service._is_email_blocked("blocked@example.com")
        assert is_blocked
        
        # Test if non-blocked email passes
        is_blocked = await email_service._is_email_blocked("allowed@example.com")
        assert not is_blocked
    
    @pytest.mark.asyncio
    async def test_sender_authorization(self, email_service):
        """Test sender authorization"""
        # Create authorized email message
        authorized_email = EmailMessage()
        authorized_email.from_address = EmailAddress.parse("admin@test.com")
        
        is_authorized = await email_service._is_sender_authorized(authorized_email)
        assert is_authorized
        
        # Create unauthorized email message
        unauthorized_email = EmailMessage()
        unauthorized_email.from_address = EmailAddress.parse("spam@badsite.com")
        
        is_authorized = await email_service._is_sender_authorized(unauthorized_email)
        assert not is_authorized
    
    @pytest.mark.asyncio
    async def test_spam_detection(self, email_service):
        """Test spam content detection"""
        # Create email with spam content
        spam_email = EmailMessage()
        spam_email.subject = "Urgent! Act now! Free money!"
        spam_email.body_text = "Click here for free money! Limited time offer!"
        
        is_spam = await email_service._is_spam_content(spam_email)
        assert is_spam
        
        # Create normal email
        normal_email = EmailMessage()
        normal_email.subject = "Meeting tomorrow"
        normal_email.body_text = "Don't forget about our meeting tomorrow at 2 PM."
        
        is_spam = await email_service._is_spam_content(normal_email)
        assert not is_spam
    
    @pytest.mark.asyncio
    async def test_broadcast_authorization(self, email_service):
        """Test broadcast authorization"""
        # Test authorized broadcaster
        is_authorized = await email_service._is_broadcast_authorized("admin@test.com")
        assert is_authorized
        
        # Test unauthorized broadcaster
        is_authorized = await email_service._is_broadcast_authorized("user@example.com")
        assert not is_authorized
    
    @pytest.mark.asyncio
    async def test_mesh_to_email_processing(self, email_service):
        """Test mesh-to-email message processing"""
        # Create mesh-to-email message
        email_message = EmailMessage()
        email_message.direction = EmailDirection.MESH_TO_EMAIL
        email_message.from_address = EmailAddress.parse("gateway@test.com")
        email_message.to_addresses = [EmailAddress.parse("user@example.com")]
        email_message.subject = "Test message"
        email_message.body_text = "Test body"
        
        # Mock SMTP client success
        email_service.smtp_client.send_email = AsyncMock(return_value=True)
        
        success = await email_service._process_mesh_to_email(email_message)
        assert success
        assert email_service.smtp_client.send_email.called
    
    @pytest.mark.asyncio
    async def test_email_to_mesh_processing(self, email_service):
        """Test email-to-mesh message processing"""
        # Create authorized email-to-mesh message
        email_message = EmailMessage()
        email_message.direction = EmailDirection.EMAIL_TO_MESH
        email_message.from_address = EmailAddress.parse("admin@test.com")
        email_message.body_text = "broadcast: Test broadcast message"
        
        # Mock communication interface
        email_service.comm = AsyncMock()
        email_service.comm.send_mesh_message = AsyncMock(return_value=True)
        
        success = await email_service._process_email_to_mesh(email_message)
        assert success
        assert email_service.comm.send_mesh_message.called
    
    @pytest.mark.asyncio
    async def test_broadcast_processing(self, email_service):
        """Test broadcast email processing"""
        # Set up test users
        email_service.user_mappings["!user1"] = UserEmailMapping(
            mesh_user_id="!user1",
            email_address="user1@test.com",
            receive_broadcasts=True
        )
        email_service.user_mappings["!user2"] = UserEmailMapping(
            mesh_user_id="!user2",
            email_address="user2@test.com",
            receive_broadcasts=True
        )
        
        # Create broadcast email
        email_message = EmailMessage()
        email_message.direction = EmailDirection.BROADCAST
        email_message.from_address = EmailAddress.parse("admin@test.com")
        email_message.subject = "Network Broadcast"
        email_message.body_text = "Important network message"
        
        # Mock SMTP client
        email_service.smtp_client.send_email = AsyncMock(return_value=True)
        
        success = await email_service._process_broadcast_email(email_message)
        assert success
        assert email_service.smtp_client.send_email.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_tag_group_messaging(self, email_service):
        """Test tag-based group messaging"""
        # Set up test users with tags
        email_service.user_mappings["!user1"] = UserEmailMapping(
            mesh_user_id="!user1",
            email_address="user1@test.com",
            receive_group_messages=True,
            tags=["emergency"]
        )
        email_service.user_mappings["!user2"] = UserEmailMapping(
            mesh_user_id="!user2",
            email_address="user2@test.com",
            receive_group_messages=True,
            tags=["emergency", "admin"]
        )
        
        # Test tag send command
        message = Message(
            sender_id="!admin",
            content="tagsend/emergency/Emergency drill at 3 PM",
            message_type=MessageType.TEXT
        )
        
        # Mock SMTP client
        email_service.smtp_client.send_email = AsyncMock(return_value=True)
        
        result = await email_service.handle_tag_send_command(message, "!admin")
        assert "✅" in result
        assert "2 users" in result
    
    @pytest.mark.asyncio
    async def test_queue_management(self, email_service):
        """Test email queue management"""
        # Create test email message
        email_message = EmailMessage()
        email_message.direction = EmailDirection.MESH_TO_EMAIL
        email_message.to_addresses = [EmailAddress.parse("test@example.com")]
        email_message.body_text = "Test message"
        
        # Queue message
        success = await email_service.queue_email_message(email_message)
        assert success
        assert email_service.message_queue.qsize() > 0
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, email_service):
        """Test statistics tracking"""
        # Get initial statistics
        stats = email_service.get_service_statistics()
        assert 'service' in stats
        assert 'queue' in stats
        assert 'messages' in stats
        assert 'security' in stats
        
        # Verify statistics structure
        assert stats['service']['is_running'] == email_service.is_running
        assert stats['queue']['current_size'] >= 0
        assert stats['messages']['total_processed'] >= 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, email_service):
        """Test error handling in various scenarios"""
        # Test invalid email command
        message = Message(
            sender_id="!12345678",
            content="email/invalid-format",
            message_type=MessageType.TEXT
        )
        
        result = await email_service.handle_email_send_command(message)
        assert "❌" in result
        assert "Invalid email format" in result
        
        # Test unauthorized block command
        message = Message(
            sender_id="!unauthorized",
            content="block/spam@example.com",
            message_type=MessageType.TEXT
        )
        
        result = await email_service.handle_block_command(message, "!unauthorized")
        assert "❌" in result
        assert "Only administrators" in result
    
    @pytest.mark.asyncio
    async def test_configuration_validation(self, email_config):
        """Test configuration validation"""
        # Test valid configuration
        config = EmailConfiguration()
        config.smtp_host = "smtp.test.com"
        config.smtp_username = "test@test.com"
        config.smtp_password = "password"
        config.imap_host = "imap.test.com"
        config.imap_username = "test@test.com"
        config.imap_password = "password"
        config.gateway_email = "gateway@test.com"
        
        errors = config.validate()
        assert len(errors) == 0
        
        # Test invalid configuration
        invalid_config = EmailConfiguration()
        errors = invalid_config.validate()
        assert len(errors) > 0
        assert any("SMTP host is required" in error for error in errors)


class TestEmailModels:
    """Test cases for email data models"""
    
    def test_email_address_parsing(self):
        """Test EmailAddress parsing"""
        # Test simple email
        addr = EmailAddress.parse("test@example.com")
        assert addr.address == "test@example.com"
        assert addr.name is None
        
        # Test email with name
        addr = EmailAddress.parse("John Doe <john@example.com>")
        assert addr.address == "john@example.com"
        assert addr.name == "John Doe"
    
    def test_email_message_creation(self):
        """Test EmailMessage creation and methods"""
        email = EmailMessage()
        email.from_address = EmailAddress.parse("sender@test.com")
        email.to_addresses = [EmailAddress.parse("recipient@test.com")]
        email.subject = "Test Subject"
        email.body_text = "Test Body"
        
        assert email.direction == EmailDirection.MESH_TO_EMAIL
        assert email.status == EmailStatus.PENDING
        assert email.priority == EmailPriority.NORMAL
        
        # Test error handling
        email.add_error("Test error", "test_type")
        assert email.last_error == "Test error"
        assert len(email.error_history) == 1
    
    def test_blocklist_entry_matching(self):
        """Test BlocklistEntry matching logic"""
        # Test exact match
        entry = BlocklistEntry(email_pattern="spam@example.com")
        assert entry.matches("spam@example.com")
        assert not entry.matches("user@example.com")
        
        # Test domain match
        entry = BlocklistEntry(email_pattern="@badsite.com")
        assert entry.matches("anyone@badsite.com")
        assert not entry.matches("user@goodsite.com")
        
        # Test wildcard match
        entry = BlocklistEntry(email_pattern="spam*@example.com")
        assert entry.matches("spam123@example.com")
        assert entry.matches("spammer@example.com")
        assert not entry.matches("user@example.com")
    
    def test_user_email_mapping(self):
        """Test UserEmailMapping functionality"""
        mapping = UserEmailMapping(
            mesh_user_id="!12345678",
            email_address="user@test.com"
        )
        
        # Test tag management
        mapping.add_tag("emergency")
        assert mapping.has_tag("emergency")
        assert mapping.has_tag("EMERGENCY")  # Case insensitive
        
        mapping.remove_tag("emergency")
        assert not mapping.has_tag("emergency")


class TestEmailParser:
    """Test cases for email content parsing"""
    
    @pytest.fixture
    def parser(self):
        """Create EmailParser instance"""
        from src.services.email.email_parser import EmailParser
        return EmailParser()
    
    def test_mesh_command_extraction(self, parser):
        """Test mesh command extraction from email content"""
        # Test broadcast command
        content = "broadcast: This is a network broadcast message"
        commands = parser.extract_mesh_commands(content)
        assert len(commands) == 1
        assert commands[0]['type'] == 'broadcast'
        assert commands[0]['content'] == 'This is a network broadcast message'
        
        # Test tag send command
        content = "tag: emergency This is an emergency message"
        commands = parser.extract_mesh_commands(content)
        assert len(commands) == 1
        assert commands[0]['type'] == 'tag_send'
        assert commands[0]['tag'] == 'emergency'
        assert commands[0]['content'] == 'This is an emergency message'
    
    def test_content_cleaning(self, parser):
        """Test email content cleaning"""
        # Test quoted content removal
        content = """This is the main message.

On 2024-01-01, someone wrote:
> This is quoted content
> That should be removed

Best regards,
John"""
        
        cleaned = parser.clean_email_content(content)
        assert "This is the main message." in cleaned
        assert "quoted content" not in cleaned
        assert "Best regards" not in cleaned
    
    def test_recipient_extraction(self, parser):
        """Test recipient extraction from subject"""
        # Test mesh ID extraction
        subject = "To: !12345678 - Important message"
        recipient = parser.extract_recipient_from_subject(subject)
        assert recipient == "!12345678"
        
        # Test name extraction
        subject = "For: NodeName - Test message"
        recipient = parser.extract_recipient_from_subject(subject)
        assert recipient == "NodeName"
    
    def test_tag_extraction(self, parser):
        """Test tag extraction from subject"""
        subject = "Emergency message #emergency #urgent"
        tags = parser.extract_tags_from_subject(subject)
        assert "emergency" in tags
        assert "urgent" in tags
    
    def test_spam_detection(self, parser):
        """Test spam content detection"""
        spam_keywords = ['urgent', 'free', 'winner', 'click here']
        
        # Test spam content
        spam_content = "URGENT! You are a winner! Click here for free money!"
        is_spam, matched = parser.detect_spam_content(spam_content, spam_keywords)
        assert is_spam
        assert len(matched) >= 2
        
        # Test normal content
        normal_content = "Meeting scheduled for tomorrow at 2 PM"
        is_spam, matched = parser.detect_spam_content(normal_content, spam_keywords)
        assert not is_spam
    
    def test_email_formatting(self, parser):
        """Test email formatting for mesh delivery"""
        email = EmailMessage()
        email.from_address = EmailAddress(address="sender@test.com", name="John Doe")
        email.subject = "Test Subject"
        email.body_text = "This is a test message for the mesh network."
        
        formatted = parser.format_email_for_mesh(email, max_length=100)
        assert "John Doe" in formatted
        assert "test message" in formatted
        assert len(formatted) <= 100


if __name__ == "__main__":
    pytest.main([__file__])