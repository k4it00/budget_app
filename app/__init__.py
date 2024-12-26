from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dateutil.relativedelta import relativedelta 
from authlib.integrations.flask_client import OAuth
from flask_compress import Compress
from flask_caching import Cache
import secrets
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

app = Flask(__name__, static_folder='static')
app.config['CACHE_TYPE'] = 'redis'
app.config['CACHE_REDIS_URL'] = 'redis://localhost:6379/0'
cache = Cache(app)
Compress(app)
secret_key = secrets.token_urlsafe(16)
app.secret_key = secret_key 
app.config.from_object(Config)

# Initialize OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Import User model
from app.models import User

# User loader callback
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def init_db():
    with app.app_context():
        db.create_all()
        from app.models import Category  # Import Category here to avoid circular import
        # Check if system categories exist specifically for user_id=1
        system_categories = Category.query.filter_by(user_id=1).first()
        if not system_categories:
            # Create default categories for the system user
            default_categories = [
                Category(name='Salary', type='Income', user_id=1, description='System default - Salary'),
                Category(name='Freelance', type='Income', user_id=1, description='System default - Freelance'),
                Category(name='Investments', type='Income', user_id=1, description='System default - Investments'),
                Category(name='Other Income', type='Income', user_id=1, description='System default - Other Income'),
                Category(name='Groceries', type='Expense', user_id=1, description='System default - Groceries'),
                Category(name='Rent', type='Expense', user_id=1, description='System default - Rent'),
                Category(name='Utilities', type='Expense', user_id=1, description='System default - Utilities'),
                Category(name='Transportation', type='Expense', user_id=1, description='System default - Transportation'),
                Category(name='Entertainment', type='Expense', user_id=1, description='System default - Entertainment'),
                Category(name='Healthcare', type='Expense', user_id=1, description='System default - Healthcare'),
                Category(name='Shopping', type='Expense', user_id=1, description='System default - Shopping'),
                Category(name='Restaurants', type='Expense', user_id=1, description='System default - Restaurants')
            ]
            try:
                db.session.bulk_save_objects(default_categories)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Error initializing default categories: {str(e)}")
        else:
            print("System categories already exist, skipping initialization.")

# Import helpers before using it
from app import helpers

# Register the utility processor
app.context_processor(helpers.utility_processor)
app.context_processor(helpers.override_url_for)

# Import routes and models at the end to avoid circular imports
from app import routes, models, errors