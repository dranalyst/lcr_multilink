"""
Utility functions for extracting country and operator information
from phone numbers, using phonenumbers + pycountry.

Designed to be reused by:
 - Asterisk_ob_logs
 - Asterisk_ib_logs
 - outbound_cdr_logs, inbound_cdr_logs (if needed later)
"""

from typing import Tuple, Optional

import phonenumbers
from phonenumbers import carrier
import pycountry


UNKNOWN = "Unknown"


def extract_country_and_operator(number: Optional[str]) -> Tuple[str, str]:
    """
    Parse a phone number string and return:
      (country_name, operator_name)

    If parsing fails or number is empty, returns ("Unknown", "Unknown").
    """
    if not number or not isinstance(number, str):
        return UNKNOWN, UNKNOWN

    try:
        # Normalize: ensure it has a leading "+" if it looks like E.164 without plus.
        num_str = number.strip()
        if not num_str.startswith("+"):
            # Very light normalization – you can customize later if needed
            if num_str.startswith("00"):
                num_str = "+" + num_str.removeprefix("00")
            else:
                num_str = "+" + num_str

        parsed = phonenumbers.parse(num_str, None)

        # ISO2 region for the number
        iso2 = phonenumbers.region_code_for_number(parsed)
        if not iso2:
            return UNKNOWN, UNKNOWN

        # Country name
        country_obj = pycountry.countries.get(alpha_2=iso2)
        country_name = country_obj.name if country_obj else UNKNOWN

        # Operator name (may be empty string)
        operator_name = carrier.name_for_number(parsed, "en") or UNKNOWN

        return country_name, operator_name

    except Exception:
        # Any parsing issue → return Unknowns
        return UNKNOWN, UNKNOWN


def set_country_and_operator(
    obj: object,
    number_attr: str,
    country_attr: str,
    operator_attr: str,
) -> None:
    """
    Generic helper to populate country/operator fields on a SQLAlchemy model.

    Example usage in a model:
        set_country_and_operator(self, "src", "src_country", "src_operator_name")
        set_country_and_operator(self, "dst", "dst_country", "dst_operator_name")

    This reads getattr(self, number_attr) and writes:
        setattr(self, country_attr, <country_name>)
        setattr(self, operator_attr, <operator_name>)
    """
    number = getattr(obj, number_attr, None)
    country, operator_name = extract_country_and_operator(number)
    setattr(obj, country_attr, country)
    setattr(obj, operator_attr, operator_name)