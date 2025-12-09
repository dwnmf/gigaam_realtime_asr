"""
GigaAM Configuration Manager

Управление конфигурацией приложения.
Поддерживает:
- Загрузка/сохранение настроек в JSON
- Значения по умолчанию
- Валидация параметров
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict


# Путь к конфигурации
def get_config_dir() -> Path:
    """Возвращает директорию конфигурации."""
    if os.name == 'nt':  # Windows
        config_dir = Path(os.environ.get('APPDATA', '~')) / 'GigaAM'
    else:  # Linux/Mac
        config_dir = Path.home() / '.config' / 'gigaam'
    
    return config_dir


def get_config_path() -> Path:
    """Возвращает путь к файлу конфигурации."""
    return get_config_dir() / 'config.json'


@dataclass
class DeviceConfig:
    """Настройки аудиоустройства."""
    id: Optional[int] = None
    name: Optional[str] = None
    use_loopback: bool = False


@dataclass
class ASRConfig:
    """Настройки распознавания речи."""
    model: str = "gigaam-v3-e2e-rnnt"
    buffer_seconds: float = 3.0
    vad_threshold: float = 0.01


@dataclass
class UIConfig:
    """Настройки интерфейса."""
    theme: str = "dark"  # dark | light
    font_size: int = 14
    minimize_to_tray: bool = True
    show_audio_level: bool = True
    show_timestamps: bool = True
    use_rich: bool = True  # Использовать Rich для консоли


@dataclass
class OutputConfig:
    """Настройки вывода."""
    auto_copy: bool = True
    save_to_file: bool = False
    file_path: str = "./transcripts/"


@dataclass
class HotkeysConfig:
    """Настройки горячих клавиш."""
    toggle_recording: str = "ctrl+shift+r"
    push_to_talk: str = "space"
    copy_last: str = "ctrl+shift+c"
    show_hide: str = "ctrl+shift+h"
    pause: str = "ctrl+shift+p"


@dataclass  
class GigaAMConfig:
    """Главный класс конфигурации."""
    device: DeviceConfig = field(default_factory=DeviceConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    hotkeys: HotkeysConfig = field(default_factory=HotkeysConfig)
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> 'GigaAMConfig':
        """
        Загружает конфигурацию из файла.
        
        Args:
            path: Путь к файлу. Если None, используется путь по умолчанию.
            
        Returns:
            Объект конфигурации
        """
        if path is None:
            path = get_config_path()
        
        config = cls()
        
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Загружаем вложенные конфиги
                if 'device' in data:
                    config.device = DeviceConfig(**data['device'])
                if 'asr' in data:
                    config.asr = ASRConfig(**data['asr'])
                if 'ui' in data:
                    config.ui = UIConfig(**data['ui'])
                if 'output' in data:
                    config.output = OutputConfig(**data['output'])
                if 'hotkeys' in data:
                    config.hotkeys = HotkeysConfig(**data['hotkeys'])
                    
            except (json.JSONDecodeError, TypeError) as e:
                print(f"⚠️ Ошибка загрузки конфигурации: {e}")
                print("   Используются значения по умолчанию")
        
        return config
    
    def save(self, path: Optional[Path] = None) -> bool:
        """
        Сохраняет конфигурацию в файл.
        
        Args:
            path: Путь к файлу. Если None, используется путь по умолчанию.
            
        Returns:
            True если успешно, False при ошибке
        """
        if path is None:
            path = get_config_path()
        
        try:
            # Создаём директорию если нужно
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Конвертируем в словарь
            data = {
                'device': asdict(self.device),
                'asr': asdict(self.asr),
                'ui': asdict(self.ui),
                'output': asdict(self.output),
                'hotkeys': asdict(self.hotkeys),
            }
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except IOError as e:
            print(f"❌ Ошибка сохранения конфигурации: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует конфигурацию в словарь."""
        return {
            'device': asdict(self.device),
            'asr': asdict(self.asr),
            'ui': asdict(self.ui),
            'output': asdict(self.output),
            'hotkeys': asdict(self.hotkeys),
        }


# Глобальный экземпляр конфигурации (ленивая загрузка)
_config: Optional[GigaAMConfig] = None


def get_config() -> GigaAMConfig:
    """Возвращает глобальный экземпляр конфигурации."""
    global _config
    if _config is None:
        _config = GigaAMConfig.load()
    return _config


def save_config() -> bool:
    """Сохраняет глобальную конфигурацию."""
    global _config
    if _config is not None:
        return _config.save()
    return False


def reset_config():
    """Сбрасывает конфигурацию до значений по умолчанию."""
    global _config
    _config = GigaAMConfig()
    _config.save()
