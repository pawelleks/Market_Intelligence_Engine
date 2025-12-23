from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime
from mie_lib.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    google_sub = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String)
    is_approved = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    allowed_pages = Column(JSON, default=[])
    subscription_status = Column(String, default='free')
    subscription_end_date = Column(DateTime, nullable=True)
    visit_count = Column(Integer, default=0)
