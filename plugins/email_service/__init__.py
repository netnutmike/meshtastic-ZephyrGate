"""
Email Service Plugin

Wraps the Email Gateway service as a plugin for the ZephyrGate plugin system.
"""

from .plugin import EmailServicePlugin

__all__ = ['EmailServicePlugin']
