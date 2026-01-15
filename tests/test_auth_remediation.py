
import os
os.environ["JWT_SECRET_KEY"] = "TEST_SECRET"
os.environ["GOOGLE_CLIENT_ID"] = "TEST_CLIENT_ID"
os.environ["TELEGRAM_BOT_TOKEN"] = "TEST_BOT_TOKEN"
os.environ["TELEGRAM_ADMIN_CHAT_ID"] = "123456"

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from mie_lib.api.routers import auth
from mie_lib.db.models import User
from fastapi import HTTPException

# Mock data
VALID_TOKEN = "valid_token"
EMAIL_ACTIVE = "active@example.com"
EMAIL_PENDING = "pending@example.com"
EMAIL_NEW = "new@example.com"

@pytest.fixture
def mock_db():
    session = MagicMock()
    return session

@pytest.fixture
def mock_verify_token():
    with patch("google.oauth2.id_token.verify_oauth2_token") as mock:
        yield mock

@pytest.fixture
def mock_send_email():
    with patch("mie_lib.api.routers.auth.send_email_notification", new_callable=AsyncMock) as mock:
        yield mock

@pytest.fixture
def mock_telegram():
    with patch("mie_lib.api.routers.auth.send_telegram_alert", new_callable=AsyncMock) as mock:
        yield mock

@pytest.mark.anyio
async def test_login_active_user(mock_db, mock_verify_token, mock_send_email):
    """Active user should get a token."""
    mock_verify_token.return_value = {"email": EMAIL_ACTIVE, "sub": "123", "name": "Active User"}
    
    # Mock DB User
    user = User(email=EMAIL_ACTIVE, google_sub="123", is_approved=True, is_admin=False)
    mock_db.query.return_value.filter.return_value.first.return_value = user
    
    mock_login_data = MagicMock(id_token=VALID_TOKEN)
    
    response = await auth.login(mock_login_data, db=mock_db)
    
    assert response.access_token is not None
    assert response.message == "Login successful."

@pytest.mark.anyio
async def test_login_pending_user(mock_db, mock_verify_token, mock_send_email, mock_telegram):
    """Pending user should get 403 Forbidden with specific message."""
    mock_verify_token.return_value = {"email": EMAIL_PENDING, "sub": "456", "name": "Pending User"}
    
    user = User(email=EMAIL_PENDING, google_sub="456", is_approved=False, is_admin=False)
    mock_db.query.return_value.filter.return_value.first.return_value = user
    
    mock_login_data = MagicMock(id_token=VALID_TOKEN)
    
    with pytest.raises(HTTPException) as exc:
        await auth.login(mock_login_data, db=mock_db)
    
    assert exc.value.status_code == 403
    assert "account is pending approval" in exc.value.detail
    # Ensure NO Telegram alert for existing pending user
    assert not mock_telegram.called

@pytest.mark.anyio
async def test_login_new_user(mock_db, mock_verify_token, mock_send_email, mock_telegram):
    """New user should be auto-approved and get a token."""
    mock_verify_token.return_value = {"email": EMAIL_NEW, "sub": "789", "name": "New User"}
    
    mock_db.query.return_value.filter.return_value.first.return_value = None # No user found
    
    mock_login_data = MagicMock(id_token=VALID_TOKEN)
    
    # Should NOT raise exception now
    response = await auth.login(mock_login_data, db=mock_db)
    
    assert response.access_token is not None
    assert response.message == "Login successful."
    
    # Ensure Telegram alert IS called for new user
    assert mock_telegram.called
    assert "Auto-Approved" in mock_telegram.call_args[0][0]
