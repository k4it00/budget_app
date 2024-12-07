from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, DateField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from datetime import datetime

class TransactionForm(FlaskForm):
    