from sqlalchemy import Column, Integer, String
from sqlalchemy.sql.sqltypes import DateTime

from database import Base

class InboundLogs(Base):
    __tablename__ = "inbound_cdr_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    aNum = Column("a_num", String(32), nullable=False)   # maps to a_num
    bNum = Column("b_num", String(32), nullable=False)   # maps to b_num
    starttime = Column(DateTime(timezone=True), nullable=False)
    duration = Column(Integer, nullable=False)
    status = Column(String, nullable=False)