"""
Integration tests for Email Gateway Service

Tests the complete email gateway functionality including SMTP/IMAP integration,
message flow, security enforcement, and cross-service communication.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import tempfile
import os
import json

from src.services.email.email_service import EmailGatewayService
from src.services.email.smtp_client import SMTPClient
from src.services.email.imap_client import IMAPClient
from src.services.email.models import (
    EmailMessage, EmailAddress, EmailConfiguration, EmailDirection,
    EmailStatus, EmailPriority, BlocklistEntry, UserEmailMapping
)
from src.models.message import Message, MessageType


class TestEmailGatewayIntegration:
    """Integration tests for complete email gateway functionality"""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def integration_config(self, temp_data_dir):
        """Create integration test configuration"""
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
                'authorized_senders': ['admin@test.com', 'user@test.com'],
                'authorized_domains': ['test.com'],
                'enable_broadcasts': True,
                'broadcast_authorized_senders': ['admin@test.com'],
                'enable_tag_messaging': True,
                'data_directory': temp_data_dir,
                'queue_max_size': 100,
                'max_message_size': 1024 * 1024,
                'spam_keywords': ['spam', 'urgent', 'free', 'winner']
            },
            'admin_users': ['!admin123']
        }
    
    @pytest.fixture
    def mock_plugin_manager(self):
        """Create mock plugin manager"""
        manager = Mock()
        manager.register_message_handler = AsyncMock()
        manager.register_command_handler = AsyncMock()
        return manager
    
    @pytest.fixture
    def mock_communication_interface(self):
        """Create mock communication interface"""
        comm = AsyncMock()
        comm.send_mesh_message = AsyncMock(return_value=True)
        return comm
    
    @pytest.fixture
    async def email_gateway(self, integration_config, mock_plugin_manager, mock_communication_interface):
        """Create fully configured email gateway service"""
        service = EmailGatewayService("email_gateway", integration_config, mock_plugin_manager)
        
        # Mock email clients to avoid actual network connections
        with patch('src.services.email.email_service.SMTPClient') as mock_smtp_class, \
             patch('src.services.email.email_service.IMAPClient') as mock_imap_class:
            
            # Create mock instances
            mock_smtp = AsyncMock()
            mock_imap = AsyncMock()
            mock_smtp_class.return_value = mock_smtp
            mock_imap_class.return_value = mock_imap
            
            # Configure mock behavior
            mock_smtp.start = AsyncMock()
            mock_smtp.stop = AsyncMock()
            mock_smtp.send_email = AsyncMock(return_value=True)
            mock_smtp.is_connected = True
            mock_smtp.get_statistics = Mock(return_value={'emails_sent': 0})
            
            mock_imap.start = AsyncMock()
            mock_imap.stop = AsyncMock()
            mock_imap.add_message_callback = Mock()
            mock_imap.is_monitoring = False
            mock_imap.get_statistics = Mock(return_value={'emails_processed': 0})
            
            # Initialize and start service
            await service.initialize()
            service.set_communication_interface(mock_communication_interface)
            await service.start()
            
            yield service
            
            # Cleanup
            await service.stop()
            await service.cleanup()
    
    @pytest.mark.asyncio
    async def test_complete_mesh_to_email_flow(self, email_gateway, mock_communication_interface):
        """Test complete mesh-to-email message flow"""
        # Set up user mapping
        user_id = "!user123"
        await email_gateway.set_user_email(user_id, "user@test.com")
        
        # Create mesh message requesting email send
        mesh_message = Message(
            sender_id=user_id,
            content="email/recipient@example.com/Test Subject/Hello from mesh network!",
            message_type=MessageType.TEXT,
            channel=0
        )
        
        # Process the command
        result = await email_gateway.handle_email_send_command(mesh_message)
        
        # Verify success
        assert "✅" in result
        assert "queued for delivery" in result
        
        # Verify queue has message
        assert email_gateway.message_queue.qsize() > 0
        
        # Process the queue (simulate background processing)
        queue_item = await email_gateway.message_queue.get()
        success = await email_gateway._process_mesh_to_email(queue_item.email_message)
        
        # Verify processing
        assert success
        assert email_gateway.smtp_client.send_email.called
        
        # Verify confirmation was sent back to mesh
        assert mock_communication_interface.send_mesh_message.called
    
    @pytest.mark.asyncio
    async def test_complete_email_to_mesh_flow(self, email_gateway, mock_communication_interface):
        """Test complete email-to-mesh message flow"""
        # Create incoming email message
        email_message = EmailMessage()
        email_message.direction = EmailDirection.EMAIL_TO_MESH
        email_message.from_address = EmailAddress.parse("admin@test.com")
        email_message.subject = "Network Broadcast"
        email_message.body_text = "broadcast: Important network announcement"
        
        # Process the email
        success = await email_gateway._process_email_to_mesh(email_message)
        
        # Verify success
        assert success
        
        # Verify mesh message was sent
        assert mock_communication_interface.send_mesh_message.called
        
        # Verify message content
        call_args = mock_communication_interface.send_mesh_message.call_args
        sent_message = call_args[0][0]
        assert "Important network announcement" in sent_message.content
    
    @pytest.mark.asyncio
    async def test_broadcast_distribution_flow(self, email_gateway):
        """Test broadcast message distribution flow"""
        # Set up multiple users for broadcast
        users = [
            ("!user1", "user1@test.com"),
            ("!user2", "user2@test.com"),
            ("!user3", "user3@test.com")
        ]
        
        for user_id, email in users:
            await email_gateway.set_user_email(user_id, email)
            # Enable broadcasts for all users
            email_gateway.user_mappings[user_id].receive_broadcasts = True
        
        # Create broadcast email
        email_message = EmailMessage()
        email_message.direction = EmailDirection.BROADCAST
        email_message.from_address = EmailAddress.parse("admin@test.com")
        email_message.subject = "Network Broadcast"
        email_message.body_text = "Important announcement for all users"
        
        # Process broadcast
        success = await email_gateway._process_broadcast_email(email_message)
        
        # Verify success
        assert success
        
        # Verify SMTP client was called for each user
        assert email_gateway.smtp_client.send_email.call_count >= len(users)
    
    @pytest.mark.asyncio
    async def test_tag_based_messaging_flow(self, email_gateway):
        """Test tag-based group messaging flow"""
        # Set up users with different tags
        users_tags = [
            ("!user1", "user1@test.com", ["emergency", "admin"]),
            ("!user2", "user2@test.com", ["emergency"]),
            ("!user3", "user3@test.com", ["general"]),
        ]
        
        for user_id, email, tags in users_tags:
            await email_gateway.set_user_email(user_id, email)
            mapping = email_gateway.user_mappings[user_id]
            mapping.receive_group_messages = True
            for tag in tags:
                mapping.add_tag(tag)
        
        # Send message to emergency tag
        sender_id = "!admin123"
        message = Message(
            sender_id=sender_id,
            content="tagsend/emergency/Emergency drill at 3 PM today",
            message_type=MessageType.TEXT
        )
        
        result = await email_gateway.handle_tag_send_command(message, sender_id)
        
        # Verify success
        assert "✅" in result
        assert "2 users" in result  # user1 and user2 have emergency tag
        
        # Verify queue has message
        assert email_gateway.message_queue.qsize() > 0
    
    @pytest.mark.asyncio
    async def test_security_enforcement_flow(self, email_gateway):
        """Test security enforcement throughout the flow"""
        # Add email to blocklist
        await email_gateway.add_to_blocklist("blocked@spam.com", "Known spammer")
        
        # Test blocked sender
        blocked_email = EmailMessage()
        blocked_email.direction = EmailDirection.EMAIL_TO_MESH
        blocked_email.from_address = EmailAddress.parse("blocked@spam.com")
        blocked_email.body_text = "This should be blocked"
        
        success = await email_gateway._process_email_to_mesh(blocked_email)
        assert not success
        
        # Test unauthorized sender
        unauthorized_email = EmailMessage()
        unauthorized_email.direction = EmailDirection.EMAIL_TO_MESH
        unauthorized_email.from_address = EmailAddress.parse("hacker@badsite.com")
        unauthorized_email.body_text = "broadcast: Unauthorized broadcast"
        
        success = await email_gateway._process_email_to_mesh(unauthorized_email)
        assert not success
        
        # Test spam content
        spam_email = EmailMessage()
        spam_email.direction = EmailDirection.EMAIL_TO_MESH
        spam_email.from_address = EmailAddress.parse("admin@test.com")  # Authorized sender
        spam_email.body_text = "URGENT! Free money! You are a winner!"
        
        success = await email_gateway._process_email_to_mesh(spam_email)
        assert not success
    
    @pytest.mark.asyncio
    async def test_admin_commands_flow(self, email_gateway):
        """Test administrative commands flow"""
        admin_user = "!admin123"
        
        # Test block command
        block_message = Message(
            sender_id=admin_user,
            content="block/spammer@badsite.com/Known spammer",
            message_type=MessageType.TEXT
        )
        
        result = await email_gateway.handle_block_command(block_message, admin_user)
        assert "✅" in result
        
        # Verify blocklist was updated
        assert any(entry.email_pattern == "spammer@badsite.com" 
                  for entry in email_gateway.blocklist.values())
        
        # Test blocklist status
        result = await email_gateway.get_blocklist_status(admin_user)
        assert "📋" in result
        assert "spammer@badsite.com" in result
        
        # Test unblock command
        unblock_message = Message(
            sender_id=admin_user,
            content="unblock/spammer@badsite.com",
            message_type=MessageType.TEXT
        )
        
        result = await email_gateway.handle_unblock_command(unblock_message, admin_user)
        assert "✅" in result
        
        # Verify removal from blocklist
        assert not any(entry.email_pattern == "spammer@badsite.com" 
                      for entry in email_gateway.blocklist.values())
    
    @pytest.mark.asyncio
    async def test_data_persistence_flow(self, email_gateway, temp_data_dir):
        """Test data persistence and recovery"""
        # Add user mappings
        await email_gateway.set_user_email("!user1", "user1@test.com")
        await email_gateway.add_user_tag("!user1", "emergency")
        
        # Add blocklist entry
        await email_gateway.add_to_blocklist("spam@example.com", "Test block")
        
        # Verify data files were created
        mappings_file = os.path.join(temp_data_dir, "user_mappings.json")
        blocklist_file = os.path.join(temp_data_dir, "blocklist.json")
        
        assert os.path.exists(mappings_file)
        assert os.path.exists(blocklist_file)
        
        # Verify file contents
        with open(mappings_file, 'r') as f:
            mappings_data = json.load(f)
            assert "!user1" in mappings_data
            assert mappings_data["!user1"]["email_address"] == "user1@test.com"
            assert "emergency" in mappings_data["!user1"]["tags"]
        
        with open(blocklist_file, 'r') as f:
            blocklist_data = json.load(f)
            assert any(entry["email_pattern"] == "spam@example.com" 
                      for entry in blocklist_data.values())
    
    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, email_gateway):
        """Test error handling and recovery"""
        # Test SMTP failure recovery
        email_gateway.smtp_client.send_email = AsyncMock(return_value=False)
        
        email_message = EmailMessage()
        email_message.direction = EmailDirection.MESH_TO_EMAIL
        email_message.to_addresses = [EmailAddress.parse("test@example.com")]
        email_message.body_text = "Test message"
        
        # First attempt should fail
        success = await email_gateway._process_mesh_to_email(email_message)
        assert not success
        
        # Message should be marked for retry if within retry limits
        if email_message.can_retry():
            assert email_message.status == EmailStatus.RETRY
        else:
            assert email_message.status == EmailStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_queue_processing_flow(self, email_gateway):
        """Test queue processing and management"""
        # Queue multiple messages
        messages = []
        for i in range(5):
            email_message = EmailMessage()
            email_message.direction = EmailDirection.MESH_TO_EMAIL
            email_message.to_addresses = [EmailAddress.parse(f"user{i}@test.com")]
            email_message.body_text = f"Test message {i}"
            
            await email_gateway.queue_email_message(email_message)
            messages.append(email_message)
        
        # Verify queue size
        assert email_gateway.message_queue.qsize() == 5
        
        # Process all messages
        processed_count = 0
        while not email_gateway.message_queue.empty():
            queue_item = await email_gateway.message_queue.get()
            success = await email_gateway._process_mesh_to_email(queue_item.email_message)
            if success:
                processed_count += 1
        
        # Verify processing
        assert processed_count == 5
        assert email_gateway.smtp_client.send_email.call_count == 5
    
    @pytest.mark.asyncio
    async def test_statistics_tracking_flow(self, email_gateway):
        """Test comprehensive statistics tracking"""
        # Perform various operations
        await email_gateway.set_user_email("!user1", "user1@test.com")
        await email_gateway.add_to_blocklist("spam@example.com", "Test")
        
        # Send some messages
        for i in range(3):
            email_message = EmailMessage()
            email_message.direction = EmailDirection.MESH_TO_EMAIL
            email_message.to_addresses = [EmailAddress.parse(f"user{i}@test.com")]
            email_message.body_text = f"Message {i}"
            
            await email_gateway.queue_email_message(email_message)
            await email_gateway._process_mesh_to_email(email_message)
        
        # Get statistics
        stats = email_gateway.get_service_statistics()
        
        # Verify statistics structure and values
        assert stats['service']['is_running'] == True
        assert stats['queue']['current_size'] >= 0
        assert stats['messages']['total_processed'] >= 3
        assert stats['messages']['mesh_to_email'] >= 3
        assert stats['security']['blocklist_entries'] >= 1
        
        # Verify SMTP and IMAP statistics are included
        assert 'smtp' in stats
        assert 'imap' in stats
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_flow(self, email_gateway):
        """Test concurrent operations handling"""
        # Create multiple concurrent operations
        tasks = []
        
        # Concurrent email sends
        for i in range(10):
            message = Message(
                sender_id=f"!user{i}",
                content=f"email/test{i}@example.com/Subject {i}/Body {i}",
                message_type=MessageType.TEXT
            )
            task = asyncio.create_task(
                email_gateway.handle_email_send_command(message)
            )
            tasks.append(task)
        
        # Concurrent admin operations
        admin_tasks = [
            email_gateway.add_to_blocklist(f"spam{i}@example.com", f"Spam {i}")
            for i in range(5)
        ]
        tasks.extend(admin_tasks)
        
        # Wait for all operations to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify no exceptions occurred
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0
        
        # Verify operations completed successfully
        successful_emails = [r for r in results[:10] if isinstance(r, str) and "✅" in r]
        assert len(successful_emails) == 10
        
        successful_blocks = [r for r in results[10:] if r is True]
        assert len(successful_blocks) == 5


class TestEmailClientIntegration:
    """Integration tests for SMTP and IMAP clients"""
    
    @pytest.fixture
    def email_config(self):
        """Create email configuration for client testing"""
        config = EmailConfiguration()
        config.smtp_host = "smtp.test.com"
        config.smtp_port = 587
        config.smtp_username = "test@test.com"
        config.smtp_password = "password"
        config.smtp_use_tls = True
        config.imap_host = "imap.test.com"
        config.imap_port = 993
        config.imap_username = "test@test.com"
        config.imap_password = "password"
        config.imap_use_ssl = True
        config.gateway_email = "gateway@test.com"
        return config
    
    @pytest.mark.asyncio
    async def test_smtp_client_integration(self, email_config):
        """Test SMTP client integration"""
        with patch('smtplib.SMTP') as mock_smtp_class:
            # Mock SMTP server
            mock_smtp = Mock()
            mock_smtp_class.return_value = mock_smtp
            mock_smtp.starttls = Mock()
            mock_smtp.login = Mock()
            mock_smtp.sendmail = Mock(return_value={})
            mock_smtp.noop = Mock(return_value=(250, 'OK'))
            mock_smtp.quit = Mock()
            
            # Create and test SMTP client
            smtp_client = SMTPClient(email_config)
            
            # Test connection
            await smtp_client.start()
            assert smtp_client.is_connected
            
            # Test email sending
            email_message = EmailMessage()
            email_message.from_address = EmailAddress.parse("sender@test.com")
            email_message.to_addresses = [EmailAddress.parse("recipient@test.com")]
            email_message.subject = "Test Subject"
            email_message.body_text = "Test Body"
            
            success = await smtp_client.send_email(email_message)
            assert success
            assert mock_smtp.sendmail.called
            
            # Test disconnection
            await smtp_client.stop()
            assert not smtp_client.is_connected
    
    @pytest.mark.asyncio
    async def test_imap_client_integration(self, email_config):
        """Test IMAP client integration"""
        with patch('imaplib.IMAP4_SSL') as mock_imap_class:
            # Mock IMAP server
            mock_imap = Mock()
            mock_imap_class.return_value = mock_imap
            mock_imap.login = Mock(return_value=('OK', [b'Logged in']))
            mock_imap.select = Mock(return_value=('OK', [b'INBOX selected']))
            mock_imap.search = Mock(return_value=('OK', [b'1 2 3']))
            mock_imap.fetch = Mock(return_value=('OK', [(b'1', b'test email content')]))
            mock_imap.noop = Mock(return_value=('OK', [b'NOOP completed']))
            mock_imap.close = Mock()
            mock_imap.logout = Mock()
            
            # Mock socket for timeout setting
            mock_imap.sock = Mock()
            mock_imap.sock.settimeout = Mock()
            
            # Create and test IMAP client
            imap_client = IMAPClient(email_config)
            
            # Test connection
            await imap_client.start()
            assert imap_client.is_connected
            
            # Test message callback
            callback_called = False
            async def test_callback(email_message):
                nonlocal callback_called
                callback_called = True
            
            imap_client.add_message_callback(test_callback)
            
            # Test disconnection
            await imap_client.stop()
            assert not imap_client.is_connected


if __name__ == "__main__":
    pytest.main([__file__])