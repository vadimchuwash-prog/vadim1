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

ИСПРАВЛЕНИЯ v1.4.8 (КРИТИЧЕСКИЕ!):
   - Range Trailing активируется только при +0.15% прибыли
     (раньше включался сразу при открытии позиции!)
   - Трейлинг закрывает ТОЛЬКО прибыльные позиции
   - Закрытие ЛИМИТНЫМ ордером (не рыночным!)
   - Перевыставление ордера каждые 5 секунд
   - Новые настройки в config.py:
     * RANGE_TRAILING_ACTIVATION_PROFIT = 0.0015 (0.15%)
     * TRAILING_CLOSE_USE_LIMIT = True
     * TRAILING_LIMIT_ORDER_TIMEOUT = 5
     * TRAILING_LIMIT_MAX_RETRIES = 3

ИСПРАВЛЕНИЯ v1.4.7:
   - Мониторинг SL ордера в run()
   - Убран дублирующий answer_callback
   - Убран захардкоженный API ключ
   - Экспорт AnalyticsMixin

========================================
