import os
import secrets

class Config:
    SECRET_KEY = secrets.token_urlsafe(16)
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = 'redis://localhost:6379/0'
    CDN_DOMAIN = os.environ.get('CDN_DOMAIN') or 'https://your-cdn-domain.com'