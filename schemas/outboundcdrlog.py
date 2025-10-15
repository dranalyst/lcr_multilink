from datetime import datetime

from pydantic import BaseModel
from typing import List, Union

class OutboundCDRLog(BaseModel):
    aNum: str
    bNum: str
    starttime: datetime
    duration: int
    status: str

LogsPayload = Union[OutboundCDRLog, List[OutboundCDRLog]]