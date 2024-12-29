from flask import current_app, url_for
from datetime import datetime, timedelta
from flask_login import current_user 
from sqlalchemy import func, or_
from app import app, db, login_manager
from dateutil.relativedelta import relativedelta  # Ensure this import is present
from app.models import Category, Transaction, RecurringTransaction
from app import cache
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from datetime import datetime
import logging
import pandas as pd
import calendar
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import SQLAlchemyError

@login_manager.user_loader
def load_user(user_id):
    from app.models import User  # Import here to avoid circular import
    return User.query.get(int(user_id))

def init_db():
    with app.app_context():
        db.create_all()

        # Import here to avoid circular imports
        from app.models import User, Category

        # Check if the system user exists
        system_user = User.query.get(1)
        if not system_user:
            # Create the system user
            system_user = User(
                id=1,
                email='system@example.com',
                first_name='System',
                last_name='User'
            )
            db.session.add(system_user)

        # Add default categories if they don't exist
        default_categories = [
            {'name': 'Income', 'type': 'Income'},
            {'name': 'Housing', 'type': 'Expense'},
            {'name': 'Transportation', 'type': 'Expense'},
            {'name': 'Food', 'type': 'Expense'},
            {'name': 'Utilities', 'type': 'Expense'},
            {'name': 'Insurance', 'type': 'Expense'},
            {'name': 'Healthcare', 'type': 'Expense'},
            {'name': 'Savings', 'type': 'Savings'},
            {'name': 'Personal', 'type': 'Expense'},
            {'name': 'Entertainment', 'type': 'Expense'},
            {'name': 'Other', 'type': 'Expense'},
        ]

        for category_data in default_categories:
            if not Category.query.filter_by(name=category_data['name']).first():
                category = Category(
                    name=category_data['name'],
                    type=category_data['type'],  # Provide a valid type
                    description=category_data.get('description', None),  # Optional description
                    budget_limit=category_data.get('budget_limit', None),  # Optional budget limit
                    user_id=system_user.id  # Assign to system user
                )
                db.session.add(category)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error initializing database: {e}")
            
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def set_user_password(user, password):
    user.password_hash = generate_password_hash(password)

def check_user_password(user, password):
    if user.password_hash:
        return check_password_hash(user.password_hash, password)
    return False

def process_monthly_trends(transactions):
    """Process transactions into monthly income and expenses data for charts"""
    try:
        monthly_data = {}
        
        # Initialize the current month if no transactions
        if not transactions:
            today = datetime.utcnow()
            month_key = today.strftime('%Y-%m')
            monthly_data[month_key] = {'income': 0.0, 'expenses': 0.0}
        
        # Process transactions
        for transaction in transactions:
            month_key = transaction.date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {'income': 0.0, 'expenses': 0.0}
            
            amount = float(transaction.amount)
            if transaction.type.lower() == 'income':
                monthly_data[month_key]['income'] += amount
            else:
                monthly_data[month_key]['expenses'] += amount

        # Sort months and prepare return data
        sorted_months = sorted(monthly_data.keys())
        
        return {
            'labels': [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in sorted_months],
            'income': [float(monthly_data[m]['income']) for m in sorted_months],
            'expenses': [float(monthly_data[m]['expenses']) for m in sorted_months]
        }
    except Exception as e:
        print(f"Error in process_monthly_trends: {str(e)}")
        return {'labels': [], 'income': [], 'expenses': []}

def process_expense_distribution(transactions):
    """Process transactions into category-based expense distribution data for charts"""
    try:
        category_totals = {}
        
        for transaction in transactions:
            if transaction.type.lower() == 'expense' and transaction.category:
                cat_name = str(transaction.category.name)
                if cat_name not in category_totals:
                    category_totals[cat_name] = 0.0
                category_totals[cat_name] += float(transaction.amount)

        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'labels': [str(cat[0]) for cat in sorted_categories],
            'values': [float(cat[1]) for cat in sorted_categories]
        }
    except Exception as e:
        print(f"Error in process_expense_distribution: {str(e)}")
        return {'labels': [], 'values': []}

def get_or_create_category(name: str, type: str, user_id: int) -> Category:
    
    try:
        # Look for existing category
        category = Category.query.filter_by(
            name=name,
            user_id=user_id
        ).first()
        
        # Create new category if it doesn't exist
        if not category:
            category = Category(
                name=name,
                type=type,
                user_id=user_id,
                description=f'Imported category - {name}'
            )
            db.session.add(category)
            db.session.flush()  # Get the ID of the new category
            
        return category
        
    except SQLAlchemyError as e:
        logger.error(f"Error getting/creating category: {str(e)}")
        raise
def process_csv_import(file, user_id):
    
    try:
        df = pd.read_csv(file, encoding='utf-8')
        success_count = 0
        error_count = 0
        
        for _, row in df.iterrows():
            try:
                transaction_date = datetime.strptime(str(row['date']), '%Y-%m-%d')
                category_name = str(row['category']).strip()
                transaction_type = str(row['type']).lower()
                
                # Get or create category
                category = get_or_create_category(
                    name=category_name,
                    type=transaction_type,
                    user_id=user_id
                )
                
                # Create transaction
                transaction = Transaction(
                    date=transaction_date,
                    amount=float(row['amount']),
                    description=str(row['description']),
                    type=transaction_type,
                    category_id=category.id,
                    user_id=user_id
                )
                
                db.session.add(transaction)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing row: {str(e)}")
                continue
                
        db.session.commit()
        return success_count, error_count
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing CSV: {str(e)}")
        raise

@cache.cached(timeout=60, key_prefix='all_users')
def get_all_users():
    from app.models import User  # Import here to avoid circular import
    return User.query.all()

def cdn_url_for(endpoint, **values):
    if endpoint == 'static':
        values['filename'] = values.get('filename', '')
        return f"{current_app.config['CDN_DOMAIN']}/{values['filename']}"
    return url_for(endpoint, **values)

def override_url_for():
    return dict(url_for=cdn_url_for)

def calculate_current_spending():
    expenses = Transaction.query.filter_by(type='Expense').all()
    spending = {}
    for expense in expenses:
        if expense.category in spending:
            spending[expense.category] += expense.amount
        else:
            spending[expense.category] = expense.amount
    return spending

def get_all_categories(user_id=None, category_type=None):
    query = Category.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    if category_type:
        query = query.filter_by(type=category_type)
    return query.order_by(Category.type, Category.name).all()

def get_budget_categories():
    """
    Get budget categories with their spending progress for the current user.
    Returns a list of dictionaries containing category budget information.
    """
    try:
        # Get the current month's date range
        today = datetime.now()
        start_of_month = datetime(today.year, today.month, 1)
        end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        # Log the date range for debugging
        current_app.logger.debug(
            f"Calculating budget progress for period: {start_of_month} to {end_of_month}"
        )

        # Get all categories for the current user
        categories = Category.query.filter_by(user_id=current_user.id).all()
        
        if not categories:
            current_app.logger.info(f"No categories found for user {current_user.id}")
            return []

        budget_progress = []

        for category in categories:
            try:
                # Get total spent in this category for the current month
                total_spent = db.session.query(func.sum(Transaction.amount)).\
                    filter(
                        Transaction.category_id == category.id,  # Changed from category.name to category.id
                        Transaction.type == 'expense',  # Changed to lowercase to match your schema
                        Transaction.date >= start_of_month,
                        Transaction.date <= end_of_month,
                        Transaction.user_id == current_user.id
                    ).scalar() or 0

                # Calculate percentage of budget spent
                budget_limit = category.budget_limit or 0
                if budget_limit > 0:
                    percentage = (total_spent / budget_limit) * 100
                else:
                    percentage = 0

                # Create category progress dictionary
                category_progress = {
                    'id': category.id,
                    'name': category.name,
                    'spent': total_spent,
                    'budget': budget_limit,
                    'percentage': round(percentage, 1),
                    'status': get_status(percentage),
                    'remaining': budget_limit - total_spent if budget_limit > 0 else 0,
                    'type': category.type
                }

                budget_progress.append(category_progress)

                # Log high spending categories
                if percentage >= 90:
                    current_app.logger.warning(
                        f"High spending alert: Category '{category.name}' at {percentage:.1f}% of budget"
                    )

            except Exception as category_error:
                current_app.logger.error(
                    f"Error processing category {category.name}: {str(category_error)}"
                )
                continue

        # Sort categories by percentage spent (descending)
        budget_progress.sort(key=lambda x: x['percentage'], reverse=True)

        current_app.logger.info(
            f"Successfully calculated budget progress for {len(budget_progress)} categories"
        )

        return budget_progress

    except Exception as e:
        current_app.logger.error(f"Error in get_budget_categories: {str(e)}")
        return []
    
def get_budget_goals(user_id: int):
    """
    Get budget goals for a user with proper error handling.
    
    Args:
        user_id: The ID of the user
    
    Returns:
        List of budget goals or empty list if error occurs
    """
    try:
        # Get all categories with budget limits
        categories = Category.query.filter(
            Category.user_id == user_id,
            Category.budget_limit > 0
        ).all()
        
        budget_goals = []
        
        for category in categories:
            try:
                # Get current month's spending
                today = datetime.now()
                start_of_month = datetime(today.year, today.month, 1)
                end_of_month = (start_of_month.replace(month=start_of_month.month + 1) 
                              if start_of_month.month < 12 
                              else start_of_month.replace(year=start_of_month.year + 1, month=1)) - timedelta(days=1)
                
                total_spent = db.session.query(func.sum(Transaction.amount)).\
                    filter(
                        Transaction.category_id == category.id,
                        Transaction.type == 'expense',
                        Transaction.date.between(start_of_month, end_of_month),
                        Transaction.user_id == user_id
                    ).scalar() or 0
                
                # Calculate percentage and status
                percentage = (total_spent / category.budget_limit * 100) if category.budget_limit > 0 else 0
                
                budget_goal = {
                    'category_id': category.id,
                    'category_name': category.name,
                    'budget_limit': category.budget_limit,
                    'spent': total_spent,
                    'remaining': max(category.budget_limit - total_spent, 0),
                    'percentage': round(percentage, 1),
                    'status': get_status(percentage)
                }
                
                budget_goals.append(budget_goal)
                
            except Exception as e:
                logger.error(f"Error processing category {category.name}: {str(e)}")
                continue
        
        return budget_goals
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_budget_goals: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_budget_goals: {str(e)}")
        return []

def get_status(percentage: float) -> str:
    """Get the status based on the progress percentage"""
    if percentage >= 100:
        return {
            'class': 'danger',
            'label': 'Over Budget',
            'icon': 'fas fa-exclamation-circle'
        }
    elif percentage >= 80:
        return {
            'class': 'warning',
            'label': 'Warning',
            'icon': 'fas fa-exclamation-triangle'
        }
    else:
        return {
            'class': 'success',
            'label': 'On Track',
            'icon': 'fas fa-check-circle'
        }

class BudgetGoal:
    def to_dict(self):
        """Convert the budget goal to a dictionary"""
        progress = self.get_progress()
        return {
            'id': self.id,
            'amount': self.amount,
            'period': self.period,
            'category_name': self.category.name,
            'progress': progress['percentage'],
            'spent': progress['spent'],
            'remaining': progress['remaining'],
            'status': progress['status'],
            'formatted_amount': format_currency(self.amount)
        }

def process_pending_recurring_transactions():
    """Process any pending recurring transactions"""
    try:
        today = datetime.utcnow().date()
        # Get all active recurring transactions that are due
        recurring_transactions = RecurringTransaction.query.filter(
            RecurringTransaction.next_date <= today,
            or_(
                RecurringTransaction.end_date == None,
                RecurringTransaction.end_date >= today
            )
        ).all()

        transactions_created = 0
        for recurring in recurring_transactions:
            # Create actual transaction
            transaction = Transaction(
                user_id=recurring.user_id,
                category_id=recurring.category_id,
                amount=recurring.amount,
                type=recurring.type,
                date=recurring.next_date,
                description=f"Recurring: {recurring.name}",
                recurring_id=recurring.id
            )
            db.session.add(transaction)

            # Update next_date based on frequency
            if recurring.frequency == 'daily':
                recurring.next_date += timedelta(days=1)
            elif recurring.frequency == 'weekly':
                recurring.next_date += timedelta(weeks=1)
            elif recurring.frequency == 'monthly':
                # Add one month to next_date
                next_month = recurring.next_date.replace(day=1) + timedelta(days=32)
                recurring.next_date = next_month.replace(day=min(recurring.next_date.day, calendar.monthrange(next_month.year, next_month.month)[1]))
            elif recurring.frequency == 'yearly':
                # Add one year to next_date
                try:
                    recurring.next_date = recurring.next_date.replace(year=recurring.next_date.year + 1)
                except ValueError:  # Handle Feb 29 in leap years
                    recurring.next_date = recurring.next_date.replace(year=recurring.next_date.year + 1, day=28)

            transactions_created += 1

        db.session.commit()
        return transactions_created

    except Exception as e:
        current_app.logger.error(f"Error processing recurring transactions: {str(e)}")
        db.session.rollback()
        raise e

def format_currency(amount):
    if amount is None or not isinstance(amount, (int, float)):
        return "0 Ft"
    try:
        # Convert to float and get absolute value for formatting
        amount = float(amount)
        
        # Format with thousand separator and no decimal places
        formatted = "{:,.0f}".format(abs(amount))
        
        # Replace comma with space for Hungarian number formatting
        formatted = formatted.replace(",", " ")
        
        # Add negative sign if amount is negative
        if amount < 0:
            return f"-{formatted} Ft"
        return f"{formatted} Ft"
        
    except (ValueError, TypeError):
        return "0 Ft"
def ensure_user_has_categories(user_id):
    """Check if user has categories and create them if they don't"""
    existing_categories = Category.query.filter_by(user_id=user_id).first()
    
    if not existing_categories:
        default_categories = [
            {'name': 'Salary', 'type': 'Income'},
            {'name': 'Freelance', 'type': 'Income'},
            {'name': 'Investments', 'type': 'Income'},
            {'name': 'Groceries', 'type': 'Expense'},
            {'name': 'Rent', 'type': 'Expense'},
            {'name': 'Utilities', 'type': 'Expense'},
            {'name': 'Transportation', 'type': 'Expense'},
            {'name': 'Entertainment', 'type': 'Expense'}
        ]
        
        try:
            for cat_data in default_categories:
                category = Category(
                    name=cat_data['name'],
                    type=cat_data['type'],
                    user_id=user_id,
                    description=f"Default {cat_data['type'].lower()} category",
                    budget_limit=0.0
                )
                db.session.add(category)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating default categories: {str(e)}")
            return False
    return True

def ensure_user_has_recurring_transactions(user_id):
    """Check if user has recurring transactions and create default ones if they don't"""
    existing_recurring = RecurringTransaction.query.filter_by(user_id=user_id).first()
    
    if not existing_recurring:
        # Get the user's categories
        salary_category = Category.query.filter_by(user_id=user_id, name='Salary').first()
        rent_category = Category.query.filter_by(user_id=user_id, name='Rent').first()
        utilities_category = Category.query.filter_by(user_id=user_id, name='Utilities').first()

        default_recurring = [
            {
                'name': 'Monthly Salary',
                'type': 'Income',
                'amount': 0.0,
                'frequency': 'monthly',
                'category_id': salary_category.id if salary_category else None,
                'start_date': datetime.utcnow()
            },
            {
                'name': 'Rent Payment',
                'type': 'Expense',
                'amount': 0.0,
                'frequency': 'monthly',
                'category_id': rent_category.id if rent_category else None,
                'start_date': datetime.utcnow()
            },
            {
                'name': 'Utility Bills',
                'type': 'Expense',
                'amount': 0.0,
                'frequency': 'monthly',
                'category_id': utilities_category.id if utilities_category else None,
                'start_date': datetime.utcnow()
            }
        ]
        
        try:
            for rec_data in default_recurring:
                recurring = RecurringTransaction(
                    user_id=user_id,
                    name=rec_data['name'],
                    type=rec_data['type'],
                    amount=rec_data['amount'],
                    frequency=rec_data['frequency'],
                    category_id=rec_data['category_id'],
                    start_date=rec_data['start_date'],
                    next_date=rec_data['start_date']
                )
                db.session.add(recurring)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating default recurring transactions: {str(e)}")
            return False
    return True


def utility_processor():
    return dict(
        format_currency=format_currency,
        min=min
    )