from datetime import datetime

from pydantic import BaseModel
from typing import List, Union

class InboundCDRLogs(BaseModel):
    aNum: str
    bNum: str
    starttime: datetime
    duration: int
    status: str

LogsPayload = Union[InboundCDRLogs, List[InboundCDRLogs]]