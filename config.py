import os
from dotenv import load_dotenv
from typing import List

# Load environment variables from the .env file in the root directory.
# This line is crucial for local development.
load_dotenv()

class Settings:
    """
    A class to hold all application settings, loaded from environment variables.
    """
    # --- DATABASE CONFIGURATION ---
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASS: str = os.getenv("DB_PASS")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "testCaller")

    # Construct the database URL from the components.
    DATABASE_URL: str = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


    # --- AUTHENTICATION & SECURITY ---
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    ACCESS_TOKEN_EXPIRE_DAYS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", 7))

    #Twilio
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN")



    # --- CORS (Cross-Origin Resource Sharing) ---
    # The default value is an empty list if the variable is not set.
    CORS_ORIGINS: List[str] = [
        origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(',') if origin
    ]
    # If no origins are specified, you might want a default for local dev, e.g., ["*"]
    if not CORS_ORIGINS:
        CORS_ORIGINS = ["*"] # Be restrictive in production!


    # --- APPLICATION BEHAVIOR ---
    # Convert string "True" or "False" to a boolean
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "False").lower() in ("true", "1", "t")

    def __init__(self):
        """
        Validate that critical secrets are loaded.
        """
        if not self.DB_PASS:
            raise ValueError("FATAL ERROR: Database password (DB_PASS) is not set in environment variables.")
        if not self.SECRET_KEY:
            raise ValueError("FATAL ERROR: Secret key (SECRET_KEY) is not set for JWT authentication.")

# Create a single, importable instance of the settings.
settings = Settings()