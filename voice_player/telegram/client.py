"""Pyrogram-клиент в двух режимах: разовый синхронный (voice-player-telegram-sync,
один поток на весь скрипт — штатный «синхронный» API Pyrogram тут работает без проблем) и
постоянный (TelegramSearch, дёргается из VoiceLoop/Asker) — а вот тут просто вызывать методы
клиента нельзя.

Pyrogram привязывает свои внутренние asyncio Task/Future к тому event loop, который увидел
на момент СОЗДАНИЯ Client(...) (не только start()) — а «синхронный» вызов (client.method(...)
без await) при этом каждый раз сам создаёт event loop под поток, из которого его позвали.
find_track() дёргается из НОВОГО threading.Thread на каждый голосовой запрос (так уже работают
VoiceLoop/Asker) — Client был создан в одном цикле, а send_message пытался исполниться в
другом, отсюда "Task ... attached to a different loop".

TelegramWorker решает это лобовым способом: один выделенный поток с одним asyncio-циклом на
всё время жизни клиента, и Client(...) создаётся ВНУТРИ этого потока (после того, как цикл
воркера уже выставлен текущим) — а не в конструкторе, вызванном откуда угодно. Что бы ни
позвало run() позже, корутина всегда исполняется в этом же одном потоке/цикле — Pyrogram
внутри себя остаётся последовательным независимо от того, из какого потока пришёл запрос.
"""

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable
from typing import TypeVar

from ..config import TELEGRAM_DATA_DIR, TELEGRAM_POLL_INTERVAL_SEC
from .settings import TelegramSettings

logger = logging.getLogger(__name__)

T = TypeVar("T")


def make_client(settings: TelegramSettings):
    """Для одноразового синхронного использования в один поток (voice-player-telegram-sync)."""
    from pyrogram import Client

    TELEGRAM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Client(
        settings.session_name,
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        workdir=str(TELEGRAM_DATA_DIR),
    )


class TelegramWorker:
    """Клиент Pyrogram + свой event loop в отдельном потоке, живёт всё время работы voice-player."""

    def __init__(self, settings: TelegramSettings):
        self.app = None
        self._loop = asyncio.new_event_loop()
        self._error: Exception | None = None
        ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run, args=(settings, ready), daemon=True, name="telegram-worker",
        )
        self._thread.start()
        ready.wait()
        if self._error is not None:
            raise self._error

    def _run(self, settings: TelegramSettings, ready: threading.Event) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            # Client(...) создаётся здесь, а не в __init__: Pyrogram запоминает "текущий" цикл
            # уже на этом шаге, а set_event_loop() выше делает текущим именно self._loop.
            # app.start() — синхронный вызов (без await, цикл ещё не "running"): Pyrogram сам
            # прогонит его через self._loop.run_until_complete(...) внутри себя — дополнительно
            # оборачивать не нужно, а с двойным run_until_complete() всё ломается.
            self.app = make_client(settings)
            self.app.start()
        except Exception as e:
            self._error = e
            ready.set()
            return
        ready.set()
        self._loop.run_forever()

    def run(self, coro: Awaitable[T], timeout: float | None = None) -> T:
        """Выполнить корутину в потоке клиента и дождаться результата — можно звать из любого потока."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    async def _stop(self) -> None:
        await self.app.stop()

    def stop(self) -> None:
        try:
            self.run(self._stop(), timeout=10)
        except Exception:
            logger.debug("ошибка при остановке телеграм-клиента", exc_info=True)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5)


async def poll_until(check: Callable[[], Awaitable[T | None]], timeout: float) -> T | None:
    """Звать check() (корутину) пока не вернёт не-None или не выйдет время."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        result = await check()
        if result is not None:
            return result
        await asyncio.sleep(TELEGRAM_POLL_INTERVAL_SEC)
    return None
