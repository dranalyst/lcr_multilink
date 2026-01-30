from sqlalchemy import Column, Integer, String, DateTime, Integer

from database import Base

class Schedule(Base):
    __tablename__ = "schedule"
    # __table_args__ = {"schema": "testCall"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batchId = Column(String(10), nullable=False)
    scheduled_time = Column(DateTime(timezone=True))
    aNum = Column(String, index=True)
    bNum = Column(String, index=True)
    status = Column(Integer, default=0)
    is_asterisk_engine = Column(Integer, default=1, nullable=False)
    schedule_sync_date = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=0, nullable=False)
    destination_gw = Column(String(20), nullable=True)
    call_provider = Column(String(50), nullable=True)