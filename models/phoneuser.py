    # models/phoneuser.py
import phonenumbers
from phonenumbers import carrier
import pycountry
from sqlalchemy import Column, String, DateTime, Integer, func, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.functions import now
from sqlalchemy.sql.sqltypes import BigInteger, Text
from sqlalchemy.sql.schema import ForeignKey

from database import Base
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid

class PhoneUsers(Base):
    __tablename__ = "phoneusers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phoneNumber: Mapped[str] = mapped_column(String(32), nullable=False)

    country_iso2: Mapped[str] = mapped_column(String(2), nullable=False, server_default="--")
    country_name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="Unknown")
    country_dial_code: Mapped[str] = mapped_column(String(6), nullable=False, server_default="+++")
    operator_name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="Unknown")

    createdOn: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    registration_status: Mapped[bool] = mapped_column("registration_status", Boolean(), server_default="true", nullable=False, unique=False)
    last_registration_status_change: Mapped[datetime] = mapped_column("last_registration_status_change", DateTime(timezone=True), server_default=func.now(), nullable=False)

    call_direction: Mapped[bool] = mapped_column(Boolean(), server_default="false", nullable=False)
    last_call_direction_change: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    user_role: Mapped[str] = mapped_column("user_role", String(50), server_default="basic",nullable=False)

    last_login_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_logout_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    user_type: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    automatic_mode: Mapped[bool] = mapped_column("automatic_mode", Boolean(), server_default="False",
                                                      nullable=False, unique=False)

    device_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),server_default=text("gen_random_uuid()"),
        unique=True,nullable=False)
    last_login_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)


    def __init__(self, **kwargs):
        """Auto-populate country fields from phone number if possible."""
        super().__init__(**kwargs)

        phone = kwargs.get("phoneNumber")
        if phone:
            try:
                num = phonenumbers.parse(phone)
                iso2 = phonenumbers.region_code_for_number(num)
                country = pycountry.countries.get(alpha_2=iso2)

                self.country_iso2 = iso2 or "--"
                self.country_name = country.name if country else "Unknown"
                self.country_dial_code = f"+{num.country_code}" if num.country_code else "+++"
                op_name = carrier.name_for_number(num, "en")
                self.operator_name = op_name or "Unknown"

            except Exception:
                self.country_iso2 = "--"
                self.country_name = "Unknown"
                self.country_dial_code = "+++"
        else:
            self.country_iso2 = "--"
            self.country_name = "Unknown"
            self.country_dial_code = "+++"



# class UserSession(Base):
#     __tablename__ = "user_sessions"
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     user_id = Column(BigInteger, ForeignKey("phoneusers.id", ondelete="CASCADE"), nullable=False)
#     device_id = Column(Text, nullable=False)  # This will be the app_install_id
#
#     # We will skip refresh_token_hash for now, but the column is ready for the future
#     # refresh_token_hash = Column(Text, unique=True, nullable=False)
#
#     created_at = Column(DateTime(timezone=True), server_default=now())
#     last_seen_at = Column(DateTime(timezone=True), server_default=now())
#     expires_at = Column(DateTime(timezone=True), nullable=False)
#     revoked_at = Column(DateTime(timezone=True), nullable=True)
#
#     reason_revoked = Column(Text, nullable=True)
#
#     # This creates the link back to the PhoneUsers model
#     user = relationship("PhoneUsers", back_populates="sessions")