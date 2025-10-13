"""
Tests for the interactive games framework

Tests the base game functionality and specific game implementations.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

from src.services.bot.games.base_game import BaseGame, GameSession, GameState, GameManager
from src.services.bot.games.tictactoe import TicTacToeGame
from src.services.bot.games.hangman import HangmanGame
from src.services.bot.games.blackjack import BlackjackGame


class TestGameManager:
    """Test the game manager functionality"""
    
    @pytest.fixture
    def game_manager(self):
        """Create a game manager for testing"""
        return GameManager()
    
    @pytest.fixture
    def sample_game(self):
        """Create a sample game for testing"""
        return TicTacToeGame()
    
    def test_register_game(self, game_manager, sample_game):
        """Test game registration"""
        game_manager.register_game(sample_game)
        
        assert "tictactoe" in game_manager.games
        assert game_manager.get_game("tictactoe") == sample_game
    
    def test_get_available_games(self, game_manager, sample_game):
        """Test getting available games list"""
        game_manager.register_game(sample_game)
        
        available = game_manager.get_available_games()
        assert "tictactoe" in available
    
    @pytest.mark.asyncio
    async def test_start_game(self, game_manager, sample_game):
        """Test starting a game"""
        game_manager.register_game(sample_game)
        
        response = await game_manager.start_game("tictactoe", "player1", "TestPlayer")
        
        assert response is not None
        assert "Tic-Tac-Toe Game Started" in response
        assert game_manager.has_active_game("player1")
    
    @pytest.mark.asyncio
    async def test_process_game_input(self, game_manager, sample_game):
        """Test processing game input"""
        game_manager.register_game(sample_game)
        
        # Start game
        await game_manager.start_game("tictactoe", "player1", "TestPlayer")
        
        # Make a move
        response = await game_manager.process_game_input("player1", "1,1")
        
        assert response is not None
        assert "AI played" in response or "Invalid" in response or "turn" in response
    
    @pytest.mark.asyncio
    async def test_quit_game(self, game_manager, sample_game):
        """Test quitting a game"""
        game_manager.register_game(sample_game)
        
        # Start game
        await game_manager.start_game("tictactoe", "player1", "TestPlayer")
        assert game_manager.has_active_game("player1")
        
        # Quit game
        response = await game_manager.process_game_input("player1", "quit")
        
        assert response is not None
        assert not game_manager.has_active_game("player1")


class TestTicTacToeGame:
    """Test Tic-Tac-Toe game implementation"""
    
    @pytest.fixture
    def tictactoe_game(self):
        """Create a Tic-Tac-Toe game for testing"""
        return TicTacToeGame()
    
    @pytest.mark.asyncio
    async def test_start_game(self, tictactoe_game):
        """Test starting a Tic-Tac-Toe game"""
        welcome_msg, session = await tictactoe_game.start_game("player1", "TestPlayer")
        
        assert "Tic-Tac-Toe Game Started" in welcome_msg
        assert session.game_type == "tictactoe"
        assert session.player_id == "player1"
        assert session.state == GameState.ACTIVE
        
        # Check initial game state
        game_data = session.game_data
        assert len(game_data['board']) == 3
        assert len(game_data['board'][0]) == 3
        assert game_data['player_symbol'] == 'X'
        assert game_data['ai_symbol'] == 'O'
    
    @pytest.mark.asyncio
    async def test_valid_move(self, tictactoe_game):
        """Test making a valid move"""
        welcome_msg, session = await tictactoe_game.start_game("player1", "TestPlayer")
        
        response, continues = await tictactoe_game.process_input(session, "1,1")
        
        assert response is not None
        assert continues in [True, False]  # Game might end immediately or continue
        
        # Check that move was made
        board = session.game_data['board']
        assert board[1][1] == 'X'  # Player's move
    
    @pytest.mark.asyncio
    async def test_invalid_move_format(self, tictactoe_game):
        """Test invalid move format"""
        welcome_msg, session = await tictactoe_game.start_game("player1", "TestPlayer")
        
        response, continues = await tictactoe_game.process_input(session, "invalid")
        
        assert "Invalid move format" in response
        assert continues is True
    
    @pytest.mark.asyncio
    async def test_invalid_position(self, tictactoe_game):
        """Test invalid position"""
        welcome_msg, session = await tictactoe_game.start_game("player1", "TestPlayer")
        
        response, continues = await tictactoe_game.process_input(session, "5,5")
        
        assert "Invalid position" in response
        assert continues is True
    
    @pytest.mark.asyncio
    async def test_occupied_position(self, tictactoe_game):
        """Test move to occupied position"""
        welcome_msg, session = await tictactoe_game.start_game("player1", "TestPlayer")
        
        # Make first move
        await tictactoe_game.process_input(session, "1,1")
        
        # Try to move to same position
        response, continues = await tictactoe_game.process_input(session, "1,1")
        
        assert "already taken" in response
        assert continues is True
    
    @pytest.mark.asyncio
    async def test_get_game_status(self, tictactoe_game):
        """Test getting game status"""
        welcome_msg, session = await tictactoe_game.start_game("player1", "TestPlayer")
        
        status = await tictactoe_game.get_game_status(session)
        
        assert "Tic-Tac-Toe" in status
        assert "Your turn" in status or "AI is thinking" in status
    
    @pytest.mark.asyncio
    async def test_get_rules(self, tictactoe_game):
        """Test getting game rules"""
        rules = await tictactoe_game.get_rules()
        
        assert "Tic-Tac-Toe Rules" in rules
        assert "three X's in a row" in rules
        assert "row,col" in rules


class TestHangmanGame:
    """Test Hangman game implementation"""
    
    @pytest.fixture
    def hangman_game(self):
        """Create a Hangman game for testing"""
        return HangmanGame()
    
    @pytest.mark.asyncio
    async def test_start_game(self, hangman_game):
        """Test starting a Hangman game"""
        welcome_msg, session = await hangman_game.start_game("player1", "TestPlayer")
        
        assert "Hangman Game Started" in welcome_msg
        assert session.game_type == "hangman"
        assert session.player_id == "player1"
        assert session.state == GameState.ACTIVE
        
        # Check initial game state
        game_data = session.game_data
        assert 'word' in game_data
        assert len(game_data['word']) > 0
        assert game_data['wrong_guesses'] == 0
        assert len(game_data['guessed_letters']) == 0
    
    @pytest.mark.asyncio
    async def test_valid_letter_guess(self, hangman_game):
        """Test making a valid letter guess"""
        welcome_msg, session = await hangman_game.start_game("player1", "TestPlayer")
        
        response, continues = await hangman_game.process_input(session, "A")
        
        assert response is not None
        assert continues in [True, False]  # Game might end or continue
        
        # Check that letter was recorded
        assert 'A' in session.game_data['guessed_letters']
    
    @pytest.mark.asyncio
    async def test_invalid_guess_format(self, hangman_game):
        """Test invalid guess format"""
        welcome_msg, session = await hangman_game.start_game("player1", "TestPlayer")
        
        response, continues = await hangman_game.process_input(session, "ABC")
        
        assert "single letter" in response
        assert continues is True
    
    @pytest.mark.asyncio
    async def test_repeated_guess(self, hangman_game):
        """Test repeated letter guess"""
        welcome_msg, session = await hangman_game.start_game("player1", "TestPlayer")
        
        # Make first guess
        await hangman_game.process_input(session, "A")
        
        # Repeat same guess
        response, continues = await hangman_game.process_input(session, "A")
        
        assert "already guessed" in response
        assert continues is True
    
    @pytest.mark.asyncio
    async def test_get_rules(self, hangman_game):
        """Test getting game rules"""
        rules = await hangman_game.get_rules()
        
        assert "Hangman Rules" in rules
        assert "wrong guesses" in rules
        assert "single letters" in rules


class TestBlackjackGame:
    """Test Blackjack game implementation"""
    
    @pytest.fixture
    def blackjack_game(self):
        """Create a Blackjack game for testing"""
        return BlackjackGame()
    
    @pytest.mark.asyncio
    async def test_start_game(self, blackjack_game):
        """Test starting a Blackjack game"""
        welcome_msg, session = await blackjack_game.start_game("player1", "TestPlayer")
        
        assert "Blackjack Game Started" in welcome_msg
        assert session.game_type == "blackjack"
        assert session.player_id == "player1"
        assert session.state == GameState.ACTIVE
        
        # Check initial game state
        game_data = session.game_data
        assert len(game_data['player_hand']) == 2
        assert len(game_data['dealer_hand']) == 2
        assert 'deck' in game_data
    
    @pytest.mark.asyncio
    async def test_hit_action(self, blackjack_game):
        """Test hit action"""
        welcome_msg, session = await blackjack_game.start_game("player1", "TestPlayer")
        
        # Skip if game ended immediately (blackjack)
        if session.game_data['game_over']:
            return
        
        initial_cards = len(session.game_data['player_hand'])
        response, continues = await blackjack_game.process_input(session, "hit")
        
        assert response is not None
        # Either got another card or busted
        assert len(session.game_data['player_hand']) >= initial_cards
    
    @pytest.mark.asyncio
    async def test_stand_action(self, blackjack_game):
        """Test stand action"""
        welcome_msg, session = await blackjack_game.start_game("player1", "TestPlayer")
        
        # Skip if game ended immediately (blackjack)
        if session.game_data['game_over']:
            return
        
        response, continues = await blackjack_game.process_input(session, "stand")
        
        assert response is not None
        # Game should end after stand
        assert continues is False
        assert session.game_data['game_over'] is True
    
    @pytest.mark.asyncio
    async def test_invalid_action(self, blackjack_game):
        """Test invalid action"""
        welcome_msg, session = await blackjack_game.start_game("player1", "TestPlayer")
        
        # Skip if game ended immediately (blackjack)
        if session.game_data['game_over']:
            return
        
        response, continues = await blackjack_game.process_input(session, "invalid")
        
        assert "Invalid action" in response
        assert continues is True
    
    @pytest.mark.asyncio
    async def test_get_rules(self, blackjack_game):
        """Test getting game rules"""
        rules = await blackjack_game.get_rules()
        
        assert "Blackjack Rules" in rules
        assert "21" in rules
        assert "hit" in rules
        assert "stand" in rules


class TestGameSession:
    """Test GameSession functionality"""
    
    def test_session_creation(self):
        """Test creating a game session"""
        session = GameSession(
            session_id="test_session",
            game_type="test_game",
            player_id="player1",
            player_name="TestPlayer",
            state=GameState.ACTIVE,
            game_data={},
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        
        assert session.session_id == "test_session"
        assert session.game_type == "test_game"
        assert session.player_id == "player1"
        assert session.state == GameState.ACTIVE
    
    def test_session_activity_update(self):
        """Test updating session activity"""
        session = GameSession(
            session_id="test_session",
            game_type="test_game",
            player_id="player1",
            player_name="TestPlayer",
            state=GameState.ACTIVE,
            game_data={},
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        
        old_activity = session.last_activity
        session.update_activity()
        
        assert session.last_activity > old_activity
    
    def test_session_serialization(self):
        """Test session to/from dict conversion"""
        session = GameSession(
            session_id="test_session",
            game_type="test_game",
            player_id="player1",
            player_name="TestPlayer",
            state=GameState.ACTIVE,
            game_data={"test": "data"},
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        
        # Convert to dict and back
        session_dict = session.to_dict()
        restored_session = GameSession.from_dict(session_dict)
        
        assert restored_session.session_id == session.session_id
        assert restored_session.game_type == session.game_type
        assert restored_session.player_id == session.player_id
        assert restored_session.state == session.state
        assert restored_session.game_data == session.game_data