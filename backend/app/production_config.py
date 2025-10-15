# backend/app/production_config.py
"""
Production configuration settings
Use this file to override default settings for production deployment
"""

import os
from .config import Settings

class ProductionSettings(Settings):
    """Production-specific settings"""
    
    # Override CORS for production
    cors_origins: list = [
        # Add your production frontend URLs here
        "https://yourdomain.com",
        "https://www.yourdomain.com",
    ]
    
    # Production logging
    log_level: str = "WARNING"
    
    # Security settings
    max_request_size: int = 512 * 1024  # 512KB for production
    api_timeout: int = 15  # Shorter timeout for production
    
    # Model settings
    max_errors: int = 3  # Stricter error handling
    model_timeout: int = 30  # Shorter model timeout
    
    # Monitoring
    enable_metrics: bool = True
    
    def get_cors_origins(self) -> list:
        """Get CORS origins from environment variables in production"""
        env_origins = os.getenv("CORS_ORIGINS")
        if env_origins:
            return [origin.strip() for origin in env_origins.split(",")]
        return self.cors_origins

# Use production settings if ENVIRONMENT=production
if os.getenv("ENVIRONMENT", "development").lower() == "production":
    settings = ProductionSettings()
else:
    from .config import settings
