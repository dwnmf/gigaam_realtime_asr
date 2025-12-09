"""GigaAM Realtime ASR - модули для распознавания речи в реальном времени."""

from .realtime_asr import RealtimeASR
from .audio_devices import list_audio_devices, get_device_by_name, get_loopback_device

__all__ = [
    'RealtimeASR',
    'list_audio_devices',
    'get_device_by_name',
    'get_loopback_device',
]
