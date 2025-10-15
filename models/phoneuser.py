    # models/phoneuser.py
import phonenumbers
import pycountry
from sqlalchemy import Column, String, DateTime, Integer, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from database import Base
from datetime import datetime

# class PhoneUsers(Base):
#     __tablename__ = "phoneusers"
#      # __table_args__ = {"schema": "public"}  # <-- use your schema name here
#
#     id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
#     phoneNumber: Mapped[str] = mapped_column("phoneNumber", String(32), nullable=False, unique=False)
#     createdOn: Mapped[datetime] = mapped_column("createdOn", DateTime(timezone=True), server_default=func.now())
#     status: Mapped[bool] = mapped_column("subscription_status", Boolean(), nullable=False, unique=False)
#     last_status_change_date: Mapped["datetime"] = mapped_column(
#         DateTime(timezone=True),server_default=func.now(),    # Postgres side default
#         nullable=False)
#
#     ob_readiness: Mapped[bool] = mapped_column(
#         Boolean(), server_default="false", nullable=False)
#
#     last_ob_readiness_date: Mapped["datetime"] = mapped_column(
#         DateTime(timezone=True), nullable=True)   # defaults to NULL
#
#     ib_readiness: Mapped[bool] = mapped_column(
#         Boolean(), server_default="false", nullable=False)
#
#     last_ib_readiness_date: Mapped["datetime"] = mapped_column(
#         DateTime(timezone=True), nullable=True)    # defaults to NULL
#
#     hashed_password: Mapped[str] = mapped_column(
#         String(255), nullable=False)   # bcrypt hashes ~60 chars, 255 gives room for others


class PhoneUsers(Base):
    __tablename__ = "phoneusers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phoneNumber: Mapped[str] = mapped_column(String(32), nullable=False)

    country_iso2: Mapped[str] = mapped_column(String(2), nullable=False, server_default="--")
    country_name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="Unknown")
    country_dial_code: Mapped[str] = mapped_column(String(6), nullable=False, server_default="+++")

    createdOn: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subscription_status: Mapped[bool] = mapped_column("subscription_status", Boolean(), server_default="true", nullable=False, unique=False)
    last_status_change_date: Mapped[datetime] = mapped_column("last_subs_status_change_date", DateTime(timezone=True), server_default=func.now(), nullable=False)

    ob_readiness: Mapped[bool] = mapped_column(Boolean(), server_default="false", nullable=False)
    last_ob_readiness_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    ib_readiness: Mapped[bool] = mapped_column(Boolean(), server_default="false", nullable=False)
    last_ib_readiness_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    user_role: Mapped[str] = mapped_column("user_role", String(50), server_default="basic",nullable=False)

    last_login_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_logout_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    user_type: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)


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
            except Exception:
                self.country_iso2 = "--"
                self.country_name = "Unknown"
                self.country_dial_code = "+++"
        else:
            self.country_iso2 = "--"
            self.country_name = "Unknown"
            self.country_dial_code = "+++"