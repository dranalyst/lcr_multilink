from typing import Optional, Tuple
import phonenumbers
from phonenumbers import carrier
import pycountry

from utils.phone_country_tools import extract_country_and_operator

UNKNOWN = "Unknown"


def enrich_msisdn(msisdn: Optional[str]) -> Tuple[str, str, str, str]:
    """
    Returns:
      (country_iso2, country_name, country_dial_code, operator_name)
    """
    if not msisdn or not isinstance(msisdn, str):
        return "--", UNKNOWN, "+++", UNKNOWN

    s = msisdn.strip()
    if not s.startswith("+"):
        if s.startswith("00"):
            s = "+" + s[2:]
        else:
            s = "+" + s

    try:
        parsed = phonenumbers.parse(s, None)

        iso2 = phonenumbers.region_code_for_number(parsed) or "--"
        country_name, operator_name = extract_country_and_operator(s)

        dial_code = f"+{parsed.country_code}" if parsed.country_code else "+++"

        return iso2, country_name, dial_code, operator_name

    except Exception:
        return "--", UNKNOWN, "+++", UNKNOWN