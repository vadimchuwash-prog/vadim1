"""
📱 TELEGRAM BOT
Управление Telegram ботом и обработка команд
"""

import time
import json
import requests
from datetime import datetime


class TelegramBot:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.offset = 0
        self._clear_updates()
    
    def _clear_updates(self):
        try:
            updates = self.get_updates()
            if updates:
                self.offset = updates[-1]['id'] + 1
        except: pass

    def send(self, message, keyboard=None):
        if not self.token or not self.chat_id: return None
        try:
            if len(message) > 4000: message = message[:4000] + "\n..."
            payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}
            if keyboard: payload["reply_markup"] = json.dumps(keyboard)
            resp = requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage", data=payload, timeout=10)
            
            if not resp.json().get('ok'):
                print(f"❌ TG Send Error: {resp.json().get('description')}")
                return None
            return resp.json().get('result', {}).get('message_id')
        except Exception as e: 
            print(f"❌ TG Network Error: {e}")
            return None
    
    def edit_message(self, message_id, text, keyboard=None):
        if not self.token or not self.chat_id or not message_id: return False
        try:
            payload = {"chat_id": self.chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
            if keyboard: payload["reply_markup"] = json.dumps(keyboard)
            resp = requests.post(f"https://api.telegram.org/bot{self.token}/editMessageText", data=payload, timeout=10)
            return resp.json().get('ok', False)
        except: return False
    
    def get_updates(self):
        if not self.token: return []
        try:
            resp = requests.get(f"https://api.telegram.org/bot{self.token}/getUpdates", params={"offset": self.offset, "timeout": 5}, timeout=10)
            updates = resp.json().get('result', [])
            result = []
            for u in updates:
                if u['update_id'] >= self.offset: self.offset = u['update_id'] + 1
                msg = u.get('message')
                cb = u.get('callback_query')
                if msg:
                    result.append({
                        "id": u['update_id'],
                        "text": msg.get('text', ''),
                        "from_id": msg['from']['id'],
                        "type": "message"
                    })
                elif cb:
                    result.append({
                        "id": u['update_id'],
                        "data": cb['data'],
                        "callback_id": cb['id'],
                        "message_id": cb['message']['message_id'],
                        "type": "callback"
                    })
            return result
        except: return []
    
    def answer_callback(self, callback_id, text=""):
        if not self.token: return
        try:
            requests.post(f"https://api.telegram.org/bot{self.token}/answerCallbackQuery", data={"callback_query_id": callback_id, "text": text}, timeout=5)
        except: pass
    
    def send_photo(self, photo_path, caption=""):
        """Отправка фото"""
        try:
            with open(photo_path, 'rb') as photo:
                r = requests.post(f"https://api.telegram.org/bot{self.token}/sendPhoto", 
                                data={'chat_id': self.chat_id, 'caption': caption}, 
                                files={'photo': photo}, timeout=10)
            return r.json() if r.status_code == 200 else None
        except Exception as e:
            print(f"❌ TG Photo Error: {e}")
            return None
