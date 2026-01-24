"""
🤖 AI ASSISTANT
Интеграция с Google Gemini для AI-анализа
"""

import os
from config import AI_GEMINI_KEY, AI_MODEL_NAME

# ==========================================
# 🛡️ AI LIBRARY SAFE IMPORT
# ==========================================
HAS_AI = False
try:
    from google import genai
    HAS_AI = True
except ImportError:
    pass
except Exception as e:
    print(f"⚠️ Ошибка импорта AI: {e}")


class AIAssistant:
    def __init__(self):
        self.has_ai = HAS_AI and AI_GEMINI_KEY
        self.client = None
        if self.has_ai:
            try:
                self.client = genai.Client(api_key=AI_GEMINI_KEY)
            except Exception as e:
                print(f"⚠️ AI Init Error: {e}")
                self.has_ai = False
    
    def chat(self, user_message, context=""):
        """Общение с AI"""
        if not self.has_ai or not self.client:
            return "⚠️ AI не подключен (GEMINI_API_KEY)"
        
        try:
            system_prompt = f"""Ты AI-ассистент UltraBTC Hybrid Bot.
{context}

Ответь кратко и по делу на русском языке."""
            
            response = self.client.models.generate_content(
                model=AI_MODEL_NAME,
                contents=user_message,
                config={
                    "system_instruction": system_prompt,
                    "temperature": 0.7,
                    "max_output_tokens": 500
                }
            )
            
            return response.text if response else "⚠️ Пустой ответ от AI"
        except Exception as e:
            return f"❌ AI Error: {e}"
    
    def analyze_market(self, market_data):
        """Анализ рынка через AI"""
        if not self.has_ai or not self.client:
            return "⚠️ AI не подключен"
        
        try:
            prompt = f"""Проанализируй рыночную ситуацию BTC/USDT:

{market_data}

Дай краткий вывод (2-3 предложения):
1. Текущий тренд
2. Уровни поддержки/сопротивления
3. Рекомендации по входу"""
            
            response = self.client.models.generate_content(
                model=AI_MODEL_NAME,
                contents=prompt,
                config={
                    "temperature": 0.5,
                    "max_output_tokens": 300
                }
            )
            
            return response.text if response else "⚠️ Нет ответа"
        except Exception as e:
            return f"❌ AI Analysis Error: {e}"
