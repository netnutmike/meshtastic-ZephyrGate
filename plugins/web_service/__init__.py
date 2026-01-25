"""
Web Admin Service Plugin

Wraps the Web Admin service as a plugin for the ZephyrGate plugin system.
"""

from .plugin import WebServicePlugin

__all__ = ['WebServicePlugin']
