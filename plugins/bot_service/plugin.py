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
from models.message import Message

# Import from local bot modules
from .bot.interactive_bot_service import InteractiveBotService
from .bot.menu_system import BotCommandSystem


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
            
            # Create stateless command system (no menu state tracking)
            self.command_system = BotCommandSystem(self.bot_service)
            
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
    
    async def start(self) -> bool:
        """
        Start the plugin and set plugin manager on bot service.
        """
        self.logger.info("Bot service plugin starting...")
        
        # Set the plugin manager on the bot service so it can call other plugins
        self.bot_service.plugin_manager = self.plugin_manager
        self.logger.info("✓ Set plugin manager on bot service")
        
        # Call parent start
        result = await super().start()
        self.logger.info(f"Bot service plugin started: {result}")
        return result
    
    async def _register_bot_commands(self):
        """Register bot service commands with the plugin system"""
        # Register help command (always available)
        self.register_command(
            "help",
            self._handle_help_command,
            "Show available commands and usage information",
            priority=100
        )
        
        # Register ping command (always available)
        self.register_command(
            "ping",
            self._handle_ping_command,
            "Test bot responsiveness",
            priority=100
        )
        
        # Utils menu command
        self.register_command(
            "utils",
            self._handle_utils_menu_command,
            "System utilities help",
            priority=100
        )
        
        # Games menu command
        self.register_command(
            "games",
            self._handle_games_menu_command,
            "Games help",
            priority=100
        )
        
        # Bot commands - route to command system
        self.register_command(
            "info",
            self._handle_quick_info_command,
            "Application information",
            priority=100
        )
        
        self.register_command(
            "stats",
            self._handle_quick_stats_command,
            "System statistics",
            priority=100
        )
        
        self.register_command(
            "glist",
            self._handle_quick_glist_command,
            "List available games",
            priority=100
        )
        
        self.register_command(
            "gplay",
            self._handle_quick_play_command,
            "Start a game",
            priority=100
        )
        
        self.register_command(
            "gstop",
            self._handle_quick_gstop_command,
            "Stop current game",
            priority=100
        )
        
        self.register_command(
            "gstatus",
            self._handle_quick_gstatus_command,
            "Show game status",
            priority=100
        )
        
        self.register_command(
            "gscores",
            self._handle_quick_gscores_command,
            "View high scores",
            priority=100
        )
        
        self.register_command(
            "history",
            self._handle_quick_history_command,
            "View message history",
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
            
            # Check if message starts with a bot command
            sender_id = message.sender_id
            content = message.content.strip()
            
            # Bot commands: utils, games, glist, gplay, gstop, gstatus, gscores, info, stats
            bot_commands = ['utils', 'games', 'glist', 'gplay', 'gstop', 'gstatus', 'gscores', 'info', 'stats']
            first_word = content.split()[0].lower() if content else ''
            
            if first_word in bot_commands:
                # Route through command system
                self.logger.debug(f"Routing bot command: {content}")
                response_text = await self.command_system.process_command(
                    sender_id, 
                    content,
                    context
                )
                
                if response_text:
                    # Create response message
                    response = Message(
                        sender_id="system",
                        recipient_id=sender_id,
                        content=response_text,
                        interface_id=message.interface_id
                    )
                    
                    # Send via message router
                    if hasattr(self.plugin_manager, 'message_router') and self.plugin_manager.message_router:
                        await self.plugin_manager.message_router.send_message(response, message.interface_id)
                        return True
                
                return False
            
            # Not a bot command - let the bot service process normally
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
        """Handle help command - shows all registered commands from all plugins"""
        try:
            # Get the global command handler from plugin_manager's message_router
            if hasattr(self.plugin_manager, 'message_router') and self.plugin_manager.message_router:
                command_handler = self.plugin_manager.message_router.command_handler
                all_commands = command_handler.get_all_commands()
                
                if not args:
                    # Show compact organized help
                    help_lines = ["📋 Commands"]
                    
                    # Critical Quick Access Only
                    help_lines.append("Quick: sos, info, wx, weather")
                    
                    # Submenus (where most commands live)
                    help_lines.append("Menus: emergency, asset, bbs, mail, channels, utils, games")
                    
                    # Other
                    help_lines.append("Other: forecast, alerts, email, ping")
                    
                    # Tips
                    help_lines.append("\nhelp <menu> for submenu commands")
                    
                    return "\n".join(help_lines)
                else:
                    # Show help for specific command or submenu
                    cmd = args[0].lower()
                    
                    # Check if it's a submenu request
                    submenu_help = {
                        'emergency': self._get_emergency_help(),
                        'asset': self._get_asset_help(),
                        'bbs': self._get_bbs_help(),
                        'mail': self._get_mail_help(),
                        'channels': self._get_channels_help(),
                        'utils': self._get_utils_help(),
                        'games': self._get_games_help(),
                    }
                    
                    if cmd in submenu_help:
                        return submenu_help[cmd]
                    
                    # Regular command help
                    if cmd in all_commands:
                        help_texts = []
                        for handler_info in all_commands[cmd]:
                            help_text = handler_info.get('help', 'No help available')
                            help_texts.append(f"{help_text}")
                        return f"{cmd}: " + " | ".join(help_texts)
                    else:
                        return f"Unknown: {cmd}\nUse 'help' to see all"
            else:
                # Fallback if message_router not available
                return "Commands: ping, help, info, games, play, history\nhelp <cmd> for details"
        except Exception as e:
            self.logger.error(f"Error in help command: {e}")
            return f"Error: {str(e)}"
    
    def _get_emergency_help(self) -> str:
        """Get help for emergency submenu"""
        return """🚨 Emergency
sos [msg] - SOS alert
emergency - Menu
  sos, cancel, respond
  status, incidents"""
    
    def _get_asset_help(self) -> str:
        """Get help for asset submenu"""
        return """📦 Asset
asset - Menu
  list, register, locate
  status, tracking
  geofence"""
    
    def _get_bbs_help(self) -> str:
        """Get help for BBS submenu"""
        return """📋 BBS
bbs - Menu
  list, read, post
  boards, board <name>
  delete, search"""
    
    def _get_mail_help(self) -> str:
        """Get help for mail submenu"""
        return """📧 Mail
mail - Menu
  list, read, send
  delete
Send: mail send
  End with '.'"""
    
    def _get_channels_help(self) -> str:
        """Get help for channels submenu"""
        return """📻 Channels
channels - Menu
  list, add
  info <id>
  search <term>"""
    
    def _get_utils_help(self) -> str:
        """Get help for utils submenu"""
        return """🔧 Utils
utils - info, stats
System information
Network statistics"""
    
    def _get_games_help(self) -> str:
        """Get help for games submenu"""
        return """🎮 Games
games - Enter menu
glist - Show games
gplay <name> - Start
gstop - Stop game
gstatus - Status
gscores - Scores"""
    
    async def _handle_ping_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle ping command"""
        return "Pong! Bot service is running."
    
    async def _handle_utils_menu_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle utils menu command - shows utils help"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Build command string from args or show help
            command = 'utils ' + ' '.join(args) if args else 'utils'
            
            # Process command through command system
            return await self.command_system.process_command(sender_id, command, context)
            
        except Exception as e:
            self.logger.error(f"Error in utils menu command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_games_menu_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle games menu command - shows games help"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Build command string from args or show help
            command = 'games ' + ' '.join(args) if args else 'games'
            
            # Process command through command system
            return await self.command_system.process_command(sender_id, command, context)
            
        except Exception as e:
            self.logger.error(f"Error in games menu command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_quick_info_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick info command - shows application information"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Route to command system for app info
            return await self.command_system.process_command(sender_id, 'info', context)
            
        except Exception as e:
            self.logger.error(f"Error in info command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_quick_stats_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick stats command - shows system statistics"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Route to command system for stats
            return await self.command_system.process_command(sender_id, 'stats', context)
            
        except Exception as e:
            self.logger.error(f"Error in stats command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_quick_glist_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick glist command - list games"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Route to command system
            return await self.command_system.process_command(sender_id, 'glist', context)
            
        except Exception as e:
            self.logger.error(f"Error in glist command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_quick_gstop_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick gstop command - stop game"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Route to command system
            return await self.command_system.process_command(sender_id, 'gstop', context)
            
        except Exception as e:
            self.logger.error(f"Error in gstop command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_quick_gstatus_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick gstatus command - show game status"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Route to command system
            return await self.command_system.process_command(sender_id, 'gstatus', context)
            
        except Exception as e:
            self.logger.error(f"Error in gstatus command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_quick_gscores_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick gscores command - show high scores"""
        try:
            sender_id = context.get('sender_id', 'unknown')
            
            # Route to command system
            return await self.command_system.process_command(sender_id, 'gscores', context)
            
        except Exception as e:
            self.logger.error(f"Error in gscores command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_quick_games_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick games command (always available)"""
        try:
            if hasattr(self.bot_service, 'game_manager') and self.bot_service.game_manager:
                games = self.bot_service.game_manager.list_games()
                if games:
                    game_list = "\n".join([f"• {game}" for game in games])
                    return f"🎮 Available games:\n{game_list}\n\nUse 'play <game>' to start"
                else:
                    return "No games available"
            else:
                return "Game system not available"
        except Exception as e:
            self.logger.error(f"Error in games command: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_quick_play_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick play command (always available)"""
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
    
    async def _handle_quick_history_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quick history command (always available)"""
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
