"""
Comprehensive Command Parser

Handles parsing of all command formats specified in Requirement 14:
- Basic commands (help, ping, etc.)
- Commands with parameters (name/YourName, phone/1/number)
- Commands with complex syntax (email/to/subject/body)
- Special format commands (wiki:, ask:, etc.)
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    """Types of command formats"""
    SIMPLE = "simple"           # help, ping, status
    PARAMETER = "parameter"     # name/John, phone/1/555-1234
    COMPLEX = "complex"         # email/to/subject/body
    PREFIXED = "prefixed"       # wiki:search term, ask:question
    TOGGLE = "toggle"           # alerts on/off, weather on/off
    NUMERIC = "numeric"         # bbsread #123, bbsdelete #456
    SPECIAL = "special"         # Custom parsing required


@dataclass
class ParsedCommand:
    """Result of command parsing"""
    original_text: str
    command: str
    command_type: CommandType
    parameters: List[str]
    named_parameters: Dict[str, str]
    flags: List[str]
    raw_args: str
    is_valid: bool
    error_message: Optional[str] = None


class CommandParser:
    """
    Comprehensive command parser that handles all command formats
    """
    
    def __init__(self):
        # Command patterns for different types
        self.patterns = {
            # Simple commands: help, ping, status, etc.
            CommandType.SIMPLE: re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*)\s*$'),
            
            # Parameter commands: name/John, phone/1/555-1234
            CommandType.PARAMETER: re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*)/(.+)$'),
            
            # Complex commands: email/to/subject/body
            CommandType.COMPLEX: re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*)/([^/]+)/([^/]+)/(.+)$'),
            
            # Prefixed commands: wiki:search, ask:question
            CommandType.PREFIXED: re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*):(.+)$'),
            
            # Toggle commands: alerts on/off
            CommandType.TOGGLE: re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*)\s+(on|off)$'),
            
            # Numeric commands: bbsread #123
            CommandType.NUMERIC: re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*)\s+#?(\d+)$'),
        }
        
        # Special command mappings
        self.special_commands = {
            'help': self._parse_help_command,
            'bbspost': self._parse_bbs_post,
            'tagsend': self._parse_tag_send,
            'email': self._parse_email_command,
            'sms': self._parse_sms_command,
            'q': self._parse_quiz_command,
            's': self._parse_survey_command,
        }
        
        # Command aliases
        self.aliases = {
            '?': 'help',
            'cmd': 'help',
            'wx': 'weather',
            'wxc': 'weather_current',
            'wxa': 'weather_alerts',
            'mwx': 'weather_marine',
            'cq': 'ping',
            'pong': 'ping',
            # Note: 'ack' is NOT aliased to 'ping' - it's a separate emergency response command
        }
        
        # Commands that require special handling
        self.complex_commands = {
            'email': ['to', 'subject', 'body'],
            'tagsend': ['tags', 'message'],
            'name': ['value'],
            'phone': ['type', 'number'],
            'address': ['value'],
        }
    
    def parse(self, text: str) -> ParsedCommand:
        """
        Parse command text into structured command object
        
        Args:
            text: Raw command text
            
        Returns:
            ParsedCommand object with parsed components
        """
        text = text.strip()
        
        if not text:
            return ParsedCommand(
                original_text=text,
                command="",
                command_type=CommandType.SIMPLE,
                parameters=[],
                named_parameters={},
                flags=[],
                raw_args="",
                is_valid=False,
                error_message="Empty command"
            )
        
        # Remove command prefixes if present
        if text.startswith(('/', '!')):
            text = text[1:]
        
        # Check for aliases
        first_word = text.split()[0].lower() if text.split() else ""
        if first_word in self.aliases:
            text = text.replace(first_word, self.aliases[first_word], 1)
        
        # Try special command parsers first (but be careful about partial matches)
        for cmd, parser in self.special_commands.items():
            # Ensure we match the full command, not just a prefix
            if text.lower() == cmd.lower() or text.lower().startswith(cmd.lower() + ' ') or text.lower().startswith(cmd.lower() + '/') or text.lower().startswith(cmd.lower() + ':'):
                return parser(text)
        
        # Try pattern matching
        for cmd_type, pattern in self.patterns.items():
            match = pattern.match(text)
            if match:
                return self._parse_by_type(text, cmd_type, match)
        
        # Fallback: treat as simple command with arguments
        parts = text.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        return ParsedCommand(
            original_text=text,
            command=command,
            command_type=CommandType.SIMPLE,
            parameters=args,
            named_parameters={},
            flags=[],
            raw_args=' '.join(args),
            is_valid=True
        )
    
    def _parse_by_type(self, text: str, cmd_type: CommandType, match: re.Match) -> ParsedCommand:
        """Parse command based on its type"""
        groups = match.groups()
        command = groups[0].lower()
        
        if cmd_type == CommandType.SIMPLE:
            return ParsedCommand(
                original_text=text,
                command=command,
                command_type=cmd_type,
                parameters=[],
                named_parameters={},
                flags=[],
                raw_args="",
                is_valid=True
            )
        
        elif cmd_type == CommandType.PARAMETER:
            parameter = groups[1]
            return ParsedCommand(
                original_text=text,
                command=command,
                command_type=cmd_type,
                parameters=[parameter],
                named_parameters={'value': parameter},
                flags=[],
                raw_args=parameter,
                is_valid=True
            )
        
        elif cmd_type == CommandType.COMPLEX:
            params = list(groups[1:])
            named_params = {}
            
            # Map parameters based on command type
            if command in self.complex_commands:
                param_names = self.complex_commands[command]
                for i, param_name in enumerate(param_names):
                    if i < len(params):
                        named_params[param_name] = params[i]
            
            return ParsedCommand(
                original_text=text,
                command=command,
                command_type=cmd_type,
                parameters=params,
                named_parameters=named_params,
                flags=[],
                raw_args='/'.join(params),
                is_valid=True
            )
        
        elif cmd_type == CommandType.PREFIXED:
            query = groups[1].strip()
            return ParsedCommand(
                original_text=text,
                command=command,
                command_type=cmd_type,
                parameters=[query],
                named_parameters={'query': query},
                flags=[],
                raw_args=query,
                is_valid=True
            )
        
        elif cmd_type == CommandType.TOGGLE:
            state = groups[1].lower()
            return ParsedCommand(
                original_text=text,
                command=command,
                command_type=cmd_type,
                parameters=[state],
                named_parameters={'state': state},
                flags=[state],
                raw_args=state,
                is_valid=True
            )
        
        elif cmd_type == CommandType.NUMERIC:
            number = groups[1]
            return ParsedCommand(
                original_text=text,
                command=command,
                command_type=cmd_type,
                parameters=[number],
                named_parameters={'id': number},
                flags=[],
                raw_args=number,
                is_valid=True
            )
        
        return ParsedCommand(
            original_text=text,
            command=command,
            command_type=CommandType.SIMPLE,
            parameters=[],
            named_parameters={},
            flags=[],
            raw_args="",
            is_valid=False,
            error_message="Unknown command format"
        )
    
    def _parse_help_command(self, text: str) -> ParsedCommand:
        """Parse help command with optional topic"""
        parts = text.split(None, 1)
        command = parts[0].lower()
        
        if len(parts) > 1:
            topic = parts[1].strip()
            return ParsedCommand(
                original_text=text,
                command=command,
                command_type=CommandType.PARAMETER,
                parameters=[topic],
                named_parameters={'topic': topic},
                flags=[],
                raw_args=topic,
                is_valid=True
            )
        else:
            return ParsedCommand(
                original_text=text,
                command=command,
                command_type=CommandType.SIMPLE,
                parameters=[],
                named_parameters={},
                flags=[],
                raw_args="",
                is_valid=True
            )
    
    def _parse_bbs_post(self, text: str) -> ParsedCommand:
        """Parse BBS post command"""
        # bbspost can be interactive or with subject/content
        parts = text.split(None, 1)
        command = parts[0].lower()
        
        if len(parts) > 1:
            # Try to parse subject/content
            content = parts[1]
            if '/' in content:
                subject_content = content.split('/', 1)
                if len(subject_content) == 2:
                    subject, body = subject_content
                    return ParsedCommand(
                        original_text=text,
                        command=command,
                        command_type=CommandType.COMPLEX,
                        parameters=[subject, body],
                        named_parameters={'subject': subject, 'content': body},
                        flags=[],
                        raw_args=content,
                        is_valid=True
                    )
            
            # Single parameter (subject only)
            return ParsedCommand(
                original_text=text,
                command=command,
                command_type=CommandType.PARAMETER,
                parameters=[content],
                named_parameters={'subject': content},
                flags=[],
                raw_args=content,
                is_valid=True
            )
        else:
            # Interactive mode
            return ParsedCommand(
                original_text=text,
                command=command,
                command_type=CommandType.SIMPLE,
                parameters=[],
                named_parameters={},
                flags=['interactive'],
                raw_args="",
                is_valid=True
            )
    
    def _parse_tag_send(self, text: str) -> ParsedCommand:
        """Parse tagsend command: tagsend/tags/message or tagsend tags message"""
        # Try slash format first
        match = re.match(r'^tagsend/([^/]+)/(.+)$', text, re.IGNORECASE)
        if match:
            tags, message = match.groups()
            return ParsedCommand(
                original_text=text,
                command='tagsend',
                command_type=CommandType.COMPLEX,
                parameters=[tags, message],
                named_parameters={'tags': tags, 'message': message},
                flags=[],
                raw_args=f"{tags}/{message}",
                is_valid=True
            )
        
        # Try space-separated format
        parts = text.split(None, 2)  # Split into at most 3 parts: command, tags, message
        if len(parts) >= 3:
            command, tags, message = parts[0], parts[1], parts[2]
            return ParsedCommand(
                original_text=text,
                command='tagsend',
                command_type=CommandType.COMPLEX,
                parameters=[tags, message],
                named_parameters={'tags': tags, 'message': message},
                flags=[],
                raw_args=f"{tags} {message}",
                is_valid=True
            )
        
        return ParsedCommand(
            original_text=text,
            command='tagsend',
            command_type=CommandType.SPECIAL,
            parameters=[],
            named_parameters={},
            flags=[],
            raw_args="",
            is_valid=False,
            error_message="Invalid tagsend format. Use: tagsend/tags/message or tagsend tags message"
        )
    
    def _parse_sms_command(self, text: str) -> ParsedCommand:
        """Parse SMS command"""
        if text.lower().startswith('sms:'):
            content = text[4:].strip()
            return ParsedCommand(
                original_text=text,
                command='sms',
                command_type=CommandType.PREFIXED,
                parameters=[content],
                named_parameters={'message': content},
                flags=[],
                raw_args=content,
                is_valid=True
            )
        
        # Handle regular SMS command with space-separated arguments
        parts = text.split(None, 1)
        command = parts[0].lower()
        
        if len(parts) > 1:
            message = parts[1]
            return ParsedCommand(
                original_text=text,
                command='sms',
                command_type=CommandType.PARAMETER,
                parameters=[message],
                named_parameters={'message': message},
                flags=[],
                raw_args=message,
                is_valid=True
            )
        
        return ParsedCommand(
            original_text=text,
            command='sms',
            command_type=CommandType.SIMPLE,
            parameters=[],
            named_parameters={},
            flags=[],
            raw_args="",
            is_valid=True
        )
    
    def _parse_quiz_command(self, text: str) -> ParsedCommand:
        """Parse quiz command: q:answer or quiz"""
        if text.lower().startswith('q:'):
            answer = text[2:].strip()
            return ParsedCommand(
                original_text=text,
                command='quiz_answer',
                command_type=CommandType.PREFIXED,
                parameters=[answer],
                named_parameters={'answer': answer},
                flags=[],
                raw_args=answer,
                is_valid=True
            )
        
        return ParsedCommand(
            original_text=text,
            command='quiz',
            command_type=CommandType.SIMPLE,
            parameters=[],
            named_parameters={},
            flags=[],
            raw_args="",
            is_valid=True
        )
    
    def _parse_survey_command(self, text: str) -> ParsedCommand:
        """Parse survey command: s:answer or survey"""
        if text.lower().startswith('s:'):
            answer = text[2:].strip()
            return ParsedCommand(
                original_text=text,
                command='survey_answer',
                command_type=CommandType.PREFIXED,
                parameters=[answer],
                named_parameters={'answer': answer},
                flags=[],
                raw_args=answer,
                is_valid=True
            )
        
        return ParsedCommand(
            original_text=text,
            command='survey',
            command_type=CommandType.SIMPLE,
            parameters=[],
            named_parameters={},
            flags=[],
            raw_args="",
            is_valid=True
        )
    
    def _parse_email_command(self, text: str) -> ParsedCommand:
        """Parse email command: email/to/subject/body"""
        # Check if it's in the complex format
        match = re.match(r'^email/([^/]+)/([^/]+)/(.+)$', text, re.IGNORECASE)
        if match:
            to, subject, body = match.groups()
            return ParsedCommand(
                original_text=text,
                command='email',
                command_type=CommandType.COMPLEX,
                parameters=[to, subject, body],
                named_parameters={'to': to, 'subject': subject, 'body': body},
                flags=[],
                raw_args=f"{to}/{subject}/{body}",
                is_valid=True
            )
        
        # Fallback to simple parsing
        parts = text.split(None, 1)
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        return ParsedCommand(
            original_text=text,
            command=command,
            command_type=CommandType.SIMPLE,
            parameters=args,
            named_parameters={},
            flags=[],
            raw_args=' '.join(args),
            is_valid=True
        )
    
    def validate_command_syntax(self, parsed_command: ParsedCommand, 
                              expected_params: Optional[List[str]] = None) -> bool:
        """
        Validate that a parsed command has the expected parameters
        
        Args:
            parsed_command: The parsed command to validate
            expected_params: List of expected parameter names
            
        Returns:
            True if command syntax is valid
        """
        if not parsed_command.is_valid:
            return False
        
        if expected_params is None:
            return True
        
        # Check that all required parameters are present
        for param in expected_params:
            if param not in parsed_command.named_parameters:
                return False
        
        return True
    
    def get_command_suggestions(self, partial_command: str, 
                              available_commands: List[str]) -> List[str]:
        """
        Get command suggestions for partial input
        
        Args:
            partial_command: Partial command text
            available_commands: List of available commands
            
        Returns:
            List of suggested commands
        """
        partial = partial_command.lower().strip()
        if not partial:
            return []
        
        suggestions = []
        
        # Exact matches first
        for cmd in available_commands:
            if cmd.lower() == partial:
                suggestions.append(cmd)
        
        # Prefix matches
        for cmd in available_commands:
            if cmd.lower().startswith(partial) and cmd not in suggestions:
                suggestions.append(cmd)
        
        # Fuzzy matches (contains)
        for cmd in available_commands:
            if partial in cmd.lower() and cmd not in suggestions:
                suggestions.append(cmd)
        
        return suggestions[:10]  # Limit to 10 suggestions