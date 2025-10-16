# backend/app/dependencies/__init__.py
from fastapi import HTTPException, Depends
from ..services.vector_model_service import vector_model_service

async def get_model_service():
    """Dependency для получения векторного сервиса модели"""
    # Always return the service - let the service handle its own errors
    # The service can work even with an empty knowledge base
    return vector_model_service

__all__ = ['get_model_service']