#!/usr/bin/env python3
"""
Test script to verify the Docker setup is working correctly.
"""

import requests
import time
import sys
import json

def test_backend_health():
    """Test backend health endpoint."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=10)
        if response.status_code == 200:
            print("✅ Backend health check passed")
            return True
        else:
            print(f"❌ Backend health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Backend health check failed: {e}")
        return False

def test_backend_analyze():
    """Test backend analyze endpoint."""
    try:
        test_data = {
            "text": "Не могу войти в мобильное приложение ВТБ"
        }
        response = requests.post(
            "http://localhost:8000/analyze",
            json=test_data,
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            print("✅ Backend analyze endpoint working")
            print(f"   Category: {result.get('category', 'N/A')}")
            print(f"   Confidence: {result.get('category_score', 'N/A')}")
            return True
        else:
            print(f"❌ Backend analyze failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Backend analyze failed: {e}")
        return False

def test_frontend():
    """Test frontend accessibility."""
    try:
        response = requests.get("http://localhost:3000", timeout=10)
        if response.status_code == 200:
            print("✅ Frontend is accessible")
            return True
        else:
            print(f"❌ Frontend test failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Frontend test failed: {e}")
        return False

def test_api_documentation():
    """Test API documentation accessibility."""
    try:
        response = requests.get("http://localhost:8000/docs", timeout=10)
        if response.status_code == 200:
            print("✅ API documentation accessible")
            return True
        else:
            print(f"❌ API documentation failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ API documentation failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Support Assistant Docker Setup")
    print("=" * 50)
    
    # Wait for services to start
    print("⏳ Waiting for services to start...")
    time.sleep(10)
    
    tests = [
        ("Backend Health", test_backend_health),
        ("Backend Analyze", test_backend_analyze),
        ("Frontend", test_frontend),
        ("API Documentation", test_api_documentation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"   ⚠️  {test_name} test failed")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The setup is working correctly.")
        print("\n🌐 Access the application at:")
        print("   Frontend: http://localhost:3000")
        print("   Backend API: http://localhost:8000")
        print("   API Docs: http://localhost:8000/docs")
        return 0
    else:
        print("❌ Some tests failed. Please check the logs and configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
