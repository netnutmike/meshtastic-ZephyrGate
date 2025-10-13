"""
Tests for interactive bot service games integration

Tests that the interactive bot service properly integrates with the games framework.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime

from src.services.bot.interactive_bot_service import InteractiveBotService
from src.models.message import Message, MessageType, MessagePriority


class TestInteractiveBotGamesIntegration:
    """Test games integration with interactive bot service"""
    
    @pytest.fixture
    def bot_service(self):
        """Create an interactive bot service for testing"""
        config = {
            'auto_response': {'enabled': False},  # Disable auto-response for cleaner testing
            'commands': {'enabled': True}
        }
        service = InteractiveBotService(config)
        return service
    
    @pytest.fixture
    def sample_message(self):
        """Create a sample message for testing"""
        return Message(
            sender_id="test_user",
            recipient_id=None,
            channel=0,
            content="test",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            timestamp=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_games_initialization(self, bot_service):
        """Test that games are properly initialized"""
        await bot_service.start()
        
        # Check that games are registered
        available_games = bot_service.game_manager.get_available_games()
        
        expected_games = [
            'tictactoe', 'hangman', 'blackjack', 'videopoker',
            'dopewars', 'lemonstand', 'golfsim', 'mastermind'
        ]
        
        for game in expected_games:
            assert game in available_games
        
        await bot_service.stop()
    
    @pytest.mark.asyncio
    async def test_games_command(self, bot_service, sample_message):
        """Test the 'games' command"""
        await bot_service.start()
        
        sample_message.content = "games"
        response = await bot_service.handle_message(sample_message)
        
        assert response is not None
        assert "Available Games" in response.content
        assert "Tictactoe" in response.content or "tictactoe" in response.content
        assert "Blackjack" in response.content or "blackjack" in response.content
        
        await bot_service.stop()
    
    @pytest.mark.asyncio
    async def test_start_tictactoe_game(self, bot_service, sample_message):
        """Test starting a Tic-Tac-Toe game"""
        await bot_service.start()
        
        sample_message.content = "tictactoe"
        response = await bot_service.handle_message(sample_message)
        
        assert response is not None
        assert "Tic-Tac-Toe Game Started" in response.content
        assert "You are X" in response.content
        
        # Check that user has active game
        assert bot_service.game_manager.has_active_game("test_user")
        
        await bot_service.stop()
    
    @pytest.mark.asyncio
    async def test_game_input_processing(self, bot_service, sample_message):
        """Test processing game input"""
        await bot_service.start()
        
        # Start game
        sample_message.content = "tictactoe"
        await bot_service.handle_message(sample_message)
        
        # Make a move
        sample_message.content = "1,1"
        response = await bot_service.handle_message(sample_message)
        
        assert response is not None
        assert ("AI played" in response.content or 
                "Your turn" in response.content or 
                "won" in response.content)
        
        await bot_service.stop()
    
    @pytest.mark.asyncio
    async def test_quit_game(self, bot_service, sample_message):
        """Test quitting a game"""
        await bot_service.start()
        
        # Start game
        sample_message.content = "tictactoe"
        await bot_service.handle_message(sample_message)
        
        assert bot_service.game_manager.has_active_game("test_user")
        
        # Quit game
        sample_message.content = "quit"
        response = await bot_service.handle_message(sample_message)
        
        assert response is not None
        assert not bot_service.game_manager.has_active_game("test_user")
        
        await bot_service.stop()
    
    @pytest.mark.asyncio
    async def test_multiple_games_same_user(self, bot_service, sample_message):
        """Test that starting a new game ends the previous one"""
        await bot_service.start()
        
        # Start first game
        sample_message.content = "tictactoe"
        await bot_service.handle_message(sample_message)
        
        assert bot_service.game_manager.has_active_game("test_user")
        session = bot_service.game_manager.get_active_session("test_user")
        assert session.game_type == "tictactoe"
        
        # Start second game (should replace first)
        sample_message.content = "hangman"
        await bot_service.handle_message(sample_message)
        
        assert bot_service.game_manager.has_active_game("test_user")
        session = bot_service.game_manager.get_active_session("test_user")
        assert session.game_type == "hangman"
        
        await bot_service.stop()
    
    @pytest.mark.asyncio
    async def test_game_help_integration(self, bot_service, sample_message):
        """Test that game help works through the bot service"""
        await bot_service.start()
        
        # Start game
        sample_message.content = "tictactoe"
        await bot_service.handle_message(sample_message)
        
        # Get help
        sample_message.content = "help"
        response = await bot_service.handle_message(sample_message)
        
        assert response is not None
        assert "rules" in response.content.lower() or "help" in response.content.lower()
        
        await bot_service.stop()
    
    @pytest.mark.asyncio
    async def test_invalid_game_command(self, bot_service, sample_message):
        """Test handling invalid game commands"""
        await bot_service.start()
        
        sample_message.content = "nonexistentgame"
        response = await bot_service.handle_message(sample_message)
        
        # Should either be handled by comprehensive command handler or return None
        # (meaning no response, which is fine for unknown commands)
        if response:
            # If there is a response, it should indicate the command wasn't found
            assert ("not implemented" in response.content.lower() or 
                    "unknown" in response.content.lower() or
                    "available" in response.content.lower())
        
        await bot_service.stop()
    
    @pytest.mark.asyncio
    async def test_game_stats(self, bot_service):
        """Test getting game statistics"""
        await bot_service.start()
        
        stats = await bot_service.get_game_stats()
        
        assert isinstance(stats, dict)
        assert 'total_games' in stats
        assert 'active_sessions' in stats
        assert stats['total_games'] == 8  # Number of implemented games
        
        await bot_service.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_users_different_games(self, bot_service):
        """Test multiple users playing different games simultaneously"""
        await bot_service.start()
        
        # User 1 starts Tic-Tac-Toe
        response1 = await bot_service.handle_game_command("tictactoe", "user1", "User1")
        assert "Tic-Tac-Toe Game Started" in response1
        
        # User 2 starts Hangman
        response2 = await bot_service.handle_game_command("hangman", "user2", "User2")
        assert "Hangman Game Started" in response2
        
        # Both should have active games
        assert bot_service.game_manager.has_active_game("user1")
        assert bot_service.game_manager.has_active_game("user2")
        
        # Games should be different
        session1 = bot_service.game_manager.get_active_session("user1")
        session2 = bot_service.game_manager.get_active_session("user2")
        
        assert session1.game_type == "tictactoe"
        assert session2.game_type == "hangman"
        
        await bot_service.stop()