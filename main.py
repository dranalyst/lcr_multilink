from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from .models import PhoneUsers
from database import Base, engine, get_db
from routers import callLogs, schedule, user, phoneuser, auth, outboundcdrlogs, inboundcdrlogs
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from core.rate_limit import limiter


Base.metadata.create_all(bind=engine)
app = FastAPI()

app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests, please wait and try again later."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the routers
app.include_router(callLogs.router)
app.include_router(schedule.router)
app.include_router(auth.router)
app.include_router(phoneuser.router)
app.include_router(outboundcdrlogs.router)
app.include_router(inboundcdrlogs.router)