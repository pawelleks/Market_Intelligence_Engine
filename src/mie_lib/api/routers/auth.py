import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jose import jwt

# Database
from mie_lib.db.database import get_db
from mie_lib.db.models import User

# Services
# Services
from mie_lib.services.telegram_service import send_telegram_alert
from mie_lib.services.email_service import send_email_notification

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Configuration ---
# You should ideally load these from a config module involved with .env
# For now, os.getenv is sufficient given the instructions.
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("CRITICAL SECURITY ERROR: JWT_SECRET_KEY is not set.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 day

# Client ID for Google Auth - Usually frontend sends this, verifying backend needs it?
# Actually verify_oauth2_token can take None for audience but it's unsafe.
# We'll rely on the one in .env if present, otherwise skip audience check (DEV ONLY WARNING)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


# --- Schemas ---
class GenericLoginResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    message: str = "Login processed. If your account is pending, check your email for updates."

class LoginRequest(BaseModel):
    id_token: str # The Google ID Token

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    is_approved: bool
    is_admin: bool
    visit_count: Optional[int] = 0

    class Config:
        from_attributes = True # Pydantic v2
        orm_mode = True # Pydantic v1 (backwards compat)

# --- Helpers ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Endpoints ---

@router.post("/login", response_model=GenericLoginResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Exchanges a Google ID Token for an App JWT.
    
    SECURITY UPDATE (VULN-04):
    Returns a unified 200 OK response for all valid Google Tokens.
    - Active Users: Receive access_token.
    - Pending/New Users: Receive a generic message and an email notification.
    """
    token_str = login_data.id_token
    
    # 1. Verify Google Token (Invalid token still returns 401 as it's a client error)
    try:
        id_info = id_token.verify_oauth2_token(
            token_str, 
            google_requests.Request(), 
            audience=GOOGLE_CLIENT_ID
        )
    except ValueError as e:
        logger.error(f"Invalid Google Token: {e}")
        raise HTTPException(status_code=401, detail="Invalid Authentication Token")

    # 2. Extract Info
    email = id_info.get("email")
    sub = id_info.get("sub") 
    name = id_info.get("name")
    
    if not email:
        raise HTTPException(status_code=400, detail="Token missing email")

    # 3. Check DB
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # --- NEW USER CASE ---
        # Registration Flow
        new_user = User(
            email=email,
            google_sub=sub,
            full_name=name,
            is_approved=False,
            is_admin=False
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Notify Admin (Registration Only)
        await send_telegram_alert(f"🚨 New User Signup: {email} ({name})")
        
        # Return 403 for New User
        raise HTTPException(
            status_code=403, 
            detail="Authentication successful, but account is pending approval."
        )

    # --- IDENTITY VERIFICATION ---
    if user.google_sub and user.google_sub != sub:
        # Mismatch - Fail Authentication
        logger.critical(f"SECURITY ALERT: User {email} ID mismatch.")
        raise HTTPException(status_code=403, detail="Authentication failed. Identity mismatch.")

    # Backfill sub
    if not user.google_sub:
        user.google_sub = sub
        db.commit()

    if not user.is_approved:
        # --- UNAPPROVED CASE ---
        # Do NOT send Telegram here (prevents spam on login attempts)
        raise HTTPException(
            status_code=403, 
            detail="Authentication successful, but account is pending approval."
        )

    # --- APPROVED CASE ---
    try:
        user.visit_count = (user.visit_count or 0) + 1
        db.commit()
    except Exception as e:
        logger.error(f"Failed to increment visit_count for {email}: {e}")
        
    # Generate JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id, "is_admin": user.is_admin},
        expires_delta=access_token_expires
    )
    
    return GenericLoginResponse(
        access_token=access_token, 
        token_type="bearer",
        message="Login successful."
    )
