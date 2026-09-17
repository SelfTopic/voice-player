"""voice-player-check-word: быстро проверить, знает ли модель Vosk слово/фразу.

Модель грузится один раз и держится открытой — подбирать кириллические замены для
tracks.txt (или windows.txt/sinks.txt) так быстрее, чем перезапускать voice-player на
каждый вариант. Слова/фразы читаются построчно из stdin, можно и интерактивно, можно
файлом: `voice-player-check-word < candidates.txt`.
"""

import sys

from .config import DEFAULT_MODEL
from .grammar import known_words
from .logging_setup import configure as configure_logging


def check_phrase(model, phrase: str) -> bool:
    """Знает ли модель все слова фразы целиком."""
    return bool(known_words(model, [phrase]))


def main() -> None:
    configure_logging(verbose=False)
    if not DEFAULT_MODEL.is_dir():
        sys.exit(f"модель не найдена: {DEFAULT_MODEL} (запусти install.sh)")

    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    print(f"загружаю модель из {DEFAULT_MODEL}…", file=sys.stderr)
    model = Model(str(DEFAULT_MODEL))
    print("готово. вводи слово/фразу построчно (Ctrl+D — выход).", file=sys.stderr)

    for line in sys.stdin:
        phrase = line.strip().lower()
        if not phrase:
            continue
        print(("✓" if check_phrase(model, phrase) else "✗"), phrase)


if __name__ == "__main__":
    main()
