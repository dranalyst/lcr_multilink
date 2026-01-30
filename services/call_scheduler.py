# app/services/call_scheduler.py
import logging
from datetime import datetime, timezone
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from database import SessionLocal
from models.schedule import Schedule
from schemas.asterisk_logs import AsteriskCallOrder
from services.asterisk_ami import originate_via_ami

logger = logging.getLogger(__name__)

MAX_BATCH = int(os.getenv("SCHEDULER_MAX_BATCH", "5"))


def dispatch_due_asterisk_calls(db: Session) -> None:
    now = datetime.now(timezone.utc)

    # 🔒 Lock rows so multiple workers don’t grab the same calls
    rows = db.execute(
        text(
            """
            SELECT id
            FROM public.schedule
            WHERE is_asterisk_engine = 1
              AND status = 0
              AND scheduled_time IS NOT NULL
              AND scheduled_time <= :now
              AND (expire_at IS NULL OR expire_at > :now)
            ORDER BY scheduled_time, id
            FOR UPDATE SKIP LOCKED
            LIMIT :lim
            """
        ),
        {"now": now, "lim": MAX_BATCH},
    ).fetchall()

    if not rows:
        return

    ids = [r[0] for r in rows]

    schedules = (
        db.query(Schedule)
        .filter(Schedule.id.in_(ids))
        .order_by(Schedule.scheduled_time, Schedule.id)
        .all()
    )

    for sch in schedules:
        attempts = getattr(sch, "attempts", 0) or 0
        max_retries = getattr(sch, "max_retries", 0) or 0

        if max_retries > 0 and attempts >= max_retries:
            sch.status = -2  # exhausted
            sch.status_change_date = now
            continue

        src = (sch.aNum or "").strip()
        dst = (sch.bNum or "").strip()

        if not dst:
            logger.warning(f"Schedule {sch.id}: empty dst (bNum), cannot originate")
            sch.status = -1
            sch.status_change_date = now
            continue

        provider = (getattr(sch, "call_provider", None) or "").strip().lower()

        logger.info(
            f"Schedule {sch.id}: provider={provider!r} src={src!r} dst={dst!r} "
            f"context will be derived in AMI"
        )

        order = AsteriskCallOrder(
            schedule_id=sch.id,
            src=src,
            dst=dst,
            trunk=provider or None,  # ✅ THIS is what your AMI should read as “provider”
            context="from-fastapi",  # can remain; AMI will override for commpeak
            exten="s",
            priority=1,
        )

        try:
            logger.info(f"Schedule {sch.id}: call_provider={provider} dst={dst} src={sch.aNum}")
            resp = originate_via_ami(order)
            logger.warning(f"AMI RAW for schedule {sch.id}: {resp}")
            logger.info(f"AMI originate result for schedule {sch.id}: {resp}")

            if hasattr(sch, "attempts"):
                sch.attempts = attempts + 1

            if resp.get("status") in ("Success", "Follows"):
                sch.status = 1  # handed to Asterisk
            else:
                sch.status = -1

            sch.status_change_date = now

        except Exception as e:
            logger.exception(f"AMI originate failed for schedule {sch.id}: {e}")
            if hasattr(sch, "attempts"):
                sch.attempts = attempts + 1
            sch.status = -1
            sch.status_change_date = now

    db.commit()


async def scheduler_loop(poll_seconds: int = 10):
    import asyncio

    while True:
        db = SessionLocal()
        try:
            dispatch_due_asterisk_calls(db)
        finally:
            db.close()

        await asyncio.sleep(poll_seconds)




# import logging
# from datetime import datetime, timezone
# import os
#
# from sqlalchemy import text
# from sqlalchemy.orm import Session
#
# from database import SessionLocal
# from models.schedule import Schedule
# from schemas.asterisk_logs import AsteriskCallOrder
# from services.asterisk_ami import originate_via_ami
#
# logger = logging.getLogger(__name__)
#
# MAX_BATCH = int(os.getenv("SCHEDULER_MAX_BATCH", "5"))
#
#
# def dispatch_due_asterisk_calls(db: Session) -> None:
#     now = datetime.now(timezone.utc)
#
#     # 🔒 Lock rows so multiple workers don’t grab the same calls
#     rows = db.execute(
#         text(
#             """
#             SELECT id
#             FROM public.schedule
#             WHERE is_asterisk_engine = 1
#               AND status = 0
#               AND scheduled_time IS NOT NULL
#               AND scheduled_time <= :now
#               AND (expire_at IS NULL OR expire_at > :now)
#             ORDER BY scheduled_time, id
#             FOR UPDATE SKIP LOCKED
#             LIMIT :lim
#             """
#         ),
#         {"now": now, "lim": MAX_BATCH},
#     ).fetchall()
#
#     if not rows:
#         return
#
#     ids = [r[0] for r in rows]
#
#     schedules = (
#         db.query(Schedule)
#         .filter(Schedule.id.in_(ids))
#         .order_by(Schedule.scheduled_time, Schedule.id)
#         .all()
#     )
#
#     for sch in schedules:
#         attempts = getattr(sch, "attempts", 0) or 0
#         max_retries = getattr(sch, "max_retries", 0) or 0
#
#         if max_retries > 0 and attempts >= max_retries:
#             sch.status = -2  # exhausted
#             continue
#
#         # ✅ We ONLY use dst (no dst_endpoint anymore)
#         dst = (sch.bNum or "").strip()
#
#         if not dst:
#             logger.warning(f"Schedule {sch.id}: empty dst (bNum), cannot originate")
#             sch.status = -1
#             continue
#
#         # ✅ Originate into ami-internal-test
#         # Dialplan will route using ${DST}
#         order = AsteriskCallOrder(
#             schedule_id=sch.id,
#             src=sch.aNum or "",
#             dst=dst,                         # ← single source of truth
#             context="from-fastapi",     # ← must exist in extensions.conf
#             exten="s",                       # ← ami-internal-test starts at s,1
#             caller_id=sch.aNum or "",
#             trunk=None,
#             priority=1,
#         )
#
#         try:
#             resp = originate_via_ami(order)
#             logger.info(f"AMI originate result for schedule {sch.id}: {resp}")
#
#             if hasattr(sch, "attempts"):
#                 sch.attempts = attempts + 1
#
#             if resp.get("status") in ("Success", "Follows"):
#                 sch.status = 1  # handed to Asterisk
#             else:
#                 sch.status = -1
#
#         except Exception as e:
#             logger.exception(f"AMI originate failed for schedule {sch.id}: {e}")
#             if hasattr(sch, "attempts"):
#                 sch.attempts = attempts + 1
#             sch.status = -1
#
#     db.commit()
#
#
# async def scheduler_loop(poll_seconds: int = 10):
#     import asyncio
#
#     while True:
#         db = SessionLocal()
#         try:
#             dispatch_due_asterisk_calls(db)
#         finally:
#             db.close()
#
#         await asyncio.sleep(poll_seconds)
