"""Проигрывание локальных файлов (скачанных из Telegram) через VLC.

VLC поддерживает MPRIS «из коробки» (плагин control/dbus в самом пакете vlc, без AUR),
поэтому дальше «пауза»/«дальше»/etc. работают через тот же Players/playerctl, что и для
браузера или Telegram — никакого отдельного управления плеером тут не нужно.
"""

from pathlib import Path

from .notify import notify, run_quiet
from .players import Players

VLC_PATTERN = "vlc"


def play_local_file(path: Path, players: Players, label: str, notify_on: bool) -> None:
    run_quiet(["vlc", "--intf", "dummy", "--no-video", "--play-and-exit", str(path)])
    players.name(VLC_PATTERN)
    if notify_on:
        notify(label)
