"""voice-player-telegram-sync: разово скачивает канал Mr. Kitty и обновляет tracks.txt.

Интерактивный (первый запуск Pyrogram спрашивает телефон/код/2FA) — поэтому отдельный
скрипт, а не часть voice-player, который обычно живёт под systemd без терминала.
"""

import logging
import re
import sys
from pathlib import Path

from ..commands import load_mapping
from ..config import (
    DEFAULT_MODEL,
    TELEGRAM_CONFIG,
    TELEGRAM_TRACKS,
    TELEGRAM_TRACKS_DIR,
)
from ..logging_setup import configure as configure_logging
from .client import make_client
from .settings import TelegramSettings, load_settings

logger = logging.getLogger(__name__)

_NON_WORD_RE = re.compile(r"[^a-zа-яё0-9]+", re.I)


def slugify_title(title: str) -> str:
    """«Bloodlust (Remix)» -> «bloodlust remix» — черновой вариант голосового слова.

    Для англоязычных названий модель Vosk почти наверняка не будет знать такое слово —
    это ожидаемо, см. предупреждения known_words() после синка и итог в _check_vocabulary().
    Неподошедшие слова правятся в tracks.txt руками, как сейчас правятся windows.txt/sinks.txt.
    """
    return " ".join(_NON_WORD_RE.sub(" ", title.strip().lower()).split())


def should_skip_title(title: str, pattern: str) -> bool:
    """pattern пустой -> ничего не пропускаем; иначе регулярка без учёта регистра."""
    return bool(pattern) and re.search(pattern, title, re.I) is not None


def merge_tracks(existing: dict[str, str], new_entries: dict[str, str]) -> dict[str, str]:
    """Добавляет новые слова, никогда не трогает уже существующие (пользователь мог их поправить)."""
    merged = dict(existing)
    for word, path in new_entries.items():
        if word not in merged:
            merged[word] = path
    return merged


def write_tracks(path: Path, tracks: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{word} = {track_path}" for word, track_path in sorted(tracks.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sync(settings: TelegramSettings) -> None:
    TELEGRAM_TRACKS_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_mapping(TELEGRAM_TRACKS, {})
    new_entries: dict[str, str] = {}

    app = make_client(settings)
    skipped = 0
    with app:
        for message in app.get_chat_history(settings.mr_kitty_channel):
            if not message.audio:
                continue
            title = message.audio.title or message.audio.file_name or f"track-{message.id}"
            if should_skip_title(title, settings.skip_titles_matching):
                skipped += 1
                continue
            slug = _NON_WORD_RE.sub("_", title.lower()).strip("_")
            dest = TELEGRAM_TRACKS_DIR / f"{message.id}-{slug}.mp3"
            if dest.exists():
                continue
            logger.info("скачиваю: %s", title)
            app.download_media(message, file_name=str(dest))
            word = slugify_title(title)
            if word:
                new_entries[word] = str(dest)

    merged = merge_tracks(existing, new_entries)
    write_tracks(TELEGRAM_TRACKS, merged)
    logger.info(
        "готово: %s треков в %s (%s новых, %s пропущено фильтром)",
        len(merged), TELEGRAM_TRACKS, len(new_entries), skipped,
    )


def _check_vocabulary() -> None:
    """Сколько слов из tracks.txt модель Vosk реально знает — остальные надо поправить руками."""
    if not DEFAULT_MODEL.is_dir():
        return
    from vosk import Model, SetLogLevel

    from ..grammar import known_words

    SetLogLevel(-1)
    model = Model(str(DEFAULT_MODEL))
    words = list(load_mapping(TELEGRAM_TRACKS, {}))
    ok = known_words(model, words)
    logger.info("модель знает %s слов из %s — остальные стоит поправить в %s", len(ok), len(words), TELEGRAM_TRACKS)


def main() -> None:
    configure_logging(verbose=True)
    settings = load_settings()
    if settings is None:
        sys.exit(f"заполни {TELEGRAM_CONFIG} и запусти снова")
    sync(settings)
    _check_vocabulary()


if __name__ == "__main__":
    main()
