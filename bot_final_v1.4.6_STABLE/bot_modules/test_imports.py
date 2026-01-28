"""
🧪 TEST IMPORTS
Тест импорта модулей для проверки корректности структуры
"""

import sys
import os

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Тестирование импортов всех модулей"""
    
    print("🧪 Testing module imports...\n")
    
    # Test 1: Основной пакет
    try:
        from bot_modules import HybridTradingBot, __version__
        print(f"✅ bot_modules: OK (version {__version__})")
    except Exception as e:
        print(f"❌ bot_modules: FAILED - {e}")
        return False
    
    # Test 2: bot_core
    try:
        from bot_modules.bot_core import HybridTradingBot
        print("✅ bot_core: OK")
    except Exception as e:
        print(f"❌ bot_core: FAILED - {e}")
        return False
    
    # Test 3: analytics
    try:
        from bot_modules.analytics import AnalyticsMixin
        print("✅ analytics: OK")
    except Exception as e:
        print(f"❌ analytics: FAILED - {e}")
        return False
    
    # Test 4: constants
    try:
        from bot_modules.constants import (
            EventType, PositionSide, OrderType, 
            MarketMode, EntryStage, Thresholds, Emoji
        )
        print("✅ constants: OK")
    except Exception as e:
        print(f"❌ constants: FAILED - {e}")
        return False
    
    # Test 5: utils
    try:
        from bot_modules.utils import (
            format_usd, format_percent, format_price,
            round_price, round_size, calculate_fee,
            calculate_pnl, is_valid_price
        )
        print("✅ utils: OK")
    except Exception as e:
        print(f"❌ utils: FAILED - {e}")
        return False
    
    print("\n🎉 All imports successful!")
    return True


def test_functions():
    """Тестирование базовых функций"""
    
    print("\n🧪 Testing basic functions...\n")
    
    from bot_modules.utils import (
        format_usd, format_percent, calculate_pnl,
        round_price, is_valid_price
    )
    from bot_modules.constants import get_position_emoji, get_pnl_emoji
    
    # Тест форматирования
    assert format_usd(1234.56) == "$1,234.56", "format_usd failed"
    print("✅ format_usd: OK")
    
    assert format_percent(5.5) == "5.50%", "format_percent failed"
    print("✅ format_percent: OK")
    
    # Тест расчётов
    pnl = calculate_pnl(100, 110, 1.0, "Buy")
    assert pnl == 10.0, f"calculate_pnl failed: expected 10.0, got {pnl}"
    print("✅ calculate_pnl: OK")
    
    # Тест округления
    rounded = round_price(99.876, 0.01)
    assert rounded == 99.88, f"round_price failed: expected 99.88, got {rounded}"
    print("✅ round_price: OK")
    
    # Тест валидации
    assert is_valid_price(100.0) == True, "is_valid_price failed"
    assert is_valid_price(-100.0) == False, "is_valid_price failed"
    print("✅ is_valid_price: OK")
    
    # Тест emoji
    emoji = get_position_emoji("Buy")
    assert emoji in ["📈", "📉"], f"get_position_emoji failed: got {emoji}"
    print("✅ get_position_emoji: OK")
    
    print("\n🎉 All function tests passed!")
    return True


if __name__ == "__main__":
    try:
        # Тест импортов
        if not test_imports():
            sys.exit(1)
        
        # Тест функций
        if not test_functions():
            sys.exit(1)
        
        print("\n" + "="*50)
        print("🎉 ALL TESTS PASSED!")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
