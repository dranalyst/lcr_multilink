from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict


class ScheduleOut(BaseModel):
    id: int
    aNum: Optional[str] = None
    bNum: str
    status: int
    scheduled_time: datetime
    # 0 = mobile, 1 = asterisk
    is_asterisk_engine: int
    attempts: int
    max_retries: int

    # For Pydantic v2: allow reading from SQLAlchemy ORM objects
    model_config = ConfigDict(from_attributes=True)


class MarkCalledBatchPayload(BaseModel):
    schedule_ids: List[int]


class UpdateInboundStatusPayload(BaseModel):
    status: Literal[-1, 0]