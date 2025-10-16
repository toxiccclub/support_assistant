#!/bin/bash

# Comprehensive system test script
# Tests all major endpoints and functionality

set -e

echo "=================================================================="
echo "🧪 Comprehensive System Test"
echo "=================================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to test endpoint
test_endpoint() {
    local name=$1
    local method=$2
    local url=$3
    local data=$4
    local expected_field=$5
    
    echo -n "Testing $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s "$url")
    else
        response=$(curl -s -X "$method" "$url" -H "Content-Type: application/json" -d "$data")
    fi
    
    if echo "$response" | jq -e ".$expected_field" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "Response: $response"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo "=== 1. Health Check ==="
test_endpoint "Health endpoint" "GET" "http://localhost:8000/health" "" "status"
echo ""

echo "=== 2. Root Endpoint ==="
test_endpoint "Root endpoint" "GET" "http://localhost:8000/" "" "status"
echo ""

echo "=== 3. Stats Endpoint ==="
test_endpoint "Stats endpoint" "GET" "http://localhost:8000/stats" "" "status"
test_endpoint "Stats model_type" "GET" "http://localhost:8000/stats" "" "model_type"
test_endpoint "Stats features" "GET" "http://localhost:8000/stats" "" "features"
echo ""

echo "=== 4. Analyze Endpoint ==="
test_endpoint "Analyze endpoint" "POST" "http://localhost:8000/analyze" '{"text": "How to reset password?"}' "category"
test_endpoint "Analyze recommendation" "POST" "http://localhost:8000/analyze" '{"text": "Test query"}' "recommendation"
test_endpoint "Analyze fallback" "POST" "http://localhost:8000/analyze" '{"text": "Another test"}' "fallback"
echo ""

echo "=== 5. Performance Test ==="
echo -n "Testing 5 concurrent requests... "
start_time=$(date +%s)
for i in {1..5}; do
    curl -s -X POST "http://localhost:8000/analyze" -H "Content-Type: application/json" -d "{\"text\": \"Test $i\"}" > /dev/null &
done
wait
end_time=$(date +%s)
duration=$((end_time - start_time))
if [ $duration -le 5 ]; then
    echo -e "${GREEN}✓ PASSED${NC} (${duration}s)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ FAILED${NC} (${duration}s, expected ≤5s)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

echo "=== 6. Docker Container Status ==="
echo -n "Checking backend container... "
if docker ps --format "{{.Names}}\t{{.Status}}" | grep -q "ai-support-backend.*Up"; then
    echo -e "${GREEN}✓ PASSED${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ FAILED${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo -n "Checking frontend container... "
if docker ps --format "{{.Names}}\t{{.Status}}" | grep -q "ai-support-frontend.*Up"; then
    echo -e "${GREEN}✓ PASSED${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ FAILED${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

echo "=================================================================="
echo "📊 Test Results"
echo "=================================================================="
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    echo ""
    echo "The vector-based AI support system is fully operational!"
    echo ""
    echo "Note: The system is currently using fallback responses because"
    echo "no knowledge base has been loaded yet. This is expected behavior."
    echo ""
    echo "To build a knowledge base, you can:"
    echo "1. Add data to training_data.xlsx"
    echo "2. Configure web scraping for vtb.by"
    echo "3. Restart the system to trigger knowledge base building"
    exit 0
else
    echo -e "${RED}❌ Some tests failed!${NC}"
    exit 1
fi

