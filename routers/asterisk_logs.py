
from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from sqlalchemy.orm import Session

from database import get_db
from models.asterisk_ob_logs import Asterisk_ob_logs
from models.schedule import Schedule
from schemas.asterisk_logs import (
    AsteriskCallOrder,
    AsteriskObCdrIn,
    AsteriskIbCdrIn,
)
from services.asterisk_ami import originate_via_ami
from services.asterisk_ingest import ingest_outbound_cdr, ingest_inbound_cdr

router = APIRouter(
    prefix="/asterisk",
    tags=["Asterisk"],   # more generic, covers OB + IB
)


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


@router.post("/cdr/ib")
async def receive_ib_cdr(
    cdr: AsteriskIbCdrIn,
    db: Session = Depends(get_db),
):
    """
    Generic IB CDR ingest endpoint using services.asterisk_ingest.ingest_inbound_cdr.
    """
    record = ingest_inbound_cdr(cdr, db)
    return {"id": record.id}