"""
Tests for Educational Service

Tests the educational and reference features including:
- Ham radio test questions
- Interactive quiz system
- Survey system
- Leaderboards
"""

import pytest
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.services.bot.educational_service import (
    EducationalService, HamQuestion, QuizQuestion, Survey, SurveyQuestion,
    UserSession, LeaderboardEntry
)


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory with test data"""
    with tempfile.TemporaryDirectory() as temp_dir:
        data_dir = Path(temp_dir)
        
        # Create ham radio data
        ham_dir = data_dir / 'hamradio'
        ham_dir.mkdir()
        
        tech_questions = [
            {
                "id": "T1A01",
                "question": "Test question 1?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct": 2,
                "explanation": "Test explanation"
            },
            {
                "id": "T1A02", 
                "question": "Test question 2?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct": 1,
                "explanation": "Test explanation 2"
            }
        ]
        
        with open(ham_dir / 'technician.json', 'w') as f:
            json.dump(tech_questions, f)
        
        # Create quiz data
        quiz_data = [
            {
                "category": "test",
                "questions": [
                    {
                        "id": "test001",
                        "question": "What is 2+2?",
                        "options": ["3", "4", "5", "6"],
                        "correct": 1,
                        "explanation": "2+2=4"
                    }
                ]
            }
        ]
        
        with open(data_dir / 'quiz_questions.json', 'w') as f:
            json.dump(quiz_data, f)
        
        # Create survey data
        surveys_dir = data_dir / 'surveys'
        surveys_dir.mkdir()
        
        survey_data = {
            "id": "test_survey",
            "title": "Test Survey",
            "description": "A test survey",
            "active": True,
            "created_date": "2024-01-01",
            "expires_date": "2025-12-31",
            "questions": [
                {
                    "id": 1,
                    "type": "multiple_choice",
                    "question": "How do you feel?",
                    "options": ["Good", "Bad", "Neutral"],
                    "required": True
                },
                {
                    "id": 2,
                    "type": "text",
                    "question": "Any comments?",
                    "required": False,
                    "max_length": 100
                }
            ]
        }
        
        with open(surveys_dir / 'test_survey.json', 'w') as f:
            json.dump(survey_data, f)
        
        yield data_dir


@pytest.fixture
def mock_database():
    """Mock database for testing"""
    with patch('src.services.bot.educational_service.get_database') as mock_db:
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []  # Return empty list for leaderboard queries
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        yield mock_cursor


@pytest.fixture
def educational_service(temp_data_dir, mock_database):
    """Create educational service with test data"""
    config = {
        'data_dir': str(temp_data_dir),
        'session_timeout_minutes': 30,
        'max_questions_per_session': 5
    }
    
    service = EducationalService(config)
    return service


class TestEducationalService:
    """Test educational service functionality"""
    
    def test_initialization(self, educational_service):
        """Test service initialization"""
        assert educational_service is not None
        assert 'technician' in educational_service.ham_questions
        assert len(educational_service.ham_questions['technician']) == 2
        assert 'test' in educational_service.quiz_questions
        assert 'test_survey' in educational_service.surveys
    
    @pytest.mark.asyncio
    async def test_hamtest_command_start(self, educational_service):
        """Test starting a ham test"""
        context = {
            'sender_id': 'test_user',
            'sender_name': 'Test User'
        }
        
        response = await educational_service.handle_hamtest_command(['technician'], context)
        
        assert "Ham Radio Test - Technician Class" in response
        assert "Question 1 of" in response
        assert "test_user" in educational_service.active_sessions
        
        session = educational_service.active_sessions['test_user']
        assert session.session_type == 'hamtest'
        assert session.category == 'technician'
        assert len(session.questions) <= 5  # max_questions_per_session
    
    @pytest.mark.asyncio
    async def test_hamtest_answer_correct(self, educational_service):
        """Test correct ham test answer"""
        context = {
            'sender_id': 'test_user',
            'sender_name': 'Test User'
        }
        
        # Start session
        await educational_service.handle_hamtest_command(['technician'], context)
        session = educational_service.active_sessions['test_user']
        
        # Get correct answer for first question
        correct_answer = chr(ord('A') + session.questions[0].correct)
        
        response = await educational_service._handle_hamtest_answer(
            [correct_answer], session, context
        )
        
        assert "✅ Correct!" in response
        assert session.score == 1
        assert session.current_question == 1
    
    @pytest.mark.asyncio
    async def test_hamtest_answer_incorrect(self, educational_service):
        """Test incorrect ham test answer"""
        context = {
            'sender_id': 'test_user',
            'sender_name': 'Test User'
        }
        
        # Start session
        await educational_service.handle_hamtest_command(['technician'], context)
        session = educational_service.active_sessions['test_user']
        
        # Get incorrect answer for first question
        incorrect_answer = 'A' if session.questions[0].correct != 0 else 'B'
        
        response = await educational_service._handle_hamtest_answer(
            [incorrect_answer], session, context
        )
        
        assert "❌ Incorrect" in response
        assert "The correct answer is" in response
        assert session.score == 0
        assert session.current_question == 1
    
    @pytest.mark.asyncio
    async def test_quiz_command_start(self, educational_service):
        """Test starting a quiz"""
        context = {
            'sender_id': 'test_user',
            'sender_name': 'Test User'
        }
        
        response = await educational_service.handle_quiz_command(['test'], context)
        
        assert "Quiz - Test" in response
        assert "What is 2+2?" in response
        assert "test_user" in educational_service.active_sessions
        
        session = educational_service.active_sessions['test_user']
        assert session.session_type == 'quiz'
        assert session.category == 'test'
    
    @pytest.mark.asyncio
    async def test_quiz_answer(self, educational_service):
        """Test quiz answer"""
        context = {
            'sender_id': 'test_user',
            'sender_name': 'Test User'
        }
        
        # Start session
        await educational_service.handle_quiz_command(['test'], context)
        session = educational_service.active_sessions['test_user']
        
        # Answer correctly (B = 4)
        response = await educational_service._handle_quiz_answer(
            ['B'], session, context
        )
        
        # Since there's only one question, it should complete immediately
        assert ("✅ Correct!" in response or "Quiz Complete" in response)
        assert "Quiz Complete" in response  # Only one question in test data
        assert session.score == 1
    
    @pytest.mark.asyncio
    async def test_survey_list(self, educational_service):
        """Test listing surveys"""
        response = await educational_service._list_surveys()
        
        assert "Available Surveys" in response
        assert "test_survey" in response
        assert "Test Survey" in response
    
    @pytest.mark.asyncio
    async def test_survey_start(self, educational_service):
        """Test starting a survey"""
        context = {
            'sender_id': 'test_user',
            'sender_name': 'Test User'
        }
        
        response = await educational_service.handle_survey_command(['test_survey'], context)
        
        assert "Test Survey" in response
        assert "How do you feel?" in response
        assert "test_user" in educational_service.active_sessions
        
        session = educational_service.active_sessions['test_user']
        assert session.session_type == 'survey'
        assert session.survey_id == 'test_survey'
    
    @pytest.mark.asyncio
    async def test_survey_answer_multiple_choice(self, educational_service):
        """Test survey multiple choice answer"""
        context = {
            'sender_id': 'test_user',
            'sender_name': 'Test User'
        }
        
        # Start session
        await educational_service.handle_survey_command(['test_survey'], context)
        session = educational_service.active_sessions['test_user']
        
        # Answer with option A (Good)
        response = await educational_service._handle_survey_answer(
            ['A'], session, context
        )
        
        assert "Answer recorded" in response
        assert "Any comments?" in response  # Next question
        assert len(session.answers) == 1
        assert session.answers[0] == "Good"
    
    @pytest.mark.asyncio
    async def test_survey_answer_text(self, educational_service):
        """Test survey text answer"""
        context = {
            'sender_id': 'test_user',
            'sender_name': 'Test User'
        }
        
        # Start session and answer first question
        await educational_service.handle_survey_command(['test_survey'], context)
        session = educational_service.active_sessions['test_user']
        await educational_service._handle_survey_answer(['A'], session, context)
        
        # Answer text question
        response = await educational_service._handle_survey_answer(
            ['This', 'is', 'a', 'test', 'comment'], session, context
        )
        
        assert "Survey Complete" in response
        assert len(session.answers) == 2
        assert session.answers[1] == "This is a test comment"
    
    @pytest.mark.asyncio
    async def test_leaderboard_empty(self, educational_service):
        """Test empty leaderboard"""
        response = await educational_service.get_leaderboard('hamtest_technician')
        
        assert "No scores recorded" in response
    
    @pytest.mark.asyncio
    async def test_leaderboard_categories(self, educational_service):
        """Test leaderboard categories listing"""
        # Add a test entry
        entry = LeaderboardEntry(
            user_id='test_user',
            user_name='Test User',
            category='hamtest_technician',
            score=85,
            total_questions=10,
            percentage=85.0,
            date=datetime.now()
        )
        educational_service.leaderboards['hamtest_technician'] = [entry]
        
        response = await educational_service.get_leaderboard()
        
        assert "Available Leaderboards" in response
        assert "Hamtest Technician: 1 entries" in response
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self, educational_service):
        """Test session cleanup"""
        # Create expired session
        old_session = UserSession(
            user_id='old_user',
            session_type='hamtest',
            session_id='old_session',
            current_question=0,
            questions=[],
            answers=[],
            score=0,
            started_at=datetime.now() - timedelta(hours=2),  # 2 hours ago
            category='technician'
        )
        
        educational_service.active_sessions['old_user'] = old_session
        
        # Run cleanup
        await educational_service.cleanup_expired_sessions()
        
        # Session should be removed
        assert 'old_user' not in educational_service.active_sessions
    
    def test_session_status(self, educational_service):
        """Test getting session status"""
        # No active session
        status = educational_service.get_session_status('test_user')
        assert status is None
        
        # Create active session
        session = UserSession(
            user_id='test_user',
            session_type='quiz',
            session_id='test_session',
            current_question=2,
            questions=[Mock(), Mock(), Mock()],
            answers=[],
            score=1,
            started_at=datetime.now(),
            category='test'
        )
        
        educational_service.active_sessions['test_user'] = session
        
        status = educational_service.get_session_status('test_user')
        assert status is not None
        assert status['type'] == 'quiz'
        assert status['category'] == 'test'
        assert status['current_question'] == 3  # 0-based + 1
        assert status['total_questions'] == 3
        assert status['score'] == 1


class TestHamQuestionData:
    """Test ham radio question data structure"""
    
    def test_ham_question_creation(self):
        """Test creating ham question"""
        question = HamQuestion(
            id="T1A01",
            question="Test question?",
            options=["A", "B", "C", "D"],
            correct=2,
            explanation="Test explanation"
        )
        
        assert question.id == "T1A01"
        assert question.question == "Test question?"
        assert len(question.options) == 4
        assert question.correct == 2
        assert question.explanation == "Test explanation"


class TestQuizData:
    """Test quiz data structures"""
    
    def test_quiz_question_creation(self):
        """Test creating quiz question"""
        question = QuizQuestion(
            id="quiz001",
            category="science",
            question="What is H2O?",
            options=["Water", "Hydrogen", "Oxygen", "Salt"],
            correct=0,
            explanation="H2O is water"
        )
        
        assert question.id == "quiz001"
        assert question.category == "science"
        assert question.correct == 0


class TestSurveyData:
    """Test survey data structures"""
    
    def test_survey_question_creation(self):
        """Test creating survey question"""
        question = SurveyQuestion(
            id=1,
            type="multiple_choice",
            question="How satisfied are you?",
            options=["Very satisfied", "Satisfied", "Neutral", "Dissatisfied"],
            required=True
        )
        
        assert question.id == 1
        assert question.type == "multiple_choice"
        assert question.required is True
        assert len(question.options) == 4
    
    def test_survey_creation(self):
        """Test creating survey"""
        questions = [
            SurveyQuestion(1, "text", "What is your name?", required=True),
            SurveyQuestion(2, "rating", "Rate our service", scale=5, required=True)
        ]
        
        survey = Survey(
            id="test_survey",
            title="Test Survey",
            description="A test survey",
            active=True,
            created_date="2024-01-01",
            expires_date="2024-12-31",
            questions=questions
        )
        
        assert survey.id == "test_survey"
        assert survey.active is True
        assert len(survey.questions) == 2
        assert survey.questions[1].scale == 5