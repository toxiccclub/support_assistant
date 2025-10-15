# backend/app/services/model_service.py
import os
import logging
import time
from typing import Optional, Dict, Any
from ..logging_utils import log_execution_time, get_structured_logger
from ..config import settings

logger = get_structured_logger(__name__)

class ModelService:
    """Сервис для работы с ML моделью"""
    
    def __init__(self):
        self._model = None
        self._is_initialized = False
        self._error_count = 0
        self._max_errors = settings.max_errors
        
    @log_execution_time
    def initialize(self) -> bool:
        """Инициализация модели с обработкой ошибок"""
        try:
            from models.model_v2_2 import IntelligentSupportSystem
            
            logger.info("🔄 Инициализация AI Support System...")
            self._model = IntelligentSupportSystem()
            
            # Загрузка базы знаний с проверкой существования файла
            knowledge_base_path = settings.get_knowledge_base_path()
            if not os.path.exists(knowledge_base_path):
                logger.error("Knowledge base file not found", path=knowledge_base_path)
                return False
                
            self._model.kb.load_knowledge_base(knowledge_base_path)
            self._is_initialized = True
            self._error_count = 0
            
            logger.info("AI Support System initialized successfully")
            return True
            
        except Exception as e:
            self._error_count += 1
            logger.error("Model initialization failed", error=str(e), error_type=type(e).__name__)
            return False
    
    @log_execution_time
    def process_query(self, query: str) -> Dict[str, Any]:
        """Обработка запроса с Circuit Breaker паттерном"""
        if not self._is_initialized:
            raise RuntimeError("Модель не инициализирована")
            
        if self._error_count >= self._max_errors:
            raise RuntimeError("Модель временно недоступна из-за частых ошибок")
        
        try:
            result = self._model.process_query(query)
            self._error_count = 0  # Сбрасываем счетчик ошибок при успехе
            return result
            
        except Exception as e:
            self._error_count += 1
            logger.error(f"❌ Ошибка обработки запроса: {e}")
            
            # Возвращаем fallback ответ вместо падения
            return self._get_fallback_response(query, str(e))
    
    def _get_fallback_response(self, query: str, error: str) -> Dict[str, Any]:
        """Fallback ответ при ошибке модели"""
        logger.warning(f"🔄 Используем fallback ответ для запроса: {query}")
        
        return {
            'response': 'Извините, в настоящее время система временно недоступна. Пожалуйста, попробуйте позже.',
            'classification': {
                'main_category': 'Ошибка системы',
                'confidence': 0.0,
                'similar_items': []
            },
            'fallback': True,
            'error': error
        }
    
    @log_execution_time
    def collect_feedback(self, result: Dict, feedback: str, rating: int) -> bool:
        """Сбор обратной связи с обработкой ошибок"""
        if not self._is_initialized:
            logger.warning("⚠️  Попытка собрать фидбэк при неинициализированной модели")
            return False
            
        try:
            self._model.collect_feedback(result, feedback, rating)
            logger.info(f"✅ Фидбэк сохранен. Рейтинг: {rating}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения фидбэка: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса модели"""
        return {
            'initialized': self._is_initialized,
            'error_count': self._error_count,
            'max_errors': self._max_errors,
            'operational': self._is_initialized and self._error_count < self._max_errors
        }
    
    def health_check(self) -> bool:
        """Проверка здоровья модели (тестовый запрос)"""
        if not self._is_initialized:
            return False
            
        try:
            # Быстрый тестовый запрос
            test_result = self._model.process_query("test")
            return True
        except Exception as e:
            logger.warning(f"⚠️  Health check failed: {e}")
            return False
    
    def reset_errors(self) -> None:
        """Сброс счетчика ошибок (для административных действий)"""
        self._error_count = 0
        logger.info("🔃 Счетчик ошибок модели сброшен")

# Singleton экземпляр сервиса
model_service = ModelService()