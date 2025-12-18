import httpx
import os
import logging

logger = logging.getLogger(__name__)

async def send_telegram_alert(message: str):
    """
    Sends a message to the configured Telegram Admin Chat.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
    
    if not token or not chat_id:
        logger.warning("Telegram configuration missing. Skipping alert.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=5.0)
            if resp.status_code != 200:
                logger.error(f"Failed to send Telegram alert: {resp.text}")
    except Exception as e:
        logger.error(f"Telegram alert error: {e}")
