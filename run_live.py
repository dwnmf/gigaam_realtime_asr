#!/usr/bin/env python3
"""
GigaAM Realtime Speech Recognition

Распознавание речи в реальном времени с использованием модели GigaAM.
Поддерживает выбор аудиоустройства, push-to-talk и различные режимы работы.

Использование:
    python run_live.py                    # Запуск с устройством по умолчанию
    python run_live.py --list-devices     # Показать доступные устройства
    python run_live.py --device 2         # Использовать устройство с ID 2
    python run_live.py --device "Realtek" # Использовать устройство по имени
    python run_live.py --loopback         # Захват системного звука
    python run_live.py --output log.txt   # Сохранить в файл
    python run_live.py --push-to-talk     # Режим push-to-talk (удерживайте ПРОБЕЛ)
    python run_live.py --accumulate       # Накопление текста между буферами
    python run_live.py --interactive      # Интерактивный выбор устройства
    python run_live.py --no-rich          # Отключить Rich UI
"""

import argparse
import json
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# Keyboard для push-to-talk
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

# Clipboard
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False

# Rich UI (опционально)
try:
    from src.ui.console import RichConsoleUI, DeviceSelector, get_console_ui, RICH_AVAILABLE
except ImportError:
    RICH_AVAILABLE = False

import onnx_asr

from src.audio_devices import (
    list_audio_devices,
    get_device_by_name,
    get_loopback_device,
    validate_device,
    get_device_info,
)
from src.realtime_asr import RealtimeASR


# Путь к конфигу
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """
    Загружает конфигурацию из config.json.
    
    Returns:
        dict с настройками или пустой dict если файл не найден
    """
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def copy_to_clipboard(text: str) -> bool:
    """
    Копирует текст в буфер обмена.
    
    Returns:
        True если успешно, False если не удалось
    """
    if not text:
        return False
    
    if CLIPBOARD_AVAILABLE:
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            pass
    
    # Fallback для Windows через subprocess
    try:
        import subprocess
        process = subprocess.Popen(
            ['clip'],
            stdin=subprocess.PIPE,
            shell=True
        )
        process.communicate(text.encode('utf-16-le'))
        return True
    except Exception:
        pass
    
    return False


def run_codex_query(query: str) -> bool:
    """
    Запускает codex с указанным запросом в отдельном окне PowerShell.
    
    Args:
        query: Текст запроса для codex
        
    Returns:
        True если успешно запущен, False если ошибка
    """
    if not query or not query.strip():
        return False
    
    try:
        import subprocess
        
        # Экранируем кавычки для PowerShell
        safe_query = query.replace('"', '`"').replace("'", "''")
        
        # Запускаем в новом окне PowerShell
        subprocess.Popen(
            ['powershell', '-NoExit', '-Command', f'codex "{safe_query}"'],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        return True
    except Exception as e:
        return False


def parse_device_arg(device_arg: str) -> int:
    """
    Парсит аргумент устройства (число или имя).
    
    Returns:
        ID устройства
        
    Raises:
        ValueError: если устройство не найдено
    """
    # Проверяем, является ли аргумент числом
    if device_arg.isdigit() or (device_arg.startswith('-') and device_arg[1:].isdigit()):
        device_id = int(device_arg)
        valid, msg = validate_device(device_id)
        if not valid:
            raise ValueError(msg)
        return device_id
    
    # Иначе ищем по имени
    device_id = get_device_by_name(device_arg)
    if device_id is None:
        raise ValueError(f"Устройство с именем '{device_arg}' не найдено")
    
    return device_id


def select_device_interactive(ui) -> Optional[int]:
    """
    Интерактивный выбор устройства.
    
    Returns:
        ID выбранного устройства или None
    """
    if RICH_AVAILABLE and hasattr(ui, 'console'):
        devices_tuple = list_audio_devices(show_output=False)
        input_devices, output_devices = devices_tuple
        if not input_devices:
            ui.print_error("Аудиоустройства не найдены!")
            return None
        
        selector = DeviceSelector()
        return selector.select_device(devices_tuple)
    else:
        # Fallback: текстовый выбор
        devices_tuple = list_audio_devices(show_output=True)
        input_devices, output_devices = devices_tuple
        if not input_devices:
            print("❌ Аудиоустройства не найдены!")
            return None
        
        try:
            choice = input("\nВведите номер устройства: ")
            return int(choice)
        except (ValueError, KeyboardInterrupt):
            return None


def run_continuous_mode(asr: RealtimeASR, device_id, output_file, accumulate: bool, ui):
    """Запуск в непрерывном режиме с Rich UI."""
    
    def on_result(text: str):
        level = asr.get_audio_level()
        
        # В режиме накопления показываем весь текст
        accumulated = ""
        if accumulate:
            full_text = asr.get_accumulated_text()
            if full_text:
                accumulated = full_text
        
        # Обновляем UI
        ui.update(
            text=text,
            level=level,
            recording=True,
            accumulated=accumulated
        )
        
        # Записываем в файл
        if output_file:
            timestamp = datetime.now().strftime("%H:%M:%S")
            output_file.write(f"[{timestamp}] {text}\n")
            output_file.flush()
    
    asr.on_result = on_result
    
    try:
        # Запускаем Live Display
        ui.start_live_display()
        
        asr.start(device=device_id)
        
        # Бесконечный цикл ожидания
        while True:
            # Периодически обновляем уровень звука (100мс для плавности без мерцания)
            level = asr.get_audio_level()
            ui.update(level=level, recording=True)
            threading.Event().wait(0.1)
            
    except KeyboardInterrupt:
        pass
    finally:
        ui.stop_live_display()


def run_continuous_mode_simple(asr: RealtimeASR, device_id, output_file, accumulate: bool):
    """Запуск в непрерывном режиме (простой вывод без Rich)."""
    last_line_len = 0
    
    def on_result(text: str):
        nonlocal last_line_len
        
        # Очищаем предыдущую строку
        clear_str = " " * last_line_len
        print(f"\r{clear_str}", end="")
        
        # Формируем вывод
        level = asr.get_audio_level()
        bars = int(level * 30)
        level_str = "▓" * min(bars, 10) + "░" * max(0, 10 - bars)
        
        # В режиме накопления показываем весь текст
        if accumulate:
            full_text = asr.get_accumulated_text()
            if full_text:
                display_text = f"{full_text} | {text}"
            else:
                display_text = text
        else:
            display_text = text
        
        output = f"🎤 [{level_str}] {display_text}"
        last_line_len = len(output) + 10
        
        print(f"\r{output}", end="", flush=True)
        
        # Записываем в файл
        if output_file:
            timestamp = datetime.now().strftime("%H:%M:%S")
            output_file.write(f"[{timestamp}] {text}\n")
            output_file.flush()
    
    asr.on_result = on_result
    
    try:
        asr.start(device=device_id)
        
        # Бесконечный цикл ожидания
        while True:
            threading.Event().wait(1)
            
    except KeyboardInterrupt:
        pass


def run_push_to_talk_mode(asr: RealtimeASR, device_id, output_file, ptt_key: str, ui, codex_enabled: bool = True):
    """Запуск в режиме push-to-talk."""
    if not KEYBOARD_AVAILABLE:
        ui.print_error("Для режима push-to-talk требуется библиотека 'keyboard'")
        ui.print_info("Установите: pip install keyboard")
        return
    
    ui.print_info(f"Режим Push-to-Talk активен!")
    ui.print_info(f"Удерживайте [{ptt_key.upper()}] для записи")
    ui.print_info(f"Отпустите для распознавания + копирования в буфер обмена")
    ui.print_info(f"Нажмите [ESC] для выхода\n")
    
    # Состояние
    is_recording = False
    segments: list = []
    
    # Нормализуем имя клавиши
    key_name = ptt_key.lower()
    was_pressed = False
    
    try:
        # Запускаем ASR (но не записываем сразу)
        asr.recording = False
        asr.start(device=device_id)
        
        # Запускаем Live Display
        ui.start_live_display()
        ui.print_info("Ожидание клавиши...")
        
        # Основной цикл с polling
        while True:
            # Проверяем ESC
            if keyboard.is_pressed('esc'):
                break
            
            # Проверяем состояние PTT клавиши
            is_key_pressed = keyboard.is_pressed(key_name)
            
            # Обновляем уровень звука
            level = asr.get_audio_level()
            ui.update(level=level, recording=is_recording)
            
            # Клавиша нажата — начинаем запись
            if is_key_pressed and not was_pressed:
                was_pressed = True
                is_recording = True
                asr.start_recording()
                ui.update(recording=True, text="")
            
            # Клавиша отпущена — останавливаем запись
            elif not is_key_pressed and was_pressed:
                was_pressed = False
                is_recording = False
                text = asr.stop_recording()
                
                ui.update(recording=False)
                
                if text:
                    segments.append(text)
                    ui.add_segment(text)
                    
                    # Копируем в буфер обмена
                    copied = copy_to_clipboard(text)
                    
                    # Запускаем codex с распознанным текстом (если включено)
                    codex_launched = run_codex_query(text) if codex_enabled else False
                    
                    # Обновляем текст в UI вместо перезапуска Live (без мерцания)
                    if codex_launched:
                        status_text = "📋 Скопировано! 🚀 Codex запущен!"
                    elif copied:
                        status_text = "📋 Скопировано!"
                    else:
                        status_text = ""
                    ui.update(text=f"{text} {status_text}", recording=False)
                    
                    # Записываем в файл
                    if output_file:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        output_file.write(f"[{timestamp}] {text}\n")
                        output_file.flush()
            
            threading.Event().wait(0.1)  # Увеличено до 100мс для стабильности
            
    except KeyboardInterrupt:
        pass
    finally:
        ui.stop_live_display()
        
        # Если запись была активна — финализируем
        if is_recording:
            text = asr.stop_recording()
            if text:
                segments.append(text)
                ui.add_segment(text)
                copied = copy_to_clipboard(text)
                ui.print_segment(text, copied=copied)
    
    # Выводим полный текст
    if segments:
        ui.segments = [(datetime.now().strftime("%H:%M:%S"), s) for s in segments]
        ui.print_final_transcript()
        
        # Сохраняем полный текст
        if output_file:
            full_text = " ".join(segments)
            output_file.write(f"\n--- ПОЛНАЯ ТРАНСКРИПЦИЯ ---\n{full_text}\n")


def main():
    parser = argparse.ArgumentParser(
        description="GigaAM Realtime Speech Recognition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python run_live.py                    # Запуск с микрофоном по умолчанию
  python run_live.py --list-devices     # Показать все аудиоустройства
  python run_live.py --interactive      # Интерактивный выбор устройства
  python run_live.py --device 2         # Использовать устройство #2
  python run_live.py --device "Realtek" # Поиск по имени
  python run_live.py --loopback         # Захват системного звука
  python run_live.py -o transcript.txt  # Сохранить транскрипцию в файл
  python run_live.py --push-to-talk     # Режим push-to-talk (ПРОБЕЛ)
  python run_live.py --ptt-key ctrl     # Push-to-talk с клавишей CTRL
  python run_live.py --accumulate       # Накопление текста
  python run_live.py --no-rich          # Отключить Rich UI
        """
    )
    
    parser.add_argument(
        '--list-devices', '-l',
        action='store_true',
        help='Показать список доступных аудиоустройств и выйти'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Интерактивный выбор аудиоустройства'
    )
    
    parser.add_argument(
        '--device', '-d',
        type=str,
        default=None,
        help='ID или часть имени аудиоустройства'
    )
    
    parser.add_argument(
        '--loopback',
        action='store_true',
        help='Использовать loopback устройство (захват системного звука)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Файл для сохранения транскрипции'
    )
    
    parser.add_argument(
        '--buffer',
        type=float,
        default=3.0,
        help='Размер буфера в секундах (по умолчанию: 3.0)'
    )
    
    parser.add_argument(
        '--vad-threshold',
        type=float,
        default=0.0,
        help='Порог VAD (0 = отключён, рекомендуется 0.01)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='gigaam-v3-e2e-rnnt',
        help='Имя модели (по умолчанию: gigaam-v3-e2e-rnnt)'
    )
    
    parser.add_argument(
        '--push-to-talk', '--ptt',
        action='store_true',
        help='Режим push-to-talk (запись при удержании клавиши)'
    )
    
    parser.add_argument(
        '--ptt-key',
        type=str,
        default='space',
        help='Клавиша для push-to-talk (по умолчанию: space). Варианты: space, ctrl, shift, alt'
    )
    
    parser.add_argument(
        '--accumulate', '-a',
        action='store_true',
        help='Режим накопления текста (объединение буферов)'
    )
    
    parser.add_argument(
        '--no-rich',
        action='store_true',
        help='Отключить Rich UI (использовать простой вывод)'
    )
    
    args = parser.parse_args()
    
    # Загружаем конфиг и применяем значения (CLI args имеют приоритет)
    config = load_config()
    
    # Применяем значения из конфига если не заданы через CLI
    if args.device is None and config.get('device'):
        args.device = config['device']
    if not args.loopback and config.get('loopback'):
        args.loopback = True
    if not args.interactive and config.get('interactive'):
        args.interactive = True
    if not args.push_to_talk and config.get('push_to_talk'):
        args.push_to_talk = True
    if args.ptt_key == 'space' and config.get('ptt_key'):
        args.ptt_key = config['ptt_key']
    if not args.accumulate and config.get('accumulate'):
        args.accumulate = True
    if not args.no_rich and config.get('no_rich'):
        args.no_rich = True
    if args.buffer == 3.0 and config.get('buffer'):
        args.buffer = config['buffer']
    if args.vad_threshold == 0.0 and config.get('vad_threshold'):
        args.vad_threshold = config['vad_threshold']
    if args.model == 'gigaam-v3-e2e-rnnt' and config.get('model'):
        args.model = config['model']
    if args.output is None and config.get('output'):
        args.output = config['output']
    
    # Флаг для codex
    codex_enabled = config.get('codex_enabled', True)
    
    # Определяем использование Rich
    use_rich = RICH_AVAILABLE and not args.no_rich
    
    # Создаём UI
    if use_rich:
        from src.ui.console import RichConsoleUI
        ui = RichConsoleUI(show_timestamps=True, show_level=True)
    else:
        from src.ui.console import SimpleConsoleUI
        ui = SimpleConsoleUI()
    
    # Показать устройства
    if args.list_devices:
        if use_rich:
            devices_tuple = list_audio_devices(show_output=False)
            input_devices, output_devices = devices_tuple
            if input_devices:
                selector = DeviceSelector()
                # Просто показываем таблицу без выбора
                selector.select_device(devices_tuple, title="Доступные устройства")
            else:
                ui.print_error("Аудиоустройства не найдены!")
        else:
            list_audio_devices(show_output=True)
        return 0
    
    # Проверка keyboard для PTT
    if args.push_to_talk and not KEYBOARD_AVAILABLE:
        ui.print_error("Для режима push-to-talk требуется библиотека 'keyboard'")
        ui.print_info("Установите: pip install keyboard")
        return 1
    
    # Баннер
    ui.print_banner()
    
    # Определяем устройство
    device_id = None
    device_name = "по умолчанию"
    
    # Интерактивный выбор
    if args.interactive:
        device_id = select_device_interactive(ui)
        if device_id is None:
            ui.print_warning("Отменено пользователем")
            return 0
        device_info = get_device_info(device_id)
        device_name = device_info['name'] if device_info else f"ID {device_id}"
    
    elif args.loopback:
        loopback_id, loopback_name = get_loopback_device()
        if loopback_id is None:
            ui.print_error("Loopback устройство не найдено!")
            ui.print_info("Советы:")
            ui.print_info("  1. Включите 'Stereo Mix' в настройках звука Windows")
            ui.print_info("  2. Или установите VB-Cable / VoiceMeeter")
            ui.print_info("  3. Используйте --list-devices для просмотра доступных устройств")
            return 1
        device_id = loopback_id
        device_name = loopback_name
        ui.print_success(f"Loopback: {loopback_name}")
    
    elif args.device:
        try:
            device_id = parse_device_arg(args.device)
            device_info = get_device_info(device_id)
            device_name = device_info['name'] if device_info else f"ID {device_id}"
        except ValueError as e:
            ui.print_error(str(e))
            ui.print_info("Используйте --list-devices для просмотра доступных устройств")
            return 1
    
    # Открываем файл для записи (если указан)
    output_file = None
    if args.output:
        try:
            output_file = open(args.output, 'a', encoding='utf-8')
            ui.print_info(f"Запись в файл: {args.output}")
        except IOError as e:
            ui.print_error(f"Ошибка открытия файла: {e}")
            return 1
    
    # Загружаем модель
    ui.print_info(f"Загрузка модели {args.model}...")
    try:
        model = onnx_asr.load_model(args.model)
    except Exception as e:
        ui.print_error(f"Ошибка загрузки модели: {e}")
        return 1
    
    ui.print_success("Модель загружена!")
    
    # Создаём ASR
    # В режиме PTT автоматически включаем накопление аудио
    use_accumulate = args.accumulate or args.push_to_talk
    
    asr = RealtimeASR(
        model=model,
        buffer_seconds=args.buffer,
        vad_threshold=args.vad_threshold,
        accumulate_mode=use_accumulate,
    )
    
    # Показываем статус
    mode = "push_to_talk" if args.push_to_talk else "continuous"
    ui.print_status(
        model=args.model,
        device=device_name,
        buffer=args.buffer,
        vad_threshold=args.vad_threshold,
        mode=mode
    )
    
    print()  # Пустая строка
    
    if args.push_to_talk:
        ui.print_info("🚀 Режим Push-to-Talk!")
        ui.print_info(f"   Удерживайте [{args.ptt_key.upper()}] для записи")
        ui.print_info("   Нажмите [ESC] для выхода")
    else:
        ui.print_info("🚀 Запуск realtime распознавания!")
        ui.print_info("   Говорите в микрофон...")
        ui.print_info("   Нажмите Ctrl+C для выхода")
    
    print()
    
    try:
        if args.push_to_talk:
            run_push_to_talk_mode(asr, device_id, output_file, args.ptt_key, ui, codex_enabled)
        else:
            if use_rich:
                run_continuous_mode(asr, device_id, output_file, args.accumulate, ui)
            else:
                run_continuous_mode_simple(asr, device_id, output_file, args.accumulate)
            
    except Exception as e:
        ui.print_error(f"Ошибка: {e}")
        return 1
    finally:
        ui.print_info("Остановка...")
        asr.stop()
        if output_file:
            output_file.close()
            ui.print_success(f"Транскрипция сохранена в {args.output}")
    
    ui.print_success("До свидания!")
    return 0


if __name__ == "__main__":
    sys.exit(main())