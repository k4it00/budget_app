from app.helpers import ensure_user_has_categories, process_monthly_trends, process_expense_distribution
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
from app.helpers import ensure_user_has_recurring_transactions, process_pending_recurring_transactions, get_all_categories, get_budget_categories, calculate_current_spending, format_currency
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

@app.route("/add_transaction", methods=["GET", "POST"])
@login_required
def add_transaction():
    if request.method == "POST":
        try:
            # Get form data
            type = request.form.get("type")
            amount = float(request.form.get("amount"))
            date = datetime.strptime(request.form.get("date"), "%Y-%m-%d")
            category_id = int(request.form.get("category_id"))
            description = request.form.get("description")

            # Create new transaction
            new_transaction = Transaction(
                type=type,
                amount=amount,
                date=date,
                category_id=category_id,
                description=description,
                user_id=current_user.id
            )

            # Add and commit to database
            db.session.add(new_transaction)
            db.session.commit()

            flash("Transaction added successfully!", "success")
            return jsonify({'success': True}), 200

        except Exception as e:
            app.logger.error(f"Error adding transaction: {e}")
            return jsonify({'success': False, 'error': 'An error occurred'}), 500

    # GET request - show form
    # Get all categories for the current user
    categories = Category.query.filter_by(user_id=current_user.id).all()
    
    # If user has no categories, create default ones
    if not categories:
        default_categories = [
            Category(name="Salary", type="income", user_id=current_user.id),
            Category(name="Business", type="income", user_id=current_user.id),
            Category(name="Investments", type="income", user_id=current_user.id),
            Category(name="Other Income", type="income", user_id=current_user.id),
            Category(name="Food & Dining", type="expense", user_id=current_user.id),
            Category(name="Transportation", type="expense", user_id=current_user.id),
            Category(name="Utilities", type="expense", user_id=current_user.id),
            Category(name="Shopping", type="expense", user_id=current_user.id),
            Category(name="Entertainment", type="expense", user_id=current_user.id),
            Category(name="Healthcare", type="expense", user_id=current_user.id),
            Category(name="Other Expenses", type="expense", user_id=current_user.id),
        ]
        
        try:
            db.session.add_all(default_categories)
            db.session.commit()
            categories = default_categories
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating default categories: {str(e)}", "error")
            categories = []

    return render_template(
        "add_transaction.html", 
        title="Add Transaction",
        categories=categories
    )


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

@app.route('/manage_categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    try:
        if request.method == 'POST':
            action = request.form.get('action')
            logger.info(f"Action received: {action}")
            
            if action == 'add':
                name = request.form.get('name')
                type = request.form.get('type')
                description = request.form.get('description', '')
                logger.info(f"Adding category with name: {name}, type: {type}, description: {description}")
                
                # Validate inputs
                if not name or not type:
                    logger.warning("Name and type are required")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': 'Name and type are required'}), 400
                    flash('Name and type are required', 'error')
                    return redirect(url_for('manage_categories'))
                
                # Check if category already exists for this user
                existing_category = Category.query.filter_by(
                    user_id=current_user.id,
                    name=name,
                    type=type
                ).first()
                
                if existing_category:
                    logger.warning("A category with this name and type already exists")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': 'A category with this name and type already exists'}), 400
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
                logger.info("Category added successfully")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': True, 'message': 'Category added successfully!'}), 200
                flash('Category added successfully!', 'success')
                
            elif action == 'edit':
                category_id = request.form.get('category_id')
                logger.info(f"Editing category with ID: {category_id}")
                if not category_id:
                    logger.warning("Category ID is required")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': 'Category ID is required'}), 400
                    flash('Category ID is required', 'error')
                    return redirect(url_for('manage_categories'))
                
                category = Category.query.get_or_404(category_id)
                
                # Verify ownership
                if category.user_id != current_user.id:
                    logger.warning("Unauthorized access attempt")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': 'Unauthorized access'}), 403
                    flash('Unauthorized access', 'error')
                    return redirect(url_for('manage_categories'))
                
                # Update category
                category.name = request.form.get('name', category.name)
                category.type = request.form.get('type', category.type)
                category.description = request.form.get('description', category.description)
                
                db.session.commit()
                logger.info("Category updated successfully")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': True, 'message': 'Category updated successfully!'}), 200
                flash('Category updated successfully!', 'success')
                
            elif action == 'delete':
                category_id = request.form.get('category_id')
                logger.info(f"Deleting category with ID: {category_id}")
                if not category_id:
                    logger.warning("Category ID is required")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': 'Category ID is required'}), 400
                    flash('Category ID is required', 'error')
                    return redirect(url_for('manage_categories'))
                
                category = Category.query.get_or_404(category_id)
                
                # Verify ownership
                if category.user_id != current_user.id:
                    logger.warning("Unauthorized access attempt")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': 'Unauthorized access'}), 403
                    flash('Unauthorized access', 'error')
                    return redirect(url_for('manage_categories'))
                
                # Check if category has associated transactions
                if category.transactions:
                    logger.warning("Cannot delete category with associated transactions")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': 'Cannot delete category with associated transactions'}), 400
                    flash('Cannot delete category with associated transactions', 'error')
                    return redirect(url_for('manage_categories'))
                
                db.session.delete(category)
                db.session.commit()
                logger.info("Category deleted successfully")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': True, 'message': 'Category deleted successfully!'}), 200
                flash('Category deleted successfully!', 'success')
            
            return redirect(url_for('manage_categories'))
        
        # GET request - display categories
        logger.info("Fetching categories for user")
        categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.type, Category.name).all()
        return render_template('manage_categories.html', categories=categories)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in manage_categories: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'An error occurred while managing categories'}), 500
        flash('An error occurred while managing categories', 'error')
        return redirect(url_for('home'))
@app.route('/add_recurring', methods=['POST'])
@login_required
def add_recurring():
    try:
        data = request.get_json()
        new_recurring = RecurringTransaction(
            user_id=current_user.id,
            name=data['name'],
            type=data['type'],
            amount=float(data['amount']),
            frequency=data['frequency'],
            category_id=data.get('category_id'),
            start_date=datetime.strptime(data['start_date'], '%Y-%m-%d'),
            end_date=datetime.strptime(data['end_date'], '%Y-%m-%d') if data['end_date'] else None,
            next_date=datetime.strptime(data['start_date'], '%Y-%m-%d')
        )
        
        db.session.add(new_recurring)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Recurring transaction added successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding recurring transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/get_recurring/<int:id>')
@login_required
def get_recurring(id):
    try:
        recurring = RecurringTransaction.query.get_or_404(id)
        if recurring.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
            
        return jsonify({
            'success': True,
            'recurring': {
                'id': recurring.id,
                'name': recurring.name,
                'type': recurring.type,
                'amount': recurring.amount,
                'frequency': recurring.frequency,
                'category_id': recurring.category_id,
                'start_date': recurring.start_date.strftime('%Y-%m-%d'),
                'end_date': recurring.end_date.strftime('%Y-%m-%d') if recurring.end_date else None
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error getting recurring transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/update_recurring/<int:id>', methods=['PUT'])
@login_required
def update_recurring(id):
    try:
        recurring = RecurringTransaction.query.get_or_404(id)
        if recurring.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        data = request.get_json()
        recurring.name = data['name']
        recurring.type = data['type']
        recurring.amount = float(data['amount'])
        recurring.frequency = data['frequency']
        recurring.category_id = data.get('category_id')
        recurring.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        recurring.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d') if data['end_date'] else None
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Recurring transaction updated successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating recurring transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/delete_recurring/<int:id>', methods=['DELETE'])
@login_required
def delete_recurring(id):
    try:
        recurring = RecurringTransaction.query.get_or_404(id)
        if recurring.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        db.session.delete(recurring)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Recurring transaction deleted successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting recurring transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/process_recurring', methods=['POST'])
@login_required
def process_recurring():
    try:
        from app.helpers import process_pending_recurring_transactions
        transactions_created = process_pending_recurring_transactions()
        return jsonify({
            'success': True, 
            'message': f'Successfully processed {transactions_created} recurring transaction(s)'
        })
    except Exception as e:
        current_app.logger.error(f"Error processing recurring transactions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    
@app.route('/restore_default_categories', methods=['POST'])
@login_required
def restore_default_categories():
    try:
        default_categories = [
            {'name': 'Salary', 'type': 'income'},  # Note: lowercase type
            {'name': 'Freelance', 'type': 'income'},
            {'name': 'Investments', 'type': 'income'},
            {'name': 'Groceries', 'type': 'expense'},
            {'name': 'Rent', 'type': 'expense'},
            {'name': 'Utilities', 'type': 'expense'},
            {'name': 'Transportation', 'type': 'expense'},
            {'name': 'Entertainment', 'type': 'expense'}
        ]
        
        categories_added = 0
        for cat_data in default_categories:
            # Check if category already exists
            existing_category = Category.query.filter_by(
                user_id=current_user.id,
                name=cat_data['name'],
                type=cat_data['type']
            ).first()
            
            if not existing_category:
                category = Category(
                    name=cat_data['name'],
                    type=cat_data['type'],
                    user_id=current_user.id,
                    description=f"Default {cat_data['type']} category",
                    budget_limit=0.0
                )
                db.session.add(category)
                categories_added += 1
        
        db.session.commit()
        
        message = f"Added {categories_added} default categories" if categories_added > 0 else "All default categories already exist"
        return jsonify({
            'success': True,
            'message': message,
            'categories_added': categories_added
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error restoring default categories: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

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
                            
                            category = Category.query.filter_by(
                                name=category_name,
                                user_id=current_user.id
                            ).first()
                            
                            if not category:
                                category = Category(
                                    name=category_name,
                                    type=transaction_type,
                                    user_id=current_user.id
                                )
                                db.session.add(category)
                                db.session.flush()
                            
                            # Create transaction
                            transaction = Transaction(
                                date=transaction_date,
                                amount=float(row['amount']),
                                description=str(row['description']),
                                type=transaction_type,
                                category_id=category.id,
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

from decimal import Decimal

@app.route('/expense_analysis')
@login_required
def expense_analysis():
    try:
        # Get the date range (default to current month)
        today = datetime.utcnow()
        start_date = today.replace(day=1)
        end_date = today

        # Get regular transactions
        regular_transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= start_date,
            Transaction.date <= end_date
        ).all()

        # Get recurring transactions
        recurring_transactions = RecurringTransaction.query.filter(
            RecurringTransaction.user_id == current_user.id,
            RecurringTransaction.is_active == True  # Only get active recurring transactions
        ).all()

        # Initialize data structures
        monthly_data = {}
        category_totals = {}
        total_income = 0.0
        total_expenses = 0.0

        # Process regular transactions
        for transaction in regular_transactions:
            amount = float(transaction.amount)
            
            # Monthly tracking
            month_key = transaction.date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {'income': 0.0, 'expenses': 0.0}
            
            if transaction.type.lower() == 'income':
                monthly_data[month_key]['income'] += amount
                total_income += amount
            else:  # expense
                monthly_data[month_key]['expenses'] += amount
                total_expenses += amount
                
                # Category tracking for expenses
                if transaction.category:
                    category_name = transaction.category.name
                    if category_name not in category_totals:
                        category_totals[category_name] = 0.0
                    category_totals[category_name] += amount

        # Process recurring transactions for the current month
        current_month = today.strftime('%Y-%m')
        if current_month not in monthly_data:
            monthly_data[current_month] = {'income': 0.0, 'expenses': 0.0}

        for recurring in recurring_transactions:
            amount = float(recurring.amount)
            
            if recurring.type.lower() == 'income':
                monthly_data[current_month]['income'] += amount
                total_income += amount
            else:  # expense
                monthly_data[current_month]['expenses'] += amount
                total_expenses += amount
                
                # Add to category totals
                if recurring.category:
                    category_name = recurring.category.name
                    if category_name not in category_totals:
                        category_totals[category_name] = 0.0
                    category_totals[category_name] += amount

        # Prepare monthly chart data
        sorted_months = sorted(monthly_data.keys())
        monthly_labels = [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in sorted_months]
        monthly_income = [monthly_data[m]['income'] for m in sorted_months]
        monthly_expenses = [monthly_data[m]['expenses'] for m in sorted_months]

        # Sort categories by amount for pie chart
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        expense_labels = [cat[0] for cat in sorted_categories]
        expense_values = [cat[1] for cat in sorted_categories]

        # Calculate summary statistics
        net_savings = total_income - total_expenses
        savings_rate = round((net_savings / total_income * 100) if total_income > 0 else 0, 1)

        # If no data, provide default values
        if not monthly_labels:
            monthly_labels = [today.strftime('%b %Y')]
            monthly_income = [0.0]
            monthly_expenses = [0.0]

        if not expense_labels:
            expense_labels = ['No Expenses']
            expense_values = [0.0]

        # Create chart_data dictionary
        chart_data = {
            'monthly': {
                'labels': monthly_labels,
                'income': monthly_income,
                'expenses': monthly_expenses
            },
            'expenses_by_category': {
                'labels': expense_labels,
                'values': expense_values
            }
        }

        return render_template('expense_analysis.html',
                             chart_data=chart_data,
                             total_income=total_income,
                             total_expenses=total_expenses,
                             net_savings=net_savings,
                             savings_rate=savings_rate)

    except Exception as e:
        current_app.logger.error(f"Error in expense_analysis: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash('An error occurred while loading the expense analysis.', 'danger')
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
@app.route('/set_budget_goals', methods=['GET', 'POST'])
@login_required
def set_budget_goals():
    try:
        if request.method == 'POST':
            # Get form data
            category_id = request.form.get('category')
            amount = request.form.get('amount')
            period = request.form.get('period')
            recurring = request.form.get('recurring', 'false') == 'true'

            # Validate inputs
            if not all([category_id, amount, period]):
                flash('All fields are required', 'error')
                return redirect(url_for('set_budget_goals'))

            try:
                amount = float(amount)
                if amount <= 0:
                    raise ValueError
            except ValueError:
                flash('Amount must be a positive number', 'error')
                return redirect(url_for('set_budget_goals'))

            valid_periods = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
            if period not in valid_periods:
                flash('Invalid period specified', 'error')
                return redirect(url_for('set_budget_goals'))

            # Check if budget goal already exists for this category and period
            existing_goal = BudgetGoal.query.filter_by(
                category_id=category_id,
                period=period,
                user_id=current_user.id
            ).first()

            if existing_goal:
                flash('A budget goal already exists for this category and period', 'error')
                return redirect(url_for('set_budget_goals'))

            # Create new budget goal
            new_goal = BudgetGoal(
                category_id=category_id,
                amount=amount,
                period=period,
                recurring=recurring,
                user_id=current_user.id
            )

            db.session.add(new_goal)
            db.session.commit()
            flash('Budget goal set successfully!', 'success')
            return redirect(url_for('set_budget_goals'))

        # GET request - show the form
        categories = Category.query.filter_by(user_id=current_user.id).all()
        current_app.logger.info(f"Found {len(categories)} categories for user {current_user.id}")

        # Get all budget goals for the current user
        goals = BudgetGoal.query.filter_by(user_id=current_user.id).all()
        current_app.logger.info(f"Found {len(goals)} budget goals for user {current_user.id}")

        # Get recurring transactions
        recurring_transactions = RecurringTransaction.query.filter_by(user_id=current_user.id).all()
        current_app.logger.info(f"Found {len(recurring_transactions)} recurring transactions for user {current_user.id}")

        budget_goals = []
        current_date = datetime.now()

        for goal in goals:
            try:
                # Calculate spent amount based on period
                query = db.session.query(func.sum(Transaction.amount)).\
                    filter(
                        Transaction.category_id == goal.category_id,
                        Transaction.type == 'expense',
                        Transaction.user_id == current_user.id
                    )

                # Adjust date filter based on period
                if goal.period == 'daily':
                    query = query.filter(
                        func.date(Transaction.date) == current_date.date()
                    )
                elif goal.period == 'weekly':
                    start_of_week = current_date - timedelta(days=current_date.weekday())
                    query = query.filter(
                        Transaction.date >= start_of_week,
                        Transaction.date < start_of_week + timedelta(days=7)
                    )
                elif goal.period == 'monthly':
                    query = query.filter(
                        extract('month', Transaction.date) == current_date.month,
                        extract('year', Transaction.date) == current_date.year
                    )
                elif goal.period == 'quarterly':
                    current_quarter = (current_date.month - 1) // 3 + 1
                    quarter_start = datetime(current_date.year, (current_quarter - 1) * 3 + 1, 1)
                    quarter_end = quarter_start + relativedelta(months=3)
                    query = query.filter(
                        Transaction.date >= quarter_start,
                        Transaction.date < quarter_end
                    )
                elif goal.period == 'yearly':
                    query = query.filter(
                        extract('year', Transaction.date) == current_date.year
                    )

                spent = query.scalar() or 0
                percentage = (spent / goal.amount) * 100 if goal.amount > 0 else 0

                category = db.session.get(Category, goal.category_id)
                budget_goals.append({
                    'id': goal.id,
                    'category': category.name,
                    'category_id': category.id,
                    'amount': goal.amount,
                    'spent': spent,
                    'percentage': percentage,
                    'period': goal.period
                })

            except Exception as e:
                current_app.logger.error(f"Error processing budget goal {goal.id}: {str(e)}")
                continue

        return render_template('budget_goals.html',
                             categories=categories,
                             budget_goals=budget_goals,
                             recurring_transactions=recurring_transactions)

    except Exception as e:
        current_app.logger.error(f"Error in set_budget_goals: {str(e)}", exc_info=True)
        flash('An error occurred while loading the page', 'error')
        return redirect(url_for('home'))   
    
@app.route('/budget_goals')
@login_required
def budget_goals():
    try:
        # Ensure user has default categories
        ensure_user_has_categories(current_user.id)
        ensure_user_has_recurring_transactions(current_user.id)
        # Get all data for the user
        goals = BudgetGoal.query.filter_by(user_id=current_user.id).all()
        recurring_transactions = RecurringTransaction.query.filter_by(user_id=current_user.id).all()
        categories = Category.query.filter_by(user_id=current_user.id).all()
        
        # Get user's goals
        goals = BudgetGoal.query.filter_by(user_id=current_user.id).all()

        # Get all transactions grouped by category name
        transactions = db.session.query(
            Category.name,
            Transaction.type,
            db.func.sum(Transaction.amount).label('total_amount')
        ).join(
            Category, Transaction.category_id == Category.id
        ).filter(
            Transaction.user_id == current_user.id
        ).group_by(
            Category.name,
            Transaction.type
        ).all()

        # Create a dictionary of category totals
        transaction_totals = {}
        for t in transactions:
            key = (t.name, t.type)  # Use tuple of name and type as key
            if t.total_amount:
                transaction_totals[key] = t.total_amount

        # Update each goal's current amount and progress
        for goal in goals:
            # Look for transactions matching the goal name and type
            current_amount = transaction_totals.get((goal.name, goal.type), 0)
            goal.current_amount = current_amount
            
            # Calculate progress
            if goal.target_amount > 0:
                goal.progress = round((current_amount / goal.target_amount) * 100, 2)
            else:
                goal.progress = 0

        return render_template('budget_goals.html', 
                             goals=goals, 
                             recurring_transactions=recurring_transactions,
                             categories=categories)
    
    except Exception as e:
        current_app.logger.error(f"Error in budget_goals route: {str(e)}", exc_info=True)
        flash('An error occurred while loading budget goals.', 'error')
        return redirect(url_for('home'))

@app.route('/add_goal', methods=['POST'])
@login_required
def add_goal():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Get the first matching category based on type
        goal_type = data['type'].capitalize()  # Convert 'income' to 'Income' or 'expense' to 'Expense'
        matching_category = Category.query.filter_by(
            user_id=current_user.id,
            type=goal_type
        ).first()

        # If no categories exist, create them
        if not matching_category:
            ensure_user_has_categories(current_user.id)
            matching_category = Category.query.filter_by(
                user_id=current_user.id,
                type=goal_type
            ).first()

        if not matching_category:
            return jsonify({'success': False, 'error': 'No matching category found'}), 400

        new_goal = BudgetGoal(
            user_id=current_user.id,
            name=data['name'],
            type=data['type'],
            target_amount=float(data['target_amount']),
            current_amount=0.0,
            category_id=matching_category.id,  # Use the matching category
            target_date=datetime.strptime(data['target_date'], '%Y-%m-%d'),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(new_goal)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'goal': {
                'id': new_goal.id,
                'name': new_goal.name,
                'type': new_goal.type,
                'target_amount': float(new_goal.target_amount),
                'current_amount': float(new_goal.current_amount),
                'target_date': new_goal.target_date.strftime('%Y-%m-%d')
            }
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating goal: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/update_goal', methods=['POST'])
@login_required
def update_goal():
    try:
        form_data = request.form
        goal_id = form_data.get('goal_id')
        goal = BudgetGoal.query.filter_by(id=goal_id, user_id=current_user.id).first()
        
        if not goal:
            return jsonify({'success': False, 'error': 'Goal not found'}), 404
            
        goal.name = form_data.get('goal_name')
        goal.type = form_data.get('goal_type')
        goal.target_amount = float(form_data.get('target_amount'))
        goal.target_date = datetime.strptime(form_data.get('target_date'), '%Y-%m-%d')

        # Update current amount based on transactions
        current_amount = db.session.query(
            db.func.sum(Transaction.amount)
        ).join(
            Category, Transaction.category_id == Category.id
        ).filter(
            Transaction.user_id == current_user.id,
            Category.name == goal.name,  # Use Category.name instead of Transaction.category_name
            Transaction.type == goal.type
        ).scalar() or 0

        goal.current_amount = current_amount
        goal.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Calculate progress
        progress = round((current_amount / goal.target_amount) * 100, 2) if goal.target_amount > 0 else 0
        
        return jsonify({
            'success': True,
            'goal': {
                'id': goal.id,
                'name': goal.name,
                'type': goal.type,
                'target_amount': goal.target_amount,
                'current_amount': current_amount,
                'target_date': goal.target_date.strftime('%Y-%m-%d'),
                'progress': progress
            }
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating goal: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/edit_goal/<int:goal_id>', methods=['POST'])
@login_required
def edit_goal(goal_id):
    try:
        goal = BudgetGoal.query.filter_by(id=goal_id, user_id=current_user.id).first()
        if not goal:
            return jsonify({'error': 'Goal not found'}), 404

        # Update goal data
        goal.name = request.form.get('goal_name', goal.name)
        goal.target_amount = float(request.form.get('target_amount', goal.target_amount))
        goal.current_amount = float(request.form.get('current_amount', goal.current_amount))
        goal.target_date = datetime.strptime(request.form.get('target_date'), '%Y-%m-%d')

        db.session.commit()

        return jsonify({
            'success': True,
            'goal': {
                'id': goal.id,
                'name': goal.name,
                'target_amount': goal.target_amount,
                'current_amount': goal.current_amount,
                'target_date': goal.target_date.strftime('%Y-%m-%d'),
                'progress': round((goal.current_amount / goal.target_amount) * 100)
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
@app.route('/delete_goal/<int:goal_id>', methods=['DELETE'])
@login_required
def delete_goal(goal_id):
    try:
        goal = BudgetGoal.query.filter_by(id=goal_id, user_id=current_user.id).first()
        
        if not goal:
            return jsonify({'success': False, 'error': 'Goal not found'}), 404
            
        db.session.delete(goal)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting goal: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/get_goal/<int:goal_id>')
@login_required
def get_goal(goal_id):
    try:
        goal = BudgetGoal.query.filter_by(id=goal_id, user_id=current_user.id).first()
        
        if not goal:
            return jsonify({'success': False, 'error': 'Goal not found'}), 404
            
        return jsonify({
            'success': True,
            'goal': {
                'id': goal.id,
                'name': goal.name,
                'target_amount': goal.target_amount,
                'current_amount': goal.current_amount,
                'target_date': goal.target_date.strftime('%Y-%m-%d'),
                'progress': round((goal.current_amount / goal.target_amount) * 100, 2) if goal.target_amount > 0 else 0
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting goal: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/get_chart_data')
@login_required
def get_chart_data():
    time_range = request.args.get('range', 'current')
    
    # Get date range based on selected option
    today = datetime.utcnow()
    if time_range == 'current':
        start_date = today.replace(day=1)
    elif time_range == 'last':
        start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    elif time_range == '3months':
        start_date = (today - timedelta(days=90)).replace(day=1)
    elif time_range == '6months':
        start_date = (today - timedelta(days=180)).replace(day=1)
    else:  # year
        start_date = (today - timedelta(days=365)).replace(day=1)

    # Get transactions for the period
    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date <= today
    ).all()

    # Process data for charts
    monthly_data = process_monthly_trends(transactions)
    distribution_data = process_expense_distribution(transactions)

    return jsonify({
        'monthly_trends': monthly_data,
        'expense_distribution': distribution_data
    })


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
@app.route('/auth/reset-password/<token>', methods=['GET', 'POST'], endpoint='auth_reset_password_with_token') 
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