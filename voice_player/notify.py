"""Уведомления и запуск процессов, которые не должны задерживать чтение микрофона."""

import shutil
import subprocess


def run_quiet(cmd: list[str]) -> None:
    # не ждём завершения, чтобы не задерживать чтение микрофона
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def notify(text: str) -> None:
    if shutil.which("notify-send"):
        run_quiet(["notify-send", "-a", "Voice Player", "-t", "2500", "-e", text])
