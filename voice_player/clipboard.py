"""Буфер обмена KDE (Klipper живёт в plasmashell); busctl есть везде, где есть systemd."""

import json
import subprocess

KLIPPER = ["busctl", "--user", "--json=short", "call", "org.kde.klipper", "/klipper", "org.kde.klipper.klipper"]


def clipboard_get() -> str | None:
    try:
        out = subprocess.run(KLIPPER + ["getClipboardContents"], capture_output=True, text=True, timeout=2)
        return json.loads(out.stdout)["data"][0] if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError):
        return None


def clipboard_set(text: str) -> bool:
    try:
        return subprocess.run(
            KLIPPER + ["setClipboardContents", "s", text],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
