"""
Rich Console UI для GigaAM

Красивый консольный интерфейс с использованием библиотеки Rich.
Поддерживает:
- Цветной вывод с градиентами
- Динамическое обновление (Live Display)
- Интерактивный выбор устройств
- Панели и таблицы
"""

from datetime import datetime
from typing import Optional, List, Callable, Tuple
import threading
import sys
import io
import time

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import Progress, BarColumn, TextColumn
    from rich.layout import Layout
    from rich.style import Style
    from rich.prompt import Prompt, IntPrompt
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# Цветовая схема
class Colors:
    """Цветовая палитра приложения."""
    PRIMARY = "#00D9FF"      # Голубой
    SECONDARY = "#FF6B6B"    # Красный
    SUCCESS = "#4ECDC4"      # Бирюзовый
    WARNING = "#FFE66D"      # Жёлтый
    ERROR = "#FF6B6B"        # Красный
    TEXT = "#FFFFFF"         # Белый
    MUTED = "#6C757D"        # Серый
    
    # Градиенты уровня звука
    LEVEL_LOW = "#00FF00"    # Зелёный (тихо)
    LEVEL_MID = "#FFFF00"    # Жёлтый (норма)
    LEVEL_HIGH = "#FF0000"   # Красный (громко)


class DeviceSelector:
    """Интерактивный выбор аудиоустройства."""
    
    def __init__(self):
        if not RICH_AVAILABLE:
            raise ImportError("Rich library is required. Install: pip install rich")
        self.console = Console()
    
    def select_device(self, devices_tuple, title: str = "Выберите устройство") -> Optional[int]:
        """
        Показывает интерактивное меню выбора устройства.
        
        Args:
            devices_tuple: Кортеж (input_devices, output_devices) от list_audio_devices()
                          где каждый элемент это (idx, name, channels)
            title: Заголовок меню
            
        Returns:
            ID выбранного устройства или None
        """
        # Распаковываем кортеж
        if isinstance(devices_tuple, tuple) and len(devices_tuple) == 2:
            input_devices, output_devices = devices_tuple
        else:
            input_devices = devices_tuple
            output_devices = []
        
        if not input_devices and not output_devices:
            self.console.print("[red]❌ Устройства не найдены![/red]")
            return None
        
        # Создаём таблицу
        table = Table(
            title=f"🎤 {title}",
            box=box.ROUNDED,
            header_style="bold cyan",
            border_style="bright_blue",
            show_lines=True
        )
        
        table.add_column("#", style="dim", width=4, justify="center")
        table.add_column("Устройство", style="white", min_width=40)
        table.add_column("Каналы", justify="center", width=8)
        table.add_column("Тип", justify="center", width=12)
        
        # Определяем loopback ключевые слова
        loopback_keywords = ['loopback', 'stereo mix', 'what u hear', 'wave out', 'wasapi']
        
        device_ids = []
        
        # Добавляем входные устройства
        for idx, name, channels in input_devices:
            # Проверяем, является ли устройство loopback
            name_lower = name.lower()
            is_loopback = any(kw in name_lower for kw in loopback_keywords)
            
            if is_loopback:
                dev_type = "[yellow]🔄 Loopback[/yellow]"
            else:
                dev_type = "[green]🎤 Вход[/green]"
            
            table.add_row(
                str(idx),
                name,
                str(channels),
                dev_type
            )
            device_ids.append(idx)
        
        self.console.print()
        self.console.print(table)
        self.console.print()
        
        # Запрашиваем выбор
        try:
            choice = IntPrompt.ask(
                "[cyan]Введите номер устройства[/cyan]",
                choices=[str(i) for i in device_ids],
                show_choices=False
            )
            return choice
        except KeyboardInterrupt:
            return None


class RichConsoleUI:
    """
    Основной класс Rich UI для ASR.
    
    Использует Live Display для динамического обновления без мерцания.
    """
    
    def __init__(self, show_timestamps: bool = True, show_level: bool = True):
        if not RICH_AVAILABLE:
            raise ImportError("Rich library is required. Install: pip install rich")
        
        # Консоль с отключением очистки для уменьшения мерцания
        stdout = sys.stdout
        if hasattr(stdout, "buffer"):
            stdout = io.TextIOWrapper(stdout.buffer, encoding="utf-8", errors="replace", write_through=True)
        self._console_file = stdout  # сохраняем, чтобы его не сборщило
        self.console = Console(
            highlight=False,
            force_terminal=True,
            legacy_windows=False,  # форсируем UTF-8 и modern console API
            file=self._console_file,
        )
        self.show_timestamps = show_timestamps
        self.show_level = show_level
        
        # Состояние
        self.is_recording = False
        self.is_paused = False
        self.audio_level = 0.0
        self._smoothed_level = 0.0  # Сглаженный уровень для анимации
        self._level_smoothing = 0.3  # Коэффициент сглаживания (0-1, меньше = плавнее)
        self.current_text = ""
        self.accumulated_text = ""
        self.segments: List[Tuple[str, str]] = []  # (timestamp, text)
        self.device_name = "Не выбрано"
        self.mode = "continuous"  # continuous | push_to_talk
        
        # Live display
        self._live: Optional[Live] = None
        self._stop_event = threading.Event()
        self._update_thread: Optional[threading.Thread] = None
        self._last_render = 0.0
        self._min_render_interval = 0.08  # ~12 FPS, чтобы сгладить обновления
        
        # Codex panel fields
        self.codex_text = ""
        self.codex_status = "Ожидание..."
        self.codex_visible = True
        
        # Codex scrolling - динамическое определение размера
        self.codex_scroll_offset = 0
        self._codex_lines_cache = []
        
        # Fast Codex panel fields (low reasoning)
        self.codex_fast_text = ""
        self.codex_fast_status = "Ожидание..."
        self.codex_fast_enabled = True
        self.codex_fast_scroll_offset = 0
        self._codex_fast_lines_cache = []
        
        # Динамический размер окна
        self._panel_size_offset = 0  # Смещение размера (можно менять +/-)
    
    def print_banner(self):
        """Выводит приветственный баннер."""
        banner = Text()
        banner.append("╔═══════════════════════════════════════════╗\n", style="bright_blue")
        banner.append("║   ", style="bright_blue")
        banner.append("🎤 GigaAM Realtime ASR", style="bold cyan")
        banner.append("              ║\n", style="bright_blue")
        banner.append("║   ", style="bright_blue")
        banner.append("Распознавание речи в реальном времени", style="dim")
        banner.append("  ║\n", style="bright_blue")
        banner.append("╚═══════════════════════════════════════════╝", style="bright_blue")
        
        self.console.print()
        self.console.print(banner)
        self.console.print()
    
    def print_status(self, model: str, device: str, buffer: float, vad_threshold: float, mode: str):
        """Выводит текущие настройки."""
        self.device_name = device
        self.mode = mode
        
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Key", style="dim")
        table.add_column("Value", style="cyan")
        
        table.add_row("🧠 Модель", model)
        table.add_row("🎧 Устройство", device)
        table.add_row("⏱️  Буфер", f"{buffer} сек")
        
        if vad_threshold > 0:
            table.add_row("🔇 VAD порог", str(vad_threshold))
        
        mode_text = "🎯 Push-to-Talk" if mode == "push_to_talk" else "🔄 Непрерывный"
        table.add_row("📍 Режим", mode_text)
        
        panel = Panel(
            table,
            title="[bold]⚙️ Настройки[/bold]",
            border_style="bright_blue",
            box=box.ROUNDED
        )
        self.console.print(panel)
    
    def _get_level_bar(self, level: float, width: int = 20) -> Text:
        """Создаёт цветную полосу уровня звука."""
        filled = int(level * width)
        empty = width - filled
        
        bar = Text()
        
        # Градиентная полоса
        for i in range(filled):
            ratio = i / width
            if ratio < 0.5:
                bar.append("█", style=Colors.LEVEL_LOW)
            elif ratio < 0.8:
                bar.append("█", style=Colors.LEVEL_MID)
            else:
                bar.append("█", style=Colors.LEVEL_HIGH)
        
        bar.append("░" * empty, style="dim")
        
        return bar
    
    def update_codex(self, text: str, status: str = None, append: bool = False):
        """Обновляет панель Codex (full)."""
        if status:
            self.codex_status = status
        
        if append:
            self.codex_text += text
        else:
            self.codex_text = text
            self.codex_scroll_offset = 0  # Сброс прокрутки при новом тексте
        
        # Обновляем кэш строк
        self._codex_lines_cache = self.codex_text.split('\n') if self.codex_text else []
        
        # Автопрокрутка вниз при добавлении текста
        if append and len(self._codex_lines_cache) > self.codex_visible_lines:
            self.codex_scroll_offset = max(0, len(self._codex_lines_cache) - self.codex_visible_lines)
            
        # Форсируем обновление, если Live запущен
        self._request_render()
    
    def update_codex_fast(self, text: str, status: str = None, append: bool = False):
        """Обновляет панель быстрого Codex (low reasoning)."""
        if status:
            self.codex_fast_status = status
        
        if append:
            self.codex_fast_text += text
        else:
            self.codex_fast_text = text
            self.codex_fast_scroll_offset = 0
        
        # Обновляем кэш строк
        self._codex_fast_lines_cache = self.codex_fast_text.split('\n') if self.codex_fast_text else []
        
        # Автопрокрутка вниз при добавлении текста
        if append and len(self._codex_fast_lines_cache) > self.codex_fast_visible_lines:
            self.codex_fast_scroll_offset = max(0, len(self._codex_fast_lines_cache) - self.codex_fast_visible_lines)
            
        self._request_render()
    
    @property
    def codex_visible_lines(self) -> int:
        """Динамическое количество видимых строк для Full Codex на основе высоты терминала."""
        terminal_height = self.console.height or 30
        # Базовое количество строк: ~40% высоты терминала для Full Codex
        base_lines = max(5, int(terminal_height * 0.4))
        return max(3, base_lines + self._panel_size_offset)
    
    @property
    def codex_fast_visible_lines(self) -> int:
        """Динамическое количество видимых строк для Fast Codex."""
        terminal_height = self.console.height or 30
        # Базовое количество строк: ~25% высоты терминала для Fast Codex
        base_lines = max(4, int(terminal_height * 0.25))
        return max(2, base_lines + self._panel_size_offset)
    
    def increase_panel_size(self, amount: int = 2):
        """Увеличить размер панелей Codex."""
        self._panel_size_offset += amount
        self._request_render()
    
    def decrease_panel_size(self, amount: int = 2):
        """Уменьшить размер панелей Codex."""
        self._panel_size_offset = max(-10, self._panel_size_offset - amount)
        self._request_render()
    
    def reset_panel_size(self):
        """Сбросить размер панелей к значению по умолчанию."""
        self._panel_size_offset = 0
        self._request_render()
    
    def scroll_codex_up(self, lines: int = 3):
        """Прокрутка ответа Codex вверх."""
        if self.codex_scroll_offset > 0:
            self.codex_scroll_offset = max(0, self.codex_scroll_offset - lines)
            self._request_render()
    
    def scroll_codex_down(self, lines: int = 3):
        """Прокрутка ответа Codex вниз."""
        max_offset = max(0, len(self._codex_lines_cache) - self.codex_visible_lines)
        if self.codex_scroll_offset < max_offset:
            self.codex_scroll_offset = min(max_offset, self.codex_scroll_offset + lines)
            self._request_render()
    
    def scroll_codex_to_top(self):
        """Прокрутка в начало."""
        if self.codex_scroll_offset != 0:
            self.codex_scroll_offset = 0
            self._request_render()
    
    def scroll_codex_to_bottom(self):
        """Прокрутка в конец."""
        max_offset = max(0, len(self._codex_lines_cache) - self.codex_visible_lines)
        if self.codex_scroll_offset != max_offset:
            self.codex_scroll_offset = max_offset
            self._request_render()

    def _request_render(self):
        if not self._live:
            return
        now = time.monotonic()
        if now - self._last_render < self._min_render_interval:
            return
        self._last_render = now
        self._live.update(self._generate_display())
    
    def _generate_display(self) -> Layout:
        """Генерирует Layout с двумя панелями (ASR слева, Codex справа)."""
        # --- 1. ЛЕВАЯ ПАНЕЛЬ (ASR) ---
        # Статус записи
        if self.is_recording:
            status_text = Text("🔴 ЗАПИСЬ", style="bold red")
        elif self.is_paused:
            status_text = Text("⏸️  ПАУЗА", style="bold yellow")
        else:
            status_text = Text("⚪ ГОТОВ", style="bold green")
        
        # Уровень звука
        level_bar = self._get_level_bar(self.audio_level)
        level_info = Text(f" {self.audio_level:.2f}", style="dim")
        
        # Сборка контента ASR
        asr_content = Text()
        asr_content.append("  ")
        asr_content.append_text(status_text)
        asr_content.append("  │  ")
        asr_content.append_text(level_bar)
        asr_content.append_text(level_info)
        asr_content.append("\n\n")
        
        # Накопленный текст
        if self.accumulated_text:
            asr_content.append(self.accumulated_text, style="dim")
            asr_content.append("\n")
        
        # Текущий текст
        current_disp = self.current_text if self.current_text else "[dim]Говорите...[/dim]"
        if self.is_recording:
            asr_content.append(current_disp, style="bold white")
        else:
            asr_content.append(current_disp)
        
        # Подсказки
        if self.mode == "push_to_talk":
            hint = "[dim]Удерживайте [SPACE] для записи • [ESC] выход[/dim]"
        else:
            hint = "[dim]Ctrl+C для выхода[/dim]"

        left_panel = Panel(
            asr_content,
            title=f"[bold cyan]🎤 {self.device_name}[/bold cyan]",
            subtitle=hint,
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 1)
        )

        # --- 2. ПРАВАЯ ПАНЕЛЬ (CODEX full) со скроллингом ---
        if self.codex_text:
            lines = self._codex_lines_cache
            total_lines = len(lines)
            
            # Получаем видимые строки с учётом смещения
            visible_lines = lines[self.codex_scroll_offset:self.codex_scroll_offset + self.codex_visible_lines]
            codex_display = '\n'.join(visible_lines)
            
            # Индикатор прокрутки
            if total_lines > self.codex_visible_lines:
                can_scroll_up = self.codex_scroll_offset > 0
                can_scroll_down = self.codex_scroll_offset < total_lines - self.codex_visible_lines
                
                scroll_indicator = Text()
                if can_scroll_up:
                    scroll_indicator.append("▲ ", style="dim cyan")
                else:
                    scroll_indicator.append("  ")
                scroll_indicator.append(f"[{self.codex_scroll_offset + 1}-{min(self.codex_scroll_offset + self.codex_visible_lines, total_lines)}/{total_lines}]", style="dim")
                if can_scroll_down:
                    scroll_indicator.append(" ▼", style="dim cyan")
                
                codex_content = Text()
                codex_content.append(codex_display)
                codex_content.append("\n\n")
                codex_content.append_text(scroll_indicator)
            else:
                codex_content = codex_display
        else:
            codex_content = "[dim]Ожидание запроса...[/dim]"
        
        scroll_hint = "[dim]↑/↓ прокрутка[/dim]" if len(self._codex_lines_cache) > self.codex_visible_lines else ""
        
        codex_full_panel = Panel(
            codex_content,
            title=f"[bold magenta]🤖 Codex: {self.codex_status}[/bold magenta]",
            subtitle=scroll_hint,
            border_style="magenta",
            box=box.ROUNDED,
            padding=(0, 1)
        )
        
        # --- 3. ПАНЕЛЬ БЫСТРОГО CODEX (low reasoning) ---
        if self.codex_fast_enabled:
            if self.codex_fast_text:
                fast_lines = self._codex_fast_lines_cache
                fast_total = len(fast_lines)
                fast_visible = fast_lines[self.codex_fast_scroll_offset:self.codex_fast_scroll_offset + self.codex_fast_visible_lines]
                fast_display = '\n'.join(fast_visible)
                
                if fast_total > self.codex_fast_visible_lines:
                    fast_indicator = Text()
                    fast_indicator.append(fast_display)
                    fast_indicator.append(f"\n[dim][{self.codex_fast_scroll_offset + 1}-{min(self.codex_fast_scroll_offset + self.codex_fast_visible_lines, fast_total)}/{fast_total}][/dim]")
                    fast_content = fast_indicator
                else:
                    fast_content = fast_display
            else:
                fast_content = "[dim]Ожидание...[/dim]"
            
            codex_fast_panel = Panel(
                fast_content,
                title=f"[bold yellow]⚡ Fast: {self.codex_fast_status}[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED,
                padding=(0, 1)
            )

        # --- 4. СБОРКА LAYOUT ---
        layout = Layout()
        
        if self.codex_fast_enabled:
            # Трёхпанельный layout: ASR слева, Fast сверху-справа, Full снизу-справа
            right_layout = Layout()
            right_layout.split_column(
                Layout(codex_fast_panel, name="fast", ratio=2),
                Layout(codex_full_panel, name="full", ratio=3)
            )
            layout.split_row(
                Layout(left_panel, name="left", ratio=1),
                Layout(right_layout, name="right", ratio=1)
            )
        else:
            # Двухпанельный layout: ASR слева, Full Codex справа
            layout.split_row(
                Layout(left_panel, name="left", ratio=1),
                Layout(codex_full_panel, name="right", ratio=1)
            )
        
        return layout
    
    def start_live_display(self):
        """Запускает Live Display."""
        self._stop_event.clear()
        self._last_render = 0.0
        self._live = Live(
            self._generate_display(),
            console=self.console,
            refresh_per_second=10,
            auto_refresh=True,
            transient=True,  # Не оставляет след после остановки
            vertical_overflow="visible",  # Предотвращает обрезку
        )
        self._live.start()
    
    def stop_live_display(self):
        """Останавливает Live Display."""
        self._stop_event.set()
        if self._live:
            self._live.stop()
            self._live = None
    
    def update(
        self,
        text: Optional[str] = None,
        level: Optional[float] = None,
        recording: Optional[bool] = None,
        paused: Optional[bool] = None,
        accumulated: Optional[str] = None
    ):
        """Обновляет отображение с минимальным мерцанием."""
        changed = False
        
        if text is not None and text != self.current_text:
            self.current_text = text
            changed = True
        
        if level is not None:
            # Экспоненциальное сглаживание для плавной анимации
            new_level = min(1.0, max(0.0, level))
            self._smoothed_level = (
                self._level_smoothing * new_level + 
                (1 - self._level_smoothing) * self._smoothed_level
            )
            # Обновляем только если изменение значительное (>2%)
            if abs(self._smoothed_level - self.audio_level) > 0.02:
                self.audio_level = self._smoothed_level
                changed = True
        
        if recording is not None and recording != self.is_recording:
            self.is_recording = recording
            changed = True
        
        if paused is not None and paused != self.is_paused:
            self.is_paused = paused
            changed = True
        
        if accumulated is not None and accumulated != self.accumulated_text:
            self.accumulated_text = accumulated
            changed = True
        
        # Обновляем Live только при реальных изменениях
        if self._live and changed:
            self._request_render()
    
    def add_segment(self, text: str):
        """Добавляет распознанный сегмент."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.segments.append((timestamp, text))
    
    def print_segment(self, text: str, copied: bool = False):
        """Выводит сегмент текста (без Live)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        output = Text()
        if self.show_timestamps:
            output.append(f"[{timestamp}] ", style="dim")
        
        if copied:
            output.append("📋 ", style="green")
        
        output.append(text, style="white")
        
        self.console.print(output)
    
    def print_final_transcript(self):
        """Выводит полную транскрипцию."""
        if not self.segments:
            return
        
        self.console.print()
        
        table = Table(
            title="📝 Полная транскрипция",
            box=box.ROUNDED,
            border_style="green",
            show_lines=True
        )
        
        table.add_column("Время", style="dim", width=10)
        table.add_column("Текст", style="white")
        
        for timestamp, text in self.segments:
            table.add_row(timestamp, text)
        
        self.console.print(table)
        
        # Полный текст
        full_text = " ".join(t for _, t in self.segments)
        self.console.print()
        self.console.print(Panel(
            full_text,
            title="[bold]Объединённый текст[/bold]",
            border_style="cyan"
        ))
    
    def print_success(self, message: str):
        """Выводит сообщение об успехе."""
        self.console.print(f"[green]✅ {message}[/green]")
    
    def print_error(self, message: str):
        """Выводит сообщение об ошибке."""
        self.console.print(f"[red]❌ {message}[/red]")
    
    def print_warning(self, message: str):
        """Выводит предупреждение."""
        self.console.print(f"[yellow]⚠️ {message}[/yellow]")
    
    def print_info(self, message: str):
        """Выводит информационное сообщение."""
        self.console.print(f"[cyan]ℹ️ {message}[/cyan]")


# Fallback для систем без Rich
class SimpleConsoleUI:
    """Простой консольный UI без Rich (fallback)."""
    
    def __init__(self, **kwargs):
        self.is_recording = False
        self.audio_level = 0.0
        self.current_text = ""
        self.segments = []
        self.device_name = ""
        self.mode = "continuous"
        self._last_line_len = 0
    
    def print_banner(self):
        print("\n" + "=" * 45)
        print("  🎤 GigaAM Realtime ASR")
        print("  Распознавание речи в реальном времени")
        print("=" * 45 + "\n")
    
    def print_status(self, model: str, device: str, buffer: float, vad_threshold: float, mode: str):
        self.device_name = device
        self.mode = mode
        print(f"🧠 Модель: {model}")
        print(f"🎧 Устройство: {device}")
        print(f"⏱️  Буфер: {buffer} сек")
        if vad_threshold > 0:
            print(f"🔇 VAD порог: {vad_threshold}")
        mode_text = "🎯 Push-to-Talk" if mode == "push_to_talk" else "🔄 Непрерывный"
        print(f"📍 Режим: {mode_text}\n")
    
    def start_live_display(self):
        pass
    
    def stop_live_display(self):
        pass
    
    def update(self, text=None, level=None, recording=None, paused=None, accumulated=None):
        if text is not None:
            self.current_text = text
        if level is not None:
            self.audio_level = level
        if recording is not None:
            self.is_recording = recording
        
        # Формируем строку
        bars = int(self.audio_level * 10)
        level_str = "▓" * min(bars, 10) + "░" * max(0, 10 - bars)
        
        status = "🔴 REC" if self.is_recording else "⚪ READY"
        output = f"\r{status} [{level_str}] {self.current_text[:60]:<60}"
        
        print(output, end="", flush=True)
    
    def add_segment(self, text: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.segments.append((timestamp, text))
    
    def print_segment(self, text: str, copied: bool = False):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = "📋 " if copied else ""
        print(f"\n[{timestamp}] {prefix}{text}")
    
    def print_final_transcript(self):
        if not self.segments:
            return
        print("\n" + "=" * 50)
        print("📝 ПОЛНАЯ ТРАНСКРИПЦИЯ:")
        print("=" * 50)
        for timestamp, text in self.segments:
            print(f"[{timestamp}] {text}")
        print("=" * 50)
    
    def print_success(self, message: str):
        print(f"✅ {message}")
    
    def print_error(self, message: str):
        print(f"❌ {message}")
    
    def print_warning(self, message: str):
        print(f"⚠️ {message}")
    
    def print_info(self, message: str):
        print(f"ℹ️ {message}")


def get_console_ui(**kwargs):
    """Возвращает подходящий UI в зависимости от доступности Rich."""
    if RICH_AVAILABLE:
        return RichConsoleUI(**kwargs)
    else:
        return SimpleConsoleUI(**kwargs)
