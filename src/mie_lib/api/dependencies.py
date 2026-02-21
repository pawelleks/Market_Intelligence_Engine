import os
from datetime import datetime
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from mie_lib.db.database import get_db
from mie_lib.db.models import User

# Re-use config from auth router or ideally a central config
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGEME_THIS_IS_UNSAFE_DEV_SECRET")
ALGORITHM = "HS256"

# Note: tokenUrl is relative to the API root. 
# Since our auth router is at /auth, the login url is /auth/login
# auto_error=False handles the case where no token is provided (for bypass or optional auth)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    # Environment-aware auth bypass for staging/development
    app_env = os.getenv("APP_ENV", "production").lower()
    if app_env in ("staging", "development"):
        return User(
            id=9999,
            email="dev@blindmonkey.io",
            full_name="Dev User",
            google_sub="dev_bypass",
            is_admin=True,
            is_approved=True,
        )

    # 1. Prioritize Real Token Verification if provided
    if token:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
            
            user = db.query(User).filter(User.email == email).first()
            if user:
                return user
            else:
                raise credentials_exception
        except JWTError:
            # If token is invalid, but we have a mock bypass, we might fall through?
            # Usually, if a token is provided, it must be valid.
            if not os.getenv("MOCK_AUTH_USER"):
                raise credentials_exception

    # 2. Check for Mock Auth (Bypass) - ONLY if no valid token or specifically requested
    mock_user_email = os.getenv("MOCK_AUTH_USER")
    if mock_user_email:
        user = db.query(User).filter(User.email == mock_user_email).first()
        if user:
            return user
        # Transient mock user
        return User(id=9999, email=mock_user_email, full_name="Mock System", google_sub="mock_bypass_sub", is_admin=True, is_approved=True)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def verify_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have administrative privileges"
        )
    return current_user
