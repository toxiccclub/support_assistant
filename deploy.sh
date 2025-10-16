#!/bin/bash

# Support Assistant Deployment Script
# This script helps deploy the Support Assistant application using Docker

set -e

echo "🚀 Support Assistant Deployment Script"
echo "======================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Function to show help
show_help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start     - Start the application (default)"
    echo "  stop      - Stop the application"
    echo "  restart   - Restart the application"
    echo "  build     - Build Docker images"
    echo "  test      - Run test suite"
    echo "  logs      - Show application logs"
    echo "  clean     - Clean up containers and images"
    echo "  prod      - Start production environment"
    echo "  help      - Show this help message"
    echo ""
}

# Function to start the application
start_app() {
    echo "🔧 Starting Support Assistant..."
    docker-compose up -d
    echo "✅ Application started successfully!"
    echo ""
    echo "🌐 Access the application at:"
    echo "   Frontend: http://localhost:3000"
    echo "   Backend API: http://localhost:8000"
    echo "   API Docs: http://localhost:8000/docs"
    echo ""
    echo "📊 To check status: docker-compose ps"
    echo "📋 To view logs: docker-compose logs -f"
}

# Function to stop the application
stop_app() {
    echo "🛑 Stopping Support Assistant..."
    docker-compose down
    echo "✅ Application stopped successfully!"
}

# Function to restart the application
restart_app() {
    echo "🔄 Restarting Support Assistant..."
    docker-compose down
    docker-compose up -d
    echo "✅ Application restarted successfully!"
}

# Function to build images
build_app() {
    echo "🔨 Building Docker images..."
    docker-compose build
    echo "✅ Images built successfully!"
}

# Function to run tests
test_app() {
    echo "🧪 Running test suite..."
    if [ -f "test_setup.py" ]; then
        python test_setup.py
    else
        echo "❌ Test script not found!"
        exit 1
    fi
}

# Function to show logs
show_logs() {
    echo "📋 Showing application logs..."
    docker-compose logs -f
}

# Function to clean up
clean_app() {
    echo "🧹 Cleaning up containers and images..."
    docker-compose down -v --rmi all
    docker system prune -f
    echo "✅ Cleanup completed!"
}

# Function to start production
start_prod() {
    echo "🚀 Starting production environment..."
    docker-compose -f docker-compose.prod.yml up -d
    echo "✅ Production environment started!"
    echo ""
    echo "🌐 Access the application at:"
    echo "   Frontend: http://localhost:80"
    echo "   Backend API: http://localhost:8000"
}

# Main script logic
case "${1:-start}" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    build)
        build_app
        ;;
    test)
        test_app
        ;;
    logs)
        show_logs
        ;;
    clean)
        clean_app
        ;;
    prod)
        start_prod
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
