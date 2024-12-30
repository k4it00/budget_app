# models.py
from datetime import datetime
from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    google_id = db.Column(db.String(128))
    is_google_user = db.Column(db.Boolean, default=False)
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)

    # Define relationships using back_populates
    categories = db.relationship('Category', back_populates='user', lazy=True)
    transactions = db.relationship('Transaction', back_populates='user', lazy=True)
    recurring_transactions = db.relationship('RecurringTransaction', back_populates='user', lazy=True)
    budget_goals = db.relationship('BudgetGoal', back_populates='user', cascade='all, delete-orphan')

    def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if not self.username and self.email:
                # Generate username from email if not provided
                self.username = self.email.split('@')[0]
    def set_password(self, password):
        """Set the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if provided password matches the hash."""
        return check_password_hash(self.password_hash, password)

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200))
    budget_limit = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Update the relationship definition
    budget_goals = db.relationship('BudgetGoal', back_populates='category', lazy=True)
    user = db.relationship('User', back_populates='categories', lazy=True)
    transactions = db.relationship('Transaction', back_populates='category', lazy=True)
    recurring_transactions = db.relationship('RecurringTransaction', back_populates='category', lazy=True)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Note: 'users.id' not 'user.id'
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'Income' or 'Expense'
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(200))
    recurring_id = db.Column(db.Integer, db.ForeignKey('recurring_transactions.id'))
    
    # Define relationships using back_populates
    category = db.relationship('Category', back_populates='transactions')
    user = db.relationship('User', back_populates='transactions')
    recurring = db.relationship('RecurringTransaction', back_populates='transactions')

class BudgetGoal(db.Model):
    __tablename__ = 'budget_goals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)  # Change to nullable=True
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    target_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Update the relationship definitions
    user = db.relationship('User', back_populates='budget_goals')
    category = db.relationship('Category', back_populates='budget_goals')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'target_amount': self.target_amount,
            'current_amount': self.current_amount,
            'target_date': self.target_date.strftime('%Y-%m-%d'),
            'progress': round((self.current_amount / self.target_amount) * 100) if self.target_amount > 0 else 0
        }

class RecurringTransaction(db.Model):
    __tablename__ = 'recurring_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=True)
    next_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, server_default='true', nullable=False) 



    # Relationships using back_populates
    user = db.relationship('User', back_populates='recurring_transactions')
    category = db.relationship('Category', back_populates='recurring_transactions')
    transactions = db.relationship('Transaction', back_populates='recurring')

    # Relationships using back_populates
    user = db.relationship('User', back_populates='recurring_transactions')
    category = db.relationship('Category', back_populates='recurring_transactions')

    def __repr__(self):
        return f'<RecurringTransaction {self.name}>'


