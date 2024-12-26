from flask import current_app, url_for
from datetime import datetime, timedelta
from flask_login import current_user 
from sqlalchemy import func
from app import db, app
from dateutil.relativedelta import relativedelta  # Ensure this import is present
from app.models import Category, Transaction, BudgetGoal, RecurringTransaction
from app import cache


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
    """Get budget categories with their spending progress for the current user"""
    try:
        # Get the current month's date range
        today = datetime.now()
        start_of_month = datetime(today.year, today.month, 1)
        end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        # Get all categories for the current user
        categories = Category.query.filter_by(user_id=current_user.id).all()
        budget_progress = []

        for category in categories:
            # Get total spent in this category for the current month
            total_spent = db.session.query(func.sum(Transaction.amount)).\
                filter(Transaction.category_id == category.id,
                       Transaction.type == 'Expense',
                       Transaction.date >= start_of_month,
                       Transaction.date <= end_of_month,
                       Transaction.user_id == current_user.id).scalar() or 0

            # Calculate percentage of budget spent
            if category.budget_limit:
                percentage = (total_spent / category.budget_limit) * 100
            else:
                percentage = 0

            budget_progress.append({
                'name': category.name,
                'spent': total_spent,
                'budget': category.budget_limit or 0,
                'percentage': round(percentage, 1)
            })

        return budget_progress

    except Exception as e:
        print(f"Error in get_budget_categories: {str(e)}")
        return []

def process_recurring_transactions():
    with app.app_context():
        try:
            now = datetime.now()
            recurring_transactions = RecurringTransaction.query.filter_by(is_active=True).all()
            
            for recurring in recurring_transactions:
                try:
                    # Skip if end date is set and passed
                    if recurring.end_date and recurring.end_date < now:
                        continue
                        
                    # Get the last processed date or use start date if never processed
                    last_processed = recurring.last_processed or recurring.start_date
                    next_date = None
                    
                    # Calculate the next date based on frequency
                    if recurring.frequency == 'daily':
                        next_date = last_processed + timedelta(days=1)
                    elif recurring.frequency == 'weekly':
                        next_date = last_processed + timedelta(weeks=1)
                    elif recurring.frequency == 'monthly':
                        next_date = last_processed + relativedelta(months=1)
                    elif recurring.frequency == 'yearly':
                        next_date = last_processed + relativedelta(years=1)
                    
                    # Process all pending transactions up to current date
                    while next_date <= now:
                        try:
                            # Get the category ID based on the category name
                            category = Category.query.filter_by(
                                name=recurring.category,
                                user_id=recurring.user_id
                            ).first()
                            
                            if not category:
                                current_app.logger.error(f"Category not found for recurring transaction: {recurring.id}")
                                break

                            # Create new transaction
                            new_transaction = Transaction(
                                date=next_date,
                                type=recurring.type,
                                category_id=category.id,
                                amount=recurring.amount,
                                description=f"[Recurring] {recurring.description}" if recurring.description else "[Recurring Transaction]",
                                user_id=recurring.user_id
                            )
                            
                            db.session.add(new_transaction)
                            recurring.last_processed = next_date
                            
                            # Calculate next date for the loop
                            if recurring.frequency == 'daily':
                                next_date += timedelta(days=1)
                            elif recurring.frequency == 'weekly':
                                next_date += timedelta(weeks=1)
                            elif recurring.frequency == 'monthly':
                                next_date += relativedelta(months=1)
                            elif recurring.frequency == 'yearly':
                                next_date += relativedelta(years=1)
                                
                        except Exception as e:
                            current_app.logger.error(f"Error processing recurring transaction {recurring.id}: {str(e)}")
                            db.session.rollback()
                            break
                            
                except Exception as e:
                    current_app.logger.error(f"Error processing recurring transaction {recurring.id}: {str(e)}")
                    continue
            
            try:
                db.session.commit()
                current_app.logger.info("Recurring transactions processed successfully")
            except Exception as e:
                current_app.logger.error(f"Error committing recurring transactions: {str(e)}")
                db.session.rollback()
                
        except Exception as e:
            current_app.logger.error(f"Error in process_recurring_transactions: {str(e)}")

def process_pending_recurring_transactions():
    """Process any pending recurring transactions immediately"""
    try:
        now = datetime.now()
        recurring_transactions = RecurringTransaction.query.filter_by(is_active=True).all()
        needs_processing = False
        for recurring in recurring_transactions:
            if recurring.end_date and recurring.end_date < now:
                recurring.is_active = False
            last_processed = recurring.last_processed or recurring.start_date
            if last_processed < now:
                needs_processing = True
        if needs_processing:
            process_recurring_transactions()
            current_app.logger.info("Pending recurring transactions processed")
        else:
            current_app.logger.info("No pending recurring transactions to process")
    except Exception as e:
        current_app.logger.error(f"Error checking recurring transactions: {str(e)}")

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

def utility_processor():
    return dict(
        format_currency=format_currency,
        min=min
    )