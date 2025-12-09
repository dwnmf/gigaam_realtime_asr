"""Модуль для работы с аудиоустройствами."""

import sounddevice as sd
from typing import Optional, Tuple, List


def list_audio_devices(show_output: bool = False) -> Tuple[List[Tuple[int, str, int]], List[Tuple[int, str, int]]]:
    """
    Получает список доступных аудиоустройств.
    
    Args:
        show_output: Если True, выводит список в консоль
        
    Returns:
        Кортеж (input_devices, output_devices), где каждый элемент —
        список кортежей (индекс, имя, количество каналов)
    """
    devices = sd.query_devices()
    default_input, default_output = sd.default.device
    
    input_devices = []
    output_devices = []
    
    for idx, device in enumerate(devices):
        max_in = device['max_input_channels']
        max_out = device['max_output_channels']
        name = device['name']
        
        if max_in > 0:
            input_devices.append((idx, name, max_in))
        if max_out > 0:
            output_devices.append((idx, name, max_out))
    
    if show_output:
        print("\n" + "=" * 50)
        print("📋 ДОСТУПНЫЕ АУДИОУСТРОЙСТВА")
        print("=" * 50)
        
        print("\n📥 УСТРОЙСТВА ВВОДА (Микрофоны):")
        print("-" * 40)
        for idx, name, channels in input_devices:
            default_mark = " ⭐ (по умолчанию)" if idx == default_input else ""
            print(f"  [{idx:2d}] 🎤 {name} ({channels} кан.){default_mark}")
        
        print("\n📤 УСТРОЙСТВА ВЫВОДА (Динамики/Наушники):")
        print("-" * 40)
        for idx, name, channels in output_devices:
            default_mark = " ⭐ (по умолчанию)" if idx == default_output else ""
            print(f"  [{idx:2d}] 🔊 {name} ({channels} кан.){default_mark}")
        
        print("\n" + "=" * 50)
        print("💡 Используйте --device <ID> для выбора устройства")
        print("=" * 50 + "\n")
    
    return input_devices, output_devices


def get_device_by_name(name_pattern: str) -> Optional[int]:
    """
    Ищет устройство ввода по части имени (без учёта регистра).
    
    Args:
        name_pattern: Часть имени устройства для поиска
        
    Returns:
        Индекс устройства или None, если не найдено
    """
    devices = sd.query_devices()
    name_lower = name_pattern.lower()
    
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            if name_lower in device['name'].lower():
                return idx
    
    return None


def get_loopback_device() -> Tuple[Optional[int], Optional[str]]:
    """
    Ищет устройство для захвата системного звука (loopback).
    
    Returns:
        Кортеж (индекс, имя) устройства или (None, None), если не найдено
    """
    devices = sd.query_devices()
    
    # Ключевые слова для поиска loopback устройств
    loopback_keywords = [
        'loopback',
        'stereo mix',
        'what u hear',
        'wave out mix',
        'record what you hear',
        'wasapi',
    ]
    
    for idx, device in enumerate(devices):
        name_lower = device['name'].lower()
        # Ищем среди устройств ввода
        if device['max_input_channels'] > 0:
            for keyword in loopback_keywords:
                if keyword in name_lower:
                    return idx, device['name']
    
    return None, None


def get_device_info(device_id: int) -> Optional[dict]:
    """
    Получает информацию об устройстве по ID.
    
    Args:
        device_id: Индекс устройства
        
    Returns:
        Словарь с информацией об устройстве или None
    """
    try:
        return sd.query_devices(device_id)
    except Exception:
        return None


def validate_device(device_id: int) -> Tuple[bool, str]:
    """
    Проверяет, что устройство существует и поддерживает ввод.
    
    Args:
        device_id: Индекс устройства
        
    Returns:
        Кортеж (успех, сообщение)
    """
    device = get_device_info(device_id)
    
    if device is None:
        return False, f"Устройство с ID {device_id} не найдено"
    
    if device['max_input_channels'] == 0:
        return False, f"Устройство '{device['name']}' не поддерживает ввод (это устройство вывода)"
    
    return True, f"Устройство: {device['name']}"
