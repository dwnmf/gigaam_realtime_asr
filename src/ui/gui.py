"""
GigaAM PyQt6 GUI Application

Графический интерфейс для распознавания речи в реальном времени.

Функции:
- Выбор аудиоустройства
- Визуализация уровня звука
- Отображение транскрипции в реальном времени
- Копирование текста в буфер обмена
- Режимы: непрерывный и push-to-talk
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
        DeviceComboBox, RecordButton
    )


# Сигналы для межпоточной коммуникации
class ASRSignals(QObject):
    """Сигналы для связи ASR потока с GUI."""
    result_ready = pyqtSignal(str)           # Новый распознанный текст
    level_updated = pyqtSignal(float)        # Уровень звука
    error_occurred = pyqtSignal(str)         # Ошибка
    segment_complete = pyqtSignal(str)       # Завершённый сегмент (для PTT)
    status_changed = pyqtSignal(str)         # Изменение статуса


class ASRWorker(QObject):
    """
    Воркер для запуска ASR в отдельном потоке.
    """
    
    def __init__(self, asr, device_id: Optional[int] = None):
        super().__init__()
        self.asr = asr
        self.device_id = device_id
        self.signals = ASRSignals()
        self.running = False
        self._level_timer: Optional[QTimer] = None
    
    def run(self):
        """Запускает ASR."""
        try:
            # Подключаем callback для результатов
            self.asr.on_result = self._on_result
            self.asr.on_segment_complete = self._on_segment
            
            self.asr.start(device=self.device_id)
            self.running = True
            self.signals.status_changed.emit("recording")
            
        except Exception as e:
            self.signals.error_occurred.emit(str(e))
            self.signals.status_changed.emit("error")
    
    def stop(self):
        """Останавливает ASR."""
        self.running = False
        if self.asr:
            self.asr.stop()
        self.signals.status_changed.emit("ready")
    
    def _on_result(self, text: str):
        """Callback при получении результата."""
        self.signals.result_ready.emit(text)
    
    def _on_segment(self, text: str):
        """Callback при завершении сегмента."""
        self.signals.segment_complete.emit(text)
    
    def get_level(self) -> float:
        """Возвращает текущий уровень звука."""
        if self.asr:
            return self.asr.get_audio_level()
        return 0.0


if PYQT6_AVAILABLE:
    
    class GigaAMWindow(QMainWindow):
        """
        Главное окно приложения GigaAM.
        """
        
        def __init__(self, model=None, config=None):
            super().__init__()
            
            self.model = model
            self.config = config
            self.asr = None
            self.asr_worker: Optional[ASRWorker] = None
            self.asr_thread: Optional[QThread] = None
            
            # Состояние
            self.is_recording = False
            self.is_ptt_mode = False
            self.device_id: Optional[int] = None
            
            # Инициализация UI
            self._setup_window()
            self._setup_ui()
            self._setup_timers()
            self._setup_tray()
            self._load_devices()
            
            # Применяем тему
            self._apply_dark_theme()
        
        def _setup_window(self):
            """Настройка окна."""
            self.setWindowTitle("🎤 GigaAM Realtime ASR")
            self.setMinimumSize(500, 600)
            self.resize(600, 700)
            
            # Иконка окна (если есть)
            # self.setWindowIcon(QIcon("path/to/icon.png"))
        
        def _setup_ui(self):
            """Создание UI элементов."""
            # Центральный виджет
            central = QWidget()
            self.setCentralWidget(central)
            
            main_layout = QVBoxLayout(central)
            main_layout.setContentsMargins(16, 16, 16, 16)
            main_layout.setSpacing(16)
            
            # === Устройство ===
            device_group = QGroupBox("🎧 Аудиоустройство")
            device_group.setStyleSheet("""
                QGroupBox {
                    font-size: 14px;
                    font-weight: bold;
                    color: #00d9ff;
                    border: 1px solid #3d3d3d;
                    border-radius: 8px;
                    margin-top: 12px;
                    padding-top: 8px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 8px;
                }
            """)
            device_layout = QVBoxLayout(device_group)
            
            self.device_combo = DeviceComboBox()
            self.device_combo.deviceChanged.connect(self._on_device_changed)
            device_layout.addWidget(self.device_combo)
            
            # Кнопка обновления
            refresh_btn = QPushButton("🔄 Обновить")
            refresh_btn.setMaximumWidth(120)
            refresh_btn.clicked.connect(self._load_devices)
            refresh_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3d3d3d;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #4d4d4d;
                }
            """)
            device_layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)
            
            main_layout.addWidget(device_group)
            
            # === Транскрипция ===
            transcription_group = QGroupBox("📝 Транскрипция")
            transcription_group.setStyleSheet("""
                QGroupBox {
                    font-size: 14px;
                    font-weight: bold;
                    color: #00d9ff;
                    border: 1px solid #3d3d3d;
                    border-radius: 8px;
                    margin-top: 12px;
                    padding-top: 8px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 8px;
                }
            """)
            transcription_layout = QVBoxLayout(transcription_group)
            
            self.transcription = TranscriptionWidget(show_timestamps=True)
            self.transcription.textCopied.connect(self._on_text_copied)
            transcription_layout.addWidget(self.transcription)
            
            main_layout.addWidget(transcription_group, stretch=1)
            
            # === Панель статуса и управления ===
            control_frame = QFrame()
            control_frame.setStyleSheet("""
                QFrame {
                    background-color: #252525;
                    border: 1px solid #3d3d3d;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)
            control_layout = QVBoxLayout(control_frame)
            control_layout.setSpacing(12)
            
            # Уровень звука
            level_layout = QHBoxLayout()
            
            self.status_indicator = StatusIndicator()
            self.status_indicator.set_status("idle")
            level_layout.addWidget(self.status_indicator)
            
            level_label = QLabel("Уровень:")
            level_label.setStyleSheet("color: #888888; font-size: 13px;")
            level_layout.addWidget(level_label)
            
            self.vu_meter = VUMeter()
            level_layout.addWidget(self.vu_meter, stretch=1)
            
            self.level_value = QLabel("0.00")
            self.level_value.setStyleSheet("color: #00d9ff; font-size: 13px; min-width: 40px;")
            level_layout.addWidget(self.level_value)
            
            control_layout.addLayout(level_layout)
            
            # Кнопки управления
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(12)
            
            self.record_btn = RecordButton()
            self.record_btn.recordingStarted.connect(self._start_recording)
            self.record_btn.recordingStopped.connect(self._stop_recording)
            btn_layout.addWidget(self.record_btn)
            
            # Кнопка копирования
            copy_btn = QPushButton("📋 Копировать всё")
            copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3d3d3d;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #4d4d4d;
                }
            """)
            copy_btn.clicked.connect(self._copy_all_text)
            btn_layout.addWidget(copy_btn)
            
            # Настройки
            settings_btn = QPushButton("⚙")
            settings_btn.setFixedSize(48, 48)
            settings_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3d3d3d;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 20px;
                }
                QPushButton:hover {
                    background-color: #4d4d4d;
                }
            """)
            settings_btn.clicked.connect(self._show_settings)
            btn_layout.addWidget(settings_btn)
            
            control_layout.addLayout(btn_layout)
            
            main_layout.addWidget(control_frame)
            
            # === Статус бар ===
            self.status_bar = QStatusBar()
            self.status_bar.setStyleSheet("""
                QStatusBar {
                    background-color: #1e1e1e;
                    color: #888888;
                    font-size: 12px;
                }
            """)
            self.setStatusBar(self.status_bar)
            self.status_bar.showMessage("Готово. Выберите устройство и нажмите 'Записывать'")
        
        def _setup_timers(self):
            """Настройка таймеров."""
            # Таймер обновления уровня звука
            self.level_timer = QTimer(self)
            self.level_timer.timeout.connect(self._update_level)
            self.level_timer.setInterval(50)  # 20 fps
        
        def _setup_tray(self):
            """Настройка системного трея (если поддерживается)."""
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            
            self.tray_icon = QSystemTrayIcon(self)
            # self.tray_icon.setIcon(QIcon("path/to/icon.png"))
            
            # Меню трея
            tray_menu = QMenu()
            
            show_action = QAction("Показать", self)
            show_action.triggered.connect(self.show)
            tray_menu.addAction(show_action)
            
            tray_menu.addSeparator()
            
            record_action = QAction("Начать/Остановить", self)
            record_action.triggered.connect(self._toggle_recording)
            tray_menu.addAction(record_action)
            
            tray_menu.addSeparator()
            
            quit_action = QAction("Выход", self)
            quit_action.triggered.connect(QApplication.quit)
            tray_menu.addAction(quit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self._on_tray_activated)
            # self.tray_icon.show()
        
        def _apply_dark_theme(self):
            """Применяет тёмную тему."""
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1e1e1e;
                }
                
                QWidget {
                    color: #ffffff;
                    font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
                }
                
                QGroupBox {
                    background-color: #252525;
                }
                
                QLabel {
                    color: #cccccc;
                }
                
                QMessageBox {
                    background-color: #2d2d2d;
                }
                
                QMessageBox QLabel {
                    color: white;
                }
                
                QMessageBox QPushButton {
                    background-color: #3d3d3d;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    min-width: 80px;
                }
                
                QMessageBox QPushButton:hover {
                    background-color: #4d4d4d;
                }
            """)
        
        def _load_devices(self):
            """Загружает список аудиоустройств."""
            try:
                from ..audio_devices import list_audio_devices
                
                devices_tuple = list_audio_devices(show_output=False)
                input_devices, output_devices = devices_tuple
                
                self.device_combo.set_devices(input_devices)
                
                if input_devices:
                    self.status_bar.showMessage(f"Найдено {len(input_devices)} устройств")
                else:
                    self.status_bar.showMessage("Аудиоустройства не найдены!")
                    
            except Exception as e:
                self.status_bar.showMessage(f"Ошибка загрузки устройств: {e}")
        
        def _on_device_changed(self, device_id: int, device_name: str):
            """Обработка смены устройства."""
            self.device_id = device_id
            self.status_bar.showMessage(f"Выбрано: {device_name}")
            
            # Если запись активна, перезапускаем с новым устройством
            if self.is_recording:
                self._stop_recording()
                self._start_recording()
        
        def _toggle_recording(self):
            """Переключает состояние записи."""
            if self.is_recording:
                self._stop_recording()
            else:
                self._start_recording()
        
        def _start_recording(self):
            """Начинает запись."""
            if not self.model:
                QMessageBox.warning(
                    self, "Ошибка",
                    "Модель ASR не загружена!\n\n"
                    "Используйте GUI launcher или загрузите модель вручную."
                )
                self.record_btn.set_recording(False)
                return
            
            self.device_id = self.device_combo.get_selected_device_id()
            
            try:
                # Создаём ASR
                from ..realtime_asr import RealtimeASR
                
                self.asr = RealtimeASR(
                    model=self.model,
                    buffer_seconds=3.0,
                    vad_threshold=0.01,
                    accumulate_mode=True
                )
                
                # Создаём воркер
                self.asr_worker = ASRWorker(self.asr, self.device_id)
                
                # Подключаем сигналы
                self.asr_worker.signals.result_ready.connect(self._on_asr_result)
                self.asr_worker.signals.error_occurred.connect(self._on_asr_error)
                self.asr_worker.signals.segment_complete.connect(self._on_segment_complete)
                self.asr_worker.signals.status_changed.connect(self._on_status_changed)
                
                # Запускаем
                self.asr_worker.run()
                
                self.is_recording = True
                self.status_indicator.set_status("recording")
                self.level_timer.start()
                self.status_bar.showMessage("🔴 Запись...")
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось начать запись:\n{e}")
                self.record_btn.set_recording(False)
        
        def _stop_recording(self):
            """Останавливает запись."""
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
            self.status_bar.showMessage("Запись остановлена")
        
        def _update_level(self):
            """Обновляет индикатор уровня звука."""
            if self.asr_worker and self.asr_worker.running:
                level = self.asr_worker.get_level()
                self.vu_meter.set_level(level)
                self.level_value.setText(f"{level:.2f}")
        
        def _on_asr_result(self, text: str):
            """Обработка результата ASR."""
            self.transcription.set_current_text(text, highlight=True)
        
        def _on_segment_complete(self, text: str):
            """Обработка завершённого сегмента."""
            self.transcription.add_segment(text)
        
        def _on_asr_error(self, error: str):
            """Обработка ошибки ASR."""
            self.status_bar.showMessage(f"Ошибка: {error}")
            self.record_btn.set_recording(False)
            self._stop_recording()
        
        def _on_status_changed(self, status: str):
            """Обработка изменения статуса."""
            self.status_indicator.set_status(status)
        
        def _copy_all_text(self):
            """Копирует весь текст в буфер обмена."""
            full_text = self.transcription.get_full_text()
            if full_text:
                clipboard = QApplication.clipboard()
                clipboard.setText(full_text)
                self.status_bar.showMessage("📋 Текст скопирован в буфер обмена")
            else:
                self.status_bar.showMessage("Нечего копировать")
        
        def _on_text_copied(self, text: str):
            """Callback при копировании текста."""
            self.status_bar.showMessage("📋 Текст скопирован в буфер обмена")
        
        def _show_settings(self):
            """Показывает диалог настроек."""
            QMessageBox.information(
                self, "Настройки",
                "Настройки будут добавлены в следующей версии.\n\n"
                "Текущие параметры:\n"
                f"• Буфер: 3.0 сек\n"
                f"• VAD порог: 0.01\n"
                f"• Модель: gigaam-v3-e2e-rnnt"
            )
        
        def _on_tray_activated(self, reason):
            """Обработка клика по иконке в трее."""
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                if self.isVisible():
                    self.hide()
                else:
                    self.show()
                    self.activateWindow()
        
        def closeEvent(self, event: QCloseEvent):
            """Обработка закрытия окна."""
            # Останавливаем запись
            if self.is_recording:
                self._stop_recording()
            
            event.accept()
    
    
    def run_gui(model=None, config=None):
        """
        Запускает GUI приложение.
        
        Args:
            model: Загруженная модель onnx_asr
            config: Объект конфигурации GigaAMConfig
        """
        app = QApplication(sys.argv)
        app.setApplicationName("GigaAM")
        app.setApplicationDisplayName("GigaAM Realtime ASR")
        
        # Установка палитры
        app.setStyle("Fusion")
        
        window = GigaAMWindow(model=model, config=config)
        window.show()
        
        sys.exit(app.exec())

else:
    # Заглушка если PyQt6 не установлен
    class GigaAMWindow:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "PyQt6 не установлен. Установите: pip install PyQt6"
            )
    
    def run_gui(*args, **kwargs):
        print("❌ PyQt6 не установлен!")
        print("   Установите: pip install PyQt6")
        sys.exit(1)
