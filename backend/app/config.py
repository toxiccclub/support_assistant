# backend/app/config.py
import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    """Настройки приложения с поддержкой переменных окружения"""
    
    # CORS настройки
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000",
        description="Разрешенные CORS origins (через запятую)"
    )
    
    # Безопасность
    max_request_size: int = Field(default=1024 * 1024, description="Максимальный размер запроса в байтах")
    api_timeout: int = Field(default=30, description="Таймаут API в секундах")
    max_errors: int = Field(default=5, description="Максимальное количество ошибок перед Circuit Breaker")
    
    # Пути к файлам
    knowledge_base_path: str = Field(
        default="app/data/knowledge_base.json",
        description="Путь к файлу базы знаний"
    )
    log_level: str = Field(default="INFO", description="Уровень логирования")
    log_file_path: Optional[str] = Field(default=None, description="Путь к файлу логов")
    
    # Модель
    model_timeout: int = Field(default=60, description="Таймаут для обработки модели в секундах")
    enable_fallback: bool = Field(default=True, description="Включить fallback ответы при ошибках")
    
    # API Configuration
    api_key: str = Field(default="sk-Hheb_7mljCgAWSIIyEYbnw", description="OpenAI API key")
    base_url: str = Field(default="https://llm.t1v.scibox.tech/v1", description="OpenAI API base URL")
    embedding_model: str = Field(default="bge-m3", description="Embedding model name")
    llm_model: str = Field(default="Qwen2.5-72B-Instruct-AWQ", description="LLM model name")
    
    # Мониторинг
    enable_metrics: bool = Field(default=False, description="Включить сбор метрик")
    metrics_port: int = Field(default=9090, description="Порт для метрик")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def get_cors_origins(self) -> List[str]:
        """Получить CORS origins с поддержкой переменных окружения"""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def get_knowledge_base_path(self) -> str:
        """Получить путь к базе знаний с проверкой существования"""
        path = Path(self.knowledge_base_path)
        if not path.exists():
            # Попробуем найти файл в других возможных местах
            possible_paths = [
                "app/data/knowledge_base.json",
                "backend/app/data/knowledge_base.json",
                "data/knowledge_base.json"
            ]
            for possible_path in possible_paths:
                if Path(possible_path).exists():
                    return possible_path
        return str(path)
    
    def is_production(self) -> bool:
        """Проверка, запущено ли приложение в продакшене"""
        return os.getenv("ENVIRONMENT", "development").lower() == "production"
    
    def get_log_level(self) -> str:
        """Получить уровень логирования"""
        return os.getenv("LOG_LEVEL", self.log_level).upper()

# Создаем экземпляр настроек
settings = Settings()