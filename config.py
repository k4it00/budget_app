from dotenv import load_dotenv
import os
import secrets

load_dotenv()
class Config:
    SECRET_KEY = secrets.token_urlsafe(16)
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET  = os.getenv('GOOGLE_CLIENT_SECRET')
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = 'redis://localhost:6379/0'
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD') 
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')
    STATIC_FOLDER = 'static'
    STATIC_URL_PATH = '/static'
    STATIC_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app/static')
    
