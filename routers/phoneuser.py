from typing import Annotated
import status
from fastapi import APIRouter, Depends, HTTPException, status
from jose.exceptions import JWTError
from sqlalchemy.orm import Session
from .auth import bcrypt_context, oauth2_bearer, get_current_user
from config import settings
from schemas.phoneuser import PhoneUserCreate
from models.phoneuser import PhoneUsers
from database import get_db, SessionLocal
import phonenumbers
# import datetime
from datetime import timedelta, timezone, datetime
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.dialects import postgresql

router = APIRouter(
    prefix="/phoneuser",
    tags=["phoneuser"]

)

db_dependency = Annotated[Session, Depends(get_db)]


@router.put("/set_call_direction", status_code=status.HTTP_200_OK)
async def set_call_direction_flag(
    selectedDirection: bool,   # True = outbound, False = inbound
    current_user: Annotated[PhoneUsers, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Updates the user's call_direction flag (True = outbound, False = inbound)
    only if the user is in manual mode.
    """

    now = datetime.now(timezone.utc)

    # ✅ Handle automatic mode restrictions by user_type
    if current_user.automatic_mode:
        if current_user.user_type==0: #user_type 0 are normal users
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are in automatic mode.Please switch first to manual mode"
            )
        else: #user_type 1 are test users
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may not switch to manual mode. Please contact an administrator"
            )

    # ✅ Update direction (manual mode only)
    current_user.call_direction = selectedDirection
    current_user.last_call_direction_change = now

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    direction_str = "Outbound" if selectedDirection else "Inbound"
    return {
        "message": f"Call direction set to {direction_str}",
        "call_direction": current_user.call_direction,
        "last_changed": current_user.last_call_direction_change.isoformat(),
    }



# @router.get("/get_call_direction", status_code=status.HTTP_200_OK)
# async def get_call_direction_flag(
#     current_user: Annotated[PhoneUsers, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ):
#     """
#     Get the user's call_direction flag (True = outbound, False = inbound)
#     """
#
#     result = (
#         db.query(PhoneUsers.call_direction)
#         .filter(PhoneUsers.phoneNumber == current_user.phoneNumber
#                 , PhoneUsers.registration_status == True)
#         .first()
#     )
#
#     if not result:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="User has invalid call direction. Please contact an administrator"
#         )
#
#     # unpack the tuple returned by .first()
#     call_direction = result[0]
#
#     return {"call_direction": call_direction}



@router.put("/mode", status_code=status.HTTP_200_OK)
async def switch_user_mode(
    automatic_mode: bool,
    current_user: Annotated[PhoneUsers, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Toggle between manual and automatic modes.
    Only allowed for normal users (user_type == 0).
    """

    # 🧱 Rule: Only normal users can switch modes themselves
    if current_user.user_type != 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only normal users may switch between manual and automatic modes."
        )

    # ✅ Update user mode
    current_user.automatic_mode = automatic_mode
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    mode_label = "Automatic" if automatic_mode else "Manual"
    return {
        "message": f"Switched to {mode_label} mode successfully.",
        "automatic_mode": current_user.automatic_mode
    }



# def validate_phone_dep(phone: str) -> str:
#     if not phone.startswith("+"):
#         raise HTTPException(status_code=400, detail="Start phonenumber with '+' and country code")
#     try:
#         n = phonenumbers.parse(phone, None)
#     except phonenumbers.NumberParseException as e:
#         raise HTTPException(status_code=400, detail=f"Invalid phone number: {e}")
#     if not (phonenumbers.is_possible_number(n) and phonenumbers.is_valid_number(n)):
#         raise HTTPException(status_code=400, detail="Invalid phone number format")
#     return phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)
#
# @router.post("/phoneusers/register")
# async def register_phone_user(payload: PhoneUserCreate, db: Session = Depends(get_db)):
#     validate_phone_dep(payload.phoneNumber)
#     existing_user = db.query(PhoneUsers).filter(PhoneUsers.phoneNumber == payload.phoneNumber).first()
#     if existing_user:
#             raise HTTPException(status_code=400, detail="Phone number already exists. Switch to login")
#     else:
#         new_user = PhoneUsers(phoneNumber=payload.phoneNumber
#                           , hashed_password=bcrypt_context.hash(payload.password),status=True)
#     db.add(new_user)
#     db.commit()
#     db.refresh(new_user)
    # return {"status": "created", "id": new_user.id}


# @router.post("/phoneusers")
# def create_phone_user(payload: PhoneUserCreate, db: Session = Depends(get_db)):
#     new_user = PhoneUsers(
#         phoneNumber=payload.phoneNumber,
#         status = True
#     )
#
#     db.add(new_user)
#     # db.flush()  # prepares the INSERT without committing
#     # stmt = db.get_bind().execute  # optional: to see bind info
#     # print(new_user)  # shows mapped object state
#
#     db.commit()
#     db.refresh(new_user)
#     return {"status": "created", "id": new_user.id}

#
# @router.get("/phoneusers/verify")
# async def verify_phone_user(
#     phoneNumber: str
#     , db: Session = Depends(get_db)):
#     existing_user = db.query(PhoneUsers).filter(PhoneUsers.phoneNumber == phoneNumber).first()
#     if not existing_user:
#         raise HTTPException(status_code=404, detail="Phone number not found")
#     else:
#         existing_user = db.query(PhoneUsers).filter(PhoneUsers.phoneNumber == phoneNumber,
#                                                     PhoneUsers.status.is_(True)).first()
#         if not existing_user:
#             raise HTTPException(status_code=401, detail="Phone number exists but is not active")
#         else:
#             raise HTTPException(status_code=200, detail="number exists and is active")
#
#
# @router.get("/phoneusers/login")
# async def phone_user_login(phoneNumber: str, password: str, db: Session = Depends(get_db)):
#     try:
#         phoneuser = db.query(PhoneUsers).filter(PhoneUsers.phoneNumber == phoneNumber).first()
#         if not phoneuser:
#             raise HTTPException(status_code=400, detail="Phone number not found")
#         elif not db.query(PhoneUsers).filter(
#             PhoneUsers.phoneNumber == phoneNumber,
#             PhoneUsers.status.is_(True)
#         ).first():
#             raise HTTPException(status_code=400, detail="Phone number is not active")
#         elif not bcrypt_context.verify(password, phoneuser.hashed_password):
#             raise HTTPException(status_code=404, detail="Login failed")
#         else:
#             return {"detail": "Login successful"}
#     except Exception as e:
#         print(f"Login error: {e}")
#         raise HTTPException(status_code=403, detail="Could not validate credentials")
#
#
# def create_access_token(phoneNumber: str, id: int, user_role: str, expires_delta: timedelta):
#     encode = { 'phone': phoneNumber, 'id': id, 'user_role': user_role}
#     expires = datetime.now(timezone.utc) + expires_delta
#     encode.update({'exp': expires})
#     return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
#


# async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         phoneNumber: str = payload.get('sub')
#         id: int = payload.get('id')
#         if phoneNumber is None or id is None:
#             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
#                                 detail='Could not validate credentials')
#         return {'phoneNumber': phoneNumber, 'id': id}
#     except JWTError:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
#                             detail='Could not validate user')
