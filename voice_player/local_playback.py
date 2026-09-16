"""Проигрывание локальных файлов (скачанных из Telegram) через mpv.

mpv регистрируется в MPRIS через плагин mpv-mpris, поэтому дальше «пауза»/«дальше»/etc.
работают через тот же Players/playerctl, что и для браузера или Telegram — никакого
отдельного управления плеером тут не нужно.
"""

from pathlib import Path

from .notify import notify, run_quiet
from .players import Players

MPV_PATTERN = "mpv"


def play_local_file(path: Path, players: Players, label: str, notify_on: bool) -> None:
    run_quiet(["mpv", "--no-video", str(path)])
    players.name(MPV_PATTERN)
    if notify_on:
        notify(label)
