import asyncio
from datetime import datetime, timedelta, timezone
from loguru import logger
from sqlalchemy import select, func

from tasks.celery_app import celery_app


def _run(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.run(coro)


# ─── Daily report ─────────────────────────────────────────────

@celery_app.task(name="tasks.tasks.generate_daily_report")
def generate_daily_report():
    """Generate and email a daily entry summary for every active facility."""
    _run(_generate_daily_report())


async def _generate_daily_report():
    from core.database import AsyncSessionLocal
    from core.config import settings
    from models.models import EntryLog, Facility

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = datetime.combine(yesterday, datetime.max.time()).replace(tzinfo=timezone.utc)

    async with AsyncSessionLocal() as db:
        facilities = (
            await db.execute(select(Facility).where(Facility.is_active.is_(True)))
        ).scalars().all()

        for facility in facilities:
            rows = (
                await db.execute(
                    select(EntryLog.decision, func.count(EntryLog.id).label("cnt"))
                    .where(EntryLog.facility_id == facility.id)
                    .where(EntryLog.entry_time >= start)
                    .where(EntryLog.entry_time <= end)
                    .group_by(EntryLog.decision)
                )
            ).all()

            total = sum(r.cnt for r in rows)
            allowed = next((r.cnt for r in rows if r.decision == "allowed"), 0)
            denied = next((r.cnt for r in rows if r.decision == "denied"), 0)
            alerted = next((r.cnt for r in rows if r.decision == "allowed_with_alert"), 0)

            report = (
                f"Daily Access Report — {facility.name}\n"
                f"Date: {yesterday}\n"
                f"Total scans : {total}\n"
                f"Allowed     : {allowed}\n"
                f"Denied      : {denied}\n"
                f"Alerts      : {alerted}"
            )
            logger.info(f"[report] {facility.name}: total={total} allowed={allowed} denied={denied}")

            if settings.sendgrid_api_key and settings.alert_email_from:
                await _send_report_email(facility.name, report, settings)


async def _send_report_email(facility_name: str, body: str, settings) -> None:
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        sg.send(Mail(
            from_email=settings.alert_email_from,
            to_emails=settings.alert_email_from,
            subject=f"Daily Access Report — {facility_name}",
            plain_text_content=body,
        ))
    except Exception as e:
        logger.error(f"Report email failed for {facility_name}: {e}")


# ─── Capture cleanup ──────────────────────────────────────────

@celery_app.task(name="tasks.tasks.cleanup_old_captures")
def cleanup_old_captures(days: int = 90):
    """Delete R2 capture objects older than N days."""
    _run(_cleanup_old_captures(days))


async def _cleanup_old_captures(days: int) -> None:
    from core.config import settings

    if not all([settings.r2_account_id, settings.r2_access_key, settings.r2_secret_key]):
        logger.info("R2 not configured — skipping capture cleanup")
        return

    try:
        import boto3

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key,
            aws_secret_access_key=settings.r2_secret_key,
            region_name="auto",
        )

        paginator = s3.get_paginator("list_objects_v2")
        deleted = 0

        for page in paginator.paginate(Bucket=settings.r2_bucket_name, Prefix="captures/"):
            stale = [
                {"Key": obj["Key"]}
                for obj in page.get("Contents", [])
                if obj["LastModified"] < cutoff
            ]
            if stale:
                s3.delete_objects(Bucket=settings.r2_bucket_name, Delete={"Objects": stale})
                deleted += len(stale)

        logger.info(f"Capture cleanup: deleted {deleted} objects older than {days}d")
    except Exception as e:
        logger.error(f"Capture cleanup failed: {e}")


# ─── Alert dispatch ───────────────────────────────────────────

@celery_app.task(
    name="tasks.tasks.send_alert_async",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def send_alert_async(self, facility_name: str, message: str) -> None:
    """Fire-and-forget alert — decouples SMS/email from the scan response path."""
    try:
        from core.config import settings

        if settings.twilio_account_sid:
            from twilio.rest import Client
            Client(settings.twilio_account_sid, settings.twilio_auth_token).messages.create(
                body=message,
                from_=settings.twilio_from_number,
                to=settings.alert_sms_to or "",
            )

        if settings.sendgrid_api_key:
            import sendgrid
            from sendgrid.helpers.mail import Mail
            sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
            sg.send(Mail(
                from_email=settings.alert_email_from,
                to_emails=settings.alert_email_from,
                subject=f"[{facility_name}] Access Alert",
                plain_text_content=message,
            ))
    except Exception as exc:
        raise self.retry(exc=exc)
