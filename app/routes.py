from app.helpers import ensure_user_has_categories
from flask import render_template, request, redirect, url_for, flash, jsonify, Response, current_app, session
from flask_login import login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from sqlalchemy import func, extract
from app import app, db, google
from app.forms import RegistrationForm, LoginForm, TransactionForm, BudgetGoalForm, RecurringTransactionForm, CategoryForm
import re
import io, csv, pandas as pd
import json
import plotly.express as px
import plotly
import calendar 
from app.helpers import set_user_password, check_user_password
from sqlalchemy.exc import SQLAlchemyError 
from app.models import User, Category, Transaction, BudgetGoal, RecurringTransaction
from app.helpers import process_pending_recurring_transactions, get_all_categories, get_budget_categories, calculate_current_spending, format_currency
import secrets
import logging
from flask_mail import Message
from app import mail  

@app.route('/')
@login_required
def home():
    try:
        # Calculate date range for current month
        today = datetime.now()
        start_of_month = datetime(today.year, today.month, 1)
        end_of_month = start_of_month + relativedelta(months=1)

        # Query transactions for current month
        monthly_transactions = db.session.query(Transaction).join(
            Category
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= start_of_month,
            Transaction.date < end_of_month
        ).all()

        # Calculate monthly totals
        monthly_income = sum(t.amount for t in monthly_transactions if t.type.lower() == 'income')
        monthly_expenses = sum(t.amount for t in monthly_transactions if t.type.lower() == 'expense')
        total_balance = monthly_income - monthly_expenses

        # Get recent transactions with proper relationship loading
        recent_transactions = db.session.query(Transaction).join(
            Category
        ).filter(
            Transaction.user_id == current_user.id
        ).order_by(
            Transaction.date.desc()
        ).limit(5).all()

        # Get budget categories and their spending
        budget_categories = []
        expense_categories = Category.query.filter(
            Category.user_id == current_user.id,
            func.lower(Category.type) == 'expense'
        ).all()

        for category in expense_categories:
            # Calculate spent amount for this category in current month
            spent = sum(t.amount for t in monthly_transactions 
                       if t.category_id == category.name and t.type.lower() == 'expense')

            # Calculate percentage of budget used
            if category.budget_limit and category.budget_limit > 0:
                percentage = (spent / category.budget_limit) * 100
            else:
                percentage = 0

            budget_categories.append({
                'name': category.name,
                'spent': spent,
                'budget_limit': category.budget_limit,
                'percentage': min(round(percentage, 1), 100)
            })

        current_app.logger.info(f"Successfully loaded dashboard for user {current_user.id}")
        
        return render_template('index.html',
                             total_balance=total_balance,
                             monthly_income=monthly_income,
                             monthly_expenses=monthly_expenses,
                             recent_transactions=recent_transactions,
                             budget_categories=budget_categories,
                             current_month=today.strftime('%B %Y'))

    except Exception as e:
        current_app.logger.error(f"Error in home route: {str(e)}", exc_info=True)
        flash('An error occurred while loading the dashboard', 'error')
        return render_template('index.html',
                             total_balance=0,
                             monthly_income=0,
                             monthly_expenses=0,
                             recent_transactions=[],
                             budget_categories=[],
                             current_month=datetime.now().strftime('%B %Y'))

@app.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    if request.method == 'POST':
        try:
            # Get form data
            amount = float(request.form['amount'])
            description = request.form['description']
            date_str = request.form['date']
            transaction_type = request.form['type']
            category_id = request.form['category_id']
            
            # Validate category exists and belongs to user
            category = Category.query.filter_by(
                id=category_id,
                user_id=current_user.id
            ).first()
            
            if not category:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Invalid category'}), 400
                flash('Invalid category selected.', 'danger')
                return redirect(url_for('add_transaction'))
            
            # Validate category type matches transaction type
            if category.type.lower() != transaction_type.lower():
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Category type does not match transaction type'}), 400
                flash('Category type does not match transaction type.', 'danger')
                return redirect(url_for('add_transaction'))
            
            # Convert date string to datetime
            date = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Create new transaction
            transaction = Transaction(
                amount=amount,
                description=description,
                date=date,
                type=transaction_type,
                category_id=category_id,
                user_id=current_user.id
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'message': 'Transaction added successfully!'
                })
            
            flash('Transaction added successfully!', 'success')
            return redirect(url_for('view_transactions'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error adding transaction: {str(e)}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': str(e)}), 500
            flash('Error adding transaction. Please try again.', 'danger')
            pass
    # GET request - render form
    try:
        # Ensure user has default categories
        ensure_user_has_categories(current_user.id)
        
        # Get income categories
        income_categories = Category.query.filter(
            db.and_(
                Category.type.ilike('Income'),  # Case-insensitive comparison
                Category.user_id == current_user.id
            )
        ).order_by(Category.name).all()
        
        # Get expense categories
        expense_categories = Category.query.filter(
            db.and_(
                Category.type.ilike('Expense'),  # Case-insensitive comparison
                Category.user_id == current_user.id
            )
        ).order_by(Category.name).all()
        
        return render_template('add_transaction.html',
                             income_categories=income_categories,
                             expense_categories=expense_categories)
    except Exception as e:
        app.logger.error(f'Error loading categories: {str(e)}')
        flash('Error loading categories. Please try again.', 'danger')
        return redirect(url_for('home'))

@app.route('/view_transactions')
@login_required
def view_transactions():
    try:
        # Get filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        category_id = request.args.get('category_id')
        transaction_type = request.args.get('type')

        # Base query
        query = Transaction.query.filter_by(user_id=current_user.id)

        # Apply filters
        if start_date:
            query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d'))
        if category_id:
            query = query.filter(Transaction.category_id == category_id)
        if transaction_type:
            query = query.filter(Transaction.type == transaction_type)

        # Get transactions
        transactions = query.order_by(Transaction.date.desc()).all()

        # Calculate totals
        total_income = sum(t.amount for t in transactions if t.type == 'income')
        total_expenses = sum(t.amount for t in transactions if t.type == 'expense')

        # Get categories
        categories = Category.query.filter_by(user_id=current_user.id).all()
        income_categories = [c for c in categories if c.type == 'income']
        expense_categories = [c for c in categories if c.type == 'expense']

        return render_template('view_transactions.html',
                             transactions=transactions,
                             categories=categories,
                             income_categories=income_categories,
                             expense_categories=expense_categories,
                             total_income=total_income,
                             total_expenses=total_expenses)

    except Exception as e:
        app.logger.error(f'Error viewing transactions: {str(e)}')
        flash('Error loading transactions', 'danger')
        return redirect(url_for('home'))



@app.route('/delete_transaction/<int:transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    try:
        transaction = Transaction.query.filter_by(
            id=transaction_id,
            user_id=current_user.id
        ).first_or_404()
        
        db.session.delete(transaction)
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Transaction deleted successfully'})
        
        flash('Transaction deleted successfully', 'success')
        return redirect(url_for('view_transactions'))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error deleting transaction: {str(e)}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash('Error deleting transaction', 'danger')
        return redirect(url_for('view_transactions'))


@app.route('/update_transaction/<int:transaction_id>', methods=['POST'])
@login_required  
def update_transaction(transaction_id):
    try:
        transaction = db.session.get_or_404(Transaction, transaction_id)
        
        # Validate form data
        if not all(key in request.form for key in ['type', 'category_id', 'amount', 'date', 'description']):
            flash('Missing required fields', 'error')
            return redirect(url_for('view_transactions'))
        
        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                raise ValueError("Amount must be greater than 0")
        except ValueError as e:
            flash(f'Invalid amount: {str(e)}', 'error')
            return redirect(url_for('view_transactions'))

        # Update transaction
        transaction.type = request.form['type']
        transaction.category_id = request.form['category_id']
        transaction.amount = amount
        transaction.description = request.form['description']
        transaction.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        
        db.session.commit()
        flash('Transaction updated successfully', 'success')
    except ValueError as e:
        db.session.rollback()
        current_app.logger.error(f"Value error updating transaction: {str(e)}")
        flash(f'Error updating transaction: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating transaction: {str(e)}")
        flash('An error occurred while updating the transaction', 'error')
    
    return redirect(url_for('view_transactions'))

logger = logging.getLogger(__name__)

@app.route('/budget_goals', methods=['GET', 'POST'])
@login_required
def set_budget_goals():
    try:
        categories = Category.query.filter_by(user_id=current_user.id).all()
        
        # Get existing budget goals
        budget_goals = BudgetGoal.query.filter_by(user_id=current_user.id).all()
        
        # Create a dictionary of category_id: goal for easy lookup
        goals_dict = {goal.category_id: goal for goal in budget_goals}
        
        if request.method == 'POST':
            # Process form submission
            for category in categories:
                amount = request.form.get(f'amount_{category.id}', type=float)
                period = request.form.get(f'period_{category.id}')
                
                if amount is not None:
                    # Update existing goal or create new one
                    if category.id in goals_dict:
                        goal = goals_dict[category.id]
                        goal.amount = amount
                        goal.period = period
                    else:
                        goal = BudgetGoal(
                            user_id=current_user.id,
                            category_id=category.id,
                            amount=amount,
                            period=period
                        )
                        db.session.add(goal)
            
            db.session.commit()
            flash('Budget goals updated successfully!', 'success')
            return redirect(url_for('set_budget_goals'))
        
        return render_template(
            'budget_goals.html',
            categories=categories,
            goals=goals_dict,
            title='Budget Goals'
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in set_budget_goals: {str(e)}")
        flash('An error occurred while processing budget goals.', 'error')
        return redirect(url_for('home'))

# Add these template filters if not already present
@app.template_filter('format_currency')
def format_currency(value):
    if value is None:
        return "$0.00"
    return f"${value:,.2f}"

@app.template_filter('format_date')
def format_date(value):
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            return value
    return value.strftime('%Y-%m-%d')

@app.route('/manage-categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    try:
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'add':
                name = request.form.get('name')
                type = request.form.get('type')
                description = request.form.get('description', '')
                
                # Validate inputs
                if not name or not type:
                    flash('Name and type are required', 'error')
                    return redirect(url_for('manage_categories'))
                
                # Check if category already exists for this user
                existing_category = Category.query.filter_by(
                    user_id=current_user.id,
                    name=name,
                    type=type
                ).first()
                
                if existing_category:
                    flash('A category with this name and type already exists', 'error')
                    return redirect(url_for('manage_categories'))
                
                # Create new category
                new_category = Category(
                    name=name,
                    type=type,
                    description=description,
                    user_id=current_user.id
                )
                db.session.add(new_category)
                db.session.commit()
                flash('Category added successfully!', 'success')
                
            elif action == 'edit':
                category_id = request.form.get('category_id')
                if not category_id:
                    flash('Category ID is required', 'error')
                    return redirect(url_for('manage_categories'))
                
                category = Category.query.get_or_404(category_id)
                
                # Verify ownership
                if category.user_id != current_user.id:
                    flash('Unauthorized access', 'error')
                    return redirect(url_for('manage_categories'))
                
                # Update category
                category.name = request.form.get('name', category.name)
                category.type = request.form.get('type', category.type)
                category.description = request.form.get('description', category.description)
                
                db.session.commit()
                flash('Category updated successfully!', 'success')
                
            elif action == 'delete':
                category_id = request.form.get('category_id')
                if not category_id:
                    flash('Category ID is required', 'error')
                    return redirect(url_for('manage_categories'))
                
                category = Category.query.get_or_404(category_id)
                
                # Verify ownership
                if category.user_id != current_user.id:
                    flash('Unauthorized access', 'error')
                    return redirect(url_for('manage_categories'))
                
                # Check if category has associated transactions
                if category.transactions:
                    flash('Cannot delete category with associated transactions', 'error')
                    return redirect(url_for('manage_categories'))
                
                db.session.delete(category)
                db.session.commit()
                flash('Category deleted successfully!', 'success')
            
            return redirect(url_for('manage_categories'))
        
        # GET request - display categories
        categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.type, Category.name).all()
        return render_template('manage_categories.html', categories=categories)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in manage_categories: {str(e)}")
        flash('An error occurred while managing categories', 'error')
        return redirect(url_for('home'))

@app.route('/add_recurring_transaction', methods=['POST'])
@login_required
def add_recurring_transaction():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['category_id', 'amount', 'description', 'frequency', 'start_date']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field.replace("_", " ").title()} is required'}), 400

        # Parse and validate the date
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
            
            # Get the first day of the previous month
            today = datetime.now()
            first_day_last_month = datetime(today.year, today.month - 1 if today.month > 1 else 12, 1)
            if today.month == 1:
                first_day_last_month = first_day_last_month.replace(year=today.year - 1)
            
            # Validate date is not in the future
            if start_date > datetime.now():
                return jsonify({'error': 'Start date cannot be in the future'}), 400
                
            # Validate date is not too far in the past (optional)
            max_past_date = datetime.now() - timedelta(days=365 * 2)  # 2 years ago
            if start_date < max_past_date:
                return jsonify({'error': 'Start date cannot be more than 2 years in the past'}), 400
                
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
        
        # Create new recurring transaction
        recurring = RecurringTransaction(
            user_id=current_user.id,
            type='expense',
            category_id=int(data['category_id']),
            amount=float(data['amount']),
            description=data['description'],
            frequency=data['frequency'],
            start_date=start_date,
            is_active=True
        )
        
        db.session.add(recurring)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Recurring transaction added successfully'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding recurring transaction: {str(e)}")
        return jsonify({'error': f'Error adding recurring transaction: {str(e)}'}), 500

@app.route('/get_recurring_transaction/<int:id>')
@login_required
def get_recurring_transaction(id):
    try:
        # Ensure user has default categories
        if not ensure_user_has_categories(current_user.id):
            return jsonify({'error': 'Error creating default categories'}), 500

        recurring = RecurringTransaction.query.filter_by(
            id=id,
            user_id=current_user.id
        ).first_or_404()
        
        return jsonify({
            'id': recurring.id,
            'type': recurring.type,
            'category_id': recurring.category_id,
            'amount': recurring.amount,
            'description': recurring.description,
            'frequency': recurring.frequency,
            'next_date': recurring.next_date.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting recurring transaction: {str(e)}')
        return jsonify({'error': 'Error loading recurring transaction details'}), 500

@app.route('/edit_recurring_transaction/<int:id>', methods=['POST'])
@login_required
def edit_recurring_transaction(id):
    try:
        # Ensure user has default categories
        if not ensure_user_has_categories(current_user.id):
            return jsonify({'error': 'Error creating default categories'}), 500

        recurring = RecurringTransaction.query.filter_by(
            id=id,
            user_id=current_user.id
        ).first_or_404()
        
        data = request.get_json()
        
        # Validate category belongs to user
        category = Category.query.filter_by(
            id=int(data['category_id']),
            user_id=current_user.id
        ).first()
        
        if not category:
            return jsonify({'error': 'Invalid category'}), 400

        # Update fields
        recurring.type = data['type'].lower()  # Ensure lowercase
        recurring.category_id = category.id
        recurring.amount = float(data['amount'])
        recurring.description = data['description']
        recurring.frequency = data['frequency']
        recurring.next_date = datetime.strptime(data['next_date'], '%Y-%m-%d').date()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Recurring transaction updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating recurring transaction: {str(e)}')
        return jsonify({'error': 'Error updating recurring transaction'}), 500

@app.route('/delete_recurring_transaction/<int:id>', methods=['POST'])
@login_required
def delete_recurring_transaction(id):
    try:
        recurring = RecurringTransaction.query.filter_by(
            id=id,
            user_id=current_user.id
        ).first_or_404()
        
        db.session.delete(recurring)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Recurring transaction deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting recurring transaction: {str(e)}')
        return jsonify({'error': 'Error deleting recurring transaction'}), 500

@app.route('/budget_goals')
@login_required
def budget_goals():
    try:
        # Get expense categories
        categories = Category.query.filter_by(
            user_id=current_user.id,
            type='expense'
        ).order_by(Category.name).all()

        # Get recurring transactions
        recurring_transactions = RecurringTransaction.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(RecurringTransaction.start_date).all()

        return render_template('budget_goals.html',
                             categories=categories,
                             recurring_transactions=recurring_transactions,
                             today=datetime.now(),
                             timedelta=timedelta)

    except Exception as e:
        current_app.logger.error(f"Error in budget_goals: {str(e)}")
        flash('Error loading budget goals', 'danger')
        return redirect(url_for('home'))

@app.route('/account_settings', methods=['GET', 'POST'])
@login_required
def account_settings():
    try:
        if request.method == 'POST':
            if 'file' in request.files:  
                file = request.files['file']
                if file.filename == '':
                    flash('No file selected', 'error')
                    return redirect(url_for('account_settings'))
                
                if not file.filename.endswith('.csv'):
                    flash('Only CSV files are allowed', 'error')
                    return redirect(url_for('account_settings'))
                
                try:
                    # Read CSV file
                    df = pd.read_csv(file, encoding='utf-8')
                    
                    # Validate CSV structure
                    required_columns = ['date', 'amount', 'type', 'category', 'description']
                    if not all(col in df.columns for col in required_columns):
                        flash('Invalid CSV format. Required columns: date, amount, type, category, description', 'error')
                        return redirect(url_for('account_settings'))
                    
                    success_count = 0
                    error_count = 0
                    
                    for _, row in df.iterrows():
                        try:
                            # Convert date string to datetime
                            transaction_date = datetime.strptime(str(row['date']), '%Y-%m-%d')
                            
                            # Get or create category
                            category_name = str(row['category']).strip()
                            transaction_type = str(row['type']).lower()
                            
                            # Find existing category
                            category = Category.query.filter_by(
                                name=category_name,
                                user_id=current_user.id
                            ).first()
                            
                            # Create new category if it doesn't exist
                            if not category:
                                category = Category(
                                    name=category_name,
                                    type=transaction_type,
                                    user_id=current_user.id,
                                    description=f'Imported category - {category_name}'
                                )
                                db.session.add(category)
                                db.session.flush()  # Flush to get the category ID
                            
                            # Create transaction with category ID (not name)
                            transaction = Transaction(
                                date=transaction_date,
                                amount=float(row['amount']),
                                description=str(row['description']),
                                type=transaction_type,
                                category_id=category.id,  # Use category.id instead of category.name
                                user_id=current_user.id
                            )
                            
                            db.session.add(transaction)
                            success_count += 1
                            
                        except Exception as row_error:
                            error_count += 1
                            current_app.logger.error(f"Error processing row: {row_error}")
                            continue
                    
                    db.session.commit()
                    flash(f'Successfully imported {success_count} transactions. {error_count} errors.', 
                          'success' if error_count == 0 else 'warning')
                    
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Error processing CSV: {str(e)}")
                    flash('Error processing CSV file', 'error')

        # Get statistics for display
        stats = {
            'total_transactions': Transaction.query.filter_by(user_id=current_user.id).count(),
            'total_categories': Category.query.filter_by(user_id=current_user.id).count(),
            'total_budget_goals': Category.query.filter(
                Category.user_id == current_user.id,
                Category.budget_limit > 0
            ).count()
        }

        return render_template('account_settings.html', user=current_user, stats=stats)

    except Exception as e:
        current_app.logger.error(f"Error in account settings: {str(e)}")
        flash('An error occurred while loading settings', 'error')
        return redirect(url_for('home'))

@app.route('/export_transactions_csv')
@login_required
def export_transactions_csv():
    try:
        # Get all transactions for the user
        transactions = Transaction.query.filter_by(user_id=current_user.id).all()
        
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['date', 'amount', 'type', 'category', 'description'])
        
        # Write transactions
        for transaction in transactions:
            writer.writerow([
                transaction.date.strftime('%Y-%m-%d'),
                transaction.amount,
                transaction.type,
                transaction.category.name,
                transaction.description
            ])
        
        # Create response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=transactions.csv'
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"Error exporting CSV: {str(e)}")
        flash('Error exporting transactions', 'error')
        return redirect(url_for('account_settings'))

@app.route('/reset_data', methods=['POST'])
@login_required
def reset_data():
    try:
        # Delete all transactions for the user
        Transaction.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        flash('All transaction data has been reset', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resetting data: {str(e)}")
        flash('Error resetting data', 'error')
    return redirect(url_for('account_settings'))

@app.route('/expense_analysis')
@login_required
def expense_analysis():
    try:
        app.logger.debug("Starting expense analysis")
        
        # Get date range (default to current month)
        today = datetime.today()
        start_date = datetime(today.year, today.month, 1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_date = datetime(today.year, today.month, last_day, 23, 59, 59)

        # Get transactions for the period
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= start_date,
            Transaction.date <= end_date
        ).all()

        # Calculate totals
        total_income = sum(t.amount for t in transactions if t.type == 'income')
        total_expenses = sum(t.amount for t in transactions if t.type == 'expense')
        net_income = total_income - total_expenses
        
        app.logger.debug(f"Total income: {total_income}, Total expenses: {total_expenses}")

        # Get previous month's data for trends
        prev_month_start = start_date - timedelta(days=start_date.day)
        prev_month_end = start_date - timedelta(days=1)
        prev_transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= prev_month_start,
            Transaction.date <= prev_month_end
        ).all()

        # Calculate previous month totals
        prev_income = sum(t.amount for t in prev_transactions if t.type == 'income')
        prev_expenses = sum(t.amount for t in prev_transactions if t.type == 'expense')

        # Calculate trends (percentage change)
        if prev_income > 0:
            income_trend = ((total_income - prev_income) / prev_income) * 100
        else:
            income_trend = 0

        if prev_expenses > 0:
            expense_trend = ((total_expenses - prev_expenses) / prev_expenses) * 100
        else:
            expense_trend = 0

        # Calculate savings rate
        savings_rate = (net_income / total_income * 100) if total_income > 0 else 0

        # Get category data
        categories_data = {}
        for transaction in transactions:
            category_name = transaction.category.name
            if transaction.type == 'expense':
                if category_name not in categories_data:
                    categories_data[category_name] = 0
                categories_data[category_name] += transaction.amount

        # Get budget data
        budget_goals = BudgetGoal.query.filter_by(user_id=current_user.id).all()
        budget_comparison = []
        total_budget = 0
        total_spent = 0

        for goal in budget_goals:
            spent = sum(t.amount for t in transactions 
                       if t.category_id == goal.category_id and t.type == 'expense')
            
            total_budget += float(goal.amount)
            total_spent += spent
            
            percentage = (spent / goal.amount * 100) if goal.amount > 0 else 0

            budget_comparison.append({
                'category': goal.category.name,
                'budget': float(goal.amount),
                'spent': float(spent),
                'remaining': float(goal.amount - spent),
                'percentage': round(percentage, 1)
            })

        # Calculate budget metrics
        budget_usage = (total_spent / total_budget * 100) if total_budget > 0 else 0
        budget_remaining = total_budget - total_spent

        # Get monthly trends
        monthly_trends = []
        current_date = today
        
        for i in range(12):
            month_start = datetime(current_date.year, current_date.month, 1)
            last_day = calendar.monthrange(current_date.year, current_date.month)[1]
            month_end = datetime(current_date.year, current_date.month, last_day, 23, 59, 59)
            
            month_transactions = Transaction.query.filter(
                Transaction.user_id == current_user.id,
                Transaction.date >= month_start,
                Transaction.date <= month_end
            ).all()

            month_income = sum(t.amount for t in month_transactions if t.type == 'income')
            month_expenses = sum(t.amount for t in month_transactions if t.type == 'expense')

            monthly_trends.append({
                'month': month_start.strftime('%B %Y'),
                'income': float(month_income),
                'expenses': float(month_expenses),
                'net': float(month_income - month_expenses)
            })

            current_date = (month_start - timedelta(days=1))

        monthly_trends.reverse()

        # Generate colors for categories
        category_colors = [f'hsl({(i * 360) / len(categories_data)}, 70%, 50%)'
                         for i in range(len(categories_data))]

        # Prepare chart data
        chart_data = {
            'expenseLabels': list(categories_data.keys()),
            'expenseData': list(categories_data.values()),
            'trendLabels': [item['month'] for item in monthly_trends],
            'incomeValues': [item['income'] for item in monthly_trends],
            'expenseValues': [item['expenses'] for item in monthly_trends],
            'categoryColors': category_colors
        }

        app.logger.debug("Rendering expense analysis template")
        return render_template('expense_analysis.html',
                             total_income=float(total_income),
                             total_expenses=float(total_expenses),
                             net_income=float(net_income),
                             income_trend=round(income_trend, 1),
                             expense_trend=round(expense_trend, 1),
                             savings_rate=round(savings_rate, 1),
                             budget_usage=round(budget_usage, 1),
                             budget_remaining=float(budget_remaining),
                             monthly_trends=monthly_trends,
                             budget_comparison=budget_comparison,
                             chart_data=chart_data)

    except Exception as e:
        app.logger.error(f"Error in expense analysis: {str(e)}")
        flash('An error occurred while analyzing expenses', 'error')
        return redirect(url_for('home'))


@app.route('/api/expense_data')
@login_required
def get_expense_data():
    try:
        time_range = request.args.get('range', 'current')
        today = datetime.today()
        
        # Calculate date range based on selection
        if time_range == 'current':
            start_date = datetime(today.year, today.month, 1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_date = datetime(today.year, today.month, last_day, 23, 59, 59)
        elif time_range == 'last':
            first_of_month = datetime(today.year, today.month, 1)
            start_date = first_of_month - timedelta(days=first_of_month.day)
            end_date = first_of_month - timedelta(seconds=1)
        elif time_range == '3months':
            start_date = today - timedelta(days=90)
            end_date = today
        elif time_range == '6months':
            start_date = today - timedelta(days=180)
            end_date = today
        else:  # year
            start_date = today - timedelta(days=365)
            end_date = today

        # Get transactions for the period
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= start_date,
            Transaction.date <= end_date
        ).all()

        # Calculate updated metrics
        # (Similar calculations as in expense_analysis route)
        
        return jsonify({
            'success': True,
            'data': {
                # Return updated data for charts and summaries
            }
        })

    except Exception as e:
        app.logger.error(f"Error fetching expense data: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch expense data'
        })
@app.route('/income_analysis')
def income_analysis():
    incomes = Transaction.query.filter_by(type='Income').all()
    if not incomes:
        flash('No transactions available for analysis.', 'info')
        return render_template('income_analysis.html')
    
    # Prepare data for charts
    income_by_category = {}
    for income in incomes:
        if income.category in income_by_category:
            income_by_category[income.category] += income.amount
        else:
            income_by_category[income.category] = income.amount
    
    # Create pie chart
    fig_pie = px.pie(
        values=list(income_by_category.values()),
        names=list(income_by_category.keys()),
        title='Income by Category'
    )
    
    # Create time series chart
    incomes_by_date = {}
    for income in incomes:
        month = income.date.strftime('%Y-%m')
        if month in incomes_by_date:
            incomes_by_date[month] += income.amount
        else:
            incomes_by_date[month] = income.amount
    
    sorted_dates = sorted(incomes_by_date.keys())
    fig_line = px.line(
        x=sorted_dates,
        y=[incomes_by_date[date] for date in sorted_dates],
        title='Monthly Income Over Time'
    )
    
    charts = {
        'pie': json.dumps(fig_pie, cls=plotly.utils.PlotlyJSONEncoder),
        'line': json.dumps(fig_line, cls=plotly.utils.PlotlyJSONEncoder)
    }
    
    return render_template('income_analysis.html',
                         charts=charts,
                         income_data=income_by_category)
@app.route('/transaction/<int:transaction_id>/edit', methods=['POST'])
@login_required
def edit_transaction_submit(transaction_id):
    try:
        transaction = Transaction.query.filter_by(
            id=transaction_id,
            user_id=current_user.id
        ).first_or_404()
        
        # Update transaction
        transaction.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        transaction.amount = float(request.form['amount'])
        transaction.description = request.form['description']
        transaction.type = request.form['type']
        transaction.category_id = int(request.form['category_id'])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Transaction updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating transaction: {str(e)}')
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/get_transaction/<int:transaction_id>')
@login_required
def get_transaction(transaction_id):
    try:
        transaction = Transaction.query.filter_by(
            id=transaction_id,
            user_id=current_user.id
        ).first_or_404()
        
        return jsonify({
            'id': transaction.id,
            'date': transaction.date.strftime('%Y-%m-%d'),
            'amount': transaction.amount,
            'description': transaction.description,
            'type': transaction.type,
            'category_id': transaction.category_id
        })
        
    except Exception as e:
        app.logger.error(f'Error getting transaction: {str(e)}')
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

    
@app.route('/add_budget_goal', methods=['POST'])
def add_budget_goal():
    try:
        data = request.get_json()
        
        # Validate input
        if not all(key in data for key in ['category_id', 'amount', 'period']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check if goal already exists
        existing_goal = BudgetGoal.query.filter_by(
            category_id=data['category_id'],
            user_id=current_user.id 
        ).first()
        
        if existing_goal:
            return jsonify({'error': 'Budget goal already exists for this category'}), 400
        
        # Create new goal
        new_goal = BudgetGoal(
            category_id=data['category_id'],
            amount=float(data['amount']),
            period=data['period'],
            user_id=current_user.id  # Add user_id when creating new goal
        )
        
        db.session.add(new_goal)
        db.session.commit()
        
        return jsonify({'message': 'Budget goal created successfully'}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error adding budget goal: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/edit_budget_goal/<int:goal_id>', methods=['POST'])
def edit_budget_goal(goal_id):
    try:
        goal = BudgetGoal.query.filter_by(
            id=goal_id,
            user_id=current_user.id
        ).first_or_404()
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Update goal
        if 'amount' in data:
            goal.amount = float(data['amount'])
        if 'period' in data:
            goal.period = data['period']
            
        db.session.commit()
        
        return jsonify({
            'message': 'Budget goal updated successfully',
            'goal': {
                'id': goal.id,
                'amount': goal.amount,
                'period': goal.period
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating budget goal {goal_id}: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/delete_budget_goal/<int:goal_id>', methods=['POST'])
def delete_budget_goal(goal_id):
    try:
        # Add user check to ensure users can only delete their own goals
        goal = BudgetGoal.query.filter_by(
            id=goal_id,
            user_id=current_user.id
        ).first_or_404()
        
        db.session.delete(goal)
        db.session.commit()
        return jsonify({'message': 'Budget goal deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error deleting budget goal {goal_id}: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    try:
        # Get form data
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        
        # Validate input
        if not all([first_name, last_name, email]):
            flash('All fields are required', 'error')
            return redirect(url_for('account_settings'))
        
        # Update user information
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.email = email
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating profile: {str(e)}")
        flash('An error occurred while updating profile', 'error')
    
    return redirect(url_for('account_settings'))

@app.route('/update_password', methods=['POST'])
@login_required
def update_password():
    try:
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate input
        if not all([current_password, new_password, confirm_password]):
            flash('All password fields are required', 'error')
            return redirect(url_for('account_settings'))
        
        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return redirect(url_for('account_settings'))
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
            return redirect(url_for('account_settings'))
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        flash('Password updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating password: {str(e)}")
        flash('An error occurred while updating password', 'error')
    
    return redirect(url_for('account_settings'))

@app.route('/auth/google')
def google_login():
    # Generate a random state
    session['google_oauth_state'] = secrets.token_urlsafe(16)
    return google.authorize_redirect(
        redirect_uri=url_for('google_authorize', _external=True),
        state=session['google_oauth_state']
    )
@app.route('/auth/google/authorize')
def google_authorize():
    try:
        session.pop('_flashes', None)

        # Verify state matches
        if request.args.get('state') != session.get('google_oauth_state'):
            flash('Authentication failed: state mismatch', 'error')
            return redirect(url_for('auth_login'))
            
        token = google.authorize_access_token()
        resp = google.get('https://www.googleapis.com/oauth2/v3/userinfo')
        user_info = resp.json()
        
        # Clear the state after use
        session.pop('google_oauth_state', None)
        
        current_app.logger.debug(f"Google user info received: {user_info}")

        # Check if user exists
        user = User.query.filter_by(email=user_info['email']).first()
        if not user:
            # Generate username from email
            username = user_info['email'].split('@')[0]
            # Make sure username is unique
            base_username = username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{counter}"
                counter += 1
                
            user = User(
                email=user_info['email'],
                username=username,  # Add generated username
                first_name=user_info.get('given_name'),
                last_name=user_info.get('family_name'),
                google_id=user_info['sub'],
                is_google_user=True
            )
            db.session.add(user)
            db.session.commit()
            
      # Ensure categories exist for both new and existing users
        if ensure_user_has_categories(user.id):
            login_user(user)
            flash('Login successful!', 'success')
        else:
            flash('Login successful but there was an error creating categories', 'warning')
            login_user(user)

        return redirect(url_for('home'))

    except Exception as e:
        current_app.logger.error(f"Error during Google login: {str(e)}", exc_info=True)
        flash('An error occurred during Google login', 'error')
        return redirect(url_for('auth_login'))

@app.route('/login', methods=['GET', 'POST'])
def auth_login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and check_user_password(user, form.password.data):  # Using helper instead of method
            login_user(user, remember=form.remember.data)
            
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('home'))
        flash('Invalid email or password', 'error')
    return render_template('auth/login.html', form=form)

@app.route('/logout')
@login_required
def auth_logout():
    logout_user()
    return redirect(url_for('auth_login'))

@app.route('/register', methods=['GET', 'POST'])
def auth_register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower(),
            first_name=form.first_name.data,
            last_name=form.last_name.data
        )
        set_user_password(user, form.password.data)  # Using helper instead of method
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth_login'))
    return render_template('auth/register.html', form=form)

@app.route('/forgot-password', methods=['GET', 'POST'])
def auth_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate reset token
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            
            try:
                db.session.commit()
                
                # Send reset email
                reset_url = url_for('auth_reset_password', token=token, _external=True)
                msg = Message('Password Reset Request',
                            sender=app.config['MAIL_DEFAULT_SENDER'],
                            recipients=[user.email])
                msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email and no changes will be made.

This link will expire in 1 hour.
'''
                mail.send(msg)
                flash('An email has been sent with instructions to reset your password.', 'success')
                
            except Exception as e:
                flash('An error occurred sending the reset email. Please try again.', 'error')
                app.logger.error(f'Password reset email error: {str(e)}')
                
        else:
            # Don't reveal if email exists or not for security
            flash('If an account exists with that email, a password reset link will be sent.', 'info')
        
        return redirect(url_for('auth_login'))
        
    return render_template('auth/forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def auth_reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    
    if user is None or (user.reset_token_expiry and 
                       user.reset_token_expiry < datetime.utcnow()):
        flash('Invalid or expired reset link', 'error')
        return redirect(url_for('auth_forgot_password'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            user.set_password(password)
            user.reset_token = None
            user.reset_token_expiry = None
            
            try:
                db.session.commit()
                flash('Your password has been updated!', 'success')
                return redirect(url_for('auth_login'))
            except Exception as e:
                flash('An error occurred. Please try again.', 'error')
                app.logger.error(f'Password reset error: {str(e)}')
                
    return render_template('auth/reset_password.html')

@app.route('/delete_user', methods=['POST'])
@login_required
def delete_user():
    try:
        user_id = current_user.id
        session.pop('_flashes', None)

        logout_user()
        
        user = User.query.get(user_id)
        if user:
            # Delete in correct order based on foreign key dependencies
            # 1. First delete budget goals
            BudgetGoal.query.filter_by(user_id=user_id).delete()
            
            # 2. Delete transactions
            Transaction.query.filter_by(user_id=user_id).delete()
            
            # 3. Delete recurring transactions
            RecurringTransaction.query.filter_by(user_id=user_id).delete()
            
            # 4. Delete categories (now safe because budget_goals are gone)
            Category.query.filter_by(user_id=user_id).delete()
            
            # 5. Finally delete the user
            db.session.delete(user)
            db.session.commit()
            
            flash('Your account has been successfully deleted', 'success')
            return redirect(url_for('home'))
        else:
            flash('User not found', 'error')
            return redirect(url_for('home'))
            
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting user: {str(e)}")
        flash('An error occurred while deleting your account', 'error')
        return redirect(url_for('account_settings'))

    return redirect(url_for('home'))