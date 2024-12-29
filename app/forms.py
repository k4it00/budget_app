# app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FloatField, SelectField, DateField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models import User

class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class TransactionForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired(), Length(max=256)])
    date = DateField('Date', validators=[DataRequired()])
    type = SelectField('Type', choices=[
        ('expense', 'Expense'),
        ('income', 'Income')
    ], validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Save Transaction')

class BudgetGoalForm(FlaskForm):
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired()])
    period = SelectField('Period', choices=[
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly')
    ], validators=[DataRequired()])
    recurring = BooleanField('Recurring')
    submit = SubmitField('Save Budget Goal')

class RecurringTransactionForm(FlaskForm):
    description = StringField('Description', validators=[DataRequired(), Length(max=200)])
    amount = FloatField('Amount', validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    type = SelectField('Type', choices=[
        ('expense', 'Expense'),
        ('income', 'Income')
    ], validators=[DataRequired()])
    frequency = SelectField('Frequency', choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly')
    ], validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[])
    submit = SubmitField('Save Recurring Transaction')

class CategoryForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=64)])
    type = SelectField('Type', choices=[
        ('expense', 'Expense'),
        ('income', 'Income')
    ], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Length(max=256)])
    budget_limit = FloatField('Budget Limit')
    submit = SubmitField('Save Category')
