"""
Tic-Tac-Toe Game Implementation

A classic 3x3 grid game where players try to get three in a row.
Supports single-player mode against a simple AI opponent.
"""

import random
from typing import List, Tuple, Optional
from .base_game import BaseGame, GameSession, GameState


class TicTacToeGame(BaseGame):
    """Tic-Tac-Toe game implementation"""
    
    def __init__(self):
        super().__init__("tictactoe", timeout_minutes=15)
        self.board_size = 3
    
    async def start_game(self, player_id: str, player_name: str, args: List[str] = None) -> Tuple[str, GameSession]:
        """Start a new Tic-Tac-Toe game"""
        # Initialize empty 3x3 board
        board = [['.' for _ in range(3)] for _ in range(3)]
        
        # Player is always X, AI is O
        game_data = {
            'board': board,
            'player_symbol': 'X',
            'ai_symbol': 'O',
            'current_turn': 'player',  # Player goes first
            'moves_made': 0,
            'game_over': False,
            'winner': None
        }
        
        session = GameSession(
            session_id=self.generate_session_id(player_id),
            game_type=self.game_type,
            player_id=player_id,
            player_name=player_name,
            state=GameState.ACTIVE,
            game_data=game_data,
            created_at=session.created_at if 'session' in locals() else None,
            last_activity=session.last_activity if 'session' in locals() else None,
            timeout_minutes=self.timeout_minutes
        )
        
        # Fix datetime initialization
        from datetime import datetime
        session.created_at = datetime.utcnow()
        session.last_activity = datetime.utcnow()
        
        board_display = self._format_board(board)
        welcome_msg = (
            f"🎮 Tic-Tac-Toe Game Started!\n\n"
            f"You are X, AI is O. You go first!\n"
            f"Enter moves as row,col (0-2). Example: '1,1' for center\n\n"
            f"{board_display}\n\n"
            f"Your turn! Enter your move:"
        )
        
        return welcome_msg, session
    
    async def process_input(self, session: GameSession, user_input: str) -> Tuple[str, bool]:
        """Process player move"""
        game_data = session.game_data
        
        if game_data['game_over']:
            return "Game is already over! Start a new game with 'tictactoe'.", False
        
        if game_data['current_turn'] != 'player':
            return "It's not your turn! Wait for AI move.", True
        
        # Parse move
        try:
            parts = user_input.strip().split(',')
            if len(parts) != 2:
                return "Invalid move format! Use 'row,col' (0-2). Example: '1,1'", True
            
            row, col = int(parts[0].strip()), int(parts[1].strip())
            
            if not (0 <= row <= 2 and 0 <= col <= 2):
                return "Invalid position! Use numbers 0-2 for row and column.", True
            
            if game_data['board'][row][col] != '.':
                return "That position is already taken! Choose an empty spot.", True
            
        except ValueError:
            return "Invalid move format! Use numbers like '1,1'", True
        
        # Make player move
        game_data['board'][row][col] = game_data['player_symbol']
        game_data['moves_made'] += 1
        
        # Check for win or draw after player move
        winner = self._check_winner(game_data['board'])
        if winner:
            game_data['game_over'] = True
            game_data['winner'] = winner
            board_display = self._format_board(game_data['board'])
            
            if winner == game_data['player_symbol']:
                return f"🎉 Congratulations! You won!\n\n{board_display}", False
            else:
                return f"😔 You lost! Better luck next time.\n\n{board_display}", False
        
        if game_data['moves_made'] >= 9:
            game_data['game_over'] = True
            board_display = self._format_board(game_data['board'])
            return f"🤝 It's a draw! Good game!\n\n{board_display}", False
        
        # AI's turn
        game_data['current_turn'] = 'ai'
        ai_row, ai_col = self._make_ai_move(game_data['board'])
        game_data['board'][ai_row][ai_col] = game_data['ai_symbol']
        game_data['moves_made'] += 1
        
        # Check for win or draw after AI move
        winner = self._check_winner(game_data['board'])
        board_display = self._format_board(game_data['board'])
        
        if winner:
            game_data['game_over'] = True
            game_data['winner'] = winner
            
            if winner == game_data['ai_symbol']:
                return f"🤖 AI wins! AI played {ai_row},{ai_col}\n\n{board_display}", False
            else:
                return f"🎉 You won! AI played {ai_row},{ai_col}\n\n{board_display}", False
        
        if game_data['moves_made'] >= 9:
            game_data['game_over'] = True
            return f"🤝 It's a draw! AI played {ai_row},{ai_col}\n\n{board_display}", False
        
        # Continue game
        game_data['current_turn'] = 'player'
        return f"🤖 AI played {ai_row},{ai_col}\n\n{board_display}\n\nYour turn! Enter your move:", True
    
    async def get_game_status(self, session: GameSession) -> str:
        """Get current game status"""
        game_data = session.game_data
        board_display = self._format_board(game_data['board'])
        
        if game_data['game_over']:
            winner = game_data['winner']
            if winner == game_data['player_symbol']:
                status = "🎉 You won!"
            elif winner == game_data['ai_symbol']:
                status = "🤖 AI won!"
            else:
                status = "🤝 Draw!"
        else:
            if game_data['current_turn'] == 'player':
                status = "Your turn! Enter your move (row,col):"
            else:
                status = "AI is thinking..."
        
        return f"🎮 Tic-Tac-Toe\n\n{board_display}\n\n{status}"
    
    async def get_rules(self) -> str:
        """Get game rules"""
        return (
            "📋 Tic-Tac-Toe Rules\n\n"
            "• Get three X's in a row (horizontal, vertical, or diagonal) to win\n"
            "• You are X, AI is O\n"
            "• Enter moves as 'row,col' using numbers 0-2\n"
            "• Example: '1,1' places X in the center\n"
            "• Board positions:\n"
            "  0,0 | 0,1 | 0,2\n"
            "  1,0 | 1,1 | 1,2\n"
            "  2,0 | 2,1 | 2,2\n\n"
            "Commands: 'quit', 'status', 'help'"
        )
    
    def _format_board(self, board: List[List[str]]) -> str:
        """Format the game board for display"""
        lines = []
        for i, row in enumerate(board):
            # Replace dots with spaces for better display
            display_row = [cell if cell != '.' else ' ' for cell in row]
            line = f" {display_row[0]} | {display_row[1]} | {display_row[2]} "
            lines.append(line)
            
            # Add separator line except after last row
            if i < len(board) - 1:
                lines.append("---|---|---")
        
        return "\n".join(lines)
    
    def _check_winner(self, board: List[List[str]]) -> Optional[str]:
        """Check if there's a winner"""
        # Check rows
        for row in board:
            if row[0] == row[1] == row[2] != '.':
                return row[0]
        
        # Check columns
        for col in range(3):
            if board[0][col] == board[1][col] == board[2][col] != '.':
                return board[0][col]
        
        # Check diagonals
        if board[0][0] == board[1][1] == board[2][2] != '.':
            return board[0][0]
        
        if board[0][2] == board[1][1] == board[2][0] != '.':
            return board[0][2]
        
        return None
    
    def _make_ai_move(self, board: List[List[str]]) -> Tuple[int, int]:
        """Make AI move using simple strategy"""
        # Strategy priority:
        # 1. Win if possible
        # 2. Block player from winning
        # 3. Take center if available
        # 4. Take corner
        # 5. Take any available spot
        
        # Check for winning move
        for row in range(3):
            for col in range(3):
                if board[row][col] == '.':
                    board[row][col] = 'O'
                    if self._check_winner(board) == 'O':
                        board[row][col] = '.'  # Undo test move
                        return row, col
                    board[row][col] = '.'  # Undo test move
        
        # Check for blocking move
        for row in range(3):
            for col in range(3):
                if board[row][col] == '.':
                    board[row][col] = 'X'
                    if self._check_winner(board) == 'X':
                        board[row][col] = '.'  # Undo test move
                        return row, col
                    board[row][col] = '.'  # Undo test move
        
        # Take center if available
        if board[1][1] == '.':
            return 1, 1
        
        # Take corners
        corners = [(0, 0), (0, 2), (2, 0), (2, 2)]
        available_corners = [(r, c) for r, c in corners if board[r][c] == '.']
        if available_corners:
            return random.choice(available_corners)
        
        # Take any available spot
        available = []
        for row in range(3):
            for col in range(3):
                if board[row][col] == '.':
                    available.append((row, col))
        
        return random.choice(available) if available else (0, 0)