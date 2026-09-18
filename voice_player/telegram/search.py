"""Поиск музыки через бота: сообщение боту -> кнопки -> клик по первой -> скачанный файл.

Бот отвечает сообщением с инлайн-кнопками (по одной на найденный трек); по требованиям
проекта всегда нажимается первая. Дальше бот либо редактирует своё сообщение, либо шлёт новое
с самим аудио — оба случая ловит _audio_reply.

Все методы здесь — корутины, исполняются через TelegramWorker.run() (см. client.py) в его
собственном потоке/цикле, а не там, откуда их позвали (обычно это одноразовый
threading.Thread из VoiceLoop/Asker) — иначе Pyrogram путает event loop'ы.
"""

import json
import logging
from pathlib import Path

from ..config import (
    TELEGRAM_DATA_DIR,
    TELEGRAM_DOWNLOAD_TIMEOUT_SEC,
    TELEGRAM_SAVED_DIR,
    TELEGRAM_SEARCH_TIMEOUT_SEC,
)
from .client import TelegramWorker, poll_until
from .settings import TelegramSettings

logger = logging.getLogger(__name__)

_OVERALL_TIMEOUT_SEC = TELEGRAM_SEARCH_TIMEOUT_SEC + TELEGRAM_DOWNLOAD_TIMEOUT_SEC + 10

# file_unique_id (свой у Telegram для каждого конкретного загруженного файла, не зависит от
# того, через какое сообщение/поиск он пришёл) -> путь на диске. Без этого поиск одного и
# того же трека дважды скачивал бы его дважды.
SAVED_INDEX = TELEGRAM_DATA_DIR / "saved_index.json"


def load_saved_index() -> dict[str, str]:
    if not SAVED_INDEX.is_file():
        return {}
    try:
        return json.loads(SAVED_INDEX.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("%s повреждён, начинаю индекс заново", SAVED_INDEX.name)
        return {}


def remember_saved(file_unique_id: str, path: str) -> None:
    index = load_saved_index()
    index[file_unique_id] = path
    SAVED_INDEX.parent.mkdir(parents=True, exist_ok=True)
    SAVED_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


class TelegramSearch:
    def __init__(self, settings: TelegramSettings):
        self.bot = settings.search_bot
        self.worker = TelegramWorker(settings)

    def find_track(self, query: str) -> Path | None:
        try:
            return self.worker.run(self._find_track(query), timeout=_OVERALL_TIMEOUT_SEC)
        except Exception:
            logger.debug("ошибка телеграм-поиска «%s»", query, exc_info=True)
            return None

    async def _find_track(self, query: str) -> Path | None:
        app = self.worker.app
        sent = await app.send_message(self.bot, query)
        reply = await poll_until(lambda: self._reply_with_buttons(sent.id), TELEGRAM_SEARCH_TIMEOUT_SEC)
        if reply is None:
            logger.debug("телеграм-бот не ответил на «%s»", query)
            return None
        await reply.click(0)  # всегда первый результат
        audio_msg = await poll_until(lambda: self._audio_reply(reply.id), TELEGRAM_DOWNLOAD_TIMEOUT_SEC)
        if audio_msg is None:
            logger.debug("телеграм-бот не прислал аудио на «%s»", query)
            return None

        media = audio_msg.audio or audio_msg.voice or audio_msg.document
        file_unique_id = getattr(media, "file_unique_id", None)
        if file_unique_id:
            cached = load_saved_index().get(file_unique_id)
            if cached and Path(cached).is_file():
                logger.info("уже скачивали раньше: %s", Path(cached).name)
                return Path(cached)

        # остаётся насовсем (не кэш!) -- часть общего пула для "дальше" (LocalPlayer)
        TELEGRAM_SAVED_DIR.mkdir(parents=True, exist_ok=True)
        downloaded = Path(await app.download_media(audio_msg, file_name=f"{TELEGRAM_SAVED_DIR}/"))
        if file_unique_id:
            remember_saved(file_unique_id, str(downloaded))
        return downloaded

    async def _reply_with_buttons(self, after_id: int):
        async for message in self.worker.app.get_chat_history(self.bot, limit=5):
            if message.id > after_id and message.reply_markup:
                return message
        return None

    async def _audio_reply(self, after_id: int):
        async for message in self.worker.app.get_chat_history(self.bot, limit=5):
            if message.id > after_id and (message.audio or message.voice or message.document):
                return message
        return None

    def close(self) -> None:
        self.worker.stop()
