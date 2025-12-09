"""
GigaAM UI Components

Модули для интерфейса пользователя.

Компоненты:
- Console UI (Rich-based CLI)
- GUI (PyQt6-based desktop app) — загружается лениво
- Widgets (Reusable PyQt6 components) — загружается лениво
"""

from .console import RichConsoleUI, DeviceSelector, SimpleConsoleUI, RICH_AVAILABLE

# GUI модули загружаются лениво, чтобы не конфликтовать с onnxruntime
# Используйте: from src.ui.gui import GigaAMWindow, run_gui
# Или: from src.ui.widgets import VUMeter, ...

PYQT6_AVAILABLE = None  # Определяется при первом обращении

def _check_pyqt6():
    """Проверяет доступность PyQt6."""
    global PYQT6_AVAILABLE
    if PYQT6_AVAILABLE is None:
        try:
            import PyQt6
            PYQT6_AVAILABLE = True
        except ImportError:
            PYQT6_AVAILABLE = False
    return PYQT6_AVAILABLE


def __getattr__(name):
    """Ленивый импорт GUI компонентов."""
    # GUI виджеты
    if name in ('VUMeter', 'TranscriptionWidget', 'StatusIndicator', 
                'DeviceComboBox', 'RecordButton'):
        if _check_pyqt6():
            from . import widgets
            return getattr(widgets, name)
        raise ImportError(f"PyQt6 required for {name}")
    
    # Главное окно
    if name in ('GigaAMWindow', 'run_gui'):
        if _check_pyqt6():
            from . import gui
            return getattr(gui, name)
        raise ImportError(f"PyQt6 required for {name}")
    
    raise AttributeError(f"module 'src.ui' has no attribute '{name}'")


__all__ = [
    # Console UI (всегда доступны)
    'RichConsoleUI',
    'DeviceSelector', 
    'SimpleConsoleUI',
    'RICH_AVAILABLE',
    # GUI (требует PyQt6)
    'VUMeter',
    'TranscriptionWidget',
    'StatusIndicator',
    'DeviceComboBox',
    'RecordButton',
    'GigaAMWindow',
    'run_gui',
    'PYQT6_AVAILABLE',
]
