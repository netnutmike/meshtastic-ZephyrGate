#!/usr/bin/env python3
"""
AI Integration Example

Demonstrates the AI integration framework for the unified Meshtastic gateway.
Shows how to:
- Configure AI services (OpenAI, Ollama)
- Detect aircraft messages using altitude data
- Generate contextual AI responses
- Handle fallback scenarios
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.bot.ai_service import AIService, AIResponse, AircraftDetector
from src.services.bot.interactive_bot_service import InteractiveBotService
from src.models.message import Message, MessageType


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demonstrate_aircraft_detection():
    """Demonstrate aircraft message detection"""
    print("\n=== Aircraft Detection Demo ===")
    
    detector = AircraftDetector(altitude_threshold=1000)
    
    # Test messages
    test_messages = [
        {
            'content': "Hello everyone, how are you?",
            'altitude': 100,
            'expected': False
        },
        {
            'content': "Aircraft N123AB requesting weather update",
            'altitude': 1500,
            'expected': True
        },
        {
            'content': "Currently at 8500 feet AGL, requesting traffic advisories",
            'altitude': None,
            'expected': True  # Should detect from altitude mention
        },
        {
            'content': "Roger tower, wilco, contact approach on 121.9",
            'altitude': 500,
            'expected': True  # Should detect from aviation phraseology
        }
    ]
    
    for i, test in enumerate(test_messages, 1):
        message = Message(
            sender_id=f"!test{i:03d}",
            recipient_id=None,
            channel=0,
            content=test['content'],
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        is_aircraft, confidence = detector.detect_aircraft_message(
            message, altitude=test['altitude']
        )
        
        status = "✅" if is_aircraft == test['expected'] else "❌"
        print(f"{status} Test {i}: {test['content'][:50]}...")
        print(f"   Altitude: {test['altitude']}m, Aircraft: {is_aircraft}, Confidence: {confidence:.2f}")


async def demonstrate_ai_service_config():
    """Demonstrate AI service configuration"""
    print("\n=== AI Service Configuration Demo ===")
    
    # OpenAI configuration
    openai_config = {
        'ai': {
            'enabled': True,
            'service_type': 'openai',
            'api_key': 'your-openai-api-key',
            'service_url': 'https://api.openai.com',
            'model_name': 'gpt-3.5-turbo',
            'aircraft_detection_enabled': True,
            'altitude_threshold_meters': 1000
        }
    }
    
    # Ollama configuration
    ollama_config = {
        'ai': {
            'enabled': True,
            'service_type': 'ollama',
            'service_url': 'http://localhost:11434',
            'model_name': 'llama2',
            'aircraft_detection_enabled': True,
            'altitude_threshold_meters': 1000
        }
    }
    
    # Disabled configuration
    disabled_config = {
        'ai': {
            'enabled': False
        }
    }
    
    configs = [
        ("OpenAI", openai_config),
        ("Ollama", ollama_config),
        ("Disabled", disabled_config)
    ]
    
    for name, config in configs:
        service = AIService(config)
        print(f"{name} Service:")
        print(f"  Enabled: {service.config.enabled}")
        print(f"  Type: {service.config.service_type}")
        print(f"  Model: {service.config.model_name}")
        print(f"  Aircraft Detection: {service.config.aircraft_detection_enabled}")
        print(f"  Provider: {'Available' if service.provider else 'None'}")
        print()


async def demonstrate_mock_ai_responses():
    """Demonstrate AI responses with mocked services"""
    print("\n=== Mock AI Response Demo ===")
    
    # Create AI service with mock provider
    config = {
        'ai': {
            'enabled': True,
            'service_type': 'openai',
            'aircraft_detection_enabled': True,
            'altitude_threshold_meters': 1000
        }
    }
    
    service = AIService(config)
    
    # Mock the provider
    mock_provider = AsyncMock()
    mock_provider.is_available.return_value = True
    service.provider = mock_provider
    
    # Test scenarios
    scenarios = [
        {
            'name': 'Aircraft Weather Request',
            'content': 'Request current weather conditions for flight planning',
            'altitude': 1500,
            'response': 'Roger, current weather shows VFR conditions with light winds from 270 at 8 knots, visibility 10+ miles, scattered clouds at 3000 feet.'
        },
        {
            'name': 'Aircraft Navigation Query',
            'content': 'What is the bearing to KORD from current position?',
            'altitude': 2000,
            'response': 'Based on your position, KORD bears approximately 090 degrees magnetic, distance 45 nautical miles. Contact Chicago Approach on 120.55.'
        },
        {
            'name': 'Ground Station Query',
            'content': 'What is the weather like?',
            'altitude': 50,
            'response': None  # Should be filtered out
        }
    ]
    
    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")
        print(f"Message: {scenario['content']}")
        print(f"Altitude: {scenario['altitude']}m")
        
        # Mock response
        if scenario['response']:
            mock_response = AIResponse(
                content=scenario['response'],
                confidence=0.9,
                processing_time=1.2,
                model_used="gpt-3.5-turbo"
            )
            mock_provider.generate_response.return_value = mock_response
        else:
            mock_provider.generate_response.return_value = None
        
        # Create test message
        message = Message(
            sender_id="!test123",
            recipient_id=None,
            channel=0,
            content=scenario['content'],
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Generate response
        response = await service.generate_response(
            message=message,
            altitude=scenario['altitude']
        )
        
        if response:
            print(f"AI Response: {response.content}")
            print(f"Confidence: {response.confidence}")
            print(f"Processing Time: {response.processing_time:.2f}s")
        else:
            print("No AI response (filtered or unavailable)")


async def demonstrate_bot_integration():
    """Demonstrate AI integration with Interactive Bot Service"""
    print("\n=== Bot Integration Demo ===")
    
    # Configure bot with AI
    config = {
        'auto_response': {
            'enabled': True,
            'greeting_enabled': False
        },
        'commands': {
            'enabled': True
        },
        'ai': {
            'enabled': True,
            'service_type': 'openai',
            'aircraft_detection_enabled': True,
            'altitude_threshold_meters': 1000
        }
    }
    
    # Create bot service (will fail to initialize AI without real API key)
    bot_service = InteractiveBotService(config)
    
    print("Bot Service Configuration:")
    print(f"  AI Config: {bot_service.config.get('ai', {})}")
    print(f"  AI Service: {'Configured' if bot_service.ai_service else 'Not configured'}")
    print(f"  AI Enabled: {bot_service.ai_enabled}")
    
    # Mock AI service for demonstration
    if bot_service.ai_service:
        mock_provider = AsyncMock()
        mock_provider.is_available.return_value = True
        mock_response = AIResponse(
            content="Roger, I can assist with aviation information.",
            confidence=0.8,
            processing_time=1.0,
            model_used="gpt-3.5-turbo"
        )
        mock_provider.generate_response.return_value = mock_response
        
        bot_service.ai_service.provider = mock_provider
        bot_service.ai_enabled = True
        
        print("  Mock AI Provider: Configured")
    
    # Test AI commands
    test_commands = [
        "aistatus",
        "askai What's the weather like for flying?",
        "help"
    ]
    
    for command in test_commands:
        print(f"\nCommand: {command}")
        
        message = Message(
            sender_id="!pilot01",
            recipient_id=None,
            channel=0,
            content=command,
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # This would normally process the message, but we'll just show the concept
        print(f"  Would process: {command}")


async def demonstrate_fallback_handling():
    """Demonstrate fallback handling when AI is unavailable"""
    print("\n=== Fallback Handling Demo ===")
    
    config = {
        'ai': {
            'enabled': True,
            'service_type': 'openai',
            'fallback_responses': [
                "AI assistant is temporarily unavailable. Please try again later.",
                "I'm having trouble connecting to AI services right now.",
                "Sorry, I can't process that request at the moment."
            ]
        }
    }
    
    service = AIService(config)
    
    # Simulate unavailable service
    print("Simulating unavailable AI service...")
    
    # Create test message
    message = Message(
        sender_id="!test123",
        recipient_id=None,
        channel=0,
        content="What's the weather like?",
        message_type=MessageType.TEXT,
        timestamp=datetime.utcnow()
    )
    
    # This will return None because no provider is available
    response = await service.generate_response(message=message, altitude=1500)
    
    if response:
        print(f"Response: {response.content}")
        print(f"Fallback used: {response.fallback_used}")
    else:
        print("No response - service unavailable")
    
    # Show statistics
    stats = service.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total requests: {stats['requests_total']}")
    print(f"  Failed requests: {stats['requests_failed']}")


async def main():
    """Run all demonstrations"""
    print("AI Integration Framework Demonstration")
    print("=" * 50)
    
    await demonstrate_aircraft_detection()
    await demonstrate_ai_service_config()
    await demonstrate_mock_ai_responses()
    await demonstrate_bot_integration()
    await demonstrate_fallback_handling()
    
    print("\n" + "=" * 50)
    print("Demo completed!")
    print("\nTo use AI integration in production:")
    print("1. Configure your AI service (OpenAI API key or Ollama URL)")
    print("2. Enable aircraft detection in configuration")
    print("3. Set appropriate altitude threshold")
    print("4. Monitor AI service statistics and health")


if __name__ == "__main__":
    asyncio.run(main())