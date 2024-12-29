from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.helpers import process_pending_recurring_transactions

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=process_pending_recurring_transactions,
    trigger=CronTrigger(hour=0, minute=0),  # Run at midnight every day
    id='process_recurring_transactions',
    name='Process recurring transactions',
    replace_existing=True
)
scheduler.start()