"""Основной цикл: чтение микрофона, быстрые команды и передача записи в Asker."""

import json
import logging
import threading
import time
from collections import deque
from pathlib import Path

from .asker import Asker
from .audio import switch_sink
from .commands import COMMANDS, FULLSCREEN, PLAY_TRACK, PLAYER, SCROLL, SEND, SINK
from .config import (
    ASK_MAX_SEC,
    ASK_MIN_SEC,
    CHUNK_MS,
    DICTATE_MAX_SEC,
    MUTE_SEC,
    PREROLL_SEC,
    SAMPLE_RATE,
)
from .dictation import Dictation, send_enter
from .grammar import (
    ASK,
    ASK_YOUTUBE,
    DICTATE,
    GOOGLE,
    ask_mode,
    command_at_end,
    parse_command,
)
from .local_playback import LocalPlayer
from .notify import notify, run_quiet
from .players import Players
from .uinput import UInputDevice
from .windows import toggle_fullscreen

logger = logging.getLogger(__name__)


class VoiceLoop:
    """Состояние распознавания живёт в атрибутах экземпляра, а не в nonlocal-переменных
    замыканий: каждый шаг — отдельный метод, который можно читать и менять независимо."""

    def __init__(
        self, *, mic, rec, free, players: Players, dictation: Dictation, asker: Asker | None,
        local_player: LocalPlayer, kdotool: str | None, keyboard: UInputDevice | None,
        mouse: UInputDevice | None, window_patterns: dict[str, str], wake: str | None,
        stable: int, min_conf: float, notify_on: bool,
    ):
        self.mic = mic
        self.rec = rec
        self.free = free  # только чтобы понять, что фраза закончилась; None, если нет asker
        self.players = players
        self.dictation = dictation
        self.asker = asker
        self.local_player = local_player
        self.kdotool = kdotool
        self.keyboard = keyboard
        self.mouse = mouse
        self.window_patterns = window_patterns
        self.wake = wake
        self.stable = stable
        self.min_conf = min_conf
        self.notify_on = notify_on

        self.chunk_bytes = SAMPLE_RATE * 2 * CHUNK_MS // 1000
        self.preroll: deque[bytes] = deque(maxlen=int(PREROLL_SEC * 1000 / CHUNK_MS))
        self.candidate: str | None = None
        self.streak = 0
        self.mute_until = 0.0
        self.need_reset = False
        self.recording: list[bytes] | None = None
        self.rec_chunks = 0
        self.paused_for_ask: list[str] = []
        self.ask_kind = ASK
        self.job: threading.Thread | None = None

    def run(self) -> None:
        try:
            while chunk := self.mic.stdout.read(self.chunk_bytes):
                self._step(chunk)
        except KeyboardInterrupt:
            pass
        finally:
            self.mic.terminate()
            for device in (self.keyboard, self.mouse):
                if device:
                    device.close()

    def _step(self, chunk: bytes) -> None:
        self.preroll.append(chunk)

        if self.job is not None:
            if self.job.is_alive():
                return
            self.job = None
            self.rec.Reset()
            return

        if self.recording is not None:
            self._continue_recording(chunk)
            return

        self._listen(chunk)

    def _continue_recording(self, chunk: bytes) -> None:
        self.recording.append(chunk)
        self.rec_chunks += 1
        ended = self.free.AcceptWaveform(chunk)
        duration = self.rec_chunks * CHUNK_MS / 1000
        max_sec = DICTATE_MAX_SEC if self.ask_kind == DICTATE else ASK_MAX_SEC
        if (ended and duration >= ASK_MIN_SEC) or duration >= max_sec:
            audio, self.recording = b"".join(self.recording), None
            self.job = threading.Thread(
                target=self.asker.handle, args=(audio, self.paused_for_ask, self.ask_kind), daemon=True,
            )
            self.job.start()

    def _listen(self, chunk: bytes) -> None:
        is_final = self.rec.AcceptWaveform(chunk)
        now = time.monotonic()
        if now < self.mute_until:
            return
        if self.need_reset:
            self.rec.Reset()
            self.need_reset = False
            return

        if is_final:
            self._on_final(now)
        elif self.stable > 0:
            self._on_partial(now)

    def _on_final(self, now: float) -> None:
        self.candidate, self.streak = None, 0
        res = json.loads(self.rec.Result())
        text = res.get("text", "")
        if not text:
            return
        conf = min((w.get("conf", 0.0) for w in res.get("result", [])), default=0.0)
        logger.debug("слышу: «%s» (conf %.2f)", text, conf)
        mode = ask_mode(text) if self.asker else None
        if mode:
            self._start_ask(mode)
            return
        cmd = parse_command(text, self.wake)
        if cmd and conf >= self.min_conf:
            self._fire(cmd, now, "конец фразы")

    def _on_partial(self, now: float) -> None:
        partial = json.loads(self.rec.PartialResult()).get("partial", "")
        cmd = command_at_end(partial, self.wake, self.asker is not None)
        if cmd and cmd == self.candidate:
            self.streak += 1
        else:
            self.candidate, self.streak = cmd, 1 if cmd else 0
        if cmd and self.streak >= self.stable:
            if cmd in (ASK, ASK_YOUTUBE, GOOGLE, DICTATE):
                self._start_ask(cmd)
            else:
                self._fire(cmd, now, "быстро")

    def _start_ask(self, mode: str) -> None:
        if mode == DICTATE and not self.keyboard:
            return  # вставлять текст нечем; обычно сюда и не попасть — слова нет в грамматике
        self.ask_kind = mode
        self.paused_for_ask = self.players.pause_playing()  # чтобы видео не мешало расслышать запрос
        logger.info("🎙 слушаю запрос…")
        if self.notify_on:
            notify("🎙 слушаю…")
        self.recording, self.rec_chunks = list(self.preroll), 0
        self.free.Reset()
        self.candidate, self.streak = None, 0

    def _fire(self, cmd: str, now: float, how: str) -> None:
        logger.info("→ %s", cmd)
        logger.debug("сработало по: %s", how)
        argv = COMMANDS[cmd]
        if argv[0] == PLAYER:
            # в потоке: опрос плееров занимает десятки миллисекунд, микрофон ждать не должен
            threading.Thread(target=self.players.run, args=(argv[1:], cmd, self.notify_on), daemon=True).start()
        elif argv[0] == SEND:
            threading.Thread(
                target=send_enter, args=(self.kdotool, self.keyboard, self.dictation, self.notify_on), daemon=True,
            ).start()
        elif argv[0] == SINK:
            threading.Thread(target=switch_sink, args=(argv[1], argv[2], self.notify_on), daemon=True).start()
        elif argv[0] == SCROLL:
            threading.Thread(target=self.mouse.scroll, args=(int(argv[1]),), daemon=True).start()
        elif argv[0] == PLAY_TRACK:
            threading.Thread(
                target=self.local_player.play, args=(Path(argv[1]), self.players, cmd, self.notify_on), daemon=True,
            ).start()
        elif argv[0] == FULLSCREEN:
            threading.Thread(
                target=toggle_fullscreen,
                args=(self.kdotool, self.keyboard, self.players, self.notify_on),
                daemon=True,
            ).start()
        else:
            run_quiet(argv)
            if cmd in self.window_patterns:
                self.players.name(self.window_patterns[cmd])
            elif self.notify_on:
                notify(cmd)
        self.mute_until = now + MUTE_SEC
        self.need_reset = True
        self.candidate, self.streak = None, 0
