#!/bin/bash

# AI Support Assistant Deployment Script
# This script handles deployment of the AI Support Assistant system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="ai-support-assistant"
ENV_FILE=".env"
BACKUP_DIR="./backups"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Create backup
create_backup() {
    if [ -d "$BACKUP_DIR" ]; then
        log_info "Creating backup..."
        BACKUP_NAME="backup-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$BACKUP_DIR/$BACKUP_NAME"
        
        # Backup logs
        if [ -d "./logs" ]; then
            cp -r ./logs "$BACKUP_DIR/$BACKUP_NAME/"
        fi
        
        # Backup data
        if [ -d "./backend/app/data" ]; then
            cp -r ./backend/app/data "$BACKUP_DIR/$BACKUP_NAME/"
        fi
        
        log_success "Backup created: $BACKUP_DIR/$BACKUP_NAME"
    fi
}

# Setup environment
setup_environment() {
    log_info "Setting up environment..."
    
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "env.example" ]; then
            cp env.example "$ENV_FILE"
            log_warning "Created $ENV_FILE from env.example. Please review and update the configuration."
        else
            log_error "No environment file found. Please create $ENV_FILE"
            exit 1
        fi
    fi
    
    # Generate admin key if not set
    if ! grep -q "ADMIN_API_KEY=" "$ENV_FILE" || grep -q "your-secure-admin-key-here" "$ENV_FILE"; then
        ADMIN_KEY=$(openssl rand -base64 32)
        sed -i "s/ADMIN_API_KEY=.*/ADMIN_API_KEY=$ADMIN_KEY/" "$ENV_FILE"
        log_info "Generated new admin API key"
    fi
    
    log_success "Environment setup completed"
}

# Deploy development environment
deploy_dev() {
    log_info "Deploying development environment..."
    
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    
    log_success "Development environment deployed"
    show_access_info
}

# Deploy production environment
deploy_prod() {
    log_info "Deploying production environment..."
    
    # Create SSL directory if it doesn't exist
    mkdir -p ./ssl
    
    # Check for SSL certificates
    if [ ! -f "./ssl/cert.pem" ] || [ ! -f "./ssl/key.pem" ]; then
        log_warning "SSL certificates not found. Generating self-signed certificates..."
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout ./ssl/key.pem \
            -out ./ssl/cert.pem \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
    fi
    
    docker-compose -f docker-compose.prod.yml down
    docker-compose -f docker-compose.prod.yml build --no-cache
    docker-compose -f docker-compose.prod.yml up -d
    
    log_success "Production environment deployed"
    show_access_info_prod
}

# Deploy with monitoring
deploy_with_monitoring() {
    log_info "Deploying with monitoring stack..."
    
    docker-compose --profile monitoring down
    docker-compose --profile monitoring build --no-cache
    docker-compose --profile monitoring up -d
    
    log_success "Environment with monitoring deployed"
    show_monitoring_info
}

# Show access information
show_access_info() {
    echo ""
    log_success "=== Development Environment Access ==="
    echo "Frontend: http://localhost:3000"
    echo "Backend API: http://localhost:8000"
    echo "API Documentation: http://localhost:8000/docs"
    echo "Health Check: http://localhost:8000/health"
    echo ""
}

show_access_info_prod() {
    echo ""
    log_success "=== Production Environment Access ==="
    echo "Frontend: https://localhost"
    echo "Backend API: https://localhost/api"
    echo "API Documentation: https://localhost/api/docs"
    echo "Health Check: https://localhost/health"
    echo ""
}

show_monitoring_info() {
    echo ""
    log_success "=== Monitoring Access ==="
    echo "Prometheus: http://localhost:9090"
    echo "Grafana: http://localhost:3001 (admin/admin)"
    echo "Metrics: http://localhost:8000/metrics"
    echo ""
}

# Health check
health_check() {
    log_info "Performing health check..."
    
    # Wait for services to start
    sleep 10
    
    # Check backend health
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "Backend health check passed"
    else
        log_error "Backend health check failed"
        return 1
    fi
    
    # Check frontend
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        log_success "Frontend health check passed"
    else
        log_warning "Frontend health check failed"
    fi
    
    log_success "Health check completed"
}

# Cleanup
cleanup() {
    log_info "Cleaning up..."
    docker-compose down
    docker system prune -f
    log_success "Cleanup completed"
}

# Show logs
show_logs() {
    log_info "Showing logs..."
    docker-compose logs -f
}

# Show help
show_help() {
    echo "AI Support Assistant Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  dev                 Deploy development environment"
    echo "  prod                Deploy production environment"
    echo "  monitoring          Deploy with monitoring stack"
    echo "  health              Perform health check"
    echo "  logs                Show logs"
    echo "  cleanup             Clean up containers and images"
    echo "  backup              Create backup"
    echo "  help                Show this help message"
    echo ""
}

# Main script
main() {
    case "${1:-help}" in
        "dev")
            check_prerequisites
            setup_environment
            create_backup
            deploy_dev
            health_check
            ;;
        "prod")
            check_prerequisites
            setup_environment
            create_backup
            deploy_prod
            health_check
            ;;
        "monitoring")
            check_prerequisites
            setup_environment
            create_backup
            deploy_with_monitoring
            health_check
            ;;
        "health")
            health_check
            ;;
        "logs")
            show_logs
            ;;
        "cleanup")
            cleanup
            ;;
        "backup")
            create_backup
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Run main function
main "$@"
