# scripts/schedule_phone_campaign.py
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, time, date
from typing import Dict, List, Optional

import psycopg2

import pycountry
import phonenumbers
from phonenumbers import timezone as pn_tz
from zoneinfo import ZoneInfo


FORCED_START_OFFSET = timedelta(minutes=10)
DEFAULT_START_HOUR_LOCAL = 8
DEFAULT_END_HOUR_LOCAL = 23


@dataclass
class CandidateNumber:
    msisdn: str
    operator_name: Optional[str] = None
    gw_name: Optional[str] = None


def iso2_to_country_name(iso2: str) -> str:
    c = pycountry.countries.get(alpha_2=(iso2 or "").upper())
    return c.name if c else "Unknown"


def _pick_weighted(items: List[str], weights: Optional[Dict[str, float]]) -> str:
    if not weights:
        return random.choice(items)

    w = [float(weights.get(x, 1.0)) for x in items]
    if sum(w) <= 0:
        return random.choice(items)
    return random.choices(items, weights=w, k=1)[0]


def _load_candidate_numbers(
    cur,
    *,
    gw_name: str,
    country_iso2: Optional[str] = None,
) -> List[CandidateNumber]:
    sql = """
        SELECT msisdn, operator_name, gw_name
        FROM public.af_gateways
        WHERE call_direction = false
          AND sip_recipient = false      -- ✅ FIXED
          AND active_status = true
          AND gw_name = %s
    """
    params = [gw_name]

    if country_iso2:
        sql += " AND country_iso2 = %s"
        params.append(country_iso2)

    sql += " ORDER BY random()"

    cur.execute(sql, tuple(params))
    rows = cur.fetchall()

    # ✅ NEW: explicit error if nothing is available
    if not rows:
        raise ValueError(
            f"No recipient number is currently available for mobile GSM calls to '{iso2_to_country_name(country_iso2)}'. Please try later."
        )

    return [CandidateNumber(msisdn=r[0], operator_name=r[1]) for r in rows]



def _pick_gateway(gateway_name: Optional[str], gw_names: Optional[List[str]]) -> Optional[str]:
    if gateway_name:
        return gateway_name
    if gw_names:
        return random.choice(gw_names)
    return None


def _infer_zoneinfo_from_msisdns(msisdns: list[str]) -> ZoneInfo:
    for m in msisdns:
        try:
            s = (m or "").strip()
            if not s:
                continue
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


def _normalize_msisdn_e164(msisdn: str) -> str:
    s = (msisdn or "").strip()
    if not s:
        return ""
    if s.startswith("+"):
        return s
    if s.startswith("00"):
        return "+" + s[2:]
    return "+" + s  # enforce + for GSM storage


def _normalize_msisdn_digits(msisdn: str) -> str:
    # for Asterisk/CommPeak dialplan that expects digits (no '+')
    s = (msisdn or "").strip()
    if not s:
        return ""
    s = s.replace(" ", "").replace("+", "")
    if s.startswith("00"):
        s = s[2:]
    return s



def schedule_phone_campaign(
    dsn: str,
    total_calls: int,
    a_num: str,
    dst_country_iso2_list: List[str],
    dst_country_weights: Optional[Dict[str, float]],
    gateway_name: Optional[str],
    gw_names: Optional[List[str]],
    distinct_lookback: int,
    call_provider: str,
    # batch_id: str,
    is_asterisk_engine: int,   # 👈 NEW (0 or 1)
    expire_in_minutes: int = 120,
    start_hour_local: int = DEFAULT_START_HOUR_LOCAL,
    end_hour_local: int = DEFAULT_END_HOUR_LOCAL,
    global_spacing_sec: int = 1,
) -> Dict[str, object]:
    """
    Creates PHONE schedule intents into public.schedule.

    IMPORTANT:
    - Does NOT set scheduled_time (Android will decide later)
    - Inserts:
        "batchId", "aNum", "bNum",
        is_asterisk_engine=0,
        expire_at=now+2h,
        destination_gw,
        call_provider
    """

    if total_calls <= 0:
        raise ValueError("total_calls must be > 0")
    if not a_num:
        raise ValueError("a_num is required")
    if not dst_country_iso2_list:
        raise ValueError("dst_country_iso2_list cannot be empty")
    if not call_provider:
        raise ValueError("call_provider is required (e.g. commpeak, gsm)")

    # ✅ Android-only script
    if is_asterisk_engine != 0:
        raise ValueError("schedule_phone_campaign is Android-only: is_asterisk_engine must be 0")

    call_provider = "gsm"  # ✅ always for Android schedules
    provider_key = call_provider.lower().strip()

    # ✅ gateway set to load from
    gw_list = []
    if gateway_name:
        gw_list = [gateway_name]
    elif gw_names:
        gw_list = list(gw_names)

    if not gw_list:
        raise ValueError("gateway_name or gw_names is required to select candidate numbers from af_gateways")

    created = 0
    failed = 0

    now_utc = datetime.now(timezone.utc)
    expire_at = now_utc + timedelta(minutes=int(expire_in_minutes))

    recent_msisdn: List[str] = []

    conn = psycopg2.connect(dsn)
    conn.autocommit = False


    try:
        with conn.cursor() as cur:

            # -----------------------------
            # AUTO batch_id (campaign_batch_counter)
            # -----------------------------
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

            dst_key = (
                dst_country_iso2_list[0].strip().lower()
                if len(dst_country_iso2_list) == 1
                else "multi"
            )

            cur.execute(
                """
                INSERT INTO public.campaign_batch_counter (dst_country_iso2, call_provider, last_seq)
                VALUES (%s, %s, 1)
                ON CONFLICT (dst_country_iso2, call_provider)
                DO UPDATE SET last_seq = campaign_batch_counter.last_seq + 1
                RETURNING last_seq
                """,
                (dst_key, provider_key),
            )
            seq = cur.fetchone()[0]
            batch_id = f"{dst_key}_{provider_key}_{seq:04d}"

            # ----------------------------------------------------
            # ✅ Pre-check: block creating a NEW batch that reuses
            # same bCountry window for pending Android schedules
            # (allow same batchId, block different batchId)
            # ----------------------------------------------------
            b_country_for_key = iso2_to_country_name(
                dst_country_iso2_list[0] if len(dst_country_iso2_list) == 1 else dst_country_iso2_list[0]
            )

            cur.execute(
                """
                SELECT 1
                FROM public.schedule
                WHERE "bCountry" = %s
                  AND status = 0
                  AND is_asterisk_engine = 0
                  AND "batchId" <> %s
                  AND int4range(start_hour_local, end_hour_local, '[)') =
                      int4range(%s, %s, '[)')
                LIMIT 1
                """,
                (b_country_for_key, batch_id, int(start_hour_local), int(end_hour_local)),
            )
            if cur.fetchone():
                raise ValueError(
                    f"Android window already has a pending batch for {b_country_for_key} "
                    f"({start_hour_local}-{end_hour_local}). Finish/cancel it or choose another window."
                )

            pool_by_country: Dict[str, List[CandidateNumber]] = {}

            for c in dst_country_iso2_list:
                cc = c.strip().upper()
                if not cc:
                    continue
                pool_by_country[cc] = []
                for gw in gw_list:
                    pool_by_country[cc].extend(_load_candidate_numbers(cur, gw_name=gw, country_iso2=cc))


            # ✅ NEW: infer destination timezone from candidate MSISDNs
            all_msisdns = []
            for cc, pool in pool_by_country.items():
                for cand in pool:
                    if cand.msisdn:
                        all_msisdns.append(str(cand.msisdn))

            dst_tz = _infer_zoneinfo_from_msisdns(all_msisdns)

            # ✅ NEW: build a single scheduling window (like schedule_campaign_new idea)
            now_utc = datetime.now(timezone.utc)
            forced_start_utc = now_utc + FORCED_START_OFFSET
            forced_start_local = forced_start_utc.astimezone(dst_tz)

            day_local = forced_start_local.date()
            day_start_utc, day_end_utc = _local_window_to_utc_range(
                day_local, start_hour_local, end_hour_local, dst_tz
            )

            # if today's window already passed, move to next day
            if forced_start_utc > day_end_utc:
                day_local = day_local + timedelta(days=1)
                day_start_utc, day_end_utc = _local_window_to_utc_range(
                    day_local, start_hour_local, end_hour_local, dst_tz
                )

            # ensure we don't schedule before forced_start_utc
            if day_start_utc < forced_start_utc:
                day_start_utc = forced_start_utc

            # generate scheduled times (sorted) and enforce global spacing
            global_spacing = timedelta(seconds=max(0, int(global_spacing_sec)))
            times = [_random_time_in_range(day_start_utc, day_end_utc) for _ in range(total_calls)]
            times.sort()

            t_cursor = day_start_utc


            for i in range(total_calls):
                dst_country = _pick_weighted(dst_country_iso2_list, dst_country_weights)
                dst_country = dst_country.strip().upper()

                pool = pool_by_country.get(dst_country, [])
                if not pool:
                    failed += 1
                    continue

                chosen = None
                for cand in pool:
                    if cand.msisdn not in recent_msisdn:
                        chosen = cand
                        break
                if chosen is None:
                    chosen = pool[0]


                # ✅ keep lookback consistent with stored format
                recent_msisdn.append(chosen.msisdn)
                if distinct_lookback > 0 and len(recent_msisdn) > distinct_lookback:
                    recent_msisdn = recent_msisdn[-distinct_lookback:]

                destination_gw = (chosen.gw_name or "").strip()  # ✅ real gw of that msisdn

                # ✅ NEW: scheduled time for this row + global spacing
                candidate = max(times[i], t_cursor)
                sched_time = candidate
                t_cursor = sched_time + global_spacing

                # ✅ FIX: normalize bNum depending on engine type
                if is_asterisk_engine == 0:
                    bnum_final = _normalize_msisdn_e164(chosen.msisdn)     # always +E164
                else:
                    bnum_final = _normalize_msisdn_digits(chosen.msisdn)  # digits only (no '+')

                b_country_name = iso2_to_country_name(dst_country)

                # ✅ Insert schedule intent (NO scheduled_time)
                cur.execute(
                    """
                    INSERT INTO public.schedule
                      (
                        "batchId",
                        "aNum",
                        "bNum",
                        "bCountry",
                        b_operator_name,
                        status,
                        is_asterisk_engine,
                        scheduled_time,
                        expire_at,
                        destination_gw,
                        call_provider,
                        start_hour_local,
                        end_hour_local
                      )
                    VALUES
                      (%s, %s, %s, %s, %s, 0, 0, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        batch_id,
                        a_num,
                        bnum_final,
                        b_country_name,
                        chosen.operator_name,
                        sched_time,
                        expire_at,
                        destination_gw,
                        call_provider,
                        int(start_hour_local),
                        int(end_hour_local),
                    ),
                )
                _new_id = cur.fetchone()[0]
                created += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "status": "ok",
        "created": created,
        "failed": failed,
        "total_requested": total_calls,
        "dst_countries": dst_country_iso2_list,
        "gateway_mode": ("fixed" if gateway_name else ("pool" if gw_names else "none")),
        "call_provider": call_provider,
        "is_asterisk_engine": is_asterisk_engine,
        "batchId": batch_id,
        "expire_in_minutes": expire_in_minutes,

        "dst_timezone": str(dst_tz),
        "window_local": {"start_hour": start_hour_local, "end_hour": end_hour_local},
        "scheduled_day_local": str(day_local),
    }