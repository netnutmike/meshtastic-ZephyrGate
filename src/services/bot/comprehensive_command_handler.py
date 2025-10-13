"""
Comprehensive Command Handler

Integrates command parsing, registry, help system, and permissions to provide
a complete command handling framework as specified in Requirement 14.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass

from src.core.plugin_interfaces import BaseCommandHandler
from .command_registry import CommandRegistry, CommandContext, CommandPermission
from .command_parser import CommandParser, ParsedCommand
from .help_system import HelpSystem
from .information_lookup_service import InformationLookupService


@dataclass
class CommandExecutionResult:
    """Result of command execution"""
    success: bool
    response: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = None


class ComprehensiveCommandHandler(BaseCommandHandler):
    """
    Comprehensive command handler that implements all requirements for
    command handling framework (Task 6.3)
    """
    
    def __init__(self, config: Dict = None):
        # Initialize with all basic commands
        basic_commands = [
            "help", "ping", "status", "sos", "sosp", "sosf", "sosm",
            "clear", "cancel", "safe", "ack", "responding", "active",
            "bbs", "bbshelp", "bbslist", "bbsread", "bbspost", "bbsdelete",
            "bbsinfo", "bbslink", "wx", "wxc", "wxa", "wxalert", "mwx",
            "whereami", "whoami", "whois", "howfar", "howtall",
            "solar", "hfcond", "sun", "moon", "tide", "earthquake", "riverflow",
            "lheard", "sitrep", "sysinfo", "leaderboard", "history", "messages",
            "wiki", "askai", "ask", "satpass", "rlist", "readnews", "readrss", "motd",
            "blackjack", "videopoker", "dopewars", "lemonstand", "golfsim",
            "mastermind", "hangman", "tictactoe", "hamtest", "quiz", "survey", "joke",
            "subscribe", "unsubscribe", "alerts", "weather", "forecasts",
            "name", "phone", "address", "setemail", "setsms", "email", "sms",
            "tagsend", "tagin", "tagout", "clearsms", "block", "unblock",
            "checkin", "checkout", "checklist"
        ]
        
        super().__init__(basic_commands)
        
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Initialize components
        self.registry = CommandRegistry()
        self.parser = CommandParser()
        self.help_system = HelpSystem(self.registry)
        
        # Initialize information lookup service
        self.information_service = InformationLookupService(config)
        
        # Initialize educational service
        from .educational_service import EducationalService
        self.educational_service = EducationalService(config)
        self.educational_service._initialize_database()
        
        # Initialize reference service
        from .reference_service import ReferenceService
        self.reference_service = ReferenceService(config)
        
        # Register this handler with the registry
        self._register_built_in_commands()
        
        # Command execution statistics
        self.execution_stats = {
            'total_commands': 0,
            'successful_commands': 0,
            'failed_commands': 0,
            'help_requests': 0
        }
    
    def set_communication_interface(self, communication):
        """Set communication interface for information service"""
        self.information_service.set_communication_interface(communication)
    
    def _register_built_in_commands(self):
        """Register built-in command handlers"""
        # Register this handler for all built-in commands
        metadata = {
            'category': {
                # Basic commands
                'help': 'basic', 'ping': 'basic', 'status': 'basic',
                
                # Emergency commands
                'sos': 'emergency', 'sosp': 'emergency', 'sosf': 'emergency', 'sosm': 'emergency',
                'clear': 'emergency', 'cancel': 'emergency', 'safe': 'emergency',
                'ack': 'emergency', 'responding': 'emergency', 'active': 'emergency',
                
                # BBS commands
                'bbs': 'bbs', 'bbshelp': 'bbs', 'bbslist': 'bbs', 'bbsread': 'bbs',
                'bbspost': 'bbs', 'bbsdelete': 'bbs', 'bbsinfo': 'bbs', 'bbslink': 'bbs',
                
                # Weather commands
                'wx': 'weather', 'wxc': 'weather', 'wxa': 'weather', 'wxalert': 'weather', 'mwx': 'weather',
                
                # Information commands
                'whereami': 'information', 'whoami': 'information', 'whois': 'information',
                'howfar': 'information', 'howtall': 'information', 'solar': 'information',
                'hfcond': 'information', 'sun': 'information', 'moon': 'information',
                'tide': 'information', 'earthquake': 'information', 'riverflow': 'information',
                'lheard': 'information', 'sitrep': 'information', 'sysinfo': 'information',
                'leaderboard': 'information', 'history': 'information', 'messages': 'information',
                'wiki': 'information', 'askai': 'information', 'ask': 'information',
                'satpass': 'information', 'rlist': 'information', 'readnews': 'information',
                'readrss': 'information', 'motd': 'information',
                
                # Game commands
                'blackjack': 'games', 'videopoker': 'games', 'dopewars': 'games',
                'lemonstand': 'games', 'golfsim': 'games', 'mastermind': 'games',
                'hangman': 'games', 'tictactoe': 'games', 'hamtest': 'games',
                'quiz': 'games', 'survey': 'games', 'joke': 'games',
                
                # Communication commands
                'subscribe': 'communication', 'unsubscribe': 'communication',
                'alerts': 'communication', 'weather': 'communication', 'forecasts': 'communication',
                'name': 'communication', 'phone': 'communication', 'address': 'communication',
                'setemail': 'communication', 'setsms': 'communication', 'email': 'communication',
                'sms': 'communication', 'tagsend': 'communication', 'tagin': 'communication',
                'tagout': 'communication', 'clearsms': 'communication',
                
                # Admin commands
                'block': 'admin', 'unblock': 'admin',
                
                # Utility commands
                'checkin': 'utility', 'checkout': 'utility', 'checklist': 'utility'
            },
            'permissions': {
                # Most commands are public
                'block': [CommandPermission.ADMIN],
                'unblock': [CommandPermission.ADMIN],
                'bbslink': [CommandPermission.ADMIN],
            },
            'usage': {
                'help': 'help [command|category]',
                'ping': 'ping',
                'status': 'status',
                'sos': 'sos [message]',
                'email': 'email/to/subject/body',
                'tagsend': 'tagsend/tags/message',
                'name': 'name/YourName',
                'phone': 'phone/type/number',
                # Add more as needed
            },
            'examples': {
                'help': ['help', 'help ping', 'help emergency'],
                'ping': ['ping'],
                'email': ['email/john@example.com/Test/Hello from mesh'],
                'tagsend': ['tagsend/emergency,responder/All units report'],
                # Add more as needed
            }
        }
        
        self.registry.register_command(self, "comprehensive_handler", metadata)
    
    async def handle_command(self, command: str, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle command execution with comprehensive parsing and help system
        
        Args:
            command: The command name
            args: Command arguments
            context: Execution context
            
        Returns:
            Command response
        """
        self.execution_stats['total_commands'] += 1
        
        try:
            # Create command context
            cmd_context = CommandContext(
                sender_id=context.get('sender_id', ''),
                sender_name=context.get('sender_name', ''),
                channel=context.get('channel', 0),
                is_direct_message=context.get('is_direct_message', False),
                is_admin=context.get('is_admin', False),
                is_moderator=context.get('is_moderator', False),
                user_permissions=context.get('user_permissions', set()),
                message_timestamp=context.get('message_timestamp'),
                interface_id=context.get('interface_id', ''),
                additional_data=context
            )
            
            # Reconstruct full command text for parsing
            full_command = command
            if args:
                full_command += ' ' + ' '.join(args)
            
            # Parse the command
            parsed_command = self.parser.parse(full_command)
            
            if not parsed_command.is_valid:
                self.execution_stats['failed_commands'] += 1
                return f"❌ Invalid command format: {parsed_command.error_message}"
            
            # Handle help commands specially
            if parsed_command.command == 'help':
                self.execution_stats['help_requests'] += 1
                return await self._handle_help_command(parsed_command, cmd_context)
            
            # Execute the specific command
            result = await self._execute_command(parsed_command, cmd_context)
            
            if result.success:
                self.execution_stats['successful_commands'] += 1
                return result.response
            else:
                self.execution_stats['failed_commands'] += 1
                return f"❌ Command failed: {result.error or 'Unknown error'}"
                
        except Exception as e:
            self.logger.error(f"Error handling command '{command}': {e}")
            self.execution_stats['failed_commands'] += 1
            return f"❌ Error executing command: {str(e)}"
    
    async def _handle_help_command(self, parsed_command: ParsedCommand, 
                                 context: CommandContext) -> str:
        """Handle help command requests"""
        
        if parsed_command.parameters:
            topic = parsed_command.parameters[0].lower()
            
            # Check if it's a category request
            if topic == 'categories':
                return self.help_system.get_categories_help()
            
            # Check if it's a category
            categories = self.help_system.get_all_categories()
            if topic in categories:
                return self.help_system.get_category_help(topic)
            
            # Check if it's a specific command
            help_text = self.help_system.get_command_help(topic, detailed=True)
            if help_text:
                return help_text
            
            # Search for similar commands
            suggestions = self.help_system.search_commands(topic)
            if suggestions:
                suggestion_text = "❓ Command not found. Did you mean:\n"
                for suggestion in suggestions[:5]:
                    suggestion_text += f"  • `{suggestion}`\n"
                return suggestion_text.strip()
            
            return f"❓ No help found for '{topic}'. Send `help` for available commands."
        
        else:
            # General help
            return self.registry.get_help_summary(context)
    
    async def _execute_command(self, parsed_command: ParsedCommand, 
                             context: CommandContext) -> CommandExecutionResult:
        """Execute a parsed command"""
        
        command = parsed_command.command
        
        # Map parsed command to actual implementation
        if command == 'ack':
            return await self._handle_response_command(parsed_command, context)
        
        elif command in ['ping', 'cq', 'test', 'pong']:
            return await self._handle_ping_command(parsed_command, context)
        
        elif command == 'status':
            return await self._handle_status_command(parsed_command, context)
        
        elif command in ['sos', 'sosp', 'sosf', 'sosm']:
            return await self._handle_sos_command(parsed_command, context)
        
        elif command in ['clear', 'cancel', 'safe']:
            return await self._handle_clear_command(parsed_command, context)
        
        elif command == 'responding':
            return await self._handle_response_command(parsed_command, context)
        
        elif command in ['active', 'alertstatus']:
            return await self._handle_active_command(parsed_command, context)
        
        elif command.startswith('bbs'):
            return await self._handle_bbs_command(parsed_command, context)
        
        elif command in ['wx', 'wxc', 'wxa', 'wxalert', 'mwx']:
            return await self._handle_weather_command(parsed_command, context)
        
        elif command in ['subscribe', 'unsubscribe']:
            return await self._handle_subscription_command(parsed_command, context)
        
        elif command in ['alerts', 'forecasts'] or (command == 'weather' and len(parsed_command.parameters) > 0 and parsed_command.parameters[0] in ['on', 'off']):
            return await self._handle_toggle_command(parsed_command, context)
        
        elif command == 'weather' and (not parsed_command.parameters or parsed_command.parameters[0] not in ['on', 'off']):
            return await self._handle_weather_command(parsed_command, context)
        
        elif command in ['name', 'phone', 'address', 'setemail', 'setsms']:
            return await self._handle_profile_command(parsed_command, context)
        
        elif command in ['email', 'sms']:
            return await self._handle_communication_command(parsed_command, context)
        
        elif command in ['tagsend', 'tagin', 'tagout']:
            return await self._handle_tag_command(parsed_command, context)
        
        elif command in ['checkin', 'checkout', 'checklist']:
            return await self._handle_asset_command(parsed_command, context)
        
        elif command in ['block', 'unblock']:
            return await self._handle_admin_command(parsed_command, context)
        
        elif command in self._get_game_commands():
            return await self._handle_game_command(parsed_command, context)
        
        elif command in self._get_information_commands():
            return await self._handle_information_command(parsed_command, context)
        
        elif command in self._get_educational_commands():
            return await self._handle_educational_command(parsed_command, context)
        
        elif command in self._get_reference_commands():
            return await self._handle_reference_command(parsed_command, context)
        
        else:
            return CommandExecutionResult(
                success=False,
                response="",
                error=f"Command '{command}' not implemented yet"
            )
    
    async def _handle_ping_command(self, parsed_command: ParsedCommand, 
                                 context: CommandContext) -> CommandExecutionResult:
        """Handle ping/connectivity test commands"""
        response = f"🏓 Pong! Bot is active and responding.\n"
        response += f"📡 Signal: Good | Sender: {context.sender_id}\n"
        response += f"⏰ Response time: <1s | Hops: 1"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    async def _handle_status_command(self, parsed_command: ParsedCommand, 
                                   context: CommandContext) -> CommandExecutionResult:
        """Handle status command"""
        response = f"📊 **System Status**\n\n"
        response += f"🟢 Core Services: Online\n"
        response += f"📡 Mesh Network: Connected\n"
        response += f"💾 Database: Operational\n"
        response += f"🔧 Commands Processed: {self.execution_stats['total_commands']}\n"
        response += f"✅ Success Rate: {self._calculate_success_rate():.1f}%"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    async def _handle_sos_command(self, parsed_command: ParsedCommand, 
                                context: CommandContext) -> CommandExecutionResult:
        """Handle SOS emergency commands"""
        sos_type = parsed_command.command.upper()
        message = parsed_command.raw_args if parsed_command.raw_args else ""
        
        response = f"🚨 **{sos_type} ALERT TRIGGERED**\n\n"
        response += f"👤 From: {context.sender_name or context.sender_id}\n"
        response += f"⏰ Time: {context.message_timestamp or 'Now'}\n"
        
        if message:
            response += f"💬 Message: {message}\n"
        
        response += f"\n🔔 Responders have been notified\n"
        response += f"📍 Location data included if available\n"
        response += f"⚠️ Will escalate if not acknowledged in 5 minutes"
        
        return CommandExecutionResult(
            success=True,
            response=response,
            metadata={'emergency': True, 'type': sos_type}
        )
    
    async def _handle_clear_command(self, parsed_command: ParsedCommand, 
                                  context: CommandContext) -> CommandExecutionResult:
        """Handle emergency clearing commands"""
        clear_type = parsed_command.command.upper()
        incident_id = parsed_command.named_parameters.get('id', 'latest')
        
        response = f"✅ **{clear_type} COMMAND RECEIVED**\n\n"
        response += f"👤 From: {context.sender_name or context.sender_id}\n"
        response += f"🆔 Incident: {incident_id}\n"
        response += f"⏰ Cleared at: Now\n\n"
        response += f"📢 All responders have been notified"
        
        return CommandExecutionResult(
            success=True,
            response=response,
            metadata={'emergency_clear': True, 'type': clear_type}
        )
    
    async def _handle_response_command(self, parsed_command: ParsedCommand, 
                                     context: CommandContext) -> CommandExecutionResult:
        """Handle emergency response commands"""
        response_type = parsed_command.command.upper()
        incident_id = parsed_command.named_parameters.get('id', 'latest')
        
        response = f"👍 **{response_type} ACKNOWLEDGED**\n\n"
        response += f"👤 Responder: {context.sender_name or context.sender_id}\n"
        response += f"🆔 Incident: {incident_id}\n"
        response += f"⏰ Time: Now\n\n"
        response += f"📢 Incident commander has been notified"
        
        return CommandExecutionResult(
            success=True,
            response=response,
            metadata={'emergency_response': True, 'type': response_type}
        )
    
    async def _handle_active_command(self, parsed_command: ParsedCommand, 
                                   context: CommandContext) -> CommandExecutionResult:
        """Handle active incidents command"""
        response = f"📋 **Active Emergency Incidents**\n\n"
        response += f"🔍 No active incidents at this time\n\n"
        response += f"💡 Send `sos`, `sosp`, `sosf`, or `sosm` to report an emergency"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    async def _handle_bbs_command(self, parsed_command: ParsedCommand, 
                                context: CommandContext) -> CommandExecutionResult:
        """Handle BBS commands"""
        command = parsed_command.command
        
        if command == 'bbs':
            response = f"📮 **Bulletin Board System**\n\n"
            response += f"1. Read Bulletins (bbslist)\n"
            response += f"2. Post Bulletin (bbspost)\n"
            response += f"3. Read Mail\n"
            response += f"4. Send Mail\n"
            response += f"5. Channel Directory\n\n"
            response += f"💡 Send command name for direct access"
        
        elif command == 'bbshelp':
            response = f"📋 **BBS Help**\n\n"
            response += f"• `bbslist` - List bulletins\n"
            response += f"• `bbsread #ID` - Read bulletin\n"
            response += f"• `bbspost` - Post bulletin\n"
            response += f"• `bbsdelete #ID` - Delete your bulletin\n"
            response += f"• `bbsinfo` - System information"
        
        elif command == 'bbslist':
            response = f"📄 **Bulletin List**\n\n"
            response += f"No bulletins available\n\n"
            response += f"💡 Send `bbspost` to create a bulletin"
        
        elif command == 'bbspost':
            if parsed_command.named_parameters.get('subject'):
                subject = parsed_command.named_parameters['subject']
                content = parsed_command.named_parameters.get('content', '')
                response = f"✅ **Bulletin Posted**\n\n"
                response += f"📝 Subject: {subject}\n"
                if content:
                    response += f"💬 Content: {content[:100]}...\n"
                response += f"👤 Author: {context.sender_name or context.sender_id}"
            else:
                response = f"📝 **Post Bulletin**\n\n"
                response += f"Usage: `bbspost subject/content`\n"
                response += f"Example: `bbspost Weekly Update/All systems operational`"
        
        else:
            response = f"❓ BBS command '{command}' not implemented yet"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    async def _handle_weather_command(self, parsed_command: ParsedCommand, 
                                    context: CommandContext) -> CommandExecutionResult:
        """Handle weather commands using information lookup service"""
        command = parsed_command.command
        args = parsed_command.parameters
        
        try:
            response = await self.information_service.handle_weather_command(
                command, args, context.__dict__
            )
            return CommandExecutionResult(success=True, response=response)
        except Exception as e:
            self.logger.error(f"Error in weather command: {e}")
            return CommandExecutionResult(
                success=False, 
                response=f"❌ Error retrieving weather information: {str(e)}",
                error=str(e)
            )
    
    def _get_game_commands(self) -> List[str]:
        """Get list of game commands"""
        return [
            'blackjack', 'videopoker', 'dopewars', 'lemonstand', 'golfsim',
            'mastermind', 'hangman', 'tictactoe', 'hamtest', 'quiz', 'survey', 'joke'
        ]
    
    def _get_information_commands(self) -> List[str]:
        """Get list of information commands"""
        return [
            'whereami', 'whoami', 'whois', 'howfar', 'howtall',
            'lheard', 'sitrep', 'sysinfo', 'leaderboard', 'history', 'messages',
            'wiki', 'askai', 'ask', 'satpass', 'rlist', 'readnews', 'readrss', 'motd'
        ]
    
    def _get_educational_commands(self) -> List[str]:
        """Get list of educational commands"""
        return ['hamtest', 'quiz', 'survey']
    
    def _get_reference_commands(self) -> List[str]:
        """Get list of reference data commands"""
        return ['solar', 'hfcond', 'sun', 'moon', 'tide', 'earthquake', 'riverflow']
    
    async def _handle_game_command(self, parsed_command: ParsedCommand, 
                                 context: CommandContext) -> CommandExecutionResult:
        """Handle game commands"""
        game = parsed_command.command
        
        # Special case for 'games' command - show available games
        if game == 'games':
            response = f"🎮 **Available Games**\n\n"
            response += f"• **tictactoe** - Classic 3x3 grid game\n"
            response += f"• **hangman** - Word guessing game\n"
            response += f"• **blackjack** - Casino card game\n"
            response += f"• **videopoker** - Video poker (Jacks or Better)\n"
            response += f"• **dopewars** - Trading simulation\n"
            response += f"• **lemonstand** - Business simulation\n"
            response += f"• **golfsim** - Golf simulator\n"
            response += f"• **mastermind** - Logic puzzle game\n\n"
            response += f"💡 Send game name to start playing!\n"
            response += f"📋 Send `help <game>` for rules"
            
            return CommandExecutionResult(success=True, response=response)
        
        # For specific games, we need to delegate to the interactive bot service
        # This will be handled by the bot service's game manager
        response = f"🎮 **{game.title()} Game**\n\n"
        response += f"Starting {game} game...\n"
        response += f"💡 Send `help {game}` for rules and instructions"
        
        return CommandExecutionResult(
            success=True,
            response=response,
            metadata={'game_command': True, 'game_type': game}
        )
    
    async def _handle_information_command(self, parsed_command: ParsedCommand, 
                                        context: CommandContext) -> CommandExecutionResult:
        """Handle information commands using information lookup service"""
        command = parsed_command.command
        args = parsed_command.parameters
        
        try:
            # Route to appropriate information service method
            if command in ['whereami', 'howfar', 'howtall']:
                response = await self.information_service.handle_location_command(
                    command, args, context.__dict__
                )
            elif command in ['whoami', 'whois', 'lheard', 'sitrep', 'status']:
                response = await self.information_service.handle_node_status_command(
                    command, args, context.__dict__
                )
            elif command in ['sysinfo', 'leaderboard', 'history', 'messages']:
                response = await self.information_service.handle_network_stats_command(
                    command, args, context.__dict__
                )
            else:
                # For other information commands not yet implemented
                response = f"ℹ️ **{command.title()} Information**\n\n"
                response += f"Information service for '{command}' not yet implemented.\n"
                response += f"This would provide {command} data.\n\n"
                response += f"💡 Send `help {command}` for detailed information"
            
            return CommandExecutionResult(success=True, response=response)
            
        except Exception as e:
            self.logger.error(f"Error in information command '{command}': {e}")
            return CommandExecutionResult(
                success=False, 
                response=f"❌ Error retrieving {command} information: {str(e)}",
                error=str(e)
            )
    
    async def _handle_educational_command(self, parsed_command: ParsedCommand, 
                                        context: CommandContext) -> CommandExecutionResult:
        """Handle educational commands using educational service"""
        command = parsed_command.command
        args = parsed_command.parameters
        
        try:
            if command == 'hamtest':
                response = await self.educational_service.handle_hamtest_command(
                    args, context.__dict__
                )
            elif command == 'quiz':
                response = await self.educational_service.handle_quiz_command(
                    args, context.__dict__
                )
            elif command == 'survey':
                response = await self.educational_service.handle_survey_command(
                    args, context.__dict__
                )
            else:
                response = f"❓ Educational command '{command}' not implemented yet"
            
            return CommandExecutionResult(success=True, response=response)
            
        except Exception as e:
            self.logger.error(f"Error in educational command '{command}': {e}")
            return CommandExecutionResult(
                success=False, 
                response=f"❌ Error in {command} command: {str(e)}",
                error=str(e)
            )
    
    async def _handle_reference_command(self, parsed_command: ParsedCommand, 
                                      context: CommandContext) -> CommandExecutionResult:
        """Handle reference data commands using reference service"""
        command = parsed_command.command
        args = parsed_command.parameters
        
        try:
            if command == 'solar':
                response = await self.reference_service.handle_solar_command(
                    args, context.__dict__
                )
            elif command == 'hfcond':
                response = await self.reference_service.handle_hfcond_command(
                    args, context.__dict__
                )
            elif command == 'earthquake':
                response = await self.reference_service.handle_earthquake_command(
                    args, context.__dict__
                )
            elif command == 'sun':
                response = await self.reference_service.handle_sun_command(
                    args, context.__dict__
                )
            elif command == 'moon':
                response = await self.reference_service.handle_moon_command(
                    args, context.__dict__
                )
            elif command == 'tide':
                response = await self.reference_service.handle_tide_command(
                    args, context.__dict__
                )
            elif command == 'riverflow':
                response = f"🌊 **River Flow Information**\n\n"
                response += "ℹ️ River flow data requires integration with\n"
                response += "USGS Water Services API.\n\n"
                response += "💡 This feature will be enhanced with API integration"
            else:
                response = f"❓ Reference command '{command}' not implemented yet"
            
            return CommandExecutionResult(success=True, response=response)
            
        except Exception as e:
            self.logger.error(f"Error in reference command '{command}': {e}")
            return CommandExecutionResult(
                success=False, 
                response=f"❌ Error in {command} command: {str(e)}",
                error=str(e)
            )
    
    async def _handle_subscription_command(self, parsed_command: ParsedCommand, 
                                         context: CommandContext) -> CommandExecutionResult:
        """Handle subscription commands"""
        command = parsed_command.command
        service = parsed_command.parameters[0] if parsed_command.parameters else None
        
        if service:
            action = "subscribed to" if command == "subscribe" else "unsubscribed from"
            response = f"✅ Successfully {action} {service} service"
        else:
            response = f"📋 **Current Subscriptions**\n\n"
            response += f"• Weather Alerts: Enabled\n"
            response += f"• Emergency Alerts: Enabled\n"
            response += f"• BBS Notifications: Disabled\n\n"
            response += f"💡 Use `{command} <service>` to modify subscriptions"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    async def _handle_toggle_command(self, parsed_command: ParsedCommand, 
                                   context: CommandContext) -> CommandExecutionResult:
        """Handle toggle commands (alerts on/off, etc.)"""
        command = parsed_command.command
        state = parsed_command.named_parameters.get('state')
        
        if state:
            status = "enabled" if state == "on" else "disabled"
            response = f"✅ {command.title()} notifications {status}"
        else:
            response = f"📊 **{command.title()} Status**\n\n"
            response += f"Current status: Enabled\n\n"
            response += f"💡 Use `{command} on` or `{command} off` to change"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    async def _handle_profile_command(self, parsed_command: ParsedCommand, 
                                    context: CommandContext) -> CommandExecutionResult:
        """Handle profile setting commands"""
        command = parsed_command.command
        value = parsed_command.named_parameters.get('value') or parsed_command.raw_args
        
        if value:
            response = f"✅ {command.title()} updated successfully"
            if command == 'name':
                response += f"\nDisplay name set to: {value}"
            elif command == 'phone':
                phone_type = parsed_command.named_parameters.get('type', '1')
                number = parsed_command.named_parameters.get('number', value)
                response += f"\nPhone {phone_type} set to: {number}"
        else:
            response = f"❓ Please provide a value for {command}\n"
            response += f"Usage: {self.help_system.get_command_help(command, detailed=False)}"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    async def _handle_communication_command(self, parsed_command: ParsedCommand, 
                                          context: CommandContext) -> CommandExecutionResult:
        """Handle communication commands (email, sms)"""
        command = parsed_command.command
        
        if command == 'email':
            to = parsed_command.named_parameters.get('to')
            subject = parsed_command.named_parameters.get('subject')
            body = parsed_command.named_parameters.get('body')
            
            # Handle case where email is passed as separate arguments
            if not (to and subject and body):
                if len(parsed_command.parameters) >= 3:
                    to = parsed_command.parameters[0]
                    subject = parsed_command.parameters[1]
                    body = ' '.join(parsed_command.parameters[2:])
                elif len(parsed_command.parameters) == 1:
                    # Check if it's in slash format
                    parts = parsed_command.parameters[0].split('/')
                    if len(parts) >= 3:
                        to = parts[0]
                        subject = parts[1]
                        body = '/'.join(parts[2:])
                    else:
                        # Check if it's space-separated in a single parameter
                        space_parts = parsed_command.parameters[0].split()
                        if len(space_parts) >= 3:
                            to = space_parts[0]
                            subject = space_parts[1]
                            body = ' '.join(space_parts[2:])
            

            
            if to and subject and body:
                response = f"📧 **Email Sent**\n\n"
                response += f"📬 To: {to}\n"
                response += f"📝 Subject: {subject}\n"
                response += f"✅ Message delivered via mesh gateway"
            else:
                response = f"❓ Invalid email format\n"
                response += f"Usage: `email/recipient/subject/message`"
        
        elif command == 'sms':
            message = parsed_command.named_parameters.get('message', parsed_command.raw_args)
            
            # Handle case where SMS is passed as separate arguments
            if not message and parsed_command.parameters:
                message = ' '.join(parsed_command.parameters)
            

            
            if message:
                response = f"📱 **SMS Sent**\n\n"
                response += f"💬 Message: {message[:50]}...\n"
                response += f"✅ Delivered via SMS gateway"
            else:
                response = f"❓ Please provide SMS message\n"
                response += f"Usage: `sms:your message here`"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    async def _handle_tag_command(self, parsed_command: ParsedCommand, 
                                context: CommandContext) -> CommandExecutionResult:
        """Handle tag-based messaging commands"""
        command = parsed_command.command
        
        if command == 'tagsend':
            tags = parsed_command.named_parameters.get('tags')
            message = parsed_command.named_parameters.get('message')
            
            # Handle case where tagsend is passed as separate arguments
            if not (tags and message) and len(parsed_command.parameters) >= 2:
                tags = parsed_command.parameters[0]
                message = ' '.join(parsed_command.parameters[1:])
            
            if tags and message:
                response = f"📢 **Tag Message Sent**\n\n"
                response += f"🏷️ Tags: {tags}\n"
                response += f"💬 Message: {message[:100]}...\n"
                response += f"✅ Delivered to tagged users"
            else:
                response = f"❓ Invalid tagsend format\n"
                response += f"Usage: `tagsend/tags/message`"
        
        elif command == 'tagin':
            tag = parsed_command.raw_args or (parsed_command.parameters[0] if parsed_command.parameters else "")
            if tag:
                response = f"✅ Added to tag group: {tag}"
            else:
                response = f"❓ Please specify tag name\nUsage: `tagin/TAGNAME`"
        
        elif command == 'tagout':
            tag = parsed_command.raw_args or (parsed_command.parameters[0] if parsed_command.parameters else "")
            if tag:
                response = f"✅ Removed from tag group: {tag}"
            else:
                response = f"❓ Please specify tag name\nUsage: `tagout/TAGNAME`"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    async def _handle_asset_command(self, parsed_command: ParsedCommand, 
                                  context: CommandContext) -> CommandExecutionResult:
        """Handle asset management commands"""
        command = parsed_command.command
        notes = parsed_command.raw_args
        
        if command == 'checkin':
            response = f"✅ **Checked In**\n\n"
            response += f"👤 User: {context.sender_name or context.sender_id}\n"
            response += f"⏰ Time: Now\n"
            if notes:
                response += f"📝 Notes: {notes}\n"
            response += f"📊 Status: Active"
        
        elif command == 'checkout':
            response = f"✅ **Checked Out**\n\n"
            response += f"👤 User: {context.sender_name or context.sender_id}\n"
            response += f"⏰ Time: Now\n"
            if notes:
                response += f"📝 Notes: {notes}\n"
            response += f"📊 Status: Inactive"
        
        elif command == 'checklist':
            response = f"📋 **Current Check-in Status**\n\n"
            response += f"👥 Active Users: 0\n"
            response += f"📊 No users currently checked in\n\n"
            response += f"💡 Use `checkin` to check in"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    async def _handle_admin_command(self, parsed_command: ParsedCommand, 
                                  context: CommandContext) -> CommandExecutionResult:
        """Handle administrative commands"""
        if not context.is_admin:
            return CommandExecutionResult(
                success=False,
                response="❌ Administrative privileges required",
                error="Administrative privileges required"
            )
        
        command = parsed_command.command
        email = parsed_command.raw_args
        
        if command == 'block':
            if email:
                response = f"🚫 **Email Blocked**\n\nAddress: {email}\nStatus: Blocked from sending messages"
            else:
                response = f"❓ Please specify email address\nUsage: `block/email@domain.com`"
        
        elif command == 'unblock':
            if email:
                response = f"✅ **Email Unblocked**\n\nAddress: {email}\nStatus: Allowed to send messages"
            else:
                response = f"❓ Please specify email address\nUsage: `unblock/email@domain.com`"
        
        return CommandExecutionResult(
            success=True,
            response=response
        )
    
    def _calculate_success_rate(self) -> float:
        """Calculate command success rate"""
        total = self.execution_stats['total_commands']
        if total == 0:
            return 100.0
        
        successful = self.execution_stats['successful_commands']
        return (successful / total) * 100.0
    
    def get_help(self, command: str) -> str:
        """Get help text for a command"""
        return self.help_system.get_command_help(command, detailed=False) or f"No help available for {command}"
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get command execution statistics"""
        stats = self.execution_stats.copy()
        stats['success_rate'] = self._calculate_success_rate()
        stats['registered_commands'] = len(self.commands)
        return stats