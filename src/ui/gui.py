"""
GigaAM PyQt6 GUI — Minimal Professional Design

Графический интерфейс для распознавания речи в реальном времени.
Строгий, минималистичный дизайн.
"""

import sys
import threading
from datetime import datetime
from typing import Optional, List, Tuple, Callable
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QFrame, QGroupBox,
        QMessageBox, QSystemTrayIcon, QMenu, QStatusBar,
        QSplitter, QSpacerItem, QSizePolicy
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QSize
    from PyQt6.QtGui import QIcon, QAction, QFont, QCloseEvent, QPalette, QColor
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

if PYQT6_AVAILABLE:
    from .widgets import (
        VUMeter, TranscriptionWidget, StatusIndicator,
        DeviceComboBox, RecordButton, ActionButton, Colors
    )


class ASRSignals(QObject):
    """Сигналы для связи ASR потока с GUI."""
    result_ready = pyqtSignal(str)
    level_updated = pyqtSignal(float)
    error_occurred = pyqtSignal(str)
    segment_complete = pyqtSignal(str)
    status_changed = pyqtSignal(str)


class ASRWorker(QObject):
    """Воркер для запуска ASR в отдельном потоке."""
    
    def __init__(self, asr, device_id: Optional[int] = None):
        super().__init__()
        self.asr = asr
        self.device_id = device_id
        self.signals = ASRSignals()
        self.running = False
    
    def run(self):
        try:
            self.asr.on_result = self._on_result
            self.asr.on_segment_complete = self._on_segment
            
            self.asr.start(device=self.device_id)
            self.running = True
            self.signals.status_changed.emit("recording")
            
        except Exception as e:
            self.signals.error_occurred.emit(str(e))
            self.signals.status_changed.emit("error")
    
    def stop(self):
        self.running = False
        if self.asr:
            self.asr.stop()
        self.signals.status_changed.emit("ready")
    
    def _on_result(self, text: str):
        self.signals.result_ready.emit(text)
    
    def _on_segment(self, text: str):
        self.signals.segment_complete.emit(text)
    
    def get_level(self) -> float:
        if self.asr:
            return self.asr.get_audio_level()
        return 0.0


if PYQT6_AVAILABLE:
    
    class GigaAMWindow(QMainWindow):
        """
        Главное окно GigaAM — минималистичный дизайн.
        """
        
        def __init__(self, model=None, config=None):
            super().__init__()
            
            self.model = model
            self.config = config
            self.asr = None
            self.asr_worker: Optional[ASRWorker] = None
            
            self.is_recording = False
            self.device_id: Optional[int] = None
            
            self._setup_window()
            self._setup_ui()
            self._setup_timers()
            self._apply_theme()
            self._load_devices()
        
        def _setup_window(self):
            self.setWindowTitle("GigaAM")
            self.setMinimumSize(480, 560)
            self.resize(520, 640)
        
        def _setup_ui(self):
            central = QWidget()
            self.setCentralWidget(central)
            
            main_layout = QVBoxLayout(central)
            main_layout.setContentsMargins(20, 20, 20, 20)
            main_layout.setSpacing(16)
            
            # ─── Заголовок ───
            header = QLabel("GigaAM")
            header.setStyleSheet(f"""
                font-size: 20px;
                font-weight: 600;
                color: {Colors.TEXT_PRIMARY};
                margin-bottom: 8px;
            """)
            main_layout.addWidget(header)
            
            # ─── Устройство ───
            device_section = QFrame()
            device_section.setStyleSheet(f"""
                QFrame {{
                    background-color: {Colors.BG_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 6px;
                    padding: 4px;
                }}
            """)
            device_layout = QVBoxLayout(device_section)
            device_layout.setContentsMargins(16, 12, 16, 12)
            device_layout.setSpacing(8)
            
            device_label = QLabel("Устройство ввода")
            device_label.setStyleSheet(f"""
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 1px;
            """)
            device_layout.addWidget(device_label)
            
            self.device_combo = DeviceComboBox()
            self.device_combo.deviceChanged.connect(self._on_device_changed)
            device_layout.addWidget(self.device_combo)
            
            main_layout.addWidget(device_section)
            
            # ─── Транскрипция ───
            self.transcription = TranscriptionWidget(show_timestamps=True)
            self.transcription.textCopied.connect(self._on_text_copied)
            main_layout.addWidget(self.transcription, stretch=1)
            
            # ─── Уровень звука ───
            level_section = QFrame()
            level_section.setStyleSheet(f"""
                QFrame {{
                    background-color: {Colors.BG_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 6px;
                }}
            """)
            level_layout = QHBoxLayout(level_section)
            level_layout.setContentsMargins(16, 12, 16, 12)
            level_layout.setSpacing(12)
            
            self.status_indicator = StatusIndicator()
            self.status_indicator.set_status("idle")
            level_layout.addWidget(self.status_indicator)
            
            self.vu_meter = VUMeter()
            level_layout.addWidget(self.vu_meter, stretch=1)
            
            self.level_value = QLabel("0.00")
            self.level_value.setStyleSheet(f"""
                color: {Colors.TEXT_MUTED};
                font-size: 11px;
                font-family: 'Consolas', 'Monaco', monospace;
                min-width: 32px;
            """)
            level_layout.addWidget(self.level_value)
            
            main_layout.addWidget(level_section)
            
            # ─── Кнопки управления ───
            control_layout = QHBoxLayout()
            control_layout.setSpacing(10)
            
            self.record_btn = RecordButton()
            self.record_btn.recordingStarted.connect(self._start_recording)
            self.record_btn.recordingStopped.connect(self._stop_recording)
            control_layout.addWidget(self.record_btn)
            
            self.copy_btn = ActionButton("Копировать")
            self.copy_btn.clicked.connect(self._copy_all_text)
            control_layout.addWidget(self.copy_btn)
            
            self.clear_btn = ActionButton("Очистить")
            self.clear_btn.clicked.connect(self._clear_text)
            control_layout.addWidget(self.clear_btn)
            
            control_layout.addStretch()
            
            main_layout.addLayout(control_layout)
            
            # ─── Статус бар ───
            self.status_bar = QStatusBar()
            self.status_bar.setStyleSheet(f"""
                QStatusBar {{
                    background-color: {Colors.BG_DARK};
                    color: {Colors.TEXT_MUTED};
                    font-size: 11px;
                    border-top: 1px solid {Colors.BORDER};
                    padding: 4px 8px;
                }}
            """)
            self.setStatusBar(self.status_bar)
            self.status_bar.showMessage("Готов к работе")
        
        def _setup_timers(self):
            self.level_timer = QTimer(self)
            self.level_timer.timeout.connect(self._update_level)
            self.level_timer.setInterval(50)
        
        def _apply_theme(self):
            self.setStyleSheet(f"""
                QMainWindow {{
                    background-color: {Colors.BG_DARK};
                }}
                
                QWidget {{
                    color: {Colors.TEXT_PRIMARY};
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }}
                
                QMessageBox {{
                    background-color: {Colors.BG_ELEVATED};
                }}
                
                QMessageBox QLabel {{
                    color: {Colors.TEXT_PRIMARY};
                }}
                
                QMessageBox QPushButton {{
                    background-color: {Colors.BG_SURFACE};
                    color: {Colors.TEXT_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 4px;
                    padding: 8px 16px;
                    min-width: 70px;
                }}
                
                QMessageBox QPushButton:hover {{
                    border-color: {Colors.ACCENT};
                }}
            """)
        
        def _load_devices(self):
            try:
                from ..audio_devices import list_audio_devices
                
                devices_tuple = list_audio_devices(show_output=False)
                input_devices, output_devices = devices_tuple
                
                self.device_combo.set_devices(input_devices)
                
                if input_devices:
                    self.status_bar.showMessage(f"Найдено устройств: {len(input_devices)}")
                else:
                    self.status_bar.showMessage("Устройства не найдены")
                    
            except Exception as e:
                self.status_bar.showMessage(f"Ошибка: {e}")
        
        def _on_device_changed(self, device_id: int, device_name: str):
            self.device_id = device_id
            self.status_bar.showMessage(f"Выбрано: {device_name}")
            
            if self.is_recording:
                self._stop_recording()
                self._start_recording()
        
        def _start_recording(self):
            if not self.model:
                QMessageBox.warning(
                    self, "Ошибка",
                    "Модель не загружена.\n\n"
                    "Запустите с загрузкой модели или используйте --no-model для тестирования UI."
                )
                self.record_btn.set_recording(False)
                return
            
            self.device_id = self.device_combo.get_selected_device_id()
            
            try:
                from ..realtime_asr import RealtimeASR
                
                self.asr = RealtimeASR(
                    model=self.model,
                    buffer_seconds=3.0,
                    vad_threshold=0.01,
                    accumulate_mode=True
                )
                
                self.asr_worker = ASRWorker(self.asr, self.device_id)
                
                self.asr_worker.signals.result_ready.connect(self._on_asr_result)
                self.asr_worker.signals.error_occurred.connect(self._on_asr_error)
                self.asr_worker.signals.segment_complete.connect(self._on_segment_complete)
                self.asr_worker.signals.status_changed.connect(self._on_status_changed)
                
                self.asr_worker.run()
                
                self.is_recording = True
                self.status_indicator.set_status("recording")
                self.level_timer.start()
                self.status_bar.showMessage("Запись...")
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось начать запись:\n{e}")
                self.record_btn.set_recording(False)
        
        def _stop_recording(self):
            if self.asr_worker:
                self.asr_worker.stop()
                self.asr_worker = None
            
            if self.asr:
                self.asr = None
            
            self.is_recording = False
            self.status_indicator.set_status("ready")
            self.level_timer.stop()
            self.vu_meter.set_level(0)
            self.level_value.setText("0.00")
            self.status_bar.showMessage("Остановлено")
        
        def _update_level(self):
            if self.asr_worker and self.asr_worker.running:
                level = self.asr_worker.get_level()
                self.vu_meter.set_level(level)
                self.level_value.setText(f"{level:.2f}")
        
        def _on_asr_result(self, text: str):
            self.transcription.set_current_text(text, highlight=True)
        
        def _on_segment_complete(self, text: str):
            self.transcription.add_segment(text)
        
        def _on_asr_error(self, error: str):
            self.status_bar.showMessage(f"Ошибка: {error}")
            self.record_btn.set_recording(False)
            self._stop_recording()
        
        def _on_status_changed(self, status: str):
            self.status_indicator.set_status(status)
        
        def _copy_all_text(self):
            full_text = self.transcription.get_full_text()
            if full_text:
                clipboard = QApplication.clipboard()
                clipboard.setText(full_text)
                self.status_bar.showMessage("Скопировано в буфер обмена")
            else:
                self.status_bar.showMessage("Нечего копировать")
        
        def _clear_text(self):
            self.transcription.clear()
            self.status_bar.showMessage("Очищено")
        
        def _on_text_copied(self, text: str):
            self.status_bar.showMessage("Скопировано")
        
        def closeEvent(self, event: QCloseEvent):
            if self.is_recording:
                self._stop_recording()
            event.accept()
    
    
    def run_gui(model=None, config=None):
        """Запускает GUI приложение."""
        app = QApplication(sys.argv)
        app.setApplicationName("GigaAM")
        app.setStyle("Fusion")
        
        window = GigaAMWindow(model=model, config=config)
        window.show()
        
        sys.exit(app.exec())

else:
    class GigaAMWindow:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyQt6 не установлен")
    
    def run_gui(*args, **kwargs):
        print("PyQt6 не установлен. Установите: pip install PyQt6")
        sys.exit(1)
