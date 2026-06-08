import asyncio
from datetime import datetime, timedelta
from loguru import logger
from tasks.celery_app import celery_app


@celery_app.task(name="tasks.tasks.generate_daily_report")
def generate_daily_report():
    """Generate and email daily entry summary for all facilities."""
    logger.info("Generating daily report...")
    # TODO: query entry_logs for yesterday, aggregate by facility,
    # format report, send via SendGrid
    pass


@celery_app.task(name="tasks.tasks.cleanup_old_captures")
def cleanup_old_captures(days: int = 90):
    """Delete captures from R2 older than N days."""
    logger.info(f"Cleaning captures older than {days} days...")
    # TODO: list R2 objects, filter by LastModified, delete old ones
    pass


@celery_app.task(
    name="tasks.tasks.send_alert_async",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def send_alert_async(self, facility_name: str, message: str):
    """Async wrapper so alert sending doesn't block the scan endpoint."""
    try:
        pass  # delegate to alerts service
    except Exception as exc:
        raise self.retry(exc=exc)
