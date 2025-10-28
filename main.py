from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
# 1. Import the settings instance from your new config file
from config import settings

from database import Base, engine
from routers import callLogs, schedule, auth, phoneuser, outboundcdrlogs, inboundcdrlogs
from core.rate_limit import limiter


# Note: We no longer need to bind the engine here if it's already done in database.py
# and database.py uses the config. This avoids circular dependencies.
# Ensure your database.py now imports 'from config import settings' and uses 'settings.DATABASE_URL'
Base.metadata.create_all(bind=engine)

# 2. Initialize FastAPI with debug mode from settings
app = FastAPI(debug=settings.DEBUG_MODE)

app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests, please wait and try again later."},
    )

# 3. Configure CORS middleware using the settings from your config file
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS, # <-- Use the setting here
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the routers (this part remains the same)
app.include_router(callLogs.router)
app.include_router(schedule.router)
app.include_router(auth.router)
app.include_router(phoneuser.router)
app.include_router(outboundcdrlogs.router)
app.include_router(inboundcdrlogs.router)

# Optional: Add a root endpoint for health checks
@app.get("/", tags=["Health Check"])
def read_root():
    return {"status": "API is running"}