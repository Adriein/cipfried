# Path to venv Python
PYTHON = .venv/bin/python
PIP = .venv/bin/pip

# Default target
.PHONY: help venv install run lint typecheck test check build clean
help:
	@echo "make venv       - Create virtual environment"
	@echo "make install    - Install the project and dev dependencies"
	@echo "make run        - Run the app (using venv)"
	@echo "make lint       - Run ruff"
	@echo "make typecheck  - Run mypy"
	@echo "make test       - Run the test suite"
	@echo "make check      - Run lint, typecheck, and tests"
	@echo "make clean      - Remove build artifacts and caches"
	@echo "make build      - Build executable with PyInstaller"

# Create venv
venv:
	python3 -m venv .venv
	$(PIP) install --upgrade pip

# Install dependencies
install: venv
	$(PIP) install -r requirements.txt

# Run app
run:
	$(PYTHON) -m cipfried.main

# Run linter
lint:
	$(PYTHON) -m ruff check .

# Run type checker
typecheck:
	$(PYTHON) -m mypy

# Run tests
test:
	$(PYTHON) -m pytest

# Run all checks
check: lint typecheck test

# Build executable
build: install
	$(PIP) install -e ".[build]"
	$(PYTHON) -m PyInstaller --onefile --name cipfried --icon=assets/monk_icon.png cipfried/main.py

# Clean artifacts
clean:
	rm -rf build dist .mypy_cache .ruff_cache *.spec
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
