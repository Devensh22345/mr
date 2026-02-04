import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN", "7749301298:AAEstLS3CaJKQ18ZY0MpesyRrZcAbzVd5LY")
    API_ID = int(os.getenv("API_ID", "37820109"))
    API_HASH = os.getenv("API_HASH", "3bdea127dfe16be0ba54fc74fb25e950")
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://10:10@cluster0.rbnwfqt.mongodb.net/?appName=Cluster0")
    DB_NAME = os.getenv("DB_NAME", "telegram_bot")
    
    # Logging Channels
    MAIN_LOG_GROUP = int(os.getenv("MAIN_LOG_GROUP", "-1003778339813"))
    STRING_CHANNEL = int(os.getenv("STRING_CHANNEL", "-1003804481865"))
    REPORT_LOG_CHANNEL = None  # Set by admin
    SEND_LOG_CHANNEL = None    # Set by admin
    OTP_LOG_CHANNEL = None     # Set by admin
    JOIN_LOG_CHANNEL = None    # Set by admin
    LEAVE_LOG_CHANNEL = None   # Set by admin
    
    # Admin Settings
    OWNER_ID = int(os.getenv("OWNER_ID", "6872968794"))
    ADMINS = list(map(int, os.getenv("ADMINS", "6872968794").split(","))) if os.getenv("ADMINS") else []
    
    # Other Settings
    MAX_ACCOUNTS = "10000"
    SESSION_DIR = "sessions"
    
    # Operation flags
    stop_reporting = False
    cancel_operation = False
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        return user_id == cls.OWNER_ID or user_id in cls.ADMINS

config = Config()
