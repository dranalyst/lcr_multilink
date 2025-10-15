from typing import Annotated
from pydantic import BaseModel, field_validator
import phonenumbers

class PhoneUserCreate(BaseModel):
    phoneNumber: str
    password: str

    # @field_validator("phoneNumber")
    # @classmethod
    # def validate_phone_e164(cls, v: str) -> str:
    #     if not isinstance(v, str):
    #         raise ValueError("phoneNumber must be a string")
    #
    #     raw = v.strip()
    #
    #     # Require leading '+'
    #     if not raw.startswith("+"):
    #         raise ValueError("Phone number must start with '+' and country code")
    #
    #     try:
    #         # Parse as an international number only
    #         number = phonenumbers.parse(raw, None)
    #     except phonenumbers.NumberParseException as e:
    #         raise ValueError(f"Invalid phone number: {e}")
    #
    #     # Validate structure against E.164 rules
    #     if not phonenumbers.is_possible_number(number) or not phonenumbers.is_valid_number(number):
    #         raise ValueError("Invalid phone number format")
    #
    #     # Normalize and return in E.164 format
    #     normalized = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    #     return normalized
    #
    # class Config:
    #     from_attributes = True