"""
Integration tests for AI service with Interactive Bot Service

Tests the complete AI integration including:
- AI service initialization in bot service
- Aircraft message detection and response
- AI command handling
- Fallback behavior when AI is unavailable
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.services.bot.interactive_bot_service import InteractiveBotService
from src.services.bot.ai_service import AIService, AIResponse
from src.models.message import Message, MessageType, MessagePriority


class TestAIIntegration:
    """Test AI integration with Interactive Bot Service"""
    
    @pytest_asyncio.fixture
    async def bot_service_with_ai(self):
        """Create bot service with AI enabled"""
        config = {
            'auto_response': {
                'enabled': True,
                'emergency_keywords': ['help', 'emergency'],
                'greeting_enabled': False  # Disable for testing
            },
            'commands': {
                'enabled': True
            },
            'ai': {
                'enabled': True,
                'service_type': 'openai',
                'api_key': 'test-key',
                'service_url': 'https://api.openai.com',
                'aircraft_detection_enabled': True,
                'altitude_threshold_meters': 1000
            }
        }
        
        service = InteractiveBotService(config)
        
        # Mock database operations
        with patch('src.services.bot.interactive_bot_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_db.return_value.cursor.return_value = mock_cursor
            
            await service.start()
        
        yield service
        await service.stop()
    
    @pytest_asyncio.fixture
    async def bot_service_no_ai(self):
        """Create bot service with AI disabled"""
        config = {
            'auto_response': {
                'enabled': True,
                'greeting_enabled': False
            },
            'commands': {
                'enabled': True
            },
            'ai': {
                'enabled': False
            }
        }
        
        service = InteractiveBotService(config)
        
        # Mock database operations
        with patch('src.services.bot.interactive_bot_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_db.return_value.cursor.return_value = mock_cursor
            
            await service.start()
        
        yield service
        await service.stop()
    
    @pytest.mark.asyncio
    async def test_ai_service_initialization(self, bot_service_with_ai):
        """Test that AI service is properly initialized"""
        assert bot_service_with_ai.ai_service is not None
        assert isinstance(bot_service_with_ai.ai_service, AIService)
        
        # AI should be disabled because we don't have a real API connection
        assert bot_service_with_ai.ai_enabled is False
    
    @pytest.mark.asyncio
    async def test_ai_disabled_service(self, bot_service_no_ai):
        """Test behavior when AI is disabled"""
        assert bot_service_no_ai.ai_service is None
        assert bot_service_no_ai.ai_enabled is False
    
    @pytest.mark.asyncio
    async def test_aircraft_message_detection_and_response(self, bot_service_with_ai):
        """Test aircraft message detection and AI response"""
        # Mock AI service to be available and return a response
        mock_ai_service = AsyncMock()
        mock_ai_service.is_enabled.return_value = True
        
        mock_response = AIResponse(
            content="Roger, current weather conditions are VFR with light winds.",
            confidence=0.9,
            processing_time=1.2,
            model_used="gpt-3.5-turbo",
            tokens_used=20
        )
        mock_ai_service.generate_response.return_value = mock_response
        
        bot_service_with_ai.ai_service = mock_ai_service
        bot_service_with_ai.ai_enabled = True
        
        # Mock recent messages method
        bot_service_with_ai._get_recent_messages = AsyncMock(return_value=[])
        
        # Create aircraft message with high altitude
        aircraft_message = Message(
            sender_id="!87654321",
            recipient_id=None,
            channel=0,
            content="Request weather update for flight planning",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Add altitude metadata
        aircraft_message.altitude = 1500  # Above threshold
        
        response = await bot_service_with_ai.handle_message(aircraft_message)
        
        assert response is not None
        assert "Roger" in response.content
        assert response.sender_id == "bot"
        assert response.recipient_id == aircraft_message.sender_id
        
        # Verify AI service was called
        mock_ai_service.generate_response.assert_called_once()
        call_args = mock_ai_service.generate_response.call_args
        assert call_args[1]['altitude'] == 1500
        assert call_args[1]['message'] == aircraft_message
    
    @pytest.mark.asyncio
    async def test_non_aircraft_message_no_ai_response(self, bot_service_with_ai):
        """Test that non-aircraft messages don't trigger AI responses"""
        # Mock AI service
        mock_ai_service = AsyncMock()
        mock_ai_service.is_enabled.return_value = True
        mock_ai_service.generate_response.return_value = None  # No response for non-aircraft
        
        bot_service_with_ai.ai_service = mock_ai_service
        bot_service_with_ai.ai_enabled = True
        bot_service_with_ai._get_recent_messages = AsyncMock(return_value=[])
        
        # Create regular message (low altitude, no aviation keywords)
        regular_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="Hello everyone, how are you today?",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Add low altitude
        regular_message.altitude = 100  # Below threshold
        
        response = await bot_service_with_ai.handle_message(regular_message)
        
        # Should get auto-response or command response, not AI response
        if response:
            # If there's a response, it should be from auto-response system
            assert "Hello" in response.content or "help" in response.content.lower()
        
        # AI service should still be called but return None
        mock_ai_service.generate_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ai_command_handling(self, bot_service_with_ai):
        """Test AI-specific commands"""
        # Mock AI service
        mock_ai_service = AsyncMock()
        mock_ai_service.is_enabled.return_value = True
        mock_ai_service.get_statistics.return_value = {
            'requests_total': 5,
            'requests_successful': 4,
            'requests_failed': 1,
            'aircraft_detected': 2,
            'config': {
                'enabled': True,
                'service_type': 'openai',
                'model': 'gpt-3.5-turbo'
            },
            'provider_info': {
                'healthy': True
            }
        }
        
        bot_service_with_ai.ai_service = mock_ai_service
        bot_service_with_ai.ai_enabled = True
        bot_service_with_ai._get_recent_messages = AsyncMock(return_value=[])
        
        # Test AI status command
        status_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="aistatus",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service_with_ai.handle_message(status_message)
        
        assert response is not None
        assert "AI Service Status" in response.content
        assert "openai" in response.content
        assert "Requests: 5" in response.content
    
    @pytest.mark.asyncio
    async def test_ask_ai_command(self, bot_service_with_ai):
        """Test asking AI a direct question"""
        # Mock AI service
        mock_ai_service = AsyncMock()
        mock_ai_service.is_enabled.return_value = True
        
        mock_response = AIResponse(
            content="The weather looks good for flying today with clear skies.",
            confidence=0.8,
            processing_time=1.0,
            model_used="gpt-3.5-turbo"
        )
        mock_ai_service.generate_response.return_value = mock_response
        
        bot_service_with_ai.ai_service = mock_ai_service
        bot_service_with_ai.ai_enabled = True
        bot_service_with_ai._get_recent_messages = AsyncMock(return_value=[])
        
        # Test ask AI command
        ask_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="askai What's the weather like for flying?",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service_with_ai.handle_message(ask_message)
        
        assert response is not None
        assert "weather looks good" in response.content
        assert response.content.startswith("🤖")
        
        # Verify AI service was called with the question
        mock_ai_service.generate_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ai_fallback_when_unavailable(self, bot_service_with_ai):
        """Test fallback behavior when AI service is unavailable"""
        # Mock AI service as unavailable
        mock_ai_service = AsyncMock()
        mock_ai_service.is_enabled.return_value = False
        
        bot_service_with_ai.ai_service = mock_ai_service
        bot_service_with_ai.ai_enabled = False
        
        # Test AI command when service is unavailable
        ask_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="askai What's the weather?",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service_with_ai.handle_message(ask_message)
        
        assert response is not None
        assert "not available" in response.content
        assert "🤖" in response.content
    
    @pytest.mark.asyncio
    async def test_ai_error_handling(self, bot_service_with_ai):
        """Test error handling in AI responses"""
        # Mock AI service to raise an exception
        mock_ai_service = AsyncMock()
        mock_ai_service.is_enabled.return_value = True
        mock_ai_service.generate_response.side_effect = Exception("API Error")
        
        bot_service_with_ai.ai_service = mock_ai_service
        bot_service_with_ai.ai_enabled = True
        bot_service_with_ai._get_recent_messages = AsyncMock(return_value=[])
        
        # Create aircraft message
        aircraft_message = Message(
            sender_id="!87654321",
            recipient_id=None,
            channel=0,
            content="Request weather update",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        aircraft_message.altitude = 1500
        
        # Should not crash and should fall back to other responses
        response = await bot_service_with_ai.handle_message(aircraft_message)
        
        # Might get auto-response or no response, but shouldn't crash
        # The important thing is that the service continues to work
        assert True  # If we get here without exception, the test passes
    
    @pytest.mark.asyncio
    async def test_ai_statistics_integration(self, bot_service_with_ai):
        """Test AI statistics integration"""
        # Mock AI service with statistics
        mock_ai_service = AsyncMock()
        mock_ai_service.get_statistics.return_value = {
            'requests_total': 10,
            'requests_successful': 8,
            'aircraft_detected': 3,
            'config': {'enabled': True}
        }
        
        bot_service_with_ai.ai_service = mock_ai_service
        
        stats = await bot_service_with_ai.get_ai_statistics()
        
        assert stats is not None
        assert stats['requests_total'] == 10
        assert stats['requests_successful'] == 8
        assert stats['aircraft_detected'] == 3
    
    @pytest.mark.asyncio
    async def test_ai_service_cleanup(self, bot_service_with_ai):
        """Test that AI service is properly cleaned up on stop"""
        # Mock AI service
        mock_ai_service = AsyncMock()
        bot_service_with_ai.ai_service = mock_ai_service
        
        await bot_service_with_ai.stop()
        
        # Verify close was called
        mock_ai_service.close.assert_called_once()


@pytest.mark.asyncio
async def test_end_to_end_aircraft_scenario():
    """End-to-end test of aircraft detection and response"""
    config = {
        'auto_response': {'enabled': True, 'greeting_enabled': False},
        'commands': {'enabled': True},
        'ai': {
            'enabled': True,
            'service_type': 'openai',
            'api_key': 'test-key',
            'aircraft_detection_enabled': True,
            'altitude_threshold_meters': 1000
        }
    }
    
    service = InteractiveBotService(config)
    
    # Mock database and AI service
    with patch('src.services.bot.interactive_bot_service.get_database') as mock_db:
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_db.return_value.cursor.return_value = mock_cursor
        
        await service.start()
        
        # Mock AI service to simulate real behavior
        mock_ai_service = AsyncMock()
        mock_ai_service.is_enabled.return_value = True
        
        # Mock aircraft detection and response
        mock_response = AIResponse(
            content="Roger, I can provide aviation weather briefing. Current conditions show VFR with 10SM visibility.",
            confidence=0.9,
            processing_time=1.5,
            model_used="gpt-3.5-turbo"
        )
        mock_ai_service.generate_response.return_value = mock_response
        
        service.ai_service = mock_ai_service
        service.ai_enabled = True
        service._get_recent_messages = AsyncMock(return_value=[])
        
        # Simulate aircraft message sequence
        messages = [
            # Initial contact from aircraft
            Message(
                sender_id="!N123AB",
                recipient_id=None,
                channel=0,
                content="Request weather briefing for flight to KORD",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            ),
            # Follow-up question
            Message(
                sender_id="!N123AB",
                recipient_id=None,
                channel=0,
                content="What are the winds aloft at 5000 feet?",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
        ]
        
        # Add altitude data to simulate aircraft
        for msg in messages:
            msg.altitude = 1500  # Above threshold
        
        responses = []
        for msg in messages:
            response = await service.handle_message(msg)
            if response:
                responses.append(response)
        
        # Should get AI responses for aircraft messages
        assert len(responses) >= 1
        assert any("Roger" in r.content for r in responses)
        
        # Verify AI service was called
        assert mock_ai_service.generate_response.call_count >= 1
        
        await service.stop()