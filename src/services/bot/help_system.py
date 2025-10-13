"""
Comprehensive Help System

Provides detailed help and documentation for all commands specified in Requirement 14.
Includes command categories, usage examples, and interactive help features.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from .command_registry import CommandRegistry, CommandContext, CommandPermission


class HelpCategory(Enum):
    """Help categories for organizing commands"""
    BASIC = "basic"
    EMERGENCY = "emergency"
    BBS = "bbs"
    WEATHER = "weather"
    GAMES = "games"
    INFORMATION = "information"
    COMMUNICATION = "communication"
    ADMIN = "admin"
    UTILITY = "utility"


@dataclass
class CommandDocumentation:
    """Comprehensive documentation for a command"""
    name: str
    category: HelpCategory
    description: str
    usage: str
    syntax: str
    parameters: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    permissions: List[CommandPermission] = field(default_factory=lambda: [CommandPermission.PUBLIC])
    notes: List[str] = field(default_factory=list)
    related_commands: List[str] = field(default_factory=list)
    version_added: str = "1.0"
    deprecated: bool = False
    replacement: Optional[str] = None


class HelpSystem:
    """
    Comprehensive help system for all commands
    """
    
    def __init__(self, command_registry: CommandRegistry):
        self.registry = command_registry
        self.documentation: Dict[str, CommandDocumentation] = {}
        self._initialize_command_documentation()
    
    def _initialize_command_documentation(self):
        """Initialize comprehensive documentation for all commands"""
        
        # Basic Commands (Requirement 14.1)
        self._add_basic_commands()
        
        # Emergency Commands (Requirement 14 - Emergency and Alert Commands)
        self._add_emergency_commands()
        
        # BBS Commands (Requirement 14.5)
        self._add_bbs_commands()
        
        # Weather Commands (Requirement 14 - Information and Utility Commands)
        self._add_weather_commands()
        
        # Information and Utility Commands
        self._add_information_commands()
        
        # Game Commands (Requirement 14 - Game and Interactive Commands)
        self._add_game_commands()
        
        # Communication Commands (Requirement 14.6)
        self._add_communication_commands()
        
        # Administrative Commands (Requirement 14 - Administrative Commands)
        self._add_admin_commands()
        
        # Asset Management Commands (Requirement 14 - Asset Management Commands)
        self._add_asset_commands()
    
    def _add_basic_commands(self):
        """Add basic command documentation"""
        
        # Help commands
        self.documentation["help"] = CommandDocumentation(
            name="help",
            category=HelpCategory.BASIC,
            description="Display help information for commands",
            usage="help [command|category]",
            syntax="help [topic]",
            parameters=[
                "topic (optional) - Specific command or category to get help for"
            ],
            examples=[
                "help - Show all available commands",
                "help ping - Show detailed help for ping command",
                "help emergency - Show all emergency commands",
                "help categories - Show all command categories"
            ],
            aliases=["?", "cmd"],
            notes=[
                "Use 'help categories' to see all available categories",
                "Use 'help <category>' to see commands in a specific category"
            ]
        )
        
        # Connectivity test commands
        self.documentation["ping"] = CommandDocumentation(
            name="ping",
            category=HelpCategory.BASIC,
            description="Test connectivity and get signal quality information",
            usage="ping",
            syntax="ping",
            examples=[
                "ping - Test connectivity and get signal report"
            ],
            aliases=["ack", "cq", "test", "pong"],
            notes=[
                "Returns signal quality, hop count, and network status",
                "Useful for testing mesh connectivity"
            ]
        )
        
        # Status commands
        self.documentation["status"] = CommandDocumentation(
            name="status",
            category=HelpCategory.BASIC,
            description="Get current system and network status",
            usage="status",
            syntax="status",
            examples=[
                "status - Show system status and active services"
            ],
            related_commands=["sitrep", "sysinfo"]
        )
    
    def _add_emergency_commands(self):
        """Add emergency command documentation"""
        
        # SOS commands
        sos_commands = [
            ("sos", "General emergency alert"),
            ("sosp", "Police emergency"),
            ("sosf", "Fire emergency"),
            ("sosm", "Medical emergency")
        ]
        
        for cmd, desc in sos_commands:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.EMERGENCY,
                description=f"{desc} - triggers immediate alert to responders",
                usage=f"{cmd} [message]",
                syntax=f"{cmd} [optional message]",
                parameters=[
                    "message (optional) - Additional information about the emergency"
                ],
                examples=[
                    f"{cmd} - Send {desc.lower()}",
                    f"{cmd} Need assistance at coordinates - Send {desc.lower()} with details"
                ],
                notes=[
                    "🚨 EMERGENCY COMMAND - Use only in real emergencies",
                    "Automatically alerts designated responders",
                    "Escalates to broader network if not acknowledged",
                    "Location information is automatically included if available"
                ],
                related_commands=["clear", "cancel", "safe", "ack", "responding"]
            )
        
        # Emergency response commands
        self.documentation["ack"] = CommandDocumentation(
            name="ack",
            category=HelpCategory.EMERGENCY,
            description="Acknowledge an emergency alert",
            usage="ack [incident_id]",
            syntax="ack [incident_id]",
            parameters=[
                "incident_id (optional) - Specific incident to acknowledge"
            ],
            examples=[
                "ack - Acknowledge the most recent emergency",
                "ack 123 - Acknowledge specific incident #123"
            ],
            related_commands=["responding", "sos", "active"]
        )
        
        self.documentation["responding"] = CommandDocumentation(
            name="responding",
            category=HelpCategory.EMERGENCY,
            description="Indicate you are responding to an emergency",
            usage="responding [incident_id]",
            syntax="responding [incident_id]",
            parameters=[
                "incident_id (optional) - Specific incident you're responding to"
            ],
            examples=[
                "responding - Respond to most recent emergency",
                "responding 123 - Respond to specific incident #123"
            ],
            related_commands=["ack", "sos", "active"]
        )
        
        # Emergency clearing commands
        clear_commands = [
            ("clear", "Clear/resolve an emergency situation"),
            ("cancel", "Cancel a false alarm emergency"),
            ("safe", "Report that you are safe")
        ]
        
        for cmd, desc in clear_commands:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.EMERGENCY,
                description=desc,
                usage=f"{cmd} [incident_id]",
                syntax=f"{cmd} [incident_id]",
                parameters=[
                    "incident_id (optional) - Specific incident to clear"
                ],
                examples=[
                    f"{cmd} - {desc} for most recent incident",
                    f"{cmd} 123 - {desc} for specific incident #123"
                ],
                related_commands=["sos", "active", "alertstatus"]
            )
        
        # Emergency status commands
        self.documentation["active"] = CommandDocumentation(
            name="active",
            category=HelpCategory.EMERGENCY,
            description="Show active emergency incidents",
            usage="active",
            syntax="active",
            examples=[
                "active - List all active emergency incidents"
            ],
            aliases=["alertstatus"],
            related_commands=["sos", "ack", "responding"]
        )
    
    def _add_bbs_commands(self):
        """Add BBS command documentation"""
        
        self.documentation["bbs"] = CommandDocumentation(
            name="bbs",
            category=HelpCategory.BBS,
            description="Access the Bulletin Board System main menu",
            usage="bbs",
            syntax="bbs",
            examples=[
                "bbs - Enter BBS main menu"
            ],
            notes=[
                "Interactive menu system for bulletins, mail, and directory",
                "Use menu numbers to navigate"
            ],
            related_commands=["bbshelp", "bbslist", "bbspost"]
        )
        
        self.documentation["bbshelp"] = CommandDocumentation(
            name="bbshelp",
            category=HelpCategory.BBS,
            description="Show BBS system help and commands",
            usage="bbshelp",
            syntax="bbshelp",
            examples=[
                "bbshelp - Show BBS help information"
            ],
            related_commands=["bbs", "bbslist"]
        )
        
        self.documentation["bbslist"] = CommandDocumentation(
            name="bbslist",
            category=HelpCategory.BBS,
            description="List available bulletins",
            usage="bbslist [board]",
            syntax="bbslist [board_name]",
            parameters=[
                "board (optional) - Specific bulletin board to list"
            ],
            examples=[
                "bbslist - List all bulletins",
                "bbslist general - List bulletins on general board"
            ],
            related_commands=["bbsread", "bbspost", "bbsdelete"]
        )
        
        self.documentation["bbsread"] = CommandDocumentation(
            name="bbsread",
            category=HelpCategory.BBS,
            description="Read a specific bulletin",
            usage="bbsread #ID",
            syntax="bbsread #message_id",
            parameters=[
                "message_id - ID number of the bulletin to read"
            ],
            examples=[
                "bbsread #123 - Read bulletin message #123",
                "bbsread 456 - Read bulletin message #456"
            ],
            related_commands=["bbslist", "bbspost", "bbsdelete"]
        )
        
        self.documentation["bbspost"] = CommandDocumentation(
            name="bbspost",
            category=HelpCategory.BBS,
            description="Post a new bulletin",
            usage="bbspost [subject[/content]]",
            syntax="bbspost [subject] or bbspost subject/content",
            parameters=[
                "subject (optional) - Subject line for the bulletin",
                "content (optional) - Content of the bulletin"
            ],
            examples=[
                "bbspost - Interactive bulletin posting",
                "bbspost Weekly Update - Post with subject only",
                "bbspost Weekly Update/All systems operational - Post with subject and content"
            ],
            related_commands=["bbslist", "bbsread", "bbsdelete"]
        )
        
        self.documentation["bbsdelete"] = CommandDocumentation(
            name="bbsdelete",
            category=HelpCategory.BBS,
            description="Delete your own bulletin",
            usage="bbsdelete #ID",
            syntax="bbsdelete #message_id",
            parameters=[
                "message_id - ID number of your bulletin to delete"
            ],
            examples=[
                "bbsdelete #123 - Delete your bulletin #123"
            ],
            notes=[
                "You can only delete your own bulletins",
                "Administrators can delete any bulletin"
            ],
            related_commands=["bbslist", "bbspost"]
        )
        
        self.documentation["bbsinfo"] = CommandDocumentation(
            name="bbsinfo",
            category=HelpCategory.BBS,
            description="Show BBS system information and statistics",
            usage="bbsinfo",
            syntax="bbsinfo",
            examples=[
                "bbsinfo - Show BBS statistics and information"
            ],
            related_commands=["bbs", "bbshelp"]
        )
        
        self.documentation["bbslink"] = CommandDocumentation(
            name="bbslink",
            category=HelpCategory.BBS,
            description="Manage BBS node linking and synchronization",
            usage="bbslink [command]",
            syntax="bbslink [sync|status|add|remove]",
            parameters=[
                "command (optional) - Link management command"
            ],
            examples=[
                "bbslink - Show link status",
                "bbslink sync - Force synchronization with peer nodes"
            ],
            permissions=[CommandPermission.ADMIN],
            related_commands=["bbs", "bbsinfo"]
        )
    
    def _add_weather_commands(self):
        """Add weather command documentation"""
        
        weather_commands = [
            ("wx", "weather", "Get current weather conditions"),
            ("wxc", "weather_current", "Get current weather conditions (detailed)"),
            ("wxa", "weather_alerts", "Get active weather alerts"),
            ("wxalert", "weather_alert", "Get weather alert details"),
            ("mwx", "weather_marine", "Get marine weather conditions")
        ]
        
        for cmd, full_name, desc in weather_commands:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.WEATHER,
                description=desc,
                usage=f"{cmd} [location]",
                syntax=f"{cmd} [location]",
                parameters=[
                    "location (optional) - Specific location for weather data"
                ],
                examples=[
                    f"{cmd} - Get weather for your location",
                    f"{cmd} Seattle - Get weather for Seattle"
                ],
                related_commands=["subscribe", "alerts"]
            )
    
    def _add_information_commands(self):
        """Add information and utility command documentation"""
        
        # Location commands
        location_commands = [
            ("whereami", "Show your current location"),
            ("whoami", "Show your node information"),
            ("whois", "Look up information about another node"),
            ("howfar", "Calculate distance to another node"),
            ("howtall", "Show altitude/elevation information")
        ]
        
        for cmd, desc in location_commands:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.INFORMATION,
                description=desc,
                usage=f"{cmd} [target]" if cmd in ["whois", "howfar"] else cmd,
                syntax=f"{cmd} [node_id]" if cmd in ["whois", "howfar"] else cmd,
                parameters=[
                    "node_id - Target node to query"
                ] if cmd in ["whois", "howfar"] else [],
                examples=[
                    f"{cmd} - {desc}",
                    f"{cmd} !12345678 - {desc} for specific node"
                ] if cmd in ["whois", "howfar"] else [f"{cmd} - {desc}"],
                related_commands=["status", "lheard"]
            )
        
        # Reference data commands
        reference_commands = [
            ("solar", "Get solar conditions and space weather"),
            ("hfcond", "Get HF band conditions"),
            ("sun", "Get sunrise/sunset times"),
            ("moon", "Get moon phase and lunar information"),
            ("tide", "Get tide information"),
            ("earthquake", "Get recent earthquake data"),
            ("riverflow", "Get river flow and flood information")
        ]
        
        for cmd, desc in reference_commands:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.INFORMATION,
                description=desc,
                usage=f"{cmd} [location]",
                syntax=f"{cmd} [location]",
                parameters=[
                    "location (optional) - Specific location for data"
                ],
                examples=[
                    f"{cmd} - {desc} for your location",
                    f"{cmd} Seattle - {desc} for Seattle"
                ],
                related_commands=["wx", "whereami"]
            )
        
        # Network information commands
        network_commands = [
            ("lheard", "List recently heard nodes"),
            ("sitrep", "Get situation report and network status"),
            ("sysinfo", "Get system information"),
            ("leaderboard", "Show network activity leaderboard"),
            ("history", "Show recent message history"),
            ("messages", "Show message statistics")
        ]
        
        for cmd, desc in network_commands:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.INFORMATION,
                description=desc,
                usage=cmd,
                syntax=cmd,
                examples=[
                    f"{cmd} - {desc}"
                ],
                related_commands=["status", "ping"]
            )
        
        # Search commands
        self.documentation["wiki"] = CommandDocumentation(
            name="wiki",
            category=HelpCategory.INFORMATION,
            description="Search Wikipedia",
            usage="wiki:search_term",
            syntax="wiki:search_term",
            parameters=[
                "search_term - Term to search for on Wikipedia"
            ],
            examples=[
                "wiki:Meshtastic - Search Wikipedia for Meshtastic",
                "wiki:Ham Radio - Search Wikipedia for Ham Radio"
            ],
            notes=[
                "Requires internet connectivity",
                "Returns summary of Wikipedia article"
            ],
            related_commands=["ask", "askai"]
        )
        
        # AI commands
        ai_commands = [
            ("askai", "Ask AI assistant a question"),
            ("ask", "Ask AI assistant a question (alias)")
        ]
        
        for cmd, desc in ai_commands:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.INFORMATION,
                description=desc,
                usage=f"{cmd}:question",
                syntax=f"{cmd}:question",
                parameters=[
                    "question - Question to ask the AI assistant"
                ],
                examples=[
                    f"{cmd}:What is Meshtastic? - Ask about Meshtastic",
                    f"{cmd}:How do I configure my radio? - Ask for help"
                ],
                notes=[
                    "Requires AI service to be configured",
                    "May have usage limits"
                ],
                related_commands=["wiki", "help"]
            )
        
        # Other information commands
        self.documentation["satpass"] = CommandDocumentation(
            name="satpass",
            category=HelpCategory.INFORMATION,
            description="Get satellite pass predictions",
            usage="satpass [satellite]",
            syntax="satpass [satellite_name]",
            parameters=[
                "satellite (optional) - Specific satellite to track"
            ],
            examples=[
                "satpass - Get ISS pass times",
                "satpass NOAA-18 - Get NOAA-18 pass times"
            ],
            related_commands=["whereami", "sun"]
        )
        
        self.documentation["rlist"] = CommandDocumentation(
            name="rlist",
            category=HelpCategory.INFORMATION,
            description="List nearby repeaters",
            usage="rlist [location]",
            syntax="rlist [location]",
            parameters=[
                "location (optional) - Location to search around"
            ],
            examples=[
                "rlist - List repeaters near your location",
                "rlist Seattle - List repeaters near Seattle"
            ],
            related_commands=["whereami", "howfar"]
        )
        
        # News commands
        news_commands = [
            ("readnews", "Read latest news"),
            ("readrss", "Read RSS feeds"),
            ("motd", "Show message of the day")
        ]
        
        for cmd, desc in news_commands:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.INFORMATION,
                description=desc,
                usage=cmd,
                syntax=cmd,
                examples=[
                    f"{cmd} - {desc}"
                ],
                related_commands=["status", "bbslist"]
            )
    
    def _add_game_commands(self):
        """Add game command documentation"""
        
        games = [
            ("blackjack", "Play Blackjack card game"),
            ("videopoker", "Play Video Poker"),
            ("dopewars", "Play DopeWars trading game"),
            ("lemonstand", "Play Lemonade Stand business simulation"),
            ("golfsim", "Play Golf Simulator"),
            ("mastermind", "Play Mastermind logic puzzle"),
            ("hangman", "Play Hangman word game"),
            ("tictactoe", "Play Tic-Tac-Toe")
        ]
        
        for cmd, desc in games:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.GAMES,
                description=desc,
                usage=cmd,
                syntax=cmd,
                examples=[
                    f"{cmd} - Start playing {desc.lower()}"
                ],
                notes=[
                    "Interactive game - follow prompts to play",
                    "Send 'quit' to exit game at any time"
                ],
                related_commands=["help games"]
            )
        
        # Educational games
        self.documentation["hamtest"] = CommandDocumentation(
            name="hamtest",
            category=HelpCategory.GAMES,
            description="Take ham radio license test questions",
            usage="hamtest [level]",
            syntax="hamtest [technician|general|extra]",
            parameters=[
                "level (optional) - License level to test"
            ],
            examples=[
                "hamtest - Random test questions",
                "hamtest technician - Technician class questions",
                "hamtest general - General class questions"
            ],
            related_commands=["quiz"]
        )
        
        self.documentation["quiz"] = CommandDocumentation(
            name="quiz",
            category=HelpCategory.GAMES,
            description="Participate in interactive quiz",
            usage="quiz [topic]",
            syntax="quiz [topic] or q:answer",
            parameters=[
                "topic (optional) - Quiz topic",
                "answer - Answer to current quiz question"
            ],
            examples=[
                "quiz - Start general quiz",
                "quiz science - Start science quiz",
                "q:42 - Answer current question with '42'"
            ],
            related_commands=["hamtest", "survey"]
        )
        
        self.documentation["survey"] = CommandDocumentation(
            name="survey",
            category=HelpCategory.GAMES,
            description="Participate in surveys",
            usage="survey [name] or s:response",
            syntax="survey [survey_name] or s:response",
            parameters=[
                "survey_name (optional) - Specific survey to take",
                "response - Response to current survey question"
            ],
            examples=[
                "survey - List available surveys",
                "survey feedback - Take feedback survey",
                "s:Very satisfied - Respond to current survey question"
            ],
            related_commands=["quiz"]
        )
        
        self.documentation["joke"] = CommandDocumentation(
            name="joke",
            category=HelpCategory.GAMES,
            description="Get a random joke",
            usage="joke",
            syntax="joke",
            examples=[
                "joke - Get a random joke"
            ],
            related_commands=["fortune"]
        )
    
    def _add_communication_commands(self):
        """Add communication command documentation"""
        
        # Subscription management
        subscription_commands = [
            ("subscribe", "Subscribe to services"),
            ("unsubscribe", "Unsubscribe from services")
        ]
        
        for cmd, desc in subscription_commands:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.COMMUNICATION,
                description=desc,
                usage=f"{cmd} [service]",
                syntax=f"{cmd} [service_name]",
                parameters=[
                    "service (optional) - Service to subscribe/unsubscribe to"
                ],
                examples=[
                    f"{cmd} - Show subscription status",
                    f"{cmd} weather - {desc.split()[0]} to weather alerts",
                    f"{cmd} emergency - {desc.split()[0]} to emergency alerts"
                ],
                related_commands=["status", "alerts"]
            )
        
        # Toggle commands
        toggle_commands = [
            ("alerts", "Toggle alert notifications"),
            ("weather", "Toggle weather notifications"),
            ("forecasts", "Toggle forecast notifications")
        ]
        
        for cmd, desc in toggle_commands:
            self.documentation[cmd] = CommandDocumentation(
                name=cmd,
                category=HelpCategory.COMMUNICATION,
                description=desc,
                usage=f"{cmd} on/off",
                syntax=f"{cmd} [on|off]",
                parameters=[
                    "state - 'on' to enable, 'off' to disable"
                ],
                examples=[
                    f"{cmd} on - Enable {desc.lower()}",
                    f"{cmd} off - Disable {desc.lower()}",
                    f"{cmd} - Show current status"
                ],
                related_commands=["subscribe", "status"]
            )
        
        # Personal information commands
        self.documentation["name"] = CommandDocumentation(
            name="name",
            category=HelpCategory.COMMUNICATION,
            description="Set your display name",
            usage="name/YourName",
            syntax="name/display_name",
            parameters=[
                "display_name - Your preferred display name"
            ],
            examples=[
                "name/John Smith - Set display name to 'John Smith'",
                "name/KC1ABC - Set display name to callsign"
            ],
            related_commands=["phone", "address", "whoami"]
        )
        
        self.documentation["phone"] = CommandDocumentation(
            name="phone",
            category=HelpCategory.COMMUNICATION,
            description="Set your phone number",
            usage="phone/type/number",
            syntax="phone/[1|2|3]/phone_number",
            parameters=[
                "type - Phone type (1=primary, 2=secondary, 3=emergency)",
                "number - Phone number"
            ],
            examples=[
                "phone/1/555-123-4567 - Set primary phone",
                "phone/2/555-987-6543 - Set secondary phone"
            ],
            related_commands=["name", "address", "clearsms"]
        )
        
        self.documentation["address"] = CommandDocumentation(
            name="address",
            category=HelpCategory.COMMUNICATION,
            description="Set your address",
            usage="address/your address",
            syntax="address/street_address",
            parameters=[
                "street_address - Your street address"
            ],
            examples=[
                "address/123 Main St, Anytown USA - Set your address"
            ],
            related_commands=["name", "phone", "whereami"]
        )
        
        # Email and SMS commands
        self.documentation["setemail"] = CommandDocumentation(
            name="setemail",
            category=HelpCategory.COMMUNICATION,
            description="Set your email address",
            usage="setemail email@domain.com",
            syntax="setemail email_address",
            parameters=[
                "email_address - Your email address"
            ],
            examples=[
                "setemail john@example.com - Set email address"
            ],
            related_commands=["email", "clearsms"]
        )
        
        self.documentation["setsms"] = CommandDocumentation(
            name="setsms",
            category=HelpCategory.COMMUNICATION,
            description="Set your SMS number",
            usage="setsms phone_number",
            syntax="setsms phone_number",
            parameters=[
                "phone_number - Your SMS-capable phone number"
            ],
            examples=[
                "setsms 555-123-4567 - Set SMS number"
            ],
            related_commands=["sms", "clearsms"]
        )
        
        self.documentation["email"] = CommandDocumentation(
            name="email",
            category=HelpCategory.COMMUNICATION,
            description="Send email via mesh gateway",
            usage="email/to/subject/body",
            syntax="email/recipient/subject/message_body",
            parameters=[
                "recipient - Email address to send to",
                "subject - Email subject line",
                "message_body - Email content"
            ],
            examples=[
                "email/john@example.com/Test/This is a test message - Send email"
            ],
            notes=[
                "Requires email gateway to be configured",
                "Internet connectivity required"
            ],
            related_commands=["setemail", "sms"]
        )
        
        self.documentation["sms"] = CommandDocumentation(
            name="sms",
            category=HelpCategory.COMMUNICATION,
            description="Send SMS message",
            usage="sms:message",
            syntax="sms:message_text",
            parameters=[
                "message_text - SMS message content"
            ],
            examples=[
                "sms:Hello from the mesh network - Send SMS message"
            ],
            notes=[
                "Requires SMS gateway to be configured",
                "Message length limits apply"
            ],
            related_commands=["setsms", "email"]
        )
        
        # Tag-based messaging
        self.documentation["tagsend"] = CommandDocumentation(
            name="tagsend",
            category=HelpCategory.COMMUNICATION,
            description="Send message to users with specific tags",
            usage="tagsend/tags/message",
            syntax="tagsend/tag1,tag2/message_text",
            parameters=[
                "tags - Comma-separated list of tags",
                "message_text - Message to send"
            ],
            examples=[
                "tagsend/emergency,responder/All units report status - Send to tagged users"
            ],
            related_commands=["tagin", "tagout"]
        )
        
        self.documentation["tagin"] = CommandDocumentation(
            name="tagin",
            category=HelpCategory.COMMUNICATION,
            description="Add yourself to a tag group",
            usage="tagin/TAGNAME",
            syntax="tagin/tag_name",
            parameters=[
                "tag_name - Name of tag group to join"
            ],
            examples=[
                "tagin/EMERGENCY - Join emergency responder tag",
                "tagin/WEATHER - Join weather alert tag"
            ],
            related_commands=["tagout", "tagsend"]
        )
        
        self.documentation["tagout"] = CommandDocumentation(
            name="tagout",
            category=HelpCategory.COMMUNICATION,
            description="Remove yourself from a tag group",
            usage="tagout/TAGNAME",
            syntax="tagout/tag_name",
            parameters=[
                "tag_name - Name of tag group to leave"
            ],
            examples=[
                "tagout/EMERGENCY - Leave emergency responder tag"
            ],
            related_commands=["tagin", "tagsend"]
        )
        
        self.documentation["clearsms"] = CommandDocumentation(
            name="clearsms",
            category=HelpCategory.COMMUNICATION,
            description="Clear your SMS contact information",
            usage="clearsms",
            syntax="clearsms",
            examples=[
                "clearsms - Remove SMS contact information"
            ],
            related_commands=["setsms", "phone"]
        )
    
    def _add_admin_commands(self):
        """Add administrative command documentation"""
        
        self.documentation["block"] = CommandDocumentation(
            name="block",
            category=HelpCategory.ADMIN,
            description="Block an email address from sending messages",
            usage="block/email@addr.com",
            syntax="block/email_address",
            parameters=[
                "email_address - Email address to block"
            ],
            examples=[
                "block/spam@example.com - Block email address"
            ],
            permissions=[CommandPermission.ADMIN],
            related_commands=["unblock"]
        )
        
        self.documentation["unblock"] = CommandDocumentation(
            name="unblock",
            category=HelpCategory.ADMIN,
            description="Unblock a previously blocked email address",
            usage="unblock/email@addr.com",
            syntax="unblock/email_address",
            parameters=[
                "email_address - Email address to unblock"
            ],
            examples=[
                "unblock/user@example.com - Unblock email address"
            ],
            permissions=[CommandPermission.ADMIN],
            related_commands=["block"]
        )
    
    def _add_asset_commands(self):
        """Add asset management command documentation"""
        
        self.documentation["checkin"] = CommandDocumentation(
            name="checkin",
            category=HelpCategory.UTILITY,
            description="Check in to the accountability system",
            usage="checkin [notes]",
            syntax="checkin [optional_notes]",
            parameters=[
                "notes (optional) - Additional check-in information"
            ],
            examples=[
                "checkin - Simple check-in",
                "checkin Arrived at staging area - Check-in with notes"
            ],
            related_commands=["checkout", "checklist"]
        )
        
        self.documentation["checkout"] = CommandDocumentation(
            name="checkout",
            category=HelpCategory.UTILITY,
            description="Check out of the accountability system",
            usage="checkout [notes]",
            syntax="checkout [optional_notes]",
            parameters=[
                "notes (optional) - Additional check-out information"
            ],
            examples=[
                "checkout - Simple check-out",
                "checkout Departing for home - Check-out with notes"
            ],
            related_commands=["checkin", "checklist"]
        )
        
        self.documentation["checklist"] = CommandDocumentation(
            name="checklist",
            category=HelpCategory.UTILITY,
            description="View current check-in status",
            usage="checklist",
            syntax="checklist",
            examples=[
                "checklist - Show who is currently checked in"
            ],
            related_commands=["checkin", "checkout"]
        )
    
    def get_command_help(self, command: str, detailed: bool = True) -> Optional[str]:
        """Get help for a specific command"""
        command = command.lower()
        
        if command not in self.documentation:
            return None
        
        doc = self.documentation[command]
        
        if detailed:
            help_text = f"📋 **{doc.name.upper()}**\n"
            help_text += f"{doc.description}\n\n"
            
            help_text += f"**Usage:** `{doc.usage}`\n"
            
            if doc.syntax != doc.usage:
                help_text += f"**Syntax:** `{doc.syntax}`\n"
            
            if doc.parameters:
                help_text += f"**Parameters:**\n"
                for param in doc.parameters:
                    help_text += f"  • {param}\n"
            
            if doc.aliases:
                help_text += f"**Aliases:** {', '.join(doc.aliases)}\n"
            
            help_text += f"**Category:** {doc.category.value.title()}\n"
            
            if doc.permissions != [CommandPermission.PUBLIC]:
                perm_names = [p.value for p in doc.permissions]
                help_text += f"**Permissions:** {', '.join(perm_names)}\n"
            
            if doc.deprecated:
                help_text += f"⚠️ **DEPRECATED**"
                if doc.replacement:
                    help_text += f" - Use `{doc.replacement}` instead"
                help_text += "\n"
            
            if doc.examples:
                help_text += f"\n**Examples:**\n"
                for example in doc.examples:
                    help_text += f"  `{example}`\n"
            
            if doc.notes:
                help_text += f"\n**Notes:**\n"
                for note in doc.notes:
                    help_text += f"  • {note}\n"
            
            if doc.related_commands:
                help_text += f"\n**Related:** {', '.join(doc.related_commands)}\n"
            
            return help_text.strip()
        else:
            return f"**{doc.name}**: {doc.description}"
    
    def get_category_help(self, category: str) -> str:
        """Get help for all commands in a category"""
        try:
            cat_enum = HelpCategory(category.lower())
        except ValueError:
            return f"Unknown category: {category}"
        
        commands = [doc for doc in self.documentation.values() if doc.category == cat_enum]
        
        if not commands:
            return f"No commands found in category: {category}"
        
        help_text = f"📚 **{category.title()} Commands**\n\n"
        
        for doc in sorted(commands, key=lambda x: x.name):
            help_text += f"**{doc.name}** - {doc.description}\n"
            if doc.deprecated:
                help_text += "  ⚠️ DEPRECATED\n"
        
        help_text += f"\n💡 Send `help <command>` for detailed information."
        
        return help_text
    
    def get_all_categories(self) -> List[str]:
        """Get list of all available categories"""
        categories = set()
        for doc in self.documentation.values():
            categories.add(doc.category.value)
        return sorted(list(categories))
    
    def get_categories_help(self) -> str:
        """Get help text for all categories"""
        categories = {}
        for name, doc in self.documentation.items():
            if doc.category not in categories:
                categories[doc.category] = []
            categories[doc.category].append(name)
        
        help_text = "📚 **Command Categories**\n\n"
        
        # Sort by category name (string value)
        sorted_categories = sorted(categories.items(), key=lambda x: x[0].value)
        
        for category, commands in sorted_categories:
            help_text += f"**{category.value.title()}** ({len(commands)} commands)\n"
            help_text += f"  Send `help {category.value}` to see commands in this category\n\n"
        
        return help_text.strip()
    
    def search_commands(self, query: str) -> List[str]:
        """Search for commands matching a query"""
        query = query.lower()
        matches = []
        
        for name, doc in self.documentation.items():
            if (query in name.lower() or 
                query in doc.description.lower() or
                any(query in alias.lower() for alias in doc.aliases)):
                matches.append(name)
        
        return sorted(matches)