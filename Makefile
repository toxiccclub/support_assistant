# Support Assistant Docker Management

.PHONY: help build up down restart logs test clean

# Default target
help:
	@echo "Support Assistant Docker Management"
	@echo "=================================="
	@echo ""
	@echo "Available commands:"
	@echo "  build     - Build Docker images"
	@echo "  up        - Start all services"
	@echo "  down      - Stop all services"
	@echo "  restart   - Restart all services"
	@echo "  logs      - Show logs from all services"
	@echo "  test      - Run test suite"
	@echo "  clean     - Clean up containers and images"
	@echo "  prod      - Start production environment"
	@echo "  dev       - Start development environment"
	@echo ""

# Development environment
dev: build up

# Production environment
prod:
	docker-compose -f docker-compose.prod.yml up -d

# Build images
build:
	docker-compose build

# Start services
up:
	docker-compose up -d
	@echo "Services started. Access at:"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

# Stop services
down:
	docker-compose down

# Restart services
restart: down up

# Show logs
logs:
	docker-compose logs -f

# Run tests
test:
	python test_setup.py

# Clean up
clean:
	docker-compose down -v --rmi all
	docker system prune -f

# Install dependencies (for local development)
install:
	pip install -r backend/requirements.txt

# Run backend locally
run-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

# Run frontend locally
run-frontend:
	cd frontend && python3 -m http.server 3000

# Check status
status:
	docker-compose ps

# Backup data
backup:
	docker-compose exec backend python -c "import json; print('Backup functionality not implemented yet')"

# Update services
update:
	docker-compose pull
	docker-compose up -d
