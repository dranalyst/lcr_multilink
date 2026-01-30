# app/routers/asterisk_control.py

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.asterisk_logs import AsteriskCallOrder
from models.asterisk_ob_logs import Asterisk_ob_logs
from services.asterisk_ami import originate_via_ami

router = APIRouter(prefix="/asterisk", tags=["asterisk_control"])


@router.post("/sendcall")
async def send_asterisk_call(
    order: AsteriskCallOrder,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Trigger an outbound test call on the Asterisk box via AMI.

    Flow:
      1. Use AMI to originate the call.
      2. (Optional but useful) Create a 'pending' CDR row with status = 'ORIGINATED'.
         The final / real CDR will later be inserted via the CDR ingestion pipeline.
    """
    try:
        ami_result = originate_via_ami(order)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to originate call via AMI: {e}",
        )

    # Optional: store a 'pending' record so that vw_all_ob_calls can see
    # that a call was requested even before the full CDR arrives.
    pending = Asterisk_ob_logs(
        calldate=datetime.now(timezone.utc),
        clid=order.caller_id or order.src,
        src=order.src,
        dst=order.dst,
        duration=0,
        extended_duration=0,
        status="ORIGINATED",
        teleservice=0,              # your default voice code
        schedule_id=order.schedule_id,
        call_type="OB",
        call_source="asterisk",
        trunk_used=order.trunk or "",
        failure_cause=None,
        latency_ms=None,
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)

    return {
        "ami": ami_result,
        "pending_cdr_id": pending.id,
        "schedule_id": order.schedule_id,
    }