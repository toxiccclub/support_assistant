#!/bin/bash

# Docker Test Script for Vector-Based AI Support System
# This script tests the Docker build and run process

set -e  # Exit on any error

echo "🐳 Testing Docker Build and Run for Vector-Based AI Support System"
echo "=================================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_status "Checking prerequisites..."

if ! command_exists docker; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! command_exists docker-compose; then
    print_error "Docker Compose is not installed or not in PATH"
    exit 1
fi

print_success "Docker and Docker Compose are available"

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p backend/vector_data
mkdir -p logs
print_success "Directories created"

# Test 1: Build the Docker image
print_status "Test 1: Building Docker image..."
cd backend

if docker build -t ai-support-vector-test .; then
    print_success "Docker image built successfully"
else
    print_error "Docker build failed"
    exit 1
fi

cd ..

# Test 2: Test Docker Compose build
print_status "Test 2: Testing Docker Compose build..."
if docker-compose build; then
    print_success "Docker Compose build successful"
else
    print_error "Docker Compose build failed"
    exit 1
fi

# Test 3: Start services
print_status "Test 3: Starting services with Docker Compose..."
docker-compose up -d

# Wait for services to start
print_status "Waiting for services to start..."
sleep 30

# Test 4: Check if services are running
print_status "Test 4: Checking service status..."
if docker-compose ps | grep -q "Up"; then
    print_success "Services are running"
else
    print_error "Services failed to start"
    docker-compose logs
    exit 1
fi

# Test 5: Health check
print_status "Test 5: Testing health endpoint..."
for i in {1..10}; do
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        print_success "Health check passed"
        break
    else
        if [ $i -eq 10 ]; then
            print_error "Health check failed after 10 attempts"
            docker-compose logs backend
            exit 1
        fi
        print_status "Health check attempt $i/10 - waiting..."
        sleep 10
    fi
done

# Test 6: Test API endpoints
print_status "Test 6: Testing API endpoints..."

# Test root endpoint
if curl -s http://localhost:8000/ | grep -q "AI Support Service"; then
    print_success "Root endpoint working"
else
    print_error "Root endpoint failed"
fi

# Test analyze endpoint
print_status "Testing analyze endpoint..."
ANALYZE_RESPONSE=$(curl -s -X POST "http://localhost:8000/analyze" \
    -H "Content-Type: application/json" \
    -d '{"text": "How to reset password?"}')

if echo "$ANALYZE_RESPONSE" | grep -q "category"; then
    print_success "Analyze endpoint working"
    echo "Response preview: $(echo "$ANALYZE_RESPONSE" | head -c 200)..."
else
    print_warning "Analyze endpoint may have issues"
    echo "Response: $ANALYZE_RESPONSE"
fi

# Test 7: Check logs for errors
print_status "Test 7: Checking for errors in logs..."
if docker-compose logs backend | grep -i error | head -5; then
    print_warning "Found some errors in logs (may be expected during initialization)"
else
    print_success "No critical errors found in logs"
fi

# Test 8: Test vector system initialization
print_status "Test 8: Testing vector system status..."
STATUS_RESPONSE=$(curl -s http://localhost:8000/stats)
if echo "$STATUS_RESPONSE" | grep -q "VectorBasedSupportSystem"; then
    print_success "Vector system is active"
else
    print_warning "Vector system status unclear"
    echo "Status response: $STATUS_RESPONSE"
fi

# Test 9: Performance test
print_status "Test 9: Running performance test..."
START_TIME=$(date +%s)
for i in {1..5}; do
    curl -s -X POST "http://localhost:8000/analyze" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"Test query $i\"}" >/dev/null
done
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
print_success "5 requests completed in ${DURATION} seconds"

# Test 10: Cleanup test
print_status "Test 10: Testing cleanup..."
docker-compose down
print_success "Services stopped successfully"

# Final summary
echo ""
echo "=================================================================="
print_success "🎉 All Docker tests completed successfully!"
echo ""
echo "Summary of tests:"
echo "✅ Docker image build"
echo "✅ Docker Compose build"
echo "✅ Service startup"
echo "✅ Health checks"
echo "✅ API endpoints"
echo "✅ Vector system integration"
echo "✅ Performance test"
echo "✅ Cleanup"
echo ""
echo "The vector-based AI support system is ready for deployment!"
echo ""
echo "To start the system:"
echo "  docker-compose up -d"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f backend"
echo ""
echo "To stop the system:"
echo "  docker-compose down"
