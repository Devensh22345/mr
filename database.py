from motor.motor_asyncio import AsyncIOMotorClient
from config import config

class Database:
    def __init__(self):
        self.client = None
        self.db = None
    
    async def connect(self):
        self.client = AsyncIOMotorClient(config.MONGODB_URI)
        self.db = self.client[config.DB_NAME]
        
        # Create indexes
        await self.create_indexes()
        print("✅ Connected to MongoDB")
    
    async def create_indexes(self):
        # Create indexes for better performance
        await self.db.accounts.create_index("user_id")
        await self.db.accounts.create_index("phone", unique=True)
        await self.db.accounts.create_index("is_active")
        await self.db.users.create_index("user_id", unique=True)
        await self.db.admins.create_index("user_id", unique=True)
        await self.db.logs.create_index("timestamp")
    
    async def disconnect(self):
        if self.client:
            self.client.close()
            print("✅ Disconnected from MongoDB")
    
    # Collections
    @property
    def users(self):
        return self.db.users
    
    @property
    def accounts(self):
        return self.db.accounts
    
    @property
    def admins(self):
        return self.db.admins
    
    @property
    def logs(self):
        return self.db.logs
    
    @property
    def settings(self):
        return self.db.settings

db = Database()
