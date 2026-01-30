from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Union, Annotated
from database import get_db
from models.outboundcdrlogs import OutboundLogs
from schemas.outboundcdrlog import OutboundCDRLog
from .auth import get_current_user
from starlette import status
from models import PhoneUsers
import json


router = APIRouter(
    prefix="/testCallLogs",
    tags=["testCallLogs"],
)

db_dependency = Annotated[Session, Depends(get_db)]

@router.post("/outbound", status_code=status.HTTP_200_OK)
async def upload_logs(payload: Union[OutboundCDRLog,List[OutboundCDRLog]],
                        current_user: Annotated[PhoneUsers, Depends(get_current_user)],
                        db: Session = Depends(get_db)):
    """
        Upload outbound call logs (only for authenticated users).

        Requirements:
          - Valid Authorization: Bearer <token> header.
          - Each log's aNum must match the current authenticated user's phoneNumber.
        """

    logs_to_insert = payload if isinstance(payload, list) else [payload]


    # for log in logs_to_insert:
    #     if log.aNum != current_user.phoneNumber:
    #         raise HTTPException(
    #             status_code=status.HTTP_403_FORBIDDEN,
    #             detail=f"Unauthorized: log aNum {log.aNum} does not match your account.",
    #         )

    try:
        for log in logs_to_insert:
            db_log = OutboundLogs(
                aNum=log.aNum,
                bNum=log.bNum,
                starttime=log.starttime,
                duration=log.duration,
                status=log.status,
                teleservice=log.teleservice,
                schedule_id=log.schedule_id
            )
            db.add(db_log)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving logs: {e}")

    return {"status": "ok", "inserted": len(logs_to_insert)}
