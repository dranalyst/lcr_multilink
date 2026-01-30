from sqlalchemy import Column, Integer, String
from sqlalchemy.sql.sqltypes import DateTime

import phonenumbers
import pycountry
from phonenumbers import carrier
from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from utils.normalize_msisdn import normalize_msisdn



class InboundLogs(Base):
    __tablename__ = "inbound_cdr_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    aNum = Column("a_num", String(32), nullable=False)             # Caller (raw)
    normalized_a_num = Column(String(32), nullable=True)           # Standardized E.164 number
    bNum = Column("b_num", String(32), nullable=False)             # Callee (user)
    starttime = Column(DateTime(timezone=True), nullable=False)
    duration = Column(Integer, nullable=False)
    status = Column(String, nullable=False)

    # 🌍 Derived metadata
    a_country = Column(String(100), nullable=False, default="Unknown")
    a_operator_name = Column(String(100), nullable=False, default="Unknown")
    b_country = Column(String(100), nullable=False, default="Unknown")
    b_operator_name = Column(String(100), nullable=False, default="Unknown")

    # def _country_name_to_iso2_fast(country_name: str | None) -> str | None:
    #     if not country_name:
    #         return None
    #
    #     name = country_name.strip()
    #     if not name:
    #         return None
    #
    #     # ✅ FAST PATH: exact name match (O(1)-ish)
    #     c = pycountry.countries.get(name=name)
    #     if c:
    #         return c.alpha_2
    #
    #     # ✅ fallback (rare): supports alt spellings like "Cote d'Ivoire"
    #     try:
    #         return pycountry.countries.lookup(name).alpha_2
    #     except LookupError:
    #         return None


    def __init__(self, **kwargs):
        """
        Automatically populate:
         - normalized_a_num (E.164)
         - a_country, a_operator_name derived from normalized number
         - b_country, b_operator_name from bNum
        """
        super().__init__(**kwargs)

        a_num = kwargs.get("aNum")
        b_num = kwargs.get("bNum")


        # --- Normalize aNum ---

        if b_num:
            try:
                iso2 = phonenumbers.region_code_for_number(phonenumbers.parse(f"+{str(b_num).lstrip('+')}", None))
            except Exception:
                iso2 = "XX"

        if a_num:
            self.normalized_a_num = normalize_msisdn(a_num, iso2) or a_num
        else:
            self.normalized_a_num = None


        if self.normalized_a_num:
            try:
                parsed_norm = phonenumbers.parse(self.normalized_a_num, None)
                iso2_a = phonenumbers.region_code_for_number(parsed_norm)
                country_a = pycountry.countries.get(alpha_2=iso2_a)
                self.a_country = country_a.name if country_a else "Unknown"
                self.a_operator_name = carrier.name_for_number(parsed_norm, "en") or "Unknown"
            except Exception:
                self.a_country = "Unknown"
                self.a_operator_name = "Unknown"
        else:
            self.a_country = "Unknown"
            self.a_operator_name = "Unknown"


        # --- Derive bNum info ---
        if b_num:
            try:
                parsed_b = phonenumbers.parse(b_num, None)
                iso2_b = phonenumbers.region_code_for_number(parsed_b)
                country_b = pycountry.countries.get(alpha_2=iso2_b)
                self.b_country = country_b.name if country_b else "Unknown"
                self.b_operator_name = carrier.name_for_number(parsed_b, "en") or "Unknown"
            except Exception:
                self.b_country = "Unknown"
                self.b_operator_name = "Unknown"
        else:
            self.b_country = "Unknown"
            self.b_operator_name = "Unknown"
