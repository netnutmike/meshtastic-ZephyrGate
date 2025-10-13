"""
Lemonade Stand Game Implementation

A business simulation game where players run a lemonade stand,
making decisions about pricing, inventory, and advertising to maximize profit.
"""

import random
from typing import List, Tuple, Dict, Any
from .base_game import BaseGame, GameSession, GameState


class LemonadeStandGame(BaseGame):
    """Lemonade Stand business simulation game"""
    
    def __init__(self):
        super().__init__("lemonstand", timeout_minutes=25)
        
        # Game configuration
        self.starting_money = 200  # Starting capital
        self.max_days = 30
        self.lemon_cost = 2  # Cost per lemon
        self.sugar_cost = 4  # Cost per cup of sugar
        self.cup_cost = 1   # Cost per cup
        self.sign_cost = 15  # Cost per advertising sign
        
        # Weather types and their effects on sales
        self.weather_types = {
            "sunny": {"name": "☀️ Sunny", "demand_multiplier": 1.5, "probability": 0.4},
            "cloudy": {"name": "☁️ Cloudy", "demand_multiplier": 1.0, "probability": 0.3},
            "rainy": {"name": "🌧️ Rainy", "demand_multiplier": 0.3, "probability": 0.2},
            "hot": {"name": "🔥 Hot", "demand_multiplier": 2.0, "probability": 0.1}
        }
    
    async def start_game(self, player_id: str, player_name: str, args: List[str] = None) -> Tuple[str, GameSession]:
        """Start a new Lemonade Stand game"""
        
        game_data = {
            'money': self.starting_money,
            'day': 1,
            'max_days': self.max_days,
            'total_profit': 0,
            'reputation': 50,  # 0-100 scale
            'game_over': False,
            
            # Daily inventory
            'lemons': 0,
            'sugar': 0,
            'cups': 0,
            'signs': 0,
            
            # Daily settings
            'price': 0.25,  # Price per cup
            'recipe_lemons': 2,  # Lemons per pitcher (affects taste)
            'recipe_sugar': 1,   # Sugar per pitcher (affects taste)
            
            # Daily results
            'weather': None,
            'customers': 0,
            'cups_sold': 0,
            'daily_revenue': 0,
            'daily_profit': 0,
            'daily_expenses': 0,
            
            # Game history
            'history': []
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
        
        welcome_msg = (
            f"🍋 Lemonade Stand Business Started!\n\n"
            f"You have ${self.starting_money} to start your lemonade business.\n"
            f"Run your stand for {self.max_days} days and maximize your profit!\n\n"
            f"{status_display}\n\n"
            f"📋 Daily Process:\n"
            f"1. Buy supplies (lemons, sugar, cups, signs)\n"
            f"2. Set your recipe and price\n"
            f"3. Open your stand for the day\n\n"
            f"Commands: 'buy', 'recipe', 'price', 'open', 'status', 'help'"
        )
        
        return welcome_msg, session
    
    async def process_input(self, session: GameSession, user_input: str) -> Tuple[str, bool]:
        """Process player command"""
        game_data = session.game_data
        
        if game_data['game_over']:
            return "Game is over! Start a new game with 'lemonstand'.", False
        
        parts = user_input.strip().lower().split()
        if not parts:
            return "Enter a command! Type 'help' for available commands.", True
        
        command = parts[0]
        
        if command == 'buy':
            return await self._handle_buy(game_data, parts[1:])
        elif command == 'recipe':
            return await self._handle_recipe(game_data, parts[1:])
        elif command == 'price':
            return await self._handle_price(game_data, parts[1:])
        elif command == 'open':
            return await self._handle_open_stand(game_data)
        elif command == 'status':
            return await self._handle_status(game_data)
        elif command == 'history':
            return await self._handle_history(game_data)
        elif command == 'supplies':
            return await self._handle_supplies(game_data)
        else:
            return "Unknown command! Type 'help' for available commands.", True
    
    async def get_game_status(self, session: GameSession) -> str:
        """Get current game status"""
        game_data = session.game_data
        
        if game_data['game_over']:
            total_profit = game_data['total_profit']
            if total_profit > 0:
                result = f"🎉 Success! Total Profit: ${total_profit:.2f}"
            else:
                result = f"😔 Loss: ${total_profit:.2f}"
            
            return f"🍋 Lemonade Stand - Game Complete\n\n{result}"
        
        status_display = self._get_status_display(game_data)
        return f"🍋 Lemonade Stand\n\n{status_display}"
    
    async def get_rules(self) -> str:
        """Get game rules"""
        return (
            "📋 Lemonade Stand Rules\n\n"
            f"• Run your stand for {self.max_days} days\n"
            f"• Start with ${self.starting_money} capital\n"
            "• Buy supplies, set recipe and price, then open\n"
            "• Weather affects customer demand\n"
            "• Recipe affects taste and customer satisfaction\n"
            "• Price affects sales volume\n"
            "• Build reputation for repeat customers\n\n"
            "Supply Costs:\n"
            f"• Lemons: ${self.lemon_cost} each\n"
            f"• Sugar: ${self.sugar_cost} per cup\n"
            f"• Cups: ${self.cup_cost} each\n"
            f"• Signs: ${self.sign_cost} each (advertising)\n\n"
            "Commands:\n"
            "• 'buy <item> <quantity>' - Buy supplies\n"
            "• 'recipe <lemons> <sugar>' - Set recipe per pitcher\n"
            "• 'price <amount>' - Set price per cup\n"
            "• 'open' - Open stand for the day\n"
            "• 'status' - Show current status\n"
            "• 'supplies' - Show supply costs\n"
            "• 'history' - Show daily history"
        )
    
    def _get_status_display(self, game_data: Dict[str, Any]) -> str:
        """Get formatted status display"""
        lines = [
            f"📅 Day: {game_data['day']}/{game_data['max_days']}",
            f"💰 Money: ${game_data['money']:.2f}",
            f"📊 Total Profit: ${game_data['total_profit']:.2f}",
            f"⭐ Reputation: {game_data['reputation']}/100",
            "",
            f"📦 Inventory:",
            f"  🍋 Lemons: {game_data['lemons']}",
            f"  🍯 Sugar: {game_data['sugar']} cups",
            f"  🥤 Cups: {game_data['cups']}",
            f"  📢 Signs: {game_data['signs']}",
            "",
            f"⚙️ Current Settings:",
            f"  Recipe: {game_data['recipe_lemons']} lemons, {game_data['recipe_sugar']} sugar per pitcher",
            f"  Price: ${game_data['price']:.2f} per cup"
        ]
        
        if game_data['weather']:
            lines.insert(4, f"🌤️ Weather: {game_data['weather']}")
        
        return "\n".join(lines)
    
    def _get_supplies_display(self, game_data: Dict[str, Any]) -> str:
        """Get supply costs display"""
        return (
            f"🛒 Supply Costs:\n"
            f"• Lemons: ${self.lemon_cost} each\n"
            f"• Sugar: ${self.sugar_cost} per cup\n"
            f"• Cups: ${self.cup_cost} each\n"
            f"• Signs: ${self.sign_cost} each (advertising)\n\n"
            f"Your money: ${game_data['money']:.2f}"
        )
    
    async def _handle_buy(self, game_data: Dict[str, Any], args: List[str]) -> Tuple[str, bool]:
        """Handle buy command"""
        if len(args) < 2:
            return "Usage: buy <item> <quantity>\nItems: lemons, sugar, cups, signs", True
        
        item = args[0].lower()
        try:
            quantity = int(args[1])
        except ValueError:
            return "Quantity must be a number!", True
        
        if quantity <= 0:
            return "Quantity must be positive!", True
        
        # Define costs
        costs = {
            'lemons': self.lemon_cost,
            'sugar': self.sugar_cost,
            'cups': self.cup_cost,
            'signs': self.sign_cost
        }
        
        if item not in costs:
            return "Unknown item! Available: lemons, sugar, cups, signs", True
        
        total_cost = costs[item] * quantity
        
        if total_cost > game_data['money']:
            max_affordable = int(game_data['money'] // costs[item])
            return f"Not enough money! You can afford {max_affordable} {item}.", True
        
        # Execute purchase
        game_data['money'] -= total_cost
        game_data[item] += quantity
        
        return f"✅ Bought {quantity} {item} for ${total_cost:.2f}!", True
    
    async def _handle_recipe(self, game_data: Dict[str, Any], args: List[str]) -> Tuple[str, bool]:
        """Handle recipe command"""
        if len(args) < 2:
            return "Usage: recipe <lemons> <sugar>\nExample: recipe 3 2", True
        
        try:
            lemons = int(args[0])
            sugar = int(args[1])
        except ValueError:
            return "Recipe amounts must be numbers!", True
        
        if lemons < 1 or lemons > 10:
            return "Lemons per pitcher must be 1-10!", True
        
        if sugar < 1 or sugar > 5:
            return "Sugar per pitcher must be 1-5!", True
        
        game_data['recipe_lemons'] = lemons
        game_data['recipe_sugar'] = sugar
        
        # Calculate taste quality
        taste_score = self._calculate_taste_quality(lemons, sugar)
        taste_desc = self._get_taste_description(taste_score)
        
        return f"✅ Recipe set: {lemons} lemons, {sugar} sugar per pitcher\nTaste: {taste_desc}", True
    
    async def _handle_price(self, game_data: Dict[str, Any], args: List[str]) -> Tuple[str, bool]:
        """Handle price command"""
        if not args:
            return f"Usage: price <amount>\nCurrent price: ${game_data['price']:.2f}", True
        
        try:
            price = float(args[0])
        except ValueError:
            return "Price must be a number!", True
        
        if price < 0.05:
            return "Price must be at least $0.05!", True
        
        if price > 5.00:
            return "Price cannot exceed $5.00!", True
        
        game_data['price'] = round(price, 2)
        
        return f"✅ Price set to ${game_data['price']:.2f} per cup", True
    
    async def _handle_open_stand(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle opening the stand for the day"""
        # Check if we have minimum supplies
        if game_data['cups'] == 0:
            return "❌ You need cups to serve lemonade! Buy some cups first.", True
        
        if game_data['lemons'] < game_data['recipe_lemons']:
            return f"❌ You need {game_data['recipe_lemons']} lemons for your recipe! You have {game_data['lemons']}.", True
        
        if game_data['sugar'] < game_data['recipe_sugar']:
            return f"❌ You need {game_data['recipe_sugar']} sugar for your recipe! You have {game_data['sugar']}.", True
        
        # Generate weather for the day
        weather_key = self._generate_weather()
        weather_info = self.weather_types[weather_key]
        game_data['weather'] = weather_info['name']
        
        # Calculate how many pitchers we can make
        max_pitchers_lemons = game_data['lemons'] // game_data['recipe_lemons']
        max_pitchers_sugar = game_data['sugar'] // game_data['recipe_sugar']
        max_pitchers = min(max_pitchers_lemons, max_pitchers_sugar)
        
        # Each pitcher makes 8 cups
        cups_per_pitcher = 8
        max_cups_from_recipe = max_pitchers * cups_per_pitcher
        max_cups = min(max_cups_from_recipe, game_data['cups'])
        
        if max_cups == 0:
            return "❌ You can't make any lemonade with your current supplies!", True
        
        # Simulate the day
        result = await self._simulate_day(game_data, max_cups, weather_info)
        
        # Advance to next day
        game_data['day'] += 1
        
        # Check if game is over
        if game_data['day'] > game_data['max_days']:
            game_data['game_over'] = True
            final_msg = result + f"\n\n🏁 Game Complete! Final profit: ${game_data['total_profit']:.2f}"
            return final_msg, False
        
        return result, True
    
    async def _handle_status(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle status command"""
        status_display = self._get_status_display(game_data)
        return status_display, True
    
    async def _handle_supplies(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle supplies command"""
        supplies_display = self._get_supplies_display(game_data)
        return supplies_display, True
    
    async def _handle_history(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle history command"""
        history = game_data.get('history', [])
        
        if not history:
            return "📊 No history yet. Open your stand to start making sales!", True
        
        lines = ["📊 Daily History:"]
        for day_data in history[-7:]:  # Show last 7 days
            lines.append(
                f"Day {day_data['day']}: {day_data['weather']} | "
                f"Sold {day_data['cups_sold']} cups | "
                f"Profit: ${day_data['profit']:.2f}"
            )
        
        return "\n".join(lines), True
    
    def _generate_weather(self) -> str:
        """Generate random weather for the day"""
        rand = random.random()
        cumulative = 0
        
        for weather_key, weather_info in self.weather_types.items():
            cumulative += weather_info['probability']
            if rand <= cumulative:
                return weather_key
        
        return "cloudy"  # Default fallback
    
    def _calculate_taste_quality(self, lemons: int, sugar: int) -> float:
        """Calculate taste quality score (0-1)"""
        # Optimal recipe is around 3 lemons, 2 sugar
        optimal_lemons = 3
        optimal_sugar = 2
        
        lemon_score = 1.0 - abs(lemons - optimal_lemons) * 0.15
        sugar_score = 1.0 - abs(sugar - optimal_sugar) * 0.2
        
        taste_score = (lemon_score + sugar_score) / 2
        return max(0.1, min(1.0, taste_score))
    
    def _get_taste_description(self, taste_score: float) -> str:
        """Get taste description from score"""
        if taste_score >= 0.9:
            return "🌟 Perfect!"
        elif taste_score >= 0.7:
            return "😋 Delicious"
        elif taste_score >= 0.5:
            return "🙂 Good"
        elif taste_score >= 0.3:
            return "😐 Okay"
        else:
            return "😝 Needs work"
    
    async def _simulate_day(self, game_data: Dict[str, Any], max_cups: int, weather_info: Dict[str, Any]) -> str:
        """Simulate a day of business"""
        # Calculate base demand
        base_customers = random.randint(20, 50)
        
        # Apply weather multiplier
        weather_customers = int(base_customers * weather_info['demand_multiplier'])
        
        # Apply advertising effect (signs)
        advertising_boost = min(game_data['signs'] * 0.1, 0.5)  # Max 50% boost
        total_customers = int(weather_customers * (1 + advertising_boost))
        
        # Apply reputation effect
        reputation_multiplier = 0.5 + (game_data['reputation'] / 100) * 0.5
        total_customers = int(total_customers * reputation_multiplier)
        
        # Calculate taste quality
        taste_score = self._calculate_taste_quality(game_data['recipe_lemons'], game_data['recipe_sugar'])
        
        # Price sensitivity - higher prices reduce demand
        price_sensitivity = max(0.2, 1.0 - (game_data['price'] - 0.25) * 0.5)
        
        # Calculate actual sales
        potential_sales = int(total_customers * price_sensitivity * taste_score)
        actual_sales = min(potential_sales, max_cups)
        
        # Use up supplies
        pitchers_used = (actual_sales + 7) // 8  # Round up
        lemons_used = pitchers_used * game_data['recipe_lemons']
        sugar_used = pitchers_used * game_data['recipe_sugar']
        
        game_data['lemons'] -= lemons_used
        game_data['sugar'] -= sugar_used
        game_data['cups'] -= actual_sales
        
        # Calculate financials
        revenue = actual_sales * game_data['price']
        expenses = (lemons_used * self.lemon_cost + 
                   sugar_used * self.sugar_cost + 
                   actual_sales * self.cup_cost)
        profit = revenue - expenses
        
        # Update game state
        game_data['money'] += profit
        game_data['total_profit'] += profit
        
        # Update reputation based on taste and price
        reputation_change = 0
        if taste_score > 0.7 and game_data['price'] < 1.0:
            reputation_change = random.randint(1, 3)
        elif taste_score < 0.4 or game_data['price'] > 2.0:
            reputation_change = random.randint(-3, -1)
        
        game_data['reputation'] = max(0, min(100, game_data['reputation'] + reputation_change))
        
        # Store daily results
        daily_result = {
            'day': game_data['day'],
            'weather': weather_info['name'],
            'customers': total_customers,
            'cups_sold': actual_sales,
            'revenue': revenue,
            'expenses': expenses,
            'profit': profit
        }
        
        if 'history' not in game_data:
            game_data['history'] = []
        game_data['history'].append(daily_result)
        
        # Create result message
        result_lines = [
            f"🍋 Day {game_data['day']} Results:",
            f"🌤️ Weather: {weather_info['name']}",
            f"👥 Customers: {total_customers}",
            f"🥤 Cups sold: {actual_sales}/{max_cups}",
            f"💰 Revenue: ${revenue:.2f}",
            f"💸 Expenses: ${expenses:.2f}",
            f"📊 Profit: ${profit:.2f}",
            f"⭐ Reputation: {game_data['reputation']}/100"
        ]
        
        if reputation_change != 0:
            change_str = f"+{reputation_change}" if reputation_change > 0 else str(reputation_change)
            result_lines.append(f"📈 Reputation change: {change_str}")
        
        result_lines.append(f"\n💰 Total money: ${game_data['money']:.2f}")
        result_lines.append(f"📊 Total profit: ${game_data['total_profit']:.2f}")
        
        return "\n".join(result_lines)