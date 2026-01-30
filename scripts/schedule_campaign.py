import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

import psycopg2
from psycopg2.extras import execute_values

import phonenumbers
import pycountry


# ==========================
# CONSTANTS
# ==========================
CALL_GAP = timedelta(minutes=3)
DEFAULT_START_OFFSET = timedelta(minutes=2)


# ==========================
# DATA MODELS
# ==========================
@dataclass(frozen=True)
class CallingProfile:
    country_iso2: str        # e.g. "ES"
    operator_name: str       # label only, stored as-is
    weight: float            # e.g. 0.4


@dataclass(frozen=True)
class OperatorWeight:
    operator_name: str       # must match af_gateways.operator_name
    weight: float            # e.g. 0.6


# ==========================
# HELPERS
# ==========================
def parse_start_at(start_at_iso: Optional[str]) -> datetime:
    now = datetime.now(timezone.utc)
    min_start = now + DEFAULT_START_OFFSET

    if not start_at_iso:
        return min_start

    dt = datetime.fromisoformat(start_at_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return max(dt.astimezone(timezone.utc), min_start)


def largest_remainder_counts(
    weights: Sequence[tuple[str, float]],
    total: int,
) -> dict[str, int]:
    raw = [(k, w * total) for k, w in weights]
    base = {k: int(v) for k, v in raw}
    remainder = total - sum(base.values())

    fracs = sorted(
        ((v - int(v), k) for k, v in raw),
        reverse=True,
    )

    for i in range(remainder):
        base[fracs[i][1]] += 1

    return base


def expand_shuffle(counts: dict[str, int]) -> list[str]:
    items: list[str] = []
    for k, c in counts.items():
        items.extend([k] * c)
    random.shuffle(items)
    return items


def country_dial_code(country_iso2: str) -> Optional[int]:
    try:
        code = phonenumbers.country_code_for_region(country_iso2.upper())
        return code if code > 0 else None
    except Exception:
        return None


def random_anum_for_iso2(country_iso2: str) -> str:
    iso2 = (country_iso2 or "--").upper()
    cc = country_dial_code(iso2) or 999

    national_len = 9 if iso2 in {"ES", "FR"} else 10
    national = "".join(str(random.randint(0, 9)) for _ in range(national_len))

    return f"+{cc}{national}"


def iso2_to_country_name(iso2: str) -> str:
    c = pycountry.countries.get(alpha_2=iso2.upper()) if iso2 and iso2 != "--" else None
    return c.name if c else "Unknown"


# ==========================
# MAIN SCHEDULER
# ==========================
def schedule_campaign(
    *,
    dsn: str,
    total_calls: int,
    start_at_iso: Optional[str],
    calling_profiles: list[CallingProfile],
    dst_country_iso2: str,
    dst_operator_mix: list[OperatorWeight],
    gw_names: list[str],
    global_spacing_sec: int = 5,
) -> dict[str, Any]:

    if total_calls <= 0:
        raise ValueError("total_calls must be > 0")
    if not calling_profiles:
        raise ValueError("calling_profiles is required")
    if not dst_operator_mix:
        raise ValueError("dst_operator_mix is required")
    if not gw_names:
        raise ValueError("gw_names is required")

    start_at_base = parse_start_at(start_at_iso)
    global_spacing = timedelta(seconds=max(0, global_spacing_sec))

    # ---- Convert percentages to exact counts ----
    calling_weights = [
        (f"{p.country_iso2}||{p.operator_name}", p.weight)
        for p in calling_profiles
    ]
    operator_weights = [
        (o.operator_name, o.weight)
        for o in dst_operator_mix
    ]

    calling_counts = largest_remainder_counts(calling_weights, total_calls)
    operator_counts = largest_remainder_counts(operator_weights, total_calls)

    calling_plan = expand_shuffle(calling_counts)
    operator_plan = expand_shuffle(operator_counts)

    b_country_name = iso2_to_country_name(dst_country_iso2)
    dst_key = dst_country_iso2.lower()

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:

        # ---- Allocate batchId (gh_0001, gh_0002, …) ----
        cur.execute(
            """
            INSERT INTO public.campaign_batch_counter (dst_country_iso2, last_seq)
            VALUES (%s, 1)
            ON CONFLICT (dst_country_iso2)
            DO UPDATE SET last_seq = campaign_batch_counter.last_seq + 1
            RETURNING last_seq
            """,
            (dst_key,),
        )
        seq = cur.fetchone()[0]
        batch_id = f"{dst_key}_{seq:04d}"

        # ---- Destination pools from af_gateways ----
        cur.execute(
            """
            SELECT operator_name, msisdn
            FROM public.af_gateways
            WHERE gw_name = ANY(%s)
              AND country_iso2 = %s
              AND msisdn IS NOT NULL AND msisdn <> ''
              AND operator_name IS NOT NULL AND operator_name <> ''
            """,
            (gw_names, dst_country_iso2),
        )

        pools: dict[str, list[str]] = {}
        for op, msisdn in cur.fetchall():
            pools.setdefault(op, []).append(msisdn)

        missing_ops = [o for o in operator_counts if o not in pools]
        if missing_ops:
            raise ValueError(f"No destination MSISDNs for operators: {missing_ops}")

        # ---- Compute gateway busy-until constraint ----
        cur.execute(
            """
            WITH gw_msisdn AS (
              SELECT msisdn
              FROM public.af_gateways
              WHERE gw_name = ANY(%s)
                AND country_iso2 = %s
            )
            SELECT max(s.scheduled_time)
            FROM public.schedule s
            JOIN gw_msisdn g ON g.msisdn = s."bNum"
            WHERE s.status = 0
            """,
            (gw_names, dst_country_iso2),
        )

        last_sched = cur.fetchone()[0]
        if last_sched:
            if last_sched.tzinfo is None:
                last_sched = last_sched.replace(tzinfo=timezone.utc)
            start_at = max(start_at_base, last_sched + CALL_GAP)
        else:
            start_at = start_at_base

        # ---- Build schedule respecting per-B-number gap ----
        next_time_for_b: dict[str, datetime] = {}
        t = start_at
        rows = []

        for i in range(total_calls):
            a_key = calling_plan[i]
            a_iso2, a_op = a_key.split("||", 1)

            a_num = random_anum_for_iso2(a_iso2)
            a_country = iso2_to_country_name(a_iso2)

            dst_op = operator_plan[i]
            b_num = random.choice(pools[dst_op])

            sched_time = max(t, next_time_for_b.get(b_num, start_at))
            next_time_for_b[b_num] = sched_time + CALL_GAP
            t += global_spacing

            rows.append((
                batch_id,
                a_num,
                a_country,
                b_num,
                b_country_name,
                dst_op,
                0,
                1,
                sched_time,
                0,
                0,
            ))

        # ---- Insert ----
        sql = """
        INSERT INTO public.schedule
          ("batchId","aNum","aCountry","bNum","bCountry",
           b_operator_name,status,is_asterisk_engine,
           scheduled_time,attempts,max_retries)
        VALUES %s
        """

        execute_values(cur, sql, rows, page_size=1000)
        conn.commit()

    return {
        "inserted": total_calls,
        "batchId": batch_id,
        "start_at_utc": start_at.isoformat(),
        "dst_country_iso2": dst_country_iso2,
        "gw_names": gw_names,
        "operator_counts": operator_counts,
        "calling_profile_counts": calling_counts,
    }