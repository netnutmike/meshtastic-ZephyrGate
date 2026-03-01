"""
Chat Platform Bridge Plugin

Provides bidirectional messaging between Meshtastic mesh networks and
popular chat platforms (Slack, Discord).

Features:
- Forward mesh messages to Slack/Discord channels
- Receive messages from Slack/Discord and send to mesh
- Flexible channel mapping and routing
- Message filtering and transformation
- Queue management for reliability
- Rate limiting and loop prevention
"""

__version__ = "0.1.0"
__author__ = "ZephyrGate Team"

from .plugin import ChatPlatformBridgePlugin, create_plugin

__all__ = ["ChatPlatformBridgePlugin", "create_plugin"]
