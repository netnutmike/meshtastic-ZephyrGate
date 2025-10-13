#!/usr/bin/env python3
"""
Example of BBS Synchronization Service Usage

This example demonstrates the key concepts and message formats used in
BBS synchronization without requiring a full database setup.
"""

import asyncio
import json
import logging
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.bbs.sync_service import SyncPeer, SyncMessage, SyncMessageType
from src.models.message import Message, MessageType


async def main():
    """Example of BBS synchronization concepts and message formats"""
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("BBS Synchronization Service Example")
    logger.info("=" * 50)
    
    # Demonstrate SyncPeer creation
    logger.info("\n1. Creating Sync Peers")
    peer_a = SyncPeer(
        node_id="!AAAAAAAA",
        name="Node A BBS",
        sync_enabled=True,
        priority=1,
        sync_bulletins=True,
        sync_mail=True,
        sync_channels=True,
        max_sync_age_days=30
    )
    
    peer_b = SyncPeer(
        node_id="!BBBBBBBB",
        name="Node B BBS",
        sync_enabled=True,
        priority=2
    )
    
    logger.info(f"Created peer A: {peer_a.name} ({peer_a.node_id})")
    logger.info(f"Created peer B: {peer_b.name} ({peer_b.node_id})")
    
    # Demonstrate sync message creation
    logger.info("\n2. Creating Sync Messages")
    
    # Peer discovery message
    discovery_msg = SyncMessage(
        message_type=SyncMessageType.PEER_DISCOVERY,
        sender_id="!AAAAAAAA",
        recipient_id=None,  # Broadcast
        data={
            "requesting_node": "!AAAAAAAA",
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    logger.info("Created peer discovery message:")
    logger.info(f"  Type: {discovery_msg.message_type.value}")
    logger.info(f"  Sender: {discovery_msg.sender_id}")
    logger.info(f"  Recipient: {discovery_msg.recipient_id or 'Broadcast'}")
    
    # Peer announcement message
    announce_msg = SyncMessage(
        message_type=SyncMessageType.PEER_ANNOUNCE,
        sender_id="!BBBBBBBB",
        recipient_id="!AAAAAAAA",
        data={
            "name": "Node B BBS",
            "capabilities": {
                "bulletins": True,
                "mail": True,
                "channels": True
            },
            "version": "1.0"
        }
    )
    
    logger.info("\nCreated peer announcement message:")
    logger.info(f"  Type: {announce_msg.message_type.value}")
    logger.info(f"  Sender: {announce_msg.sender_id}")
    logger.info(f"  Recipient: {announce_msg.recipient_id}")
    
    # Sync request message
    sync_request_msg = SyncMessage(
        message_type=SyncMessageType.SYNC_REQUEST,
        sender_id="!AAAAAAAA",
        recipient_id="!BBBBBBBB",
        data={
            "last_sync": None,
            "sync_bulletins": True,
            "sync_mail": True,
            "sync_channels": True,
            "max_age_days": 30
        }
    )
    
    logger.info("\nCreated sync request message:")
    logger.info(f"  Type: {sync_request_msg.message_type.value}")
    logger.info(f"  Sender: {sync_request_msg.sender_id}")
    logger.info(f"  Recipient: {sync_request_msg.recipient_id}")
    
    # Demonstrate message serialization
    logger.info("\n3. Message Serialization")
    
    mesh_message = discovery_msg.to_mesh_message()
    logger.info("Serialized discovery message for mesh transmission:")
    logger.info(json.dumps(json.loads(mesh_message), indent=2))
    
    # Demonstrate message deserialization
    logger.info("\n4. Message Deserialization")
    
    parsed_msg = SyncMessage.from_mesh_message(mesh_message)
    if parsed_msg:
        logger.info("Successfully parsed message from mesh format:")
        logger.info(f"  Type: {parsed_msg.message_type.value}")
        logger.info(f"  Sender: {parsed_msg.sender_id}")
        logger.info(f"  Sync ID: {parsed_msg.sync_id}")
    else:
        logger.error("Failed to parse message")
    
    # Demonstrate sync response with data
    logger.info("\n5. Sync Response with Data")
    
    sync_response_msg = SyncMessage(
        message_type=SyncMessageType.SYNC_RESPONSE,
        sender_id="!BBBBBBBB",
        recipient_id="!AAAAAAAA",
        data={
            "bulletins": [
                {
                    "id": 1,
                    "board": "general",
                    "sender_id": "!CCCCCCCC",
                    "sender_name": "TestUser",
                    "subject": "Test Bulletin",
                    "content": "This is a test bulletin for sync",
                    "timestamp": datetime.utcnow().isoformat(),
                    "unique_id": "test-bulletin-123"
                }
            ],
            "channels": [
                {
                    "id": 1,
                    "name": "Local Repeater",
                    "frequency": "146.520",
                    "description": "Local 2m repeater",
                    "channel_type": "repeater",
                    "location": "Test City",
                    "tone": "100.0",
                    "offset": "+0.6"
                }
            ],
            "mail": []
        }
    )
    
    logger.info("Created sync response with sample data:")
    logger.info(f"  Bulletins: {len(sync_response_msg.data['bulletins'])}")
    logger.info(f"  Channels: {len(sync_response_msg.data['channels'])}")
    logger.info(f"  Mail: {len(sync_response_msg.data['mail'])}")
    
    # Show sync acknowledgment
    logger.info("\n6. Sync Acknowledgment")
    
    ack_msg = SyncMessage(
        message_type=SyncMessageType.SYNC_ACK,
        sender_id="!AAAAAAAA",
        recipient_id="!BBBBBBBB",
        data={
            "success": True,
            "conflicts": 0,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    logger.info("Created sync acknowledgment:")
    logger.info(f"  Success: {ack_msg.data['success']}")
    logger.info(f"  Conflicts: {ack_msg.data['conflicts']}")
    
    # Show peer configuration options
    logger.info("\n7. Peer Configuration Options")
    logger.info(f"Peer A Configuration:")
    logger.info(f"  - Sync bulletins: {peer_a.sync_bulletins}")
    logger.info(f"  - Sync mail: {peer_a.sync_mail}")
    logger.info(f"  - Sync channels: {peer_a.sync_channels}")
    logger.info(f"  - Max sync age: {peer_a.max_sync_age_days} days")
    logger.info(f"  - Priority: {peer_a.priority}")
    logger.info(f"  - Enabled: {peer_a.sync_enabled}")
    
    # Show message types
    logger.info("\n8. Available Sync Message Types")
    for msg_type in SyncMessageType:
        logger.info(f"  - {msg_type.value}")
    
    logger.info("\n" + "=" * 50)
    logger.info("BBS synchronization example completed!")
    logger.info("\nKey Features Demonstrated:")
    logger.info("- Peer management and configuration")
    logger.info("- Sync message creation and serialization")
    logger.info("- Message types for different sync operations")
    logger.info("- Data structures for bulletins, channels, and mail")
    logger.info("- Conflict resolution and acknowledgment")
    logger.info("\nIn a real deployment, these messages would be:")
    logger.info("- Sent over Meshtastic mesh network")
    logger.info("- Processed by the BBSSyncService")
    logger.info("- Used to synchronize BBS data between nodes")
    logger.info("- Handled with duplicate prevention and conflict resolution")


if __name__ == "__main__":
    asyncio.run(main())