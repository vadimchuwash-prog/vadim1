"""
🔐 SECURITY MANAGER
Управление шифрованием и хранением учетных данных
"""

import os
import json
from cryptography.fernet import Fernet
from config import KEY_FILE, SECRETS_FILE


class SecurityManager:
    def __init__(self):
        self.key = self._load_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _load_or_create_key(self):
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, "rb") as f: return f.read()
        else:
            key = Fernet.generate_key()
            with open(KEY_FILE, "wb") as f: f.write(key)
            return key
    
    def save_credentials(self, api_key, secret_key, tg_token, tg_chat_id):
        data = json.dumps({"api_key": api_key, "secret_key": secret_key, "tg_token": tg_token, "tg_chat_id": tg_chat_id}).encode()
        encrypted = self.cipher.encrypt(data)
        with open(SECRETS_FILE, "wb") as f: f.write(encrypted)
    
    def load_credentials(self):
        if not os.path.exists(SECRETS_FILE): return None
        with open(SECRETS_FILE, "rb") as f: encrypted = f.read()
        try: return json.loads(self.cipher.decrypt(encrypted))
        except: return None
