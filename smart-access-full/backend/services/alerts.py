from loguru import logger
from core.config import settings
from models.models import Facility, EntryLog


async def send_alert(facility: Facility, log: EntryLog, reason: str):
    """
    Send SMS + email alert when decision is denied or allowed_with_alert.
    Fires async — never blocks the gate response.
    """
    message = (
        f"[{facility.name}] ACCESS ALERT\n"
        f"Plate: {log.plate_number or 'N/A'}\n"
        f"Driver: {log.driver_name or 'Unknown'}\n"
        f"Decision: {log.decision.upper()}\n"
        f"Reason: {reason}\n"
        f"Time: {log.entry_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    await _send_sms(message)
    await _send_email(facility.name, message, log)
    logger.info(f"Alert sent for log {log.id}")


async def _send_sms(message: str):
    if not settings.twilio_account_sid:
        logger.debug("Twilio not configured, skipping SMS")
        return
    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            body=message,
            from_=settings.twilio_from_number,
            to="+92XXXXXXXXXX",   # TODO: pull from facility settings table
        )
    except Exception as e:
        logger.error(f"SMS send failed: {e}")


async def _send_email(facility_name: str, body: str, log: EntryLog):
    if not settings.sendgrid_api_key:
        logger.debug("SendGrid not configured, skipping email")
        return
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        mail = Mail(
            from_email=settings.alert_email_from,
            to_emails="security@yourdomain.com",  # TODO: per-facility config
            subject=f"[{facility_name}] Access Alert — {log.decision.upper()}",
            plain_text_content=body,
        )
        sg.send(mail)
    except Exception as e:
        logger.error(f"Email send failed: {e}")
