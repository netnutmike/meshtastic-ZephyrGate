"""
Integration tests for Educational Features

Tests the integration between educational services and command handling:
- Ham radio test commands
- Quiz commands  
- Survey commands
- Leaderboard commands
- Reference data commands
"""

import pytest
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.services.bot.comprehensive_command_handler import ComprehensiveCommandHandler
from src.services.bot.command_registry import CommandContext


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
                "question": "Which of the following is a purpose of the Amateur Radio Service?",
                "options": [
                    "Personal communications",
                    "Commercial communications", 
                    "Advancing skills in radio art",
                    "All of the above"
                ],
                "correct": 2,
                "explanation": "The Amateur Radio Service advances skills in radio art."
            }
        ]
        
        with open(ham_dir / 'technician.json', 'w') as f:
            json.dump(tech_questions, f)
        
        # Create quiz data
        quiz_data = [
            {
                "category": "science",
                "questions": [
                    {
                        "id": "sci001",
                        "question": "What is the speed of light?",
                        "options": ["299,792,458 m/s", "300,000,000 m/s", "186,000 mi/s", "Both A and C"],
                        "correct": 3,
                        "explanation": "The speed of light is exactly 299,792,458 m/s, approximately 186,000 mi/s."
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
            "id": "feedback",
            "title": "User Feedback Survey",
            "description": "Help us improve the system",
            "active": True,
            "created_date": "2024-01-01",
            "expires_date": "2025-12-31",
            "questions": [
                {
                    "id": 1,
                    "type": "multiple_choice",
                    "question": "How would you rate the system?",
                    "options": ["Excellent", "Good", "Fair", "Poor"],
                    "required": True
                }
            ]
        }
        
        with open(surveys_dir / 'feedback.json', 'w') as f:
            json.dump(survey_data, f)
        
        yield data_dir


@pytest.fixture
def mock_database():
    """Mock database for testing"""
    with patch('src.services.bot.educational_service.get_database') as mock_db:
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        yield mock_cursor


@pytest.fixture
def command_handler(temp_data_dir, mock_database):
    """Create command handler with educational services"""
    config = {
        'data_dir': str(temp_data_dir),
        'session_timeout_minutes': 30,
        'max_questions_per_session': 5
    }
    
    handler = ComprehensiveCommandHandler(config)
    return handler


@pytest.fixture
def test_context():
    """Create test command context"""
    return CommandContext(
        sender_id='test_user',
        sender_name='Test User',
        channel=0,
        is_direct_message=True,
        is_admin=False,
        is_moderator=False,
        user_permissions={'user'},
        message_timestamp=datetime.now(),
        interface_id='test_interface',
        additional_data={}
    )


class TestEducationalIntegration:
    """Test educational features integration"""
    
    @pytest.mark.asyncio
    async def test_hamtest_command_flow(self, command_handler, test_context):
        """Test complete ham test command flow"""
        # Start ham test
        result = await command_handler._handle_educational_command(
            Mock(command='hamtest', parameters=['technician']), 
            test_context
        )
        
        assert result.success
        assert "Ham Radio Test - Technician Class" in result.response
        assert "Question 1 of" in result.response
        
        # Check that session was created
        educational_service = command_handler.educational_service
        assert test_context.sender_id in educational_service.active_sessions
        
        session = educational_service.active_sessions[test_context.sender_id]
        assert session.session_type == 'hamtest'
        assert session.category == 'technician'
    
    @pytest.mark.asyncio
    async def test_quiz_command_flow(self, command_handler, test_context):
        """Test complete quiz command flow"""
        # Start quiz
        result = await command_handler._handle_educational_command(
            Mock(command='quiz', parameters=['science']), 
            test_context
        )
        
        assert result.success
        assert "Quiz - Science" in result.response
        assert "What is the speed of light?" in result.response
        
        # Check that session was created
        educational_service = command_handler.educational_service
        assert test_context.sender_id in educational_service.active_sessions
        
        session = educational_service.active_sessions[test_context.sender_id]
        assert session.session_type == 'quiz'
        assert session.category == 'science'
    
    @pytest.mark.asyncio
    async def test_survey_command_flow(self, command_handler, test_context):
        """Test complete survey command flow"""
        # List surveys
        result = await command_handler._handle_educational_command(
            Mock(command='survey', parameters=[]), 
            test_context
        )
        
        assert result.success
        assert "Available Surveys" in result.response
        assert "feedback" in result.response
        
        # Start specific survey
        result = await command_handler._handle_educational_command(
            Mock(command='survey', parameters=['feedback']), 
            test_context
        )
        
        assert result.success
        assert "User Feedback Survey" in result.response
        assert "How would you rate the system?" in result.response
        
        # Check that session was created
        educational_service = command_handler.educational_service
        assert test_context.sender_id in educational_service.active_sessions
        
        session = educational_service.active_sessions[test_context.sender_id]
        assert session.session_type == 'survey'
        assert session.survey_id == 'feedback'
    
    @pytest.mark.asyncio
    async def test_hamtest_answer_flow(self, command_handler, test_context):
        """Test ham test answer handling"""
        # Start ham test
        await command_handler._handle_educational_command(
            Mock(command='hamtest', parameters=['technician']), 
            test_context
        )
        
        educational_service = command_handler.educational_service
        session = educational_service.active_sessions[test_context.sender_id]
        
        # Answer question correctly (C is correct for our test question)
        response = await educational_service._handle_hamtest_answer(
            ['C'], session, test_context.__dict__
        )
        
        # Since there's only one question, it completes immediately
        assert ("✅ Correct!" in response or "Ham Test Complete" in response)
        assert "Ham Test Complete" in response  # Only one question
        assert "100.0%" in response  # Perfect score
    
    @pytest.mark.asyncio
    async def test_quiz_answer_flow(self, command_handler, test_context):
        """Test quiz answer handling"""
        # Start quiz
        await command_handler._handle_educational_command(
            Mock(command='quiz', parameters=['science']), 
            test_context
        )
        
        educational_service = command_handler.educational_service
        session = educational_service.active_sessions[test_context.sender_id]
        
        # Answer question correctly (D is correct for our test question)
        response = await educational_service._handle_quiz_answer(
            ['D'], session, test_context.__dict__
        )
        
        assert ("✅ Correct!" in response or "Quiz Complete" in response)
        assert "Quiz Complete" in response  # Only one question
    
    @pytest.mark.asyncio
    async def test_survey_answer_flow(self, command_handler, test_context):
        """Test survey answer handling"""
        # Start survey
        await command_handler._handle_educational_command(
            Mock(command='survey', parameters=['feedback']), 
            test_context
        )
        
        educational_service = command_handler.educational_service
        session = educational_service.active_sessions[test_context.sender_id]
        
        # Answer survey question
        response = await educational_service._handle_survey_answer(
            ['A'], session, test_context.__dict__
        )
        
        assert "Survey Complete" in response  # Only one question
        assert "Thank you for completing" in response
    
    @pytest.mark.asyncio
    async def test_invalid_educational_command(self, command_handler, test_context):
        """Test handling of invalid educational command"""
        result = await command_handler._handle_educational_command(
            Mock(command='invalid_edu_command', parameters=[]), 
            test_context
        )
        
        assert result.success
        assert "not implemented yet" in result.response
    
    @pytest.mark.asyncio
    async def test_hamtest_invalid_level(self, command_handler, test_context):
        """Test ham test with invalid license level"""
        result = await command_handler._handle_educational_command(
            Mock(command='hamtest', parameters=['invalid_level']), 
            test_context
        )
        
        assert result.success
        # The service defaults to 'technician' for invalid levels
        assert ("No invalid_level class questions available" in result.response or 
                "Ham Radio Test - Technician Class" in result.response)
    
    @pytest.mark.asyncio
    async def test_quiz_invalid_category(self, command_handler, test_context):
        """Test quiz with invalid category"""
        result = await command_handler._handle_educational_command(
            Mock(command='quiz', parameters=['invalid_category']), 
            test_context
        )
        
        assert result.success
        # The service defaults to 'general' for invalid categories
        assert ("No invalid_category quiz questions available" in result.response or 
                "No general quiz questions available" in result.response)
        assert "Available categories: science" in result.response
    
    @pytest.mark.asyncio
    async def test_survey_invalid_id(self, command_handler, test_context):
        """Test survey with invalid ID"""
        result = await command_handler._handle_educational_command(
            Mock(command='survey', parameters=['invalid_survey']), 
            test_context
        )
        
        assert result.success
        assert "Survey 'invalid_survey' not found" in result.response


class TestReferenceIntegration:
    """Test reference data features integration"""
    
    @pytest.mark.asyncio
    async def test_solar_command(self, command_handler, test_context):
        """Test solar conditions command"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock failed API call to test fallback
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await command_handler._handle_reference_command(
                Mock(command='solar', parameters=[]), 
                test_context
            )
            
            assert result.success
            assert "Unable to retrieve solar data" in result.response
    
    @pytest.mark.asyncio
    async def test_hfcond_command(self, command_handler, test_context):
        """Test HF conditions command"""
        result = await command_handler._handle_reference_command(
            Mock(command='hfcond', parameters=[]), 
            test_context
        )
        
        assert result.success
        assert "HF Band Conditions" in result.response
        assert "80m:" in result.response
        assert "20m:" in result.response
    
    @pytest.mark.asyncio
    async def test_earthquake_command(self, command_handler, test_context):
        """Test earthquake data command"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock empty earthquake data
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"features": []}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await command_handler._handle_reference_command(
                Mock(command='earthquake', parameters=[]), 
                test_context
            )
            
            assert result.success
            assert "No significant earthquakes" in result.response
    
    @pytest.mark.asyncio
    async def test_sun_command(self, command_handler, test_context):
        """Test sun information command"""
        result = await command_handler._handle_reference_command(
            Mock(command='sun', parameters=[]), 
            test_context
        )
        
        assert result.success
        assert "Sun Information" in result.response
        assert "Sunrise:" in result.response
        assert "Sunset:" in result.response
    
    @pytest.mark.asyncio
    async def test_moon_command(self, command_handler, test_context):
        """Test moon phase command"""
        result = await command_handler._handle_reference_command(
            Mock(command='moon', parameters=[]), 
            test_context
        )
        
        assert result.success
        assert "Moon Information" in result.response
        assert "Phase:" in result.response
        assert "Illumination:" in result.response
    
    @pytest.mark.asyncio
    async def test_tide_command(self, command_handler, test_context):
        """Test tide information command"""
        result = await command_handler._handle_reference_command(
            Mock(command='tide', parameters=[]), 
            test_context
        )
        
        assert result.success
        assert "Tide Information" in result.response
        assert "location-specific data" in result.response
    
    @pytest.mark.asyncio
    async def test_riverflow_command(self, command_handler, test_context):
        """Test river flow command"""
        result = await command_handler._handle_reference_command(
            Mock(command='riverflow', parameters=[]), 
            test_context
        )
        
        assert result.success
        assert "River Flow Information" in result.response
        assert "USGS Water Services API" in result.response
    
    @pytest.mark.asyncio
    async def test_invalid_reference_command(self, command_handler, test_context):
        """Test handling of invalid reference command"""
        result = await command_handler._handle_reference_command(
            Mock(command='invalid_ref_command', parameters=[]), 
            test_context
        )
        
        assert result.success
        assert "not implemented yet" in result.response


class TestCommandCategories:
    """Test command categorization"""
    
    def test_educational_commands_list(self, command_handler):
        """Test educational commands are properly categorized"""
        educational_commands = command_handler._get_educational_commands()
        
        assert 'hamtest' in educational_commands
        assert 'quiz' in educational_commands
        assert 'survey' in educational_commands
        assert len(educational_commands) == 3
    
    def test_reference_commands_list(self, command_handler):
        """Test reference commands are properly categorized"""
        reference_commands = command_handler._get_reference_commands()
        
        assert 'solar' in reference_commands
        assert 'hfcond' in reference_commands
        assert 'earthquake' in reference_commands
        assert 'sun' in reference_commands
        assert 'moon' in reference_commands
        assert 'tide' in reference_commands
        assert 'riverflow' in reference_commands
        assert len(reference_commands) == 7
    
    def test_information_commands_updated(self, command_handler):
        """Test information commands no longer include reference commands"""
        information_commands = command_handler._get_information_commands()
        
        # These should NOT be in information commands anymore
        assert 'solar' not in information_commands
        assert 'hfcond' not in information_commands
        assert 'earthquake' not in information_commands
        
        # These should still be in information commands
        assert 'whereami' in information_commands
        assert 'whoami' in information_commands
        assert 'wiki' in information_commands