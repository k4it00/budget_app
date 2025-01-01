from flask import Flask, url_for
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dateutil.relativedelta import relativedelta 
from authlib.integrations.flask_client import OAuth
from flask_compress import Compress
from flask_caching import Cache
from flask import jsonify, request
from werkzeug.exceptions import NotFound
import secrets
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from urllib.parse import urlparse
from flask_mail import Mail
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
app = Flask(__name__,
           static_url_path='/static',
           static_folder='static')
app.config.from_object(Config)
app.config['CACHE_TYPE'] = 'redis'
app.config['CACHE_REDIS_URL'] = 'redis://localhost:6379/0'
secret_key = secrets.token_urlsafe(16)
app.secret_key = secret_key 
app.config.from_object(Config)

# Configure the database URL
DATABASE_URL = os.getenv('DATABASE_URI')

# Keep your existing postgres:// to postgresql:// conversion logic
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Configure SQLAlchemy - MOVED BEFORE db.init_app(app)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'pool_recycle': 1800,
    'pool_pre_ping': True
}
# Configure static files
app.config.update(
    STATIC_FOLDER=os.path.join(app.root_path, 'static'),
    SEND_FILE_MAX_AGE_DEFAULT=31536000
    )

# Initialize extensions with app - MOVED AFTER setting SQLALCHEMY_DATABASE_URI
db.init_app(app)
migrate = Migrate(app, db)
mail.init_app(app)
login_manager.init_app(app)
cache = Cache(app)
Compress(app)

# Register template function
@app.template_global()
def static_file_url(filename):
    return url_for('static', filename=filename)
# Initialize OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Configure Flask-Login
login_manager.login_view = 'auth_login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Import helpers before using it
from app import helpers

# Register the utility processor
app.context_processor(helpers.utility_processor)
@app.template_filter('format_currency')
def format_currency(value):
    return "{:,.0f} Ft".format(value)

@app.template_filter('format_date')
def format_date(value):
    return value.strftime('%Y-%m-%d')
# Import routes and models at the end to avoid circular imports
from app import routes, models

from app.helpers import init_db

__all__ = ['app', 'db', 'init_db']