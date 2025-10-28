from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models.schedule import Schedule
from models.phoneuser import PhoneUsers
from typing import List, Annotated, Literal
from datetime import datetime, timezone
from .auth import get_current_user
from schemas.schedule import ScheduleOut, MarkCalledBatchPayload, UpdateInboundStatusPayload


router = APIRouter(
    prefix="/schedule",
    tags=["schedule"]
)


@router.get("/bnumbers")
async def get_numbers(
    current_user: Annotated[PhoneUsers, Depends(get_current_user)],
    db: Session = Depends(get_db),
    limit: int = Query(5, ge=1, le=100, description="Maximum number of bnumbers to return (default: 15)")
):
    """
    Return up to <limit> eligible schedules for aNum=user_phone with these rules:
      - If bNum has PhoneUsers(user_type==0 AND call_direction==False) → include.
      - If bNum missing in PhoneUsers OR user_type!=0 → include ONLY if status==0.
      - If bNum has PhoneUsers(user_type==0 AND call_direction==True) → exclude.
    """

    # current_user = db.merge(current_user)
    user_phone = current_user.phoneNumber

    # ✅ Step 1: Fetch more than limit to allow for filtering
    schedules = (
        db.query(Schedule)
        .filter(Schedule.aNum == user_phone, Schedule.status.in_([-1, 0]))
        .order_by(Schedule.id.asc())
        .limit(limit * 4)   # small buffer before filtering
        .all()
    )
    if not schedules:
        return []

    # ✅ Step 2: Gather distinct bNums to check readiness
    bnums = list({s.bNum for s in schedules if s.bNum})

    pu_map = {}
    if bnums:
        rows = (
            db.query(
                PhoneUsers.phoneNumber,
                PhoneUsers.call_direction,
                PhoneUsers.user_type
            )
            .filter(PhoneUsers.phoneNumber.in_(bnums))
            .all()
        )
        pu_map = {p: (cd, ut) for p, cd, ut in rows}

    # ✅ Step 3: Apply filtering rules (keep duplicates allowed)
    filtered = []
    for s in schedules:
        info = pu_map.get(s.bNum)
        include = False

        if info is None:
            # No phoneusers record → allow only pending
            include = (s.status == 0)
        else:
            call_direction, user_type = info
            user_type = 0 if user_type == 0 else 1
            if user_type == 0:
                # Include if inbound-ready (False = inbound)
                include = (not call_direction)
            else:
                # Non-type-0 allowed only if pending
                include = (s.status == 0)

        if include:
            filtered.append(s)

        # ✅ Stop once we’ve reached limit rows, including duplicates
        if len(filtered) >= limit:
            break

    if not filtered:
        return []

    # ✅ Step 4: Update sync timestamp
    now = datetime.now(timezone.utc)
    for r in filtered:
        r.schedule_sync_date = now
    db.commit()

    # ✅ Step 5: Return up to <limit> rows (duplicates preserved)
    return [
        {
            "id": r.id,
            "aNum": r.aNum,
            "bNum": r.bNum,
            "status": r.status,
        }
        for r in filtered[:limit]
    ]



# @router.get("/bnumbers")
# async def get_numbers(current_user: Annotated[PhoneUsers, Depends(get_current_user)], db: Session = Depends(get_db)):
#     """
#     Return schedules for aNum=user_phone with these rules:
#       - If bNum has PhoneUsers(user_type==0 AND ib_readiness==True) -> include.
#       - If bNum missing in PhoneUsers OR user_type!=0 -> include ONLY if status==0.
#       - If bNum has PhoneUsers(user_type==0 AND ib_readiness==False) -> EXCLUDE.
#     Returns a plain list for Kotlin JSONArray parsing.
#     """
#     user_phone = current_user.phoneNumber
#     schedules = (
#         db.query(Schedule)
#         .filter(Schedule.aNum == user_phone, Schedule.status.in_([-1, 0]))
#         .order_by(Schedule.id.asc())
#         .all()
#     )
#     if not schedules:
#         return []
#
#     # distinct bNums to check readiness
#     bnums = list({s.bNum for s in schedules if s.bNum})
#
#     # Map: phone -> (call_direction, user_type)
#     pu_map = {}
#     if bnums:
#         rows = (
#             db.query(PhoneUsers.phoneNumber, PhoneUsers.call_direction, PhoneUsers.user_type)
#             .filter(PhoneUsers.phoneNumber.in_(bnums))
#             .all()
#         )
#         pu_map = {phone: (call_direction, user_type) for phone, call_direction, user_type in rows}
#
#     filtered = []
#     for s in schedules:
#         info = pu_map.get(s.bNum)
#
#         if info is None:
#             # No phoneusers record -> allow only pending
#             if s.status == 0:
#                 filtered.append(s)
#             continue
#
#         call_direction, user_type = info
#         # Treat None as not-0 to be safe on legacy rows
#         user_type = 0 if user_type == 0 else 1
#
#         if user_type == 0:
#             if call_direction == 0:
#                 filtered.append(s)        # ok
#             else:
#                 pass                      # explicit exclude when ib_ready is False
#         else:
#             if s.status == 0:
#                 filtered.append(s)        # non-type-0 allowed only if pending
#
#     if not filtered:
#         return []
#
#     # Update sync timestamp only for what we actually return
#     now = datetime.now(timezone.utc)
#     for r in filtered:
#         r.schedule_sync_date = now
#     db.commit()
#
#     return [
#         {"id": r.id, "aNum": r.aNum, "bNum": r.bNum, "status": r.status}
#         for r in filtered
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



@router.put("/mark-called-batch")
async def mark_batch_called(payload: MarkCalledBatchPayload,
                            current_user: Annotated[PhoneUsers, Depends(get_current_user)],
                            db: Session = Depends(get_db)):
    # Exit early if the client sent an empty list
    if not payload.schedule_ids:
        return {"status": "no_ids_provided", "updated_count": 0}

    # Fetch all records from the DB that match the provided IDs in one query
    records_to_update = db.query(Schedule).filter(Schedule.id.in_(payload.schedule_ids)).all()

    # Security Check: Ensure all requested records belong to the current user.
    # If even one record does not belong to them, reject the entire transaction.
    for record in records_to_update:
        if record.aNum != current_user.phoneNumber:
            raise HTTPException(
                status_code=403,
                detail=f"You are not authorized to update schedule ID {record.id}."
            )

    # Validation Check: Ensure all IDs provided by the client were found in the DB.
    if len(records_to_update) != len(set(payload.schedule_ids)):
        raise HTTPException(
            status_code=404,
            detail="One or more of the provided schedule IDs were not found."
        )

    # If all checks pass, update the status and timestamp for each record
    update_time = datetime.now(timezone.utc)
    for record in records_to_update:
        record.status = 1
        record.status_change_date = update_time

    # Commit all changes to the database in a single transaction
    db.commit()

    updated_ids = [record.id for record in records_to_update]

    return {
        "status": "batch_updated",
        "updated_count": len(updated_ids),
        "updated_ids": updated_ids
    }

@router.put("/update_ib_calls", status_code=status.HTTP_200_OK)
async def update_inbound_call_status(
        payload: UpdateInboundStatusPayload,  # Use the Pydantic model as an argument
        current_user: Annotated[PhoneUsers, Depends(get_current_user)],
        db: Session = Depends(get_db)
):
    """
    Updates the status of inbound call schedules for a user.
    - If status = -1 is provided, it finds active calls (status=0) and cancels them.
    - If status = 0 is provided, it finds canceled calls (status=-1) and reactivates them.
    """
    new_status = payload.status

    # 2. Determine which records to find based on the desired new status.
    if new_status == -1:
        # If we are canceling, we need to find active schedules (status 0).
        status_to_find = 0
        action_verb = "canceled"
    else:  # new_status will be 0
        # If we are reactivating, we need to find already canceled schedules (status -1).
        status_to_find = -1
        action_verb = "reactivated"

    # 3. Find all schedules for this user that have the status we need to change.
    records_to_update = (
        db.query(Schedule)
        .filter(Schedule.bNum == current_user.phoneNumber, Schedule.status == status_to_find)
        .all()
    )

    if not records_to_update:
        # Use HTTP 204 No Content, which is more appropriate when the request is valid
        # but there's nothing to update.
        raise HTTPException(
            status_code=status.HTTP_204_NO_CONTENT
        )

    # 4. Update all found records to the new status in one transaction.
    for record in records_to_update:
        record.status = new_status
        record.status_change_date = datetime.now(timezone.utc)

    db.commit()

    # 5. Return a dynamic success message.
    return {
        "message": f"{len(records_to_update)} scheduled inbound calls {action_verb} successfully.",
        "b_number": current_user.phoneNumber
    }