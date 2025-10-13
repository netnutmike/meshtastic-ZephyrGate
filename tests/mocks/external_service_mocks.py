"""
Mock objects for external services used in ZephyrGate.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, AsyncMock, MagicMock
import json


class MockWeatherService:
    """Mock weather service for testing."""
    
    def __init__(self):
        self.api_calls = []
        self.weather_data = {
            "current": {
                "temperature": 22.5,
                "humidity": 65,
                "pressure": 1013.25,
                "wind_speed": 5.2,
                "wind_direction": 180,
                "description": "Partly cloudy",
                "icon": "partly-cloudy"
            },
            "forecast": [
                {
                    "date": datetime.utcnow().date(),
                    "high": 25,
                    "low": 18,
                    "description": "Sunny",
                    "precipitation": 0
                },
                {
                    "date": (datetime.utcnow() + timedelta(days=1)).date(),
                    "high": 23,
                    "low": 16,
                    "description": "Cloudy",
                    "precipitation": 20
                }
            ],
            "alerts": [
                {
                    "title": "Severe Thunderstorm Warning",
                    "description": "Severe thunderstorms expected in the area",
                    "severity": "severe",
                    "start": datetime.utcnow(),
                    "end": datetime.utcnow() + timedelta(hours=3)
                }
            ]
        }
    
    async def get_current_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        """Mock getting current weather."""
        self.api_calls.append(("current_weather", lat, lon))
        await asyncio.sleep(0.1)  # Simulate API delay
        return self.weather_data["current"]
    
    async def get_forecast(self, lat: float, lon: float, days: int = 5) -> List[Dict[str, Any]]:
        """Mock getting weather forecast."""
        self.api_calls.append(("forecast", lat, lon, days))
        await asyncio.sleep(0.1)
        return self.weather_data["forecast"][:days]
    
    async def get_alerts(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        """Mock getting weather alerts."""
        self.api_calls.append(("alerts", lat, lon))
        await asyncio.sleep(0.1)
        return self.weather_data["alerts"]
    
    def set_weather_data(self, data: Dict[str, Any]):
        """Set mock weather data."""
        self.weather_data.update(data)


class MockEmailService:
    """Mock email service for testing."""
    
    def __init__(self):
        self.sent_emails = []
        self.received_emails = []
        self.smtp_connected = False
        self.imap_connected = False
        self.blocklist = set()
    
    async def connect_smtp(self, host: str, port: int, username: str, password: str) -> bool:
        """Mock SMTP connection."""
        await asyncio.sleep(0.1)
        self.smtp_connected = True
        return True
    
    async def connect_imap(self, host: str, port: int, username: str, password: str) -> bool:
        """Mock IMAP connection."""
        await asyncio.sleep(0.1)
        self.imap_connected = True
        return True
    
    async def send_email(self, to: str, subject: str, body: str, from_addr: str = None) -> bool:
        """Mock sending email."""
        if not self.smtp_connected:
            raise ConnectionError("SMTP not connected")
        
        if to in self.blocklist:
            return False
        
        email = {
            "to": to,
            "from": from_addr or "gateway@example.com",
            "subject": subject,
            "body": body,
            "timestamp": datetime.utcnow()
        }
        
        self.sent_emails.append(email)
        await asyncio.sleep(0.1)
        return True
    
    async def check_emails(self) -> List[Dict[str, Any]]:
        """Mock checking for new emails."""
        if not self.imap_connected:
            raise ConnectionError("IMAP not connected")
        
        await asyncio.sleep(0.1)
        return self.received_emails.copy()
    
    def add_received_email(self, from_addr: str, subject: str, body: str):
        """Add a mock received email."""
        email = {
            "from": from_addr,
            "subject": subject,
            "body": body,
            "timestamp": datetime.utcnow()
        }
        self.received_emails.append(email)
    
    def add_to_blocklist(self, email: str):
        """Add email to blocklist."""
        self.blocklist.add(email)
    
    def remove_from_blocklist(self, email: str):
        """Remove email from blocklist."""
        self.blocklist.discard(email)


class MockAIService:
    """Mock AI service for testing."""
    
    def __init__(self):
        self.api_calls = []
        self.responses = {
            "default": "I'm a mock AI assistant. How can I help you?",
            "aircraft": "Hello pilot! I see you're flying at high altitude. Safe travels!",
            "emergency": "I understand this is an emergency. Help is on the way."
        }
    
    async def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Mock AI response generation."""
        self.api_calls.append((prompt, context))
        await asyncio.sleep(0.2)  # Simulate AI processing time
        
        # Simple response logic based on context
        if context and context.get("altitude", 0) > 1000:
            return self.responses["aircraft"]
        elif "SOS" in prompt.upper() or "EMERGENCY" in prompt.upper():
            return self.responses["emergency"]
        else:
            return self.responses["default"]
    
    def set_response(self, key: str, response: str):
        """Set mock response for specific scenarios."""
        self.responses[key] = response


class MockRedisService:
    """Mock Redis service for testing."""
    
    def __init__(self):
        self.data = {}
        self.connected = False
    
    async def connect(self) -> bool:
        """Mock Redis connection."""
        await asyncio.sleep(0.1)
        self.connected = True
        return True
    
    async def disconnect(self):
        """Mock Redis disconnection."""
        self.connected = False
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Mock setting a value."""
        if not self.connected:
            raise ConnectionError("Redis not connected")
        
        self.data[key] = {
            "value": value,
            "expire": datetime.utcnow() + timedelta(seconds=expire) if expire else None
        }
        return True
    
    async def get(self, key: str) -> Optional[Any]:
        """Mock getting a value."""
        if not self.connected:
            raise ConnectionError("Redis not connected")
        
        item = self.data.get(key)
        if not item:
            return None
        
        # Check expiration
        if item["expire"] and datetime.utcnow() > item["expire"]:
            del self.data[key]
            return None
        
        return item["value"]
    
    async def delete(self, key: str) -> bool:
        """Mock deleting a value."""
        if not self.connected:
            raise ConnectionError("Redis not connected")
        
        if key in self.data:
            del self.data[key]
            return True
        return False
    
    def clear(self):
        """Clear all mock data."""
        self.data.clear()


class MockHTTPClient:
    """Mock HTTP client for testing external API calls."""
    
    def __init__(self):
        self.requests = []
        self.responses = {}
        self.default_response = {"status": 200, "data": {}}
    
    async def get(self, url: str, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Mock HTTP GET request."""
        self.requests.append(("GET", url, headers))
        await asyncio.sleep(0.1)
        
        response = self.responses.get(url, self.default_response)
        if response["status"] != 200:
            raise Exception(f"HTTP {response['status']}")
        
        return response["data"]
    
    async def post(self, url: str, data: Dict[str, Any] = None, 
                   headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Mock HTTP POST request."""
        self.requests.append(("POST", url, data, headers))
        await asyncio.sleep(0.1)
        
        response = self.responses.get(url, self.default_response)
        if response["status"] != 200:
            raise Exception(f"HTTP {response['status']}")
        
        return response["data"]
    
    def set_response(self, url: str, status: int = 200, data: Dict[str, Any] = None):
        """Set mock response for a URL."""
        self.responses[url] = {
            "status": status,
            "data": data or {}
        }


# Factory functions for creating mock services
def create_mock_external_services():
    """Create all external service mocks."""
    return {
        "weather": MockWeatherService(),
        "email": MockEmailService(),
        "ai": MockAIService(),
        "redis": MockRedisService(),
        "http": MockHTTPClient()
    }


# Pytest fixtures (only available when pytest is installed)
try:
    import pytest

    @pytest.fixture
    def mock_weather_service():
        """Provide a mock weather service."""
        return MockWeatherService()

    @pytest.fixture
    def mock_email_service():
        """Provide a mock email service."""
        return MockEmailService()

    @pytest.fixture
    def mock_ai_service():
        """Provide a mock AI service."""
        return MockAIService()

    @pytest.fixture
    def mock_redis_service():
        """Provide a mock Redis service."""
        return MockRedisService()

    @pytest.fixture
    def mock_http_client():
        """Provide a mock HTTP client."""
        return MockHTTPClient()

    @pytest.fixture
    def mock_external_services(mock_weather_service, mock_email_service, 
                              mock_ai_service, mock_redis_service, mock_http_client):
        """Provide all external service mocks."""
        return {
            "weather": mock_weather_service,
            "email": mock_email_service,
            "ai": mock_ai_service,
            "redis": mock_redis_service,
            "http": mock_http_client
        }

except ImportError:
    # pytest not available, skip fixture definitions
    pass