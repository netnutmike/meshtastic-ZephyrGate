"""
Interactive Games Framework

Provides base classes and game implementations for the interactive bot system.
Supports multiple game types including card games, logic puzzles, and simulations.
"""

from .base_game import BaseGame, GameSession, GameState
from .tictactoe import TicTacToeGame
from .hangman import HangmanGame
from .blackjack import BlackjackGame
from .videopoker import VideoPokerGame
from .dopewars import DopeWarsGame
from .lemonstand import LemonadeStandGame
from .golfsim import GolfSimulatorGame
from .mastermind import MastermindGame

__all__ = [
    'BaseGame', 'GameSession', 'GameState',
    'TicTacToeGame', 'HangmanGame', 'BlackjackGame', 'VideoPokerGame',
    'DopeWarsGame', 'LemonadeStandGame', 'GolfSimulatorGame', 'MastermindGame'
]