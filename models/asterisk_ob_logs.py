from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.sql.sqltypes import DateTime

from database import Base
from utils.phone_country_tools import set_country_and_operator


class Asterisk_ob_logs(Base):
    __tablename__ = "asterisk_ob_cdr"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    calldate = Column(DateTime(timezone=True), nullable=False)
    clid = Column("clid", String(80), nullable=False)
    src = Column("src", String(32), nullable=False)
    dst = Column("dst", String(32), nullable=False)

    # Duration fields
    duration = Column("billsec", Integer, nullable=False)
    extended_duration = Column("duration", Integer, nullable=True)

    status = Column("disposition", String, nullable=False)
    teleservice = Column(Integer, nullable=False, default=0)
    schedule_id = Column(Integer, ForeignKey("schedule.id"), nullable=False)

    # Raw Asterisk metadata
    dcontext = Column("dcontext", String(100), nullable=True)
    channel = Column("channel", String(50), nullable=True)
    dstchannel = Column("dstchannel", String(50), nullable=True)
    lastapp = Column("lastapp", String(100), nullable=True)
    lastdata = Column("lastdata", String(100), nullable=True)
    amaflags = Column("amaflags", Integer, nullable=True)
    accountcode = Column("accountcode", String(100), nullable=True)
    userfield = Column("userfield", String(100), nullable=True)
    linkedid = Column("linkedid", String(32), nullable=True)
    call_provider = Column("call_provider", String(50), nullable=True)

    # Higher-level classification
    call_source = Column("call_source", String(20), nullable=True)
    #region = Column("region", String(50), nullable=True)
    call_type = Column("call_type", String(50), nullable=True)
    trunk_used = Column("trunk_used", String(50), nullable=True)
    failure_cause = Column("failure_cause", String(100), nullable=True)
    latency_ms = Column("latency_ms", Integer, nullable=True)
    notes = Column("notes", String, nullable=True)

    # 🌍 Country & operator info (ORM attributes a_ / b_*, columns map to src_/dst_*)
    src_country = Column("src_country", String(100), nullable=False, default="Unknown")
    src_operator_name = Column("src_operator_name", String(100), nullable=False, default="Unknown")
    dst_country = Column("dst_country", String(100), nullable=False, default="Unknown")
    dst_operator_name = Column("dst_operator_name", String(100), nullable=False, default="Unknown")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Enrich A-number (src)
        set_country_and_operator(
            obj=self,
            number_attr="src",
            country_attr="src_country",
            operator_attr="src_operator_name",
        )

        # Enrich B-number (dst)
        set_country_and_operator(
            obj=self,
            number_attr="dst",
            country_attr="dst_country",
            operator_attr="dst_operator_name",
        )



# import phonenumbers
# import pycountry
# from phonenumbers import carrier
# from sqlalchemy import Column, Integer, String
# from sqlalchemy.sql import func
# from sqlalchemy.sql.schema import ForeignKey
# from sqlalchemy.sql.sqltypes import DateTime
# from database import Base
#
# class Asterisk_ob_logs(Base):
#     __tablename__ = "asterisk_ob_cdr"
#
#     id = Column(Integer, primary_key=True, index=True, autoincrement=True)
#     calldate = Column(DateTime(timezone=True), nullable=False)
#     clid = Column("clid", String(80), nullable=False)
#     src = Column("src", String(32), nullable=False)
#     dst = Column("dst", String(32), nullable=False)
#
#     duration = Column("billsec", Integer, nullable=False)
#     extended_duration = Column("duration", Integer, nullable=True)
#     status = Column("disposition", String, nullable=False)
#     teleservice = Column(Integer, nullable=False, default=0)
#     schedule_id = Column(Integer, ForeignKey("schedule.id"), nullable=False)
#
#     dcontext = Column("dcontext", String(100), nullable=True)
#     channel = Column("channel", String(50), nullable=True)
#     dstchannel = Column("dstchannel", String(50), nullable=True)
#     lastapp = Column("lastapp", String(100), nullable=True)
#     lastdata = Column("lastdata", String(100), nullable=True)
#     amaflags = Column("amaflags", String(100), nullable=True)
#     accountcode = Column("accountcode", String(100), nullable=True)
#     call_type = Column("call_type", String(50), nullable=True)
#     userfield = Column("userfield", String(100), nullable=True)
#     trunk_used = Column("trunk_used", String(50), nullable=True)
#     failure_cause = Column("failure_cause", String(100), nullable=True)
#     latency_ms = Column("latency_ms", Integer, nullable=True)
#
#     # 🌍 Country & operator info
#     a_country = Column("src_country", String(100), nullable=False, default="Unknown")
#     a_operator_name = Column("src_operator_name", String(100), nullable=False, default="Unknown")
#     b_country = Column("dst_country", String(100), nullable=False, default="Unknown")
#     b_operator_name = Column("dst_operator_name", String(100), nullable=False, default="Unknown")
#
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#
#         # --- A Number details ---
#         a_num = kwargs.get("src")
#         if a_num:
#             try:
#                 parsed_a = phonenumbers.parse(a_num, None)
#                 iso2_a = phonenumbers.region_code_for_number(parsed_a)
#                 country_a = pycountry.countries.get(alpha_2=iso2_a)
#                 self.src_country = country_a.name if country_a else "Unknown"
#                 self.src_operator_name = carrier.name_for_number(parsed_a, "en") or "Unknown"
#             except Exception:
#                 self.src_country = "Unknown"
#                 self.src_operator_name = "Unknown"
#
#         # --- B Number details ---
#         b_num = kwargs.get("dst")
#         if b_num:
#             try:
#                 parsed_b = phonenumbers.parse(b_num, None)
#                 iso2_b = phonenumbers.region_code_for_number(parsed_b)
#                 country_b = pycountry.countries.get(alpha_2=iso2_b)
#                 self.dst_country = country_b.name if country_b else "Unknown"
#                 self.dst_operator_name = carrier.name_for_number(parsed_b, "en") or "Unknown"
#             except Exception:
#                 self.dst_country = "Unknown"
#                 self.dst_operator_name = "Unknown"