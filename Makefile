# ZephyrGate Makefile
# Provides convenient commands for development and testing

.PHONY: help install test test-unit test-integration test-coverage test-fast clean lint format check

# Default target
help:
	@echo "ZephyrGate Development Commands"
	@echo "==============================="
	@echo ""
	@echo "Setup:"
	@echo "  install          Install dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-coverage    Run tests with coverage report"
	@echo "  test-fast        Run tests excluding slow ones"
	@echo "  test-parallel    Run tests in parallel"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             Run linting checks"
	@echo "  format           Format code with black and isort"
	@echo "  check            Run all quality checks"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean            Clean up temporary files"
	@echo "  clean-cache      Clean Python cache files"
	@echo ""

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install pytest-xdist pytest-mock

# Testing
test:
	python run_tests.py

test-unit:
	python run_tests.py --unit

test-integration:
	python run_tests.py --integration

test-coverage:
	python run_tests.py --coverage

test-fast:
	python run_tests.py --fast

test-parallel:
	python run_tests.py --parallel 4

# Specific test commands
test-meshtastic:
	python run_tests.py --markers meshtastic

test-database:
	python run_tests.py --markers database

test-external:
	python run_tests.py --markers external

# Code quality
lint:
	@echo "Running flake8..."
	flake8 src tests --max-line-length=100 --ignore=E203,W503
	@echo "Running mypy..."
	mypy src --ignore-missing-imports

format:
	@echo "Formatting with black..."
	black src tests --line-length=100
	@echo "Sorting imports with isort..."
	isort src tests --profile black

check: lint
	@echo "Running all quality checks..."
	python run_tests.py --fast
	@echo "All checks passed!"

# Cleanup
clean:
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.db" -delete
	find . -type f -name "*.tmp" -delete

clean-cache:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

# Docker testing
test-docker:
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
	docker-compose -f docker-compose.test.yml down

# Documentation
docs:
	@echo "Generating documentation..."
	mkdocs build

docs-serve:
	mkdocs serve

# Development server (for web interface testing)
dev-server:
	@echo "Starting development server..."
	python -m src.main --config config/default.yaml --debug

# Database operations
db-init:
	@echo "Initializing database..."
	python -c "from src.core.database import init_database; init_database()"

db-migrate:
	@echo "Running database migrations..."
	alembic upgrade head

# Quick development cycle
dev: format lint test-fast
	@echo "Development cycle complete!"

# CI/CD pipeline simulation
ci: clean install-dev check test-coverage
	@echo "CI pipeline simulation complete!"