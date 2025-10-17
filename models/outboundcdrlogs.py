import phonenumbers
import pycountry
from phonenumbers import carrier
from sqlalchemy import Column, Integer, String
from sqlalchemy.sql import func
from sqlalchemy.sql.sqltypes import DateTime
from database import Base

class OutboundLogs(Base):
    __tablename__ = "outbound_cdr_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    aNum = Column("a_num", String(32), nullable=False)   # maps to a_num
    bNum = Column("b_num", String(32), nullable=False)   # maps to b_num
    starttime = Column(DateTime(timezone=True), nullable=False)
    duration = Column(Integer, nullable=False)
    status = Column(String, nullable=False)

    # 🌍 Country & operator info
    a_country = Column(String(100), nullable=False, default="Unknown")
    a_operator_name = Column(String(100), nullable=False, default="Unknown")
    b_country = Column(String(100), nullable=False, default="Unknown")
    b_operator_name = Column(String(100), nullable=False, default="Unknown")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # --- A Number details ---
        a_num = kwargs.get("aNum")
        if a_num:
            try:
                parsed_a = phonenumbers.parse(a_num, None)
                iso2_a = phonenumbers.region_code_for_number(parsed_a)
                country_a = pycountry.countries.get(alpha_2=iso2_a)
                self.a_country = country_a.name if country_a else "Unknown"
                self.a_operator_name = carrier.name_for_number(parsed_a, "en") or "Unknown"
            except Exception:
                self.a_country = "Unknown"
                self.a_operator_name = "Unknown"

        # --- B Number details ---
        b_num = kwargs.get("bNum")
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