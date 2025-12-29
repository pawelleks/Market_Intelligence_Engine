import logging
import asyncio

logger = logging.getLogger(__name__)

async def send_email_notification(to_email: str, subject: str, body: str):
    """
    Mock Email Service.
    In production, this would connect to an SMTP server or AWS SES.
    For now, it logs the email to the system logs.
    """
    # Simulate network latency to match typical email sending or token generation overhead
    # This helps in masking timing side-channels to some extent.
    await asyncio.sleep(0.1) 
    
    logger.info("="*60)
    logger.info(f"📧 [MOCK EMAIL] To: {to_email}")
    logger.info(f"Subject: {subject}")
    logger.info(f"Body: {body}")
    logger.info("="*60)
    
    return True
