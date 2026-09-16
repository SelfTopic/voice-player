"""Аудиовыход (pactl sinks) и захват микрофона."""

import logging
import re
import shutil
import subprocess
import sys

from .config import CHUNK_MS, SAMPLE_RATE
from .notify import notify

logger = logging.getLogger(__name__)


def switch_sink(pattern: str, label: str, notify_on: bool) -> None:
    """Сделать устройство выводом по умолчанию и перенести на него всё, что уже играет."""
    def pactl(*args: str) -> str:
        return subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=2).stdout

    try:
        rx = re.compile(pattern, re.I)
        # формат: id<TAB>имя<TAB>драйвер<TAB>формат<TAB>состояние
        names = [line.split("\t")[1] for line in pactl("list", "short", "sinks").splitlines() if "\t" in line]
        name = next((n for n in names if rx.search(n)), None)
        if name is None:
            message = f"нет устройства «{label}»"
        else:
            pactl("set-default-sink", name)
            for line in pactl("list", "short", "sink-inputs").splitlines():
                stream = line.split("\t")[0]
                if stream.isdigit():
                    pactl("move-sink-input", stream, name)
            message = f"звук: {label}"
    except (OSError, subprocess.SubprocessError, re.error) as e:
        message = f"не удалось переключить звук: {e}"
    logger.info(message)
    if notify_on:
        notify(message)


def mic_process(device: str | None) -> subprocess.Popen:
    if shutil.which("parec"):
        cmd = [
            "parec", "--raw", "--format=s16le", f"--rate={SAMPLE_RATE}", "--channels=1",
            f"--latency-msec={CHUNK_MS // 2}",
        ]
        if device:
            cmd.append(f"--device={device}")
    elif shutil.which("pw-record"):
        cmd = ["pw-record", "--rate", str(SAMPLE_RATE), "--channels", "1", "--format", "s16"]
        if device:
            cmd += ["--target", device]
        cmd.append("-")
    else:
        sys.exit("нужен parec (libpulse) или pw-record (pipewire)")
    return subprocess.Popen(cmd, stdout=subprocess.PIPE)
