#!/usr/bin/env python3
"""
JS8Call Integration Example for ZephyrGate

This example demonstrates how to use the JS8Call integration service
to connect to JS8Call, monitor messages, and forward urgent messages
to the mesh network.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import initialize_database
from src.services.bbs.js8call_service import JS8CallConfig, JS8CallService
from src.services.bbs.models import JS8CallMessage, JS8CallPriority


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def mesh_callback(message: str, source: str):
    """
    Mock mesh callback function that would normally send messages to the mesh network.
    In a real implementation, this would interface with the Meshtastic device.
    """
    logger.info(f"MESH FORWARD [{source}]: {message}")


async def simulate_js8call_messages(service: JS8CallService):
    """
    Simulate receiving JS8Call messages for demonstration purposes.
    In a real implementation, these would come from the JS8Call TCP API.
    """
    logger.info("Simulating JS8Call messages...")
    
    # Simulate normal message
    normal_msg = JS8CallMessage(
        callsign="KI7ABC",
        group="@ALLCALL",
        message="Weather report: Clear skies, 72F",
        frequency="14078000",
        priority=JS8CallPriority.NORMAL,
        timestamp=datetime.utcnow()
    )
    await service._handle_js8call_message(normal_msg)
    
    await asyncio.sleep(1)
    
    # Simulate urgent message
    urgent_msg = JS8CallMessage(
        callsign="KI7DEF",
        group="@ALLCALL",
        message="Traffic accident on I-5 northbound, mile marker 127",
        frequency="14078000",
        priority=JS8CallPriority.URGENT,
        timestamp=datetime.utcnow()
    )
    await service._handle_js8call_message(urgent_msg)
    
    await asyncio.sleep(1)
    
    # Simulate emergency message
    emergency_msg = JS8CallMessage(
        callsign="KI7EMG",
        group="@ALLCALL",
        message="Emergency: Hiker lost on Mount Rainier, grid CN87",
        frequency="14078000",
        priority=JS8CallPriority.EMERGENCY,
        timestamp=datetime.utcnow()
    )
    await service._handle_js8call_message(emergency_msg)


async def main():
    """Main example function"""
    logger.info("Starting JS8Call Integration Example")
    
    # Initialize database
    db_manager = initialize_database('data/js8call_example.db')
    logger.info("Database initialized")
    
    # Configure JS8Call integration
    config = JS8CallConfig(
        enabled=True,
        host="localhost",
        port=2442,
        monitored_groups=["@ALLCALL", "@EMCOMM", "@WEATHER"],
        urgent_keywords=["urgent", "priority", "traffic", "accident"],
        emergency_keywords=["emergency", "mayday", "sos", "help", "lost"],
        auto_forward_urgent=True,
        auto_forward_emergency=True,
        reconnect_interval=30
    )
    
    logger.info(f"JS8Call config: enabled={config.enabled}, "
                f"monitored_groups={config.monitored_groups}")
    
    # Create JS8Call service
    service = JS8CallService(config, mesh_callback)
    
    try:
        # Note: In this example, we don't actually start the JS8Call client
        # because it would try to connect to a real JS8Call instance.
        # Instead, we simulate message handling.
        
        logger.info("JS8Call service created (not connecting to real JS8Call for demo)")
        
        # Simulate receiving and processing messages
        await simulate_js8call_messages(service)
        
        # Display statistics
        stats = service.get_statistics()
        logger.info(f"Service statistics: {stats}")
        
        # Show recent messages
        recent_messages = service.get_recent_messages(10)
        logger.info(f"Recent messages count: {len(recent_messages)}")
        
        for msg in recent_messages:
            logger.info(f"  {msg.timestamp}: {msg.callsign} -> {msg.group}: "
                       f"{msg.message} (Priority: {msg.priority.value})")
        
        # Show urgent messages only
        urgent_messages = service.get_urgent_messages()
        logger.info(f"Urgent messages count: {len(urgent_messages)}")
        
        for msg in urgent_messages:
            logger.info(f"  URGENT: {msg.callsign}: {msg.message}")
        
        # Search for specific content
        search_results = service.search_messages("emergency")
        logger.info(f"Messages containing 'emergency': {len(search_results)}")
        
        # Test group management
        logger.info(f"Monitored groups: {service.get_monitored_groups()}")
        service.add_monitored_group("@NEWGROUP")
        logger.info(f"After adding @NEWGROUP: {service.get_monitored_groups()}")
        service.remove_monitored_group("@NEWGROUP")
        logger.info(f"After removing @NEWGROUP: {service.get_monitored_groups()}")
        
    except Exception as e:
        logger.error(f"Error in JS8Call example: {e}")
        raise
    
    logger.info("JS8Call Integration Example completed")


if __name__ == "__main__":
    asyncio.run(main())