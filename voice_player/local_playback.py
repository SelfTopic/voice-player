"""Проигрывание локальных файлов (скачанных из Telegram) через VLC.

VLC поддерживает MPRIS «из коробки» (плагин control/dbus в самом пакете), поэтому дальше
«пауза»/«дальше»/etc. работают через тот же Players/playerctl, что и для браузера или Telegram.

LocalPlayer держит один активный процесс: новый трек сначала останавливает предыдущий, если
тот ещё играет. Без этого каждый вызов запускал независимый VLC, ничего не трогая — оттуда
несколько треков одновременно, если голосом назвать больше одного подряд.
"""

import subprocess
import threading
from pathlib import Path

from .notify import notify, run_quiet
from .players import Players

VLC_PATTERN = "vlc"


class LocalPlayer:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.process: subprocess.Popen | None = None

    def play(self, path: Path, players: Players, label: str, notify_on: bool) -> None:
        with self.lock:
            self._stop()
            self.process = run_quiet(["vlc", "--intf", "dummy", "--no-video", "--play-and-exit", str(path)])
        players.name(VLC_PATTERN)
        if notify_on:
            notify(label)

    def _stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
