# Makefile for the Kubernetes MCP Agent

# Variables
IMAGE_NAME := kubernetes-mcp
TAG := latest
PIPENV_DIR := app

# Phony targets are not files.
.PHONY: all test build lint format clean help

# Default target: show help
default: help

all: format lint test build
	@echo "✅ All checks and build passed!"

test:
	@echo "🧪 Running tests..."
	PYTHONPATH=. pipenv run python -m pytest tests/

build:
	@echo "🏗️ Building Docker image..."
	docker build -t $(IMAGE_NAME):$(TAG) .

lint:
	@echo "🔍 Linting code with ruff..."
	(cd $(PIPENV_DIR) && pipenv run ruff check .)

format:
	@echo "🎨 Formatting code with ruff..."
	(cd $(PIPENV_DIR) && pipenv run ruff format .)

clean:
	@echo "🧹 Cleaning up..."
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -exec rm -rf {} +

help:
	@echo "Makefile for Kubernetes MCP Agent"
	@echo ""
	@echo "Usage:"
	@echo "  make all      - Run all checks (format, lint, test) and build the image."
	@echo "  make test     - Run the pytest test suite."
	@echo "  make build    - Build the Docker image."
	@echo "  make lint     - Check code for linting errors with ruff."
	@echo "  make format   - Format the code with ruff."
	@echo "  make clean    - Remove temporary Python files."
