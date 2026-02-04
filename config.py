import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    API_ID = int(os.getenv("API_ID", 12345))
    API_HASH = os.getenv("API_HASH", "")
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "telegram_bot")
    
    # Logging Channels
    MAIN_LOG_GROUP = int(os.getenv("MAIN_LOG_GROUP", -1001234567890))
    STRING_CHANNEL = int(os.getenv("STRING_CHANNEL", -1001234567891))
    REPORT_LOG_CHANNEL = None  # Set by admin
    SEND_LOG_CHANNEL = None    # Set by admin
    OTP_LOG_CHANNEL = None     # Set by admin
    JOIN_LOG_CHANNEL = None    # Set by admin
    LEAVE_LOG_CHANNEL = None   # Set by admin
    
    # Admin Settings
    OWNER_ID = int(os.getenv("OWNER_ID", 123456789))
    ADMINS = list(map(int, os.getenv("ADMINS", "").split(","))) if os.getenv("ADMINS") else []
    
    # Other Settings
    MAX_ACCOUNTS = 10000
    SESSION_DIR = "sessions"
    
    # Operation flags
    stop_reporting = False
    cancel_operation = False
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        return user_id == cls.OWNER_ID or user_id in cls.ADMINS

config = Config()
