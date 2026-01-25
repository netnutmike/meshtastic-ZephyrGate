"""
Asset Tracking Service Plugin

Wraps the Asset Tracking service as a plugin for the ZephyrGate plugin system.
"""

from .plugin import AssetServicePlugin

__all__ = ['AssetServicePlugin']
