from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from database import Base


class ResumeLog(Base):
    __tablename__ = "resume_logs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    role = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)