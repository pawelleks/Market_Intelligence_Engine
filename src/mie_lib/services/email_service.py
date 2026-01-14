from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Initialize SendGrid client
# Initialize SendGrid client
# In production, ensure SENDGRID_API_KEY is set in environment
api_key = os.getenv('SENDGRID_API_KEY')
if api_key:
    try:
        sg = SendGridAPIClient(api_key)
    except Exception as e:
        logger.error(f"Failed to init SendGrid: {e}")
        sg = None
else:
    logger.warning("SENDGRID_API_KEY not found. Email service disabled.")
    sg = None

FROM_EMAIL = os.getenv('SENDGRID_FROM_EMAIL', 'noreply@blindmonkey.io')
FROM_NAME = os.getenv('SENDGRID_FROM_NAME', 'BlindMonkey.io')

def send_email(
    to_email: str, 
    subject: str, 
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """Send email via SendGrid (Synchronous)."""
    if not sg:
        logger.warning("SendGrid client not initialized. Email not sent.")
        return False
        
    if not os.getenv('SENDGRID_API_KEY'):
        logger.warning("SENDGRID_API_KEY not set. Email not sent.")
        return False
        
    message = Mail(
        from_email=(FROM_EMAIL, FROM_NAME),
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
        plain_text_content=text_content
    )
    
    try:
        response = sg.send(message)
        logger.info(f"✅ Email sent to {to_email}: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"❌ Email error for {to_email}: {e}")
        return False

def send_access_request_received(to_email: str, name: str) -> bool:
    """Send confirmation that access request was received."""
    subject = "Access Request Received - BlindMonkey.io"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Access Request Received</h2>
        
        <p>Hi {name},</p>
        
        <p>Thanks for requesting access to BlindMonkey.io!</p>
        
        <p>Your request is being reviewed. You'll receive another email once 
        your access is approved (usually within 24 hours).</p>
        
        <p>In the meantime, feel free to reply to this email with any questions.</p>
        
        <p>Best,<br>
        Pawel<br>
        <a href="https://blindmonkey.io">BlindMonkey.io</a></p>
    </body>
    </html>
    """
    
    text = f"""
    Access Request Received
    
    Hi {name},
    
    Thanks for requesting access to BlindMonkey.io!
    
    Your request is being reviewed. You'll receive another email once 
    your access is approved (usually within 24 hours).
    
    Best,
    Pawel
    BlindMonkey.io
    """
    
    return send_email(to_email, subject, html, text)

def send_access_approved(to_email: str, name: str) -> bool:
    """Send notification that access was approved."""
    subject = "Access Approved - Welcome to BlindMonkey.io! 🎉"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #22c55e;">Access Approved - Welcome! 🎉</h2>
        
        <p>Hi {name},</p>
        
        <p><strong>Great news!</strong> Your access to BlindMonkey.io has been approved.</p>
        
        <p style="margin: 20px 0;">
            <a href="https://blindmonkey.io" 
               style="background: #3b82f6; color: white; padding: 12px 24px; 
                      text-decoration: none; border-radius: 6px; display: inline-block;">
                → Login Now
            </a>
        </p>
        
        <h3>What's Inside:</h3>
        <ul>
            <li>9 Economic Models with 67 years of historical data</li>
            <li>Prediction Analysis Framework</li>
            <li>Recession signal tracking and analysis</li>
            <li>Market performance insights</li>
            <li>Business cycle monitoring</li>
        </ul>
        
        <p style="background: #fef3c7; padding: 12px; border-left: 4px solid #f59e0b;">
            <strong>Remember:</strong> This is educational content only, not financial advice.
        </p>
        
        <p>Questions? Just reply to this email anytime.</p>
        
        <p>Looking forward to your feedback!</p>
        
        <p>Best,<br>
        Pawel<br>
        <a href="https://blindmonkey.io">BlindMonkey.io</a></p>
    </body>
    </html>
    """
    
    text = f"""
    Access Approved - Welcome to BlindMonkey.io!
    
    Hi {name},
    
    Great news! Your access to BlindMonkey.io has been approved.
    
    → Login now: https://blindmonkey.io
    
    What's Inside:
    • 9 Economic Models with 67 years of data
    • Prediction Analysis Framework
    • Recession signal tracking
    • Market analysis tools
    
    Remember: This is educational content only, not financial advice.
    
    Questions? Just reply anytime.
    
    Best,
    Pawel
    BlindMonkey.io
    """
    
    return send_email(to_email, subject, html, text)

def send_account_deleted(to_email: str, name: str) -> bool:
    """Send confirmation of account deletion."""
    subject = "Account Deleted - BlindMonkey.io"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Account Deleted</h2>
        
        <p>Hi {name},</p>
        
        <p>Your BlindMonkey.io account has been permanently deleted as requested.</p>
        
        <p>All your data has been removed from our systems.</p>
        
        <p>If you change your mind, you're welcome to create a new account anytime.</p>
        
        <p>Thanks for trying BlindMonkey.io!</p>
        
        <p>Best,<br>
        Pawel</p>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html)

# Generic async adapter if needed for compatibility with old calls
async def send_email_notification(to_email: str, subject: str, body: str):
    """
    Async wrapper for sending generic emails. 
    Maintains compatibility with existing code calling this function.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    # Run synchronous SendGrid call in executor
    await loop.run_in_executor(None, send_email, to_email, subject, body, body)
    return True
