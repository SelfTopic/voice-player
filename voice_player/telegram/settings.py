"""Настройки Telegram-интеграции: ~/.config/voice-player/telegram.toml."""

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ..config import TELEGRAM_CONFIG

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ("api_id", "api_hash", "session_name", "mr_kitty_channel", "search_bot")


@dataclass
class TelegramSettings:
    api_id: int
    api_hash: str
    session_name: str
    mr_kitty_channel: str
    search_bot: int | str  # @username или числовой id
    # регулярка (без учёта регистра): треки с совпадением в названии voice-player-telegram-sync
    # не скачивает — каверы, ремиксы и т.п., которые обычно не нужны в офлайн-каталоге
    skip_titles_matching: str = ""


def load_settings(path: Path = TELEGRAM_CONFIG) -> TelegramSettings | None:
    if not path.is_file():
        return None
    with path.open("rb") as f:
        data = tomllib.load(f)
    missing = [key for key in _REQUIRED_KEYS if not data.get(key)]
    if missing:
        logger.warning("%s: не заполнены поля %s, телеграм-интеграция выключена", path.name, missing)
        return None
    fields = {key: data[key] for key in _REQUIRED_KEYS}
    fields["skip_titles_matching"] = data.get("skip_titles_matching", "")
    return TelegramSettings(**fields)
