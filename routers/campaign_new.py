# routers/campaign_new.py
from __future__ import annotations

import os
from typing import List, Optional, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, conint, confloat

from scripts.schedule_campaign_new import (
    schedule_campaign,
    CallingProfile,
    OperatorWeight,
)

# ✅ import the correct function
from scripts.schedule_phone_campaign import schedule_phone_campaign

from models.phoneuser import PhoneUsers
from .auth import get_current_user

router = APIRouter(prefix="/campaigns", tags=["campaigns"], dependencies=[])


# ---------------------------
# Existing /new_campaign
# ---------------------------

class CallingProfileIn(BaseModel):
    country_iso2: str = Field(..., min_length=2, max_length=2, description="ISO2 like ES, FR, GH")
    weight: confloat(gt=0)


class OperatorWeightIn(BaseModel):
    operator_name: str = Field(..., min_length=1, max_length=100, description="Must match af_gateways.operator_name")
    weight: confloat(gt=0)


class NewCampaignRequest(BaseModel):
    total_calls_per_day: conint(gt=0, le=100000) = 100

    dst_country_iso2: str = Field(..., min_length=2, max_length=2)
    dst_operator_mix: List[OperatorWeightIn]
    gw_names: List[str] = Field(..., min_length=1)

    calling_profiles: List[CallingProfileIn]

    calling_operator_choices: Optional[Dict[str, List[str]]] = None

    call_provider: str = Field(default="commpeak", max_length=50)

    # optional: force same caller ID for all scheduled calls
    forced_a_num: Optional[str] = Field(default=None, max_length=25)

    start_hour_local: conint(ge=0, le=23) = 8
    end_hour_local: conint(ge=1, le=24) = 23

    expire_at_iso: Optional[str] = None
    global_spacing_sec: conint(ge=0, le=3600) = 1


@router.post("/new_campaign", summary="Create/overwrite next 2-week campaign batch (calls-per-day)")
async def new_campaign(req: NewCampaignRequest):
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not set on the server")

    try:
        return schedule_campaign(
            dsn=dsn,
            total_calls_per_day=req.total_calls_per_day,
            calling_profiles=[
                CallingProfile(country_iso2=p.country_iso2, weight=float(p.weight))
                for p in req.calling_profiles
            ],
            dst_country_iso2=req.dst_country_iso2,
            dst_operator_mix=[
                OperatorWeight(operator_name=o.operator_name, weight=float(o.weight))
                for o in req.dst_operator_mix
            ],
            gw_names=req.gw_names,
            start_hour_local=req.start_hour_local,
            end_hour_local=req.end_hour_local,
            expire_at_iso=req.expire_at_iso,
            global_spacing_sec=req.global_spacing_sec,
            calling_operator_choices=req.calling_operator_choices,
            call_provider=req.call_provider,
            forced_a_num=req.forced_a_num,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scheduling failed: {e}")


# ---------------------------
# /phone_campaign (NO AUTH)
# ---------------------------

class PhoneCampaignRequest(BaseModel):
    total_calls: conint(gt=0, le=100000) = 100

    # ✅ REQUIRED: handset that will later sync & place the calls
    a_num: str = Field(..., min_length=5, max_length=25, description="Origin handset MSISDN")

    dst_country_iso2_list: List[str] = Field(
        ..., min_length=1, description="List of ISO2 like ['GH','NG','CI']"
    )

    # optional weights: {"GH": 0.5, "NG": 0.3}
    dst_country_weights: Optional[Dict[str, float]] = None

    # gateway selection
    gateway_name: Optional[str] = None
    gw_names: Optional[List[str]] = None

    # avoid repeating same MSISDNs
    distinct_lookback: conint(ge=0, le=100000) = 2000

    # routing metadata
    call_provider: str = Field(default="commpeak", max_length=50)
    # batchId: str = Field(default=None, max_length=10)

    is_asterisk_engine: conint(ge=0, le=1) = 0

    start_hour_local: conint(ge=0, le=23) = 8
    end_hour_local: conint(ge=1, le=24) = 23
    global_spacing_sec: conint(ge=0, le=3600) = 1

    # expiry window
    expire_in_minutes: conint(ge=1, le=1440) = 120


@router.post(
    "/phone_campaign",
    summary="Create phone campaign schedule intents (no auth, no scheduled_time)"
)
async def phone_campaign(req: PhoneCampaignRequest):
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL is not set on the server",
        )

    dst_list = [c.strip().upper() for c in req.dst_country_iso2_list if c.strip()]
    if not dst_list:
        raise HTTPException(status_code=400, detail="dst_country_iso2_list is empty")

    try:
        return schedule_phone_campaign(
            dsn=dsn,
            total_calls=req.total_calls,
            a_num=req.a_num,                         # ✅ explicit handset
            dst_country_iso2_list=dst_list,
            dst_country_weights=req.dst_country_weights,
            gateway_name=req.gateway_name,
            gw_names=req.gw_names,
            distinct_lookback=req.distinct_lookback,
            call_provider=req.call_provider,
            # batch_id=req.batchId,
            is_asterisk_engine=req.is_asterisk_engine,
            expire_in_minutes=req.expire_in_minutes,
            start_hour_local=req.start_hour_local,
            end_hour_local=req.end_hour_local,
            global_spacing_sec=req.global_spacing_sec,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scheduling failed: {e}")


