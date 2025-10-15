# backend/app/logging_utils.py
import logging
import os
import json
from datetime import datetime
from pathlib import Path
import functools
import time
import asyncio
from typing import Any, Callable, Optional, Dict
import structlog
from .config import settings

class JSONFormatter(logging.Formatter):
    """JSON форматтер для структурированного логирования"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Добавляем дополнительные поля если есть
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'execution_time'):
            log_entry['execution_time'] = record.execution_time
        if hasattr(record, 'error_type'):
            log_entry['error_type'] = record.error_type
        
        # Добавляем exception info если есть
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)

def setup_logging(log_level: str = None) -> str:
    """Настройка структурированного логирования с JSON форматом"""
    
    if log_level is None:
        log_level = settings.get_log_level()
    
    # Получаем путь к файлу логов из настроек
    log_file = settings.log_file_path
    if not log_file:
        # Если путь не указан, не создаем файловый handler
        log_file = None
    elif not log_file.endswith('.log'):
        # Если путь указан но не является файлом, создаем дефолтный
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = log_dir / f"app_{timestamp}.log"
    
    # Настройка root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Создаем JSON formatter (нужен для продакшена и файлов)
    json_formatter = JSONFormatter()
    
    # JSON File handler (only if log file path is provided)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)
    
    # Console handler (читаемый формат для разработки)
    if not settings.is_production():
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    else:
        # В продакшене используем JSON и для консоли
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(json_formatter)
        root_logger.addHandler(console_handler)
    
    # Настройка structlog для дополнительного контекста
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    return str(log_file)

def get_structured_logger(name: str) -> structlog.BoundLogger:
    """Получить структурированный логгер"""
    return structlog.get_logger(name)

def log_execution_time(func: Callable) -> Callable:
    """Декоратор для логирования времени выполнения синхронных функций"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        function_name = f"{func.__module__}.{func.__name__}"
        logger = get_structured_logger(__name__)
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                "Function completed",
                function=function_name,
                execution_time=execution_time,
                status="success"
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                "Function failed",
                function=function_name,
                execution_time=execution_time,
                error=str(e),
                error_type=type(e).__name__,
                status="error"
            )
            raise
    
    return wrapper

def log_execution_time_async(func: Callable) -> Callable:
    """Декоратор для логирования времени выполнения асинхронных функций"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        function_name = f"{func.__module__}.{func.__name__}"
        logger = get_structured_logger(__name__)
        
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                "Async function completed",
                function=function_name,
                execution_time=execution_time,
                status="success"
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                "Async function failed",
                function=function_name,
                execution_time=execution_time,
                error=str(e),
                error_type=type(e).__name__,
                status="error"
            )
            raise
    
    return wrapper

def log_request(request_id: str, user_id: Optional[str] = None):
    """Декоратор для логирования HTTP запросов"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_structured_logger(__name__)
            logger.info(
                "Request started",
                request_id=request_id,
                user_id=user_id,
                function=func.__name__
            )
            
            try:
                result = await func(*args, **kwargs)
                logger.info(
                    "Request completed",
                    request_id=request_id,
                    user_id=user_id,
                    status="success"
                )
                return result
            except Exception as e:
                logger.error(
                    "Request failed",
                    request_id=request_id,
                    user_id=user_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    status="error"
                )
                raise
        
        return wrapper
    return decorator