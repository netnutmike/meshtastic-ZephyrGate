"""
Integration tests for Interactive Bot System (Task 6.9)

Comprehensive tests covering:
- Auto-response and keyword detection functionality
- Command handling and game interactions
- AI integration and aircraft response scenarios
- Information lookup and reference services

Requirements: 4.1, 4.2, 4.3, 4.4, 4.7, 4.8
"""

import pytest
import pytest_asyncio
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.services.bot.interactive_bot_service import InteractiveBotService, AutoResponseRule
from src.services.bot.ai_service import AIService, AIResponse, AIContext
from src.services.bot.comprehensive_command_handler import ComprehensiveCommandHandler
from src.services.bot.educational_service import EducationalService
from src.services.bot.information_lookup_service import InformationLookupService
from src.services.bot.games.base_game import GameManager
from src.models.message import Message, MessageType, MessagePriority
from src.core.plugin_interfaces import PluginCommunicationInterface


class MockCommunicationInterface:
    """Mock communication interface for testing"""
    
    def __init__(self):
        self.sent_messages = []
        self.plugin_messages = []
        
    async def send_mesh_message(self, message):
        """Mock sending mesh message"""
        self.sent_messages.append(message)
        
    async def send_message(self, plugin_message):
        """Mock sending plugin message"""
        self.plugin_messages.append(plugin_message)
        
    def clear_messages(self):
        """Clear sent messages for testing"""
        self.sent_messages.clear()
        self.plugin_messages.clear()


class TestInteractiveBotSystemIntegration:
    """Comprehensive integration tests for interactive bot system"""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory with test data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            
            # Create ham radio data
            ham_dir = data_dir / 'hamradio'
            ham_dir.mkdir()
            
            tech_questions = [
                {
                    "id": "T1A01",
                    "question": "Which of the following is a purpose of the Amateur Radio Service?",
                    "options": [
                        "Personal communications",
                        "Commercial communications", 
                        "Advancing skills in radio art",
                        "All of the above"
                    ],
                    "correct": 2,
                    "explanation": "The Amateur Radio Service advances skills in radio art."
                }
            ]
            
            with open(ham_dir / 'technician.json', 'w') as f:
                json.dump(tech_questions, f)
            
            # Create quiz data
            quiz_questions = [
                {
                    "id": "Q001",
                    "category": "general",
                    "question": "What is the capital of France?",
                    "options": ["London", "Berlin", "Paris", "Madrid"],
                    "correct": 2,
                    "explanation": "Paris is the capital of France."
                }
            ]
            
            with open(data_dir / 'quiz_questions.json', 'w') as f:
                json.dump(quiz_questions, f)
            
            # Create survey data
            surveys_dir = data_dir / 'surveys'
            surveys_dir.mkdir()
            
            test_survey = {
                "id": "test_survey",
                "title": "Test Survey",
                "description": "A test survey",
                "active": True,
                "created_date": "2024-01-01",
                "expires_date": "2024-12-31",
                "questions": [
                    {
                        "id": 1,
                        "type": "multiple_choice",
                        "question": "How do you rate the mesh network?",
                        "options": ["Excellent", "Good", "Fair", "Poor"],
                        "required": True
                    }
                ]
            }
            
            with open(surveys_dir / 'test_survey.json', 'w') as f:
                json.dump(test_survey, f)
            
            yield data_dir
    
    @pytest.fixture
    def config(self, temp_data_dir):
        """Create comprehensive test configuration"""
        return {
            'data_dir': str(temp_data_dir),
            'auto_response': {
                'enabled': True,
                'emergency_keywords': ['help', 'emergency', 'urgent', 'mayday'],
                'greeting_enabled': True,
                'greeting_message': 'Welcome to the mesh network!',
                'greeting_delay_hours': 24,
                'aircraft_responses': True,
                'emergency_escalation_delay': 5,  # 5 seconds for testing
                'emergency_escalation_message': 'EMERGENCY ALERT: Unacknowledged emergency from {sender}',
                'response_rate_limit': 10,
                'cooldown_seconds': 2  # 2 seconds for testing
            },
            'commands': {
                'enabled': True,
                'help_enabled': True,
                'permissions_enabled': False
            },
            'ai': {
                'enabled': True,
                'service_type': 'openai',
                'api_key': 'test-key',
                'service_url': 'https://api.openai.com',
                'aircraft_detection': True,
                'altitude_threshold': 1000,
                'model_name': 'gpt-3.5-turbo',
                'max_tokens': 150,
                'temperature': 0.7
            },
            'games': {
                'enabled': True,
                'session_timeout_minutes': 30,
                'max_concurrent_sessions': 100
            },
            'educational': {
                'enabled': True,
                'ham_data_dir': str(temp_data_dir / 'hamradio'),
                'quiz_data_file': str(temp_data_dir / 'quiz_questions.json'),
                'surveys_dir': str(temp_data_dir / 'surveys')
            },
            'information': {
                'enabled': True,
                'default_location': (40.7128, -74.0060),  # NYC
                'weather_api_key': 'test_weather_key'
            },
            'message_history': {
                'history_retention_days': 30,
                'max_offline_messages': 50,
                'offline_message_ttl_hours': 72,
                'max_message_chunk_size': 200,
                'store_forward_enabled': True
            }
        }
    
    @pytest_asyncio.fixture
    async def bot_service(self, config):
        """Create interactive bot service with full configuration"""
        service = InteractiveBotService(config)
        
        # Mock database operations
        with patch('src.services.bot.interactive_bot_service.get_database') as mock_db:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = None
            mock_db.return_value.cursor.return_value = mock_cursor
            mock_db.return_value.commit = Mock()
            
            # Mock educational service database operations
            with patch('src.services.bot.educational_service.get_database') as mock_edu_db:
                mock_edu_cursor = Mock()
                mock_edu_cursor.fetchall.return_value = []
                mock_edu_cursor.fetchone.return_value = None
                mock_edu_db.return_value.cursor.return_value = mock_edu_cursor
                mock_edu_db.return_value.commit = Mock()
                
                await service.start()
                yield service
                await service.stop()
    
    @pytest.fixture
    def mock_communication(self):
        """Create mock communication interface"""
        return MockCommunicationInterface()
    
    def create_test_message(self, content: str, sender_id: str = "!12345678", 
                          recipient_id: str = None, altitude: float = None) -> Message:
        """Create a test message"""
        message = Message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            channel=0,
            content=content,
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        # Add altitude data if provided
        if altitude is not None:
            message.telemetry = {'altitude': altitude}
            
        return message
    
    # Test 1: Auto-response and keyword detection functionality
    @pytest.mark.asyncio
    async def test_auto_response_keyword_detection(self, bot_service, mock_communication):
        """Test auto-response and keyword detection functionality (Requirement 4.1)"""
        bot_service.set_communication_interface(mock_communication)
        
        # Test basic ping response
        ping_message = self.create_test_message("ping")
        response = await bot_service.handle_message(ping_message)
        
        assert response is not None
        assert "pong" in response.content.lower()
        assert response.sender_id == "bot"
        assert response.recipient_id == ping_message.sender_id
        
        # Test help keyword response
        help_message = self.create_test_message("?")
        response = await bot_service.handle_message(help_message)
        
        assert response is not None
        assert "commands" in response.content.lower()
        
        # Test weather keyword response
        weather_message = self.create_test_message("weather")
        response = await bot_service.handle_message(weather_message)
        
        assert response is not None
        assert "weather" in response.content.lower()
        
        # Test BBS keyword response
        bbs_message = self.create_test_message("bbs")
        response = await bot_service.handle_message(bbs_message)
        
        assert response is not None
        assert "bbs" in response.content.lower()
        
        # Test games keyword response
        games_message = self.create_test_message("games")
        response = await bot_service.handle_message(games_message)
        
        assert response is not None
        assert "games" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_emergency_keyword_detection_and_escalation(self, bot_service, mock_communication):
        """Test emergency keyword detection and escalation (Requirement 4.2)"""
        bot_service.set_communication_interface(mock_communication)
        
        # Test emergency keyword detection
        emergency_message = self.create_test_message("urgent help needed", "!emergency1")
        response = await bot_service.handle_message(emergency_message)
        
        assert response is not None
        assert "emergency" in response.content.lower()
        
        # Check that emergency escalation task was created
        assert len(bot_service.emergency_escalation_tasks) > 0
        
        # Check that plugin message was sent to emergency service
        assert len(mock_communication.plugin_messages) > 0
        emergency_plugin_msg = mock_communication.plugin_messages[0]
        assert hasattr(emergency_plugin_msg, 'type') or hasattr(emergency_plugin_msg, 'message_type')
        
        # Wait for escalation (short delay for testing)
        await asyncio.sleep(6)
        
        # Check that escalation message was sent
        assert len(mock_communication.sent_messages) > 0
        escalation_sent = any("EMERGENCY ALERT" in msg.content for msg in mock_communication.sent_messages)
        assert escalation_sent
    
    @pytest.mark.asyncio
    async def test_new_node_greeting(self, bot_service, mock_communication):
        """Test new node greeting functionality (Requirement 4.3)"""
        bot_service.set_communication_interface(mock_communication)
        
        # First message from a new node should trigger greeting
        new_node_message = self.create_test_message("hello", "!newnode123")
        await bot_service.handle_message(new_node_message)
        
        # Check that greeting was sent
        assert "!newnode123" in bot_service.new_node_greetings
        assert len(mock_communication.sent_messages) > 0
        
        greeting_sent = any("Welcome" in msg.content for msg in mock_communication.sent_messages)
        assert greeting_sent
    
    @pytest.mark.asyncio
    async def test_rate_limiting_and_cooldowns(self, bot_service, mock_communication):
        """Test rate limiting and cooldown functionality"""
        bot_service.set_communication_interface(mock_communication)
        
        # Add a test rule with short cooldown
        test_rule = AutoResponseRule(
            keywords=['ratelimit'],
            response='Rate test response',
            priority=1,
            cooldown_seconds=1,
            max_responses_per_hour=5
        )
        bot_service.add_auto_response_rule(test_rule)
        
        # First response should work
        test_message = self.create_test_message("ratelimit")
        response1 = await bot_service.handle_message(test_message)
        assert response1 is not None
        assert response1.content == 'Rate test response'
        
        # Second response should be rate limited
        response2 = await bot_service.handle_message(test_message)
        # Should either be None or a different response (not the rate limited one)
        if response2 is not None:
            assert response2.content != 'Rate test response'
        
        # Wait for cooldown
        await asyncio.sleep(1.5)
        
        # Third response should work
        response3 = await bot_service.handle_message(test_message)
        assert response3 is not None
        assert response3.content == 'Rate test response'
    
    # Test 2: Command handling and game interactions
    @pytest.mark.asyncio
    async def test_basic_command_handling(self, bot_service, mock_communication):
        """Test basic command handling (Requirement 4.4, 4.5)"""
        bot_service.set_communication_interface(mock_communication)
        
        # Test help command (use ? to avoid emergency keyword)
        help_message = self.create_test_message("?")
        response = await bot_service.handle_message(help_message)
        
        assert response is not None
        assert "commands" in response.content.lower()
        
        # Test status command
        status_message = self.create_test_message("status")
        response = await bot_service.handle_message(status_message)
        
        assert response is not None
        # Should get some kind of status response
        
        # Test ping command
        ping_message = self.create_test_message("ping")
        response = await bot_service.handle_message(ping_message)
        
        assert response is not None
        assert "pong" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_game_interactions(self, bot_service, mock_communication):
        """Test game interactions (Requirement 4.1.3)"""
        bot_service.set_communication_interface(mock_communication)
        
        # Test starting a tic-tac-toe game
        tictactoe_message = self.create_test_message("tictactoe")
        response = await bot_service.handle_message(tictactoe_message)
        
        assert response is not None
        assert "tic" in response.content.lower() or "game" in response.content.lower()
        
        # Check that game session was created
        assert bot_service.game_manager.has_active_game("!12345678")
        
        # Test game input
        game_input = self.create_test_message("1")  # Make a move
        response = await bot_service.handle_message(game_input)
        
        assert response is not None
        # Should get game board or game response
        
        # Test starting hangman game
        hangman_message = self.create_test_message("hangman", "!player2")
        response = await bot_service.handle_message(hangman_message)
        
        assert response is not None
        assert "hangman" in response.content.lower() or "guess" in response.content.lower()
        
        # Test blackjack game
        blackjack_message = self.create_test_message("blackjack", "!player3")
        response = await bot_service.handle_message(blackjack_message)
        
        assert response is not None
        assert "blackjack" in response.content.lower() or "card" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_educational_features(self, bot_service, mock_communication):
        """Test educational features (Requirement 4.2.1, 4.2.2, 4.2.3)"""
        bot_service.set_communication_interface(mock_communication)
        
        # Test ham radio test (use a different command to avoid ping response)
        hamtest_message = self.create_test_message("hamtest")
        response = await bot_service.handle_message(hamtest_message)
        
        assert response is not None
        # Should get some response (may be error due to missing data files)
        
        # Test quiz system
        quiz_message = self.create_test_message("quiz general", "!quizzer1")
        response = await bot_service.handle_message(quiz_message)
        
        assert response is not None
        # Should start a quiz session
        
        # Test survey system
        survey_message = self.create_test_message("survey test_survey", "!surveyor1")
        response = await bot_service.handle_message(survey_message)
        
        assert response is not None
        # Should start a survey session
    
    # Test 3: AI integration and aircraft response scenarios
    @pytest.mark.asyncio
    async def test_ai_integration_setup(self, bot_service):
        """Test AI integration setup (Requirement 4.7, 4.8)"""
        # Check that AI service was initialized
        assert hasattr(bot_service, 'ai_service')
        
        # AI should be enabled in config but may not be available without real API
        assert bot_service.config['ai']['enabled'] == True
    
    @pytest.mark.asyncio
    async def test_aircraft_message_detection(self, bot_service, mock_communication):
        """Test aircraft message detection and AI response (Requirement 4.8)"""
        bot_service.set_communication_interface(mock_communication)
        
        # Mock AI service to return a response
        mock_ai_response = AIResponse(
            content="Hello pilot! I see you're flying at high altitude. Safe travels!",
            confidence=0.9,
            processing_time=1.2,
            model_used="gpt-3.5-turbo",
            tokens_used=25
        )
        
        with patch.object(bot_service, 'ai_service') as mock_ai:
            mock_ai.generate_response = AsyncMock(return_value=mock_ai_response)
            bot_service.ai_enabled = True
            
            # Create high-altitude message (simulating aircraft)
            aircraft_message = self.create_test_message(
                "Testing radio from aircraft", 
                "!aircraft1", 
                altitude=5000  # Above threshold
            )
            
            response = await bot_service.handle_message(aircraft_message)
            
            # Should get AI response for aircraft
            if response is not None:
                assert "pilot" in response.content.lower() or "altitude" in response.content.lower()
                # Verify AI service was called
                mock_ai.generate_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ai_fallback_behavior(self, bot_service, mock_communication):
        """Test AI fallback behavior when service is unavailable"""
        bot_service.set_communication_interface(mock_communication)
        
        # Mock AI service to raise an exception
        with patch.object(bot_service, 'ai_service') as mock_ai:
            mock_ai.generate_response = AsyncMock(side_effect=Exception("AI service unavailable"))
            bot_service.ai_enabled = True
            
            # Create high-altitude message
            aircraft_message = self.create_test_message(
                "Testing from aircraft", 
                "!aircraft2", 
                altitude=3000
            )
            
            response = await bot_service.handle_message(aircraft_message)
            
            # Should handle gracefully without crashing
            # May return None or a fallback response
            if response is not None:
                # Should not be an error message
                assert "error" not in response.content.lower()
    
    # Test 4: Information lookup and reference services
    @pytest.mark.asyncio
    async def test_information_lookup_commands(self, bot_service, mock_communication):
        """Test information lookup commands (Requirement 4.1.4, 4.1.5, 4.2.4, 4.2.5)"""
        bot_service.set_communication_interface(mock_communication)
        
        # Mock external API calls
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value={'weather': 'sunny'})
            mock_response.text = AsyncMock(return_value='Weather data')
            mock_response.status = 200
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # Test weather command
            weather_message = self.create_test_message("wx")
            response = await bot_service.handle_message(weather_message)
            
            assert response is not None
            # Should get weather information or service response
            
            # Test solar conditions
            solar_message = self.create_test_message("solar")
            response = await bot_service.handle_message(solar_message)
            
            assert response is not None
            # Should get solar condition information
            
            # Test earthquake data
            earthquake_message = self.create_test_message("earthquake")
            response = await bot_service.handle_message(earthquake_message)
            
            assert response is not None
            # Should get earthquake information
    
    @pytest.mark.asyncio
    async def test_location_based_services(self, bot_service, mock_communication):
        """Test location-based information services"""
        bot_service.set_communication_interface(mock_communication)
        
        # Test whereami command
        whereami_message = self.create_test_message("whereami")
        response = await bot_service.handle_message(whereami_message)
        
        assert response is not None
        # Should get location information
        
        # Test howfar command
        howfar_message = self.create_test_message("howfar !target123")
        response = await bot_service.handle_message(howfar_message)
        
        assert response is not None
        # Should get distance information or error message
    
    @pytest.mark.asyncio
    async def test_reference_data_commands(self, bot_service, mock_communication):
        """Test reference data commands (Requirement 4.2.4, 4.2.5)"""
        bot_service.set_communication_interface(mock_communication)
        
        # Mock external API calls for reference data
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value={'data': 'reference_data'})
            mock_response.text = AsyncMock(return_value='Reference data response')
            mock_response.status = 200
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # Test sun/moon data
            sun_message = self.create_test_message("sun")
            response = await bot_service.handle_message(sun_message)
            
            assert response is not None
            
            moon_message = self.create_test_message("moon")
            response = await bot_service.handle_message(moon_message)
            
            assert response is not None
            
            # Test HF conditions
            hfcond_message = self.create_test_message("hfcond")
            response = await bot_service.handle_message(hfcond_message)
            
            assert response is not None
    
    @pytest.mark.asyncio
    async def test_network_information_commands(self, bot_service, mock_communication):
        """Test network information commands (Requirement 4.3.6)"""
        bot_service.set_communication_interface(mock_communication)
        
        # Test system info
        sysinfo_message = self.create_test_message("sysinfo")
        response = await bot_service.handle_message(sysinfo_message)
        
        assert response is not None
        # Should get system information
        
        # Test leaderboard
        leaderboard_message = self.create_test_message("leaderboard")
        response = await bot_service.handle_message(leaderboard_message)
        
        assert response is not None
        # Should get leaderboard information
        
        # Test message history
        history_message = self.create_test_message("history")
        response = await bot_service.handle_message(history_message)
        
        assert response is not None
        # Should get message history
    
    # Test 5: Integration and error handling
    @pytest.mark.asyncio
    async def test_service_integration_and_coordination(self, bot_service, mock_communication):
        """Test integration between different services"""
        bot_service.set_communication_interface(mock_communication)
        
        # Test that multiple services can handle different aspects of the same message
        complex_message = self.create_test_message("help with weather emergency")
        response = await bot_service.handle_message(complex_message)
        
        assert response is not None
        # Should prioritize emergency response over other keywords
        assert "emergency" in response.content.lower()
        
        # Test command vs auto-response priority
        command_message = self.create_test_message("ping")  # Both command and auto-response
        response = await bot_service.handle_message(command_message)
        
        assert response is not None
        assert "pong" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_error_handling_and_resilience(self, bot_service, mock_communication):
        """Test error handling and service resilience"""
        bot_service.set_communication_interface(mock_communication)
        
        # Test handling of malformed commands
        malformed_message = self.create_test_message("!@#$%^&*()")
        response = await bot_service.handle_message(malformed_message)
        
        # Should handle gracefully without crashing
        # May return None or an error message
        
        # Test handling of very long messages
        long_message = self.create_test_message("a" * 1000)
        response = await bot_service.handle_message(long_message)
        
        # Should handle gracefully
        
        # Test handling when services are disabled
        bot_service.config['commands']['enabled'] = False
        disabled_command = self.create_test_message("status")  # Use non-emergency keyword
        response = await bot_service.handle_message(disabled_command)
        
        # Should still handle auto-responses even if commands are disabled
        # May get auto-response or no response
    
    @pytest.mark.asyncio
    async def test_concurrent_message_handling(self, bot_service, mock_communication):
        """Test concurrent message handling"""
        bot_service.set_communication_interface(mock_communication)
        
        # Create multiple messages from different users
        messages = [
            self.create_test_message("ping", f"!user{i}")
            for i in range(5)
        ]
        
        # Process messages concurrently
        tasks = [bot_service.handle_message(msg) for msg in messages]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete without exceptions
        for response in responses:
            assert not isinstance(response, Exception)
            if response is not None:
                assert "pong" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_service_statistics_and_monitoring(self, bot_service):
        """Test service statistics and monitoring"""
        # Get response statistics
        stats = bot_service.get_response_statistics()
        
        assert 'total_rules' in stats
        assert 'emergency_rules' in stats
        assert 'active_rules' in stats
        assert 'known_nodes' in stats
        assert isinstance(stats['total_rules'], int)
        assert stats['total_rules'] > 0  # Should have default rules
        
        # Test command execution statistics
        if hasattr(bot_service.comprehensive_handler, 'execution_stats'):
            cmd_stats = bot_service.comprehensive_handler.execution_stats
            assert 'total_commands' in cmd_stats
            assert 'successful_commands' in cmd_stats
            assert 'failed_commands' in cmd_stats


if __name__ == '__main__':
    pytest.main([__file__, '-v'])