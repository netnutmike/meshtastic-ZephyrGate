"""
Basic functionality tests for Email Gateway Service

Simple tests to verify core email gateway functionality without complex mocking.
"""

import asyncio
import pytest
import tempfile
import os
from unittest.mock import Mock, AsyncMock

from src.services.email.email_service import EmailGatewayService
from src.services.email.models import EmailMessage, EmailAddress, EmailDirection
from src.models.message import Message, MessageType


class TestEmailBasicFunctionality:
    """Basic functionality tests"""
    
    def test_email_address_parsing(self):
        """Test email address parsing"""
        # Simple email
        addr = EmailAddress.parse("test@example.com")
        assert addr.address == "test@example.com"
        assert addr.name is None
        
        # Email with name
        addr = EmailAddress.parse("John Doe <john@example.com>")
        assert addr.address == "john@example.com"
        assert addr.name == "John Doe"
    
    def test_email_message_creation(self):
        """Test email message creation"""
        email = EmailMessage()
        email.from_address = EmailAddress.parse("sender@test.com")
        email.to_addresses = [EmailAddress.parse("recipient@test.com")]
        email.subject = "Test Subject"
        email.body_text = "Test Body"
        
        assert email.direction == EmailDirection.MESH_TO_EMAIL
        assert len(email.to_addresses) == 1
        assert email.to_addresses[0].address == "recipient@test.com"
    
    def test_email_parser_commands(self):
        """Test email parser command extraction"""
        from src.services.email.email_parser import EmailParser
        parser = EmailParser()
        
        # Test broadcast command
        commands = parser.extract_mesh_commands("broadcast: This is a network broadcast")
        assert len(commands) == 1
        assert commands[0]['type'] == 'broadcast'
        assert commands[0]['content'] == 'This is a network broadcast'
        
        # Test tag command
        commands = parser.extract_mesh_commands("tag: emergency This is an emergency message")
        assert len(commands) == 1
        assert commands[0]['type'] == 'tag_send'
        assert commands[0]['tag'] == 'emergency'
        assert commands[0]['content'] == 'This is an emergency message'
    
    def test_email_content_cleaning(self):
        """Test email content cleaning"""
        from src.services.email.email_parser import EmailParser
        parser = EmailParser()
        
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
    
    def test_spam_detection(self):
        """Test spam detection"""
        from src.services.email.email_parser import EmailParser
        parser = EmailParser()
        
        spam_keywords = ['urgent', 'free', 'winner', 'click here']
        
        # Test spam content
        is_spam, matched = parser.detect_spam_content(
            "URGENT! You are a winner! Click here for free money!", 
            spam_keywords
        )
        assert is_spam
        assert len(matched) >= 2
        
        # Test normal content
        is_spam, matched = parser.detect_spam_content(
            "Meeting scheduled for tomorrow at 2 PM", 
            spam_keywords
        )
        assert not is_spam
    
    def test_blocklist_matching(self):
        """Test blocklist entry matching"""
        from src.services.email.models import BlocklistEntry
        
        # Test exact match
        entry = BlocklistEntry(email_pattern="spam@example.com")
        assert entry.matches("spam@example.com")
        assert not entry.matches("user@example.com")
        
        # Test domain match
        entry = BlocklistEntry(email_pattern="@badsite.com")
        assert entry.matches("anyone@badsite.com")
        assert not entry.matches("user@goodsite.com")
    
    def test_user_mapping_tags(self):
        """Test user email mapping tag functionality"""
        from src.services.email.models import UserEmailMapping
        
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
    
    @pytest.mark.asyncio
    async def test_service_configuration(self):
        """Test service configuration loading"""
        config = {
            'email': {
                'smtp_host': 'smtp.test.com',
                'smtp_port': 587,
                'smtp_username': 'test@test.com',
                'smtp_password': 'password',
                'gateway_email': 'gateway@test.com',
                'enable_blocklist': True,
                'authorized_senders': ['admin@test.com']
            }
        }
        
        mock_plugin_manager = Mock()
        mock_plugin_manager.register_message_handler = AsyncMock()
        mock_plugin_manager.register_command_handler = AsyncMock()
        
        service = EmailGatewayService("email_gateway", config, mock_plugin_manager)
        
        # Check configuration loading
        assert service.email_config.smtp_host == 'smtp.test.com'
        assert service.email_config.gateway_email == 'gateway@test.com'
        assert service.email_config.enable_blocklist == True
        assert 'admin@test.com' in service.email_config.authorized_senders
    
    @pytest.mark.asyncio
    async def test_user_email_management(self):
        """Test user email management without full service initialization"""
        config = {
            'email': {
                'smtp_host': 'smtp.test.com',
                'gateway_email': 'gateway@test.com'
            }
        }
        
        mock_plugin_manager = Mock()
        service = EmailGatewayService("email_gateway", config, mock_plugin_manager)
        
        # Test setting user email
        result = await service.set_user_email("!12345678", "user@test.com")
        assert "✅" in result
        assert "!12345678" in service.user_mappings
        
        # Test clearing user email
        result = await service.clear_user_email("!12345678")
        assert "✅" in result
        assert "!12345678" not in service.user_mappings
    
    @pytest.mark.asyncio
    async def test_tag_management(self):
        """Test tag management functionality"""
        config = {
            'email': {
                'smtp_host': 'smtp.test.com',
                'gateway_email': 'gateway@test.com'
            }
        }
        
        mock_plugin_manager = Mock()
        service = EmailGatewayService("email_gateway", config, mock_plugin_manager)
        
        # Test adding tag
        result = await service.add_user_tag("!12345678", "emergency")
        assert "✅" in result
        assert service.user_mappings["!12345678"].has_tag("emergency")
        
        # Test removing tag
        result = await service.remove_user_tag("!12345678", "emergency")
        assert "✅" in result
        assert not service.user_mappings["!12345678"].has_tag("emergency")
    
    @pytest.mark.asyncio
    async def test_email_validation(self):
        """Test email validation functionality"""
        config = {
            'email': {
                'smtp_host': 'smtp.test.com',
                'gateway_email': 'gateway@test.com',
                'max_message_size': 1024
            }
        }
        
        mock_plugin_manager = Mock()
        service = EmailGatewayService("email_gateway", config, mock_plugin_manager)
        service.is_running = True
        
        # Mock SMTP client
        service.smtp_client = Mock()
        service.smtp_client.is_connected = True
        
        # Test valid email
        is_valid, error = await service.validate_email_send_request(
            "!12345678", "test@example.com", "Subject", "Body"
        )
        assert is_valid
        assert error is None
        
        # Test invalid email format
        is_valid, error = await service.validate_email_send_request(
            "!12345678", "invalid-email", "Subject", "Body"
        )
        assert not is_valid
        assert "Invalid email address format" in error
    
    def test_email_help_generation(self):
        """Test email help text generation"""
        config = {
            'email': {
                'smtp_host': 'smtp.test.com',
                'gateway_email': 'gateway@test.com'
            }
        }
        
        mock_plugin_manager = Mock()
        service = EmailGatewayService("email_gateway", config, mock_plugin_manager)
        
        # Test help generation
        help_text = asyncio.run(service.get_email_help())
        assert "📧 Email Gateway Help:" in help_text
        assert "email/to@domain.com/subject/message" in help_text
        assert "tagin/tagname" in help_text
        assert "broadcast/message" in help_text


if __name__ == "__main__":
    pytest.main([__file__])