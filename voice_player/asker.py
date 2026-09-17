"""Медленный режим: «джарвис, включи ...» и «загугли ...», распознаётся Whisper."""

import logging
import time
import urllib.parse

from .clipboard import clipboard_get, clipboard_set
from .config import BROWSER_PATTERN
from .dictation import Dictation, type_text
from .grammar import ASK, ASK_YOUTUBE, DICTATE, GOOGLE, PROMPTS, extract_query
from .local_playback import LocalPlayer
from .notify import notify, run_quiet
from .players import Players, playerctl
from .telegram.search import TelegramSearch
from .uinput import KEY_ENTER, KEY_ESC, KEY_L, KEY_LEFTCTRL, KEY_V, UInputDevice
from .windows import focus_window

logger = logging.getLogger(__name__)


def replace_youtube_tab(kdotool: str | None, keyboard: "UInputDevice | None", url: str) -> bool:
    """Открыть ссылку в текущей вкладке YouTube, а не в новой: Ctrl+L, вставить, Enter.
    Срабатывает, только если в Chrome выбрана вкладка YouTube; иначе False — открывай новую."""
    if not (kdotool and keyboard):
        return False
    window_class, fullscreen, caption = focus_window(kdotool, "chrom")
    if not window_class or "YouTube" not in caption:
        return False
    previous = clipboard_get()
    if not clipboard_set(url):
        return False
    time.sleep(0.15)  # дать окну получить фокус
    if fullscreen == "1":
        keyboard.tap([KEY_ESC])  # в полноэкранном видео адресной строки нет
        time.sleep(0.4)
    keyboard.tap([KEY_LEFTCTRL, KEY_L])
    time.sleep(0.1)
    keyboard.tap([KEY_LEFTCTRL, KEY_V])
    time.sleep(0.1)
    keyboard.tap([KEY_ENTER])
    if previous is not None:
        time.sleep(0.5)
        clipboard_set(previous)  # вернуть то, что было в буфере
    return True


class Asker:
    def __init__(
        self, whisper_model: str, names: list[str], players: Players,
        kdotool: str | None, keyboard: "UInputDevice | None", dictation: Dictation, notify_on: bool,
        telegram: TelegramSearch | None = None, local_player: LocalPlayer | None = None,
    ):
        import numpy as np
        import yt_dlp
        from faster_whisper import WhisperModel

        from .grammar import build_prompt

        self.np, self.yt_dlp = np, yt_dlp
        self.players = players
        self.kdotool, self.keyboard = kdotool, keyboard
        self.dictation = dictation
        self.notify_on = notify_on
        self.telegram = telegram
        self.local_player = local_player or LocalPlayer()
        self.prompt = build_prompt(names)
        self.whisper = WhisperModel(whisper_model, device="cpu", compute_type="int8")

    def close(self) -> None:
        if self.telegram:
            self.telegram.close()

    def say(self, text: str) -> None:
        logger.info(text)
        if self.notify_on:
            notify(text)

    def transcribe(self, audio: bytes, mode: str = ASK) -> str:
        samples = self.np.frombuffer(audio, dtype=self.np.int16).astype(self.np.float32) / 32768.0
        segments, _ = self.whisper.transcribe(
            samples, language="ru", beam_size=5, initial_prompt=PROMPTS.get(mode, self.prompt),
        )
        return " ".join(s.text.strip() for s in segments).strip()

    def search(self, query: str) -> dict | None:
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
        with self.yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
        entries = info.get("entries") or []
        return entries[0] if entries else None

    def handle(self, audio: bytes, paused: list[str], mode: str = ASK) -> None:
        playback_replaced = False
        try:
            t = time.monotonic()
            text = self.transcribe(audio, mode)
            logger.debug("whisper: «%s» (%.1f с)", text, time.monotonic() - t)
            query = extract_query(text, mode)
            if not query:
                self.say("не расслышал")
                return
            if mode == DICTATE:
                window = type_text(self.kdotool, self.keyboard, query)
                if window:
                    self.dictation.remember(window)
                    self.say(f"✍ {query}")
                else:
                    self.say("не удалось вставить текст")
                return
            if mode == GOOGLE:
                # поиск — всегда новая вкладка; музыка после записи запроса продолжит играть
                run_quiet(["xdg-open", "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)])
                self.say(f"🔎 {query}")
                return
            if mode == ASK and self.telegram:
                playback_replaced = self._play_from_telegram(query)
                if playback_replaced:
                    return
            playback_replaced = self._search_youtube(query)
        except Exception as e:
            logger.debug("необработанная ошибка в Asker.handle", exc_info=True)
            self.say(f"ошибка: {e}")
        finally:
            if not playback_replaced:
                for instance in paused:
                    playerctl(instance, "play")

    def _play_from_telegram(self, query: str) -> bool:
        """Режим ASK (музыка): поискать у бота в Telegram. -> нашли и запустили?"""
        self.say(f"ищу в телеграме: {query}")
        t = time.monotonic()
        track = self.telegram.find_track(query)
        logger.debug("телеграм-поиск: %.1f с", time.monotonic() - t)
        if not track:
            logger.debug("телеграм ничего не нашёл, пробую youtube")
            return False
        self.local_player.play(track, self.players, query, notify_on=False)  # своё "▶" даст self.say ниже
        self.say(f"▶ {query}")
        return True

    def _search_youtube(self, query: str) -> bool:
        """Режим ASK_YOUTUBE, и подстраховка для ASK, если телеграм не нашёл. -> нашли и открыли?"""
        self.say(f"ищу: {query}")
        t = time.monotonic()
        video = self.search(query)
        if not video:
            self.say(f"ничего не нашёл: {query}")
            return False
        logger.debug("поиск: %.1f с", time.monotonic() - t)
        url = f"https://www.youtube.com/watch?v={video['id']}"
        if replace_youtube_tab(self.kdotool, self.keyboard, url):
            where = "в той же вкладке"
        else:
            run_quiet(["xdg-open", url])
            where = "в новой вкладке"
        self.players.name(BROWSER_PATTERN)
        self.say(f"▶ {video.get('title') or query}")
        logger.debug("открыто %s", where)
        return True
