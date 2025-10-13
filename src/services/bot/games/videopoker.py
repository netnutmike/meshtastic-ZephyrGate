"""
Video Poker Game Implementation

Classic video poker game where players try to make the best 5-card poker hand.
Features standard Jacks or Better rules with hold/discard mechanics.
"""

import random
from typing import List, Tuple, Dict, Any, Set
from collections import Counter
from .base_game import BaseGame, GameSession, GameState


class PokerCard:
    """Represents a playing card for poker"""
    
    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank
        self.rank_value = self._get_rank_value()
    
    def _get_rank_value(self) -> int:
        """Get numeric value for ranking"""
        rank_values = {
            'A': 14, 'K': 13, 'Q': 12, 'J': 11, '10': 10,
            '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2
        }
        return rank_values[self.rank]
    
    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"
    
    def __eq__(self, other) -> bool:
        return self.suit == other.suit and self.rank == other.rank
    
    def __hash__(self) -> int:
        return hash((self.suit, self.rank))


class PokerHand:
    """Represents a 5-card poker hand"""
    
    def __init__(self, cards: List[PokerCard] = None):
        self.cards = cards or []
    
    def add_card(self, card: PokerCard):
        """Add a card to the hand"""
        if len(self.cards) < 5:
            self.cards.append(card)
    
    def remove_card(self, index: int) -> PokerCard:
        """Remove card at index"""
        if 0 <= index < len(self.cards):
            return self.cards.pop(index)
        return None
    
    def evaluate(self) -> Tuple[str, int]:
        """Evaluate hand and return (hand_name, payout_multiplier)"""
        if len(self.cards) != 5:
            return "Incomplete Hand", 0
        
        # Sort cards by rank value for easier evaluation
        sorted_cards = sorted(self.cards, key=lambda c: c.rank_value, reverse=True)
        ranks = [c.rank_value for c in sorted_cards]
        suits = [c.suit for c in sorted_cards]
        
        # Count ranks
        rank_counts = Counter(ranks)
        counts = sorted(rank_counts.values(), reverse=True)
        
        # Check for flush
        is_flush = len(set(suits)) == 1
        
        # Check for straight
        is_straight = self._is_straight(ranks)
        
        # Special case for A-2-3-4-5 straight (wheel)
        if ranks == [14, 5, 4, 3, 2]:
            is_straight = True
            ranks = [5, 4, 3, 2, 1]  # Treat ace as 1 for wheel
        
        # Evaluate hand type (Jacks or Better rules)
        if is_straight and is_flush:
            if ranks[0] == 14 and ranks[1] == 13:  # A-K-Q-J-10
                return "Royal Flush", 800
            else:
                return "Straight Flush", 50
        elif counts == [4, 1]:
            return "Four of a Kind", 25
        elif counts == [3, 2]:
            return "Full House", 9
        elif is_flush:
            return "Flush", 6
        elif is_straight:
            return "Straight", 4
        elif counts == [3, 1, 1]:
            return "Three of a Kind", 3
        elif counts == [2, 2, 1]:
            return "Two Pair", 2
        elif counts == [2, 1, 1, 1]:
            # Check if pair is Jacks or better
            pair_rank = max(rank for rank, count in rank_counts.items() if count == 2)
            if pair_rank >= 11:  # Jacks (11) or better
                return "Jacks or Better", 1
            else:
                return "Pair (Low)", 0
        else:
            return "High Card", 0
    
    def _is_straight(self, ranks: List[int]) -> bool:
        """Check if ranks form a straight"""
        if len(set(ranks)) != 5:
            return False
        
        # Check normal straight
        if ranks[0] - ranks[4] == 4:
            return True
        
        # Check for A-2-3-4-5 wheel straight
        if ranks == [14, 5, 4, 3, 2]:
            return True
        
        return False
    
    def __str__(self) -> str:
        return ', '.join(str(card) for card in self.cards)


class VideoPokerGame(BaseGame):
    """Video Poker (Jacks or Better) game implementation"""
    
    def __init__(self):
        super().__init__("videopoker", timeout_minutes=15)
        self.suits = ['♠', '♥', '♦', '♣']
        self.ranks = ['A', 'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3', '2']
        self.bet_amount = 1  # Fixed bet for simplicity
    
    async def start_game(self, player_id: str, player_name: str, args: List[str] = None) -> Tuple[str, GameSession]:
        """Start a new Video Poker game"""
        # Create and shuffle deck
        deck = self._create_deck()
        random.shuffle(deck)
        
        # Deal initial 5 cards
        hand = PokerHand()
        for _ in range(5):
            hand.add_card(deck.pop())
        
        game_data = {
            'deck': [{'suit': c.suit, 'rank': c.rank} for c in deck],
            'hand': [{'suit': c.suit, 'rank': c.rank} for c in hand.cards],
            'held_cards': [False] * 5,  # Which cards to hold
            'game_phase': 'hold_select',  # hold_select, draw, game_over
            'game_over': False,
            'final_hand': None,
            'payout': 0,
            'credits': 100  # Starting credits
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
        
        hand_display = self._get_hand_display(game_data)
        welcome_msg = (
            f"🎮 Video Poker (Jacks or Better) Started!\n\n"
            f"Credits: {game_data['credits']}\n"
            f"Bet: {self.bet_amount} credit(s)\n\n"
            f"{hand_display}\n\n"
            f"Select cards to HOLD (1-5) or 'draw' to discard all:\n"
            f"Example: 'hold 1 3 5' or just 'draw'"
        )
        
        return welcome_msg, session
    
    async def process_input(self, session: GameSession, user_input: str) -> Tuple[str, bool]:
        """Process player input"""
        game_data = session.game_data
        
        if game_data['game_over']:
            return "Game is already over! Start a new game with 'videopoker'.", False
        
        input_str = user_input.strip().lower()
        
        if game_data['game_phase'] == 'hold_select':
            if input_str == 'draw':
                # Draw without holding any cards
                return await self._handle_draw(game_data)
            elif input_str.startswith('hold'):
                # Parse hold command
                parts = input_str.split()
                if len(parts) == 1:
                    return "Specify which cards to hold! Example: 'hold 1 3 5' or 'draw' for none.", True
                
                try:
                    positions = []
                    for part in parts[1:]:
                        pos = int(part)
                        if 1 <= pos <= 5:
                            positions.append(pos - 1)  # Convert to 0-based index
                        else:
                            return "Card positions must be 1-5!", True
                    
                    # Set held cards
                    game_data['held_cards'] = [False] * 5
                    for pos in positions:
                        game_data['held_cards'][pos] = True
                    
                    return await self._handle_draw(game_data)
                    
                except ValueError:
                    return "Invalid card positions! Use numbers 1-5.", True
            else:
                return "Use 'hold 1 2 3' to hold cards 1,2,3 or 'draw' to discard all.", True
        
        else:
            return "Game phase not ready for input.", True
    
    async def get_game_status(self, session: GameSession) -> str:
        """Get current game status"""
        game_data = session.game_data
        hand_display = self._get_hand_display(game_data)
        
        status_msg = f"🎮 Video Poker\n\nCredits: {game_data['credits']}\n\n{hand_display}"
        
        if game_data['game_over']:
            final_hand = game_data['final_hand']
            payout = game_data['payout']
            if payout > 0:
                status_msg += f"\n\n🎉 {final_hand}! You won {payout} credits!"
            else:
                status_msg += f"\n\n😔 {final_hand}. No payout."
        elif game_data['game_phase'] == 'hold_select':
            status_msg += "\n\nSelect cards to hold (1-5) or 'draw':"
        
        return status_msg
    
    async def get_rules(self) -> str:
        """Get game rules"""
        return (
            "📋 Video Poker (Jacks or Better) Rules\n\n"
            "• Make the best 5-card poker hand possible\n"
            "• You get 5 cards, choose which to hold\n"
            "• Discard unwanted cards and draw replacements\n"
            "• Minimum winning hand: Pair of Jacks\n\n"
            "Payouts (for 1 credit bet):\n"
            "• Royal Flush: 800\n"
            "• Straight Flush: 50\n"
            "• Four of a Kind: 25\n"
            "• Full House: 9\n"
            "• Flush: 6\n"
            "• Straight: 4\n"
            "• Three of a Kind: 3\n"
            "• Two Pair: 2\n"
            "• Jacks or Better: 1\n\n"
            "Commands: 'hold 1 2 3', 'draw', 'quit', 'status'"
        )
    
    def _create_deck(self) -> List[PokerCard]:
        """Create a standard 52-card deck"""
        deck = []
        for suit in self.suits:
            for rank in self.ranks:
                deck.append(PokerCard(suit, rank))
        return deck
    
    def _hand_from_data(self, hand_data: List[Dict[str, str]]) -> PokerHand:
        """Convert hand data back to PokerHand object"""
        hand = PokerHand()
        for card_data in hand_data:
            hand.add_card(PokerCard(card_data['suit'], card_data['rank']))
        return hand
    
    def _get_hand_display(self, game_data: Dict[str, Any]) -> str:
        """Get formatted hand display"""
        hand = self._hand_from_data(game_data['hand'])
        held_cards = game_data['held_cards']
        
        lines = []
        
        # Card display
        card_strs = []
        for i, card in enumerate(hand.cards):
            card_str = str(card)
            if held_cards[i]:
                card_str += " (HELD)"
            card_strs.append(f"{i+1}: {card_str}")
        
        lines.append("Your Hand:")
        lines.extend(card_strs)
        
        # Show current hand evaluation if in hold phase
        if game_data['game_phase'] == 'hold_select':
            hand_name, payout = hand.evaluate()
            lines.append(f"\nCurrent: {hand_name} (Pays: {payout})")
        
        return "\n".join(lines)
    
    async def _handle_draw(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle the draw phase"""
        game_data['game_phase'] = 'draw'
        
        # Replace non-held cards
        deck_cards = [PokerCard(c['suit'], c['rank']) for c in game_data['deck']]
        hand_cards = [PokerCard(c['suit'], c['rank']) for c in game_data['hand']]
        held_cards = game_data['held_cards']
        
        new_hand = []
        cards_drawn = 0
        
        for i in range(5):
            if held_cards[i]:
                # Keep this card
                new_hand.append(hand_cards[i])
            else:
                # Draw new card
                if deck_cards:
                    new_card = deck_cards.pop()
                    new_hand.append(new_card)
                    cards_drawn += 1
                else:
                    # Shouldn't happen with proper deck management
                    new_hand.append(hand_cards[i])
        
        # Update game data
        game_data['hand'] = [{'suit': c.suit, 'rank': c.rank} for c in new_hand]
        game_data['deck'] = [{'suit': c.suit, 'rank': c.rank} for c in deck_cards]
        
        # Evaluate final hand
        final_hand = PokerHand(new_hand)
        hand_name, payout = final_hand.evaluate()
        
        game_data['game_phase'] = 'game_over'
        game_data['game_over'] = True
        game_data['final_hand'] = hand_name
        game_data['payout'] = payout
        game_data['credits'] += payout - self.bet_amount  # Add winnings, subtract bet
        
        # Create result message
        hand_display = self._get_hand_display(game_data)
        
        if cards_drawn > 0:
            draw_msg = f"Drew {cards_drawn} new card(s).\n\n"
        else:
            draw_msg = "Kept all cards.\n\n"
        
        if payout > 0:
            result_msg = f"🎉 {hand_name}! You won {payout} credits!"
            if payout >= 25:
                result_msg = f"🎊 " + result_msg  # Extra celebration for big wins
        else:
            result_msg = f"😔 {hand_name}. No payout this time."
        
        final_msg = f"{draw_msg}{hand_display}\n\n{result_msg}\n\nFinal Credits: {game_data['credits']}"
        
        return final_msg, False