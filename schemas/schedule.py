from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class ScheduleOut(BaseModel):
    id: int
    aNum: Optional[str] = None
    bNum: str
    status: int
    schedule_sync_date: Optional[datetime] = None
    status_change_date: Optional[datetime] = None
    inbound_status: int

    class Config:
        orm_mode = True