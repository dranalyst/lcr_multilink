import os
from pprint import pprint

from schedule_campaign import (
    schedule_campaign,
    CallingProfile,
    OperatorWeight,
)

# --- DATABASE ---
DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres@127.0.0.1:5432/testCaller"
)

# --- DRY RUN PARAMETERS ---
TOTAL_CALLS = 20

CALLING_PROFILES = [
    CallingProfile(country_iso2="ES", operator_name="Orange", weight=0.5),
    CallingProfile(country_iso2="FR", operator_name="Orange", weight=0.5),
]

DST_OPERATOR_MIX = [
    OperatorWeight(operator_name="MTN", weight=0.6),
    OperatorWeight(operator_name="Vodafone", weight=0.4),
]

GW_NAMES = ["gh_gw1", "gh_gw2"]

# Optional ISO datetime (None = now + 2 minutes)
START_AT_ISO = None
# Example:
# START_AT_ISO = "2025-12-23T15:00:00+01:00"

print("=== DRY RUN: scheduling campaign ===")

result = schedule_campaign(
    dsn=DSN,
    total_calls=TOTAL_CALLS,
    start_at_iso=START_AT_ISO,
    calling_profiles=CALLING_PROFILES,
    dst_country_iso2="GH",
    dst_operator_mix=DST_OPERATOR_MIX,
    gw_names=GW_NAMES,
    global_spacing_sec=5,
)

print("\n=== RESULT ===")
pprint(result)