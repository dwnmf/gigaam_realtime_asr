"""
GigaAM Custom PyQt6 Widgets — Minimal Professional Design

Кастомные виджеты для GUI приложения.
Минималистичный, строгий дизайн без лишних украшений.
"""

from typing import Optional, List, Tuple
from datetime import datetime

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
        QPushButton, QTextEdit, QComboBox, QFrame,
        QScrollArea, QSizePolicy, QGroupBox, QProgressBar
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtProperty, QSize, QPropertyAnimation, QEasingCurve
    from PyQt6.QtGui import (
        QPainter, QColor, QLinearGradient, QPen, QBrush,
        QFont, QPalette, QFontDatabase
    )
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════
# ЦВЕТОВАЯ ПАЛИТРА — Строгая, профессиональная
# ═══════════════════════════════════════════════════════════════════════════

class Colors:
    """Централизованная цветовая схема."""
    # Фоны
    BG_DARK = "#0d0d0d"
    BG_PRIMARY = "#141414"
    BG_SECONDARY = "#1a1a1a"
    BG_ELEVATED = "#1f1f1f"
    BG_SURFACE = "#252525"
    
    # Границы
    BORDER = "#2a2a2a"
    BORDER_SUBTLE = "#1f1f1f"
    
    # Текст
    TEXT_PRIMARY = "#e8e8e8"
    TEXT_SECONDARY = "#888888"
    TEXT_MUTED = "#555555"
    
    # Акценты
    ACCENT = "#3b82f6"          # Синий
    ACCENT_HOVER = "#60a5fa"
    ACCENT_ACTIVE = "#2563eb"
    
    # Состояния
    SUCCESS = "#22c55e"
    WARNING = "#eab308"
    DANGER = "#ef4444"
    
    # Специальные
    RECORDING = "#dc2626"
    RECORDING_GLOW = "#7f1d1d"


if PYQT6_AVAILABLE:

    class VUMeter(QWidget):
        """
        Минималистичный индикатор уровня звука.
        
        Простая полоса с градиентом от синего к красному.
        """
        
        def __init__(self, parent=None, orientation=Qt.Orientation.Horizontal):
            super().__init__(parent)
            self._level = 0.0
            self._peak = 0.0
            self._peak_hold_time = 30
            self._peak_counter = 0
            self._orientation = orientation
            
            if orientation == Qt.Orientation.Horizontal:
                self.setMinimumSize(200, 6)
                self.setMaximumHeight(8)
            else:
                self.setMinimumSize(6, 100)
                self.setMaximumWidth(8)
            
            self._animation = QPropertyAnimation(self, b"level")
            self._animation.setDuration(50)
            self._animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        def get_level(self) -> float:
            return self._level
        
        def set_level(self, value: float):
            value = max(0.0, min(1.0, value))
            self._level = value
            
            if value > self._peak:
                self._peak = value
                self._peak_counter = 0
            else:
                self._peak_counter += 1
                if self._peak_counter > self._peak_hold_time:
                    self._peak = max(0, self._peak - 0.03)
            
            self.update()
        
        level = pyqtProperty(float, fget=get_level, fset=set_level)
        
        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            rect = self.rect()
            
            # Фон — тёмная полоса
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(Colors.BG_DARK))
            painter.drawRoundedRect(rect, 2, 2)
            
            # Градиент заполнения
            if self._orientation == Qt.Orientation.Horizontal:
                gradient = QLinearGradient(0, 0, rect.width(), 0)
            else:
                gradient = QLinearGradient(0, rect.height(), 0, 0)
            
            # Синий → Жёлтый → Красный
            gradient.setColorAt(0.0, QColor(Colors.ACCENT))
            gradient.setColorAt(0.6, QColor(Colors.WARNING))
            gradient.setColorAt(1.0, QColor(Colors.DANGER))
            
            # Заполнение по уровню
            if self._orientation == Qt.Orientation.Horizontal:
                fill_width = int(rect.width() * self._level)
                fill_rect = rect.adjusted(0, 0, -(rect.width() - fill_width), 0)
            else:
                fill_height = int(rect.height() * self._level)
                fill_rect = rect.adjusted(0, rect.height() - fill_height, 0, 0)
            
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(fill_rect, 2, 2)


    class TranscriptionWidget(QFrame):
        """
        Виджет транскрипции — минимальный дизайн.
        
        Чистый текстовый вывод без лишних украшений.
        """
        
        textCopied = pyqtSignal(str)
        
        def __init__(self, parent=None, show_timestamps=True):
            super().__init__(parent)
            self.show_timestamps = show_timestamps
            self.segments: List[Tuple[str, str]] = []
            
            self._setup_ui()
            self._apply_style()
        
        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)
            
            # Текущий текст
            self.current_label = QLabel("")
            self.current_label.setObjectName("currentText")
            self.current_label.setWordWrap(True)
            self.current_label.setMinimumHeight(48)
            self.current_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(self.current_label)
            
            # История
            self.history_text = QTextEdit()
            self.history_text.setObjectName("historyText")
            self.history_text.setReadOnly(True)
            self.history_text.setMinimumHeight(120)
            self.history_text.setPlaceholderText("Здесь появится распознанный текст...")
            layout.addWidget(self.history_text, stretch=1)
        
        def _apply_style(self):
            self.setStyleSheet(f"""
                TranscriptionWidget {{
                    background-color: {Colors.BG_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 4px;
                }}
                
                #currentText {{
                    color: {Colors.TEXT_PRIMARY};
                    font-size: 15px;
                    font-weight: 500;
                    padding: 12px;
                    background-color: {Colors.BG_SECONDARY};
                    border-radius: 4px;
                    border: 1px solid {Colors.BORDER_SUBTLE};
                }}
                
                #historyText {{
                    color: {Colors.TEXT_SECONDARY};
                    font-size: 13px;
                    background-color: {Colors.BG_DARK};
                    border: none;
                    border-radius: 4px;
                    padding: 12px;
                    selection-background-color: {Colors.ACCENT};
                }}
            """)
        
        def set_current_text(self, text: str, highlight: bool = True):
            if text:
                self.current_label.setText(text)
                if highlight:
                    self.current_label.setStyleSheet(f"""
                        color: {Colors.TEXT_PRIMARY};
                        font-size: 15px;
                        font-weight: 500;
                        padding: 12px;
                        background-color: {Colors.BG_SECONDARY};
                        border-radius: 4px;
                        border-left: 3px solid {Colors.ACCENT};
                    """)
            else:
                self.current_label.setText("")
                self.current_label.setStyleSheet(f"""
                    color: {Colors.TEXT_MUTED};
                    font-size: 15px;
                    font-style: italic;
                    padding: 12px;
                    background-color: {Colors.BG_SECONDARY};
                    border-radius: 4px;
                """)
        
        def add_segment(self, text: str, timestamp: Optional[str] = None):
            if timestamp is None:
                timestamp = datetime.now().strftime("%H:%M:%S")
            
            self.segments.append((timestamp, text))
            
            if self.show_timestamps:
                line = f"<span style='color: {Colors.TEXT_MUTED};'>[{timestamp}]</span>  {text}"
            else:
                line = text
            
            self.history_text.append(line)
            
            scrollbar = self.history_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
        def get_full_text(self) -> str:
            return " ".join(text for _, text in self.segments)
        
        def clear(self):
            self.segments.clear()
            self.history_text.clear()
            self.set_current_text("")


    class StatusIndicator(QWidget):
        """
        Простой индикатор статуса — маленький круг.
        """
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedSize(10, 10)
            self._color = QColor(Colors.TEXT_MUTED)
            self._pulsing = False
            self._pulse_opacity = 1.0
            
            self._pulse_timer = QTimer(self)
            self._pulse_timer.timeout.connect(self._update_pulse)
            self._pulse_direction = -1
        
        def set_status(self, status: str):
            self._pulsing = False
            self._pulse_timer.stop()
            
            if status == 'idle':
                self._color = QColor(Colors.TEXT_MUTED)
            elif status == 'ready':
                self._color = QColor(Colors.SUCCESS)
            elif status == 'recording':
                self._color = QColor(Colors.RECORDING)
                self._pulsing = True
                self._pulse_timer.start(50)
            elif status == 'paused':
                self._color = QColor(Colors.WARNING)
            elif status == 'error':
                self._color = QColor(Colors.DANGER)
            
            self.update()
        
        def _update_pulse(self):
            self._pulse_opacity += 0.08 * self._pulse_direction
            if self._pulse_opacity <= 0.4:
                self._pulse_direction = 1
            elif self._pulse_opacity >= 1.0:
                self._pulse_direction = -1
            self.update()
        
        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            color = QColor(self._color)
            if self._pulsing:
                color.setAlphaF(self._pulse_opacity)
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(0, 0, 10, 10)


    class DeviceComboBox(QComboBox):
        """
        Выпадающий список устройств — чистый дизайн.
        """
        
        deviceChanged = pyqtSignal(int, str)
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.devices: List[Tuple[int, str, int]] = []
            
            self._apply_style()
            self.currentIndexChanged.connect(self._on_index_changed)
        
        def _apply_style(self):
            self.setStyleSheet(f"""
                DeviceComboBox {{
                    background-color: {Colors.BG_ELEVATED};
                    color: {Colors.TEXT_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 4px;
                    padding: 10px 12px;
                    font-size: 13px;
                    min-width: 300px;
                }}
                
                DeviceComboBox:hover {{
                    border-color: {Colors.ACCENT};
                }}
                
                DeviceComboBox:focus {{
                    border-color: {Colors.ACCENT};
                    outline: none;
                }}
                
                DeviceComboBox::drop-down {{
                    border: none;
                    width: 24px;
                }}
                
                DeviceComboBox::down-arrow {{
                    width: 0;
                    height: 0;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid {Colors.TEXT_SECONDARY};
                }}
                
                DeviceComboBox QAbstractItemView {{
                    background-color: {Colors.BG_ELEVATED};
                    color: {Colors.TEXT_PRIMARY};
                    selection-background-color: {Colors.ACCENT};
                    selection-color: white;
                    border: 1px solid {Colors.BORDER};
                    padding: 4px;
                }}
            """)
        
        def set_devices(self, devices: List[Tuple[int, str, int]]):
            self.devices = devices
            self.clear()
            
            for idx, name, channels in devices:
                display_name = f"{name} ({channels}ch)"
                self.addItem(display_name, userData=idx)
        
        def get_selected_device_id(self) -> Optional[int]:
            if self.currentIndex() >= 0:
                return self.currentData()
            return None
        
        def select_device_by_id(self, device_id: int) -> bool:
            for i in range(self.count()):
                if self.itemData(i) == device_id:
                    self.setCurrentIndex(i)
                    return True
            return False
        
        def _on_index_changed(self, index: int):
            if index >= 0 and index < len(self.devices):
                device_id = self.currentData()
                device_name = self.devices[index][1] if index < len(self.devices) else ""
                self.deviceChanged.emit(device_id, device_name)


    class RecordButton(QPushButton):
        """
        Кнопка записи — строгий минимальный стиль.
        """
        
        recordingStarted = pyqtSignal()
        recordingStopped = pyqtSignal()
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self._is_recording = False
            self.setText("Начать запись")
            self.setCheckable(True)
            
            self._apply_style()
            self.clicked.connect(self._on_clicked)
        
        def _apply_style(self):
            self.setStyleSheet(f"""
                RecordButton {{
                    background-color: {Colors.ACCENT};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 12px 24px;
                    font-size: 13px;
                    font-weight: 600;
                    min-width: 140px;
                    min-height: 40px;
                }}
                
                RecordButton:hover {{
                    background-color: {Colors.ACCENT_HOVER};
                }}
                
                RecordButton:pressed {{
                    background-color: {Colors.ACCENT_ACTIVE};
                }}
                
                RecordButton:checked {{
                    background-color: {Colors.RECORDING};
                }}
                
                RecordButton:checked:hover {{
                    background-color: #b91c1c;
                }}
            """)
        
        def _on_clicked(self, checked: bool):
            self._is_recording = checked
            if checked:
                self.setText("Остановить")
                self.recordingStarted.emit()
            else:
                self.setText("Начать запись")
                self.recordingStopped.emit()
        
        def set_recording(self, recording: bool):
            if recording != self._is_recording:
                self._is_recording = recording
                self.setChecked(recording)
                self.setText("Остановить" if recording else "Начать запись")
        
        def is_recording(self) -> bool:
            return self._is_recording


    class ActionButton(QPushButton):
        """
        Вторичная кнопка действия.
        """
        
        def __init__(self, text: str, parent=None):
            super().__init__(text, parent)
            self._apply_style()
        
        def _apply_style(self):
            self.setStyleSheet(f"""
                ActionButton {{
                    background-color: {Colors.BG_SURFACE};
                    color: {Colors.TEXT_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 4px;
                    padding: 10px 20px;
                    font-size: 13px;
                    min-height: 36px;
                }}
                
                ActionButton:hover {{
                    background-color: {Colors.BG_ELEVATED};
                    border-color: {Colors.ACCENT};
                }}
                
                ActionButton:pressed {{
                    background-color: {Colors.BG_SECONDARY};
                }}
            """)


else:
    # Заглушки
    class VUMeter:
        pass
    
    class TranscriptionWidget:
        pass
    
    class StatusIndicator:
        pass
    
    class DeviceComboBox:
        pass
    
    class RecordButton:
        pass
    
    class ActionButton:
        pass

    class Colors:
        pass
