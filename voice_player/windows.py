"""Управление окнами KDE через kdotool/kwin-скрипты: фокус, переключение, полный экран."""

import json
import logging
import re
import shutil
import subprocess
import time

from .config import DATA_DIR, TELEGRAM_MAIN_CAPTION
from .notify import notify
from .players import Players
from .uinput import KEY_ENTER, KEY_ESC, KEY_F, KEY_LEFTCTRL, UInputDevice

logger = logging.getLogger(__name__)

# Полный экран: у Chrome и Telegram в MPRIS такого нет, поэтому нажимаем клавиши.
# YouTube: F — развернуть, Esc — выйти. Просмотрщик видео Telegram: Ctrl+Enter — переключить.
# KWin-скрипт выбирает окно (активное, если подходит, иначе верхнее подходящее), даёт ему фокус
# и сообщает «класс<TAB>1/0<TAB>заголовок». Окна с заголовком __EXCLUDE__ пропускаются.
FULLSCREEN_JS = """
var pattern = __PATTERN__;
var exclude = __EXCLUDE__;
var re = pattern ? new RegExp(pattern, "i") : null;
var ex = exclude ? new RegExp(exclude) : null;
function cls(w) { return (w.resourceClass || "") + " " + (w.resourceName || ""); }
function fits(w) { return re.test(cls(w)) && !(ex && ex.test(w.caption || "")); }
var active = workspace.activeWindow;
var target = null;
if (!re || (active && fits(active))) {
  target = active;
} else {
  var stack = (workspace.stackingOrder || workspace.windowList()).filter(function (w) {
    return w.normalWindow && fits(w);
  });
  target = stack.length ? stack[stack.length - 1] : null;
}
if (!target) {
  output_error("нет окна");
} else {
  if (target !== active) {
    target.minimized = false;
    workspace.activeWindow = target;
  }
  output_result(cls(target) + "\\t" + (target.fullScreen ? "1" : "0") + "\\t" + (target.caption || ""));
}
"""

# KWin-скрипт: переключиться на окно по классу; если оно уже активно — на следующее такое же
WINDOW_JS = """
var re = new RegExp(__PATTERN__, "i");
function matches(w) {
  return w.normalWindow && !w.skipTaskbar && re.test((w.resourceClass || "") + " " + (w.resourceName || ""));
}
function same(a, b) { return !!a && !!b && String(a.internalId) === String(b.internalId); }
var all = workspace.windowList().filter(matches);
if (all.length === 0) {
  output_error("нет окна");
} else {
  var active = workspace.activeWindow;
  var i = -1;
  for (var k = 0; k < all.length; k++) { if (same(all[k], active)) { i = k; } }
  var target;
  if (i >= 0) {
    target = all[(i + 1) % all.length];
  } else {
    var stack = (workspace.stackingOrder || all).filter(matches);
    target = stack.length ? stack[stack.length - 1] : all[0];
  }
  target.minimized = false;
  workspace.activeWindow = target;
  output_result(target.caption);
}
"""

# если windows.txt нет: слово -> регулярка по классу окна
WINDOWS_FALLBACK = {
    "терминал": "konsole|kitty|alacritty|wezterm|foot|ghostty|terminal",
    "браузер": "chrome|chromium",
    "ютуб": "chrome|chromium",
    "редактор": "^code|codium",
    "телеграм": "telegram",
}


def find_kdotool() -> str | None:
    local = DATA_DIR / "bin/kdotool"
    return str(local) if local.is_file() else shutil.which("kdotool")


def focus_window(kdotool: str, pattern: str, exclude: str = "") -> tuple[str, str, str]:
    """Дать фокус окну по классу (см. FULLSCREEN_JS) -> (класс, "1"/"0" — полноэкранное, заголовок).
    Если окна нет — пустые строки."""
    script = FULLSCREEN_JS.replace("__PATTERN__", json.dumps(pattern)).replace("__EXCLUDE__", json.dumps(exclude))
    try:
        out = subprocess.run(
            [kdotool, "kwinscript", "--inline", script], capture_output=True, text=True, timeout=3,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = ""
    parts = (out.splitlines()[-1] if out else "").split("\t", 2)
    return (parts[0], parts[1], parts[2]) if len(parts) == 3 else ("", "", "")


def window_command(kdotool: str, pattern: str) -> list[str]:
    return [kdotool, "kwinscript", "--inline", WINDOW_JS.replace("__PATTERN__", json.dumps(pattern))]


def app_of(name: str) -> str | None:
    name = name.lower()
    if "chrom" in name:
        return "chrome"
    if "telegram" in name:
        return "telegram"
    return None


def toggle_fullscreen(kdotool: str, keyboard: UInputDevice, players: Players, notify_on: bool) -> None:
    # окно того, что играет (или названо последним); если не знаем — активное окно
    sent, _ = players.targets("next")
    app = app_of(sent[0]) if sent else None
    pattern = {"chrome": "chrom", "telegram": "telegram"}.get(app, "")
    exclude = TELEGRAM_MAIN_CAPTION if app == "telegram" else ""
    window_class, fullscreen, caption = focus_window(kdotool, pattern, exclude)
    app = app or app_of(window_class)
    state = {"1": "полноэкранное", "0": "обычное"}.get(fullscreen, "?")
    logger.debug("полный экран: окно «%s», сейчас %s", caption or window_class or "?", state)

    def refuse(message: str) -> None:
        logger.warning(message)
        if notify_on:
            notify(message)

    if app == "chrome" and window_class:
        keys = [KEY_ESC] if fullscreen == "1" else [KEY_F]
    elif app == "telegram":
        if not window_class or re.match(TELEGRAM_MAIN_CAPTION, caption):
            refuse("открой видео в Telegram: в главном окне полного экрана нет")
            return
        keys = [KEY_LEFTCTRL, KEY_ENTER]
    else:
        refuse("не знаю, как развернуть это окно")
        return
    time.sleep(0.15)  # дать окну получить фокус
    keyboard.tap(keys)
