"""
🚀 UltraBTC HYBRID v1.4 - MAIN ENTRY POINT
Главная точка входа в программу
"""

import time
import socket
import requests.packages.urllib3.util.connection as urllib3_cn
import ccxt

# FORCE IPV4 GLOBALLY
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

_old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = _old_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

from security import SecurityManager
from telegram_bot import TelegramBot
from trading_bot import HybridTradingBot
from config import TG_BOT_TOKEN


if __name__ == "__main__":
    sec = SecurityManager()
    creds = sec.load_credentials()
    if not creds:
        print("🔑 Setup Credentials (BINGX):")
        sec.save_credentials(
            input("API Key: "), 
            input("Secret Key: "), 
            input("TG Token: "), 
            input("TG Chat ID: ")
        )
        creds = sec.load_credentials()
    
    try:
        ex = ccxt.bingx({
            'apiKey': creds['api_key'], 
            'secret': creds['secret_key'], 
            'enableRateLimit': True, 
            'timeout': 10000,
            'options': {'defaultType': 'swap'}
        })
        tg_token = creds['tg_token'] if creds['tg_token'] else TG_BOT_TOKEN
        bot = HybridTradingBot(ex, TelegramBot(tg_token, creds['tg_chat_id']))
        bot.run()
    except Exception as e: 
        print(f"\n❌ Error: {e}")
