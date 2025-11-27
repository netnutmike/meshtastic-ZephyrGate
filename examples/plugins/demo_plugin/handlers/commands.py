"""
Command handlers for demo_plugin plugin

This module contains command handler implementations.
"""

from typing import List, Dict, Any


async def handle_custom_command(args: List[str], context: Dict[str, Any]) -> str:
    """
    Handle a custom command.
    
    Args:
        args: Command arguments
        context: Command context (sender, channel, etc.)
        
    Returns:
        Response message
    """
    sender = context.get('sender_id', 'unknown')
    
    # Implement your command logic here
    response = f"Custom command executed by {sender}"
    
    if args:
        response += f" with args: {' '.join(args)}"
    
    return response
