"""
Educational and Reference Features Service

Implements educational content and reference information services:
- Ham radio test question system with FCC question pools
- Interactive quiz system with scoring and leaderboards
- Survey system with custom survey support
- Reference data commands (solar, earthquake, etc.)

Requirements: 4.2.1, 4.2.2, 4.2.3, 4.2.4, 4.2.5
"""

import json
import logging
import random
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from core.database import get_database


@dataclass
class HamQuestion:
    """Ham radio test question"""
    id: str
    question: str
    options: List[str]
    correct: int
    explanation: str


@dataclass
class QuizQuestion:
    """Quiz question"""
    id: str
    category: str
    question: str
    options: List[str]
    correct: int
    explanation: str


@dataclass
class SurveyQuestion:
    """Survey question"""
    id: int
    type: str  # multiple_choice, text, rating, yes_no
    question: str
    options: Optional[List[str]] = None
    required: bool = True
    max_length: Optional[int] = None
    scale: Optional[int] = None


@dataclass
class Survey:
    """Survey definition"""
    id: str
    title: str
    description: str
    active: bool
    created_date: str
    expires_date: str
    questions: List[SurveyQuestion]


@dataclass
class UserSession:
    """User session for quizzes/surveys"""
    user_id: str
    session_type: str  # 'hamtest', 'quiz', 'survey'
    session_id: str
    current_question: int
    questions: List[Any]
    answers: List[Any]
    score: int
    started_at: datetime
    category: Optional[str] = None
    survey_id: Optional[str] = None


@dataclass
class LeaderboardEntry:
    """Leaderboard entry"""
    user_id: str
    user_name: str
    category: str
    score: int
    total_questions: int
    percentage: float
    date: datetime


class EducationalService:
    """
    Educational and reference features service
    """
    
    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Data storage
        self.ham_questions: Dict[str, List[HamQuestion]] = {}
        self.quiz_questions: Dict[str, List[QuizQuestion]] = {}
        self.surveys: Dict[str, Survey] = {}
        
        # Active sessions
        self.active_sessions: Dict[str, UserSession] = {}
        
        # Leaderboards
        self.leaderboards: Dict[str, List[LeaderboardEntry]] = {}
        
        # Configuration
        self.data_dir = Path(self.config.get('data_dir', 'data'))
        self.session_timeout = self.config.get('session_timeout_minutes', 30)
        self.max_questions_per_session = self.config.get('max_questions_per_session', 10)
        
        # Initialize database tables
        self._initialize_database()
        
        # Load data
        self._load_ham_questions()
        self._load_quiz_questions()
        self._load_surveys()
        self._load_leaderboards()
    
    def _initialize_database(self):
        """Initialize database tables for educational features"""
        try:
            db = get_database()
            cursor = db.cursor()
            
            # Ham test sessions and scores
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ham_test_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    license_level TEXT NOT NULL,
                    questions_asked INTEGER DEFAULT 0,
                    correct_answers INTEGER DEFAULT 0,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    score_percentage REAL,
                    passed BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES users (node_id)
                )
            """)
            
            # Quiz sessions and scores
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quiz_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    category TEXT NOT NULL,
                    questions_asked INTEGER DEFAULT 0,
                    correct_answers INTEGER DEFAULT 0,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    score_percentage REAL,
                    FOREIGN KEY (user_id) REFERENCES users (node_id)
                )
            """)
            
            # Survey responses
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS survey_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    survey_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    question_id INTEGER NOT NULL,
                    response TEXT NOT NULL,
                    submitted_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (node_id)
                )
            """)
            
            # Survey sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS survey_sessions (
                    id TEXT PRIMARY KEY,
                    survey_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    questions_answered INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (node_id)
                )
            """)
            
            db.commit()
            self.logger.info("Educational service database tables initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing educational database: {e}")
    
    def _load_ham_questions(self):
        """Load ham radio test questions from JSON files"""
        try:
            ham_dir = self.data_dir / 'hamradio'
            if not ham_dir.exists():
                self.logger.warning(f"Ham radio data directory not found: {ham_dir}")
                return
            
            for level in ['technician', 'general', 'extra']:
                file_path = ham_dir / f'{level}.json'
                if file_path.exists():
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        questions = []
                        for q_data in data:
                            question = HamQuestion(
                                id=q_data['id'],
                                question=q_data['question'],
                                options=q_data['options'],
                                correct=q_data['correct'],
                                explanation=q_data['explanation']
                            )
                            questions.append(question)
                        self.ham_questions[level] = questions
                        self.logger.info(f"Loaded {len(questions)} {level} ham questions")
                else:
                    self.logger.warning(f"Ham radio file not found: {file_path}")
                    
        except Exception as e:
            self.logger.error(f"Error loading ham questions: {e}")
    
    def _load_quiz_questions(self):
        """Load quiz questions from JSON file"""
        try:
            quiz_file = self.data_dir / 'quiz_questions.json'
            if not quiz_file.exists():
                self.logger.warning(f"Quiz questions file not found: {quiz_file}")
                return
            
            with open(quiz_file, 'r') as f:
                data = json.load(f)
                
                for category_data in data:
                    category = category_data['category']
                    questions = []
                    
                    for q_data in category_data['questions']:
                        question = QuizQuestion(
                            id=q_data['id'],
                            category=category,
                            question=q_data['question'],
                            options=q_data['options'],
                            correct=q_data['correct'],
                            explanation=q_data['explanation']
                        )
                        questions.append(question)
                    
                    self.quiz_questions[category] = questions
                    self.logger.info(f"Loaded {len(questions)} {category} quiz questions")
                    
        except Exception as e:
            self.logger.error(f"Error loading quiz questions: {e}")
    
    def _load_surveys(self):
        """Load surveys from JSON files"""
        try:
            surveys_dir = self.data_dir / 'surveys'
            if not surveys_dir.exists():
                self.logger.warning(f"Surveys directory not found: {surveys_dir}")
                return
            
            for survey_file in surveys_dir.glob('*.json'):
                try:
                    with open(survey_file, 'r') as f:
                        data = json.load(f)
                        
                        questions = []
                        for q_data in data['questions']:
                            question = SurveyQuestion(
                                id=q_data['id'],
                                type=q_data['type'],
                                question=q_data['question'],
                                options=q_data.get('options'),
                                required=q_data.get('required', True),
                                max_length=q_data.get('max_length'),
                                scale=q_data.get('scale')
                            )
                            questions.append(question)
                        
                        survey = Survey(
                            id=data['id'],
                            title=data['title'],
                            description=data['description'],
                            active=data['active'],
                            created_date=data['created_date'],
                            expires_date=data['expires_date'],
                            questions=questions
                        )
                        
                        self.surveys[survey.id] = survey
                        self.logger.info(f"Loaded survey: {survey.title}")
                        
                except Exception as e:
                    self.logger.error(f"Error loading survey {survey_file}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error loading surveys: {e}")
    
    def _load_leaderboards(self):
        """Load leaderboards from database"""
        try:
            db = get_database()
            cursor = db.cursor()
            
            # Load ham test leaderboards
            cursor.execute("""
                SELECT user_id, user_name, license_level, 
                       MAX(score_percentage) as best_score,
                       COUNT(*) as attempts,
                       MAX(completed_at) as last_attempt
                FROM ham_test_sessions 
                WHERE completed_at IS NOT NULL
                GROUP BY user_id, license_level
                ORDER BY best_score DESC, last_attempt DESC
            """)
            
            ham_results = cursor.fetchall()
            for level in ['technician', 'general', 'extra']:
                self.leaderboards[f'hamtest_{level}'] = []
            
            for row in ham_results:
                user_id, user_name, level, score, attempts, last_attempt = row
                entry = LeaderboardEntry(
                    user_id=user_id,
                    user_name=user_name or user_id,
                    category=f'hamtest_{level}',
                    score=int(score) if score else 0,
                    total_questions=attempts,
                    percentage=score or 0.0,
                    date=datetime.fromisoformat(last_attempt) if last_attempt else datetime.now()
                )
                self.leaderboards[f'hamtest_{level}'].append(entry)
            
            # Load quiz leaderboards
            cursor.execute("""
                SELECT user_id, user_name, category,
                       MAX(score_percentage) as best_score,
                       COUNT(*) as attempts,
                       MAX(completed_at) as last_attempt
                FROM quiz_sessions 
                WHERE completed_at IS NOT NULL
                GROUP BY user_id, category
                ORDER BY best_score DESC, last_attempt DESC
            """)
            
            quiz_results = cursor.fetchall()
            for row in quiz_results:
                user_id, user_name, category, score, attempts, last_attempt = row
                leaderboard_key = f'quiz_{category}'
                if leaderboard_key not in self.leaderboards:
                    self.leaderboards[leaderboard_key] = []
                
                entry = LeaderboardEntry(
                    user_id=user_id,
                    user_name=user_name or user_id,
                    category=leaderboard_key,
                    score=int(score) if score else 0,
                    total_questions=attempts,
                    percentage=score or 0.0,
                    date=datetime.fromisoformat(last_attempt) if last_attempt else datetime.now()
                )
                self.leaderboards[leaderboard_key].append(entry)
            
            self.logger.info("Loaded leaderboards from database")
            
        except Exception as e:
            self.logger.error(f"Error loading leaderboards: {e}")
    
    async def handle_hamtest_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle ham radio test commands"""
        user_id = context.get('sender_id', '')
        user_name = context.get('sender_name', user_id)
        
        # Check for active session
        if user_id in self.active_sessions:
            session = self.active_sessions[user_id]
            if session.session_type == 'hamtest':
                return await self._handle_hamtest_answer(args, session, context)
        
        # Start new session
        level = 'technician'  # default
        if args:
            requested_level = args[0].lower()
            if requested_level in ['technician', 'general', 'extra']:
                level = requested_level
            elif requested_level in ['tech', 't']:
                level = 'technician'
            elif requested_level in ['gen', 'g']:
                level = 'general'
            elif requested_level in ['extra', 'e', 'ae']:
                level = 'extra'
        
        if level not in self.ham_questions or not self.ham_questions[level]:
            return f"❌ No {level} class questions available"
        
        # Create new session
        session_id = f"hamtest_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        questions = random.sample(
            self.ham_questions[level], 
            min(self.max_questions_per_session, len(self.ham_questions[level]))
        )
        
        session = UserSession(
            user_id=user_id,
            session_type='hamtest',
            session_id=session_id,
            current_question=0,
            questions=questions,
            answers=[],
            score=0,
            started_at=datetime.now(),
            category=level
        )
        
        self.active_sessions[user_id] = session
        
        # Store session in database
        await self._store_ham_session(session, user_name)
        
        # Present first question
        return await self._present_ham_question(session)
    
    async def _handle_hamtest_answer(self, args: List[str], session: UserSession, context: Dict[str, Any]) -> str:
        """Handle ham test answer"""
        if not args:
            return "❓ Please provide your answer (A, B, C, or D)"
        
        answer_text = args[0].upper()
        if answer_text not in ['A', 'B', 'C', 'D']:
            return "❓ Please answer with A, B, C, or D"
        
        answer_index = ord(answer_text) - ord('A')
        current_question = session.questions[session.current_question]
        
        # Check answer
        is_correct = answer_index == current_question.correct
        session.answers.append(answer_index)
        
        if is_correct:
            session.score += 1
        
        response = f"{'✅' if is_correct else '❌'} "
        if is_correct:
            response += "Correct!\n"
        else:
            correct_letter = chr(ord('A') + current_question.correct)
            response += f"Incorrect. The correct answer is {correct_letter}.\n"
        
        response += f"💡 {current_question.explanation}\n\n"
        
        # Move to next question
        session.current_question += 1
        
        if session.current_question >= len(session.questions):
            # Session complete
            return await self._complete_ham_session(session, context)
        else:
            # Present next question
            response += await self._present_ham_question(session)
            return response
    
    async def _present_ham_question(self, session: UserSession) -> str:
        """Present current ham test question"""
        question = session.questions[session.current_question]
        
        response = f"📚 **Ham Radio Test - {session.category.title()} Class**\n"
        response += f"Question {session.current_question + 1} of {len(session.questions)}\n\n"
        response += f"**{question.id}:** {question.question}\n\n"
        
        for i, option in enumerate(question.options):
            letter = chr(ord('A') + i)
            response += f"{letter}. {option}\n"
        
        response += f"\n💡 Reply with A, B, C, or D"
        return response
    
    async def _complete_ham_session(self, session: UserSession, context: Dict[str, Any]) -> str:
        """Complete ham test session"""
        user_name = context.get('sender_name', session.user_id)
        
        # Calculate results
        total_questions = len(session.questions)
        correct_answers = session.score
        percentage = (correct_answers / total_questions) * 100
        passed = percentage >= 74  # FCC passing grade
        
        # Update database
        await self._update_ham_session(session, user_name, percentage, passed)
        
        # Update leaderboard
        await self._update_ham_leaderboard(session, user_name, percentage)
        
        # Remove active session
        if session.user_id in self.active_sessions:
            del self.active_sessions[session.user_id]
        
        # Generate response
        response = f"🎓 **Ham Test Complete - {session.category.title()} Class**\n\n"
        response += f"📊 **Results:**\n"
        response += f"• Score: {correct_answers}/{total_questions} ({percentage:.1f}%)\n"
        response += f"• Status: {'✅ PASSED' if passed else '❌ FAILED'}\n"
        
        if passed:
            response += f"🎉 Congratulations! You passed the {session.category} class exam!\n"
        else:
            response += f"📚 Keep studying! You need 74% to pass.\n"
        
        response += f"\n💡 Send `hamtest {session.category}` to try again"
        response += f"\n🏆 Send `leaderboard hamtest` to see rankings"
        
        return response
    
    async def handle_quiz_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle quiz commands"""
        user_id = context.get('sender_id', '')
        user_name = context.get('sender_name', user_id)
        
        # Check for active session
        if user_id in self.active_sessions:
            session = self.active_sessions[user_id]
            if session.session_type == 'quiz':
                return await self._handle_quiz_answer(args, session, context)
        
        # Start new session
        category = 'general'  # default
        if args:
            requested_category = args[0].lower()
            if requested_category in self.quiz_questions:
                category = requested_category
        
        if category not in self.quiz_questions or not self.quiz_questions[category]:
            available = list(self.quiz_questions.keys())
            return f"❌ No {category} quiz questions available.\n💡 Available categories: {', '.join(available)}"
        
        # Create new session
        session_id = f"quiz_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        questions = random.sample(
            self.quiz_questions[category], 
            min(self.max_questions_per_session, len(self.quiz_questions[category]))
        )
        
        session = UserSession(
            user_id=user_id,
            session_type='quiz',
            session_id=session_id,
            current_question=0,
            questions=questions,
            answers=[],
            score=0,
            started_at=datetime.now(),
            category=category
        )
        
        self.active_sessions[user_id] = session
        
        # Store session in database
        await self._store_quiz_session(session, user_name)
        
        # Present first question
        return await self._present_quiz_question(session)
    
    async def _handle_quiz_answer(self, args: List[str], session: UserSession, context: Dict[str, Any]) -> str:
        """Handle quiz answer"""
        if not args:
            return "❓ Please provide your answer (A, B, C, or D)"
        
        answer_text = args[0].upper()
        if answer_text not in ['A', 'B', 'C', 'D']:
            return "❓ Please answer with A, B, C, or D"
        
        answer_index = ord(answer_text) - ord('A')
        current_question = session.questions[session.current_question]
        
        # Check answer
        is_correct = answer_index == current_question.correct
        session.answers.append(answer_index)
        
        if is_correct:
            session.score += 1
        
        response = f"{'✅' if is_correct else '❌'} "
        if is_correct:
            response += "Correct!\n"
        else:
            correct_letter = chr(ord('A') + current_question.correct)
            response += f"Incorrect. The correct answer is {correct_letter}.\n"
        
        response += f"💡 {current_question.explanation}\n\n"
        
        # Move to next question
        session.current_question += 1
        
        if session.current_question >= len(session.questions):
            # Session complete
            return await self._complete_quiz_session(session, context)
        else:
            # Present next question
            response += await self._present_quiz_question(session)
            return response
    
    async def _present_quiz_question(self, session: UserSession) -> str:
        """Present current quiz question"""
        question = session.questions[session.current_question]
        
        response = f"🧠 **Quiz - {session.category.title()}**\n"
        response += f"Question {session.current_question + 1} of {len(session.questions)}\n\n"
        response += f"**{question.question}**\n\n"
        
        for i, option in enumerate(question.options):
            letter = chr(ord('A') + i)
            response += f"{letter}. {option}\n"
        
        response += f"\n💡 Reply with A, B, C, or D"
        return response
    
    async def _complete_quiz_session(self, session: UserSession, context: Dict[str, Any]) -> str:
        """Complete quiz session"""
        user_name = context.get('sender_name', session.user_id)
        
        # Calculate results
        total_questions = len(session.questions)
        correct_answers = session.score
        percentage = (correct_answers / total_questions) * 100
        
        # Update database
        await self._update_quiz_session(session, user_name, percentage)
        
        # Update leaderboard
        await self._update_quiz_leaderboard(session, user_name, percentage)
        
        # Remove active session
        if session.user_id in self.active_sessions:
            del self.active_sessions[session.user_id]
        
        # Generate response
        response = f"🧠 **Quiz Complete - {session.category.title()}**\n\n"
        response += f"📊 **Results:**\n"
        response += f"• Score: {correct_answers}/{total_questions} ({percentage:.1f}%)\n"
        
        if percentage >= 80:
            response += f"🎉 Excellent work!\n"
        elif percentage >= 60:
            response += f"👍 Good job!\n"
        else:
            response += f"📚 Keep learning!\n"
        
        response += f"\n💡 Send `quiz {session.category}` to try again"
        response += f"\n🏆 Send `leaderboard quiz` to see rankings"
        
        return response
    
    async def handle_survey_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """Handle survey commands"""
        user_id = context.get('sender_id', '')
        user_name = context.get('sender_name', user_id)
        
        # Check for active session
        if user_id in self.active_sessions:
            session = self.active_sessions[user_id]
            if session.session_type == 'survey':
                return await self._handle_survey_answer(args, session, context)
        
        # List available surveys or start specific survey
        if not args:
            return await self._list_surveys()
        
        survey_id = args[0].lower()
        if survey_id not in self.surveys:
            return f"❌ Survey '{survey_id}' not found.\n💡 Send `survey` to see available surveys"
        
        survey = self.surveys[survey_id]
        if not survey.active:
            return f"❌ Survey '{survey.title}' is not currently active"
        
        # Check if survey has expired
        if survey.expires_date:
            try:
                expires = datetime.fromisoformat(survey.expires_date)
                if datetime.now() > expires:
                    return f"❌ Survey '{survey.title}' has expired"
            except:
                pass
        
        # Check if user has already completed this survey
        if await self._has_completed_survey(user_id, survey_id):
            return f"✅ You have already completed the survey '{survey.title}'"
        
        # Create new session
        session_id = f"survey_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = UserSession(
            user_id=user_id,
            session_type='survey',
            session_id=session_id,
            current_question=0,
            questions=survey.questions,
            answers=[],
            score=0,
            started_at=datetime.now(),
            survey_id=survey_id
        )
        
        self.active_sessions[user_id] = session
        
        # Store session in database
        await self._store_survey_session(session, user_name, survey_id)
        
        # Present survey intro and first question
        response = f"📋 **{survey.title}**\n\n"
        response += f"{survey.description}\n\n"
        response += await self._present_survey_question(session)
        
        return response
    
    async def _list_surveys(self) -> str:
        """List available surveys"""
        active_surveys = [s for s in self.surveys.values() if s.active]
        
        if not active_surveys:
            return "📋 No surveys are currently available"
        
        response = "📋 **Available Surveys**\n\n"
        for survey in active_surveys:
            response += f"• **{survey.id}** - {survey.title}\n"
            response += f"  {survey.description}\n"
            response += f"  Questions: {len(survey.questions)}\n\n"
        
        response += "💡 Send `survey <id>` to start a survey"
        return response
    
    async def _handle_survey_answer(self, args: List[str], session: UserSession, context: Dict[str, Any]) -> str:
        """Handle survey answer"""
        if not args:
            return "❓ Please provide your answer"
        
        current_question = session.questions[session.current_question]
        answer = ' '.join(args)
        
        # Validate answer based on question type
        if current_question.type == 'multiple_choice':
            try:
                if answer.upper() in ['A', 'B', 'C', 'D']:
                    answer_index = ord(answer.upper()) - ord('A')
                    if answer_index < len(current_question.options):
                        answer = current_question.options[answer_index]
                    else:
                        return f"❓ Please choose A-{chr(ord('A') + len(current_question.options) - 1)}"
                elif answer not in current_question.options:
                    return f"❓ Please choose from the available options or use A, B, C, etc."
            except:
                return "❓ Invalid answer format"
        
        elif current_question.type == 'yes_no':
            if answer.lower() not in ['yes', 'no', 'y', 'n']:
                return "❓ Please answer Yes or No"
            answer = 'Yes' if answer.lower() in ['yes', 'y'] else 'No'
        
        elif current_question.type == 'rating':
            try:
                rating = int(answer)
                if rating < 1 or rating > current_question.scale:
                    return f"❓ Please rate from 1 to {current_question.scale}"
                answer = str(rating)
            except ValueError:
                return f"❓ Please provide a number from 1 to {current_question.scale}"
        
        elif current_question.type == 'text':
            if current_question.max_length and len(answer) > current_question.max_length:
                return f"❓ Answer too long. Maximum {current_question.max_length} characters"
        
        # Store answer
        session.answers.append(answer)
        
        # Store in database
        await self._store_survey_response(session, current_question, answer, context)
        
        # Move to next question
        session.current_question += 1
        
        if session.current_question >= len(session.questions):
            # Survey complete
            return await self._complete_survey_session(session, context)
        else:
            # Present next question
            response = "✅ Answer recorded.\n\n"
            response += await self._present_survey_question(session)
            return response
    
    async def _present_survey_question(self, session: UserSession) -> str:
        """Present current survey question"""
        question = session.questions[session.current_question]
        
        response = f"**Question {session.current_question + 1} of {len(session.questions)}**\n\n"
        response += f"{question.question}\n\n"
        
        if question.type == 'multiple_choice':
            for i, option in enumerate(question.options):
                letter = chr(ord('A') + i)
                response += f"{letter}. {option}\n"
            response += f"\n💡 Reply with A, B, C, etc. or type your choice"
        
        elif question.type == 'yes_no':
            response += "💡 Reply with Yes or No"
        
        elif question.type == 'rating':
            response += f"💡 Rate from 1 to {question.scale} (1 = lowest, {question.scale} = highest)"
        
        elif question.type == 'text':
            if question.max_length:
                response += f"💡 Text answer (max {question.max_length} characters)"
            else:
                response += "💡 Text answer"
        
        if question.required:
            response += " (Required)"
        else:
            response += " (Optional - send 'skip' to skip)"
        
        return response
    
    async def _complete_survey_session(self, session: UserSession, context: Dict[str, Any]) -> str:
        """Complete survey session"""
        user_name = context.get('sender_name', session.user_id)
        
        # Update database
        await self._update_survey_session(session, user_name)
        
        # Remove active session
        if session.user_id in self.active_sessions:
            del self.active_sessions[session.user_id]
        
        survey = self.surveys[session.survey_id]
        
        response = f"✅ **Survey Complete**\n\n"
        response += f"Thank you for completing '{survey.title}'!\n"
        response += f"📊 You answered {len(session.answers)} questions.\n\n"
        response += f"Your responses have been recorded and will help improve our services."
        
        return response
    
    async def get_leaderboard(self, category: str = None) -> str:
        """Get leaderboard for specified category"""
        if category:
            # Specific category
            if category not in self.leaderboards:
                return f"❌ No leaderboard found for '{category}'"
            
            entries = self.leaderboards[category][:10]  # Top 10
            if not entries:
                return f"📊 No scores recorded for '{category}' yet"
            
            response = f"🏆 **{category.replace('_', ' ').title()} Leaderboard**\n\n"
            for i, entry in enumerate(entries, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                response += f"{medal} {entry.user_name}: {entry.percentage:.1f}%\n"
            
            return response
        
        else:
            # List all categories
            categories = list(self.leaderboards.keys())
            if not categories:
                return "📊 No leaderboards available yet"
            
            response = "🏆 **Available Leaderboards**\n\n"
            for cat in sorted(categories):
                count = len(self.leaderboards[cat])
                response += f"• {cat.replace('_', ' ').title()}: {count} entries\n"
            
            response += "\n💡 Send `leaderboard <category>` to view specific rankings"
            return response
    
    # Database helper methods
    async def _store_ham_session(self, session: UserSession, user_name: str):
        """Store ham test session in database"""
        try:
            db = get_database()
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO ham_test_sessions 
                (id, user_id, user_name, license_level, started_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session.session_id, session.user_id, user_name, session.category, session.started_at))
            db.commit()
        except Exception as e:
            self.logger.error(f"Error storing ham session: {e}")
    
    async def _update_ham_session(self, session: UserSession, user_name: str, percentage: float, passed: bool):
        """Update ham test session with results"""
        try:
            db = get_database()
            cursor = db.cursor()
            cursor.execute("""
                UPDATE ham_test_sessions 
                SET questions_asked = ?, correct_answers = ?, completed_at = ?, 
                    score_percentage = ?, passed = ?
                WHERE id = ?
            """, (len(session.questions), session.score, datetime.now(), 
                  percentage, passed, session.session_id))
            db.commit()
        except Exception as e:
            self.logger.error(f"Error updating ham session: {e}")
    
    async def _store_quiz_session(self, session: UserSession, user_name: str):
        """Store quiz session in database"""
        try:
            db = get_database()
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO quiz_sessions 
                (id, user_id, user_name, category, started_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session.session_id, session.user_id, user_name, session.category, session.started_at))
            db.commit()
        except Exception as e:
            self.logger.error(f"Error storing quiz session: {e}")
    
    async def _update_quiz_session(self, session: UserSession, user_name: str, percentage: float):
        """Update quiz session with results"""
        try:
            db = get_database()
            cursor = db.cursor()
            cursor.execute("""
                UPDATE quiz_sessions 
                SET questions_asked = ?, correct_answers = ?, completed_at = ?, score_percentage = ?
                WHERE id = ?
            """, (len(session.questions), session.score, datetime.now(), percentage, session.session_id))
            db.commit()
        except Exception as e:
            self.logger.error(f"Error updating quiz session: {e}")
    
    async def _store_survey_session(self, session: UserSession, user_name: str, survey_id: str):
        """Store survey session in database"""
        try:
            db = get_database()
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO survey_sessions 
                (id, survey_id, user_id, user_name, started_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session.session_id, survey_id, session.user_id, user_name, session.started_at))
            db.commit()
        except Exception as e:
            self.logger.error(f"Error storing survey session: {e}")
    
    async def _store_survey_response(self, session: UserSession, question: SurveyQuestion, answer: str, context: Dict[str, Any]):
        """Store survey response in database"""
        try:
            user_name = context.get('sender_name', session.user_id)
            db = get_database()
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO survey_responses 
                (survey_id, user_id, user_name, question_id, response, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session.survey_id, session.user_id, user_name, question.id, answer, datetime.now()))
            db.commit()
        except Exception as e:
            self.logger.error(f"Error storing survey response: {e}")
    
    async def _update_survey_session(self, session: UserSession, user_name: str):
        """Update survey session as completed"""
        try:
            db = get_database()
            cursor = db.cursor()
            cursor.execute("""
                UPDATE survey_sessions 
                SET completed_at = ?, questions_answered = ?
                WHERE id = ?
            """, (datetime.now(), len(session.answers), session.session_id))
            db.commit()
        except Exception as e:
            self.logger.error(f"Error updating survey session: {e}")
    
    async def _has_completed_survey(self, user_id: str, survey_id: str) -> bool:
        """Check if user has completed a survey"""
        try:
            db = get_database()
            cursor = db.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM survey_sessions 
                WHERE user_id = ? AND survey_id = ? AND completed_at IS NOT NULL
            """, (user_id, survey_id))
            count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            self.logger.error(f"Error checking survey completion: {e}")
            return False
    
    async def _update_ham_leaderboard(self, session: UserSession, user_name: str, percentage: float):
        """Update ham test leaderboard"""
        try:
            leaderboard_key = f'hamtest_{session.category}'
            if leaderboard_key not in self.leaderboards:
                self.leaderboards[leaderboard_key] = []
            
            # Find existing entry for this user
            existing_entry = None
            for entry in self.leaderboards[leaderboard_key]:
                if entry.user_id == session.user_id:
                    existing_entry = entry
                    break
            
            if existing_entry:
                # Update if this is a better score
                if percentage > existing_entry.percentage:
                    existing_entry.score = int(percentage)
                    existing_entry.percentage = percentage
                    existing_entry.date = datetime.now()
            else:
                # Add new entry
                entry = LeaderboardEntry(
                    user_id=session.user_id,
                    user_name=user_name,
                    category=leaderboard_key,
                    score=int(percentage),
                    total_questions=len(session.questions),
                    percentage=percentage,
                    date=datetime.now()
                )
                self.leaderboards[leaderboard_key].append(entry)
            
            # Sort leaderboard
            self.leaderboards[leaderboard_key].sort(key=lambda x: (-x.percentage, x.date))
            
        except Exception as e:
            self.logger.error(f"Error updating ham leaderboard: {e}")
    
    async def _update_quiz_leaderboard(self, session: UserSession, user_name: str, percentage: float):
        """Update quiz leaderboard"""
        try:
            leaderboard_key = f'quiz_{session.category}'
            if leaderboard_key not in self.leaderboards:
                self.leaderboards[leaderboard_key] = []
            
            # Find existing entry for this user
            existing_entry = None
            for entry in self.leaderboards[leaderboard_key]:
                if entry.user_id == session.user_id:
                    existing_entry = entry
                    break
            
            if existing_entry:
                # Update if this is a better score
                if percentage > existing_entry.percentage:
                    existing_entry.score = int(percentage)
                    existing_entry.percentage = percentage
                    existing_entry.date = datetime.now()
            else:
                # Add new entry
                entry = LeaderboardEntry(
                    user_id=session.user_id,
                    user_name=user_name,
                    category=leaderboard_key,
                    score=int(percentage),
                    total_questions=len(session.questions),
                    percentage=percentage,
                    date=datetime.now()
                )
                self.leaderboards[leaderboard_key].append(entry)
            
            # Sort leaderboard
            self.leaderboards[leaderboard_key].sort(key=lambda x: (-x.percentage, x.date))
            
        except Exception as e:
            self.logger.error(f"Error updating quiz leaderboard: {e}")
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            current_time = datetime.now()
            expired_sessions = []
            
            for user_id, session in self.active_sessions.items():
                time_elapsed = current_time - session.started_at
                if time_elapsed.total_seconds() > (self.session_timeout * 60):
                    expired_sessions.append(user_id)
            
            for user_id in expired_sessions:
                del self.active_sessions[user_id]
                self.logger.info(f"Cleaned up expired session for user {user_id}")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up sessions: {e}")
    
    def get_session_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get current session status for user"""
        if user_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[user_id]
        return {
            'type': session.session_type,
            'category': session.category,
            'current_question': session.current_question + 1,
            'total_questions': len(session.questions),
            'score': session.score,
            'started_at': session.started_at,
            'survey_id': session.survey_id
        }