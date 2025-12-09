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
        
        self.console = Console()
        self.show_timestamps = show_timestamps
        self.show_level = show_level
        
        # Состояние
        self.is_recording = False
        self.is_paused = False
        self.audio_level = 0.0
        self.current_text = ""
        self.accumulated_text = ""
        self.segments: List[Tuple[str, str]] = []  # (timestamp, text)
        self.device_name = "Не выбрано"
        self.mode = "continuous"  # continuous | push_to_talk
        
        # Live display
        self._live: Optional[Live] = None
        self._stop_event = threading.Event()
        self._update_thread: Optional[threading.Thread] = None
    
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
    
    def _generate_display(self) -> Panel:
        """Генерирует панель отображения для Live."""
        # Статус записи
        if self.is_recording:
            status = Text("🔴 ЗАПИСЬ", style="bold red")
        elif self.is_paused:
            status = Text("⏸️  ПАУЗА", style="bold yellow")
        else:
            status = Text("⚪ ГОТОВ", style="bold green")
        
        # Уровень звука
        level_bar = self._get_level_bar(self.audio_level)
        level_text = f" {self.audio_level:.2f}"
        
        # Текущий текст
        display_text = self.current_text if self.current_text else "[dim]Ожидание речи...[/dim]"
        
        # Собираем Layout
        content = Text()
        
        # Строка статуса
        content.append("  ")
        content.append_text(status)
        content.append("  │  ")
        content.append_text(level_bar)
        content.append(level_text, style="dim")
        content.append("\n\n")
        
        # Текст
        if self.accumulated_text:
            content.append("  ", style="dim")
            content.append(self.accumulated_text, style="dim")
            content.append("\n")
        
        content.append("  ")
        if self.is_recording:
            content.append(display_text, style="bold white")
        else:
            content.append(display_text)
        
        content.append("\n")
        
        # Подсказки
        if self.mode == "push_to_talk":
            hint = "[dim]Удерживайте [SPACE] для записи • [ESC] выход[/dim]"
        else:
            hint = "[dim]Ctrl+C для выхода[/dim]"
        
        panel = Panel(
            content,
            title=f"[bold cyan]🎤 {self.device_name}[/bold cyan]",
            subtitle=hint,
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 1)
        )
        
        return panel
    
    def start_live_display(self):
        """Запускает Live Display."""
        self._stop_event.clear()
        self._live = Live(
            self._generate_display(),
            console=self.console,
            refresh_per_second=15,
            transient=False
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
        """Обновляет отображение."""
        if text is not None:
            self.current_text = text
        if level is not None:
            self.audio_level = min(1.0, max(0.0, level))
        if recording is not None:
            self.is_recording = recording
        if paused is not None:
            self.is_paused = paused
        if accumulated is not None:
            self.accumulated_text = accumulated
        
        if self._live:
            self._live.update(self._generate_display())
    
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
