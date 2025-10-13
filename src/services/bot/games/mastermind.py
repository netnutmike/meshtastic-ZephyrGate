"""
Mastermind Game Implementation

A logic puzzle game where players try to guess a secret code
by making guesses and receiving feedback about correct positions and colors.
"""

import random
from typing import List, Tuple, Dict, Any
from .base_game import BaseGame, GameSession, GameState


class MastermindGame(BaseGame):
    """Mastermind logic puzzle game"""
    
    def __init__(self):
        super().__init__("mastermind", timeout_minutes=25)
        
        # Game configuration
        self.code_length = 4
        self.max_guesses = 10
        self.colors = ['R', 'G', 'B', 'Y', 'O', 'P']  # Red, Green, Blue, Yellow, Orange, Purple
        self.color_names = {
            'R': '🔴 Red',
            'G': '🟢 Green', 
            'B': '🔵 Blue',
            'Y': '🟡 Yellow',
            'O': '🟠 Orange',
            'P': '🟣 Purple'
        }
        self.allow_duplicates = True
    
    async def start_game(self, player_id: str, player_name: str, args: List[str] = None) -> Tuple[str, GameSession]:
        """Start a new Mastermind game"""
        
        # Generate secret code
        if self.allow_duplicates:
            secret_code = [random.choice(self.colors) for _ in range(self.code_length)]
        else:
            secret_code = random.sample(self.colors, self.code_length)
        
        game_data = {
            'secret_code': secret_code,
            'guesses': [],  # List of (guess, feedback) tuples
            'current_guess': 1,
            'max_guesses': self.max_guesses,
            'game_over': False,
            'won': False,
            'code_length': self.code_length,
            'available_colors': self.colors.copy()
        }
        
        session = GameSession(
            session_id=self.generate_session_id(player_id),
            game_type=self.game_type,
            player_id=player_id,
            player_name=player_name,
            state=GameState.ACTIVE,
            game_data=game_data,
            created_at=None,
            last_activity=None,
            timeout_minutes=self.timeout_minutes
        )
        
        # Fix datetime initialization
        from datetime import datetime
        session.created_at = datetime.utcnow()
        session.last_activity = datetime.utcnow()
        
        colors_display = self._get_colors_display()
        rules_display = self._get_rules_display()
        
        welcome_msg = (
            f"🧩 Mastermind Game Started!\n\n"
            f"I've created a secret {self.code_length}-color code.\n"
            f"You have {self.max_guesses} guesses to crack it!\n\n"
            f"{colors_display}\n\n"
            f"{rules_display}\n\n"
            f"Guess #{game_data['current_guess']}: Enter {self.code_length} colors (e.g., 'RGBY'):"
        )
        
        return welcome_msg, session
    
    async def process_input(self, session: GameSession, user_input: str) -> Tuple[str, bool]:
        """Process player guess"""
        game_data = session.game_data
        
        if game_data['game_over']:
            return "Game is already over! Start a new game with 'mastermind'.", False
        
        guess_input = user_input.strip().upper()
        
        # Validate guess format
        if len(guess_input) != self.code_length:
            return f"Please enter exactly {self.code_length} colors! Example: 'RGBY'", True
        
        # Validate colors
        guess = list(guess_input)
        for color in guess:
            if color not in self.colors:
                valid_colors = ', '.join(self.colors)
                return f"Invalid color '{color}'! Use: {valid_colors}", True
        
        # Check for duplicates if not allowed
        if not self.allow_duplicates and len(set(guess)) != len(guess):
            return "No duplicate colors allowed in this game!", True
        
        # Process the guess
        feedback = self._calculate_feedback(guess, game_data['secret_code'])
        game_data['guesses'].append((guess, feedback))
        
        # Check if player won
        if feedback['exact_matches'] == self.code_length:
            game_data['game_over'] = True
            game_data['won'] = True
            
            guesses_display = self._get_guesses_display(game_data)
            secret_display = self._get_secret_display(game_data['secret_code'])
            
            return (
                f"🎉 Congratulations! You cracked the code!\n\n"
                f"{guesses_display}\n\n"
                f"{secret_display}\n\n"
                f"You won in {game_data['current_guess']} guess(es)! 🏆"
            ), False
        
        # Check if out of guesses
        if game_data['current_guess'] >= game_data['max_guesses']:
            game_data['game_over'] = True
            game_data['won'] = False
            
            guesses_display = self._get_guesses_display(game_data)
            secret_display = self._get_secret_display(game_data['secret_code'])
            
            return (
                f"💀 Game Over! You've used all {self.max_guesses} guesses.\n\n"
                f"{guesses_display}\n\n"
                f"{secret_display}\n\n"
                f"Better luck next time!"
            ), False
        
        # Continue game
        game_data['current_guess'] += 1
        guesses_display = self._get_guesses_display(game_data)
        
        return (
            f"Guess #{game_data['current_guess'] - 1} feedback:\n"
            f"🎯 Exact matches: {feedback['exact_matches']}\n"
            f"🟡 Color matches: {feedback['color_matches']}\n\n"
            f"{guesses_display}\n\n"
            f"Guess #{game_data['current_guess']}: Enter {self.code_length} colors:"
        ), True
    
    async def get_game_status(self, session: GameSession) -> str:
        """Get current game status"""
        game_data = session.game_data
        
        if game_data['game_over']:
            if game_data['won']:
                result = f"🎉 You won in {len(game_data['guesses'])} guesses!"
            else:
                result = f"💀 Game over! The code was: {' '.join(game_data['secret_code'])}"
            
            guesses_display = self._get_guesses_display(game_data)
            return f"🧩 Mastermind - Game Complete\n\n{result}\n\n{guesses_display}"
        
        guesses_display = self._get_guesses_display(game_data)
        remaining = game_data['max_guesses'] - game_data['current_guess'] + 1
        
        status = (
            f"🧩 Mastermind\n\n"
            f"Guess #{game_data['current_guess']} of {game_data['max_guesses']}\n"
            f"Remaining guesses: {remaining}\n\n"
            f"{guesses_display}\n\n"
            f"Enter your next guess:"
        )
        
        return status
    
    async def get_rules(self) -> str:
        """Get game rules"""
        colors_display = self._get_colors_display()
        
        return (
            f"📋 Mastermind Rules\n\n"
            f"• Guess the secret {self.code_length}-color code\n"
            f"• You have {self.max_guesses} guesses to crack it\n"
            f"• After each guess, you get feedback:\n"
            f"  🎯 Exact matches: Right color in right position\n"
            f"  🟡 Color matches: Right color in wrong position\n"
            f"• Use logic to deduce the secret code!\n"
            f"• Duplicates {'allowed' if self.allow_duplicates else 'not allowed'}\n\n"
            f"{colors_display}\n\n"
            f"Example guess: 'RGBY' (Red, Green, Blue, Yellow)\n"
            f"Commands: '<colors>', 'status', 'help'"
        )
    
    def _calculate_feedback(self, guess: List[str], secret: List[str]) -> Dict[str, int]:
        """Calculate feedback for a guess"""
        exact_matches = 0
        color_matches = 0
        
        # Count exact matches first
        guess_remaining = []
        secret_remaining = []
        
        for i in range(len(guess)):
            if guess[i] == secret[i]:
                exact_matches += 1
            else:
                guess_remaining.append(guess[i])
                secret_remaining.append(secret[i])
        
        # Count color matches (right color, wrong position)
        for color in guess_remaining:
            if color in secret_remaining:
                color_matches += 1
                secret_remaining.remove(color)  # Remove one instance
        
        return {
            'exact_matches': exact_matches,
            'color_matches': color_matches
        }
    
    def _get_colors_display(self) -> str:
        """Get available colors display"""
        lines = ["🎨 Available Colors:"]
        for color in self.colors:
            lines.append(f"  {color} = {self.color_names[color]}")
        return "\n".join(lines)
    
    def _get_rules_display(self) -> str:
        """Get rules summary display"""
        return (
            f"📋 How to play:\n"
            f"• Enter {self.code_length} color letters (e.g., 'RGBY')\n"
            f"• 🎯 = Right color, right position\n"
            f"• 🟡 = Right color, wrong position"
        )
    
    def _get_guesses_display(self, game_data: Dict[str, Any]) -> str:
        """Get display of all guesses and feedback"""
        if not game_data['guesses']:
            return "📝 No guesses yet"
        
        lines = ["📝 Your Guesses:"]
        
        for i, (guess, feedback) in enumerate(game_data['guesses'], 1):
            guess_str = ' '.join(guess)
            exact = feedback['exact_matches']
            color = feedback['color_matches']
            
            # Add color emojis for visual appeal
            guess_display = []
            for color_code in guess:
                if color_code in self.color_names:
                    emoji = self.color_names[color_code].split()[0]  # Get just the emoji
                    guess_display.append(f"{color_code}{emoji}")
                else:
                    guess_display.append(color_code)
            
            guess_visual = ' '.join(guess_display)
            lines.append(f"{i:2d}. {guess_visual} → 🎯{exact} 🟡{color}")
        
        return "\n".join(lines)
    
    def _get_secret_display(self, secret_code: List[str]) -> str:
        """Get secret code display"""
        secret_visual = []
        for color_code in secret_code:
            if color_code in self.color_names:
                emoji = self.color_names[color_code].split()[0]  # Get just the emoji
                secret_visual.append(f"{color_code}{emoji}")
            else:
                secret_visual.append(color_code)
        
        return f"🔐 Secret Code: {' '.join(secret_visual)}"