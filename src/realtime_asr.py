"""Realtime ASR с callback-based стримингом."""

import numpy as np
import sounddevice as sd
import threading
import sys
from collections import deque
from typing import Optional, Callable, List


class RealtimeASR:
    """
    Класс для распознавания речи в реальном времени.
    
    Использует callback-based аудио поток и обработку в отдельном потоке
    для минимальной задержки.
    
    Attributes:
        model: Модель ASR (onnx_asr)
        sample_rate: Частота дискретизации (по умолчанию 16000)
        buffer_seconds: Размер буфера в секундах (по умолчанию 3)
        min_audio_seconds: Минимальная длина аудио для распознавания (по умолчанию 1.5)
        accumulate_mode: Режим накопления текста (соединение буферов)
    """
    
    def __init__(
        self,
        model,
        sample_rate: int = 16000,
        buffer_seconds: float = 3.0,
        min_audio_seconds: float = 1.5,
        vad_threshold: float = 0.01,
        accumulate_mode: bool = False,
    ):
        """
        Инициализация RealtimeASR.
        
        Args:
            model: Загруженная модель onnx_asr
            sample_rate: Частота дискретизации
            buffer_seconds: Размер кольцевого буфера в секундах
            min_audio_seconds: Минимальная длина аудио для распознавания
            vad_threshold: Порог RMS для детектора голоса (0 = отключён)
            accumulate_mode: Если True, накапливает текст между буферами
        """
        self.model = model
        self.sample_rate = sample_rate
        self.buffer_seconds = buffer_seconds
        self.min_samples = int(sample_rate * min_audio_seconds)
        self.vad_threshold = vad_threshold
        self.accumulate_mode = accumulate_mode
        
        # Кольцевой буфер для аудио данных
        self.buffer = deque(maxlen=int(sample_rate * buffer_seconds))
        # Буфер накопления аудио (для режима accumulate)
        self.accumulated_audio: List[np.ndarray] = []
        self.lock = threading.Lock()
        
        # Состояние
        self.running = False
        self.paused = False
        self.recording = True  # Для push-to-talk
        self.last_text = ""
        self.stream: Optional[sd.InputStream] = None
        self.process_thread: Optional[threading.Thread] = None
        
        # Накопленный текст (для режима accumulate)
        self.accumulated_text: List[str] = []
        
        # Callback для результатов
        self.on_result: Optional[Callable[[str], None]] = None
        self.on_segment_complete: Optional[Callable[[str], None]] = None
        
        # Статистика
        self.audio_level = 0.0
        self.is_speech = False
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback вызывается sounddevice при получении аудио."""
        if status:
            print(f"\n⚠️ Audio: {status}", file=sys.stderr)
        
        audio_chunk = indata[:, 0].copy()
        
        # Вычисляем уровень звука (RMS)
        self.audio_level = np.sqrt(np.mean(audio_chunk ** 2))
        
        # VAD: определяем наличие речи
        if self.vad_threshold > 0:
            self.is_speech = self.audio_level > self.vad_threshold
        else:
            self.is_speech = True
        
        # Добавляем в буфер только если запись активна
        if self.recording:
            with self.lock:
                self.buffer.extend(audio_chunk)
                # В режиме накопления сохраняем все чанки
                if self.accumulate_mode:
                    self.accumulated_audio.append(audio_chunk)
    
    def _process_loop(self):
        """Цикл обработки аудио в отдельном потоке."""
        while self.running:
            if self.paused or not self.recording:
                threading.Event().wait(0.1)
                continue
            
            audio = None
            with self.lock:
                if len(self.buffer) >= self.min_samples:
                    audio = np.array(list(self.buffer), dtype=np.float32)
            
            if audio is not None:
                # Если VAD включён и нет речи — пропускаем
                if self.vad_threshold > 0 and not self.is_speech:
                    threading.Event().wait(0.1)
                    continue
                
                try:
                    text = self.model.recognize(audio, sample_rate=self.sample_rate)
                    if text and text != self.last_text:
                        self.last_text = text
                        
                        if self.on_result:
                            self.on_result(text)
                        else:
                            # Вывод по умолчанию
                            self._default_output(text)
                except Exception as e:
                    print(f"\n⚠️ ASR Error: {e}", file=sys.stderr)
            
            # Небольшая пауза между итерациями
            threading.Event().wait(0.1)
    
    def _default_output(self, text: str):
        """Вывод результата по умолчанию."""
        # Индикатор уровня звука
        level_bars = int(self.audio_level * 50)
        level_indicator = "█" * min(level_bars, 10)
        
        print(f"\r🎤 [{level_indicator:<10}] {text}    ", end="", flush=True)
    
    def start(self, device: Optional[int] = None):
        """
        Запускает распознавание.
        
        Args:
            device: ID аудиоустройства (None = по умолчанию)
        """
        if self.running:
            print("⚠️ ASR уже запущен")
            return
        
        self.running = True
        self.paused = False
        self.recording = True
        
        # Создаём аудио поток
        self.stream = sd.InputStream(
            device=device,
            channels=1,
            samplerate=self.sample_rate,
            dtype='float32',
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.1),  # 100ms блоки
        )
        self.stream.start()
        
        # Запускаем обработку в отдельном потоке
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.process_thread.start()
    
    def stop(self):
        """Останавливает распознавание."""
        self.running = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        if self.process_thread:
            self.process_thread.join(timeout=1.0)
            self.process_thread = None
        
        # Очищаем буфер
        with self.lock:
            self.buffer.clear()
        
        self.last_text = ""
    
    def pause(self):
        """Ставит распознавание на паузу."""
        self.paused = True
    
    def resume(self):
        """Возобновляет распознавание."""
        self.paused = False
    
    # ========== Push-to-Talk методы ==========
    
    def start_recording(self):
        """
        Начинает запись (для push-to-talk).
        Очищает буфер и начинает накопление аудио.
        """
        with self.lock:
            self.buffer.clear()
            self.accumulated_audio.clear()
        self.last_text = ""
        self.recording = True
    
    def stop_recording(self) -> str:
        """
        Останавливает запись (для push-to-talk).
        Финализирует распознавание и возвращает результат.
        
        Returns:
            Финальный распознанный текст
        """
        self.recording = False
        
        # Получаем финальный текст
        final_text = ""
        
        with self.lock:
            if self.accumulate_mode and self.accumulated_audio:
                # Объединяем все накопленные чанки
                full_audio = np.concatenate(self.accumulated_audio)
                try:
                    final_text = self.model.recognize(full_audio, sample_rate=self.sample_rate)
                except Exception as e:
                    print(f"\n⚠️ ASR Error: {e}", file=sys.stderr)
                self.accumulated_audio.clear()
            elif len(self.buffer) > 0:
                # Используем текущий буфер
                audio = np.array(list(self.buffer), dtype=np.float32)
                try:
                    final_text = self.model.recognize(audio, sample_rate=self.sample_rate)
                except Exception as e:
                    print(f"\n⚠️ ASR Error: {e}", file=sys.stderr)
        
        # Добавляем в накопленный текст
        if final_text:
            self.accumulated_text.append(final_text)
            if self.on_segment_complete:
                self.on_segment_complete(final_text)
        
        return final_text
    
    def is_recording(self) -> bool:
        """Возвращает True, если запись активна."""
        return self.recording
    
    # ========== Методы накопления текста ==========
    
    def get_accumulated_text(self) -> str:
        """Возвращает весь накопленный текст."""
        return " ".join(self.accumulated_text)
    
    def get_accumulated_segments(self) -> List[str]:
        """Возвращает список всех сегментов."""
        return self.accumulated_text.copy()
    
    def clear_accumulated_text(self):
        """Очищает накопленный текст."""
        self.accumulated_text.clear()
    
    def clear_buffer(self):
        """Очищает аудио буфер."""
        with self.lock:
            self.buffer.clear()
            self.accumulated_audio.clear()
        self.last_text = ""
    
    def get_audio_level(self) -> float:
        """Возвращает текущий уровень звука (0.0 - 1.0)."""
        return min(self.audio_level, 1.0)
    
    def is_active(self) -> bool:
        """Возвращает True, если ASR запущен и не на паузе."""
        return self.running and not self.paused
