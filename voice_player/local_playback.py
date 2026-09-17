"""Проигрывание локальных файлов (скачанных из Telegram) через VLC.

VLC поддерживает MPRIS «из коробки» (плагин control/dbus в самом пакете), поэтому
«пауза»/«играй» работают через тот же Players/playerctl, что и для браузера или Telegram —
у VLC там всегда ровно один трек, MPRIS Pause/Play это отрабатывает нормально.

Но у каждого запущенного VLC плейлист из одного файла — родных Next/Previous там просто
нет, чем листать. Поэтому «дальше»/«назад» для локальных треков ловит не playerctl, а сам
LocalPlayer (см. VLC_PATTERN и его использование в loop.py): «дальше» — случайный другой
трек из общего пула (каталог Mr. Kitty + всё, что когда-либо нашёл бот-поиск), «назад» —
на шаг раньше по истории уже проигранного в этом сеансе.

LocalPlayer держит один активный процесс: новый трек сначала останавливает предыдущий,
вместо того чтобы играть поверх него (раньше каждый вызов запускал новый VLC, ничего не
останавливая — вот откуда несколько треков сразу).
"""

import logging
import random
import subprocess
import threading
from pathlib import Path

from .notify import notify, run_quiet
from .players import Players

VLC_PATTERN = "vlc"
# Mr. Kitty качается как .mp3, но бот-поиск в Telegram присылает аудио в чём попало
AUDIO_EXTENSIONS = ("*.mp3", "*.m4a", "*.ogg", "*.opus", "*.flac", "*.wav")

logger = logging.getLogger(__name__)


class LocalPlayer:
    def __init__(self, track_dirs: list[Path]):
        self.track_dirs = track_dirs
        self.lock = threading.Lock()
        self.process: subprocess.Popen | None = None
        self.history: list[Path] = []
        self.position = -1  # индекс текущего трека в history

    def play(self, path: Path, players: Players, label: str, notify_on: bool) -> None:
        """Явный выбор трека (голосом названный или найденный ботом): всё, что было
        «впереди» после текущей позиции (если до этого листали назад), отбрасывается."""
        with self.lock:
            del self.history[self.position + 1 :]
            self.history.append(path)
            self.position = len(self.history) - 1
            self._spawn(path)
        players.name(VLC_PATTERN)
        if notify_on:
            notify(label)

    def next(self, players: Players, notify_on: bool) -> None:
        """Если до этого «листали назад» — шаг вперёд по истории; иначе случайный трек
        из общего пула (не совпадающий с текущим, если пул больше одного файла)."""
        with self.lock:
            if self.position + 1 < len(self.history):
                self.position += 1
            else:
                current = self.history[self.position] if self.history else None
                pool = [p for p in self._pool() if p != current]
                if not pool:
                    logger.debug("некуда переключаться: пул локальных треков пуст")
                    return
                self.history.append(random.choice(pool))
                self.position = len(self.history) - 1
            path = self.history[self.position]
            self._spawn(path)
        players.name(VLC_PATTERN)
        if notify_on:
            notify(path.stem)

    def previous(self, players: Players, notify_on: bool) -> None:
        with self.lock:
            if self.position <= 0:
                logger.debug("некуда возвращаться: история пуста")
                return
            self.position -= 1
            path = self.history[self.position]
            self._spawn(path)
        players.name(VLC_PATTERN)
        if notify_on:
            notify(path.stem)

    def _pool(self) -> list[Path]:
        return [
            p for d in self.track_dirs if d.is_dir()
            for pattern in AUDIO_EXTENSIONS for p in d.glob(pattern)
        ]

    def _spawn(self, path: Path) -> None:
        """Вызывать только под self.lock."""
        self._stop()
        self.process = run_quiet(["vlc", "--intf", "dummy", "--no-video", "--play-and-exit", str(path)])

    def _stop(self) -> None:
        """Вызывать только под self.lock."""
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
