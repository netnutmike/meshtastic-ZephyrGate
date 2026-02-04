"""
Bot/Games Command System for ZephyrGate

Stateless command system - all commands work globally without menu state tracking.
This is ideal for off-grid systems where connection state is unreliable.
"""

import asyncio
import logging
from typing import Any, Dict, List

class BotCommandSystem:
    """
    Stateless bot command system.
    
    All commands are globally unique and work from anywhere.
    Menu commands just display help - no state tracking needed.
    """
    
    def __init__(self, bot_service):
        self.logger = logging.getLogger(__name__)
        self.bot_service = bot_service
    
    async def process_command(self, user_id: str, command: str, context: Dict[str, Any] = None) -> str:
        """Process bot command and return response - stateless"""
        try:
            context = context or {}
            
            # Parse command and arguments
            parts = command.strip().split()
            if not parts:
                return self._show_bot_help()
            
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            # Route to appropriate handler - all commands work globally
            if cmd in ['help', '?']:
                return self._show_bot_help()
            elif cmd == 'utils':
                return self._show_utils_help()
            elif cmd == 'games':
                return self._show_games_help()
            elif cmd == 'info':
                return await self._handle_info(args, context)
            elif cmd == 'stats':
                return await self._show_stats(args)
            elif cmd == 'glist':
                return await self._list_games(args)
            elif cmd == 'gplay':
                return await self._play_game(user_id, args, context)
            elif cmd == 'gstop':
                return await self._stop_game(user_id, args)
            elif cmd == 'gstatus':
                return await self._game_status(user_id, args)
            elif cmd == 'gscores':
                return await self._high_scores(args)
            else:
                return f"Unknown: {cmd}\nType 'help' for commands"
        
        except Exception as e:
            self.logger.error(f"Error processing bot command '{command}' for {user_id}: {e}")
            return "Error processing command"
    
    def _show_bot_help(self) -> str:
        """Show main bot help"""
        return """🤖 Bot Commands
info - App info
stats - System stats
utils - Utilities
games - Games menu
glist - List games
gplay <name> - Start
gstop - Stop game
gstatus - Status
gscores - Scores"""
    
    def _show_utils_help(self) -> str:
        """Show utils menu help"""
        return """🔧 Utils
info - App info
stats - System stats
All commands work globally"""
    
    def _show_games_help(self) -> str:
        """Show games menu help"""
        return """🎮 Games
glist - List games
gplay <name> - Start
gstop - Stop game
gstatus - Status
gscores - Scores
All commands work globally"""
    
    # Command handlers - all stateless
    
    async def _handle_info(self, args: List[str], context: Dict[str, Any] = None) -> str:
        """Handle info command - show application information"""
        try:
            lines = []
            lines.append("ℹ️ ZephyrGate")
            
            # Get version
            try:
                with open('VERSION', 'r') as f:
                    version = f.read().strip()
                    lines.append(f"Version: {version}")
            except:
                lines.append("Version: Unknown")
            
            # Get enabled plugins from config
            if hasattr(self.bot_service, 'config'):
                config = self.bot_service.config
                enabled_plugins = config.get('plugins', {}).get('enabled_plugins', [])
                if enabled_plugins:
                    lines.append(f"\nPlugins: {len(enabled_plugins)}")
                    # Show first few plugins
                    for plugin in enabled_plugins[:5]:
                        lines.append(f"• {plugin}")
                    if len(enabled_plugins) > 5:
                        lines.append(f"• ...and {len(enabled_plugins) - 5} more")
            
            # Get bot features
            if hasattr(self.bot_service, 'config'):
                bot_config = self.bot_service.config.get('bot', {})
                lines.append("\nBot Features:")
                lines.append(f"• Auto-response: {'✓' if bot_config.get('auto_response') else '✗'}")
                lines.append(f"• Games: {'✓' if bot_config.get('games', {}).get('enabled') else '✗'}")
                lines.append(f"• AI: {'✓' if bot_config.get('ai', {}).get('enabled') else '✗'}")
            
            return "\n".join(lines)
        except Exception as e:
            self.logger.error(f"Error in info command: {e}")
            return "ℹ️ ZephyrGate\nVersion: 1.1.0"
    
    async def _show_stats(self, args: List[str]) -> str:
        """Show system statistics"""
        try:
            lines = []
            lines.append("📊 System Stats")
            
            # Get database stats
            try:
                from core.database import get_database
                db = get_database()
                db_stats = db.get_stats()
                
                lines.append("\nDatabase:")
                lines.append(f"• Nodes: {db_stats.get('users', 0)}")
                lines.append(f"• Messages: {db_stats.get('message_history', 0)}")
                lines.append(f"• Bulletins: {db_stats.get('bulletins', 0)}")
                lines.append(f"• Mail: {db_stats.get('mail', 0)}")
                lines.append(f"• Channels: {db_stats.get('channels', 0)}")
                lines.append(f"• SOS: {db_stats.get('sos_incidents', 0)}")
                
                # Database size
                size_bytes = db_stats.get('database_size_bytes', 0)
                size_mb = size_bytes / (1024 * 1024)
                lines.append(f"• DB Size: {size_mb:.1f} MB")
                
            except Exception as e:
                self.logger.error(f"Error getting database stats: {e}")
                lines.append("\nDatabase: Not available")
            
            # Get bot stats if available
            if hasattr(self.bot_service, 'get_stats'):
                try:
                    # Check if get_stats is async or sync
                    stats_method = self.bot_service.get_stats
                    if asyncio.iscoroutinefunction(stats_method):
                        bot_stats = await stats_method()
                    else:
                        bot_stats = stats_method()
                    
                    lines.append("\nBot Service:")
                    lines.append(f"• Sessions: {bot_stats.get('active_sessions', 0)}")
                    lines.append(f"• Commands: {bot_stats.get('commands_executed', 0)}")
                    lines.append(f"• Games: {bot_stats.get('active_games', 0)}")
                except Exception as e:
                    self.logger.error(f"Error getting bot stats: {e}")
            
            # Get game manager stats
            if hasattr(self.bot_service, 'game_manager') and self.bot_service.game_manager:
                try:
                    game_stats = await self.bot_service.game_manager.get_session_stats()
                    lines.append("\nGames:")
                    lines.append(f"• Available: {game_stats.get('total_games', 0)}")
                    lines.append(f"• Active: {game_stats.get('active_sessions', 0)}")
                except Exception as e:
                    self.logger.error(f"Error getting game stats: {e}")
            
            return "\n".join(lines)
        except Exception as e:
            self.logger.error(f"Error getting system stats: {e}")
            return f"Error: {str(e)}"
    
    # Game commands - fixed to use correct GameManager methods
    
    async def _list_games(self, args: List[str]) -> str:
        """List available games"""
        try:
            if hasattr(self.bot_service, 'game_manager') and self.bot_service.game_manager:
                # Use get_available_games() not list_games()
                games = self.bot_service.game_manager.get_available_games()
                if games:
                    result = ["🎮 Games"]
                    for game in games:
                        result.append(f"• {game}")
                    result.append("\ngplay <name> to start")
                    return "\n".join(result)
                else:
                    return "No games available"
            else:
                return "Game system not available"
        except Exception as e:
            self.logger.error(f"Error listing games: {e}")
            return f"Error: {str(e)}"
    
    async def _play_game(self, user_id: str, args: List[str], context: Dict[str, Any] = None) -> str:
        """Start a game"""
        try:
            if not args:
                return "Usage: gplay <game>"
            
            game_name = args[0].lower()
            player_name = context.get('sender_name', user_id) if context else user_id
            
            if hasattr(self.bot_service, 'game_manager') and self.bot_service.game_manager:
                # Use correct method signature
                result = await self.bot_service.game_manager.start_game(
                    game_name,
                    user_id,
                    player_name
                )
                return result if result else f"Game '{game_name}' not found"
            else:
                return "Game system not available"
        except Exception as e:
            self.logger.error(f"Error starting game: {e}")
            return f"Error: {str(e)}"
    
    async def _stop_game(self, user_id: str, args: List[str]) -> str:
        """Stop current game"""
        try:
            if hasattr(self.bot_service, 'game_manager') and self.bot_service.game_manager:
                # Use process_game_input with 'quit' command
                result = await self.bot_service.game_manager.process_game_input(user_id, 'quit')
                return result if result else "No active game"
            else:
                return "Game system not available"
        except Exception as e:
            self.logger.error(f"Error stopping game: {e}")
            return f"Error: {str(e)}"
    
    async def _game_status(self, user_id: str, args: List[str]) -> str:
        """Check game status"""
        try:
            if hasattr(self.bot_service, 'game_manager') and self.bot_service.game_manager:
                # Get active session
                session = self.bot_service.game_manager.get_active_session(user_id)
                if session:
                    result = ["🎮 Game Status"]
                    result.append(f"Game: {session.game_type}")
                    result.append(f"State: {session.state.value}")
                    return "\n".join(result)
                else:
                    return "No active game"
            else:
                return "Game system not available"
        except Exception as e:
            self.logger.error(f"Error getting game status: {e}")
            return f"Error: {str(e)}"
    
    async def _high_scores(self, args: List[str]) -> str:
        """View high scores"""
        try:
            # High scores not implemented in GameManager yet
            return "🏆 High scores\nComing soon!"
        except Exception as e:
            self.logger.error(f"Error getting high scores: {e}")
            return f"Error: {str(e)}"
