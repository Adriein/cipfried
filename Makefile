# Path to venv Python
PYTHON = .venv/bin/python
PIP = .venv/bin/pip

# Default target
.PHONY: help
help:
	@echo "make venv       - Create virtual environment"
	@echo "make install    - Install dependencies from requirements.txt"
	@echo "make run        - Run the app (using venv)"
	@echo "make test       - Run tests with pytest"
	@echo "make clean      - Remove build artifacts"
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

# Run tests
test:
	$(PYTHON) -m pytest

# Build executable
build:
	$(PYTHON) -m pip install pyinstaller
	$(PYTHON) -m PyInstaller --onefile --name cipfried --icon=assets/monk_icon.png cipfried/main.py

# Clean artifacts
clean:
	rm -rf build dist __pycache__ .pytest_cache *.spec