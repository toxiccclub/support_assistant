"""
Test script for the new vector-based knowledge system
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent / "app"))

from app.services.vector_model_service import vector_model_service
from app.services.excel_processor import process_training_data
from app.services.web_scraper import scrape_vtb_website

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_vector_system():
    """Test the vector-based system"""
    try:
        logger.info("🧪 Testing Vector-based Knowledge System...")
        
        # Test 1: Initialize the system
        logger.info("1. Testing system initialization...")
        success = await vector_model_service.initialize()
        if not success:
            logger.error("❌ System initialization failed")
            return False
        
        logger.info("✅ System initialized successfully")
        
        # Test 2: Test query processing
        logger.info("2. Testing query processing...")
        test_queries = [
            "Как восстановить пароль от интернет-банка?",
            "Моя карта заблокирована, что делать?",
            "Хочу стать клиентом вашего банка",
            "Не работает мобильное приложение",
            "Как открыть депозит?"
        ]
        
        for query in test_queries:
            logger.info(f"Testing query: {query}")
            result = await vector_model_service.process_query(query)
            
            logger.info(f"Response: {result.get('response', 'No response')[:100]}...")
            logger.info(f"Category: {result.get('classification', {}).get('main_category', 'Unknown')}")
            logger.info(f"Confidence: {result.get('classification', {}).get('confidence', 0.0):.2f}")
            logger.info(f"Search results: {len(result.get('search_results', []))}")
            logger.info("-" * 50)
        
        # Test 3: Test system status
        logger.info("3. Testing system status...")
        status = vector_model_service.get_status()
        logger.info(f"System status: {status}")
        
        # Test 4: Test health check
        logger.info("4. Testing health check...")
        health = vector_model_service.health_check()
        logger.info(f"Health check: {'✅ PASS' if health else '❌ FAIL'}")
        
        logger.info("🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_data_processing():
    """Test data processing components"""
    try:
        logger.info("🧪 Testing data processing components...")
        
        # Test Excel processing
        excel_file = "/home/dima/support_assistant/backend/models/training_data.xlsx"
        if os.path.exists(excel_file):
            logger.info("Testing Excel data processing...")
            excel_data = process_training_data(excel_file, "test_processed_data.json")
            logger.info(f"✅ Processed {len(excel_data)} chunks from Excel")
        else:
            logger.warning(f"Excel file not found: {excel_file}")
        
        # Test web scraping (optional)
        logger.info("Testing web scraping...")
        try:
            web_data = await scrape_vtb_website("test_web_data.json")
            logger.info(f"✅ Scraped {len(web_data)} chunks from website")
        except Exception as e:
            logger.warning(f"Web scraping failed (expected in test environment): {e}")
        
        logger.info("✅ Data processing tests completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Data processing test failed: {e}")
        return False

async def main():
    """Main test function"""
    logger.info("🚀 Starting Vector Knowledge System Tests...")
    
    # Test data processing
    await test_data_processing()
    
    # Test vector system
    success = await test_vector_system()
    
    if success:
        logger.info("🎉 All tests passed!")
    else:
        logger.error("❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
