"""
Bot Service Plugin

Wraps the InteractiveBotService as a plugin for the ZephyrGate plugin system.
This allows the bot service to be loaded, managed, and monitored through the
unified plugin architecture.
"""

import asyncio
from typing import Dict, Any, List

# Import from symlinked modules
from core.enhanced_plugin import EnhancedPlugin
from bot.interactive_bot_service import InteractiveBotService
from models.message import Message


class BotServicePlugin(EnhancedPlugin):
    """
    Plugin wrapper for the Interactive Bot Service.
    
    Provides:
    - Auto-response to keywords
    - Command handling system
    - Interactive games
    - Message history
    - AI integration
    - New node greetings
    """
    
    async def initialize(self) -> bool:
        """Initialize the bot service plugin"""
        self.logger.info("Initializing Bot Service Plugin")
        
        try:
            # Create the bot service instance with plugin config
            self.bot_service = InteractiveBotService(self.config)
            
            # Initialize the bot service
            await self.bot_service.start()
            
            # Register message handler to route all messages to bot service
            self.register_message_handler(
                self._handle_message,
                priority=100
            )
            
            # Register bot commands with plugin system
            await self._register_bot_commands()
            
            self.logger.info("Bot Service Plugin initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize bot service: {e}", exc_info=True)
            return False
    
    async def _register_bot_commands(self):
        """Register bot service commands with the plugin system"""
        # Register help command
        self.register_command(
            "help",
            self._handle_help_command,
            "Show available commands and usage information",
            priority=100
        )
        
        # Register ping command
        self.register_command(
            "ping",
            self._handle_ping_command,
            "Test bot responsiveness",
            priority=100
        )
        
        # Register info command
        self.register_command(
            "info",
            self._handle_info_command,
            "Get information about topics",
            priority=100
        )
        
        # Register history command
        self.register_command(
            "history",
            self._handle_history_command,
            "View message history",
            priority=100
        )
        
        # Register game commands if game manager is available
        if hasattr(self.bot_service, 'game_manager') and self.bot_service.game_manager:
            self.register_command(
                "games",
                self._handle_games_command,
                "List available games",
                priority=100
            )
            
            self.register_command(
                "play",
                self._handle_play_command,
                "Start a game",
                priority=100
            )
    
    async def _handle_message(self, message: Message, context: Dict[str, Any] = None) -> bool:
        """
        Handle incoming messages through the bot service.
        
        Args:
            message: The message to handle
            context: Optional context dictionary
        
        Returns:
            True if message was handled, False otherwise.
        """
        try:
            self.logger.debug(f"Bot service plugin handling message: {message.content}")
            
            # Let the bot service process the message
            # This includes auto-response, command detection, etc.
            response = await self.bot_service.handle_message(message)
            
            self.logger.debug(f"Bot service returned response: {response}")
            
            # If we got a response message, send it via message router
            if response:
                self.logger.info(f"Sending bot response: {response.content[:50]}...")
                
                # Get the message router from plugin manager
                if hasattr(self.plugin_manager, 'message_router') and self.plugin_manager.message_router:
                    await self.plugin_manager.message_router.send_message(response, message.interface_id)
                    self.logger.info(f"Response sent via message router")
                else:
                    self.logger.error("Message router not available - cannot send response")
                
                return True
            else:
                self.logger.debug("Bot service returned no response")
                return False
            
        except Exception as e:
            self.logger.error(f"Error handling message in bot service: {e}", exc_info=True)
            return False
    
    async def _handle_help_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle help command"""
        try:
            # For now, return a short help message to avoid overwhelming the radio
            # TODO: Implement proper message chunking with delays
            return "📋 Commands: ping, help, info, history, games, play, status, weather, bbs\nSend 'help <command>' for details"
        except Exception as e:
            self.logger.error(f"Error in help command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_ping_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle ping command"""
        return "Pong! Bot service is running."
    
    async def _handle_info_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle info command"""
        try:
            if not args:
                return "Usage: info <topic>"
            
            # Delegate to bot service's information lookup
            if hasattr(self.bot_service, 'comprehensive_handler'):
                return await self.bot_service.comprehensive_handler.handle_command('info', args, context)
            else:
                return f"Information lookup for: {' '.join(args)}"
        except Exception as e:
            self.logger.error(f"Error in info command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_history_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle history command"""
        try:
            count = 10
            if args and args[0].isdigit():
                count = int(args[0])
            
            # Delegate to bot service's message history
            if hasattr(self.bot_service, 'comprehensive_handler'):
                return await self.bot_service.comprehensive_handler.handle_command('history', args, context)
            else:
                return f"Message history (last {count} messages)"
        except Exception as e:
            self.logger.error(f"Error in history command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_games_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle games list command"""
        try:
            if hasattr(self.bot_service, 'game_manager') and self.bot_service.game_manager:
                games = self.bot_service.game_manager.list_games()
                if games:
                    game_list = "\n".join([f"• {game}" for game in games])
                    return f"Available games:\n{game_list}\n\nUse 'play <game>' to start"
                else:
                    return "No games available"
            else:
                return "Game system not available"
        except Exception as e:
            self.logger.error(f"Error in games command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_play_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle play game command"""
        try:
            if not args:
                return "Usage: play <game_name>"
            
            game_name = args[0].lower()
            
            if hasattr(self.bot_service, 'game_manager') and self.bot_service.game_manager:
                # Delegate to game manager
                result = await self.bot_service.game_manager.start_game(
                    game_name,
                    context.get('sender_id', 'unknown')
                )
                return result
            else:
                return "Game system not available"
        except Exception as e:
            self.logger.error(f"Error in play command: {e}")
            return f"Error: {str(e)}"
    
    async def cleanup(self):
        """Clean up bot service resources"""
        self.logger.info("Cleaning up Bot Service Plugin")
        
        try:
            if hasattr(self, 'bot_service') and self.bot_service:
                await self.bot_service.stop()
            
            self.logger.info("Bot Service Plugin cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up bot service: {e}", exc_info=True)
    
    async def on_message_received(self, message: Message):
        """
        Handle messages received by the plugin system.
        
        This is called by the plugin framework for all messages.
        """
        # The message handler registered in initialize() will handle this
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get bot service status"""
        status = {
            'service': 'bot',
            'running': hasattr(self, 'bot_service') and self.bot_service._running,
            'features': {
                'auto_response': self.get_config('auto_response.enabled', True),
                'commands': self.get_config('commands.enabled', True),
                'games': hasattr(self, 'bot_service') and hasattr(self.bot_service, 'game_manager'),
                'ai': self.get_config('ai.enabled', False)
            }
        }
        
        # Add bot service stats if available
        if hasattr(self, 'bot_service') and hasattr(self.bot_service, 'get_stats'):
            try:
                status['stats'] = self.bot_service.get_stats()
            except:
                pass
        
        return status
    
    def get_metadata(self):
        """Get plugin metadata"""
        from core.plugin_manager import PluginMetadata, PluginPriority
        return PluginMetadata(
            name="bot_service",
            version="1.0.0",
            description="Interactive bot service with command handling, games, and auto-response",
            author="ZephyrGate Team",
            priority=PluginPriority.HIGH
        )
