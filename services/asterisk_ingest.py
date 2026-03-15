# services/asterisk_ingest.py
from sqlalchemy.orm import Session
from models.asterisk_ob_logs import Asterisk_ob_logs
from models.schedule import Schedule
from schemas.asterisk_logs import AsteriskObCdrIn


def ingest_outbound_cdr(payload: AsteriskObCdrIn, db: Session) -> Asterisk_ob_logs:
    # Optional: validate schedule exists
    schedule = db.query(Schedule).filter(Schedule.id == payload.schedule_id).first()
    if not schedule:
        # You could raise or just log
        # For now, we allow a CDR with unknown schedule
        pass

    record = Asterisk_ob_logs(
        calldate=payload.calldate,
        clid=payload.clid or "",
        src=payload.src or "",
        dst=payload.dst or "",
        duration=payload.duration or 0,
        extended_duration=payload.extended_duration,
        status=payload.status or "UNKNOWN",
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
        call_source=payload.call_source,
        userfield=payload.userfield,
        trunk_used=payload.trunk_used,
        failure_cause=payload.failure_cause,
        latency_ms=payload.latency_ms,
        call_provider=payload.call_provider,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    # Example: update schedule based on disposition
    if schedule:
        disp = (payload.status or "").upper()
        if disp == "ANSWERED":
            schedule.status = 2  # completed
        else:
            schedule.status = -1  # failed
        db.commit()

    return record


