"""MQTT Gateway Plugin for ZephyrGate.

This plugin forwards Meshtastic mesh messages to MQTT brokers following
the official Meshtastic MQTT protocol standards.
"""

from .plugin import MQTTGatewayPlugin

__all__ = ['MQTTGatewayPlugin']
