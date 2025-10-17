from datetime import timedelta, datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import now
from starlette import status
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
import phonenumbers
from database import SessionLocal
from models import PhoneUsers
from schemas.phoneuser import PhoneUserCreate
from pydantic import BaseModel
from slowapi.util import get_remote_address
from core.rate_limit import limiter
import asyncio

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

# --------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------
SECRET_KEY = "+i1u41234567890123456789012345678901234567I="
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/token")


# --------------------------------------------------------------------
# DEPENDENCIES
# --------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------
def create_access_token(phoneNumber: str, user_id: int, expires_delta: timedelta):
    now = datetime.now(timezone.utc)  # ✅ timezone-aware UTC
    encode = {"phone": phoneNumber, "id": user_id,
              "iat": int(now.timestamp()),
              "exp": now + expires_delta}
    # expires = datetime.now(timezone.utc) + expires_delta
    # encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_phoneuser(username: str, password: str, db: Session):
    """Verify phone number and password against DB."""
    user = (
        db.query(PhoneUsers)
        .filter(PhoneUsers.phoneNumber == username)
        .filter(PhoneUsers.registration_status.is_(True))
        .first()
    )

    if not user:
        return False

    if not bcrypt_context.verify(password, user.hashed_password):
        return False

    return user


def validate_phone_dep(phone: str) -> str:
    if not phone.startswith("+"):
        raise HTTPException(status_code=400, detail="Start phonenumber with '+' and country code")
    try:
        n = phonenumbers.parse(phone, None)
    except phonenumbers.NumberParseException as e:
        raise HTTPException(status_code=400, detail=f"Invalid phone number: {e}")
    if not (phonenumbers.is_possible_number(n) and phonenumbers.is_valid_number(n)):
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    return phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)


# ✅ Input schema for password change
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str



# ✅ Helper to decode and verify token
def get_current_user(token: Annotated[str, Depends(oauth2_bearer)], db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("id")
        issued_at = payload.get("iat")

        if user_id is None or issued_at is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials."
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials."
        )

    user = db.query(PhoneUsers).filter(PhoneUsers.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found."
        )

    # Compare token issue time with last logout
    if user.last_logout_date:
        token_time = datetime.fromtimestamp(issued_at, timezone.utc)
        if token_time < user.last_logout_date:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired (token revoked after logout)"
                )

    return user


# --------------------------------------------------------------------
# ENDPOINTS
# --------------------------------------------------------------------
@router.post("/token")
@limiter.limit("5/minute")   # 🚫 max 5 login attempts per IP per minute
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Authenticates a user using phone number (as username) and password.
    Returns a signed JWT token if successful.
    """
    client_host = request.client.host  # ✅ IP address here
    user = authenticate_phoneuser(form_data.username, form_data.password, db)
    if not user:
        # ⏱ Delay slightly to make automated brute force slower
        await asyncio.sleep(1)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(phoneNumber = user.phoneNumber,
                                user_id = user.id,
                                expires_delta = timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    )
    user.last_login_date = datetime.now(timezone.utc)
    user.last_login_ip = client_host
    db.add(user)
    db.commit()

    return {"access_token": token, "token_type": "bearer"}


@router.put("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: Annotated[PhoneUsers, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Logout endpoint.
    - Marks user as offline (ob_readiness / ib_readiness = False)
    - Updates last logout timestamp.
    - Uses current_user from JWT to ensure secure logout.
    """

    now = datetime.now(timezone.utc)

    # Record logout time
    current_user.last_logout_date = now

    # Mark user as not ready for test calls
    current_user.ob_readiness = False
    current_user.last_ob_readiness_date = now
    current_user.ib_readiness = False
    current_user.last_ib_readiness_date = now

    db.add(current_user)
    db.commit()

    # Returning 204 means “no content”, which is REST-correct for logout
    return {"message": "Logged out successfully"}


@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")   # Limit new account creations per IP
async def create_user(
    request: Request,
    create_phone_user_request: PhoneUserCreate,
    db: Annotated[Session, Depends(get_db)]
):
    validate_phone_dep(create_phone_user_request.phoneNumber)
    """
    Registers a new user with hashed password.
    """
    # Check if user already exists
    existing = db.query(PhoneUsers).filter(
        PhoneUsers.phoneNumber == create_phone_user_request.phoneNumber
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )

    new_user = PhoneUsers(
        phoneNumber=create_phone_user_request.phoneNumber,
        hashed_password=bcrypt_context.hash(create_phone_user_request.password)

    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"status": "created", "id": new_user.id}



@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    request: ChangePasswordRequest,
    current_user: Annotated[PhoneUsers, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Verify existing password
    if not bcrypt_context.verify(request.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password."
        )

    # Prevent reusing the same password
    if bcrypt_context.verify(request.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the current one."
        )

    # Hash and update
    hashed_new = bcrypt_context.hash(request.new_password)
    current_user.hashed_password = hashed_new
    db.add(current_user)
    db.commit()

    return {"message": "Password updated successfully."}