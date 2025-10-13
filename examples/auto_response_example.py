#!/usr/bin/env python3
"""
Auto-Response System Example

This example demonstrates the enhanced auto-response system capabilities:
- Keyword detection and monitoring
- Emergency keyword alerting with escalation
- New node greeting system
- Configurable auto-response rules and triggers
- Rate limiting and cooldowns
"""

import asyncio
import logging
from datetime import datetime
from unittest.mock import AsyncMock

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.bot.interactive_bot_service import InteractiveBotService, AutoResponseRule
from src.models.message import Message, MessageType, MessagePriority


async def main():
    """Demonstrate the auto-response system"""
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Create bot service with enhanced configuration
    config = {
        'auto_response': {
            'enabled': True,
            'emergency_keywords': ['help', 'emergency', 'urgent', 'mayday', 'sos'],
            'greeting_enabled': True,
            'greeting_message': '🎉 Welcome to ZephyrGate! Send "help" for available commands.',
            'emergency_escalation_delay': 10,  # 10 seconds for demo
            'response_rate_limit': 5,  # 5 responses per hour max
            'cooldown_seconds': 3  # 3 second cooldown between responses
        },
        'commands': {
            'enabled': True,
            'help_enabled': True
        },
        'ai': {
            'enabled': False
        }
    }
    
    # Create bot service
    bot_service = InteractiveBotService(config)
    
    # Mock communication interface for demo
    mock_comm = AsyncMock()
    bot_service.set_communication_interface(mock_comm)
    
    # Mock database for demo
    from unittest.mock import patch, Mock
    with patch('src.services.bot.interactive_bot_service.get_database') as mock_db:
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_db.return_value.cursor.return_value = mock_cursor
        
        # Start the service
        await bot_service.start()
        logger.info("Auto-response system started")
        
        # Demonstrate new node greeting
        logger.info("\n=== New Node Greeting Demo ===")
        new_node_message = Message(
            sender_id="!87654321",
            recipient_id=None,
            channel=0,
            content="hello world",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service.handle_message(new_node_message)
        if response:
            logger.info(f"Auto-response: {response.content}")
        
        # Check if greeting was sent
        if mock_comm.send_mesh_message.called:
            logger.info("✓ New node greeting sent successfully")
        
        # Demonstrate keyword detection
        logger.info("\n=== Keyword Detection Demo ===")
        test_messages = [
            ("ping", "Connectivity test"),
            ("help", "Help request"),
            ("weather", "Weather inquiry"),
            ("games", "Gaming request")
        ]
        
        for content, description in test_messages:
            test_message = Message(
                sender_id="!12345678",
                recipient_id=None,
                channel=0,
                content=content,
                message_type=MessageType.TEXT,
                priority=MessagePriority.NORMAL,
                timestamp=datetime.utcnow()
            )
            
            response = await bot_service.handle_message(test_message)
            if response:
                logger.info(f"{description}: {response.content[:50]}...")
            
            # Wait to avoid rate limiting
            await asyncio.sleep(1)
        
        # Demonstrate rate limiting
        logger.info("\n=== Rate Limiting Demo ===")
        ping_message = Message(
            sender_id="!12345678",
            recipient_id=None,
            channel=0,
            content="ping",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        # First ping should work
        response1 = await bot_service.handle_message(ping_message)
        logger.info(f"First ping: {'✓ Response' if response1 else '✗ No response'}")
        
        # Second ping should be rate limited
        response2 = await bot_service.handle_message(ping_message)
        logger.info(f"Second ping (immediate): {'✓ Response' if response2 else '✗ Rate limited'}")
        
        # Wait for cooldown
        logger.info("Waiting for cooldown...")
        await asyncio.sleep(4)
        
        # Third ping should work after cooldown
        response3 = await bot_service.handle_message(ping_message)
        logger.info(f"Third ping (after cooldown): {'✓ Response' if response3 else '✗ No response'}")
        
        # Demonstrate emergency keyword detection
        logger.info("\n=== Emergency Keyword Demo ===")
        emergency_message = Message(
            sender_id="!99999999",
            recipient_id=None,
            channel=0,
            content="emergency help needed at coordinates 40.7128,-74.0060",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service.handle_message(emergency_message)
        if response:
            logger.info(f"Emergency response: {response.content}")
        
        # Check if emergency escalation task was created
        if bot_service.emergency_escalation_tasks:
            logger.info("✓ Emergency escalation task created")
            logger.info("Waiting for escalation demo (10 seconds)...")
            await asyncio.sleep(11)
            
            # Check if escalation message was sent
            if mock_comm.send_mesh_message.call_count > 1:
                logger.info("✓ Emergency escalation message sent")
        
        # Demonstrate custom rule addition
        logger.info("\n=== Custom Rule Demo ===")
        custom_rule = AutoResponseRule(
            keywords=['demo', 'example'],
            response='🤖 This is a custom auto-response rule demonstration!',
            priority=5,  # High priority
            cooldown_seconds=2,
            max_responses_per_hour=3
        )
        bot_service.add_auto_response_rule(custom_rule)
        
        demo_message = Message(
            sender_id="!11111111",
            recipient_id=None,
            channel=0,
            content="demo test",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
        
        response = await bot_service.handle_message(demo_message)
        if response:
            logger.info(f"Custom rule response: {response.content}")
        
        # Show statistics
        logger.info("\n=== System Statistics ===")
        stats = bot_service.get_response_statistics()
        for key, value in stats.items():
            if key != 'responses_by_rule':
                logger.info(f"{key}: {value}")
        
        # Stop the service
        await bot_service.stop()
        logger.info("\nAuto-response system stopped")


if __name__ == "__main__":
    asyncio.run(main())