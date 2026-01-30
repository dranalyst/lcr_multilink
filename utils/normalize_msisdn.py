import re
import phonenumbers
from phonenumbers import NumberParseException


def normalize_msisdn(
    src: str | None,
    iso2_country: str | None,
) -> str | None:
    """
    Normalize any inbound SRC MSISDN into E.164 format (+CCCXXXXXXXXX).

    Inputs:
      - src: raw source number from CDR (e.g. '0247123456', '00233247123456', '+233247123456')
      - iso2_country: destination country ISO2 (e.g. 'GH', 'NG')

    Returns:
      - '+E164' formatted MSISDN
      - None if cannot be normalized safely
    """

    if not src:
        return None

    s = str(src).strip()

    # remove spaces, dashes, brackets
    s = re.sub(r"[^\d+]", "", s)

    if not s:
        return None

    # 1️⃣ Try strict parsing first (best case)
    try:
        if s.startswith("+"):
            p = phonenumbers.parse(s, None)
        else:
            p = phonenumbers.parse(s, iso2_country.upper() if iso2_country else None)

        if phonenumbers.is_valid_number(p):
            return phonenumbers.format_number(
                p, phonenumbers.PhoneNumberFormat.E164
            )
    except NumberParseException:
        pass

    # 2️⃣ Handle international prefix "00"
    if s.startswith("00"):
        try:
            p = phonenumbers.parse("+" + s[2:], None)
            if phonenumbers.is_valid_number(p):
                return phonenumbers.format_number(
                    p, phonenumbers.PhoneNumberFormat.E164
                )
        except NumberParseException:
            pass

    # 3️⃣ Handle local numbers like 024xxxxxxx (Ghana-style)
    if iso2_country:
        try:
            cc = phonenumbers.country_code_for_region(iso2_country.upper())
            if cc:
                # strip leading trunk 0 if present
                if s.startswith("0"):
                    s = s[1:]

                candidate = f"+{cc}{s}"
                p = phonenumbers.parse(candidate, None)
                if phonenumbers.is_valid_number(p):
                    return phonenumbers.format_number(
                        p, phonenumbers.PhoneNumberFormat.E164
                    )
        except Exception:
            pass

    # ❌ Could not normalize safely
    return None