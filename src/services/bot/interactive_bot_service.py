"""
Interactive Bot Service

Main service that provides intelligent auto-response, command handling, and interactive features:
- Intelligent auto-response with keyword detection
- Comprehensive command handling system
- Interactive games and educational features
- AI integration for aircraft message responses
- Message processing and routing for bot commands
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable, Any, Set
from dataclasses import dataclass, field

from src.models.message import Message, MessageType, MessagePriority
from src.core.database import get_database
from src.core.plugin_interfaces import (
    MessageHandler, CommandHandler, BaseMessageHandler, BaseCommandHandler,
    PluginCommunicationInterface, PluginMessage, PluginMessageType
)


@dataclass
class AutoResponseRule:
    """Configuration for auto-response rules"""
    keywords: List[str]
    response: str
    priority: int = 100
    channel_specific: bool = False
    direct_message_only: bool = False
    emergency: bool = False
    enabled: bool = True
    conditions: Dict[str, Any] = field(default_factory=dict)
    match_type: str = "contains"  # "contains", "exact", "starts_with", "ends_with", "regex"
    case_sensitive: bool = False
    cooldown_seconds: int = 0  # Cooldown between responses to same user
    max_responses_per_hour: int = 0  # Rate limiting (0 = unlimited)
    channels: List[int] = field(default_factory=list)  # Specific channels (empty = all)
    exclude_channels: List[int] = field(default_factory=list)  # Excluded channels
    time_restrictions: Dict[str, Any] = field(default_factory=dict)  # Time-based restrictions
    escalation_delay: int = 300  # Seconds before escalating emergency (5 minutes default)


@dataclass
class ResponseTracker:
    """Track responses for rate limiting and cooldowns"""
    user_id: str
    rule_keywords: List[str]
    last_response: datetime
    response_count: int = 1
    escalated: bool = False


@dataclass
class CommandInfo:
    """Information about a registered command"""
    name: str
    handler: CommandHandler
    plugin_name: str
    help_text: str
    permissions: List[str] = field(default_factory=list)
    enabled: bool = True


class InteractiveBotService:
    """
    Main interactive bot service that provides auto-response and command handling
    """
    
    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Core components
        self.communication: Optional[PluginCommunicationInterface] = None
        
        # Auto-response system
        self.auto_response_rules: List[AutoResponseRule] = []
        self.emergency_keywords: Set[str] = set()
        self.greeting_enabled = True
        self.new_node_greetings: Dict[str, datetime] = {}
        self.response_tracker: Dict[str, List[ResponseTracker]] = {}  # user_id -> list of trackers
        self.known_nodes: Set[str] = set()  # Track known nodes for greeting
        self.emergency_escalation_tasks: Dict[str, asyncio.Task] = {}  # Track escalation tasks
        
        # Command system - use comprehensive command handler
        from .comprehensive_command_handler import ComprehensiveCommandHandler
        self.comprehensive_handler = ComprehensiveCommandHandler(self.config)
        self.command_handlers: Dict[str, CommandInfo] = {}
        self.command_aliases: Dict[str, str] = {}
        self.help_categories: Dict[str, List[str]] = {}
        
        # Games framework
        from .games.base_game import GameManager
        self.game_manager = GameManager()
        self._initialize_games()
        
        # Message handlers
        self.message_handlers: List[MessageHandler] = []
        
        # AI integration
        self.ai_service = None
        self.ai_enabled = False
        self.aircraft_altitude_threshold = 1000  # meters
        
        # Service state
        self._running = False
        
        # Initialize default configuration
        self._initialize_default_config()
    
    def _initialize_default_config(self):
        """Initialize default configuration values"""
        default_config = {
            'auto_response': {
                'enabled': True,
                'emergency_keywords': ['help', 'emergency', 'urgent', 'mayday', 'sos', 'distress'],
                'greeting_enabled': True,
                'greeting_message': 'Welcome to the mesh network! Send "help" for available commands.',
                'greeting_delay_hours': 24,  # Don't greet same node again for 24 hours
                'aircraft_responses': True,
                'emergency_escalation_delay': 300,  # 5 minutes
                'emergency_escalation_message': 'EMERGENCY ALERT: Unacknowledged emergency keyword detected from {sender}. Original message: {message}',
                'response_rate_limit': 10,  # Max responses per hour per user
                'cooldown_seconds': 30  # Default cooldown between responses
            },
            'commands': {
                'enabled': True,
                'help_enabled': True,
                'permissions_enabled': False
            },
            'ai': {
                'enabled': False,
                'aircraft_detection': True,
                'altitude_threshold': 1000,
                'service_url': None,
                'api_key': None
            },
            'monitoring': {
                'new_node_detection': True,
                'node_activity_tracking': True,
                'response_analytics': True
            },
            'message_history': {
                'history_retention_days': 30,
                'max_offline_messages': 50,
                'offline_message_ttl_hours': 72,
                'max_message_chunk_size': 200,
                'store_forward_enabled': True,
                'chunk_responses': True,
                'offline_check_interval': 300,
                'cleanup_interval': 3600,
                'max_history_results': 100,
                'enable_message_search': True,
                'enable_replay_system': True
            }
        }
        
        # Merge with provided config
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
            elif isinstance(value, dict):
                for subkey, subvalue in value.items():
                    if subkey not in self.config[key]:
                        self.config[key][subkey] = subvalue
    
    async def start(self):
        """Start the interactive bot service"""
        if self._running:
            return
        
        self._running = True
        
        # Initialize auto-response rules
        await self._initialize_auto_response_rules()
        
        # Initialize default commands
        await self._initialize_default_commands()
        
        # Initialize educational service
        from .educational_service import EducationalService
        self.educational_service = EducationalService(self.config)
        # Initialize the educational database
        self.educational_service._initialize_database()
        
        # Initialize message history service
        from .message_history_service import MessageHistoryService
        self.message_history_service = MessageHistoryService(self.config.get('message_history', {}))
        self.message_history_service.set_communication_interface(self.communication)
        await self.message_history_service.start()
        
        # Initialize AI service if configured
        await self._initialize_ai_service()
        
        # Start game manager cleanup task
        await self._start_game_manager()
        
        self.logger.info("Interactive Bot Service started")
    
    async def stop(self):
        """Stop the interactive bot service"""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel all pending escalation tasks
        for task in self.emergency_escalation_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete cancellation
        if self.emergency_escalation_tasks:
            await asyncio.gather(*self.emergency_escalation_tasks.values(), return_exceptions=True)
        
        self.emergency_escalation_tasks.clear()
        
        # Stop game manager
        if hasattr(self.game_manager, 'session_cleanup_task') and self.game_manager.session_cleanup_task:
            self.game_manager.session_cleanup_task.cancel()
        
        # Stop message history service
        if hasattr(self, 'message_history_service'):
            await self.message_history_service.stop()
        
        # Close AI service
        if self.ai_service:
            await self.ai_service.close()
        
        self.logger.info("Interactive Bot Service stopped")
    
    def _is_admin_user(self, user_id: str) -> bool:
        """Check if user has admin privileges"""
        # TODO: Implement proper admin checking from database/config
        admin_users = self.config.get('admin_users', [])
        return user_id in admin_users
    
    def _is_moderator_user(self, user_id: str) -> bool:
        """Check if user has moderator privileges"""
        # TODO: Implement proper moderator checking from database/config
        moderator_users = self.config.get('moderator_users', [])
        return user_id in moderator_users or self._is_admin_user(user_id)
    
    def _get_user_permissions(self, user_id: str) -> set:
        """Get user permissions"""
        permissions = set()
        
        if self._is_admin_user(user_id):
            permissions.add('admin')
        
        if self._is_moderator_user(user_id):
            permissions.add('moderator')
        
        # TODO: Add more granular permissions from database
        permissions.add('user')
        
        return permissions
    
    def set_communication_interface(self, communication: PluginCommunicationInterface):
        """Set the communication interface for plugin communication"""
        self.communication = communication
        # Also set it for the comprehensive handler's information service
        self.comprehensive_handler.set_communication_interface(communication)
        # Set it for the message history service if it exists
        if hasattr(self, 'message_history_service'):
            self.message_history_service.set_communication_interface(communication)
    
    async def handle_message(self, message: Message) -> Optional[Message]:
        """
        Handle incoming message for bot processing
        
        Args:
            message: The incoming message to process
            
        Returns:
            Response message if applicable, None otherwise
        """
        if not self._running:
            return None
        
        content = message.content.strip()
        sender_id = message.sender_id
        is_direct_message = message.recipient_id is not None
        
        try:
            # Process message through message history service first
            if hasattr(self, 'message_history_service'):
                history_response = await self.message_history_service.handle_message(message)
                if history_response:
                    return history_response
            
            # Check for new node greeting
            if self.greeting_enabled and sender_id not in self.new_node_greetings:
                await self._handle_new_node_greeting(sender_id, message)
            
            # Check for auto-response triggers first (higher priority)
            auto_response = await self._check_auto_response(content, sender_id, is_direct_message, message)
            if auto_response:
                return self._create_response_message(auto_response, message)
            
            # Check for active educational session first
            if self.educational_service and sender_id in self.educational_service.active_sessions:
                session = self.educational_service.active_sessions[sender_id]
                context = {
                    'sender_id': sender_id,
                    'sender_name': getattr(message, 'sender_name', sender_id),
                    'channel': getattr(message, 'channel', 0),
                    'is_direct_message': message.recipient_id is not None,
                    'message_timestamp': getattr(message, 'timestamp', None),
                    'interface_id': getattr(message, 'interface_id', ''),
                    'message': message
                }
                
                # Handle educational session input
                if session.session_type == 'hamtest':
                    response = await self.educational_service._handle_hamtest_answer(
                        content.split(), session, context
                    )
                    return self._create_response_message(response, message)
                elif session.session_type == 'quiz':
                    response = await self.educational_service._handle_quiz_answer(
                        content.split(), session, context
                    )
                    return self._create_response_message(response, message)
                elif session.session_type == 'survey':
                    response = await self.educational_service._handle_survey_answer(
                        content.split(), session, context
                    )
                    return self._create_response_message(response, message)
            
            # Check for active game input, but allow game commands to override
            if self.game_manager.has_active_game(sender_id):
                # Check if this is a new game command (should override current game)
                if content.lower() in self.game_manager.games:
                    command_response = await self._handle_command(content, sender_id, message)
                    if command_response:
                        return self._create_response_message(command_response, message)
                else:
                    # Process as game input
                    game_response = await self.game_manager.process_game_input(sender_id, content)
                    if game_response:
                        return self._create_response_message(game_response, message)
            
            # Check for commands (single words or starting with / or !)
            if content.startswith(('/', '!')) or (len(content.split()) == 1 and content.isalpha()):
                command_response = await self._handle_command(content, sender_id, message)
                if command_response:
                    return self._create_response_message(command_response, message)
            
            # Check for AI response (aircraft detection)
            if self.ai_enabled and self.config['ai']['aircraft_detection']:
                ai_response = await self._check_ai_response(message)
                if ai_response:
                    return self._create_response_message(ai_response, message)
            
        except Exception as e:
            self.logger.error(f"Error handling message in bot service: {e}")
            return None
        
        return None
    
    async def register_command_handler(self, handler: CommandHandler, plugin_name: str):
        """
        Register a command handler
        
        Args:
            handler: The command handler to register
            plugin_name: Name of the plugin registering the handler
        """
        for command in handler.get_commands():
            command_info = CommandInfo(
                name=command,
                handler=handler,
                plugin_name=plugin_name,
                help_text=handler.get_help(command)
            )
            
            self.command_handlers[command] = command_info
            self.logger.debug(f"Registered command '{command}' from plugin '{plugin_name}'")
    
    async def unregister_command_handler(self, handler: CommandHandler, plugin_name: str):
        """
        Unregister a command handler
        
        Args:
            handler: The command handler to unregister
            plugin_name: Name of the plugin unregistering the handler
        """
        commands_to_remove = []
        for command, info in self.command_handlers.items():
            if info.handler == handler and info.plugin_name == plugin_name:
                commands_to_remove.append(command)
        
        for command in commands_to_remove:
            del self.command_handlers[command]
            self.logger.debug(f"Unregistered command '{command}' from plugin '{plugin_name}'")
    
    async def register_message_handler(self, handler: MessageHandler, plugin_name: str):
        """
        Register a message handler
        
        Args:
            handler: The message handler to register
            plugin_name: Name of the plugin registering the handler
        """
        self.message_handlers.append(handler)
        self.logger.debug(f"Registered message handler from plugin '{plugin_name}'")
    
    async def unregister_message_handler(self, handler: MessageHandler, plugin_name: str):
        """
        Unregister a message handler
        
        Args:
            handler: The message handler to unregister
            plugin_name: Name of the plugin unregistering the handler
        """
        try:
            self.message_handlers.remove(handler)
            self.logger.debug(f"Unregistered message handler from plugin '{plugin_name}'")
        except ValueError:
            pass
    
    def add_auto_response_rule(self, rule: AutoResponseRule):
        """Add an auto-response rule"""
        self.auto_response_rules.append(rule)
        self.auto_response_rules.sort(key=lambda r: r.priority)
        
        if rule.emergency:
            self.emergency_keywords.update(rule.keywords)
        
        self.logger.info(f"Added auto-response rule with keywords: {rule.keywords}")
    
    def remove_auto_response_rule(self, keywords: List[str]):
        """Remove auto-response rules matching keywords"""
        removed_count = 0
        self.auto_response_rules = [
            rule for rule in self.auto_response_rules 
            if not any(kw in rule.keywords for kw in keywords) or (removed_count := removed_count + 1, False)[1]
        ]
        
        # Update emergency keywords
        self.emergency_keywords = set()
        for rule in self.auto_response_rules:
            if rule.emergency:
                self.emergency_keywords.update(rule.keywords)
        
        self.logger.info(f"Removed {removed_count} auto-response rules")
    
    def update_auto_response_rule(self, keywords: List[str], **updates):
        """Update existing auto-response rule"""
        for rule in self.auto_response_rules:
            if any(kw in rule.keywords for kw in keywords):
                for key, value in updates.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                
                # Re-sort if priority changed
                if 'priority' in updates:
                    self.auto_response_rules.sort(key=lambda r: r.priority)
                
                # Update emergency keywords if needed
                if 'emergency' in updates or 'keywords' in updates:
                    self.emergency_keywords = set()
                    for r in self.auto_response_rules:
                        if r.emergency:
                            self.emergency_keywords.update(r.keywords)
                
                self.logger.info(f"Updated auto-response rule with keywords: {keywords}")
                return True
        
        return False
    
    def get_auto_response_rules(self) -> List[AutoResponseRule]:
        """Get all auto-response rules"""
        return self.auto_response_rules.copy()
    
    def get_response_statistics(self) -> Dict[str, Any]:
        """Get response statistics for monitoring"""
        stats = {
            'total_rules': len(self.auto_response_rules),
            'emergency_rules': len([r for r in self.auto_response_rules if r.emergency]),
            'active_rules': len([r for r in self.auto_response_rules if r.enabled]),
            'known_nodes': len(self.known_nodes),
            'greeted_nodes': len(self.new_node_greetings),
            'active_escalations': len(self.emergency_escalation_tasks),
            'tracked_users': len(self.response_tracker)
        }
        
        # Response counts by rule
        rule_stats = {}
        for user_trackers in self.response_tracker.values():
            for tracker in user_trackers:
                rule_key = ','.join(sorted(tracker.rule_keywords))
                if rule_key not in rule_stats:
                    rule_stats[rule_key] = 0
                rule_stats[rule_key] += tracker.response_count
        
        stats['responses_by_rule'] = rule_stats
        return stats
    
    async def _initialize_auto_response_rules(self):
        """Initialize default auto-response rules"""
        if not self.config['auto_response']['enabled']:
            return
        
        # Load known nodes from database
        await self._load_known_nodes()
        
        # Emergency keywords with escalation
        emergency_keywords = self.config['auto_response']['emergency_keywords']
        if emergency_keywords:
            emergency_rule = AutoResponseRule(
                keywords=emergency_keywords,
                response="🚨 Emergency keywords detected. Alerting responders and escalating if no response...",
                priority=1,
                emergency=True,
                escalation_delay=self.config['auto_response']['emergency_escalation_delay'],
                cooldown_seconds=60,  # 1 minute cooldown for emergency responses
                max_responses_per_hour=5  # Limit emergency responses
            )
            self.add_auto_response_rule(emergency_rule)
        
        # Basic help response
        help_rule = AutoResponseRule(
            keywords=['help', '?', 'commands'],
            response="📋 Available commands: help, ping, status, weather, games, bbs. Send 'help <command>' for details.",
            priority=50,
            cooldown_seconds=self.config['auto_response'].get('cooldown_seconds', 30),
            max_responses_per_hour=self.config['auto_response'].get('response_rate_limit', 10)
        )
        self.add_auto_response_rule(help_rule)
        
        # Ping/connectivity test responses
        ping_rule = AutoResponseRule(
            keywords=['ping', 'test', 'cq'],
            response="🏓 Pong! Bot is active and responding. Signal quality: Good",
            priority=10,
            cooldown_seconds=self.config['auto_response'].get('cooldown_seconds', 30),
            max_responses_per_hour=self.config['auto_response'].get('response_rate_limit', 20)
        )
        self.add_auto_response_rule(ping_rule)
        
        # Network status keywords
        status_rule = AutoResponseRule(
            keywords=['status', 'sitrep', 'network'],
            response="📊 Network Status: Active nodes detected. Send 'status' command for detailed information.",
            priority=30,
            cooldown_seconds=60,
            max_responses_per_hour=5
        )
        self.add_auto_response_rule(status_rule)
        
        # Weather keywords
        weather_rule = AutoResponseRule(
            keywords=['weather', 'wx', 'forecast'],
            response="🌤️ Weather service available. Send 'wx' for current conditions or 'forecast' for extended forecast.",
            priority=40,
            cooldown_seconds=120,
            max_responses_per_hour=3
        )
        self.add_auto_response_rule(weather_rule)
        
        # BBS keywords
        bbs_rule = AutoResponseRule(
            keywords=['bbs', 'bulletin', 'mail', 'messages'],
            response="📮 BBS system available. Send 'bbs' to access bulletin board, mail, and directory services.",
            priority=45,
            cooldown_seconds=60,
            max_responses_per_hour=5
        )
        self.add_auto_response_rule(bbs_rule)
        
        # Gaming keywords
        games_rule = AutoResponseRule(
            keywords=['games', 'play', 'fun'],
            response="🎮 Games available: blackjack, hangman, tictactoe, quiz. Send game name to start playing!",
            priority=60,
            cooldown_seconds=120,
            max_responses_per_hour=3
        )
        self.add_auto_response_rule(games_rule)
        
        # Greeting for specific phrases
        greeting_rule = AutoResponseRule(
            keywords=['hello', 'hi', 'hey', 'good morning', 'good evening'],
            response="👋 Hello! Welcome to the mesh network. Send 'help' if you need assistance.",
            priority=70,
            cooldown_seconds=300,  # 5 minute cooldown for greetings
            max_responses_per_hour=2
        )
        self.add_auto_response_rule(greeting_rule)
    
    async def _initialize_default_commands(self):
        """Initialize default bot commands"""
        if not self.config['commands']['enabled']:
            return
        
        # Create default command handler
        default_handler = BotCommandHandler(self)
        await self.register_command_handler(default_handler, "interactive_bot")
    
    async def _initialize_ai_service(self):
        """Initialize AI service if configured"""
        ai_config = self.config.get('ai', {})
        if not ai_config.get('enabled', False):
            self.logger.info("AI service disabled in configuration")
            return
        
        try:
            from .ai_service import AIService
            
            # Pass the full config dictionary to AIService
            self.ai_service = AIService(self.config)
            self.ai_enabled = await self.ai_service.is_enabled()
            
            if self.ai_enabled:
                self.logger.info("AI service initialized and available")
            else:
                self.logger.warning("AI service initialized but not available")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize AI service: {e}")
            self.ai_service = None
            self.ai_enabled = False
    
    async def _load_known_nodes(self):
        """Load known nodes from database"""
        try:
            db = get_database()
            cursor = db.cursor()
            cursor.execute("SELECT DISTINCT node_id FROM users WHERE last_seen > datetime('now', '-30 days')")
            rows = cursor.fetchall()
            self.known_nodes = {row[0] for row in rows}
            self.logger.debug(f"Loaded {len(self.known_nodes)} known nodes from database")
        except Exception as e:
            self.logger.error(f"Error loading known nodes: {e}")
            self.known_nodes = set()
    
    async def _handle_new_node_greeting(self, sender_id: str, message: Message):
        """Handle greeting for new nodes"""
        if not self.greeting_enabled or not self.config['auto_response']['greeting_enabled']:
            return
        
        # Check if this is truly a new node
        if sender_id in self.known_nodes:
            return
        
        # Check if we've already greeted this node recently
        greeting_delay_hours = self.config['auto_response'].get('greeting_delay_hours', 24)
        if sender_id in self.new_node_greetings:
            last_greeting = self.new_node_greetings[sender_id]
            time_since_greeting = datetime.utcnow() - last_greeting
            if time_since_greeting.total_seconds() < (greeting_delay_hours * 3600):
                return
        
        # Record the greeting
        self.new_node_greetings[sender_id] = datetime.utcnow()
        self.known_nodes.add(sender_id)
        
        # Store in database
        await self._store_new_node(sender_id)
        
        greeting_message = self.config['auto_response'].get(
            'greeting_message',
            '🎉 Welcome to the mesh network! You\'re now connected to our community. Send "help" for available commands and services.'
        )
        
        # Enhanced greeting with network info
        enhanced_greeting = f"{greeting_message}\n\n📡 Network Services:\n• BBS: Send 'bbs' for bulletins and mail\n• Weather: Send 'wx' for conditions\n• Games: Send 'games' for entertainment\n• Help: Send 'help' anytime"
        
        # Send greeting via communication interface
        if self.communication:
            response_message = self._create_response_message(enhanced_greeting, message)
            await self.communication.send_mesh_message(response_message)
            
            # Log the new node greeting
            self.logger.info(f"Sent welcome greeting to new node: {sender_id}")
    
    async def _store_new_node(self, node_id: str):
        """Store new node in database"""
        try:
            db = get_database()
            cursor = db.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users (node_id, short_name, last_seen)
                VALUES (?, ?, ?)
            """, (node_id, node_id[-4:], datetime.utcnow()))
            db.commit()
        except Exception as e:
            self.logger.error(f"Error storing new node {node_id}: {e}")
    
    async def _handle_command(self, content: str, sender_id: str, message: Message) -> Optional[str]:
        """Handle command processing using comprehensive command handler"""
        # Parse command
        content = content.lstrip('!/').strip()
        parts = content.split()
        if not parts:
            return None
        
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        # Create enhanced context for comprehensive handler
        context = {
            'sender_id': sender_id,
            'sender_name': getattr(message, 'sender_name', sender_id),
            'channel': getattr(message, 'channel', 0),
            'is_direct_message': message.recipient_id is not None,
            'is_admin': self._is_admin_user(sender_id),
            'is_moderator': self._is_moderator_user(sender_id),
            'user_permissions': self._get_user_permissions(sender_id),
            'message_timestamp': getattr(message, 'timestamp', None),
            'interface_id': getattr(message, 'interface_id', ''),
            'message': message
        }
        
        try:
            # Check for quiz/survey answer shortcuts (q:answer, s:answer)
            if content.startswith('q:') and len(content) > 2:
                # Quiz answer shortcut
                if self.educational_service and sender_id in self.educational_service.active_sessions:
                    session = self.educational_service.active_sessions[sender_id]
                    if session.session_type == 'quiz':
                        answer = content[2:].strip()
                        response = await self.educational_service._handle_quiz_answer(
                            [answer], session, context
                        )
                        return response
                return "❓ No active quiz session. Send 'quiz' to start."
            
            elif content.startswith('s:') and len(content) > 2:
                # Survey answer shortcut
                if self.educational_service and sender_id in self.educational_service.active_sessions:
                    session = self.educational_service.active_sessions[sender_id]
                    if session.session_type == 'survey':
                        answer = content[2:].strip()
                        response = await self.educational_service._handle_survey_answer(
                            [answer], session, context
                        )
                        return response
                return "❓ No active survey session. Send 'survey' to see available surveys."
            
            # Check if this is a game command first
            if command in self.game_manager.games:
                # Start the game directly
                game_response = await self.handle_game_command(
                    command, sender_id, context.get('sender_name', sender_id), args
                )
                return game_response
            elif command == 'games':
                # Show available games
                return await self.get_games_list()
            
            # Use comprehensive command handler for other commands
            response = await self.comprehensive_handler.handle_command(command, args, context)
            return response
            
        except Exception as e:
            self.logger.error(f"Error executing command '{command}': {e}")
            return f"❌ Error executing command '{command}'. Please try again."
    
    async def _check_auto_response(self, content: str, sender_id: str, 
                                 is_direct_message: bool, message: Message) -> Optional[str]:
        """Check for auto-response triggers with enhanced matching and rate limiting"""
        if not self.config['auto_response']['enabled']:
            return None
        
        current_time = datetime.utcnow()
        
        for rule in self.auto_response_rules:
            if not rule.enabled:
                continue
            
            # Check channel restrictions
            if rule.direct_message_only and not is_direct_message:
                continue
            
            # Check channel whitelist/blacklist
            if rule.channels and message.channel not in rule.channels:
                continue
            if rule.exclude_channels and message.channel in rule.exclude_channels:
                continue
            
            # Check time restrictions
            if not self._check_time_restrictions(rule, current_time):
                continue
            
            # Check for keyword matches based on match type
            if not self._check_keyword_match(content, rule):
                continue
            
            # Check rate limiting and cooldowns
            if not self._check_rate_limits(sender_id, rule, current_time):
                continue
            
            # Record the response
            self._record_response(sender_id, rule, current_time)
            
            # Handle emergency keywords with escalation
            if rule.emergency:
                await self._handle_emergency_keyword_with_escalation(content, sender_id, message, rule)
            
            return rule.response
        
        return None
    
    def _check_keyword_match(self, content: str, rule: AutoResponseRule) -> bool:
        """Check if content matches rule keywords based on match type"""
        content_to_check = content if rule.case_sensitive else content.lower()
        
        for keyword in rule.keywords:
            keyword_to_check = keyword if rule.case_sensitive else keyword.lower()
            
            if rule.match_type == "exact":
                if content_to_check == keyword_to_check:
                    return True
            elif rule.match_type == "starts_with":
                if content_to_check.startswith(keyword_to_check):
                    return True
            elif rule.match_type == "ends_with":
                if content_to_check.endswith(keyword_to_check):
                    return True
            elif rule.match_type == "regex":
                try:
                    if re.search(keyword_to_check, content_to_check):
                        return True
                except re.error:
                    self.logger.warning(f"Invalid regex pattern: {keyword_to_check}")
            else:  # default: "contains"
                if keyword_to_check in content_to_check:
                    return True
        
        return False
    
    def _check_time_restrictions(self, rule: AutoResponseRule, current_time: datetime) -> bool:
        """Check if current time meets rule time restrictions"""
        if not rule.time_restrictions:
            return True
        
        # TODO: Implement time-based restrictions (hours, days of week, etc.)
        # For now, always return True
        return True
    
    def _check_rate_limits(self, sender_id: str, rule: AutoResponseRule, current_time: datetime) -> bool:
        """Check rate limits and cooldowns for user and rule"""
        if sender_id not in self.response_tracker:
            return True
        
        user_trackers = self.response_tracker[sender_id]
        
        # Check for existing tracker for this rule
        for tracker in user_trackers:
            if set(tracker.rule_keywords) == set(rule.keywords):
                # Check cooldown
                if rule.cooldown_seconds > 0:
                    time_since_last = (current_time - tracker.last_response).total_seconds()
                    if time_since_last < rule.cooldown_seconds:
                        return False
                
                # Check hourly rate limit
                if rule.max_responses_per_hour > 0:
                    hour_ago = current_time - timedelta(hours=1)
                    if tracker.last_response > hour_ago and tracker.response_count >= rule.max_responses_per_hour:
                        return False
        
        return True
    
    def _record_response(self, sender_id: str, rule: AutoResponseRule, current_time: datetime):
        """Record response for rate limiting tracking"""
        if sender_id not in self.response_tracker:
            self.response_tracker[sender_id] = []
        
        user_trackers = self.response_tracker[sender_id]
        
        # Find existing tracker or create new one
        tracker = None
        for t in user_trackers:
            if set(t.rule_keywords) == set(rule.keywords):
                tracker = t
                break
        
        if tracker:
            # Update existing tracker
            hour_ago = current_time - timedelta(hours=1)
            if tracker.last_response <= hour_ago:
                tracker.response_count = 1  # Reset count for new hour
            else:
                tracker.response_count += 1
            tracker.last_response = current_time
        else:
            # Create new tracker
            tracker = ResponseTracker(
                user_id=sender_id,
                rule_keywords=rule.keywords,
                last_response=current_time
            )
            user_trackers.append(tracker)
        
        # Clean up old trackers (older than 24 hours)
        day_ago = current_time - timedelta(days=1)
        self.response_tracker[sender_id] = [
            t for t in user_trackers if t.last_response > day_ago
        ]
    
    async def _check_ai_response(self, message: Message) -> Optional[str]:
        """Check if AI response is needed (aircraft detection)"""
        if not self.ai_enabled or not self.ai_service:
            return None
        
        try:
            # Extract altitude from message metadata if available
            altitude = getattr(message, 'altitude', None)
            location = getattr(message, 'location', None)
            
            # Get recent message context for this sender
            recent_messages = await self._get_recent_messages(message.sender_id, limit=5)
            
            # Generate AI response
            ai_response = await self.ai_service.generate_response(
                message=message,
                altitude=altitude,
                location=location,
                recent_messages=recent_messages
            )
            
            if ai_response and not ai_response.fallback_used:
                self.logger.info(f"Generated AI response for {message.sender_id} (aircraft: {ai_response.confidence > 0.5})")
                return ai_response.content
            
        except Exception as e:
            self.logger.error(f"Error generating AI response: {e}")
        
        return None
    
    async def _handle_emergency_keyword_with_escalation(self, content: str, sender_id: str, 
                                                      message: Message, rule: AutoResponseRule):
        """Handle emergency keyword detection with escalation"""
        self.logger.warning(f"Emergency keyword detected from {sender_id}: {content}")
        
        # Immediate notification to emergency response service
        if self.communication:
            emergency_message = PluginMessage(
                type=PluginMessageType.SYSTEM_EVENT,
                target_plugin="emergency_response",
                data={
                    'type': 'emergency_keyword_detected',
                    'sender_id': sender_id,
                    'content': content,
                    'message': message,
                    'auto_detected': True
                }
            )
            await self.communication.send_message(emergency_message)
        
        # Set up escalation if not already escalated for this user
        escalation_key = f"{sender_id}_{hash(content)}"
        if escalation_key not in self.emergency_escalation_tasks:
            escalation_task = asyncio.create_task(
                self._escalate_emergency_after_delay(sender_id, content, message, rule.escalation_delay)
            )
            self.emergency_escalation_tasks[escalation_key] = escalation_task
    
    async def _escalate_emergency_after_delay(self, sender_id: str, content: str, 
                                            message: Message, delay_seconds: int):
        """Escalate emergency after delay if no response received"""
        try:
            await asyncio.sleep(delay_seconds)
            
            # Check if emergency was acknowledged/resolved
            escalation_key = f"{sender_id}_{hash(content)}"
            
            # Find the response tracker to check if escalated
            if sender_id in self.response_tracker:
                for tracker in self.response_tracker[sender_id]:
                    if tracker.escalated:
                        return  # Already escalated
            
            # Escalate to wider audience
            escalation_message = self.config['auto_response']['emergency_escalation_message'].format(
                sender=sender_id,
                message=content
            )
            
            self.logger.critical(f"Escalating emergency from {sender_id}: {content}")
            
            # Send escalation message to all channels
            if self.communication:
                escalation_msg = Message(
                    sender_id="emergency_bot",
                    recipient_id=None,  # Broadcast
                    channel=0,  # Primary channel
                    content=f"🚨🚨 {escalation_message} 🚨🚨",
                    message_type=MessageType.TEXT,
                    priority=MessagePriority.EMERGENCY,
                    timestamp=datetime.utcnow()
                )
                await self.communication.send_mesh_message(escalation_msg)
                
                # Also notify emergency response service about escalation
                escalation_plugin_msg = PluginMessage(
                    type=PluginMessageType.SYSTEM_EVENT,
                    target_plugin="emergency_response",
                    data={
                        'type': 'emergency_escalated',
                        'sender_id': sender_id,
                        'original_content': content,
                        'escalation_message': escalation_message,
                        'original_message': message
                    }
                )
                await self.communication.send_message(escalation_plugin_msg)
            
            # Mark as escalated
            if sender_id in self.response_tracker:
                for tracker in self.response_tracker[sender_id]:
                    if any(kw in content.lower() for kw in tracker.rule_keywords):
                        tracker.escalated = True
                        break
            
        except asyncio.CancelledError:
            self.logger.debug(f"Emergency escalation cancelled for {sender_id}")
        except Exception as e:
            self.logger.error(f"Error during emergency escalation: {e}")
        finally:
            # Clean up escalation task
            escalation_key = f"{sender_id}_{hash(content)}"
            if escalation_key in self.emergency_escalation_tasks:
                del self.emergency_escalation_tasks[escalation_key]
    
    def cancel_emergency_escalation(self, sender_id: str, content: str):
        """Cancel emergency escalation (called when emergency is acknowledged)"""
        escalation_key = f"{sender_id}_{hash(content)}"
        if escalation_key in self.emergency_escalation_tasks:
            task = self.emergency_escalation_tasks[escalation_key]
            task.cancel()
            del self.emergency_escalation_tasks[escalation_key]
            self.logger.info(f"Cancelled emergency escalation for {sender_id}")
    
    def _create_response_message(self, content: str, original_message: Message) -> Message:
        """Create a response message"""
        return Message(
            sender_id="bot",
            recipient_id=original_message.sender_id,  # Always respond to sender
            channel=original_message.channel,
            content=content,
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
    
    def _initialize_games(self):
        """Initialize all available games"""
        from .games import (
            TicTacToeGame, HangmanGame, BlackjackGame, VideoPokerGame,
            DopeWarsGame, LemonadeStandGame, GolfSimulatorGame, MastermindGame
        )
        
        # Register all game implementations
        self.game_manager.register_game(TicTacToeGame())
        self.game_manager.register_game(HangmanGame())
        self.game_manager.register_game(BlackjackGame())
        self.game_manager.register_game(VideoPokerGame())
        self.game_manager.register_game(DopeWarsGame())
        self.game_manager.register_game(LemonadeStandGame())
        self.game_manager.register_game(GolfSimulatorGame())
        self.game_manager.register_game(MastermindGame())
        
        self.logger.info(f"Initialized {len(self.game_manager.games)} games")
    
    async def _start_game_manager(self):
        """Start the game manager"""
        # The game manager will start its cleanup task automatically when needed
        pass
    
    async def handle_game_command(self, game_type: str, player_id: str, player_name: str, args: List[str] = None) -> str:
        """Handle game start command"""
        if game_type not in self.game_manager.games:
            available_games = ", ".join(self.game_manager.get_available_games())
            return f"Unknown game '{game_type}'. Available games: {available_games}"
        
        # Start new game (game manager will handle ending any existing game)
        response = await self.game_manager.start_game(game_type, player_id, player_name, args)
        return response or f"Error starting {game_type} game."
    
    async def get_games_list(self) -> str:
        """Get list of available games"""
        return await self.game_manager.get_game_list()
    
    async def get_game_stats(self) -> Dict[str, Any]:
        """Get game statistics"""
        return await self.game_manager.get_session_stats()
    
    async def _get_recent_messages(self, sender_id: str, limit: int = 5) -> List[Message]:
        """Get recent messages for context"""
        try:
            db = get_database()
            cursor = db.cursor()
            
            # Get recent messages from this sender and bot responses
            cursor.execute("""
                SELECT sender_id, recipient_id, channel, content, timestamp, message_type
                FROM messages 
                WHERE (sender_id = ? OR recipient_id = ?) 
                AND timestamp > datetime('now', '-1 hour')
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (sender_id, sender_id, limit))
            
            rows = cursor.fetchall()
            messages = []
            
            for row in rows:
                # Create Message objects from database rows
                message = Message(
                    sender_id=row[0],
                    recipient_id=row[1],
                    channel=row[2] or 0,
                    content=row[3],
                    message_type=MessageType.TEXT,
                    timestamp=datetime.fromisoformat(row[4]) if row[4] else datetime.utcnow()
                )
                messages.append(message)
            
            # Return in chronological order (oldest first)
            return list(reversed(messages))
            
        except Exception as e:
            self.logger.error(f"Error getting recent messages for {sender_id}: {e}")
            return []
    
    async def get_ai_statistics(self) -> Optional[Dict[str, Any]]:
        """Get AI service statistics"""
        if self.ai_service:
            return self.ai_service.get_statistics()
        return None


class BotCommandHandler(BaseCommandHandler):
    """Default command handler for bot commands"""
    
    def __init__(self, bot_service: InteractiveBotService):
        super().__init__(['help', 'ping', 'status', 'commands', 'askai', 'ask', 'aistatus'])
        self.bot_service = bot_service
        
        # Add help text
        self.add_help('help', 'Show available commands or help for specific command')
        self.add_help('ping', 'Test bot responsiveness')
        self.add_help('status', 'Show bot status and statistics')
        self.add_help('commands', 'List all available commands')
        self.add_help('askai', 'Ask AI assistant a question (if available)')
        self.add_help('ask', 'Ask AI assistant a question (if available)')
        self.add_help('aistatus', 'Show AI service status and statistics')
    
    async def handle_command(self, command: str, args: List[str], context: Dict[str, Any]) -> str:
        """Handle bot commands"""
        if command == 'help':
            return await self._handle_help(args)
        elif command == 'ping':
            return "Pong! Bot is active and responding."
        elif command == 'status':
            return await self._handle_status()
        elif command == 'commands':
            return await self._handle_commands()
        elif command in ['askai', 'ask']:
            return await self._handle_ai_question(args, context)
        elif command == 'aistatus':
            return await self._handle_ai_status()
        else:
            return f"Command {command} not implemented"
    
    async def _handle_help(self, args: List[str]) -> str:
        """Handle help command"""
        if not args:
            # General help
            commands = list(self.bot_service.command_handlers.keys())
            commands.sort()
            return f"Available commands: {', '.join(commands)}. Send 'help <command>' for details."
        
        command = args[0].lower()
        if command in self.bot_service.command_handlers:
            command_info = self.bot_service.command_handlers[command]
            return f"{command}: {command_info.help_text}"
        else:
            return f"Unknown command: {command}"
    
    async def _handle_status(self) -> str:
        """Handle status command"""
        num_commands = len(self.bot_service.command_handlers)
        num_rules = len(self.bot_service.auto_response_rules)
        ai_status = "enabled" if self.bot_service.ai_enabled else "disabled"
        
        status_lines = [
            "🤖 Bot Status: Active",
            f"Commands: {num_commands}",
            f"Auto-response rules: {num_rules}",
            f"AI integration: {ai_status}"
        ]
        
        # Add AI statistics if available
        if self.bot_service.ai_enabled and self.bot_service.ai_service:
            try:
                ai_stats = self.bot_service.ai_service.get_statistics()
                status_lines.extend([
                    f"AI requests: {ai_stats['requests_total']}",
                    f"Aircraft detected: {ai_stats['aircraft_detected']}"
                ])
            except Exception:
                pass
        
        return "\n".join(status_lines)
    
    async def _handle_commands(self) -> str:
        """Handle commands list"""
        commands_by_plugin = {}
        
        for command, info in self.bot_service.command_handlers.items():
            plugin = info.plugin_name
            if plugin not in commands_by_plugin:
                commands_by_plugin[plugin] = []
            commands_by_plugin[plugin].append(command)
        
        result = "Available commands by plugin:\n"
        for plugin, commands in commands_by_plugin.items():
            commands.sort()
            result += f"{plugin}: {', '.join(commands)}\n"
        
        return result.strip()
    
    async def _handle_ai_question(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle AI question command"""
        if not self.bot_service.ai_enabled or not self.bot_service.ai_service:
            return "🤖 AI assistant is not available. Check configuration or service status."
        
        if not args:
            return "❓ Please provide a question. Usage: askai <your question>"
        
        question = " ".join(args)
        
        try:
            # Create a mock message for AI processing
            from src.models.message import Message, MessageType
            mock_message = Message(
                sender_id=context['sender_id'],
                recipient_id="bot",
                channel=context.get('channel', 0),
                content=question,
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            
            # Add sender name if available
            if 'sender_name' in context:
                mock_message.sender_name = context['sender_name']
            
            # Get recent messages for context
            recent_messages = await self.bot_service._get_recent_messages(context['sender_id'], limit=3)
            
            # Generate AI response
            ai_response = await self.bot_service.ai_service.generate_response(
                message=mock_message,
                altitude=None,  # No altitude data for direct questions
                location=None,
                recent_messages=recent_messages
            )
            
            if ai_response:
                if ai_response.fallback_used:
                    return f"🤖 {ai_response.content}"
                else:
                    return f"🤖 {ai_response.content}"
            else:
                return "🤖 Sorry, I couldn't process your question right now. Please try again later."
                
        except Exception as e:
            self.bot_service.logger.error(f"Error handling AI question: {e}")
            return "🤖 Error processing your question. Please try again later."
    
    async def _handle_ai_status(self) -> str:
        """Handle AI status command"""
        if not self.bot_service.ai_service:
            return "🤖 AI service is not configured."
        
        try:
            stats = self.bot_service.ai_service.get_statistics()
            
            status_lines = [
                f"🤖 AI Service Status:",
                f"Enabled: {'✅' if stats['config']['enabled'] else '❌'}",
                f"Service: {stats['config']['service_type']}",
                f"Model: {stats['config']['model']}"
            ]
            
            if 'provider_info' in stats:
                provider = stats['provider_info']
                status_lines.append(f"Health: {'✅' if provider.get('healthy', False) else '❌'}")
            
            status_lines.extend([
                f"Requests: {stats['requests_total']} total",
                f"Success: {stats['requests_successful']}",
                f"Failed: {stats['requests_failed']}",
                f"Aircraft detected: {stats['aircraft_detected']}",
                f"Avg response time: {stats['average_response_time']:.2f}s"
            ])
            
            return "\n".join(status_lines)
            
        except Exception as e:
            self.bot_service.logger.error(f"Error getting AI status: {e}")
            return "🤖 Error retrieving AI status."


class BotMessageHandler(BaseMessageHandler):
    """Message handler for bot service"""
    
    def __init__(self, bot_service: InteractiveBotService, priority: int = 100):
        super().__init__(priority)
        self.bot_service = bot_service
    
    def can_handle(self, message: Message) -> bool:
        """Check if this handler can process the message"""
        # Bot can handle all text messages
        return message.message_type == MessageType.TEXT
    
    async def handle_message(self, message: Message, context: Dict[str, Any]) -> Optional[Any]:
        """Handle message through bot service"""
        return await self.bot_service.handle_message(message)