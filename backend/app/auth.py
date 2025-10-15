# backend/app/auth.py
"""
Authentication and authorization utilities
"""

import os
import secrets
from typing import Optional
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Simple API key authentication for admin endpoints
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "dev-admin-key-12345")

security = HTTPBearer()

async def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify admin API key"""
    if credentials.credentials != ADMIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True

async def get_current_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current admin user (simple implementation)"""
    await verify_admin_token(credentials)
    return {"username": "admin", "role": "admin"}

# For development only - remove in production
def get_admin_key() -> str:
    """Get admin API key for development"""
    if os.getenv("ENVIRONMENT", "development").lower() == "development":
        return ADMIN_API_KEY
    return "Admin key not available in production"
