"""
Blackjack Game Implementation

Classic casino card game where players try to get as close to 21 as possible
without going over, while beating the dealer's hand.
"""

import random
from typing import List, Tuple, Dict, Any
from .base_game import BaseGame, GameSession, GameState


class Card:
    """Represents a playing card"""
    
    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank
    
    def value(self) -> int:
        """Get numeric value of card for blackjack"""
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11  # Ace handling is done at hand level
        else:
            return int(self.rank)
    
    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


class BlackjackHand:
    """Represents a blackjack hand"""
    
    def __init__(self):
        self.cards: List[Card] = []
    
    def add_card(self, card: Card):
        """Add a card to the hand"""
        self.cards.append(card)
    
    def value(self) -> int:
        """Calculate hand value with proper Ace handling"""
        total = 0
        aces = 0
        
        for card in self.cards:
            if card.rank == 'A':
                aces += 1
                total += 11
            else:
                total += card.value()
        
        # Adjust for Aces
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        
        return total
    
    def is_blackjack(self) -> bool:
        """Check if hand is a natural blackjack"""
        return len(self.cards) == 2 and self.value() == 21
    
    def is_bust(self) -> bool:
        """Check if hand is bust (over 21)"""
        return self.value() > 21
    
    def __str__(self) -> str:
        return ', '.join(str(card) for card in self.cards)


class BlackjackGame(BaseGame):
    """Blackjack card game implementation"""
    
    def __init__(self):
        super().__init__("blackjack", timeout_minutes=20)
        self.suits = ['♠', '♥', '♦', '♣']
        self.ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    
    async def start_game(self, player_id: str, player_name: str, args: List[str] = None) -> Tuple[str, GameSession]:
        """Start a new Blackjack game"""
        # Create and shuffle deck
        deck = self._create_deck()
        random.shuffle(deck)
        
        # Deal initial cards
        player_hand = BlackjackHand()
        dealer_hand = BlackjackHand()
        
        # Deal two cards to each
        player_hand.add_card(deck.pop())
        dealer_hand.add_card(deck.pop())
        player_hand.add_card(deck.pop())
        dealer_hand.add_card(deck.pop())
        
        game_data = {
            'deck': [{'suit': c.suit, 'rank': c.rank} for c in deck],
            'player_hand': [{'suit': c.suit, 'rank': c.rank} for c in player_hand.cards],
            'dealer_hand': [{'suit': c.suit, 'rank': c.rank} for c in dealer_hand.cards],
            'game_phase': 'player_turn',  # player_turn, dealer_turn, game_over
            'game_over': False,
            'result': None,  # win, lose, push, blackjack
            'player_stood': False
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
        
        # Check for immediate blackjack
        player_bj = self._hand_from_data(game_data['player_hand']).is_blackjack()
        dealer_bj = self._hand_from_data(game_data['dealer_hand']).is_blackjack()
        
        if player_bj or dealer_bj:
            game_data['game_phase'] = 'game_over'
            game_data['game_over'] = True
            
            if player_bj and dealer_bj:
                game_data['result'] = 'push'
                result_msg = "🤝 Push! Both have blackjack!"
            elif player_bj:
                game_data['result'] = 'blackjack'
                result_msg = "🎉 BLACKJACK! You win!"
            else:
                game_data['result'] = 'lose'
                result_msg = "😔 Dealer has blackjack. You lose!"
            
            game_display = self._get_game_display(game_data, show_dealer_hole=True)
            welcome_msg = f"🎮 Blackjack Game Started!\n\n{game_display}\n\n{result_msg}"
            return welcome_msg, session
        
        # Normal game start
        game_display = self._get_game_display(game_data)
        welcome_msg = (
            f"🎮 Blackjack Game Started!\n\n"
            f"{game_display}\n\n"
            f"Commands: 'hit' (take card), 'stand' (keep current hand)\n"
            f"Your turn! Hit or stand?"
        )
        
        return welcome_msg, session
    
    async def process_input(self, session: GameSession, user_input: str) -> Tuple[str, bool]:
        """Process player action"""
        game_data = session.game_data
        
        if game_data['game_over']:
            return "Game is already over! Start a new game with 'blackjack'.", False
        
        action = user_input.strip().lower()
        
        if game_data['game_phase'] == 'player_turn':
            if action == 'hit':
                return await self._handle_hit(game_data)
            elif action == 'stand':
                return await self._handle_stand(game_data)
            else:
                return "Invalid action! Use 'hit' to take a card or 'stand' to keep your hand.", True
        
        elif game_data['game_phase'] == 'dealer_turn':
            return "Dealer is playing automatically. Please wait...", True
        
        else:
            return "Game is over! Start a new game with 'blackjack'.", False
    
    async def get_game_status(self, session: GameSession) -> str:
        """Get current game status"""
        game_data = session.game_data
        game_display = self._get_game_display(game_data, show_dealer_hole=game_data['game_over'])
        
        if game_data['game_over']:
            result = game_data['result']
            if result == 'blackjack':
                status = "🎉 BLACKJACK! You win!"
            elif result == 'win':
                status = "🎉 You win!"
            elif result == 'lose':
                status = "😔 You lose!"
            elif result == 'push':
                status = "🤝 Push! It's a tie!"
            else:
                status = "Game over!"
        elif game_data['game_phase'] == 'player_turn':
            status = "Your turn! Hit or stand?"
        elif game_data['game_phase'] == 'dealer_turn':
            status = "Dealer is playing..."
        else:
            status = "Game in progress"
        
        return f"🎮 Blackjack\n\n{game_display}\n\n{status}"
    
    async def get_rules(self) -> str:
        """Get game rules"""
        return (
            "📋 Blackjack Rules\n\n"
            "• Get as close to 21 as possible without going over\n"
            "• Beat the dealer's hand to win\n"
            "• Aces count as 1 or 11 (whichever is better)\n"
            "• Face cards (J, Q, K) count as 10\n"
            "• Blackjack (21 with first 2 cards) beats regular 21\n"
            "• Dealer must hit on 16 and stand on 17\n\n"
            "Commands:\n"
            "• 'hit' - Take another card\n"
            "• 'stand' - Keep current hand\n"
            "• 'quit', 'status', 'help'"
        )
    
    def _create_deck(self) -> List[Card]:
        """Create a standard 52-card deck"""
        deck = []
        for suit in self.suits:
            for rank in self.ranks:
                deck.append(Card(suit, rank))
        return deck
    
    def _hand_from_data(self, hand_data: List[Dict[str, str]]) -> BlackjackHand:
        """Convert hand data back to BlackjackHand object"""
        hand = BlackjackHand()
        for card_data in hand_data:
            hand.add_card(Card(card_data['suit'], card_data['rank']))
        return hand
    
    def _get_game_display(self, game_data: Dict[str, Any], show_dealer_hole: bool = False) -> str:
        """Get formatted game display"""
        player_hand = self._hand_from_data(game_data['player_hand'])
        dealer_hand = self._hand_from_data(game_data['dealer_hand'])
        
        # Dealer display
        if show_dealer_hole or game_data['game_over']:
            dealer_cards = str(dealer_hand)
            dealer_value = dealer_hand.value()
            dealer_display = f"Dealer: {dealer_cards} (Value: {dealer_value})"
        else:
            # Hide hole card
            visible_card = dealer_hand.cards[0]
            dealer_display = f"Dealer: {visible_card}, [Hidden]"
        
        # Player display
        player_cards = str(player_hand)
        player_value = player_hand.value()
        player_display = f"Player: {player_cards} (Value: {player_value})"
        
        return f"{dealer_display}\n{player_display}"
    
    async def _handle_hit(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle player hit action"""
        # Draw card from deck
        if not game_data['deck']:
            return "No more cards in deck! Game ends in a push.", False
        
        card_data = game_data['deck'].pop()
        game_data['player_hand'].append(card_data)
        
        player_hand = self._hand_from_data(game_data['player_hand'])
        
        if player_hand.is_bust():
            # Player busts
            game_data['game_phase'] = 'game_over'
            game_data['game_over'] = True
            game_data['result'] = 'lose'
            
            game_display = self._get_game_display(game_data, show_dealer_hole=True)
            return f"💥 BUST! You went over 21!\n\n{game_display}\n\n😔 You lose!", False
        
        elif player_hand.value() == 21:
            # Player has 21, automatically stand
            return await self._handle_stand(game_data)
        
        else:
            # Continue player turn
            game_display = self._get_game_display(game_data)
            return f"You drew {card_data['rank']}{card_data['suit']}\n\n{game_display}\n\nHit or stand?", True
    
    async def _handle_stand(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle player stand action"""
        game_data['player_stood'] = True
        game_data['game_phase'] = 'dealer_turn'
        
        # Dealer plays
        dealer_hand = self._hand_from_data(game_data['dealer_hand'])
        
        # Dealer hits on 16, stands on 17
        while dealer_hand.value() < 17:
            if not game_data['deck']:
                break
            
            card_data = game_data['deck'].pop()
            game_data['dealer_hand'].append(card_data)
            dealer_hand = self._hand_from_data(game_data['dealer_hand'])
        
        # Determine winner
        game_data['game_phase'] = 'game_over'
        game_data['game_over'] = True
        
        player_hand = self._hand_from_data(game_data['player_hand'])
        player_value = player_hand.value()
        dealer_value = dealer_hand.value()
        
        game_display = self._get_game_display(game_data, show_dealer_hole=True)
        
        if dealer_hand.is_bust():
            game_data['result'] = 'win'
            return f"💥 Dealer busts!\n\n{game_display}\n\n🎉 You win!", False
        elif player_value > dealer_value:
            game_data['result'] = 'win'
            return f"🎉 You win! {player_value} beats {dealer_value}!\n\n{game_display}", False
        elif player_value < dealer_value:
            game_data['result'] = 'lose'
            return f"😔 You lose! {dealer_value} beats {player_value}.\n\n{game_display}", False
        else:
            game_data['result'] = 'push'
            return f"🤝 Push! Both have {player_value}.\n\n{game_display}", False