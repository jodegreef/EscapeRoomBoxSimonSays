import os
import threading
from pathlib import Path
from typing import Dict, Optional

import pygame

# Favor ALSA on Linux to avoid PulseAudio overhead on Pi; allow pinning a device via AUDIO_DEVICE
os.environ.setdefault("SDL_AUDIODRIVER", "alsa")
if "AUDIO_DEVICE" in os.environ:
    os.environ["AUDIODEV"] = os.environ["AUDIO_DEVICE"]

_initialized = False
_failed = False
_cache: Dict[Path, pygame.mixer.Sound] = {}
_preroll_sound: Optional[pygame.mixer.Sound] = None


def init_audio():
    global _initialized, _failed, _preroll_sound
    if _initialized or _failed:
        return
    try:
        freq = int(os.environ.get("AUDIO_RATE", "22050"))
        buf = int(os.environ.get("AUDIO_BUFFER", "128"))
        pygame.mixer.pre_init(frequency=freq, size=-16, channels=2, buffer=buf)
        pygame.init()
        pygame.mixer.init()
        _preroll_sound = _load_pad_sound() or _make_silence_sound(freq)
        _initialized = True
    except Exception as e:
        _failed = True
        print(f"(Audio init failed: {e})")


def play_sound_file(path: Path):
    init_audio()
    if _failed:
        return
    if not path.exists():
        print(f"(Sound file not found at {path})")
        return
    try:
        snd = _cache.get(path)
        if snd is None:
            snd = pygame.mixer.Sound(str(path))
            _cache[path] = snd
        channel = pygame.mixer.find_channel(True)
        if _preroll_sound:
            channel.play(_preroll_sound)
            channel.queue(snd)
        else:
            channel.play(snd)
    except Exception as e:
        print(f"(Audio play failed for {path}: {e})")


def _make_silence_sound(freq: int) -> Optional[pygame.mixer.Sound]:
    pad_ms = int(os.environ.get("AUDIO_PAD_MS", "200"))
    try:
        mixer_init = pygame.mixer.get_init()
        channels = mixer_init[2] if mixer_init else 2
        sample_size_bytes = 2  # 16-bit
        frames = max(1, int(freq * (pad_ms / 1000)))
        buf = b"\x00" * frames * channels * sample_size_bytes
        return pygame.mixer.Sound(buffer=buf)
    except Exception as e:
        print(f"(Could not create silence pad: {e})")
        return None


def _load_pad_sound() -> Optional[pygame.mixer.Sound]:
    pad_path = os.environ.get("AUDIO_PAD_FILE", "pad.wav")
    if not pad_path:
        return None
    p = Path(pad_path)
    if not p.exists():
        return None
    try:
        return pygame.mixer.Sound(str(p))
    except Exception as e:
        print(f"(Could not load pad file {pad_path}: {e})")
        return None

