from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.schedule import Schedule
from models.phoneuser import PhoneUsers
from typing import List, Annotated
from datetime import datetime, timezone
from .auth import get_current_user
from schemas.schedule import ScheduleOut

router = APIRouter(
    prefix="/schedule",
    tags=["schedule"]
)


@router.get("/bnumbers")
async def get_numbers(current_user: Annotated[PhoneUsers, Depends(get_current_user)], db: Session = Depends(get_db)):
    """
    Return schedules for aNum=user_phone with these rules:
      - If bNum has PhoneUsers(user_type==0 AND ib_readiness==True) -> include.
      - If bNum missing in PhoneUsers OR user_type!=0 -> include ONLY if status==0.
      - If bNum has PhoneUsers(user_type==0 AND ib_readiness==False) -> EXCLUDE.
    Returns a plain list for Kotlin JSONArray parsing.
    """
    user_phone = current_user.phoneNumber
    schedules = (
        db.query(Schedule)
        .filter(Schedule.aNum == user_phone, Schedule.status.in_([-1, 0]))
        .order_by(Schedule.id.asc())
        .all()
    )
    if not schedules:
        return []

    # distinct bNums to check readiness
    bnums = list({s.bNum for s in schedules if s.bNum})

    # Map: phone -> (ib_ready, user_type)
    pu_map = {}
    if bnums:
        rows = (
            db.query(PhoneUsers.phoneNumber, PhoneUsers.ib_readiness, PhoneUsers.user_type)
            .filter(PhoneUsers.phoneNumber.in_(bnums))
            .all()
        )
        pu_map = {phone: (ib_ready, user_type) for phone, ib_ready, user_type in rows}

    filtered = []
    for s in schedules:
        info = pu_map.get(s.bNum)

        if info is None:
            # No phoneusers record -> allow only pending
            if s.status == 0:
                filtered.append(s)
            continue

        ib_ready, user_type = info
        # Treat None as not-0 to be safe on legacy rows
        user_type = 0 if user_type == 0 else 1

        if user_type == 0:
            if ib_ready:
                filtered.append(s)        # ok
            else:
                pass                      # explicit exclude when ib_ready is False
        else:
            if s.status == 0:
                filtered.append(s)        # non-type-0 allowed only if pending

    if not filtered:
        return []

    # Update sync timestamp only for what we actually return
    now = datetime.now(timezone.utc)
    for r in filtered:
        r.schedule_sync_date = now
    db.commit()

    return [
        {"id": r.id, "aNum": r.aNum, "bNum": r.bNum, "status": r.status}
        for r in filtered
    ]


# @router.get("/bnumbers")
# async def get_numbers(
#     user_phone: str,
#     db: Session = Depends(get_db)
# ):
#     """
#         Fetch B-numbers assigned to a given user (aNum).
#         Returns all records (status -1, 0, 1) to let frontend decide:
#           - status = 0 → pending (to call)
#           - status = 1 → done (checked)
#           - status = -1 → skipped (crossed)
#         """
#
#     records = (
#         db.query(Schedule)
#         .filter(Schedule.aNum == user_phone, Schedule.status.in_([-1, 0]))
#         .order_by(Schedule.id.asc())
#         .all()
#     )
#
#     if not records:
#         return []
#
#     # update schedule_sync_date for all retrieved records
#     now = datetime.now(timezone.utc)
#     for r in records:
#         r.schedule_sync_date = now
#     db.commit()
#
#     return [
#         {
#             "id": r.id,
#             "aNum": r.aNum,
#             "bNum": r.bNum,
#             "status": r.status
#         }
#         for r in records
#     ]


@router.get("/inboundcalls")
async def get_inbound_calls(
    current_user: Annotated[PhoneUsers, Depends(get_current_user)], db: Session = Depends(get_db)
):
    user_phone = current_user.phoneNumber
    # Count how many inbound calls are scheduled for this user (bNum = user phone)
    count = (
        db.query(Schedule)
        .filter(Schedule.bNum == user_phone, Schedule.status == 0)
        .count()
    )

    return {"expected_inbound_calls": count}


@router.put("/mark-called/{schedule_id}")
async def mark_number_called(schedule_id: int,
                             current_user: Annotated[PhoneUsers, Depends(get_current_user)],
                             db: Session = Depends(get_db)):
    record = db.query(Schedule).filter(Schedule.id == schedule_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Matching scheduled call not found")

    # Verify ownership:
    if record.aNum != current_user.phoneNumber:
        raise HTTPException(status_code=403, detail="You are not authorized to update this schedule")

    record.status = 1
    record.status_change_date = datetime.now(timezone.utc)
    db.commit()

    return {"status": "updated", "id": record.id}



##@router.get("/numbers")
##def get_numbers(db: Session = Depends(get_db)):
##    rows = db.query(Schedule).all()
##    return [row.bNum for row in rows if row.bNum]


#from fastapi import APIRouter
#from database import get_pg_connection
#
#import psycopg2
#
#router = APIRouter()
#
#@router.get("/numbers")
#def get_numbers():
#    conn = get_pg_connection()
#    cur = conn.cursor()
#    cur.execute('SELECT "bNum" FROM "testCall"."schedule"')
#    rows = cur.fetchall()
#    cur.close()
#    conn.close()
#    return [row[0] for row in rows]
