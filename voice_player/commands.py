"""Реестр быстрых команд: слово -> что с ним делать."""

import logging
from pathlib import Path

from .config import SCROLL_NOTCHES

logger = logging.getLogger(__name__)

# Команды плеера: кому их отдать, решает Players. Без явного -p playerctl отдаёт команду,
# которую текущий плеер не умеет (например «дальше» у одиночного видео YouTube), следующему — Telegram.
PLAYER = "__player__"
FULLSCREEN = "__fullscreen__"
SCROLL = "__scroll__"
SINK = "__sink__"
SEND = "__send__"

# слово -> команда. Слова должны быть известны модели.
COMMANDS: dict[str, list[str]] = {
    "пауза": [PLAYER, "pause"],
    "стоп": [PLAYER, "pause"],
    "играй": [PLAYER, "play"],
    "плей": [PLAYER, "play"],
    "продолжи": [PLAYER, "play"],
    "продолжай": [PLAYER, "play"],
    "дальше": [PLAYER, "next"],
    "следующее": [PLAYER, "next"],
    "следующая": [PLAYER, "next"],
    "назад": [PLAYER, "previous"],
    "предыдущее": [PLAYER, "previous"],
    "вперёд": [PLAYER, "position", "10+"],
    "промотай": [PLAYER, "position", "10+"],
    "мотай": [PLAYER, "position", "10+"],
    "перемотай": [PLAYER, "position", "10+"],
    "отмотай": [PLAYER, "position", "10-"],
    "громче": ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"],
    "тише": ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"],
    "полный экран": [FULLSCREEN],
    "разверни": [FULLSCREEN],
    "вниз": [SCROLL, str(-SCROLL_NOTCHES)],
    "ниже": [SCROLL, str(-SCROLL_NOTCHES)],
    "вверх": [SCROLL, str(SCROLL_NOTCHES)],
    "выше": [SCROLL, str(SCROLL_NOTCHES)],
    "отправь": [SEND],
}


def read_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def load_mapping(path: Path, fallback: dict[str, str]) -> dict[str, str]:
    """«терминал = konsole|kitty» -> {"терминал": "konsole|kitty"}"""
    if not path.is_file():
        return dict(fallback)
    mapping = {}
    for line in read_lines(path):
        word, sep, pattern = line.partition("=")
        if sep and word.strip() and pattern.strip():
            mapping[word.strip().lower()] = pattern.strip()
        else:
            logger.warning("%s: не понял строку «%s»", path.name, line)
    return mapping
