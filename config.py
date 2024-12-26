import os
import secrets

class Config:
    SECRET_KEY = secrets.token_urlsafe(16)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', 
        "521888432006-o0reaqqldvegla1fqc2go0mhgsp2e0nm.apps.googleusercontent.com")
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', 
        "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")
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = 'redis://localhost:6379/0'
    CDN_DOMAIN = os.environ.get('CDN_DOMAIN') or 'https://your-cdn-domain.com'