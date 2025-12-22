import os
import threading
from pathlib import Path
from typing import Dict

import pygame

_initialized = False
_failed = False
_cache: Dict[Path, pygame.mixer.Sound] = {}


def init_audio():
    global _initialized, _failed
    if _initialized or _failed:
        return
    try:
        # Small buffer to reduce start latency
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=256)
        pygame.init()
        pygame.mixer.init()
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
        # Play asynchronously; mixer handles concurrency
        snd.play()
    except Exception as e:
        print(f"(Audio play failed for {path}: {e})")

