from datetime import datetime
from typing import Optional, List, Dict, Any

class User:
    def __init__(self, user_id: int, username: str = None, first_name: str = None):
        self.user_id = user_id
        self.username = username
        self.first_name = first_name
        self.joined_at = datetime.utcnow()
        self.log_channel = None
        self.accounts = []
    
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "joined_at": self.joined_at,
            "log_channel": self.log_channel,
            "accounts": self.accounts
        }

class Account:
    def __init__(self, session_string: str, phone: str, api_id: int, api_hash: str,
                 user_id: int, name: str = None, username: str = None):
        self.session_string = session_string
        self.phone = phone
        self.api_id = api_id
        self.api_hash = api_hash
        self.user_id = user_id
        self.name = name
        self.username = username
        self.created_at = datetime.utcnow()
        self.is_active = True
        self.is_frozen = False
        self.last_checked = datetime.utcnow()
    
    def to_dict(self):
        return {
            "session_string": self.session_string,
            "phone": self.phone,
            "api_id": self.api_id,
            "api_hash": self.api_hash,
            "user_id": self.user_id,
            "name": self.name,
            "username": self.username,
            "created_at": self.created_at,
            "is_active": self.is_active,
            "is_frozen": self.is_frozen,
            "last_checked": self.last_checked
        }

class Admin:
    def __init__(self, user_id: int, username: str = None, added_by: int = None):
        self.user_id = user_id
        self.username = username
        self.added_by = added_by
        self.added_at = datetime.utcnow()
        self.permissions = ["all"]
    
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "username": self.username,
            "added_by": self.added_by,
            "added_at": self.added_at,
            "permissions": self.permissions
        }
