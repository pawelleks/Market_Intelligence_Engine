from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from mie_lib.db.database import get_db
from mie_lib.db.models import User
from mie_lib.api.dependencies import verify_admin
from mie_lib.api.routers.auth import UserResponse  # Reuse schema

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin)]
)

@router.get("/users", response_model=List[UserResponse])
def list_unapproved_users(db: Session = Depends(get_db)):
    """List all users who are strictly NOT approved (Pending)."""
    return db.query(User).filter(User.is_approved == False).all()

@router.get("/users/all", response_model=List[UserResponse])
def list_all_users(db: Session = Depends(get_db)):
    """List ALL users (Approved and Pending) with stats."""
    return db.query(User).all()

@router.put("/users/{user_id}/approve", response_model=UserResponse)
async def approve_user(user_id: int, db: Session = Depends(get_db)):
    """Approve a pending user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_approved = True
    # Reset status if it was revoked
    if user.subscription_status == 'revoked':
        user.subscription_status = 'free'
        
    db.commit()
    db.refresh(user)
    
    # Send Approval Email
    from mie_lib.services.email_service import send_access_approved
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, send_access_approved, user.email, user.full_name or "there")
    except Exception as e:
        print(f"Failed to send approval email: {e}")

    return user

@router.put("/users/{user_id}/revoke", response_model=UserResponse)
def revoke_user(user_id: int, db: Session = Depends(get_db)):
    """Revoke access for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_approved = False
    user.subscription_status = 'revoked'
    db.commit()
    db.refresh(user)
    return user

@router.put("/users/{user_id}/deny")
def deny_user(user_id: int, db: Session = Depends(get_db)):
    """Deny (Delete) a pending user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db.delete(user)
    db.commit()
    return {"message": "User denied and removed"}
