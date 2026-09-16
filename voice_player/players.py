"""Кому из медиаплееров отдавать голосовые команды."""

import logging
import re
import subprocess
import threading
import time

from .notify import notify

logger = logging.getLogger(__name__)


def playerctl(instance: str, *action: str) -> bool:
    try:
        return subprocess.run(
            ["playerctl", "-p", instance, *action],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class Players:
    """«пауза» глушит всё, что играет. «играй» включает то, что упомянуто позже:
    приложение, названное голосом («телеграм»), или то, что было поставлено на паузу.
    Остальное — тому, что играет сейчас."""

    def __init__(self):
        self.lock = threading.Lock()
        self.named: str | None = None  # регулярка приложения, названного последним
        self.named_at = 0.0
        self.paused: list[str] = []
        self.paused_at = 0.0

    def name(self, pattern: str) -> None:
        with self.lock:
            self.named, self.named_at = pattern, time.monotonic()

    @staticmethod
    def all_players() -> list[tuple[str, str]]:
        try:
            out = subprocess.run(
                ["playerctl", "-a", "status", "--format", "{{playerInstance}}\t{{status}}"],
                capture_output=True, text=True, timeout=2,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return []
        players = []
        for line in out.splitlines():
            instance, _, status = line.partition("\t")
            if instance and instance != "playerctld":
                players.append((instance, status.strip()))
        return players

    def pause_playing(self) -> list[str]:
        playing = [i for i, s in self.all_players() if s == "Playing"]
        for instance in playing:
            playerctl(instance, "pause")
        if playing:
            with self.lock:
                self.paused, self.paused_at = playing, time.monotonic()
        return playing

    def targets(self, action: str) -> tuple[list[str], list[str]]:
        """-> (кому отправить команду, кого перед этим поставить на паузу)"""
        players = self.all_players()
        instances = [i for i, _ in players]
        playing = [i for i, s in players if s == "Playing"]
        with self.lock:
            named = None
            if self.named:
                rx = re.compile(self.named, re.I)
                named = next((i for i in instances if rx.search(i)), None)
            paused = [i for i in self.paused if i in instances]
            named_is_newer = self.named_at > self.paused_at

        if action == "play":
            if named and (named_is_newer or not paused):
                return [named], [i for i in playing if i != named]
            if paused:
                return paused, []
            return playing[:1] or ["playerctld"], []
        target = playing[:1] or ([named] if named else ["playerctld"])
        return target, []

    def run(self, action: list[str], label: str, notify_on: bool) -> None:
        if action[0] == "pause":
            ok = True  # если ничего не играет — это не ошибка
            paused = self.pause_playing()
            sent = paused
        else:
            sent, to_pause = self.targets(action[0])
            for instance in to_pause:
                playerctl(instance, "pause")
            ok = all(playerctl(instance, *action) for instance in sent)
        logger.debug("плеер: %s", ", ".join(sent) or "—")
        if not ok:
            logger.warning("плеер не умеет «%s»", label)
        if notify_on:
            notify(label if ok else f"плеер не умеет «{label}»")
