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
    # 1. Check for Mock Auth (Bypass)
    mock_user_email = os.getenv("MOCK_AUTH_USER")
    if mock_user_email:
        # Try to find the mock user
        user = db.query(User).filter(User.email == mock_user_email).first()
        if user:
            return user
        else:
            # Create a mock admin user if it doesn't exist (for seamless dev experience)
            print(f"Mock user {mock_user_email} not found. Creating temporary mock admin.")
            mock_user = User(
                email=mock_user_email,
                full_name="Mock Admin",
                google_sub="mock_bypass_sub",
                is_admin=True,
                is_approved=True
            )
            # CAUTION: This user might not be persisted if transaction logic isn't handled here,
            # but usually Depends(get_db) provides a session. 
            # Ideally we should just rely on an existing user or create one properly.
            # Let's just create a dummy object that behaves like User for read-only purposes 
            # OR commit it if we want persistence.
            # Better to just return the object without saving to DB to avoid pollution, 
            # UNLESS other parts of the app query the DB for this user ID.
            # The app likely uses user.id.
            
            # Let's try to fetch ANY user or create a transient one.
            # If we return a transient user, user.id might be None, which could break foreign keys.
            # Let's assume the developer will provide an email of an EXISTING user in the DB, 
            # or we accept that we might crash if the user doesn't exist.
            # BUT, for "bypass", we usually want it to just work.
            
            # Helper for completely detached mock user:
            return User(id=9999, email=mock_user_email, full_name="Mock System", google_sub="mock_bypass_sub", is_admin=True, is_approved=True)

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
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
        
    try:
        user.visit_count = (user.visit_count or 0) + 1
        db.commit()
    except Exception as e:
        print(f"Failed to track visit: {e}")
        
    return user

async def verify_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have administrative privileges"
        )
    return current_user
