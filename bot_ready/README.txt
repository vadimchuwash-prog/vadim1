========================================
   UltraBTC HYBRID v1.4.8 - ГОТОВ К ЗАПУСКУ
========================================

ЗАПУСК:
   python main.py

ПЕРЕД ПЕРВЫМ ЗАПУСКОМ:
   pip install -r requirements.txt

СТРУКТУРА:
   main.py           - точка входа (ЗАПУСКАТЬ ЭТОТ ФАЙЛ!)
   trading_bot.py    - обёртка бота
   config.py         - настройки
   security.py       - безопасность API ключей
   telegram_bot.py   - Telegram уведомления
   bot_modules/      - модули бота (НЕ ТРОГАТЬ)

ПЕРВЫЙ ЗАПУСК:
   При первом запуске бот попросит ввести:
   - API Key (BingX)
   - Secret Key (BingX)
   - Telegram Bot Token
   - Telegram Chat ID

ИСПРАВЛЕНИЯ v1.4.8:
   - КРИТИЧЕСКИЙ ФИКС: Range Trailing теперь срабатывает
     ТОЛЬКО когда позиция в прибыли! Раньше закрывал в убытке.

ИСПРАВЛЕНИЯ v1.4.7:
   - Мониторинг SL ордера в run()
   - Убран дублирующий answer_callback
   - Убран захардкоженный API ключ
   - Экспорт AnalyticsMixin
   - Импорты в bot_trailing.py

========================================
