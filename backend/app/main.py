import os
import json
import logging
import time
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from pydantic import BaseModel, constr
from fastapi.middleware.cors import CORSMiddleware
import asyncio

# Импорт утилит и сервисов
from .logging_utils import setup_logging, log_execution_time_async, get_structured_logger
from .config import settings
from .services.model_service import model_service, ModelService
from .dependencies import get_model_service
from .monitoring import metrics_collector, record_request_metric, get_health_status
from .auth import verify_admin_token, get_current_admin_user, get_admin_key
from .rate_limiter import check_rate_limit

# Настройка логирования
log_file_path = setup_logging()
logger = get_structured_logger(__name__)

app = FastAPI(
    title="AI Support Service",
    description="Интеллектуальная система поддержки клиентов",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Безопасные CORS настройки (оставляем без изменений)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization", 
        "X-Requested-With",
        "Accept"
    ],
    expose_headers=["Content-Length", "X-Request-ID"],
    max_age=600,
)

# Security middleware (enhanced)
@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # Remove server information (skip for now to avoid MutableHeaders issues)
    # if "server" in response.headers:
    #     del response.headers["server"]
    
    # Add rate limit headers if available
    if hasattr(request.state, 'rate_limit_remaining'):
        response.headers["X-RateLimit-Limit"] = "10"
        response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
        response.headers["X-RateLimit-Reset"] = str(request.state.rate_limit_reset)
    
    return response

# Timeout middleware (оставляем без изменений)
@app.middleware("http") 
async def timeout_middleware(request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=settings.api_timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Request timeout: {request.url}")
        raise HTTPException(status_code=504, detail="Request timeout")

# Модели запросов (оставляем без изменений)
class AnalyzeRequest(BaseModel):
    text: constr(min_length=1, max_length=5000)

class ServerFeedbackRequest(BaseModel):
    query: constr(min_length=1, max_length=5000)
    response: constr(min_length=1, max_length=10000)
    rating: int
    user_feedback: constr(max_length=2000) = ""
    user_id: Optional[str] = None

class QueryRequest(BaseModel):
    query: constr(min_length=1, max_length=5000)
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    response: str
    category: str
    confidence: float
    similar_questions: list = []
    timestamp: str

class FeedbackRequest(BaseModel):
    original_text: str
    predicted_category: str
    corrected_category: Optional[str] = None
    suggested_solution: str
    status: str
    operator_rating: int
    operator_notes: str = ""
    customer_name: str = ""
    customer_email: str = ""
    customer_phone: str = ""
    priority: str = "normal"
    timestamp: str

# Инициализация при старте
@app.on_event("startup")
@log_execution_time_async
async def startup_event():
    """Инициализация системы при запуске"""
    try:
        logger.info(f"🚀 Запуск AI Support Service...")
        logger.info(f"🌐 CORS разрешены для: {settings.get_cors_origins()}")
        
        # Инициализируем модель
        success = model_service.initialize()
        if not success:
            logger.error("❌ Не удалось инициализировать модель при запуске")
            # Не падаем, сервис может работать в degraded mode
        
        logger.info("✅ AI Support Service запущен")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске: {e}")
        # Решаем, падать ли полностью или работать без модели
        # В данном случае - работаем, но с ограниченной функциональностью

# Endpoint'ы
@app.get("/")
@log_execution_time_async
async def root():
    return {
        "status": "AI Support Service is running", 
        "model_status": model_service.get_status(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
@log_execution_time_async
@record_request_metric
async def health_check():
    """Проверка здоровья сервиса с детальными метриками"""
    return get_health_status()

@app.post("/analyze")
@log_execution_time_async
@record_request_metric
async def analyze(
    request: Request,
    req: AnalyzeRequest, 
    model: ModelService = Depends(get_model_service)  # Используем dependency injection
):
    """Анализ запроса с обработанными ошибками"""
    try:
        # Apply rate limiting
        await check_rate_limit(request)
        
        logger.info(f"🔍 Анализ запроса: {req.text[:100]}...")
        
        # Обрабатываем запрос через сервис
        start_time = time.time()
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            model.process_query,
            req.text
        )
        execution_time = time.time() - start_time
        
        logger.info(f"✅ Запрос обработан за {execution_time:.3f}s")
        
        # Форматируем ответ
        similar_questions = [
            item['knowledge_item']['question'] 
            for item in result.get('classification', {}).get('similar_items', [])[:3]
        ]
        
        response_data = {
            "category": result.get('classification', {}).get('main_category', 'Неизвестно'),
            "category_score": float(result.get('classification', {}).get('confidence', 0.0)),
            "entities": [],
            "kb_candidates": similar_questions,
            "selected_kb": {
                "title": result.get('classification', {}).get('main_category', 'Неизвестно'), 
                "template": result.get('response', '')
            },
            "recommendation": result.get('response', ''),
            "fallback": result.get('fallback', False)
        }
        
        return response_data
        
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка анализа: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Внутренняя ошибка сервера при обработке запроса"
        )

@app.post("/feedback")
@log_execution_time_async
async def submit_feedback(
    request: ServerFeedbackRequest, 
    background_tasks: BackgroundTasks,
    model: ModelService = Depends(get_model_service)
):
    """Сбор обратной связи для ML модели"""
    try:
        mock_result = {
            'user_query': request.query,
            'response': request.response,
            'classification': {'main_category': 'Unknown'}
        }
        
        # Добавляем в фоновые задачи
        background_tasks.add_task(
            model.collect_feedback,
            mock_result,
            request.user_feedback,
            request.rating
        )
        
        logger.info(f"📝 Фидбэк получен. Рейтинг: {request.rating}")
        
        return {
            "status": "feedback_received", 
            "message": "Спасибо за обратную связь!",
            "saved": True
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки фидбэка: {e}")
        # Не падаем полностью, просто сообщаем об ошибке сохранения
        return {
            "status": "feedback_received", 
            "message": "Спасибо за обратную связь! (Ошибка сохранения, но мы её учтем)",
            "saved": False
        }

@app.get("/stats")
@log_execution_time_async
async def get_statistics(model: ModelService = Depends(get_model_service)):
    """Получение статистики по модели"""
    try:
        model_status = model.get_status()
        
        stats = {
            "status": "operational" if model_status['operational'] else "degraded",
            "model_type": "IntelligentSupportSystem",
            "model_status": model_status,
            "timestamp": datetime.now().isoformat(),
            "features": ["classification", "response_generation", "similar_questions"]
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail="Error getting statistics")

@app.get("/metrics")
@log_execution_time_async
async def get_metrics():
    """Получение метрик системы"""
    return metrics_collector.get_metrics()

@app.post("/admin/reset-errors")
async def reset_errors(admin_user = Depends(get_current_admin_user)):
    """Административный endpoint для сброса ошибок"""
    model_service.reset_errors()
    return {"status": "errors_reset", "message": "Счетчик ошибок сброшен"}

@app.post("/admin/reset-metrics")
async def reset_metrics(admin_user = Depends(get_current_admin_user)):
    """Административный endpoint для сброса метрик"""
    metrics_collector.reset_metrics()
    return {"status": "metrics_reset", "message": "Метрики сброшены"}

@app.get("/admin/key")
async def get_admin_api_key(admin_user = Depends(get_current_admin_user)):
    """Get admin API key for development"""
    return {"admin_key": get_admin_key(), "note": "Development only - remove in production"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )