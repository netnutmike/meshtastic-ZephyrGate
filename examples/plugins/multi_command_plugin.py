"""
Multi-Command Plugin - Example of multiple command handlers

This plugin demonstrates:
- Registering multiple commands with different priorities
- Command argument parsing and validation
- Context usage in command handlers
- Help text and usage information
- Command aliases and variations
- Error handling in commands

The plugin provides a suite of utility commands that showcase
various command handling patterns.
"""

from typing import Dict, Any, List
from datetime import datetime
from src.core.enhanced_plugin import EnhancedPlugin


class MultiCommandPlugin(EnhancedPlugin):
    """
    Multi-command plugin demonstrating various command patterns.
    
    Features:
    - Multiple command handlers
    - Different priority levels
    - Argument parsing
    - Context access
    - Help system
    """
    
    async def initialize(self) -> bool:
        """Initialize the plugin and register commands"""
        self.logger.info("Initializing Multi-Command Plugin")
        
        # Register commands with different priorities
        
        # High priority command (executes first if multiple plugins handle same command)
        self.register_command(
            "echo",
            self.handle_echo_command,
            "Echo back the provided message",
            priority=50
        )
        
        # Normal priority commands
        self.register_command(
            "time",
            self.handle_time_command,
            "Show current time",
            priority=100
        )
        
        self.register_command(
            "calc",
            self.handle_calc_command,
            "Simple calculator (add, sub, mul, div)",
            priority=100
        )
        
        self.register_command(
            "reverse",
            self.handle_reverse_command,
            "Reverse a string",
            priority=100
        )
        
        self.register_command(
            "count",
            self.handle_count_command,
            "Count words or characters in text",
            priority=100
        )
        
        self.register_command(
            "info",
            self.handle_info_command,
            "Show information about the sender",
            priority=100
        )
        
        self.register_command(
            "help",
            self.handle_help_command,
            "Show help for multi-command plugin",
            priority=100
        )
        
        # Low priority command (executes last)
        self.register_command(
            "fallback",
            self.handle_fallback_command,
            "Fallback handler for testing",
            priority=200
        )
        
        # Initialize command usage tracking
        await self.store_data("command_usage", {})
        
        return True
    
    async def handle_echo_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'echo' command.
        
        Usage: echo <message>
        """
        if not args:
            return "Usage: echo <message>"
        
        message = " ".join(args)
        
        # Track usage
        await self._track_command_usage("echo")
        
        return f"Echo: {message}"
    
    async def handle_time_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'time' command.
        
        Usage: time [format]
        Formats: utc, local, unix
        """
        time_format = args[0].lower() if args else "utc"
        
        now = datetime.utcnow()
        
        if time_format == "utc":
            result = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        elif time_format == "local":
            result = now.strftime("%Y-%m-%d %H:%M:%S")
        elif time_format == "unix":
            result = str(int(now.timestamp()))
        else:
            return "Invalid format. Use: utc, local, or unix"
        
        # Track usage
        await self._track_command_usage("time")
        
        return f"Current time ({time_format}): {result}"
    
    async def handle_calc_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'calc' command for simple calculations.
        
        Usage: calc <operation> <num1> <num2>
        Operations: add, sub, mul, div
        """
        if len(args) < 3:
            return "Usage: calc <operation> <num1> <num2>\nOperations: add, sub, mul, div"
        
        operation = args[0].lower()
        
        try:
            num1 = float(args[1])
            num2 = float(args[2])
        except ValueError:
            return "Error: Invalid numbers provided"
        
        # Perform calculation
        if operation == "add":
            result = num1 + num2
        elif operation == "sub":
            result = num1 - num2
        elif operation == "mul":
            result = num1 * num2
        elif operation == "div":
            if num2 == 0:
                return "Error: Division by zero"
            result = num1 / num2
        else:
            return "Invalid operation. Use: add, sub, mul, or div"
        
        # Track usage
        await self._track_command_usage("calc")
        
        return f"{num1} {operation} {num2} = {result}"
    
    async def handle_reverse_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'reverse' command to reverse a string.
        
        Usage: reverse <text>
        """
        if not args:
            return "Usage: reverse <text>"
        
        text = " ".join(args)
        reversed_text = text[::-1]
        
        # Track usage
        await self._track_command_usage("reverse")
        
        return f"Reversed: {reversed_text}"
    
    async def handle_count_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'count' command to count words or characters.
        
        Usage: count <words|chars> <text>
        """
        if len(args) < 2:
            return "Usage: count <words|chars> <text>"
        
        count_type = args[0].lower()
        text = " ".join(args[1:])
        
        if count_type == "words":
            count = len(text.split())
            result = f"Word count: {count}"
        elif count_type == "chars":
            count = len(text)
            result = f"Character count: {count}"
        else:
            return "Invalid type. Use: words or chars"
        
        # Track usage
        await self._track_command_usage("count")
        
        return result
    
    async def handle_info_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'info' command to show sender information.
        
        Usage: info
        """
        sender_id = context.get('sender_id', 'unknown')
        channel = context.get('channel', 'unknown')
        timestamp = context.get('timestamp', datetime.utcnow())
        
        # Format timestamp
        if isinstance(timestamp, datetime):
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = str(timestamp)
        
        # Build info response
        info_lines = [
            "Message Context Information:",
            "=" * 40,
            f"Sender ID: {sender_id}",
            f"Channel: {channel}",
            f"Timestamp: {time_str}",
        ]
        
        # Add additional context if available
        if 'is_dm' in context:
            info_lines.append(f"Direct Message: {context['is_dm']}")
        
        # Track usage
        await self._track_command_usage("info")
        
        return "\n".join(info_lines)
    
    async def handle_help_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'help' command to show available commands.
        
        Usage: help [command]
        """
        if args:
            # Show help for specific command
            command = args[0].lower()
            return self._get_command_help(command)
        
        # Show all commands
        help_lines = [
            "Multi-Command Plugin - Available Commands:",
            "=" * 50,
            "",
            "echo <message>           - Echo back a message",
            "time [format]            - Show current time",
            "calc <op> <n1> <n2>      - Simple calculator",
            "reverse <text>           - Reverse a string",
            "count <type> <text>      - Count words or characters",
            "info                     - Show message context info",
            "help [command]           - Show this help",
            "",
            "Use 'help <command>' for detailed help on a specific command.",
        ]
        
        # Track usage
        await self._track_command_usage("help")
        
        return "\n".join(help_lines)
    
    async def handle_fallback_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'fallback' command (low priority).
        
        This demonstrates a low-priority handler that only executes
        if no higher-priority handler processes the command.
        
        Usage: fallback
        """
        # Track usage
        await self._track_command_usage("fallback")
        
        return "Fallback handler executed (low priority)"
    
    def _get_command_help(self, command: str) -> str:
        """Get detailed help for a specific command"""
        help_text = {
            'echo': "echo <message>\n\nEcho back the provided message.\n\nExample: echo Hello World",
            'time': "time [format]\n\nShow current time in specified format.\n\nFormats: utc, local, unix\nExample: time utc",
            'calc': "calc <operation> <num1> <num2>\n\nPerform simple calculations.\n\nOperations: add, sub, mul, div\nExample: calc add 5 3",
            'reverse': "reverse <text>\n\nReverse the provided text.\n\nExample: reverse Hello",
            'count': "count <type> <text>\n\nCount words or characters in text.\n\nTypes: words, chars\nExample: count words Hello World",
            'info': "info\n\nShow information about the message context.\n\nExample: info",
            'help': "help [command]\n\nShow help information.\n\nExample: help calc",
            'fallback': "fallback\n\nLow-priority fallback handler for testing.\n\nExample: fallback"
        }
        
        if command in help_text:
            return help_text[command]
        else:
            return f"No help available for command: {command}"
    
    async def _track_command_usage(self, command: str):
        """Track command usage statistics"""
        try:
            usage = await self.retrieve_data("command_usage", {})
            
            if command not in usage:
                usage[command] = 0
            
            usage[command] += 1
            
            await self.store_data("command_usage", usage)
            
        except Exception as e:
            self.logger.error(f"Error tracking command usage: {e}")


# Example configuration for this plugin (in config.yaml):
"""
plugins:
  multi_command:
    enabled: true
"""
