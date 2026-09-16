"""Голосовой ввод текста: вставка через буфер обмена и отправка Enter в то же окно."""

import logging
import re
import threading
import time

from .clipboard import clipboard_get, clipboard_set
from .config import SEND_WINDOW_SEC, TERMINAL_PATTERN
from .notify import notify
from .uinput import KEY_ENTER, KEY_LEFTCTRL, KEY_LEFTSHIFT, KEY_V, UInputDevice
from .windows import focus_window

logger = logging.getLogger(__name__)


class Dictation:
    """Куда и когда последний раз вставлен текст — чтобы «отправь» не нажал Enter где попало
    (например, в терминале с недописанной командой)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.window, self.at = "", 0.0

    def remember(self, window: str) -> None:
        with self.lock:
            self.window, self.at = window, time.monotonic()

    def take(self, window: str) -> bool:
        """Можно ли нажать Enter в этом окне. Разрешение одноразовое."""
        with self.lock:
            ok = bool(window) and window == self.window and time.monotonic() - self.at <= SEND_WINDOW_SEC
            if ok:
                self.window = ""
            return ok


def type_text(kdotool: str, keyboard: UInputDevice, text: str) -> str | None:
    """Вставить текст в активное окно через буфер обмена (набор по клавишам ломается на раскладках).
    -> класс окна, куда вставили, или None."""
    window_class, _, _ = focus_window(kdotool, "")  # без шаблона берётся активное окно, фокус не меняется
    if not window_class:
        return None
    previous = clipboard_get()
    if not clipboard_set(text):
        return None
    time.sleep(0.1)
    if re.search(TERMINAL_PATTERN, window_class, re.I):
        keyboard.tap([KEY_LEFTCTRL, KEY_LEFTSHIFT, KEY_V])  # в терминале Ctrl+V не вставляет
    else:
        keyboard.tap([KEY_LEFTCTRL, KEY_V])
    if previous is not None:
        time.sleep(0.5)
        clipboard_set(previous)  # вернуть то, что было в буфере
    return window_class


def send_enter(kdotool: str, keyboard: UInputDevice, dictation: Dictation, notify_on: bool) -> None:
    window_class = focus_window(kdotool, "")[0]
    if dictation.take(window_class):
        keyboard.tap([KEY_ENTER])
        message = "отправлено"
    else:
        message = "«отправь» работает только сразу после «напиши» и в том же окне"
    logger.info(message)
    if notify_on:
        notify(message)
