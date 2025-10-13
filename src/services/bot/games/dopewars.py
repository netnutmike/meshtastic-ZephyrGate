"""
DopeWars Game Implementation

A text-based trading simulation game where players buy and sell commodities
across different locations to maximize profit within a time limit.
"""

import random
from typing import List, Tuple, Dict, Any
from .base_game import BaseGame, GameSession, GameState


class DopeWarsGame(BaseGame):
    """DopeWars trading simulation game"""
    
    def __init__(self):
        super().__init__("dopewars", timeout_minutes=30)
        
        # Game configuration
        self.starting_cash = 2000
        self.starting_debt = 5500
        self.max_days = 30
        self.max_inventory = 100
        
        # Locations
        self.locations = [
            "Bronx", "Ghetto", "Central Park", "Manhattan", "Coney Island", "Brooklyn"
        ]
        
        # Commodities with base prices and volatility
        self.commodities = {
            "Acid": {"base_price": 1000, "volatility": 0.8},
            "Cocaine": {"base_price": 15000, "volatility": 0.6},
            "Hashish": {"base_price": 480, "volatility": 0.7},
            "Heroin": {"base_price": 5500, "volatility": 0.5},
            "Ludes": {"base_price": 11, "volatility": 0.9},
            "MDA": {"base_price": 1500, "volatility": 0.7},
            "Opium": {"base_price": 540, "volatility": 0.6},
            "PCP": {"base_price": 1000, "volatility": 0.8},
            "Peyote": {"base_price": 220, "volatility": 0.9},
            "Shrooms": {"base_price": 630, "volatility": 0.8},
            "Speed": {"base_price": 90, "volatility": 0.9},
            "Weed": {"base_price": 315, "volatility": 0.8}
        }
        
        # Random events
        self.events = [
            {"type": "police", "message": "🚔 Police raid! You lost some inventory!", "effect": "lose_inventory"},
            {"type": "find", "message": "💰 You found money on the ground!", "effect": "gain_money"},
            {"type": "cheap", "message": "📉 Market crash! Prices are low!", "effect": "lower_prices"},
            {"type": "expensive", "message": "📈 Market boom! Prices are high!", "effect": "raise_prices"},
            {"type": "mugging", "message": "😱 You got mugged! Lost some cash!", "effect": "lose_money"},
            {"type": "tip", "message": "💡 Hot tip: Check the prices in other locations!", "effect": "none"}
        ]
    
    async def start_game(self, player_id: str, player_name: str, args: List[str] = None) -> Tuple[str, GameSession]:
        """Start a new DopeWars game"""
        
        # Initialize game state
        game_data = {
            'cash': self.starting_cash,
            'debt': self.starting_debt,
            'day': 1,
            'max_days': self.max_days,
            'current_location': random.choice(self.locations),
            'inventory': {},  # commodity -> quantity
            'max_inventory': self.max_inventory,
            'game_over': False,
            'final_score': 0,
            'market_prices': self._generate_market_prices(),
            'last_event': None
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
        
        status_display = self._get_status_display(game_data)
        market_display = self._get_market_display(game_data)
        
        welcome_msg = (
            f"🎮 DopeWars - Trading Simulation Started!\n\n"
            f"You have {self.max_days} days to make as much money as possible!\n"
            f"Pay off your debt and maximize your profit.\n\n"
            f"{status_display}\n\n"
            f"{market_display}\n\n"
            f"Commands: 'buy <item> <qty>', 'sell <item> <qty>', 'travel <location>', 'status', 'help'"
        )
        
        return welcome_msg, session
    
    async def process_input(self, session: GameSession, user_input: str) -> Tuple[str, bool]:
        """Process player command"""
        game_data = session.game_data
        
        if game_data['game_over']:
            return "Game is over! Start a new game with 'dopewars'.", False
        
        parts = user_input.strip().lower().split()
        if not parts:
            return "Enter a command! Type 'help' for available commands.", True
        
        command = parts[0]
        
        if command == 'buy':
            return await self._handle_buy(game_data, parts[1:])
        elif command == 'sell':
            return await self._handle_sell(game_data, parts[1:])
        elif command == 'travel':
            return await self._handle_travel(game_data, parts[1:])
        elif command == 'status':
            return await self._handle_status(game_data)
        elif command == 'market':
            return await self._handle_market(game_data)
        elif command == 'inventory':
            return await self._handle_inventory(game_data)
        elif command == 'locations':
            return await self._handle_locations(game_data)
        else:
            return "Unknown command! Type 'help' for available commands.", True
    
    async def get_game_status(self, session: GameSession) -> str:
        """Get current game status"""
        game_data = session.game_data
        
        if game_data['game_over']:
            final_score = game_data['final_score']
            net_worth = game_data['cash'] - game_data['debt']
            
            if net_worth > 0:
                result = f"🎉 Success! Final Score: ${final_score:,}"
            else:
                result = f"😔 Game Over. Final Score: ${final_score:,}"
            
            return f"🎮 DopeWars - Game Complete\n\n{result}"
        
        status_display = self._get_status_display(game_data)
        return f"🎮 DopeWars\n\n{status_display}"
    
    async def get_rules(self) -> str:
        """Get game rules"""
        return (
            "📋 DopeWars Rules\n\n"
            f"• You have {self.max_days} days to make money trading commodities\n"
            f"• Start with ${self.starting_cash:,} cash and ${self.starting_debt:,} debt\n"
            f"• Buy low, sell high across different locations\n"
            f"• Inventory limit: {self.max_inventory} items total\n"
            "• Random events can help or hurt your business\n"
            "• Goal: Pay off debt and maximize profit\n\n"
            "Commands:\n"
            "• 'buy <item> <quantity>' - Buy commodities\n"
            "• 'sell <item> <quantity>' - Sell commodities\n"
            "• 'travel <location>' - Move to new location\n"
            "• 'status' - Show current status\n"
            "• 'market' - Show current prices\n"
            "• 'inventory' - Show your inventory\n"
            "• 'locations' - List all locations"
        )
    
    def _generate_market_prices(self) -> Dict[str, Dict[str, int]]:
        """Generate random market prices for all locations"""
        prices = {}
        
        for location in self.locations:
            prices[location] = {}
            
            # Only some commodities available in each location
            available_commodities = random.sample(
                list(self.commodities.keys()), 
                random.randint(4, 8)
            )
            
            for commodity in available_commodities:
                base_price = self.commodities[commodity]["base_price"]
                volatility = self.commodities[commodity]["volatility"]
                
                # Apply random price variation
                variation = random.uniform(-volatility, volatility)
                price = int(base_price * (1 + variation))
                price = max(1, price)  # Minimum price of 1
                
                prices[location][commodity] = price
        
        return prices
    
    def _get_status_display(self, game_data: Dict[str, Any]) -> str:
        """Get formatted status display"""
        cash = game_data['cash']
        debt = game_data['debt']
        day = game_data['day']
        max_days = game_data['max_days']
        location = game_data['current_location']
        
        inventory_count = sum(game_data['inventory'].values())
        net_worth = cash - debt
        
        lines = [
            f"📍 Location: {location}",
            f"📅 Day: {day}/{max_days}",
            f"💰 Cash: ${cash:,}",
            f"💳 Debt: ${debt:,}",
            f"📊 Net Worth: ${net_worth:,}",
            f"📦 Inventory: {inventory_count}/{self.max_inventory}"
        ]
        
        if game_data.get('last_event'):
            lines.append(f"📰 {game_data['last_event']}")
        
        return "\n".join(lines)
    
    def _get_market_display(self, game_data: Dict[str, Any]) -> str:
        """Get formatted market prices display"""
        location = game_data['current_location']
        prices = game_data['market_prices'].get(location, {})
        
        if not prices:
            return f"No market data available for {location}"
        
        lines = [f"💹 Market Prices in {location}:"]
        
        for commodity, price in sorted(prices.items()):
            lines.append(f"• {commodity}: ${price:,}")
        
        return "\n".join(lines)
    
    def _get_inventory_display(self, game_data: Dict[str, Any]) -> str:
        """Get formatted inventory display"""
        inventory = game_data['inventory']
        
        if not inventory:
            return "📦 Inventory: Empty"
        
        lines = ["📦 Your Inventory:"]
        total_value = 0
        location = game_data['current_location']
        prices = game_data['market_prices'].get(location, {})
        
        for commodity, quantity in sorted(inventory.items()):
            current_price = prices.get(commodity, 0)
            value = current_price * quantity
            total_value += value
            
            lines.append(f"• {commodity}: {quantity} (worth ${value:,})")
        
        lines.append(f"Total Value: ${total_value:,}")
        return "\n".join(lines)
    
    async def _handle_buy(self, game_data: Dict[str, Any], args: List[str]) -> Tuple[str, bool]:
        """Handle buy command"""
        if len(args) < 2:
            return "Usage: buy <item> <quantity>", True
        
        commodity = args[0].title()
        try:
            quantity = int(args[1])
        except ValueError:
            return "Quantity must be a number!", True
        
        if quantity <= 0:
            return "Quantity must be positive!", True
        
        location = game_data['current_location']
        prices = game_data['market_prices'].get(location, {})
        
        if commodity not in prices:
            return f"{commodity} is not available in {location}!", True
        
        price = prices[commodity]
        total_cost = price * quantity
        
        if total_cost > game_data['cash']:
            max_affordable = game_data['cash'] // price
            return f"Not enough cash! You can afford {max_affordable} {commodity}.", True
        
        current_inventory = sum(game_data['inventory'].values())
        if current_inventory + quantity > self.max_inventory:
            available_space = self.max_inventory - current_inventory
            return f"Not enough inventory space! You can carry {available_space} more items.", True
        
        # Execute purchase
        game_data['cash'] -= total_cost
        if commodity not in game_data['inventory']:
            game_data['inventory'][commodity] = 0
        game_data['inventory'][commodity] += quantity
        
        return f"✅ Bought {quantity} {commodity} for ${total_cost:,}!", True
    
    async def _handle_sell(self, game_data: Dict[str, Any], args: List[str]) -> Tuple[str, bool]:
        """Handle sell command"""
        if len(args) < 2:
            return "Usage: sell <item> <quantity>", True
        
        commodity = args[0].title()
        try:
            quantity = int(args[1])
        except ValueError:
            return "Quantity must be a number!", True
        
        if quantity <= 0:
            return "Quantity must be positive!", True
        
        if commodity not in game_data['inventory']:
            return f"You don't have any {commodity}!", True
        
        if quantity > game_data['inventory'][commodity]:
            available = game_data['inventory'][commodity]
            return f"You only have {available} {commodity}!", True
        
        location = game_data['current_location']
        prices = game_data['market_prices'].get(location, {})
        
        if commodity not in prices:
            return f"No market for {commodity} in {location}!", True
        
        price = prices[commodity]
        total_value = price * quantity
        
        # Execute sale
        game_data['cash'] += total_value
        game_data['inventory'][commodity] -= quantity
        
        if game_data['inventory'][commodity] == 0:
            del game_data['inventory'][commodity]
        
        return f"✅ Sold {quantity} {commodity} for ${total_value:,}!", True
    
    async def _handle_travel(self, game_data: Dict[str, Any], args: List[str]) -> Tuple[str, bool]:
        """Handle travel command"""
        if not args:
            return "Usage: travel <location>", True
        
        destination = " ".join(args).title()
        
        if destination not in self.locations:
            available = ", ".join(self.locations)
            return f"Unknown location! Available: {available}", True
        
        if destination == game_data['current_location']:
            return f"You're already in {destination}!", True
        
        # Travel to new location
        game_data['current_location'] = destination
        game_data['day'] += 1
        
        # Check if game is over
        if game_data['day'] > game_data['max_days']:
            return await self._end_game(game_data)
        
        # Generate new market prices
        game_data['market_prices'] = self._generate_market_prices()
        
        # Random event chance
        if random.random() < 0.3:  # 30% chance
            event = random.choice(self.events)
            game_data['last_event'] = event['message']
            await self._apply_event(game_data, event)
        else:
            game_data['last_event'] = None
        
        status_display = self._get_status_display(game_data)
        market_display = self._get_market_display(game_data)
        
        return f"✈️ Traveled to {destination}!\n\n{status_display}\n\n{market_display}", True
    
    async def _handle_status(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle status command"""
        status_display = self._get_status_display(game_data)
        inventory_display = self._get_inventory_display(game_data)
        return f"{status_display}\n\n{inventory_display}", True
    
    async def _handle_market(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle market command"""
        market_display = self._get_market_display(game_data)
        return market_display, True
    
    async def _handle_inventory(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle inventory command"""
        inventory_display = self._get_inventory_display(game_data)
        return inventory_display, True
    
    async def _handle_locations(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle locations command"""
        current = game_data['current_location']
        locations_list = []
        
        for location in self.locations:
            if location == current:
                locations_list.append(f"• {location} (current)")
            else:
                locations_list.append(f"• {location}")
        
        return f"📍 Available Locations:\n" + "\n".join(locations_list), True
    
    async def _apply_event(self, game_data: Dict[str, Any], event: Dict[str, Any]):
        """Apply random event effects"""
        effect = event['effect']
        
        if effect == "lose_inventory":
            if game_data['inventory']:
                # Lose random portion of random commodity
                commodity = random.choice(list(game_data['inventory'].keys()))
                loss = random.randint(1, max(1, game_data['inventory'][commodity] // 2))
                game_data['inventory'][commodity] -= loss
                if game_data['inventory'][commodity] <= 0:
                    del game_data['inventory'][commodity]
        
        elif effect == "gain_money":
            bonus = random.randint(100, 1000)
            game_data['cash'] += bonus
        
        elif effect == "lose_money":
            loss = random.randint(50, min(500, game_data['cash'] // 2))
            game_data['cash'] = max(0, game_data['cash'] - loss)
        
        elif effect == "lower_prices":
            # Reduce all prices in current location by 20-40%
            location = game_data['current_location']
            if location in game_data['market_prices']:
                for commodity in game_data['market_prices'][location]:
                    reduction = random.uniform(0.2, 0.4)
                    game_data['market_prices'][location][commodity] = int(
                        game_data['market_prices'][location][commodity] * (1 - reduction)
                    )
        
        elif effect == "raise_prices":
            # Increase all prices in current location by 20-50%
            location = game_data['current_location']
            if location in game_data['market_prices']:
                for commodity in game_data['market_prices'][location]:
                    increase = random.uniform(0.2, 0.5)
                    game_data['market_prices'][location][commodity] = int(
                        game_data['market_prices'][location][commodity] * (1 + increase)
                    )
    
    async def _end_game(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """End the game and calculate final score"""
        game_data['game_over'] = True
        
        # Calculate final score
        cash = game_data['cash']
        debt = game_data['debt']
        
        # Add inventory value at current location
        inventory_value = 0
        location = game_data['current_location']
        prices = game_data['market_prices'].get(location, {})
        
        for commodity, quantity in game_data['inventory'].items():
            if commodity in prices:
                inventory_value += prices[commodity] * quantity
        
        final_score = cash + inventory_value - debt
        game_data['final_score'] = final_score
        
        # Create end game message
        if final_score > 0:
            result = f"🎉 Congratulations! You made a profit of ${final_score:,}!"
        elif final_score == 0:
            result = f"🤝 You broke even! Not bad for a first try."
        else:
            result = f"😔 You ended in debt by ${abs(final_score):,}. Better luck next time!"
        
        summary = (
            f"⏰ Time's up! Game Over!\n\n"
            f"Final Summary:\n"
            f"💰 Cash: ${cash:,}\n"
            f"📦 Inventory Value: ${inventory_value:,}\n"
            f"💳 Debt: ${debt:,}\n"
            f"📊 Final Score: ${final_score:,}\n\n"
            f"{result}"
        )
        
        return summary, False