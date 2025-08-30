.PHONY: help build run stop clean test docker-test dev install lint format

# Default target
help:
	@echo "Available commands:"
	@echo "  build        - Build Docker image"
	@echo "  run          - Run with Docker Compose"
	@echo "  stop         - Stop Docker Compose"
	@echo "  clean        - Clean Docker images and containers"
	@echo "  test         - Run tests"
	@echo "  docker-test  - Test Docker build"
	@echo "  dev          - Run in development mode"
	@echo "  install      - Install dependencies"
	@echo "  lint         - Run linter"
	@echo "  format       - Format code"

# Docker commands
build:
	docker build -t cfgapp .

run:
	docker-compose up -d

stop:
	docker-compose down

clean:
	docker-compose down --rmi all --volumes --remove-orphans
	docker system prune -f

# Development commands
dev:
	poetry run python -m src.main

install:
	poetry install

test:
	poetry run pytest tests/ -v

lint:
	poetry run ruff check src/ tests/

format:
	poetry run ruff format src/ tests/

# Docker testing
docker-test:
	@echo "Testing Docker build..."
	docker build -t cfgapp-test .
	@echo "Testing if templates are included..."
	docker run --rm cfgapp-test ls -la /app/templates/
	@echo "Testing if application starts..."
	docker run --rm -d --name cfgapp-test-run -p 8001:8000 cfgapp-test
	@sleep 3
	@curl -f http://localhost:8001/health || echo "Health check failed"
	@docker stop cfgapp-test-run
	@docker rmi cfgapp-test
	@echo "Docker test completed!"

# Combined commands
all: install lint test build

deploy: build run

check: lint test
