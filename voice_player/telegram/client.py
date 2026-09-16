"""Тонкая обёртка над Pyrogram: одно подключение на всё время работы + поллинг-хелперы.

Pyrogram даёт синхронный API (без async/await в вызывающем коде), поэтому клиент используется
так же, как остальные блокирующие вызовы проекта (playerctl, yt-dlp, faster-whisper) — просто
исполняется в отдельном потоке, без отдельного asyncio-цикла в остальной части кода.
"""

import logging
import time
from collections.abc import Callable
from typing import TypeVar

from ..config import TELEGRAM_DATA_DIR, TELEGRAM_POLL_INTERVAL_SEC
from .settings import TelegramSettings

logger = logging.getLogger(__name__)

T = TypeVar("T")


def make_client(settings: TelegramSettings):
    from pyrogram import Client

    TELEGRAM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Client(
        settings.session_name,
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        workdir=str(TELEGRAM_DATA_DIR),
    )


def poll_until(check: Callable[[], T | None], timeout: float) -> T | None:
    """Звать check() пока не вернёт не-None или не выйдет время."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result is not None:
            return result
        time.sleep(TELEGRAM_POLL_INTERVAL_SEC)
    return None
