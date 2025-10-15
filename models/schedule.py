from sqlalchemy import Column, Integer, String, DateTime
from database import Base

class Schedule(Base):
    __tablename__ = "schedule"
    # __table_args__ = {"schema": "testCall"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    aNum = Column(String, index=True)
    bNum = Column(String, index=True)
    status = Column(Integer, default=0)
    schedule_sync_date = Column(DateTime(timezone=True), nullable=True)
    status_change_date = Column(DateTime(timezone=True), nullable=True)