"""Пути, константы и подстраиваемые параметры. Ничего не исполняет."""

from pathlib import Path

SAMPLE_RATE = 16000
CHUNK_MS = 50

DATA_DIR = Path.home() / ".local/share/voice-player"
CONFIG_DIR = Path.home() / ".config/voice-player"
DEFAULT_MODEL = DATA_DIR / "model"
DEFAULT_NAMES = CONFIG_DIR / "names.txt"
DEFAULT_WINDOWS = CONFIG_DIR / "windows.txt"
DEFAULT_SINKS = CONFIG_DIR / "sinks.txt"

SCROLL_NOTCHES = 5  # щелчков колеса за команду, в большинстве программ это ~15 строк
SINK_WORD = "звук"  # «звук наушники», «звук монитор»
SEND_WINDOW_SEC = 120  # «отправь» работает столько секунд после «напиши» и только в том же окне

BROWSER_PATTERN = "chrom|firefox"  # куда открываются ссылки из запросов
TERMINAL_PATTERN = r"konsole|yakuake|kitty|alacritty|wezterm|foot|ghostty|terminal"
# Главное окно Telegram. В нём Ctrl+Enter может отправить сообщение, поэтому туда не жмём:
# полный экран есть только у просмотрщика видео (его заголовок переводится, поэтому исключаем главное).
TELEGRAM_MAIN_CAPTION = r"^Telegram(?: \(\d+\))?$"

# после срабатывания: игнорировать хвост слова, затем сбросить распознаватель
MUTE_SEC = 0.35

ASK_WORD = "джарвис"
ASK_VERBS = ["включи", "поставь", "найди", "открой", "покажи", "запусти"]
# поиск в Google: «загугли ...». Самого «загугли» модель не знает и обычно слышит его как «гугл».
SEARCH_WORDS = ["погугли", "гугл", "поищи"]
# голосовой ввод: «напиши ...» вставляет текст в активное окно, «отправь» жмёт Enter
DICTATE_WORDS = ["напиши", "набери", "введи"]
DICTATE_MAX_SEC = 20.0
ASK_MIN_SEC = 1.5  # раньше не останавливать запись, даже если пауза
ASK_MAX_SEC = 8.0
PREROLL_SEC = 1.5  # сколько звука до срабатывания отдать Whisper
