#!/usr/bin/env python3
"""
GigaAM GUI Launcher

Запуск графического интерфейса для распознавания речи.

Использование:
    python run_gui.py                    # Запуск GUI
    python run_gui.py --model MODEL_NAME # Указать модель
"""

import argparse
import sys
from pathlib import Path

# Добавляем src в путь
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def check_dependencies(skip_model_check: bool = False) -> bool:
    """Проверяет наличие необходимых зависимостей."""
    missing = []
    
    try:
        import PyQt6
    except ImportError:
        missing.append("PyQt6")
    
    if not skip_model_check:
        try:
            import onnx_asr
        except ImportError:
            missing.append("onnx_asr")
    
    try:
        import sounddevice
    except ImportError:
        missing.append("sounddevice")
    
    if missing:
        print("❌ Отсутствуют зависимости:")
        for dep in missing:
            print(f"   • {dep}")
        print()
        print("Установите их командой:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="GigaAM GUI - Графический интерфейс для распознавания речи"
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='gigaam-v3-e2e-rnnt',
        help='Имя модели (по умолчанию: gigaam-v3-e2e-rnnt)'
    )
    
    parser.add_argument(
        '--no-model',
        action='store_true',
        help='Запустить без загрузки модели (для тестирования UI)'
    )
    
    args = parser.parse_args()
    
    # Проверяем зависимости
    if not check_dependencies(skip_model_check=args.no_model):
        return 1
    
    # Загружаем модель
    model = None
    if not args.no_model:
        print(f"🧠 Загрузка модели {args.model}...")
        try:
            import onnx_asr
            model = onnx_asr.load_model(args.model)
            print("✅ Модель загружена!")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки модели: {e}")
            print("   GUI будет запущен без модели")
    
    # Загружаем конфигурацию
    try:
        from src.config import get_config
        config = get_config()
    except Exception:
        config = None
    
    # Запускаем GUI
    print("🚀 Запуск GUI...")
    
    from src.ui.gui import run_gui
    run_gui(model=model, config=config)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
