from datetime import datetime

from pydantic import BaseModel
from typing import List, Union, Optional


class AsteriskCallOrder(BaseModel):
    schedule_id: int
    src: str
    dst: str

    # NEW: tells AMI how to build the channel/context
    call_provider: Optional[str] = None  # e.g. "commpeak", "gsm"

    # keep as optional override; AMI will decide if None
    context: Optional[str] = None

    caller_id: Optional[str] = None
    exten: str = "s"
    priority: int = 1
    trunk: Optional[str] = None

    # OPTIONAL: for your CLI-equivalent originate
    application: Optional[str] = None   # e.g. "Playback"
    data: Optional[str] = None          # e.g. "demo-congrats"



# class AsteriskCallOrder(BaseModel):
#     schedule_id: int
#     src: str
#     dst: str
#     context: str = "from-fastapi"
#     caller_id: Optional[str] = None
#     # context: str = "from-internal"
#     exten: str = "s"
#     priority: int = 1
#     trunk: Optional[str] = None   # e.g. "SIP/mytrunk"


# -------------------------------------------------------------------
# Base CDR schema shared by OB + IB Asterisk logs
#    -> matches ORM attribute names (not DB column names)
# -------------------------------------------------------------------
class AsteriskCdrBase(BaseModel):
    calldate: datetime
    clid: Optional[str] = None
    src: Optional[str] = None
    dst: Optional[str] = None

    # ORM mapping:
    #   duration           -> billsec
    #   extended_duration  -> duration
    duration: Optional[int] = None
    extended_duration: Optional[int] = None

    status: Optional[str] = None          # disposition
    teleservice: int = 0                  # you’re using 0 = voice by default

    dcontext: Optional[str] = None
    channel: Optional[str] = None
    dstchannel: Optional[str] = None
    lastapp: Optional[str] = None
    lastdata: Optional[str] = None
    amaflags: Optional[int] = None
    accountcode: Optional[str] = None
    call_type: Optional[str] = None
    call_source: Optional[str] = None
    userfield: Optional[str] = None
    trunk_used: Optional[str] = None
    failure_cause: Optional[str] = None
    latency_ms: Optional[int] = None


# -------------------------------------------------------------------
# 4) OUTBOUND Asterisk CDR input – matches models/Asterisk_ob_logs
#    schedule_id = Integer, non-nullable
# -------------------------------------------------------------------
class AsteriskObCdrIn(AsteriskCdrBase):
    schedule_id: int


# -------------------------------------------------------------------
# 5) INBOUND Asterisk CDR input – matches models/Asterisk_ib_logs
#    schedule_id -> mapped to DB test_run_id (String(50), nullable)
# -------------------------------------------------------------------
class AsteriskIbCdrIn(AsteriskCdrBase):
    schedule_id: Optional[str] = None   # maps to test_run_id column
    standard_src: Optional[str] = None