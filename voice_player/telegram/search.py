"""Поиск музыки через бота: сообщение боту -> кнопки -> клик по первой -> скачанный файл.

Бот отвечает сообщением с инлайн-кнопками (по одной на найденный трек); по требованиям
проекта всегда нажимается первая. Дальше бот либо редактирует своё сообщение, либо шлёт новое
с самим аудио — оба случая ловит _audio_reply.
"""

import logging
from pathlib import Path

from ..config import (
    TELEGRAM_DOWNLOAD_TIMEOUT_SEC,
    TELEGRAM_SAVED_DIR,
    TELEGRAM_SEARCH_TIMEOUT_SEC,
)
from .client import make_client, poll_until
from .settings import TelegramSettings

logger = logging.getLogger(__name__)


class TelegramSearch:
    def __init__(self, settings: TelegramSettings):
        self.bot = settings.search_bot
        self.app = make_client(settings)
        self.app.start()

    def find_track(self, query: str) -> Path | None:
        try:
            sent = self.app.send_message(self.bot, query)
            reply = poll_until(lambda: self._reply_with_buttons(sent.id), TELEGRAM_SEARCH_TIMEOUT_SEC)
            if reply is None:
                logger.debug("телеграм-бот не ответил на «%s»", query)
                return None
            reply.click(0)  # всегда первый результат
            audio = poll_until(lambda: self._audio_reply(reply.id), TELEGRAM_DOWNLOAD_TIMEOUT_SEC)
            if audio is None:
                logger.debug("телеграм-бот не прислал аудио на «%s»", query)
                return None
            # остаётся насовсем (не кэш!) -- часть общего пула для "дальше" (LocalPlayer)
            TELEGRAM_SAVED_DIR.mkdir(parents=True, exist_ok=True)
            return Path(self.app.download_media(audio, file_name=f"{TELEGRAM_SAVED_DIR}/"))
        except Exception:
            logger.debug("ошибка телеграм-поиска «%s»", query, exc_info=True)
            return None

    def _reply_with_buttons(self, after_id: int):
        for message in self.app.get_chat_history(self.bot, limit=5):
            if message.id > after_id and message.reply_markup:
                return message
        return None

    def _audio_reply(self, after_id: int):
        for message in self.app.get_chat_history(self.bot, limit=5):
            if message.id > after_id and (message.audio or message.voice or message.document):
                return message
        return None

    def close(self) -> None:
        self.app.stop()
