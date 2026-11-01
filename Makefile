# DriftCheck Makefile

.PHONY: lint type test check examples eval install dev-install clean

# Default target
all: check

# Linting with ruff
lint:
	ruff check driftcheck tests
	ruff format --check driftcheck tests

# Type checking with mypy
type:
	mypy driftcheck

# Testing with pytest
test:
	pytest -q --cov=driftcheck --cov-report=term-missing

# Run all checks
check: lint type test

# Install in development mode
install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

# Run examples (generate outputs)
examples:
	python scripts/make_examples.py

# Run evaluation
eval:
	python -m driftcheck eval --help

# Clean build artifacts
clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Help
help:
	@echo "Available targets:"
	@echo "  lint        - Run ruff linting and format check"
	@echo "  type        - Run mypy type checking"
	@echo "  test        - Run pytest with coverage"
	@echo "  check       - Run all checks (lint, type, test)"
	@echo "  install     - Install package in development mode"
	@echo "  dev-install - Install package with dev dependencies"
	@echo "  examples    - Generate example outputs"
	@echo "  eval        - Run evaluation"
	@echo "  clean       - Clean build artifacts"