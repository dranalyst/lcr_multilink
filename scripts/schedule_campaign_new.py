import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, time, date
from typing import Any, Optional, Sequence

import psycopg2
from psycopg2.extras import execute_values

import phonenumbers
from phonenumbers import PhoneNumberType, carrier
from phonenumbers import timezone as pn_tz
from zoneinfo import ZoneInfo

import pycountry


# ==========================
# CONSTANTS
# ==========================
CALL_GAP_MIN = timedelta(minutes=3)
CALL_GAP_MAX = timedelta(minutes=5)
FORCED_START_OFFSET = timedelta(minutes=10)
BATCH_WINDOW_DAYS = 7

DEFAULT_START_HOUR_LOCAL = 6
DEFAULT_END_HOUR_LOCAL = 23


# ==========================
# DATA MODELS
# ==========================
@dataclass(frozen=True)
class CallingProfile:
    country_iso2: str
    weight: float


@dataclass(frozen=True)
class OperatorWeight:
    operator_name: str
    weight: float


# ==========================
# HELPERS
# ==========================
def iso2_to_country_name(iso2: str) -> str:
    c = pycountry.countries.get(alpha_2=iso2.upper()) if iso2 and iso2 != "--" else None
    return c.name if c else "Unknown"


def largest_remainder_counts(weights: Sequence[tuple[str, float]], total: int) -> dict[str, int]:
    raw = [(k, float(w) * total) for k, w in weights]
    base = {k: int(v) for k, v in raw}
    remainder = total - sum(base.values())

    fracs = sorted(((v - int(v), k) for k, v in raw), reverse=True)
    for i in range(remainder):
        base[fracs[i][1]] += 1
    return base


def expand_shuffle(counts: dict[str, int]) -> list[str]:
    items: list[str] = []
    for k, c in counts.items():
        items.extend([k] * c)
    random.shuffle(items)
    return items


def _infer_zoneinfo_from_msisdns(msisdns: list[str]) -> ZoneInfo:
    for m in msisdns:
        try:
            s = m.strip()
            if not s.startswith("+"):
                s = "+" + s
            parsed = phonenumbers.parse(s, None)
            tzs = pn_tz.time_zones_for_number(parsed)
            if tzs:
                return ZoneInfo(tzs[0])
        except Exception:
            continue
    return ZoneInfo("UTC")


def _local_window_to_utc_range(
    local_day: date,
    start_hour_local: int,
    end_hour_local: int,
    dst_tz: ZoneInfo,
) -> tuple[datetime, datetime]:
    start_hour_local = int(start_hour_local)
    end_hour_local = int(end_hour_local)

    start_local = datetime.combine(local_day, time(start_hour_local, 0, 0), tzinfo=dst_tz)
    end_local = datetime.combine(local_day, time(end_hour_local, 0, 0), tzinfo=dst_tz)

    if end_local <= start_local:
        end_local = start_local + timedelta(hours=15)

    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _random_time_in_range(start_utc: datetime, end_utc: datetime) -> datetime:
    if end_utc <= start_utc:
        return start_utc
    delta = (end_utc - start_utc).total_seconds()
    return start_utc + timedelta(seconds=(random.random() * delta))


def _random_anum_candidate_for_iso2(country_iso2: str) -> str:
    """
    Generate a plausible E.164 A-number for a given ISO2.
    Improved: keeps a longer prefix and retries until phonenumbers 'carrier' returns a non-empty name,
    which avoids lots of 'Unknown' for GB and others.
    """
    iso2 = (country_iso2 or "--").upper()

    if iso2 == "--":
        return "+999" + "".join(str(random.randint(0, 9)) for _ in range(10))

    # Prefer MOBILE example for the region
    example = None
    try:
        example = phonenumbers.example_number_for_type(iso2, PhoneNumberType.MOBILE)
    except Exception:
        example = None

    # Fallback if metadata isn't available
    if not example:
        try:
            cc = phonenumbers.country_code_for_region(iso2) or 999
        except Exception:
            cc = 999
        return f"+{cc}" + "".join(str(random.randint(0, 9)) for _ in range(10))

    cc = example.country_code
    nsn = phonenumbers.national_significant_number(example)  # digits only

    # Keep a longer prefix so we stay inside "known" ranges.
    # GB is particularly sensitive; keep at least 5 digits of NSN.
    keep = 5 if iso2 == "GB" else min(6, max(3, len(nsn) - 4))
    prefix = nsn[:keep]
    rest_len = max(0, len(nsn) - keep)

    # Try a few candidates until the carrier DB recognizes the prefix
    for _ in range(30):
        rest = "".join(str(random.randint(0, 9)) for _ in range(rest_len))
        candidate = f"+{cc}{prefix}{rest}"
        try:
            p = phonenumbers.parse(candidate, None)
            if phonenumbers.is_valid_number(p):
                op = (carrier.name_for_number(p, "en") or "").strip()
                if op:
                    return candidate
        except Exception:
            pass

    # If no recognized carrier found quickly, return a plausible number anyway
    rest = "".join(str(random.randint(0, 9)) for _ in range(rest_len))
    return f"+{cc}{prefix}{rest}"


def _operator_for_number_e164(num_e164: str) -> str:
    try:
        parsed = phonenumbers.parse(num_e164, None)
        op = carrier.name_for_number(parsed, "en") or ""
        return op.strip()
    except Exception:
        return ""


def _random_anum_for_iso2_with_operator_choices(
    country_iso2: str,
    allowed_ops: Optional[list[str]],
    max_tries: int = 50,
) -> tuple[str, Optional[str]]:
    """
    If allowed_ops is provided, try to generate a number whose carrier name matches one.
    Returns: (aNum, matched_operator_or_None)

    NOTE: carrier mapping coverage varies by country/provider; this is best-effort.
    """
    if not allowed_ops:
        n = _random_anum_candidate_for_iso2(country_iso2)
        return n, None

    # normalize allowed list for comparison
    allowed_norm = {x.strip().lower() for x in allowed_ops if x and x.strip()}
    if not allowed_norm:
        n = _random_anum_candidate_for_iso2(country_iso2)
        return n, None

    last_num = None
    last_op = None
    for _ in range(max_tries):
        n = _random_anum_candidate_for_iso2(country_iso2)
        op = _operator_for_number_e164(n)
        last_num, last_op = n, op
        if op and op.strip().lower() in allowed_norm:
            return n, op

    # fallback: return last generated even if operator couldn't be matched
    return (last_num or _random_anum_candidate_for_iso2(country_iso2)), (last_op or None)


def _normalize_msisdn(msisdn: str) -> str:
    s = (msisdn or "").strip()
    if not s:
        return ""
    if s.startswith("+"):
        return s
    if s.startswith("00"):
        return "+" + s[2:]
    return s  # keep digits if stored without plus



def _random_bnum_gap() -> timedelta:
    """
    Random timedelta between CALL_GAP_MIN and CALL_GAP_MAX (inclusive-ish).
    """
    lo = int(CALL_GAP_MIN.total_seconds())
    hi = int(CALL_GAP_MAX.total_seconds())
    return timedelta(seconds=random.randint(lo, hi))

# ==========================
# MAIN SCHEDULER
# ==========================
def schedule_campaign(
    *,
    dsn: str,
    total_calls_per_day: int,
    calling_profiles: list[CallingProfile],
    dst_country_iso2: str,
    dst_operator_mix: list[OperatorWeight],
    gw_names: list[str],
    call_provider: str,
    start_hour_local: int = DEFAULT_START_HOUR_LOCAL,
    end_hour_local: int = DEFAULT_END_HOUR_LOCAL,
    expire_at_iso: Optional[str] = None,
    global_spacing_sec: int = 1,
    calling_operator_choices: Optional[dict[str, list[str]]] = None,  # NEW
    forced_a_num: Optional[str] = None,
) -> dict[str, Any]:
    if total_calls_per_day <= 0:
        raise ValueError("total_calls_per_day must be > 0")
    if not calling_profiles:
        raise ValueError("calling_profiles is required")
    if not dst_operator_mix:
        raise ValueError("dst_operator_mix is required")
    if not gw_names:
        raise ValueError("gw_names is required")
    if not call_provider:
        raise ValueError("call_provider is required")

    now_utc = datetime.now(timezone.utc)

    # Normalize forced caller ID once
    if forced_a_num:
        forced_a_num = forced_a_num.strip()
        if not forced_a_num.startswith("+"):
            forced_a_num = "+" + forced_a_num

    # expiry default: now + 1 year
    if expire_at_iso:
        expire_at = datetime.fromisoformat(expire_at_iso)
        if expire_at.tzinfo is None:
            expire_at = expire_at.replace(tzinfo=timezone.utc)
        expire_at = expire_at.astimezone(timezone.utc)
    else:
        expire_at = now_utc + timedelta(days=365)

    forced_start_utc = now_utc + FORCED_START_OFFSET
    global_spacing = timedelta(seconds=max(0, int(global_spacing_sec)))

    # per-day exact counts
    calling_weights = [(p.country_iso2.upper(), float(p.weight)) for p in calling_profiles]
    operator_weights = [(o.operator_name, float(o.weight)) for o in dst_operator_mix]

    calling_counts_day = largest_remainder_counts(calling_weights, total_calls_per_day)
    operator_counts_day = largest_remainder_counts(operator_weights, total_calls_per_day)

    b_country_name = iso2_to_country_name(dst_country_iso2)
    dst_key = dst_country_iso2.lower()

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        # Spec (1): overwrite only the SAME window (or overlapping window) >= now+10m
        cur.execute(
            """
            DELETE FROM public.schedule s
            USING public.af_gateways g
            WHERE s."bNum" = g.msisdn
              AND g.gw_name = ANY(%s)
              AND g.call_direction = false
              AND g.sip_recipient = true
              AND g.active_status = true
              AND s.scheduled_time >= %s
              AND s.status = 0
              AND s.is_asterisk_engine = 1
              AND s."bCountry" = %s
              AND int4range(s.start_hour_local, s.end_hour_local, '[)') &&
                  int4range(%s, %s, '[)')
            """,
            (
                gw_names,
                forced_start_utc,
                b_country_name,
                int(start_hour_local),
                int(end_hour_local),
            ),
        )
        overwritten = cur.rowcount

        # batch counter
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS public.campaign_batch_counter (
              dst_country_iso2 text NOT NULL,
              call_provider varchar(50) NOT NULL,
              last_seq integer NOT NULL DEFAULT 0,
              CONSTRAINT campaign_batch_counter_pk
              PRIMARY KEY (dst_country_iso2, call_provider)
            )
            """
        )
        cur.execute(
            """
            INSERT INTO public.campaign_batch_counter (dst_country_iso2, call_provider, last_seq)
            VALUES (%s, %s, 1)
            ON CONFLICT (dst_country_iso2, call_provider)
            DO UPDATE SET last_seq = campaign_batch_counter.last_seq + 1
            RETURNING last_seq
            """,
            (dst_key,call_provider.lower().strip()),
        )
        seq = cur.fetchone()[0]
        provider_key = call_provider.lower().strip()
        batch_id = f"{dst_key}_{provider_key}_{seq:04d}"


        # ----------------------------------------------------
        # ✅ Pre-check: block creating a NEW batch that overlaps
        # same bCountry window for pending Asterisk schedules
        # (but allow same batchId, which your constraint permits)
        # ----------------------------------------------------
        cur.execute(
            """
            SELECT 1
            FROM public.schedule
            WHERE "bCountry" = %s
              AND status = 0
              AND is_asterisk_engine = 1
              AND "batchId" <> %s
              AND int4range(start_hour_local, end_hour_local, '[)') &&
                  int4range(%s, %s, '[)')
            LIMIT 1
            """,
            (b_country_name, batch_id, int(start_hour_local), int(end_hour_local)),
        )
        if cur.fetchone():
            raise ValueError(
                f"Overlapping window not allowed for {b_country_name} "
                f"({start_hour_local}-{end_hour_local}) with an existing pending batch. "
                f"Pick another window or complete/cancel the existing pending batch."
            )

        # destination pools
        # destination pools
        cur.execute(
            """
            SELECT operator_name, msisdn, gw_name
            FROM public.af_gateways
            WHERE gw_name = ANY(%s)
              AND call_direction = false
              AND sip_recipient = true
              AND active_status = true
              AND country_iso2 = %s
              AND msisdn IS NOT NULL AND msisdn <> ''
              AND operator_name IS NOT NULL AND operator_name <> ''
            """,
            (gw_names, dst_country_iso2),
        )

        pools: dict[str, list[tuple[str, str]]] = {}
        all_msisdns: list[str] = []

        for op, msisdn, gw_name in cur.fetchall():
            ms = str(msisdn).strip()
            gw = str(gw_name).strip()
            if not ms or not gw:
                continue
            pools.setdefault(op, []).append((ms, gw))
            all_msisdns.append(ms)

        missing_ops = [o for o in operator_counts_day if o not in pools or not pools[o]]
        if missing_ops:
            raise ValueError(f"No destination MSISDNs for operators: {missing_ops}")

        dst_tz = _infer_zoneinfo_from_msisdns(all_msisdns)

        # respect already scheduled calls before forced_start_utc
        bnums_next_allowed: dict[str, datetime] = {}
        cur.execute(
            """
            WITH gw_msisdn AS (
              SELECT msisdn
              FROM public.af_gateways
              WHERE gw_name = ANY(%s)
                AND call_direction = false
                AND sip_recipient = true
                AND active_status = true
                AND country_iso2 = %s
                AND msisdn IS NOT NULL AND msisdn <> ''
            )
            SELECT s."bNum", max(s.scheduled_time)
            FROM public.schedule s
            JOIN gw_msisdn g ON g.msisdn = s."bNum"
            WHERE s.scheduled_time < %s
            GROUP BY s."bNum"
            """,
            (gw_names, dst_country_iso2, forced_start_utc),
        )
        for bnum, mx in cur.fetchall():
            if mx:
                if mx.tzinfo is None:
                    mx = mx.replace(tzinfo=timezone.utc)
                bnums_next_allowed[str(bnum)] = mx + _random_bnum_gap()

        forced_start_local = forced_start_utc.astimezone(dst_tz)
        start_local_date = forced_start_local.date()

        rows = []
        inserted_min_utc: Optional[datetime] = None
        inserted_max_utc: Optional[datetime] = None

        for d in range(BATCH_WINDOW_DAYS):
            day_local = start_local_date + timedelta(days=d)

            calling_plan = expand_shuffle(calling_counts_day)      # list of iso2
            operator_plan = expand_shuffle(operator_counts_day)    # list of dst operator_name

            day_start_utc, day_end_utc = _local_window_to_utc_range(
                day_local, start_hour_local, end_hour_local, dst_tz
            )
            if d == 0 and day_start_utc < forced_start_utc:
                day_start_utc = forced_start_utc

            daily_times = [_random_time_in_range(day_start_utc, day_end_utc) for _ in range(total_calls_per_day)]
            daily_times.sort()

            t_cursor = day_start_utc
            for i in range(total_calls_per_day):
                a_iso2 = calling_plan[i]

                if forced_a_num:
                    # ✅ Force same caller ID for all scheduled calls
                    a_num = forced_a_num
                    a_country = iso2_to_country_name(a_iso2)
                    matched_op = None
                else:
                    allowed_ops = None
                    if calling_operator_choices:
                        allowed_ops = calling_operator_choices.get(a_iso2.upper()) or calling_operator_choices.get(
                            a_iso2.lower())

                    a_num, matched_op = _random_anum_for_iso2_with_operator_choices(
                        a_iso2, allowed_ops
                    )
                    a_country = iso2_to_country_name(a_iso2)

                dst_op = operator_plan[i]
                b_num, destination_gw = random.choice(pools[dst_op])
                b_num_norm = _normalize_msisdn(b_num)

                candidate = max(daily_times[i], t_cursor)
                t_cursor = candidate + global_spacing

                allowed = bnums_next_allowed.get(b_num_norm, day_start_utc)
                sched_time = max(candidate, allowed)
                bnums_next_allowed[b_num_norm] = sched_time + _random_bnum_gap()

                rows.append((
                    batch_id,
                    a_num,
                    a_country,
                    b_num_norm,
                    b_country_name,
                    dst_op,
                    0,
                    1,
                    sched_time,
                    0,
                    0,
                    expire_at,
                    call_provider,
                    destination_gw,
                    start_hour_local,
                    end_hour_local,
                ))

                inserted_min_utc = sched_time if inserted_min_utc is None else min(inserted_min_utc, sched_time)
                inserted_max_utc = sched_time if inserted_max_utc is None else max(inserted_max_utc, sched_time)

        sql = """
        INSERT INTO public.schedule
          ("batchId","aNum","aCountry","bNum","bCountry",
           b_operator_name,status,is_asterisk_engine,
           scheduled_time,attempts,max_retries,expire_at,
           call_provider,destination_gw, start_hour_local,end_hour_local)
        VALUES %s
        """
        execute_values(cur, sql, rows, page_size=2000)
        conn.commit()

    batch_end = inserted_max_utc if inserted_max_utc else forced_start_utc
    next_batch_recommended_at = (batch_end - timedelta(days=7)).astimezone(timezone.utc)

    return {
        # "batchId": batch_id,
        "overwritten_deleted_rows": overwritten,
        "dst_country_iso2": dst_country_iso2,
        "dst_timezone": str(dst_tz),
        "calls_per_day": total_calls_per_day,
        "days_inserted": BATCH_WINDOW_DAYS,
        "inserted": len(rows),
        "window_local": {"start_hour": start_hour_local, "end_hour": end_hour_local},
        "expire_at_utc": expire_at.isoformat(),
        "scheduled_min_utc": inserted_min_utc.isoformat() if inserted_min_utc else None,
        "scheduled_max_utc": inserted_max_utc.isoformat() if inserted_max_utc else None,
        "next_batch_recommended_at_utc": next_batch_recommended_at.isoformat(),
        "operator_counts_per_day": operator_counts_day,
        "calling_profile_counts_per_day": calling_counts_day,
        "gw_names": gw_names,
    }