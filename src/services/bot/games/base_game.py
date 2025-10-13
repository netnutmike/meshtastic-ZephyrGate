"""
Base Game Framework

Provides base classes for implementing interactive games in the mesh network.
Handles game session management, state persistence, and common game mechanics.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import json


class GameState(Enum):
    """Game session states"""
    WAITING = "waiting"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class GameSession:
    """Represents an active game session"""
    session_id: str
    game_type: str
    player_id: str
    player_name: str
    state: GameState
    game_data: Dict[str, Any]
    created_at: datetime
    last_activity: datetime
    timeout_minutes: int = 30
    
    def is_expired(self) -> bool:
        """Check if session has expired due to inactivity"""
        if self.timeout_minutes <= 0:
            return False
        timeout = timedelta(minutes=self.timeout_minutes)
        return datetime.utcnow() - self.last_activity > timeout
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for storage"""
        return {
            'session_id': self.session_id,
            'game_type': self.game_type,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'state': self.state.value,
            'game_data': self.game_data,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'timeout_minutes': self.timeout_minutes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameSession':
        """Create session from dictionary"""
        return cls(
            session_id=data['session_id'],
            game_type=data['game_type'],
            player_id=data['player_id'],
            player_name=data['player_name'],
            state=GameState(data['state']),
            game_data=data['game_data'],
            created_at=datetime.fromisoformat(data['created_at']),
            last_activity=datetime.fromisoformat(data['last_activity']),
            timeout_minutes=data.get('timeout_minutes', 30)
        )


class BaseGame(ABC):
    """
    Abstract base class for all interactive games
    
    Provides common functionality for game session management,
    input validation, and response formatting.
    """
    
    def __init__(self, game_type: str, timeout_minutes: int = 30):
        self.game_type = game_type
        self.timeout_minutes = timeout_minutes
        self.logger = logging.getLogger(f"{__name__}.{game_type}")
        
        # Game configuration
        self.max_concurrent_sessions = 100
        self.allow_spectators = False
        self.save_high_scores = True
        
    @abstractmethod
    async def start_game(self, player_id: str, player_name: str, args: List[str] = None) -> Tuple[str, GameSession]:
        """
        Start a new game session
        
        Args:
            player_id: Unique identifier for the player
            player_name: Display name for the player
            args: Optional game-specific arguments
            
        Returns:
            Tuple of (welcome_message, game_session)
        """
        pass
    
    @abstractmethod
    async def process_input(self, session: GameSession, user_input: str) -> Tuple[str, bool]:
        """
        Process player input for an active game
        
        Args:
            session: Current game session
            user_input: Player's input/move
            
        Returns:
            Tuple of (response_message, game_continues)
        """
        pass
    
    @abstractmethod
    async def get_game_status(self, session: GameSession) -> str:
        """
        Get current game status/board display
        
        Args:
            session: Current game session
            
        Returns:
            Formatted status message
        """
        pass
    
    async def end_game(self, session: GameSession, reason: str = "completed") -> str:
        """
        End a game session
        
        Args:
            session: Game session to end
            reason: Reason for ending (completed, abandoned, timeout)
            
        Returns:
            Final message to player
        """
        if reason == "completed":
            session.state = GameState.COMPLETED
        elif reason == "abandoned":
            session.state = GameState.ABANDONED
        else:
            session.state = GameState.COMPLETED
        
        # Save high score if applicable
        if self.save_high_scores and reason == "completed":
            await self._save_high_score(session)
        
        return await self._get_end_game_message(session, reason)
    
    async def pause_game(self, session: GameSession) -> str:
        """Pause an active game"""
        session.state = GameState.PAUSED
        return f"🎮 Game paused. Send 'resume' to continue or 'quit' to end the game."
    
    async def resume_game(self, session: GameSession) -> str:
        """Resume a paused game"""
        session.state = GameState.ACTIVE
        session.update_activity()
        status = await self.get_game_status(session)
        return f"🎮 Game resumed!\n\n{status}"
    
    async def get_help(self) -> str:
        """Get help text for this game"""
        return f"🎮 {self.game_type.title()} Game\n\nSend '{self.game_type}' to start a new game."
    
    async def get_rules(self) -> str:
        """Get detailed rules for this game"""
        return f"📋 {self.game_type.title()} Rules\n\nRules not implemented for this game."
    
    def validate_input(self, user_input: str, valid_inputs: List[str] = None) -> bool:
        """
        Validate user input against allowed inputs
        
        Args:
            user_input: Input to validate
            valid_inputs: List of valid inputs (None = any input allowed)
            
        Returns:
            True if input is valid
        """
        if valid_inputs is None:
            return True
        
        return user_input.lower().strip() in [v.lower() for v in valid_inputs]
    
    def format_game_board(self, board: List[List[str]], labels: bool = True) -> str:
        """
        Format a game board for display
        
        Args:
            board: 2D array representing the game board
            labels: Whether to include row/column labels
            
        Returns:
            Formatted board string
        """
        if not board:
            return ""
        
        lines = []
        
        # Add column labels if requested
        if labels and len(board[0]) <= 10:
            col_labels = "   " + " ".join(str(i) for i in range(len(board[0])))
            lines.append(col_labels)
        
        # Add rows with optional row labels
        for i, row in enumerate(board):
            if labels:
                row_str = f"{i} |" + "|".join(f" {cell} " for cell in row) + "|"
            else:
                row_str = "|".join(f" {cell} " for cell in row)
            lines.append(row_str)
        
        return "\n".join(lines)
    
    def generate_session_id(self, player_id: str) -> str:
        """Generate unique session ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"{self.game_type}_{player_id}_{timestamp}"
    
    async def _save_high_score(self, session: GameSession):
        """Save high score (to be implemented by subclasses if needed)"""
        pass
    
    async def _get_end_game_message(self, session: GameSession, reason: str) -> str:
        """Get end game message"""
        if reason == "completed":
            return f"🎮 Game completed! Thanks for playing {self.game_type.title()}!"
        elif reason == "abandoned":
            return f"🎮 Game abandoned. Thanks for playing {self.game_type.title()}!"
        elif reason == "timeout":
            return f"⏰ Game timed out due to inactivity. Thanks for playing {self.game_type.title()}!"
        else:
            return f"🎮 Game ended. Thanks for playing {self.game_type.title()}!"


class GameManager:
    """
    Manages multiple game sessions and provides game discovery
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.games: Dict[str, BaseGame] = {}
        self.active_sessions: Dict[str, GameSession] = {}  # player_id -> session
        self.session_cleanup_task: Optional[asyncio.Task] = None
        
    def register_game(self, game: BaseGame):
        """Register a game implementation"""
        self.games[game.game_type] = game
        self.logger.info(f"Registered game: {game.game_type}")
    
    def unregister_game(self, game_type: str):
        """Unregister a game implementation"""
        if game_type in self.games:
            del self.games[game_type]
            self.logger.info(f"Unregistered game: {game_type}")
    
    def get_available_games(self) -> List[str]:
        """Get list of available game types"""
        return list(self.games.keys())
    
    def get_game(self, game_type: str) -> Optional[BaseGame]:
        """Get game implementation by type"""
        return self.games.get(game_type)
    
    async def start_game(self, game_type: str, player_id: str, player_name: str, args: List[str] = None) -> Optional[str]:
        """
        Start a new game session
        
        Args:
            game_type: Type of game to start
            player_id: Player identifier
            player_name: Player display name
            args: Optional game arguments
            
        Returns:
            Welcome message or None if game not found
        """
        game = self.games.get(game_type)
        if not game:
            return None
        
        # End any existing session for this player
        if player_id in self.active_sessions:
            old_session = self.active_sessions[player_id]
            await game.end_game(old_session, "abandoned")
        
        try:
            welcome_msg, session = await game.start_game(player_id, player_name, args)
            self.active_sessions[player_id] = session
            
            # Start cleanup task if not running
            if self.session_cleanup_task is None or self.session_cleanup_task.done():
                self.session_cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
            
            return welcome_msg
            
        except Exception as e:
            self.logger.error(f"Error starting game {game_type} for {player_id}: {e}")
            return f"❌ Error starting {game_type}. Please try again."
    
    async def process_game_input(self, player_id: str, user_input: str) -> Optional[str]:
        """
        Process input for player's active game
        
        Args:
            player_id: Player identifier
            user_input: Player's input
            
        Returns:
            Game response or None if no active game
        """
        if player_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[player_id]
        game = self.games.get(session.game_type)
        
        if not game:
            # Clean up orphaned session
            del self.active_sessions[player_id]
            return None
        
        # Check for special commands
        input_lower = user_input.lower().strip()
        if input_lower in ['quit', 'exit', 'stop']:
            response = await game.end_game(session, "abandoned")
            del self.active_sessions[player_id]
            return response
        elif input_lower == 'pause' and session.state == GameState.ACTIVE:
            return await game.pause_game(session)
        elif input_lower == 'resume' and session.state == GameState.PAUSED:
            return await game.resume_game(session)
        elif input_lower in ['status', 'board', 'show']:
            return await game.get_game_status(session)
        elif input_lower in ['help', 'rules']:
            return await game.get_rules()
        
        # Process game-specific input
        try:
            session.update_activity()
            response, game_continues = await game.process_input(session, user_input)
            
            if not game_continues:
                # Game ended
                del self.active_sessions[player_id]
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing input for {session.game_type}: {e}")
            return f"❌ Error processing input. Send 'quit' to end the game."
    
    def get_active_session(self, player_id: str) -> Optional[GameSession]:
        """Get active session for player"""
        return self.active_sessions.get(player_id)
    
    def has_active_game(self, player_id: str) -> bool:
        """Check if player has an active game"""
        return player_id in self.active_sessions
    
    async def get_game_list(self) -> str:
        """Get formatted list of available games"""
        if not self.games:
            return "🎮 No games available."
        
        games_list = []
        for game_type, game in self.games.items():
            games_list.append(f"• {game_type.title()}")
        
        return f"🎮 Available Games:\n" + "\n".join(games_list) + f"\n\nSend game name to start playing!"
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        stats = {
            'total_games': len(self.games),
            'active_sessions': len(self.active_sessions),
            'games_by_type': {}
        }
        
        for session in self.active_sessions.values():
            game_type = session.game_type
            if game_type not in stats['games_by_type']:
                stats['games_by_type'][game_type] = 0
            stats['games_by_type'][game_type] += 1
        
        return stats
    
    async def _cleanup_expired_sessions(self):
        """Background task to clean up expired sessions"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                expired_players = []
                for player_id, session in self.active_sessions.items():
                    if session.is_expired():
                        expired_players.append(player_id)
                
                for player_id in expired_players:
                    session = self.active_sessions[player_id]
                    game = self.games.get(session.game_type)
                    if game:
                        await game.end_game(session, "timeout")
                    del self.active_sessions[player_id]
                    self.logger.info(f"Cleaned up expired session for {player_id}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in session cleanup: {e}")