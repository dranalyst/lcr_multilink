
from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
from database import get_db
from models.asterisk_ob_logs import Asterisk_ob_logs
from models.asterisk_ib_logs import Asterisk_ib_logs  # <-- add this
from models.schedule import Schedule
from schemas.asterisk_logs import (
    AsteriskCallOrder,
    AsteriskObCdrIn,
    AsteriskIbCdrIn,
)
from services.asterisk_ami import originate_via_ami
from services.asterisk_ingest import ingest_outbound_cdr  #, ingest_inbound_cdr
from zoneinfo import ZoneInfo
import re
from utils.normalize_msisdn import normalize_msisdn

router = APIRouter(
    prefix="/asterisk",
    tags=["Asterisk"],   # more generic, covers OB + IB
)


def extract_src_from_clid(clid: Optional[str], src: Optional[str]) -> Optional[str]:
    """
    For clid of the form: "NAME" <NUMBER>
    If NAME looks like a phone number (+ or digits), return NAME.
    Otherwise, return NUMBER. Fallback to existing src if parsing fails.
    """
    if not clid:
        return src

    # Example clid: "+34655519202" <9367212>
    m = re.match(r'"?(?P<name>[^"]*)"?\s*<(?P<num>[^>]+)>', clid)
    if not m:
        return src

    name = m.group("name").strip()
    num = m.group("num").strip()

    # If "name" looks like a real phone number, prefer it
    if name and (name.startswith("+") or name.isdigit()):
        return name

    # Otherwise fall back to the numeric part
    if num and (num.startswith("+") or num.isdigit()):
        return num

    return src


def parse_asterisk_timestamp(
    value: Optional[str],
    userfield_tz: Optional[str] = None,
) -> datetime:
    """
    Parse Asterisk CDR(start) string into an aware datetime.

    - Timestamp may be naive or ISO formatted
    - Timezone is taken from CDR(userfield) if provided
      (expects an IANA tz like 'Europe/Madrid')
    - Falls back to UTC safely
    """

    if not value:
        return datetime.now(timezone.utc)

    # 1️⃣ Parse timestamp
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.now(timezone.utc)

    # 2️⃣ If already timezone-aware → return as-is
    if dt.tzinfo is not None:
        return dt

    # 3️⃣ Attach timezone from userfield if possible
    if userfield_tz:
        try:
            return dt.replace(tzinfo=ZoneInfo(userfield_tz))
        except Exception:
            # invalid timezone string → fall back to UTC
            pass

    # 4️⃣ Final fallback
    return dt.replace(tzinfo=timezone.utc)



@router.post("/originate", status_code=status.HTTP_202_ACCEPTED)
async def send_call_order(
    payload: AsteriskCallOrder,
    db: Session = Depends(get_db),
):
    """
    Originate an outbound test call on Asterisk for this schedule_id.
    Uses AMI via services.asterisk_ami.originate_via_ami.
    """

    # 1. Check that schedule exists and is an Asterisk schedule
    schedule = db.query(Schedule).filter(Schedule.id == payload.schedule_id).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {payload.schedule_id} not found",
        )

    if schedule.is_asterisk_engine != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schedule is not flagged for Asterisk engine",
        )

    # 2. Call AMI helper (channel, vars, etc. handled inside)
    ami_response = originate_via_ami(payload)

    if ami_response.get("status") not in ("Success", "Follows"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AMI originate failed: {ami_response.get('message')}",
        )

    # 3. Update schedule status (e.g. 1 = "sent to Asterisk")
    schedule.status = 1
    db.commit()

    return {
        "message": "Call order sent to Asterisk",
        "ami_response": ami_response,  # dict with status/message/raw
    }


@router.post("/ob_cdr", status_code=status.HTTP_201_CREATED)
async def ingest_asterisk_ob_cdr(
    payload: AsteriskObCdrIn,
    db: Session = Depends(get_db),
):
    """
    Receive one outbound Asterisk CDR in JSON format and store it
    into asterisk_ob_cdr using Asterisk_ob_logs model.
    """

    schedule = db.query(Schedule).filter(Schedule.id == payload.schedule_id).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown schedule_id {payload.schedule_id}",
        )

    cdr = Asterisk_ob_logs(
        calldate=payload.calldate,
        clid=payload.clid,
        src=payload.src,
        dst=payload.dst,
        duration=payload.duration,
        extended_duration=payload.extended_duration,
        status=payload.status,
        teleservice=payload.teleservice,
        schedule_id=payload.schedule_id,
        dcontext=payload.dcontext,
        channel=payload.channel,
        dstchannel=payload.dstchannel,
        lastapp=payload.lastapp,
        lastdata=payload.lastdata,
        amaflags=payload.amaflags,
        accountcode=payload.accountcode,
        call_type=payload.call_type,
        userfield=payload.userfield,
        trunk_used=payload.trunk_used,
        failure_cause=payload.failure_cause,
        latency_ms=payload.latency_ms,
    )

    db.add(cdr)
    db.commit()
    db.refresh(cdr)

    # Optionally update schedule.status based on disposition
    if payload.status and payload.status.upper() == "ANSWERED":
        schedule.status = 2  # 2 = 'completed'
    else:
        schedule.status = -1  # failure code
    db.commit()

    return {"id": cdr.id}


@router.post("/cdr/ob")
async def receive_ob_cdr(
    cdr: AsteriskObCdrIn,
    db: Session = Depends(get_db),
):
    """
    Generic OB CDR ingest endpoint using services.asterisk_ingest.ingest_outbound_cdr.
    """
    record = ingest_outbound_cdr(cdr, db)
    return {"id": record.id}


@router.get("/ib_cdrs")
async def receive_ib_cdr_via_get(
    # Core CDR fields we pass from Asterisk via CURL query parameters
    clid: Optional[str] = None,
    src: Optional[str] = None,
    dst: Optional[str] = None,
    channel: Optional[str] = None,
    dstchannel: Optional[str] = None,
    disposition: Optional[str] = None,
    accountcode: Optional[str] = None,
    duration: Optional[int] = None,
    billsec: Optional[int] = None,
    dcontext: Optional[str] = None,
    lastapp: Optional[str] = None,
    lastdata: Optional[str] = None,
    amaflags: Optional[int] = None,
    userfield: Optional[str] = None,
    linkedid: Optional[str] = None,

    # Extra meta fields (optional)
    schedule_id: Optional[int] = None,
    call_source: Optional[str] = "asterisk",
    call_type: Optional[str] = "inbound",
    trunk_used: Optional[str] = None,
    failure_cause: Optional[str] = None,
    latency_ms: Optional[int] = None,
    notes: Optional[str] = None,

    # IMPORTANT: Asterisk CDR(start) → calldate
    start: Optional[str] = None,

    db: Session = Depends(get_db)
):
    """
    Inbound CDR ingest endpoint to be called by Asterisk via CURL (GET).
    Stores records into asterisk_ib_cdr table.
    """

    calldate = parse_asterisk_timestamp(start, userfield_tz=userfield,)

    # Fix src using clid if possible
    effective_src = extract_src_from_clid(clid, src)
    standard_src = normalize_msisdn(effective_src, accountcode[:2])  # later you can normalize with phonenumbers, etc.

    # # For now, keep standard_src = src (you can normalize later)
    # standard_src = src

    cdr = Asterisk_ib_logs(
        calldate=calldate,
        clid=clid,
        src=effective_src,
        standard_src=standard_src,
        dst=dst,
        dcontext=dcontext,
        channel=channel,
        dstchannel=dstchannel,
        lastapp=lastapp,
        lastdata=lastdata,
        extended_duration=duration,
        duration=billsec,
        status=disposition,
        amaflags=amaflags,
        accountcode=accountcode,
        userfield=userfield,
        linkedid=linkedid,
        schedule_id=schedule_id,
        call_source=call_source,
        call_type=call_type,
        trunk_used=trunk_used,
        failure_cause=failure_cause,
        latency_ms=latency_ms,
        notes=notes,
        # src_country / dst_country / operators & teleservice
        # use DB defaults defined in your CREATE TABLE
    )

    db.add(cdr)
    db.commit()
    db.refresh(cdr)

    return {"id": cdr.id, "status": "ok"}