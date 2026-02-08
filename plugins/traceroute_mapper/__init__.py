"""Network Traceroute Mapper Plugin for ZephyrGate.

This plugin automatically discovers and maps mesh network topology by performing
intelligent traceroutes to nodes. It prioritizes important network changes,
respects network health constraints, and publishes results to MQTT for
visualization by mapping tools.
"""

from .plugin import TracerouteMapperPlugin

__all__ = ['TracerouteMapperPlugin']
