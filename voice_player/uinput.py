"""Виртуальная клавиатура/мышь через /dev/uinput."""

import fcntl
import os
import struct
import time

# linux/input-event-codes.h, linux/uinput.h
EV_SYN, EV_KEY, EV_REL, SYN_REPORT = 0x00, 0x01, 0x02, 0
KEY_ESC, KEY_ENTER, KEY_LEFTCTRL, KEY_F, KEY_L, KEY_V, KEY_LEFTSHIFT = 1, 28, 29, 33, 38, 47, 42
BTN_LEFT, BTN_RIGHT = 0x110, 0x111
REL_X, REL_Y, REL_WHEEL = 0x00, 0x01, 0x08
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT, UI_DEV_SETUP = 0x40045564, 0x40045565, 0x40045566, 0x405C5503
BUS_VIRTUAL = 0x06


class UInputDevice:
    """Создаётся один раз при запуске: новому устройству композитору нужно время, чтобы его подхватить."""

    def __init__(self, name: str, keys: tuple[int, ...] = (), rels: tuple[int, ...] = ()):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        try:
            if keys:
                fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
                for key in keys:
                    fcntl.ioctl(self.fd, UI_SET_KEYBIT, key)
            if rels:
                fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_REL)
                for rel in rels:
                    fcntl.ioctl(self.fd, UI_SET_RELBIT, rel)
            setup = struct.pack("HHHH80sI", BUS_VIRTUAL, 0x1209, 0x7670, 1, name.encode(), 0)
            fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except OSError:
            os.close(self.fd)
            raise

    def _emit(self, ev_type: int, code: int, value: int) -> None:
        os.write(self.fd, struct.pack("llHHi", 0, 0, ev_type, code, value))

    def tap(self, keys: list[int]) -> None:
        """Нажать сочетание: все клавиши по порядку, отпустить в обратном."""
        for key in keys:
            self._emit(EV_KEY, key, 1)
            self._emit(EV_SYN, SYN_REPORT, 0)
            time.sleep(0.02)
        for key in reversed(keys):
            self._emit(EV_KEY, key, 0)
            self._emit(EV_SYN, SYN_REPORT, 0)
            time.sleep(0.02)

    def scroll(self, notches: int) -> None:
        """Колёсико: плюс — вверх, минус — вниз. По одному щелчку, чтобы прокрутка шла плавно.
        Прокручивается окно под курсором мыши, а не активное."""
        step = 1 if notches > 0 else -1
        for _ in range(abs(notches)):
            self._emit(EV_REL, REL_WHEEL, step)
            self._emit(EV_SYN, SYN_REPORT, 0)
            time.sleep(0.015)

    def close(self) -> None:
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        finally:
            os.close(self.fd)
