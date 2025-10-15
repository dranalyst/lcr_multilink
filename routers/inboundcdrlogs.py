from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Union, Annotated
from database import get_db
from models import PhoneUsers
from models.inboundcdrlogs import InboundLogs
from schemas.inboundcdrlogs import InboundCDRLogs
from .auth import get_current_user
from starlette import status

router = APIRouter(
    prefix="/testCallLogs",
    tags=["testCallLogs"]
)

db_dependency = Annotated[Session, Depends(get_db)]

@router.post("/inbound")
async def upload_inbound_logs(payload: Union[InboundCDRLogs, List[InboundCDRLogs]],
                            current_user: Annotated[PhoneUsers, Depends(get_current_user)],
                            db: Session = Depends(get_db)):
    """
        Upload inbound call logs (only for authenticated users).
        Each request must include a valid Authorization: Bearer <token> header.
        """

    # Double-check that the logs belong to this user (sanity validation)
    # Only allow logs where bNum matches the authenticated user's phone number

    logs_to_insert = payload if isinstance(payload, list) else [payload]

    for log in logs_to_insert:
        if log.bNum != current_user.phoneNumber:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unauthorized: log bNum {log.bNum} does not match your account."
            )

    try:
        for log in logs_to_insert:
            db_log = InboundLogs(
                aNum=log.aNum,
                bNum=log.bNum,
                starttime=log.starttime,
                duration=log.duration,
                status=log.status
            )
            db.add(db_log)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving logs: {e}")

    return {"status": "ok", "inserted": len(logs_to_insert)}

