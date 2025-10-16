# backend/app/main.py
import os
import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import asyncio


# Импорт модели
from models.model_final import IntelligentSupportSystem

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Support Service")

# Глобальная переменная для системы
support_system = None

# Модели запросов/ответов
class QueryRequest(BaseModel):
    query: str
    user_id: str = None
    session_id: str = None

class QueryResponse(BaseModel):
    response: str
    category: str
    confidence: float
    similar_questions: list = []
    timestamp: str

class AnalyzeRequest(BaseModel):
    text: str

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

class ServerFeedbackRequest(BaseModel):
    query: str
    response: str
    rating: int
    user_feedback: str = ""
    user_id: str = None


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Инициализация системы при запуске"""
    global support_system
    try:
        logger.info("Инициализация AI Support System...")
        support_system = IntelligentSupportSystem()
        
        # Загрузка обученной модели
        support_system.kb.load_knowledge_base('app/data/knowledge_base.json')
        # ИЛИ обучение с нуля:
        
        logger.info("AI Support System успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")
        raise

@app.get("/")
async def root():
    return {"status": "AI Support Service is running", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy" if support_system else "unhealthy",
        "model_loaded": support_system is not None,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    if not support_system:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Анализ запроса: {req.text}")
        
        # ⬇️ ВЫЗЫВАЕМ МОДЕЛЬ В ОТДЕЛЬНОМ ПОТОКЕ ⬇️
        result = await asyncio.get_event_loop().run_in_executor(
            None,  # Используем стандартный executor
            support_system.process_query,  # Синхронный метод
            req.text  # Аргумент
        )
        
        # Адаптируем ответ под формат
        similar_questions = [
            item['knowledge_item']['question'] 
            for item in result['classification']['similar_items'][:3]
        ] if 'classification' in result and 'similar_items' in result['classification'] else []
        
        # Создаем рекомендацию на основе ответа
        recommendation = result['response']
        
        return {
            "category": result['classification']['main_category'],
            "category_score": float(result['classification']['confidence']),
            "entities": [],  # Можете добавить извлечение сущностей если нужно
            "kb_candidates": similar_questions,  # Используем похожие вопросы как кандидаты
            "selected_kb": {"title": result['classification']['main_category'], "template": recommendation},
            "recommendation": recommendation
        }
        
    except Exception as e:
        logger.error(f"Ошибка анализа: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

@app.post("/feedback")
async def submit_feedback(request: ServerFeedbackRequest, background_tasks: BackgroundTasks):
    """Сбор обратной связи для ML модели (асинхронно)"""
    if not support_system:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Создаем mock result для обратной связи
        mock_result = {
            'user_query': request.query,
            'response': request.response,
            'classification': {'main_category': 'Unknown'}
        }
        
        # Добавляем в фоновые задачи
        background_tasks.add_task(
            support_system.collect_feedback,
            mock_result,
            request.user_feedback,
            request.rating
        )
        
        logger.info(f"Обратная связь получена. Рейтинг: {request.rating}")
        
        return {"status": "feedback_received", "message": "Спасибо за обратную связь!"}
        
    except Exception as e:
        logger.error(f"Ошибка сохранения обратной связи: {e}")
        raise HTTPException(status_code=500, detail="Error saving feedback")

@app.get("/stats")
async def get_statistics():
    """Получение статистики по модели"""
    if not support_system:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Здесь можно добавить сбор статистики из вашей модели
        stats = {
            "status": "operational",
            "model_type": "IntelligentSupportSystem",
            "timestamp": datetime.now().isoformat(),
            "features": ["classification", "response_generation", "similar_questions"]
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail="Error getting statistics")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )