"""
Golf Simulator Game Implementation

A golf simulation game where players play through a 9-hole course,
making club selections and dealing with various course conditions.
"""

import random
from typing import List, Tuple, Dict, Any
from .base_game import BaseGame, GameSession, GameState


class GolfSimulatorGame(BaseGame):
    """Golf simulator game implementation"""
    
    def __init__(self):
        super().__init__("golfsim", timeout_minutes=20)
        
        # Golf clubs and their characteristics
        self.clubs = {
            "driver": {"distance": 250, "accuracy": 0.6, "name": "Driver"},
            "3wood": {"distance": 220, "accuracy": 0.7, "name": "3-Wood"},
            "5iron": {"distance": 160, "accuracy": 0.8, "name": "5-Iron"},
            "7iron": {"distance": 140, "accuracy": 0.85, "name": "7-Iron"},
            "9iron": {"distance": 120, "accuracy": 0.9, "name": "9-Iron"},
            "wedge": {"distance": 80, "accuracy": 0.95, "name": "Wedge"},
            "putter": {"distance": 20, "accuracy": 0.98, "name": "Putter"}
        }
        
        # Course holes with par, distance, and hazards
        self.course = [
            {"hole": 1, "par": 4, "distance": 380, "hazards": ["water"], "description": "Dogleg right with water hazard"},
            {"hole": 2, "par": 3, "distance": 165, "hazards": ["sand"], "description": "Short par 3 with bunkers"},
            {"hole": 3, "par": 5, "distance": 520, "hazards": ["trees"], "description": "Long par 5 through trees"},
            {"hole": 4, "par": 4, "distance": 410, "hazards": ["water", "sand"], "description": "Challenging par 4 with multiple hazards"},
            {"hole": 5, "par": 3, "distance": 145, "hazards": [], "description": "Open par 3, no hazards"},
            {"hole": 6, "par": 4, "distance": 395, "hazards": ["trees"], "description": "Tree-lined fairway"},
            {"hole": 7, "par": 5, "distance": 485, "hazards": ["water"], "description": "Par 5 with water crossing"},
            {"hole": 8, "par": 4, "distance": 360, "hazards": ["sand"], "description": "Short par 4 with strategic bunkers"},
            {"hole": 9, "par": 4, "distance": 425, "hazards": ["water", "trees"], "description": "Finishing hole with water and trees"}
        ]
        
        # Weather conditions
        self.weather_conditions = {
            "calm": {"name": "☀️ Calm", "wind_factor": 1.0, "accuracy_factor": 1.0},
            "breezy": {"name": "🌤️ Breezy", "wind_factor": 0.9, "accuracy_factor": 0.95},
            "windy": {"name": "💨 Windy", "wind_factor": 0.8, "accuracy_factor": 0.85},
            "stormy": {"name": "⛈️ Stormy", "wind_factor": 0.7, "accuracy_factor": 0.7}
        }
    
    async def start_game(self, player_id: str, player_name: str, args: List[str] = None) -> Tuple[str, GameSession]:
        """Start a new Golf Simulator game"""
        
        # Generate weather for the round
        weather_key = random.choice(list(self.weather_conditions.keys()))
        weather = self.weather_conditions[weather_key]
        
        game_data = {
            'current_hole': 1,
            'total_holes': len(self.course),
            'scores': [],  # List of scores for each hole
            'current_distance': 0,  # Distance remaining to pin
            'current_strokes': 0,  # Strokes on current hole
            'total_strokes': 0,
            'weather': weather,
            'game_over': False,
            'position': 'tee',  # tee, fairway, rough, sand, water, green
            'last_shot': None,
            'hole_complete': False
        }
        
        # Set up first hole
        first_hole = self.course[0]
        game_data['current_distance'] = first_hole['distance']
        
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
        
        hole_info = self._get_hole_info(game_data)
        status_display = self._get_status_display(game_data)
        
        welcome_msg = (
            f"⛳ Golf Simulator Started!\n\n"
            f"Playing 9 holes at Mesh Valley Golf Course\n"
            f"Weather: {weather['name']}\n\n"
            f"{hole_info}\n\n"
            f"{status_display}\n\n"
            f"Select your club: driver, 3wood, 5iron, 7iron, 9iron, wedge, putter\n"
            f"Commands: '<club>', 'status', 'clubs', 'help'"
        )
        
        return welcome_msg, session
    
    async def process_input(self, session: GameSession, user_input: str) -> Tuple[str, bool]:
        """Process player club selection"""
        game_data = session.game_data
        
        if game_data['game_over']:
            return "Game is over! Start a new game with 'golfsim'.", False
        
        if game_data['hole_complete']:
            # Move to next hole
            return await self._advance_to_next_hole(game_data)
        
        club_input = user_input.strip().lower()
        
        if club_input == 'status':
            return await self._handle_status(game_data)
        elif club_input == 'clubs':
            return await self._handle_clubs(game_data)
        elif club_input == 'scorecard':
            return await self._handle_scorecard(game_data)
        elif club_input in self.clubs:
            return await self._handle_shot(game_data, club_input)
        else:
            available_clubs = ", ".join(self.clubs.keys())
            return f"Unknown club! Available clubs: {available_clubs}", True
    
    async def get_game_status(self, session: GameSession) -> str:
        """Get current game status"""
        game_data = session.game_data
        
        if game_data['game_over']:
            total_strokes = game_data['total_strokes']
            total_par = sum(hole['par'] for hole in self.course)
            score_vs_par = total_strokes - total_par
            
            if score_vs_par < 0:
                result = f"🏆 Excellent! {abs(score_vs_par)} under par!"
            elif score_vs_par == 0:
                result = f"👏 Great round! Even par!"
            else:
                result = f"🙂 Good effort! {score_vs_par} over par"
            
            return f"⛳ Golf Simulator - Round Complete\n\nTotal Score: {total_strokes}\n{result}"
        
        hole_info = self._get_hole_info(game_data)
        status_display = self._get_status_display(game_data)
        
        return f"⛳ Golf Simulator\n\n{hole_info}\n\n{status_display}"
    
    async def get_rules(self) -> str:
        """Get game rules"""
        return (
            "📋 Golf Simulator Rules\n\n"
            "• Play through 9 holes of golf\n"
            "• Select appropriate clubs for each shot\n"
            "• Try to get the ball in the hole in as few strokes as possible\n"
            "• Weather affects distance and accuracy\n"
            "• Different lies (fairway, rough, sand) affect your shots\n"
            "• Avoid hazards like water and sand traps\n\n"
            "Clubs (distance/accuracy):\n"
            "• Driver: Long distance, less accurate\n"
            "• 3-Wood: Good distance, moderate accuracy\n"
            "• Irons (5,7,9): Medium distance, good accuracy\n"
            "• Wedge: Short distance, very accurate\n"
            "• Putter: Very short, extremely accurate (greens only)\n\n"
            "Commands: '<club>', 'status', 'clubs', 'scorecard'"
        )
    
    def _get_hole_info(self, game_data: Dict[str, Any]) -> str:
        """Get current hole information"""
        hole_num = game_data['current_hole']
        hole = self.course[hole_num - 1]
        
        lines = [
            f"🏌️ Hole {hole['hole']} - Par {hole['par']} ({hole['distance']} yards)",
            f"📝 {hole['description']}"
        ]
        
        if hole['hazards']:
            hazard_icons = {"water": "💧", "sand": "🏖️", "trees": "🌳"}
            hazard_list = [f"{hazard_icons.get(h, '⚠️')} {h.title()}" for h in hole['hazards']]
            lines.append(f"⚠️ Hazards: {', '.join(hazard_list)}")
        
        return "\n".join(lines)
    
    def _get_status_display(self, game_data: Dict[str, Any]) -> str:
        """Get current status display"""
        lines = [
            f"📍 Distance to pin: {game_data['current_distance']} yards",
            f"🏌️ Strokes this hole: {game_data['current_strokes']}",
            f"📊 Total strokes: {game_data['total_strokes']}",
            f"🌤️ Weather: {game_data['weather']['name']}",
            f"📍 Position: {game_data['position'].title()}"
        ]
        
        if game_data['last_shot']:
            lines.append(f"⛳ Last shot: {game_data['last_shot']}")
        
        return "\n".join(lines)
    
    def _get_clubs_display(self, game_data: Dict[str, Any]) -> str:
        """Get clubs information display"""
        weather = game_data['weather']
        position = game_data['position']
        
        lines = ["🏌️ Available Clubs:"]
        
        for club_key, club_info in self.clubs.items():
            # Adjust distance for weather and position
            base_distance = club_info['distance']
            adjusted_distance = int(base_distance * weather['wind_factor'])
            
            # Position adjustments
            if position == 'rough':
                adjusted_distance = int(adjusted_distance * 0.8)
            elif position == 'sand':
                adjusted_distance = int(adjusted_distance * 0.6)
            
            accuracy = int(club_info['accuracy'] * 100)
            lines.append(f"• {club_key}: {club_info['name']} (~{adjusted_distance}y, {accuracy}% accuracy)")
        
        return "\n".join(lines)
    
    def _get_scorecard_display(self, game_data: Dict[str, Any]) -> str:
        """Get scorecard display"""
        if not game_data['scores']:
            return "📊 Scorecard: No holes completed yet"
        
        lines = ["📊 Scorecard:"]
        total_strokes = 0
        total_par = 0
        
        for i, score in enumerate(game_data['scores']):
            hole = self.course[i]
            par = hole['par']
            total_strokes += score
            total_par += par
            
            score_vs_par = score - par
            if score_vs_par == -2:
                result = "🦅 Eagle"
            elif score_vs_par == -1:
                result = "🐦 Birdie"
            elif score_vs_par == 0:
                result = "⚪ Par"
            elif score_vs_par == 1:
                result = "🟡 Bogey"
            else:
                result = f"🔴 +{score_vs_par}"
            
            lines.append(f"Hole {hole['hole']}: {score} (Par {par}) {result}")
        
        overall_vs_par = total_strokes - total_par
        if overall_vs_par < 0:
            overall_result = f"{abs(overall_vs_par)} under par"
        elif overall_vs_par == 0:
            overall_result = "Even par"
        else:
            overall_result = f"{overall_vs_par} over par"
        
        lines.append(f"\nTotal: {total_strokes} ({overall_result})")
        return "\n".join(lines)
    
    async def _handle_status(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle status command"""
        hole_info = self._get_hole_info(game_data)
        status_display = self._get_status_display(game_data)
        return f"{hole_info}\n\n{status_display}", True
    
    async def _handle_clubs(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle clubs command"""
        clubs_display = self._get_clubs_display(game_data)
        return clubs_display, True
    
    async def _handle_scorecard(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Handle scorecard command"""
        scorecard_display = self._get_scorecard_display(game_data)
        return scorecard_display, True
    
    async def _handle_shot(self, game_data: Dict[str, Any], club_key: str) -> Tuple[str, bool]:
        """Handle taking a shot with selected club"""
        club = self.clubs[club_key]
        weather = game_data['weather']
        position = game_data['position']
        distance_to_pin = game_data['current_distance']
        
        # Special case: putter only works on green
        if club_key == 'putter' and position != 'green':
            return "❌ You can only use the putter on the green!", True
        
        # Calculate shot distance
        base_distance = club['distance']
        
        # Apply weather effects
        shot_distance = base_distance * weather['wind_factor']
        
        # Apply position effects
        if position == 'rough':
            shot_distance *= 0.8
        elif position == 'sand':
            shot_distance *= 0.6
        
        # Add random variation
        distance_variation = random.uniform(0.8, 1.2)
        shot_distance = int(shot_distance * distance_variation)
        
        # Calculate accuracy
        base_accuracy = club['accuracy']
        accuracy = base_accuracy * weather['accuracy_factor']
        
        # Position affects accuracy
        if position == 'rough':
            accuracy *= 0.9
        elif position == 'sand':
            accuracy *= 0.8
        
        # Determine if shot is accurate
        is_accurate = random.random() < accuracy
        
        # Update strokes
        game_data['current_strokes'] += 1
        game_data['total_strokes'] += 1
        
        # Calculate result
        if club_key == 'putter':
            # Putting logic
            if distance_to_pin <= 20 and is_accurate:
                # Successful putt
                game_data['current_distance'] = 0
                game_data['hole_complete'] = True
                game_data['last_shot'] = f"Great putt! Ball is in the hole!"
                
                # Record score for this hole
                game_data['scores'].append(game_data['current_strokes'])
                
                return await self._complete_hole(game_data)
            else:
                # Missed putt
                remaining = random.randint(1, 8)
                game_data['current_distance'] = remaining
                game_data['last_shot'] = f"Putt missed by {remaining} feet"
                
                status = self._get_status_display(game_data)
                return f"⛳ {game_data['last_shot']}\n\n{status}\n\nSelect your next club:", True
        
        else:
            # Regular shot logic
            if shot_distance >= distance_to_pin:
                # Shot reaches or passes the green
                if is_accurate:
                    # Good shot - lands on green
                    remaining = random.randint(5, 25)
                    game_data['current_distance'] = remaining
                    game_data['position'] = 'green'
                    game_data['last_shot'] = f"Great shot with {club['name']}! On the green, {remaining} feet from pin"
                else:
                    # Inaccurate shot - might hit hazard or rough
                    hazard_hit = self._check_hazard_hit(game_data)
                    if hazard_hit:
                        return await self._handle_hazard(game_data, hazard_hit, club['name'])
                    else:
                        # Lands in rough near green
                        remaining = random.randint(20, 50)
                        game_data['current_distance'] = remaining
                        game_data['position'] = 'rough'
                        game_data['last_shot'] = f"Shot with {club['name']} went wide, in the rough {remaining} yards from pin"
            else:
                # Shot doesn't reach green
                remaining = distance_to_pin - shot_distance
                game_data['current_distance'] = remaining
                
                if is_accurate:
                    game_data['position'] = 'fairway'
                    game_data['last_shot'] = f"Good shot with {club['name']}! {remaining} yards remaining, in the fairway"
                else:
                    # Check for hazards
                    hazard_hit = self._check_hazard_hit(game_data)
                    if hazard_hit:
                        return await self._handle_hazard(game_data, hazard_hit, club['name'])
                    else:
                        game_data['position'] = 'rough'
                        game_data['last_shot'] = f"Shot with {club['name']} went into the rough, {remaining} yards remaining"
        
        # Continue hole
        status = self._get_status_display(game_data)
        return f"⛳ {game_data['last_shot']}\n\n{status}\n\nSelect your next club:", True
    
    def _check_hazard_hit(self, game_data: Dict[str, Any]) -> str:
        """Check if shot hits a hazard"""
        hole_num = game_data['current_hole']
        hole = self.course[hole_num - 1]
        hazards = hole['hazards']
        
        if not hazards:
            return None
        
        # 20% chance of hitting hazard on inaccurate shot
        if random.random() < 0.2:
            return random.choice(hazards)
        
        return None
    
    async def _handle_hazard(self, game_data: Dict[str, Any], hazard: str, club_name: str) -> Tuple[str, bool]:
        """Handle hitting a hazard"""
        if hazard == 'water':
            # Water hazard - penalty stroke and drop
            game_data['current_strokes'] += 1  # Penalty stroke
            game_data['total_strokes'] += 1
            game_data['position'] = 'rough'
            # Add some distance back
            game_data['current_distance'] += random.randint(30, 60)
            game_data['last_shot'] = f"💧 Shot with {club_name} went in the water! Penalty stroke, dropping in rough"
            
        elif hazard == 'sand':
            # Sand trap
            game_data['position'] = 'sand'
            game_data['last_shot'] = f"🏖️ Shot with {club_name} landed in a sand trap!"
            
        elif hazard == 'trees':
            # Trees - difficult lie
            game_data['position'] = 'rough'
            game_data['current_distance'] += random.randint(10, 30)
            game_data['last_shot'] = f"🌳 Shot with {club_name} hit the trees! Difficult lie in the rough"
        
        status = self._get_status_display(game_data)
        return f"⛳ {game_data['last_shot']}\n\n{status}\n\nSelect your next club:", True
    
    async def _complete_hole(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Complete the current hole"""
        hole_num = game_data['current_hole']
        hole = self.course[hole_num - 1]
        strokes = game_data['current_strokes']
        par = hole['par']
        
        # Determine score description
        score_vs_par = strokes - par
        if score_vs_par == -2:
            score_desc = "🦅 EAGLE! Amazing!"
        elif score_vs_par == -1:
            score_desc = "🐦 Birdie! Great job!"
        elif score_vs_par == 0:
            score_desc = "⚪ Par. Well played!"
        elif score_vs_par == 1:
            score_desc = "🟡 Bogey. Not bad!"
        elif score_vs_par == 2:
            score_desc = "🟠 Double bogey."
        else:
            score_desc = f"🔴 {score_vs_par} over par."
        
        result_msg = f"🏌️ Hole {hole_num} Complete!\n\nScore: {strokes} (Par {par})\n{score_desc}"
        
        # Check if round is complete
        if hole_num >= len(self.course):
            game_data['game_over'] = True
            total_strokes = game_data['total_strokes']
            total_par = sum(h['par'] for h in self.course)
            final_score = total_strokes - total_par
            
            if final_score < 0:
                final_desc = f"🏆 Outstanding! {abs(final_score)} under par!"
            elif final_score == 0:
                final_desc = f"👏 Excellent! Even par!"
            else:
                final_desc = f"🙂 Good round! {final_score} over par."
            
            scorecard = self._get_scorecard_display(game_data)
            
            final_msg = f"{result_msg}\n\n🏁 Round Complete!\nTotal Score: {total_strokes}\n{final_desc}\n\n{scorecard}"
            return final_msg, False
        
        else:
            game_data['hole_complete'] = True
            return f"{result_msg}\n\nPress any key to continue to the next hole...", True
    
    async def _advance_to_next_hole(self, game_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Advance to the next hole"""
        game_data['current_hole'] += 1
        game_data['current_strokes'] = 0
        game_data['hole_complete'] = False
        game_data['position'] = 'tee'
        game_data['last_shot'] = None
        
        # Set up new hole
        hole = self.course[game_data['current_hole'] - 1]
        game_data['current_distance'] = hole['distance']
        
        hole_info = self._get_hole_info(game_data)
        status_display = self._get_status_display(game_data)
        
        return f"⛳ Next Hole!\n\n{hole_info}\n\n{status_display}\n\nSelect your club:", True