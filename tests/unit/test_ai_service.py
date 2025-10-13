"""
Tests for AI Service

Tests the AI integration framework including:
- AI service interface and implementations
- Aircraft message detection
- Contextual response generation
- Configuration and fallback handling
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import aiohttp

from src.services.bot.ai_service import (
    AIService, AIServiceConfig, AIContext, AIResponse,
    OpenAIService, OllamaService, AircraftDetector
)
from src.models.message import Message, MessageType


class TestAIServiceConfig:
    """Test AI service configuration"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = AIServiceConfig()
        
        assert config.enabled is False
        assert config.service_type == "openai"
        assert config.model_name == "gpt-3.5-turbo"
        assert config.max_tokens == 150
        assert config.temperature == 0.7
        assert config.timeout_seconds == 30
        assert config.aircraft_detection_enabled is True
        assert config.altitude_threshold_meters == 1000
        assert len(config.fallback_responses) > 0
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = AIServiceConfig(
            enabled=True,
            service_type="ollama",
            model_name="llama2",
            altitude_threshold_meters=500
        )
        
        assert config.enabled is True
        assert config.service_type == "ollama"
        assert config.model_name == "llama2"
        assert config.altitude_threshold_meters == 500


class TestAIContext:
    """Test AI context data structure"""
    
    def test_basic_context(self):
        """Test basic context creation"""
        context = AIContext(
            sender_id="!12345678",
            sender_name="TestUser",
            message_content="Hello AI"
        )
        
        assert context.sender_id == "!12345678"
        assert context.sender_name == "TestUser"
        assert context.message_content == "Hello AI"
        assert context.is_aircraft is False
        assert context.altitude_meters is None
    
    def test_aircraft_context(self):
        """Test aircraft context"""
        context = AIContext(
            sender_id="!87654321",
            sender_name="Pilot",
            message_content="Flying at 5000 feet",
            altitude_meters=1524,
            is_aircraft=True
        )
        
        assert context.is_aircraft is True
        assert context.altitude_meters == 1524


class TestAircraftDetector:
    """Test aircraft message detection"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AircraftDetector(altitude_threshold=1000)
    
    def test_altitude_detection(self):
        """Test detection based on altitude"""
        message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="Hello from above",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # High altitude should trigger detection
        is_aircraft, confidence = self.detector.detect_aircraft_message(message, altitude=2000)
        assert is_aircraft is True
        assert confidence > 0.5
        
        # Low altitude should not trigger
        is_aircraft, confidence = self.detector.detect_aircraft_message(message, altitude=500)
        assert is_aircraft is False
        assert confidence < 0.6
    
    def test_keyword_detection(self):
        """Test detection based on aviation keywords"""
        # Aviation keywords
        aviation_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="Aircraft on approach to runway 27",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        is_aircraft, confidence = self.detector.detect_aircraft_message(aviation_message)
        assert confidence > 0.2  # Should have some confidence from keywords
        
        # Regular message
        regular_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="Hello everyone, how is the weather?",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        is_aircraft, confidence = self.detector.detect_aircraft_message(regular_message)
        assert confidence < 0.3  # Should have low confidence
    
    def test_altitude_text_detection(self):
        """Test detection of altitude mentions in text"""
        altitude_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="Currently at 8500 feet AGL",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        is_aircraft, confidence = self.detector.detect_aircraft_message(altitude_message)
        assert confidence > 0.1  # Should detect altitude mention
    
    def test_radio_phraseology_detection(self):
        """Test detection of aviation radio phrases"""
        radio_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="Roger that, wilco, contact tower on 121.9",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        is_aircraft, confidence = self.detector.detect_aircraft_message(radio_message)
        assert confidence > 0.1  # Should detect radio phraseology


class TestOpenAIService:
    """Test OpenAI service implementation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = AIServiceConfig(
            enabled=True,
            service_type="openai",
            service_url="https://api.openai.com",
            api_key="test-key",
            model_name="gpt-3.5-turbo"
        )
        self.service = OpenAIService(self.config)
    
    @pytest.mark.asyncio
    async def test_system_prompt_building(self):
        """Test system prompt construction"""
        # Regular context
        context = AIContext(
            sender_id="!12345678",
            sender_name="TestUser",
            message_content="Hello"
        )
        
        prompt = self.service._build_system_prompt(context)
        assert "Meshtastic mesh network" in prompt
        assert "radio communication" in prompt
        
        # Aircraft context
        aircraft_context = AIContext(
            sender_id="!87654321",
            sender_name="Pilot",
            message_content="Hello from aircraft",
            altitude_meters=1500,
            is_aircraft=True
        )
        
        aircraft_prompt = self.service._build_system_prompt(aircraft_context)
        assert "aircraft" in aircraft_prompt
        assert "aviation" in aircraft_prompt
        assert "1500m altitude" in aircraft_prompt
    
    @pytest.mark.asyncio
    async def test_fallback_response(self):
        """Test fallback response creation"""
        fallback = self.service._create_fallback_response("Test error")
        
        assert isinstance(fallback, AIResponse)
        assert fallback.fallback_used is True
        assert fallback.error == "Test error"
        assert fallback.content in self.config.fallback_responses
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check when service is unavailable"""
        # Mock failed HTTP request
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_get.return_value.__aenter__.return_value = mock_response
            
            is_healthy = await self.service.is_available()
            assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test service cleanup"""
        # Create a mock session
        self.service.session = AsyncMock()
        self.service.session.closed = False
        
        await self.service.close()
        self.service.session.close.assert_called_once()


class TestOllamaService:
    """Test Ollama service implementation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = AIServiceConfig(
            enabled=True,
            service_type="ollama",
            service_url="http://localhost:11434",
            model_name="llama2"
        )
        self.service = OllamaService(self.config)
    
    @pytest.mark.asyncio
    async def test_prompt_building(self):
        """Test prompt construction for Ollama"""
        context = AIContext(
            sender_id="!12345678",
            sender_name="TestUser",
            message_content="What's the weather like?",
            recent_messages=[]
        )
        
        prompt = self.service._build_prompt(context)
        assert "Meshtastic mesh network" in prompt
        assert "What's the weather like?" in prompt
        assert "Assistant:" in prompt
    
    @pytest.mark.asyncio
    async def test_aircraft_prompt(self):
        """Test aircraft-specific prompt"""
        context = AIContext(
            sender_id="!87654321",
            sender_name="Pilot",
            message_content="Need weather update",
            altitude_meters=2000,
            is_aircraft=True
        )
        
        prompt = self.service._build_prompt(context)
        assert "aircraft" in prompt
        assert "2000m altitude" in prompt
    
    def test_service_info(self):
        """Test service information"""
        info = self.service.get_service_info()
        
        assert info["service_type"] == "ollama"
        assert info["model"] == "llama2"
        assert info["url"] == "http://localhost:11434"


class TestAIService:
    """Test main AI service coordinator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = {
            'ai': {
                'enabled': True,
                'service_type': 'openai',
                'api_key': 'test-key',
                'service_url': 'https://api.openai.com',
                'aircraft_detection_enabled': True,
                'altitude_threshold_meters': 1000
            }
        }
        self.service = AIService(self.config)
    
    @pytest.mark.asyncio
    async def test_disabled_service(self):
        """Test behavior when AI is disabled"""
        disabled_config = {'ai': {'enabled': False}}
        disabled_service = AIService(disabled_config)
        
        is_enabled = await disabled_service.is_enabled()
        assert is_enabled is False
    
    @pytest.mark.asyncio
    async def test_aircraft_message_processing(self):
        """Test processing of aircraft messages"""
        # Mock the provider
        mock_provider = AsyncMock()
        mock_response = AIResponse(
            content="Roger, weather conditions are clear",
            confidence=0.8,
            processing_time=1.5,
            model_used="gpt-3.5-turbo"
        )
        mock_provider.generate_response.return_value = mock_response
        mock_provider.is_available.return_value = True
        
        self.service.provider = mock_provider
        
        # Create aircraft message
        message = Message(
            sender_id="!87654321",
            recipient_id=None,
            channel=0,
            content="Request weather update for flight",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        response = await self.service.generate_response(
            message=message,
            altitude=1500,  # Above threshold
            location=(40.7128, -74.0060)
        )
        
        assert response is not None
        assert response.content == "Roger, weather conditions are clear"
        assert self.service.stats['aircraft_detected'] > 0
    
    @pytest.mark.asyncio
    async def test_non_aircraft_message_filtering(self):
        """Test that non-aircraft messages are filtered out"""
        # Mock the provider
        mock_provider = AsyncMock()
        mock_provider.is_available.return_value = True
        self.service.provider = mock_provider
        
        # Create regular message (low altitude, no aviation keywords)
        message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="Hello everyone, how are you?",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        response = await self.service.generate_response(
            message=message,
            altitude=100  # Below threshold
        )
        
        # Should return None for non-aircraft messages when aircraft detection is enabled
        assert response is None
    
    def test_statistics_tracking(self):
        """Test statistics collection"""
        stats = self.service.get_statistics()
        
        assert 'requests_total' in stats
        assert 'requests_successful' in stats
        assert 'requests_failed' in stats
        assert 'aircraft_detected' in stats
        assert 'config' in stats
        
        # Check config in stats
        assert stats['config']['enabled'] is True
        assert stats['config']['service_type'] == 'openai'
    
    @pytest.mark.asyncio
    async def test_provider_initialization_failure(self):
        """Test handling of provider initialization failure"""
        bad_config = {
            'ai': {
                'enabled': True,
                'service_type': 'unsupported_service'
            }
        }
        
        service = AIService(bad_config)
        assert service.provider is None
        
        is_enabled = await service.is_enabled()
        assert is_enabled is False
    
    @pytest.mark.asyncio
    async def test_openai_without_api_key(self):
        """Test OpenAI initialization without API key"""
        no_key_config = {
            'ai': {
                'enabled': True,
                'service_type': 'openai'
                # No api_key provided
            }
        }
        
        service = AIService(no_key_config)
        assert service.provider is None
    
    @pytest.mark.asyncio
    async def test_ollama_default_url(self):
        """Test Ollama with default URL"""
        ollama_config = {
            'ai': {
                'enabled': True,
                'service_type': 'ollama'
                # No service_url provided
            }
        }
        
        service = AIService(ollama_config)
        assert service.provider is not None
        assert service.config.service_url == "http://localhost:11434"


@pytest.mark.asyncio
async def test_ai_service_integration():
    """Integration test for AI service with mock responses"""
    config = {
        'ai': {
            'enabled': True,
            'service_type': 'openai',
            'api_key': 'test-key',
            'service_url': 'https://api.openai.com',
            'aircraft_detection_enabled': True
        }
    }
    
    service = AIService(config)
    
    # Mock the provider directly
    mock_provider = AsyncMock()
    mock_provider.is_available.return_value = True
    mock_response = AIResponse(
        content="Roger, I can assist with aviation weather information.",
        confidence=0.8,
        processing_time=1.5,
        model_used="gpt-3.5-turbo",
        tokens_used=25
    )
    mock_provider.generate_response.return_value = mock_response
    service.provider = mock_provider
    
    # Test aircraft message
    aircraft_message = Message(
        sender_id="!87654321",
        recipient_id=None,
        channel=0,
        content="Request current weather conditions for flight planning",
        message_type=MessageType.TEXT,
        timestamp=datetime.utcnow()
    )
    
    response = await service.generate_response(
        message=aircraft_message,
        altitude=1500
    )
    
    assert response is not None
    assert "Roger" in response.content
    assert response.fallback_used is False
    assert service.stats['aircraft_detected'] == 1
    assert service.stats['requests_successful'] == 1