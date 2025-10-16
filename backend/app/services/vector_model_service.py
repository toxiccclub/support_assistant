"""
Vector-based Model Service
Uses vector embeddings and hybrid search for intelligent responses
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from ..logging_utils import log_execution_time, get_structured_logger
from ..config import settings
from .vector_database import VectorKnowledgeBase
from .web_scraper import scrape_vtb_website
from .excel_processor import process_training_data
from openai import OpenAI
from datetime import datetime

logger = get_structured_logger(__name__)

class VectorModelService:
    """Vector-based model service with hybrid search"""
    
    def __init__(self):
        self._knowledge_base: Optional[VectorKnowledgeBase] = None
        self._is_initialized = False
        self._error_count = 0
        self._max_errors = settings.max_errors
        self._llm_client: Optional[OpenAI] = None
        
    @log_execution_time
    async def initialize(self) -> bool:
        """Initialize the vector-based model service"""
        try:
            logger.info("🔄 Initializing Vector-based AI Support System...")
            
            # Initialize LLM client
            self._llm_client = OpenAI(
                api_key=settings.api_key,
                base_url=settings.base_url
            )
            
            # Initialize knowledge base
            self._knowledge_base = VectorKnowledgeBase(
                api_key=settings.api_key,
                base_url=settings.base_url
            )
            
            # Check if knowledge base exists
            kb_path = settings.get_knowledge_base_path()
            if os.path.exists(kb_path):
                logger.info("Loading existing knowledge base...")
                try:
                    self._knowledge_base.load_knowledge_base(kb_path)
                    self._is_initialized = True
                except Exception as e:
                    logger.warning(f"Failed to load existing knowledge base: {e}")
                    logger.info("Building new knowledge base...")
                    success = await self._build_knowledge_base()
                    if not success:
                        # Initialize with empty knowledge base
                        logger.info("Initializing with empty knowledge base...")
                        self._is_initialized = True
            else:
                logger.info("Building new knowledge base...")
                success = await self._build_knowledge_base()
                if not success:
                    # Initialize with empty knowledge base
                    logger.info("Initializing with empty knowledge base...")
                    self._is_initialized = True
            
            self._error_count = 0
            logger.info("Vector-based AI Support System initialized successfully")
            return True
            
        except Exception as e:
            self._error_count += 1
            logger.error("Vector model initialization failed", error=str(e), error_type=type(e).__name__)
            return False
    
    async def _build_knowledge_base(self) -> bool:
        """Build knowledge base from all sources"""
        try:
            # Paths for data sources
            excel_file = "/home/dima/support_assistant/backend/models/training_data.xlsx"
            web_scraped_file = "/home/dima/support_assistant/backend/app/data/web_scraped_data.json"
            
            # Check if Excel file exists
            if not os.path.exists(excel_file):
                logger.error(f"Excel training file not found: {excel_file}")
                return False
            
            # Process Excel data first
            logger.info("Processing Excel training data...")
            excel_data = process_training_data(excel_file, "processed_training_data.json")
            
            # Web scraping (optional)
            web_data = []
            try:
                logger.info("Starting web scraping...")
                web_data = await scrape_vtb_website(web_scraped_file)
                logger.info(f"Web scraping completed: {len(web_data)} chunks")
            except Exception as e:
                logger.warning(f"Web scraping failed, continuing with Excel data only: {e}")
            
            # Build knowledge base
            success = await self._knowledge_base.build_knowledge_base(excel_file, web_scraped_file)
            
            if success:
                # Save knowledge base
                kb_path = settings.get_knowledge_base_path()
                self._knowledge_base.save_knowledge_base(kb_path)
                logger.info(f"Knowledge base saved to {kb_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error building knowledge base: {e}")
            return False
    
    @log_execution_time
    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process user query using vector search and LLM"""
        if not self._is_initialized:
            raise RuntimeError("Vector model not initialized")
            
        if self._error_count >= self._max_errors:
            raise RuntimeError("Vector model temporarily unavailable due to frequent errors")
        
        try:
            logger.info(f"Processing query: {query[:100]}...")
            
            # Search for relevant documents
            search_results = await self._knowledge_base.search(query, top_k=5)
            logger.info(f"Search returned {len(search_results) if search_results else 0} results")
            
            # Always use LLM for response generation and categorization
            if search_results:
                # Generate response using LLM with search results
                response = await self._generate_response(query, search_results)
                # Extract classification from search results
                classification = self._extract_classification(search_results)
            else:
                # Generate response using LLM without search results
                logger.info("No search results found, using LLM for analysis without knowledge base")
                response = await self._generate_response_without_kb(query)
                # Use LLM for classification
                classification = await self._classify_query_with_llm(query)
            
            result = {
                'user_query': query,
                'response': response,
                'classification': classification,
                'search_results': search_results,
                'has_suggestion': bool(response),
                'timestamp': datetime.now().isoformat(),
                'processing_metadata': {
                    'num_search_results': len(search_results),
                    'search_types': list(set(result.get('search_types', []) for result in search_results)),
                    'model_version': 'vector_based_v1.0'
                }
            }
            
            return result
            
        except Exception as e:
            self._error_count += 1
            logger.error(f"❌ Error processing query: {e}")
            return self._get_fallback_response(query, str(e))
    
    async def _generate_response(self, query: str, search_results: List[Dict[str, Any]]) -> str:
        """Generate response using LLM based on search results"""
        if not self._llm_client:
            return ""
        
        try:
            # Prepare context from search results
            context_parts = []
            for i, result in enumerate(search_results[:3]):  # Use top 3 results
                doc = result['document']
                context_parts.append(f"Источник {i+1}: {doc.get('content', '')}")
            
            context = "\n\n".join(context_parts)
            
            system_prompt = """Ты - помощник службы поддержки банка ВТБ Беларусь. 
            Используй предоставленную информацию для ответа на вопрос клиента.
            Отвечай на русском языке, будь вежливым и профессиональным.
            Если информации недостаточно, предложи связаться с оператором."""
            
            user_prompt = f"""
            Вопрос клиента: {query}
            
            Контекст из базы знаний:
            {context}
            
            Ответь на вопрос клиента, используя предоставленную информацию.
            """
            
            response = self._llm_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return ""
    
    async def _generate_response_without_kb(self, query: str) -> str:
        """Generate response using LLM without knowledge base"""
        if not self._llm_client:
            logger.warning("LLM client not available")
            return "Извините, в настоящее время система временно недоступна. Пожалуйста, попробуйте позже или обратитесь к оператору."
        
        try:
            response = self._llm_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Вы - помощник службы поддержки банка. Отвечайте на вопросы клиентов вежливо и профессионально. 
                        Если у вас нет конкретной информации, предложите клиенту обратиться к оператору или посетить отделение банка.
                        Отвечайте кратко и по существу."""
                    },
                    {
                        "role": "user", 
                        "content": f"Вопрос клиента: {query}"
                    }
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating LLM response without KB: {e}")
            return "Извините, в настоящее время система временно недоступна. Пожалуйста, попробуйте позже или обратитесь к оператору."
    
    async def _classify_query_with_llm(self, query: str) -> Dict[str, Any]:
        """Classify query using LLM"""
        if not self._llm_client:
            return {
                'main_category': 'Неопределено',
                'subcategory': 'Общий вопрос',
                'confidence': 0.0
            }
        
        try:
            response = self._llm_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Проанализируйте вопрос клиента и определите категорию и подкатегорию. 
                        Верните ответ в формате JSON:
                        {
                            "main_category": "Основная категория",
                            "subcategory": "Подкатегория", 
                            "confidence": 0.8
                        }
                        
                        Возможные основные категории:
                        - Банковские услуги
                        - Карты и платежи
                        - Кредиты и займы
                        - Вклады и инвестиции
                        - Интернет-банкинг
                        - Техническая поддержка
                        - Общие вопросы
                        
                        Подкатегории должны быть более конкретными."""
                    },
                    {
                        "role": "user",
                        "content": f"Вопрос: {query}"
                    }
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            # Parse JSON response
            import json
            content = response.choices[0].message.content.strip()
            logger.info(f"LLM classification response: {content}")
            
            # Try to extract JSON from the response
            try:
                # Look for JSON in the response
                if '{' in content and '}' in content:
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    json_str = content[start:end]
                    result = json.loads(json_str)
                    return result
                else:
                    # If no JSON found, try to parse the whole response
                    result = json.loads(content)
                    return result
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM JSON response: {e}")
                logger.warning(f"Raw response: {content}")
                
                # Fallback: try to extract category from text
                if "Банковские услуги" in content or "банковские" in content.lower():
                    return {'main_category': 'Банковские услуги', 'subcategory': 'Общие вопросы', 'confidence': 0.7}
                elif "карт" in content.lower() or "платеж" in content.lower():
                    return {'main_category': 'Карты и платежи', 'subcategory': 'Блокировка карты', 'confidence': 0.7}
                elif "кредит" in content.lower() or "займ" in content.lower():
                    return {'main_category': 'Кредиты и займы', 'subcategory': 'Общие вопросы', 'confidence': 0.7}
                elif "вклад" in content.lower() or "инвестиц" in content.lower():
                    return {'main_category': 'Вклады и инвестиции', 'subcategory': 'Общие вопросы', 'confidence': 0.7}
                elif "интернет" in content.lower() or "банкинг" in content.lower() or "логин" in content.lower():
                    return {'main_category': 'Интернет-банкинг', 'subcategory': 'Технические проблемы', 'confidence': 0.7}
                elif "техническ" in content.lower() or "проблем" in content.lower():
                    return {'main_category': 'Техническая поддержка', 'subcategory': 'Общие проблемы', 'confidence': 0.7}
                else:
                    return {'main_category': 'Общие вопросы', 'subcategory': 'Неопределено', 'confidence': 0.5}
            
        except Exception as e:
            logger.error(f"Error classifying query with LLM: {e}")
            return {
                'main_category': 'Общие вопросы',
                'subcategory': 'Неопределено',
                'confidence': 0.0
            }
    
    def _extract_classification(self, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract classification information from search results"""
        if not search_results:
            return {
                'main_category': 'Неопределено',
                'subcategory': 'Общий вопрос',
                'confidence': 0.0
            }
        
        # Get the best match
        best_result = search_results[0]
        doc = best_result['document']
        
        # Extract category information
        main_category = doc.get('main_category', 'Неопределено')
        subcategory = doc.get('subcategory', 'Общий вопрос')
        confidence = best_result.get('similarity_score', 0.0)
        
        return {
            'main_category': main_category,
            'subcategory': subcategory,
            'confidence': confidence,
            'search_type': best_result.get('search_type', 'unknown')
        }
    
    def _get_fallback_response(self, query: str, error: str) -> Dict[str, Any]:
        """Fallback response when model fails"""
        logger.warning(f"🔄 Using fallback response for query: {query}")
        
        return {
            'user_query': query,
            'response': 'Извините, в настоящее время система временно недоступна. Пожалуйста, попробуйте позже или обратитесь к оператору.',
            'classification': {
                'main_category': 'Ошибка системы',
                'subcategory': 'Техническая проблема',
                'confidence': 0.0
            },
            'search_results': [],
            'has_suggestion': False,
            'timestamp': datetime.now().isoformat(),
            'fallback': True,
            'error': error
        }
    
    @log_execution_time
    async def collect_feedback(self, result: Dict, feedback: str, rating: int) -> bool:
        """Collect feedback for continuous learning"""
        if not self._is_initialized:
            logger.warning("⚠️ Attempting to collect feedback with uninitialized model")
            return False
            
        try:
            # Store feedback for future analysis
            feedback_entry = {
                'query': result.get('user_query', ''),
                'response': result.get('response', ''),
                'classification': result.get('classification', {}),
                'user_feedback': feedback,
                'operator_rating': rating,
                'timestamp': datetime.now().isoformat()
            }
            
            # TODO: Implement feedback storage and retraining logic
            logger.info(f"✅ Feedback collected. Rating: {rating}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error collecting feedback: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get model status"""
        return {
            'initialized': self._is_initialized,
            'error_count': self._error_count,
            'max_errors': self._max_errors,
            'operational': self._is_initialized and self._error_count < self._max_errors,
            'model_type': 'vector_based'
        }
    
    def health_check(self) -> bool:
        """Health check for the vector model"""
        if not self._is_initialized:
            return False
            
        try:
            # Quick test search
            test_results = asyncio.run(self._knowledge_base.search("test", top_k=1))
            return True
        except Exception as e:
            logger.warning(f"⚠️ Health check failed: {e}")
            return False
    
    def reset_errors(self) -> None:
        """Reset error counter"""
        self._error_count = 0
        logger.info("🔃 Vector model error counter reset")
    
    async def rebuild_knowledge_base(self) -> bool:
        """Rebuild knowledge base from sources"""
        try:
            logger.info("Rebuilding knowledge base...")
            success = await self._build_knowledge_base()
            if success:
                self._is_initialized = True
                logger.info("Knowledge base rebuilt successfully")
            return success
        except Exception as e:
            logger.error(f"Error rebuilding knowledge base: {e}")
            return False

# Singleton instance
vector_model_service = VectorModelService()
