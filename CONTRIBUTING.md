# Contributing to ZephyrGate

Thank you for your interest in contributing to ZephyrGate! This document provides guidelines and information for contributors.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Contributing Guidelines](#contributing-guidelines)
5. [Pull Request Process](#pull-request-process)
6. [Issue Reporting](#issue-reporting)
7. [Development Standards](#development-standards)
8. [Testing](#testing)
9. [Documentation](#documentation)
10. [Community](#community)

## Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

Examples of behavior that contributes to creating a positive environment include:

- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported by contacting the project team. All complaints will be reviewed and investigated promptly and fairly.

## Getting Started

### Ways to Contribute

- **Code Contributions**: Bug fixes, new features, performance improvements
- **Documentation**: Improve existing docs, write tutorials, create examples
- **Testing**: Write tests, report bugs, test on different platforms
- **Design**: UI/UX improvements, graphics, logos
- **Community**: Help other users, answer questions, moderate discussions
- **Translation**: Translate documentation and interface text

### First-Time Contributors

If you're new to contributing to open source projects:

1. Look for issues labeled `good first issue` or `help wanted`
2. Read through the codebase to understand the architecture
3. Start with small changes like documentation improvements
4. Ask questions in discussions or issues if you need help

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git
- Docker (optional, for containerized development)
- SQLite 3.35+
- A Meshtastic device (for testing) or simulator

### Local Development Environment

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/your-username/zephyrgate.git
   cd zephyrgate
   ```

2. **Create a virtual environment:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

4. **Set up pre-commit hooks:**

   ```bash
   pre-commit install
   ```

5. **Create development configuration:**

   ```bash
   cp config/config-example.yaml config/development.yaml
   # Edit development.yaml with your settings
   ```

6. **Initialize the database:**

   ```bash
   python src/main.py --init-db
   ```

7. **Run the application:**
   ```bash
   python src/main.py --config config/development.yaml
   ```

### Docker Development Environment

1. **Build development image:**

   ```bash
   docker-compose -f docker-compose.dev.yml build
   ```

2. **Start development environment:**

   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

3. **Access the container:**
   ```bash
   docker-compose -f docker-compose.dev.yml exec zephyrgate bash
   ```

## Contributing Guidelines

### Branch Strategy

- **main**: Production-ready code
- **develop**: Integration branch for features
- **feature/**: Feature branches (e.g., `feature/emergency-alerts`)
- **bugfix/**: Bug fix branches (e.g., `bugfix/database-connection`)
- **hotfix/**: Critical fixes for production

### Workflow

1. **Create a feature branch:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes:**

   - Write code following our style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes:**

   ```bash
   # Run unit tests
   python -m pytest tests/unit/

   # Run integration tests
   python -m pytest tests/integration/

   # Run linting
   flake8 src/
   black --check src/
   ```

4. **Commit your changes:**

   ```bash
   git add .
   git commit -m "feat: add emergency alert escalation"
   ```

5. **Push and create pull request:**
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**

```
feat(emergency): add automatic escalation for SOS alerts
fix(bbs): resolve message synchronization issue
docs(api): update REST API documentation
test(weather): add unit tests for weather service
```

## Pull Request Process

### Before Submitting

1. **Ensure your code follows our standards:**

   - Code passes all tests
   - Code follows style guidelines
   - Documentation is updated
   - No merge conflicts with main branch

2. **Update the changelog:**

   - Add entry to `CHANGELOG.md` if applicable
   - Follow the existing format

3. **Test thoroughly:**
   - Test on multiple platforms if possible
   - Verify backward compatibility
   - Test edge cases

### Pull Request Template

When creating a pull request, use this template:

```markdown
## Description

Brief description of changes made.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] Changelog updated

## Related Issues

Closes #123
```

### Review Process

1. **Automated checks:** All CI/CD checks must pass
2. **Code review:** At least one maintainer must approve
3. **Testing:** Changes are tested in development environment
4. **Documentation:** Documentation is reviewed for accuracy
5. **Merge:** Maintainer merges the pull request

## Issue Reporting

### Bug Reports

When reporting bugs, please include:

1. **Environment information:**

   - OS and version
   - Python version
   - ZephyrGate version
   - Meshtastic device model

2. **Steps to reproduce:**

   - Clear, numbered steps
   - Expected behavior
   - Actual behavior

3. **Additional context:**
   - Error messages or logs
   - Screenshots if applicable
   - Configuration files (sanitized)

### Feature Requests

When requesting features:

1. **Use case:** Describe the problem you're trying to solve
2. **Proposed solution:** Your idea for implementing the feature
3. **Alternatives:** Other solutions you've considered
4. **Additional context:** Any other relevant information

### Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Improvements or additions to documentation
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention is needed
- `question`: Further information is requested
- `wontfix`: This will not be worked on

## Development Standards

### Code Style

We use the following tools and standards:

- **Python**: PEP 8 with Black formatter
- **Line length**: 88 characters (Black default)
- **Import sorting**: isort
- **Linting**: flake8 with additional plugins
- **Type hints**: Required for new code

### Code Quality Tools

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/

# Security scanning
bandit -r src/
```

### Architecture Guidelines

1. **Modularity**: Keep components loosely coupled
2. **Single Responsibility**: Each class/function should have one purpose
3. **Dependency Injection**: Use dependency injection for testability
4. **Error Handling**: Comprehensive error handling and logging
5. **Configuration**: Use configuration files, not hardcoded values

### Database Guidelines

1. **Migrations**: All schema changes must have migrations
2. **Transactions**: Use transactions for data consistency
3. **Indexing**: Add appropriate indexes for performance
4. **Validation**: Validate data at the application level

## Testing

### Test Structure

```
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
├── fixtures/       # Test data and fixtures
├── mocks/          # Mock objects
└── conftest.py     # Pytest configuration
```

### Writing Tests

1. **Unit Tests:**

   - Test individual functions/methods
   - Use mocks for external dependencies
   - Aim for high code coverage

2. **Integration Tests:**

   - Test component interactions
   - Use test database
   - Test real scenarios

3. **Test Naming:**
   ```python
   def test_should_create_sos_alert_when_valid_message_received():
       # Test implementation
   ```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/unit/test_emergency_service.py

# Run with coverage
python -m pytest --cov=src tests/

# Run integration tests only
python -m pytest tests/integration/
```

### Test Guidelines

- Write tests for all new functionality
- Maintain or improve code coverage
- Use descriptive test names
- Keep tests simple and focused
- Mock external dependencies

## Documentation

### Documentation Types

1. **Code Documentation:**

   - Docstrings for all public functions/classes
   - Inline comments for complex logic
   - Type hints for function signatures

2. **User Documentation:**

   - User manual and guides
   - API documentation
   - Configuration examples

3. **Developer Documentation:**
   - Architecture documentation
   - Setup and development guides
   - Contributing guidelines

### Documentation Standards

- Use clear, concise language
- Include code examples
- Keep documentation up-to-date with code changes
- Use proper Markdown formatting
- Include diagrams where helpful

### Building Documentation

```bash
# Install documentation dependencies
pip install -r docs/requirements.txt

# Build documentation
cd docs/
make html

# Serve documentation locally
python -m http.server 8000 -d _build/html/
```

## Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and community discussion
- **Discord**: Real-time chat and support (link in README)
- **Email**: Direct contact for sensitive issues

### Community Guidelines

1. **Be respectful**: Treat all community members with respect
2. **Be helpful**: Help others when you can
3. **Be patient**: Remember that everyone has different experience levels
4. **Stay on topic**: Keep discussions relevant to ZephyrGate
5. **Search first**: Check existing issues and discussions before posting

### Recognition

We recognize contributors in several ways:

- **Contributors file**: Listed in CONTRIBUTORS.md
- **Release notes**: Mentioned in release announcements
- **Hall of fame**: Featured on project website
- **Badges**: GitHub profile badges for significant contributions

## Getting Help

If you need help with contributing:

1. **Read the documentation**: Check existing docs first
2. **Search issues**: Look for similar questions or problems
3. **Ask in discussions**: Use GitHub Discussions for questions
4. **Join Discord**: Get real-time help from the community
5. **Contact maintainers**: Email for sensitive or urgent issues

## License

By contributing to ZephyrGate, you agree that your contributions will be licensed under the GNU General Public License v3.0.

---

Thank you for contributing to ZephyrGate! Your efforts help make this project better for everyone in the Meshtastic community.
