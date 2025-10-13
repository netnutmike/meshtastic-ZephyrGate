"""
Email Gateway Service Package

Provides two-way email gateway functionality for bridging mesh network
communications with email systems.
"""

from .email_service import EmailGatewayService

__all__ = ['EmailGatewayService']