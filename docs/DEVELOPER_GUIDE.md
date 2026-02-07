# ZephyrGate Developer Guide

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Architecture Overview](#architecture-overview)
3. [Code Organization](#code-organization)
4. [Development Workflow](#development-workflow)
5. [Testing Strategy](#testing-strategy)
6. [API Development](#api-development)
7. [Plugin Development](#plugin-development)
8. [Database Development](#database-development)
9. [Frontend Development](#frontend-development)
10. [Debugging and Profiling](#debugging-and-profiling)
11. [Performance Optimization](#performance-optimization)
12. [Security Considerations](#security-considerations)

## Development Environment Setup

### Prerequisites

- Python 3.9+
- Git
- Docker and Docker Compose
- SQLite 3.35+
- Node.js 16+ (for frontend development)
- A Meshtastic device or simulator

### Quick Setup

```bash
# Clone repository
git clone https://github.com/your-repo/zephyrgate.git
cd zephyrgate

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Set up configuration
cp config/config-example.yaml config/development.yaml
# Edit development.yaml with your settings

# Initialize database
python src/main.py --init-db

# Run tests to verify setup
python -m pytest tests/unit/
```

### IDE Configuration

#### VS Code

Recommended extensions:
- Python
- Pylance
- Black Formatter
- isort
- GitLens
- Docker

Settings (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    }
}
```

#### PyCharm

1. Open project in PyCharm
2. Configure Python interpreter to use `./venv/bin/python`
3. Enable Black formatter in Settings → Tools → External Tools
4. Configure pytest as test runner
5. Enable code inspections for Python

### Development Tools

#### Code Quality Tools

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/
pylint src/

# Type checking
mypy src/

# Security scanning
bandit -r src/

# Dependency scanning
safety check
```

#### Git Hooks

Pre-commit configuration (`.pre-commit-config.yaml`):
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 22.3.0
    hooks:
      - id: black
        language_version: python3.9

  - repo: https://github.com/pycqa/isort
    rev: 5.10.1
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 4.0.1
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v0.950
    hooks:
      - id: mypy
```

## Architecture Overview

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ZephyrGate Application                   │
├─────────────────────────────────────────────────────────────┤
│  Web Interface (FastAPI)  │  Message Router  │  Plugin Mgr  │
├─────────────────────────────────────────────────────────────┤
│  Emergency │  BBS  │  Bot  │  Weather │  Email │  Asset     │
│  Service   │  Svc  │  Svc  │  Service │  Svc   │  Tracking  │
├─────────────────────────────────────────────────────────────┤
│         Core Infrastructure (Config, DB, Logging)          │
├─────────────────────────────────────────────────────────────┤
│  Meshtastic Interfaces (Serial, TCP, BLE)  │  External APIs │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Modularity**: Each service is independent and pluggable
2. **Separation of Concerns**: Clear boundaries between components
3. **Dependency Injection**: Services receive dependencies via constructor
4. **Event-Driven**: Services communicate through events and message routing
5. **Configuration-Driven**: Behavior controlled through configuration files
6. **Testability**: All components are unit testable with mocks

### Core Components

#### Message Router
Central hub for all message processing:
- Receives messages from Meshtastic interfaces
- Routes messages to appropriate services
- Handles message queuing and rate limiting
- Manages response coordination

#### Service Manager
Manages service lifecycle:
- Loads and initializes services
- Handles service dependencies
- Monitors service health
- Provides service discovery

#### Configuration Manager
Handles all configuration:
- Loads configuration from multiple sources
- Validates configuration values
- Provides runtime configuration updates
- Manages environment-specific settings

## Code Organization

### Directory Structure

```
src/
├── core/                   # Core infrastructure
│   ├── config.py          # Configuration management
│   ├── database.py        # Database connections and migrations
│   ├── interfaces.py      # Core interfaces and protocols
│   ├── logging.py         # Logging configuration
│   ├── message_router.py  # Central message routing
│   ├── plugin_manager.py  # Plugin lifecycle management
│   └── service_manager.py # Service management
├── models/                 # Data models
│   ├── message.py         # Message models
│   └── user.py            # User models
├── services/              # Service modules
│   ├── emergency/         # Emergency response service
│   ├── bbs/              # Bulletin board system
│   ├── bot/              # Interactive bot service
│   ├── weather/          # Weather and alert service
│   ├── email/            # Email gateway service
│   ├── asset/            # Asset tracking service
│   └── web/              # Web administration service
├── utils/                 # Utility functions
└── main.py               # Application entry point
```

### Service Structure

Each service follows a consistent structure:

```
services/example/
├── __init__.py           # Service exports
├── service.py           # Main service class
├── models.py            # Service-specific models
├── handlers.py          # Message/command handlers
├── database.py          # Database operations
├── config.py            # Service configuration
└── utils.py             # Service utilities
```

### Naming Conventions

- **Classes**: PascalCase (`MessageRouter`, `EmergencyService`)
- **Functions/Methods**: snake_case (`process_message`, `handle_sos`)
- **Variables**: snake_case (`user_id`, `message_content`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_MESSAGE_SIZE`, `DEFAULT_TIMEOUT`)
- **Files/Modules**: snake_case (`message_router.py`, `emergency_service.py`)

## Development Workflow

### Feature Development

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/emergency-escalation
   ```

2. **Implement Feature**
   - Write failing tests first (TDD approach)
   - Implement minimum viable functionality
   - Refactor and optimize
   - Add comprehensive tests

3. **Test Thoroughly**
   ```bash
   # Unit tests
   python -m pytest tests/unit/test_emergency_service.py -v
   
   # Integration tests
   python -m pytest tests/integration/test_emergency_integration.py -v
   
   # Full test suite
   python -m pytest --cov=src tests/
   ```

4. **Code Quality Checks**
   ```bash
   # Format and lint
   black src/ tests/
   isort src/ tests/
   flake8 src/ tests/
   mypy src/
   ```

5. **Update Documentation**
   - Update docstrings
   - Update user documentation
   - Update API documentation
   - Add configuration examples

6. **Create Pull Request**
   - Use descriptive title and description
   - Link related issues
   - Include testing instructions
   - Request appropriate reviewers

### Bug Fix Workflow

1. **Reproduce Bug**
   - Create failing test that reproduces the issue
   - Document expected vs actual behavior

2. **Fix Bug**
   - Make minimal changes to fix the issue
   - Ensure fix doesn't break existing functionality

3. **Verify Fix**
   - Ensure test now passes
   - Run full test suite
   - Test manually if needed

4. **Document Fix**
   - Update changelog
   - Add comments explaining the fix
   - Update documentation if needed

## Testing Strategy

### Test Types

#### Unit Tests
Test individual components in isolation:

```python
# tests/unit/test_emergency_service.py
import pytest
from unittest.mock import Mock, patch
from src.services.emergency.service import EmergencyService

class TestEmergencyService:
    def setup_method(self):
        self.config = Mock()
        self.db = Mock()
        self.message_router = Mock()
        self.service = EmergencyService(self.config, self.db, self.message_router)
    
    def test_should_create_sos_incident_when_sos_message_received(self):
        # Arrange
        message = Mock()
        message.content = "SOS Need help at coordinates"
        message.sender_id = "!12345678"
        
        # Act
        result = self.service.handle_sos_message(message)
        
        # Assert
        assert result.incident_type == "SOS"
        assert result.sender_id == "!12345678"
        self.db.create_incident.assert_called_once()
```

#### Integration Tests
Test component interactions:

```python
# tests/integration/test_emergency_integration.py
import pytest
from src.core.message_router import MessageRouter
from src.services.emergency.service import EmergencyService
from tests.fixtures import create_test_message

class TestEmergencyIntegration:
    def setup_method(self):
        self.router = MessageRouter()
        self.emergency_service = EmergencyService()
        self.router.register_service(self.emergency_service)
    
    def test_sos_message_flow_end_to_end(self):
        # Arrange
        sos_message = create_test_message("SOS Help needed")
        
        # Act
        self.router.process_message(sos_message)
        
        # Assert
        incidents = self.emergency_service.get_active_incidents()
        assert len(incidents) == 1
        assert incidents[0].message == "Help needed"
```

#### End-to-End Tests
Test complete user workflows:

```python
# tests/e2e/test_emergency_workflow.py
import pytest
from tests.utils import MeshtasticSimulator, WebClient

class TestEmergencyWorkflow:
    def test_complete_sos_response_workflow(self):
        # Simulate SOS alert from field user
        simulator = MeshtasticSimulator()
        simulator.send_message("!field001", "SOS Lost in woods, GPS: 40.7128,-74.0060")
        
        # Verify alert appears in web interface
        web_client = WebClient()
        alerts = web_client.get_active_alerts()
        assert len(alerts) == 1
        
        # Simulate responder acknowledgment
        simulator.send_message("!responder001", "ACK 1")
        
        # Verify incident is acknowledged
        incident = web_client.get_incident(1)
        assert incident.status == "acknowledged"
        assert "!responder001" in incident.responders
```

### Test Fixtures and Utilities

```python
# tests/fixtures.py
import pytest
from src.models.message import Message
from src.models.user import User

@pytest.fixture
def sample_user():
    return User(
        node_id="!12345678",
        short_name="TestUser",
        long_name="Test User",
        email="test@example.com"
    )

@pytest.fixture
def sample_message():
    return Message(
        id="msg_001",
        sender_id="!12345678",
        content="Test message",
        timestamp=datetime.utcnow(),
        channel=0
    )

def create_test_message(content, sender_id="!12345678"):
    return Message(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        sender_id=sender_id,
        content=content,
        timestamp=datetime.utcnow(),
        channel=0
    )
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/unit/test_emergency_service.py

# Run tests with coverage
python -m pytest --cov=src --cov-report=html tests/

# Run tests in parallel
python -m pytest -n auto tests/

# Run only failed tests
python -m pytest --lf

# Run tests matching pattern
python -m pytest -k "emergency" tests/
```

## API Development

### REST API Structure

ZephyrGate uses FastAPI for the web interface and REST API:

```python
# src/services/web/api/emergency.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from ..models import IncidentResponse, CreateIncidentRequest
from ..dependencies import get_emergency_service

router = APIRouter(prefix="/api/emergency", tags=["emergency"])

@router.get("/incidents", response_model=List[IncidentResponse])
async def get_incidents(
    emergency_service = Depends(get_emergency_service)
):
    """Get all active incidents."""
    incidents = await emergency_service.get_active_incidents()
    return [IncidentResponse.from_model(incident) for incident in incidents]

@router.post("/incidents", response_model=IncidentResponse)
async def create_incident(
    request: CreateIncidentRequest,
    emergency_service = Depends(get_emergency_service)
):
    """Create a new incident."""
    incident = await emergency_service.create_incident(
        incident_type=request.incident_type,
        message=request.message,
        sender_id=request.sender_id
    )
    return IncidentResponse.from_model(incident)
```

### API Models

```python
# src/services/web/models.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class IncidentType(str, Enum):
    SOS = "SOS"
    SOSP = "SOSP"
    SOSF = "SOSF"
    SOSM = "SOSM"

class IncidentStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

class CreateIncidentRequest(BaseModel):
    incident_type: IncidentType
    message: str
    sender_id: str = Field(..., regex=r"^![0-9a-f]{8}$")
    location: Optional[tuple[float, float]] = None

class IncidentResponse(BaseModel):
    id: str
    incident_type: IncidentType
    status: IncidentStatus
    message: str
    sender_id: str
    location: Optional[tuple[float, float]]
    created_at: datetime
    responders: List[str]
    
    @classmethod
    def from_model(cls, incident):
        return cls(
            id=incident.id,
            incident_type=incident.incident_type,
            status=incident.status,
            message=incident.message,
            sender_id=incident.sender_id,
            location=incident.location,
            created_at=incident.created_at,
            responders=incident.responders
        )
```

### API Documentation

FastAPI automatically generates OpenAPI documentation:

```python
# src/services/web/main.py
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(
    title="ZephyrGate API",
    description="Unified Meshtastic Gateway API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Custom API documentation
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="ZephyrGate API Documentation",
        swagger_favicon_url="/static/favicon.ico"
    )
```

## Plugin Development

### Plugin Interface

```python
# src/core/plugin_interfaces.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from .message_router import MessageRouter

class ServicePlugin(ABC):
    """Base interface for all service plugins."""
    
    def __init__(self, config: Dict[str, Any], message_router: MessageRouter):
        self.config = config
        self.message_router = message_router
        self.enabled = config.get('enabled', True)
    
    @abstractmethod
    async def start(self) -> None:
        """Start the service plugin."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the service plugin."""
        pass
    
    @abstractmethod
    async def handle_message(self, message) -> Optional[Any]:
        """Handle incoming message."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Service name."""
        pass
    
    @property
    def health_status(self) -> Dict[str, Any]:
        """Return service health status."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "status": "healthy"
        }
```

### Creating a Custom Plugin

```python
# src/services/custom/my_plugin.py
from typing import Dict, Any, Optional
from src.core.plugin_interfaces import ServicePlugin
from src.models.message import Message

class MyCustomPlugin(ServicePlugin):
    """Custom plugin example."""
    
    @property
    def name(self) -> str:
        return "my_custom_plugin"
    
    async def start(self) -> None:
        """Initialize the plugin."""
        self.logger = logging.getLogger(f"zephyr.{self.name}")
        self.logger.info(f"Starting {self.name}")
        
        # Register message handlers
        self.message_router.register_handler(
            pattern=r"^CUSTOM:",
            handler=self.handle_custom_command
        )
    
    async def stop(self) -> None:
        """Cleanup plugin resources."""
        self.logger.info(f"Stopping {self.name}")
    
    async def handle_message(self, message: Message) -> Optional[str]:
        """Handle incoming messages."""
        if message.content.startswith("CUSTOM:"):
            return await self.handle_custom_command(message)
        return None
    
    async def handle_custom_command(self, message: Message) -> str:
        """Handle custom commands."""
        command = message.content[7:]  # Remove "CUSTOM:" prefix
        
        if command == "STATUS":
            return "Custom plugin is running!"
        elif command == "VERSION":
            return "Custom plugin v1.0.0"
        else:
            return f"Unknown custom command: {command}"
```

### Plugin Registration

```python
# src/core/plugin_manager.py
class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.plugin_configs = {}
    
    def register_plugin(self, plugin_class, config):
        """Register a plugin class with configuration."""
        plugin_name = plugin_class.__name__.lower()
        self.plugin_configs[plugin_name] = config
        
        # Instantiate plugin
        plugin = plugin_class(config, self.message_router)
        self.plugins[plugin_name] = plugin
        
        return plugin
    
    async def start_all_plugins(self):
        """Start all registered plugins."""
        for plugin in self.plugins.values():
            if plugin.enabled:
                await plugin.start()
    
    async def stop_all_plugins(self):
        """Stop all plugins."""
        for plugin in self.plugins.values():
            await plugin.stop()
```

## Database Development

### Database Schema Management

ZephyrGate uses SQLite with Alembic for migrations:

```python
# src/core/database.py
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

Base = declarative_base()

class DatabaseManager:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.metadata = MetaData()
    
    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def run_migrations(self):
        """Run database migrations."""
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
    
    def get_session(self):
        """Get database session."""
        return self.SessionLocal()
```

### Model Definition

```python
# src/models/emergency.py
from sqlalchemy import Column, String, DateTime, Boolean, Text, Float
from sqlalchemy.sql import func
from src.core.database import Base

class SOSIncident(Base):
    __tablename__ = "sos_incidents"
    
    id = Column(String, primary_key=True)
    incident_type = Column(String, nullable=False)
    sender_id = Column(String, nullable=False)
    message = Column(Text)
    location_lat = Column(Float)
    location_lon = Column(Float)
    status = Column(String, default="active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    escalated = Column(Boolean, default=False)
    
    def to_dict(self):
        return {
            "id": self.id,
            "incident_type": self.incident_type,
            "sender_id": self.sender_id,
            "message": self.message,
            "location": (self.location_lat, self.location_lon) if self.location_lat else None,
            "status": self.status,
            "created_at": self.created_at,
            "escalated": self.escalated
        }
```

### Database Operations

```python
# src/services/emergency/database.py
from typing import List, Optional
from sqlalchemy.orm import Session
from src.models.emergency import SOSIncident
from src.core.database import DatabaseManager

class EmergencyDatabase:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def create_incident(self, incident_data: dict) -> SOSIncident:
        """Create a new SOS incident."""
        with self.db_manager.get_session() as session:
            incident = SOSIncident(**incident_data)
            session.add(incident)
            session.commit()
            session.refresh(incident)
            return incident
    
    def get_active_incidents(self) -> List[SOSIncident]:
        """Get all active incidents."""
        with self.db_manager.get_session() as session:
            return session.query(SOSIncident).filter(
                SOSIncident.status == "active"
            ).all()
    
    def update_incident_status(self, incident_id: str, status: str) -> Optional[SOSIncident]:
        """Update incident status."""
        with self.db_manager.get_session() as session:
            incident = session.query(SOSIncident).filter(
                SOSIncident.id == incident_id
            ).first()
            
            if incident:
                incident.status = status
                session.commit()
                session.refresh(incident)
            
            return incident
```

### Database Migrations

```python
# migrations/versions/001_create_sos_incidents.py
"""Create SOS incidents table

Revision ID: 001
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'sos_incidents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('incident_type', sa.String(), nullable=False),
        sa.Column('sender_id', sa.String(), nullable=False),
        sa.Column('message', sa.Text()),
        sa.Column('location_lat', sa.Float()),
        sa.Column('location_lon', sa.Float()),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime()),
        sa.Column('escalated', sa.Boolean(), default=False),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('sos_incidents')
```

## Frontend Development

### Web Interface Structure

```
src/services/web/
├── static/
│   ├── css/
│   │   └── dashboard.css
│   ├── js/
│   │   ├── dashboard.js
│   │   └── components/
│   └── images/
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   └── components/
└── api/
    ├── emergency.py
    ├── bbs.py
    └── system.py
```

### Frontend Technologies

- **HTML5**: Semantic markup
- **CSS3**: Modern styling with Flexbox/Grid
- **JavaScript (ES6+)**: Modern JavaScript features
- **WebSockets**: Real-time updates
- **Chart.js**: Data visualization
- **Bootstrap**: Responsive design framework

### Real-time Updates

```javascript
// src/services/web/static/js/dashboard.js
class Dashboard {
    constructor() {
        this.websocket = null;
        this.charts = {};
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.initializeCharts();
        this.bindEvents();
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
        };
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected, reconnecting...');
            setTimeout(() => this.connectWebSocket(), 5000);
        };
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'incident_created':
                this.addIncidentToTable(data.incident);
                break;
            case 'system_stats':
                this.updateSystemStats(data.stats);
                break;
            case 'message_received':
                this.addMessageToFeed(data.message);
                break;
        }
    }
    
    addIncidentToTable(incident) {
        const table = document.getElementById('incidents-table');
        const row = table.insertRow(1); // Insert after header
        
        row.innerHTML = `
            <td>${incident.id}</td>
            <td><span class="badge badge-${this.getIncidentBadgeClass(incident.type)}">${incident.type}</span></td>
            <td>${incident.sender_id}</td>
            <td>${incident.message}</td>
            <td>${new Date(incident.created_at).toLocaleString()}</td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="dashboard.acknowledgeIncident('${incident.id}')">
                    Acknowledge
                </button>
            </td>
        `;
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});
```

## Debugging and Profiling

### Logging Configuration

```python
# src/core/logging.py
import logging
import logging.config
from typing import Dict, Any

def setup_logging(config: Dict[str, Any]) -> None:
    """Set up logging configuration."""
    
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
            'detailed': {
                'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
            },
            'json': {
                'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'standard',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'filename': 'logs/zephyrgate.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5
            }
        },
        'loggers': {
            'zephyr': {
                'level': config.get('log_level', 'INFO'),
                'handlers': ['console', 'file'],
                'propagate': False
            }
        }
    }
    
    logging.config.dictConfig(logging_config)
```

### Debug Mode

```python
# src/main.py
import logging
from src.core.config import ConfigurationManager

def main():
    config = ConfigurationManager()
    
    if config.get('debug', False):
        # Enable debug logging
        logging.getLogger('zephyr').setLevel(logging.DEBUG)
        
        # Enable SQL query logging
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        
        # Enable asyncio debug mode
        import asyncio
        asyncio.get_event_loop().set_debug(True)
```

### Performance Profiling

```python
# scripts/profile.py
import cProfile
import pstats
from src.main import main

def profile_application():
    """Profile the application startup and basic operations."""
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run application code
    main()
    
    profiler.disable()
    
    # Save profile results
    profiler.dump_stats('profile_results.prof')
    
    # Print top functions by cumulative time
    stats = pstats.Stats('profile_results.prof')
    stats.sort_stats('cumulative')
    stats.print_stats(20)

if __name__ == '__main__':
    profile_application()
```

### Memory Profiling

```python
# scripts/memory_profile.py
from memory_profiler import profile
from src.services.emergency.service import EmergencyService

@profile
def test_emergency_service_memory():
    """Profile memory usage of emergency service."""
    
    service = EmergencyService()
    
    # Simulate processing many incidents
    for i in range(1000):
        incident_data = {
            'id': f'incident_{i}',
            'incident_type': 'SOS',
            'sender_id': f'!{i:08x}',
            'message': f'Test incident {i}'
        }
        service.create_incident(incident_data)
    
    # Check memory usage
    incidents = service.get_active_incidents()
    print(f"Created {len(incidents)} incidents")

if __name__ == '__main__':
    test_emergency_service_memory()
```

## Performance Optimization

### Database Optimization

```python
# src/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

class OptimizedDatabaseManager:
    def __init__(self, database_url: str):
        # Optimize SQLite for performance
        engine_args = {
            'echo': False,
            'pool_pre_ping': True,
            'connect_args': {
                'check_same_thread': False,
                'timeout': 30,
                # SQLite optimizations
                'isolation_level': None,  # Autocommit mode
            }
        }
        
        if 'sqlite' in database_url:
            engine_args['poolclass'] = StaticPool
            engine_args['connect_args'].update({
                'pragma': {
                    'journal_mode': 'WAL',
                    'synchronous': 'NORMAL',
                    'cache_size': -64000,  # 64MB cache
                    'temp_store': 'MEMORY',
                    'mmap_size': 268435456,  # 256MB mmap
                }
            })
        
        self.engine = create_engine(database_url, **engine_args)
```

### Caching Strategy

```python
# src/core/cache.py
import redis
import json
from typing import Any, Optional
from functools import wraps

class CacheManager:
    def __init__(self, redis_url: str = None):
        if redis_url:
            self.redis = redis.from_url(redis_url)
        else:
            self.redis = None
        self.local_cache = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if self.redis:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
        
        return self.local_cache.get(key)
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set value in cache with TTL."""
        if self.redis:
            self.redis.setex(key, ttl, json.dumps(value))
        else:
            self.local_cache[key] = value

def cached(ttl: int = 3600):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator
```

### Async Optimization

```python
# src/core/async_utils.py
import asyncio
from typing import List, Callable, Any
from concurrent.futures import ThreadPoolExecutor

class AsyncOptimizer:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def run_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """Run blocking function in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)
    
    async def gather_with_limit(self, tasks: List, limit: int = 10) -> List[Any]:
        """Run tasks with concurrency limit."""
        semaphore = asyncio.Semaphore(limit)
        
        async def limited_task(task):
            async with semaphore:
                return await task
        
        limited_tasks = [limited_task(task) for task in tasks]
        return await asyncio.gather(*limited_tasks)
```

## Security Considerations

### Input Validation

```python
# src/core/validation.py
import re
from typing import Any, Dict
from pydantic import BaseModel, validator

class MessageValidator(BaseModel):
    content: str
    sender_id: str
    channel: int
    
    @validator('content')
    def validate_content(cls, v):
        if len(v) > 1000:
            raise ValueError('Message content too long')
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\']', '', v)
        return sanitized
    
    @validator('sender_id')
    def validate_sender_id(cls, v):
        if not re.match(r'^![0-9a-f]{8}$', v):
            raise ValueError('Invalid sender ID format')
        return v
    
    @validator('channel')
    def validate_channel(cls, v):
        if not 0 <= v <= 255:
            raise ValueError('Channel must be between 0 and 255')
        return v
```

### Authentication and Authorization

```python
# src/core/auth.py
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class AuthManager:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = 'HS256'
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    def create_token(self, user_data: Dict[str, Any], expires_in: int = 3600) -> str:
        """Create JWT token."""
        payload = {
            'user_data': user_data,
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload['user_data']
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
```

### Rate Limiting

```python
# src/core/rate_limiter.py
import time
from collections import defaultdict, deque
from typing import Dict, Deque

class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for identifier."""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        user_requests = self.requests[identifier]
        while user_requests and user_requests[0] < window_start:
            user_requests.popleft()
        
        # Check if under limit
        if len(user_requests) < self.max_requests:
            user_requests.append(now)
            return True
        
        return False
    
    def get_reset_time(self, identifier: str) -> float:
        """Get time when rate limit resets."""
        user_requests = self.requests[identifier]
        if not user_requests:
            return 0
        
        return user_requests[0] + self.window_seconds
```

This developer guide provides comprehensive information for contributing to ZephyrGate. For additional help, consult the API documentation, join our Discord community, or create an issue on GitHub.