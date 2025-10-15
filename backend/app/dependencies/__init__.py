# backend/app/dependencies/__init__.py
from fastapi import HTTPException, Depends
from ..services.model_service import model_service

async def get_model_service():
    """Dependency для получения сервиса модели"""
    if not model_service.get_status()['operational']:
        raise HTTPException(
            status_code=503,
            detail="Сервис временно недоступен. Пожалуйста, попробуйте позже."
        )
    return model_service

__all__ = ['get_model_service']