"""
Hangman Game Implementation

Classic word guessing game where players try to guess a word by suggesting letters.
Features a built-in word list and ASCII art hangman display.
"""

import random
from typing import List, Tuple, Set
from .base_game import BaseGame, GameSession, GameState


class HangmanGame(BaseGame):
    """Hangman word guessing game"""
    
    def __init__(self):
        super().__init__("hangman", timeout_minutes=20)
        self.max_wrong_guesses = 6
        self.word_list = [
            # Technology words
            "COMPUTER", "INTERNET", "SOFTWARE", "HARDWARE", "NETWORK", "DATABASE",
            "ALGORITHM", "PROGRAMMING", "ENCRYPTION", "FIREWALL", "ROUTER", "SERVER",
            
            # Ham radio terms
            "ANTENNA", "FREQUENCY", "MODULATION", "AMPLIFIER", "TRANSCEIVER", "REPEATER",
            "OSCILLATOR", "BANDWIDTH", "PROPAGATION", "IONOSPHERE", "WAVELENGTH",
            
            # General words
            "ADVENTURE", "CHALLENGE", "DISCOVERY", "EXPLORATION", "INNOVATION", "KNOWLEDGE",
            "MYSTERY", "PUZZLE", "QUESTION", "SOLUTION", "TECHNOLOGY", "UNIVERSE",
            "WEATHER", "MOUNTAIN", "OCEAN", "FOREST", "DESERT", "VALLEY",
            
            # Mesh networking
            "MESHTASTIC", "PROTOCOL", "PACKET", "GATEWAY", "BRIDGE", "NODE",
            "TOPOLOGY", "ROUTING", "BROADCAST", "UNICAST", "MULTICAST"
        ]
    
    async def start_game(self, player_id: str, player_name: str, args: List[str] = None) -> Tuple[str, GameSession]:
        """Start a new Hangman game"""
        # Select random word
        word = random.choice(self.word_list)
        
        game_data = {
            'word': word,
            'guessed_letters': set(),
            'wrong_guesses': 0,
            'max_wrong_guesses': self.max_wrong_guesses,
            'game_over': False,
            'won': False,
            'current_display': self._get_word_display(word, set())
        }
        
        session = GameSession(
            session_id=self.generate_session_id(player_id),
            game_type=self.game_type,
            player_id=player_id,
            player_name=player_name,
            state=GameState.ACTIVE,
            game_data=game_data,
            created_at=None,  # Will be set below
            last_activity=None,  # Will be set below
            timeout_minutes=self.timeout_minutes
        )
        
        # Fix datetime initialization
        from datetime import datetime
        session.created_at = datetime.utcnow()
        session.last_activity = datetime.utcnow()
        
        hangman_display = self._get_hangman_display(0)
        word_display = game_data['current_display']
        
        welcome_msg = (
            f"🎮 Hangman Game Started!\n\n"
            f"Guess the word by entering letters one at a time.\n"
            f"You have {self.max_wrong_guesses} wrong guesses allowed.\n\n"
            f"{hangman_display}\n\n"
            f"Word: {word_display}\n"
            f"Wrong guesses: 0/{self.max_wrong_guesses}\n"
            f"Guessed letters: (none)\n\n"
            f"Enter a letter:"
        )
        
        return welcome_msg, session
    
    async def process_input(self, session: GameSession, user_input: str) -> Tuple[str, bool]:
        """Process letter guess"""
        game_data = session.game_data
        
        if game_data['game_over']:
            return "Game is already over! Start a new game with 'hangman'.", False
        
        # Validate input
        guess = user_input.strip().upper()
        if len(guess) != 1 or not guess.isalpha():
            return "Please enter a single letter!", True
        
        if guess in game_data['guessed_letters']:
            return f"You already guessed '{guess}'! Try a different letter.", True
        
        # Process guess
        game_data['guessed_letters'].add(guess)
        word = game_data['word']
        
        if guess in word:
            # Correct guess
            game_data['current_display'] = self._get_word_display(word, game_data['guessed_letters'])
            
            # Check if word is complete
            if '_' not in game_data['current_display']:
                game_data['game_over'] = True
                game_data['won'] = True
                
                hangman_display = self._get_hangman_display(game_data['wrong_guesses'])
                return (
                    f"🎉 Congratulations! You guessed the word!\n\n"
                    f"{hangman_display}\n\n"
                    f"Word: {game_data['current_display']}\n"
                    f"You won with {game_data['wrong_guesses']} wrong guesses!"
                ), False
            
            # Continue game
            hangman_display = self._get_hangman_display(game_data['wrong_guesses'])
            guessed_list = sorted(list(game_data['guessed_letters']))
            
            return (
                f"✅ Good guess! '{guess}' is in the word.\n\n"
                f"{hangman_display}\n\n"
                f"Word: {game_data['current_display']}\n"
                f"Wrong guesses: {game_data['wrong_guesses']}/{game_data['max_wrong_guesses']}\n"
                f"Guessed letters: {', '.join(guessed_list)}\n\n"
                f"Enter another letter:"
            ), True
        
        else:
            # Wrong guess
            game_data['wrong_guesses'] += 1
            
            # Check if game over
            if game_data['wrong_guesses'] >= game_data['max_wrong_guesses']:
                game_data['game_over'] = True
                game_data['won'] = False
                
                hangman_display = self._get_hangman_display(game_data['wrong_guesses'])
                return (
                    f"💀 Game Over! You've been hanged!\n\n"
                    f"{hangman_display}\n\n"
                    f"The word was: {word}\n"
                    f"Better luck next time!"
                ), False
            
            # Continue game
            hangman_display = self._get_hangman_display(game_data['wrong_guesses'])
            guessed_list = sorted(list(game_data['guessed_letters']))
            
            return (
                f"❌ Sorry, '{guess}' is not in the word.\n\n"
                f"{hangman_display}\n\n"
                f"Word: {game_data['current_display']}\n"
                f"Wrong guesses: {game_data['wrong_guesses']}/{game_data['max_wrong_guesses']}\n"
                f"Guessed letters: {', '.join(guessed_list)}\n\n"
                f"Enter another letter:"
            ), True
    
    async def get_game_status(self, session: GameSession) -> str:
        """Get current game status"""
        game_data = session.game_data
        hangman_display = self._get_hangman_display(game_data['wrong_guesses'])
        guessed_list = sorted(list(game_data['guessed_letters']))
        guessed_str = ', '.join(guessed_list) if guessed_list else "(none)"
        
        if game_data['game_over']:
            if game_data['won']:
                status = f"🎉 You won! The word was: {game_data['word']}"
            else:
                status = f"💀 Game over! The word was: {game_data['word']}"
        else:
            status = "Enter a letter to guess:"
        
        return (
            f"🎮 Hangman Game\n\n"
            f"{hangman_display}\n\n"
            f"Word: {game_data['current_display']}\n"
            f"Wrong guesses: {game_data['wrong_guesses']}/{game_data['max_wrong_guesses']}\n"
            f"Guessed letters: {guessed_str}\n\n"
            f"{status}"
        )
    
    async def get_rules(self) -> str:
        """Get game rules"""
        return (
            "📋 Hangman Rules\n\n"
            "• Guess the hidden word by entering letters one at a time\n"
            f"• You have {self.max_wrong_guesses} wrong guesses before you lose\n"
            "• Enter single letters only (A-Z)\n"
            "• Correct guesses reveal letters in the word\n"
            "• Wrong guesses add parts to the hangman drawing\n"
            "• Win by guessing all letters before the drawing is complete\n\n"
            "Commands: 'quit', 'status', 'help'"
        )
    
    def _get_word_display(self, word: str, guessed_letters: Set[str]) -> str:
        """Get current word display with guessed letters revealed"""
        display = []
        for letter in word:
            if letter in guessed_letters:
                display.append(letter)
            else:
                display.append('_')
        return ' '.join(display)
    
    def _get_hangman_display(self, wrong_guesses: int) -> str:
        """Get ASCII art hangman display based on wrong guesses"""
        stages = [
            # 0 wrong guesses
            """
  +---+
  |   |
      |
      |
      |
      |
=========
            """,
            # 1 wrong guess
            """
  +---+
  |   |
  O   |
      |
      |
      |
=========
            """,
            # 2 wrong guesses
            """
  +---+
  |   |
  O   |
  |   |
      |
      |
=========
            """,
            # 3 wrong guesses
            """
  +---+
  |   |
  O   |
 /|   |
      |
      |
=========
            """,
            # 4 wrong guesses
            """
  +---+
  |   |
  O   |
 /|\\  |
      |
      |
=========
            """,
            # 5 wrong guesses
            """
  +---+
  |   |
  O   |
 /|\\  |
 /    |
      |
=========
            """,
            # 6 wrong guesses (game over)
            """
  +---+
  |   |
  O   |
 /|\\  |
 / \\  |
      |
=========
            """
        ]
        
        if wrong_guesses >= len(stages):
            return stages[-1].strip()
        
        return stages[wrong_guesses].strip()