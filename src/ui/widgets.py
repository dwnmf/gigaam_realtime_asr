"""
GigaAM Custom PyQt6 Widgets

Кастомные виджеты для GUI приложения:
- VUMeter: Индикатор уровня звука с градиентом
- TranscriptionWidget: Область отображения транскрипции
- StatusBar: Панель статуса с иконками
- DeviceComboBox: Выпадающий список устройств
"""

from typing import Optional, List, Tuple
from datetime import datetime

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
        QPushButton, QTextEdit, QComboBox, QFrame,
        QScrollArea, QSizePolicy, QGroupBox, QProgressBar
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
    from PyQt6.QtGui import (
        QPainter, QColor, QLinearGradient, QPen, QBrush,
        QFont, QPalette, QFontDatabase
    )
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


if PYQT6_AVAILABLE:

    class VUMeter(QWidget):
        """
        Визуальный индикатор уровня звука с градиентом.
        
        Цвета: зелёный (тихо) -> жёлтый (норма) -> красный (громко)
        """
        
        def __init__(self, parent=None, orientation=Qt.Orientation.Horizontal):
            super().__init__(parent)
            self._level = 0.0  # 0.0 - 1.0
            self._peak = 0.0
            self._peak_hold_time = 30  # frames
            self._peak_counter = 0
            self._orientation = orientation
            
            # Размеры
            if orientation == Qt.Orientation.Horizontal:
                self.setMinimumSize(200, 24)
                self.setMaximumHeight(32)
            else:
                self.setMinimumSize(24, 100)
                self.setMaximumWidth(32)
            
            # Цвета градиента
            self._color_low = QColor(0, 255, 0)     # Зелёный
            self._color_mid = QColor(255, 255, 0)   # Жёлтый  
            self._color_high = QColor(255, 0, 0)    # Красный
            
            # Фон
            self._bg_color = QColor(40, 40, 40)
            self._border_color = QColor(80, 80, 80)
            
            # Анимация
            self._animation = QPropertyAnimation(self, b"level")
            self._animation.setDuration(50)
            self._animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        def get_level(self) -> float:
            return self._level
        
        def set_level(self, value: float):
            """Устанавливает уровень (0.0 - 1.0)."""
            value = max(0.0, min(1.0, value))
            self._level = value
            
            # Обновляем пик
            if value > self._peak:
                self._peak = value
                self._peak_counter = 0
            else:
                self._peak_counter += 1
                if self._peak_counter > self._peak_hold_time:
                    self._peak = max(0, self._peak - 0.02)
            
            self.update()
        
        level = property(get_level, set_level)
        
        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            rect = self.rect().adjusted(1, 1, -1, -1)
            
            # Фон
            painter.fillRect(rect, self._bg_color)
            
            # Градиент
            if self._orientation == Qt.Orientation.Horizontal:
                gradient = QLinearGradient(0, 0, rect.width(), 0)
            else:
                gradient = QLinearGradient(0, rect.height(), 0, 0)
            
            gradient.setColorAt(0.0, self._color_low)
            gradient.setColorAt(0.5, self._color_mid)
            gradient.setColorAt(1.0, self._color_high)
            
            # Заполняем по уровню
            if self._orientation == Qt.Orientation.Horizontal:
                fill_width = int(rect.width() * self._level)
                fill_rect = rect.adjusted(0, 0, -(rect.width() - fill_width), 0)
            else:
                fill_height = int(rect.height() * self._level)
                fill_rect = rect.adjusted(0, rect.height() - fill_height, 0, 0)
            
            painter.fillRect(fill_rect, QBrush(gradient))
            
            # Пиковая метка
            if self._peak > 0.01:
                painter.setPen(QPen(Qt.GlobalColor.white, 2))
                if self._orientation == Qt.Orientation.Horizontal:
                    peak_x = int(rect.width() * self._peak)
                    painter.drawLine(peak_x, rect.top(), peak_x, rect.bottom())
                else:
                    peak_y = int(rect.height() * (1 - self._peak))
                    painter.drawLine(rect.left(), peak_y, rect.right(), peak_y)
            
            # Рамка
            painter.setPen(QPen(self._border_color, 1))
            painter.drawRoundedRect(rect, 3, 3)
    
    
    class TranscriptionWidget(QFrame):
        """
        Виджет отображения транскрипции.
        
        Показывает:
        - Текущий распознаваемый текст (с подсветкой)
        - История сегментов с временными метками
        """
        
        textCopied = pyqtSignal(str)  # Сигнал при копировании текста
        
        def __init__(self, parent=None, show_timestamps=True):
            super().__init__(parent)
            self.show_timestamps = show_timestamps
            self.segments: List[Tuple[str, str]] = []  # (timestamp, text)
            
            self._setup_ui()
            self._apply_style()
        
        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)
            
            # Текущий текст (большой, выделенный)
            self.current_label = QLabel("Ожидание речи...")
            self.current_label.setObjectName("currentText")
            self.current_label.setWordWrap(True)
            self.current_label.setMinimumHeight(60)
            self.current_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(self.current_label)
            
            # Разделитель
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setObjectName("separator")
            layout.addWidget(separator)
            
            # История (прокручиваемая)
            self.history_text = QTextEdit()
            self.history_text.setObjectName("historyText")
            self.history_text.setReadOnly(True)
            self.history_text.setMinimumHeight(100)
            layout.addWidget(self.history_text, stretch=1)
            
            # Кнопки
            btn_layout = QHBoxLayout()
            
            self.copy_btn = QPushButton("📋 Копировать")
            self.copy_btn.setObjectName("copyBtn")
            self.copy_btn.clicked.connect(self._on_copy)
            btn_layout.addWidget(self.copy_btn)
            
            self.clear_btn = QPushButton("🗑️ Очистить")
            self.clear_btn.setObjectName("clearBtn")
            self.clear_btn.clicked.connect(self.clear)
            btn_layout.addWidget(self.clear_btn)
            
            btn_layout.addStretch()
            layout.addLayout(btn_layout)
        
        def _apply_style(self):
            self.setStyleSheet("""
                TranscriptionWidget {
                    background-color: #1e1e1e;
                    border: 1px solid #3d3d3d;
                    border-radius: 8px;
                }
                
                #currentText {
                    color: #00d9ff;
                    font-size: 18px;
                    font-weight: bold;
                    padding: 8px;
                    background-color: #252525;
                    border-radius: 4px;
                }
                
                #separator {
                    background-color: #3d3d3d;
                }
                
                #historyText {
                    color: #cccccc;
                    font-size: 14px;
                    background-color: #1a1a1a;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                }
                
                QPushButton {
                    background-color: #3d3d3d;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 13px;
                }
                
                QPushButton:hover {
                    background-color: #4d4d4d;
                }
                
                QPushButton:pressed {
                    background-color: #2d2d2d;
                }
            """)
        
        def set_current_text(self, text: str, highlight: bool = True):
            """Устанавливает текущий распознаваемый текст."""
            if highlight and text:
                self.current_label.setText(text)
                self.current_label.setStyleSheet("""
                    color: #00d9ff;
                    font-size: 18px;
                    font-weight: bold;
                    padding: 8px;
                    background-color: #252525;
                    border-radius: 4px;
                """)
            elif text:
                self.current_label.setText(text)
            else:
                self.current_label.setText("Ожидание речи...")
                self.current_label.setStyleSheet("""
                    color: #666666;
                    font-size: 18px;
                    font-style: italic;
                    padding: 8px;
                    background-color: #252525;
                    border-radius: 4px;
                """)
        
        def add_segment(self, text: str, timestamp: Optional[str] = None):
            """Добавляет завершённый сегмент в историю."""
            if timestamp is None:
                timestamp = datetime.now().strftime("%H:%M:%S")
            
            self.segments.append((timestamp, text))
            
            # Добавляем в историю
            if self.show_timestamps:
                line = f"<span style='color: #666666;'>[{timestamp}]</span> {text}"
            else:
                line = text
            
            self.history_text.append(line)
            
            # Прокручиваем вниз
            scrollbar = self.history_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
        def get_full_text(self) -> str:
            """Возвращает весь накопленный текст."""
            return " ".join(text for _, text in self.segments)
        
        def clear(self):
            """Очищает историю."""
            self.segments.clear()
            self.history_text.clear()
            self.set_current_text("")
        
        def _on_copy(self):
            """Копирует текст в буфер обмена."""
            full_text = self.get_full_text()
            if full_text:
                from PyQt6.QtWidgets import QApplication
                clipboard = QApplication.clipboard()
                clipboard.setText(full_text)
                self.textCopied.emit(full_text)
    
    
    class StatusIndicator(QWidget):
        """
        Индикатор статуса (точка с цветом).
        """
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedSize(16, 16)
            self._color = QColor(100, 100, 100)  # Серый (idle)
            self._pulsing = False
            self._pulse_opacity = 1.0
            
            self._pulse_timer = QTimer(self)
            self._pulse_timer.timeout.connect(self._update_pulse)
            self._pulse_direction = -1
        
        def set_status(self, status: str):
            """
            Устанавливает статус:
            - 'idle': серый
            - 'ready': зелёный
            - 'recording': красный (пульсирует)
            - 'paused': жёлтый
            - 'error': оранжевый
            """
            self._pulsing = False
            self._pulse_timer.stop()
            
            if status == 'idle':
                self._color = QColor(100, 100, 100)
            elif status == 'ready':
                self._color = QColor(76, 175, 80)  # Зелёный
            elif status == 'recording':
                self._color = QColor(244, 67, 54)  # Красный
                self._pulsing = True
                self._pulse_timer.start(50)
            elif status == 'paused':
                self._color = QColor(255, 193, 7)  # Жёлтый
            elif status == 'error':
                self._color = QColor(255, 152, 0)  # Оранжевый
            
            self.update()
        
        def _update_pulse(self):
            """Обновляет пульсацию."""
            self._pulse_opacity += 0.05 * self._pulse_direction
            if self._pulse_opacity <= 0.3:
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
            
            # Внешний круг (тень)
            painter.setPen(Qt.PenStyle.NoPen)
            shadow = QColor(0, 0, 0, 50)
            painter.setBrush(shadow)
            painter.drawEllipse(2, 2, 12, 12)
            
            # Основной круг
            painter.setBrush(color)
            painter.drawEllipse(1, 1, 12, 12)
            
            # Блик
            highlight = QColor(255, 255, 255, 80)
            painter.setBrush(highlight)
            painter.drawEllipse(3, 3, 4, 4)
    
    
    class DeviceComboBox(QComboBox):
        """
        Выпадающий список аудиоустройств.
        """
        
        deviceChanged = pyqtSignal(int, str)  # (device_id, device_name)
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.devices: List[Tuple[int, str, int]] = []  # (id, name, channels)
            
            self._apply_style()
            self.currentIndexChanged.connect(self._on_index_changed)
        
        def _apply_style(self):
            self.setStyleSheet("""
                DeviceComboBox {
                    background-color: #2d2d2d;
                    color: white;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 14px;
                    min-width: 300px;
                }
                
                DeviceComboBox:hover {
                    border-color: #00d9ff;
                }
                
                DeviceComboBox::drop-down {
                    border: none;
                    width: 30px;
                }
                
                DeviceComboBox QAbstractItemView {
                    background-color: #2d2d2d;
                    color: white;
                    selection-background-color: #00d9ff;
                    selection-color: black;
                    border: 1px solid #3d3d3d;
                }
            """)
        
        def set_devices(self, devices: List[Tuple[int, str, int]]):
            """Заполняет список устройств."""
            self.devices = devices
            self.clear()
            
            for idx, name, channels in devices:
                # Определяем тип устройства
                name_lower = name.lower()
                loopback_keywords = ['loopback', 'stereo mix', 'what u hear', 'wave out']
                
                if any(kw in name_lower for kw in loopback_keywords):
                    prefix = "🔄 "
                else:
                    prefix = "🎤 "
                
                display_name = f"{prefix}{name} ({channels}ch)"
                self.addItem(display_name, userData=idx)
        
        def get_selected_device_id(self) -> Optional[int]:
            """Возвращает ID выбранного устройства."""
            if self.currentIndex() >= 0:
                return self.currentData()
            return None
        
        def select_device_by_id(self, device_id: int) -> bool:
            """Выбирает устройство по ID."""
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
        Кнопка записи с визуальными эффектами.
        """
        
        recordingStarted = pyqtSignal()
        recordingStopped = pyqtSignal()
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self._is_recording = False
            self.setText("🎙 Записывать")
            self.setCheckable(True)
            
            self._apply_style()
            self.clicked.connect(self._on_clicked)
        
        def _apply_style(self):
            self.setStyleSheet("""
                RecordButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 24px;
                    padding: 12px 32px;
                    font-size: 16px;
                    font-weight: bold;
                    min-width: 160px;
                    min-height: 48px;
                }
                
                RecordButton:hover {
                    background-color: #45a049;
                }
                
                RecordButton:pressed {
                    background-color: #3d8b40;
                }
                
                RecordButton:checked {
                    background-color: #f44336;
                }
                
                RecordButton:checked:hover {
                    background-color: #da190b;
                }
            """)
        
        def _on_clicked(self, checked: bool):
            self._is_recording = checked
            if checked:
                self.setText("⏹ Остановить")
                self.recordingStarted.emit()
            else:
                self.setText("🎙 Записывать")
                self.recordingStopped.emit()
        
        def set_recording(self, recording: bool):
            """Программно устанавливает состояние записи."""
            if recording != self._is_recording:
                self._is_recording = recording
                self.setChecked(recording)
                if recording:
                    self.setText("⏹ Остановить")
                else:
                    self.setText("🎙 Записывать")
        
        def is_recording(self) -> bool:
            return self._is_recording

else:
    # Заглушки если PyQt6 не установлен
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
