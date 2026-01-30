from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, conint, confloat

from scripts.schedule_campaign import (
    schedule_campaign,
    CallingProfile,
    OperatorWeight,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CallingProfileIn(BaseModel):
    country_iso2: str = Field(..., min_length=2, max_length=2, description="ISO2 like ES, FR, GH")
    operator_name: str = Field(..., min_length=1, max_length=100)
    weight: confloat(gt=0)  # positive


class OperatorWeightIn(BaseModel):
    operator_name: str = Field(..., min_length=1, max_length=100)
    weight: confloat(gt=0)  # positive


class ScheduleCampaignRequest(BaseModel):
    total_calls: conint(gt=0, le=100000) = 100
    start_at_iso: Optional[str] = Field(
        default=None,
        description="ISO datetime. If omitted => now+2min (and gateway busy-until rule still applies).",
    )
    calling_profiles: List[CallingProfileIn]
    dst_country_iso2: str = Field(..., min_length=2, max_length=2)
    dst_operator_mix: List[OperatorWeightIn]
    gw_names: List[str] = Field(..., min_length=1, description="e.g. ['gh_gw1','gh_gw2']")
    global_spacing_sec: conint(ge=0, le=3600) = 5


@router.post("/schedule", summary="Schedule a call campaign (inserts into schedule table)")
async def schedule_campaign_endpoint(req: ScheduleCampaignRequest):
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not set on the server")

    try:
        result = schedule_campaign(
            dsn=dsn,
            total_calls=req.total_calls,
            start_at_iso=req.start_at_iso,
            calling_profiles=[
                CallingProfile(
                    country_iso2=p.country_iso2,
                    operator_name=p.operator_name,
                    weight=float(p.weight),
                )
                for p in req.calling_profiles
            ],
            dst_country_iso2=req.dst_country_iso2,
            dst_operator_mix=[
                OperatorWeight(
                    operator_name=o.operator_name,
                    weight=float(o.weight),
                )
                for o in req.dst_operator_mix
            ],
            gw_names=req.gw_names,
            global_spacing_sec=req.global_spacing_sec,
        )
        return result

    except ValueError as e:
        # validation / missing operator pools etc.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scheduling failed: {e}")