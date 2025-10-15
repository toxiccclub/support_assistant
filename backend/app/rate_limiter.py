# backend/app/rate_limiter.py
"""
Rate limiting implementation
"""

import time
from typing import Dict, Tuple
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from .config import settings

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.max_requests = 10  # requests per window
        self.window_size = 60   # seconds
    
    def is_allowed(self, client_ip: str) -> Tuple[bool, int]:
        """Check if request is allowed and return remaining requests"""
        now = time.time()
        client_requests = self.requests[client_ip]
        
        # Remove old requests outside the window
        while client_requests and client_requests[0] <= now - self.window_size:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) >= self.max_requests:
            return False, 0
        
        # Add current request
        client_requests.append(now)
        
        # Return remaining requests
        remaining = max(0, self.max_requests - len(client_requests))
        return True, remaining
    
    def get_reset_time(self, client_ip: str) -> int:
        """Get time when rate limit resets"""
        client_requests = self.requests[client_ip]
        if not client_requests:
            return int(time.time())
        
        oldest_request = client_requests[0]
        return int(oldest_request + self.window_size)

# Global rate limiter instance
rate_limiter = RateLimiter()

async def check_rate_limit(request: Request):
    """Middleware function to check rate limits"""
    client_ip = request.client.host
    
    # Skip rate limiting for localhost in development
    if client_ip in ["127.0.0.1", "localhost"] and settings.is_production() == False:
        return
    
    allowed, remaining = rate_limiter.is_allowed(client_ip)
    
    if not allowed:
        reset_time = rate_limiter.get_reset_time(client_ip)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Too many requests.",
            headers={
                "X-RateLimit-Limit": str(rate_limiter.max_requests),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(reset_time - int(time.time()))
            }
        )
    
    # Add rate limit headers to response
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_reset = rate_limiter.get_reset_time(client_ip)
