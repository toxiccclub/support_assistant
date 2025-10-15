# backend/app/monitoring.py
"""
Monitoring and metrics collection for the AI Support Service
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime
from .config import settings
from .logging_utils import get_structured_logger

logger = get_structured_logger(__name__)

class MetricsCollector:
    """Сбор метрик для мониторинга"""
    
    def __init__(self):
        self._metrics = {
            'requests_total': 0,
            'requests_success': 0,
            'requests_failed': 0,
            'model_errors': 0,
            'average_response_time': 0.0,
            'last_request_time': None,
            'startup_time': datetime.now().isoformat()
        }
        self._response_times = []
        self._max_response_times = 100  # Keep last 100 response times
    
    def record_request(self, success: bool, response_time: float, error_type: Optional[str] = None):
        """Записать метрику запроса"""
        self._metrics['requests_total'] += 1
        self._metrics['last_request_time'] = datetime.now().isoformat()
        
        if success:
            self._metrics['requests_success'] += 1
        else:
            self._metrics['requests_failed'] += 1
            if error_type:
                self._metrics['model_errors'] += 1
        
        # Обновляем среднее время ответа
        self._response_times.append(response_time)
        if len(self._response_times) > self._max_response_times:
            self._response_times.pop(0)
        
        self._metrics['average_response_time'] = sum(self._response_times) / len(self._response_times)
        
        logger.info(
            "Request metric recorded",
            success=success,
            response_time=response_time,
            error_type=error_type,
            total_requests=self._metrics['requests_total']
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить текущие метрики"""
        uptime = (datetime.now() - datetime.fromisoformat(self._metrics['startup_time'])).total_seconds()
        
        return {
            **self._metrics,
            'uptime_seconds': uptime,
            'success_rate': (
                self._metrics['requests_success'] / max(self._metrics['requests_total'], 1)
            ) * 100,
            'error_rate': (
                self._metrics['requests_failed'] / max(self._metrics['requests_total'], 1)
            ) * 100
        }
    
    def reset_metrics(self):
        """Сбросить метрики"""
        self._metrics = {
            'requests_total': 0,
            'requests_success': 0,
            'requests_failed': 0,
            'model_errors': 0,
            'average_response_time': 0.0,
            'last_request_time': None,
            'startup_time': datetime.now().isoformat()
        }
        self._response_times = []
        logger.info("Metrics reset")

# Global metrics collector
metrics_collector = MetricsCollector()

def record_request_metric(func):
    """Декоратор для автоматического сбора метрик запросов"""
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        success = True
        error_type = None
        
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            success = False
            error_type = type(e).__name__
            raise
        finally:
            response_time = time.time() - start_time
            metrics_collector.record_request(success, response_time, error_type)
    
    return wrapper

def get_health_status() -> Dict[str, Any]:
    """Получить детальный статус здоровья системы"""
    metrics = metrics_collector.get_metrics()
    
    # Определяем статус на основе метрик
    if metrics['error_rate'] > 50:
        status = "critical"
    elif metrics['error_rate'] > 20:
        status = "degraded"
    elif metrics['requests_total'] == 0:
        status = "unknown"
    else:
        status = "healthy"
    
    return {
        'status': status,
        'timestamp': datetime.now().isoformat(),
        'metrics': metrics,
        'version': '1.0.0',
        'environment': settings.is_production() and 'production' or 'development'
    }
