from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Literal

class ScheduleOut(BaseModel):
    id: int
    aNum: Optional[str] = None
    bNum: str
    status: int
    schedule_sync_date: Optional[datetime] = None
    status_change_date: Optional[datetime] = None

    class Config:
        orm_mode = True


class MarkCalledBatchPayload(BaseModel):
    schedule_ids: List[int]


class UpdateInboundStatusPayload(BaseModel):
    status: Literal[-1, 0]