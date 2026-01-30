from sqlalchemy import Column, Integer, String
from sqlalchemy.sql.sqltypes import DateTime

from database import Base
from utils.phone_country_tools import set_country_and_operator


class Asterisk_ib_logs(Base):
    __tablename__ = "asterisk_ib_cdr"

    # Using uniqueid as the primary key (matches classic Asterisk CDR layout)
    id = Column(Integer, primary_key=True, index=True)

    calldate = Column(DateTime(timezone=True), nullable=False)
    clid = Column("clid", String(80), nullable=True)
    src = Column("src", String(80), nullable=True)
    standard_src = Column("standard_src", String(80), nullable=True)
    dst = Column("dst", String(80), nullable=True)
    dcontext = Column("dcontext", String(80), nullable=True)
    channel = Column("channel", String(80), nullable=True)
    dstchannel = Column("dstchannel", String(80), nullable=True)
    lastapp = Column("lastapp", String(80), nullable=True)
    lastdata = Column("lastdata", String(80), nullable=True)

    # Asterisk duration fields
    duration = Column("billsec", Integer, nullable=True)   # total duration
    extended_duration = Column("duration", Integer, nullable=True)     # billed seconds

    status = Column("disposition", String(45), nullable=True)
    amaflags = Column("amaflags", Integer, nullable=True)
    accountcode = Column("accountcode", String(20), nullable=True)
    userfield = Column("userfield", String(255), nullable=True)
    linkedid = Column("linkedid", String(32), nullable=True)

    # Extra classification / metadata
    schedule_id = Column("schedule_id", String(50), nullable=True)
    call_source = Column("call_source", String(20), nullable=True)
    # region = Column("region", String(50), nullable=True)
    call_type = Column("call_type", String(20), nullable=True)
    trunk_used = Column("trunk_used", String(50), nullable=True)
    failure_cause = Column("failure_cause", String(100), nullable=True)
    latency_ms = Column("latency_ms", Integer, nullable=True)
    notes = Column("notes", String, nullable=True)

    # 🌍 Country & operator info (aligned with your final naming)
    src_country = Column("src_country", String(100), nullable=False, default="Unknown")
    src_operator_name = Column("src_operator_name", String(100), nullable=False, default="Unknown")
    dst_country = Column("dst_country", String(100), nullable=False, default="Unknown")
    dst_operator_name = Column("dst_operator_name", String(100), nullable=False, default="Unknown")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Enrich A-number (src)
        set_country_and_operator(
            obj=self,
            number_attr="standard_src",
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