"""Кэш «что просили голосом» -> «какой файл в итоге проигрался».

Whisper транскрибирует одну и ту же произнесённую фразу чуть по-разному от раза к разу —
одна другая буква, и бот присылает уже другой результат (скажем, ремикс вместо оригинала).
Нечёткое сравнение нового запроса с уже виденными раньше избавляет от повторного похода в
Telegram за тем, что уже один раз нашлось и лежит на диске.

Сознательно ищет только "почти то же самое" (высокий порог схожести целой строки), а не
пытается понять, что "Иванов песня" и "Иванов песня концерт 2018" — один и тот же трек:
это была бы уже отдельная, менее надёжная эвристика с риском подсунуть не то, что просили.
"""

import json
import logging
from difflib import SequenceMatcher
from pathlib import Path

from ..config import TELEGRAM_DATA_DIR

logger = logging.getLogger(__name__)

QUERY_CACHE = TELEGRAM_DATA_DIR / "query_cache.json"
SIMILARITY_THRESHOLD = 0.85  # эмпирически: пара опечаток/букв на длинной фразе всё ещё проходит


def normalize(query: str) -> str:
    return " ".join(query.strip().lower().split())


def load_query_cache() -> dict[str, str]:
    if not QUERY_CACHE.is_file():
        return {}
    try:
        return json.loads(QUERY_CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("%s повреждён, начинаю кэш запросов заново", QUERY_CACHE.name)
        return {}


def remember_query(query: str, path: str) -> None:
    cache = load_query_cache()
    cache[normalize(query)] = path
    QUERY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    QUERY_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def find_similar(query: str, threshold: float = SIMILARITY_THRESHOLD) -> str | None:
    """Похожий уже виденный запрос -> путь к файлу (если он ещё существует на диске), иначе None."""
    normalized = normalize(query)
    best_path, best_ratio = None, 0.0
    for cached_query, path in load_query_cache().items():
        ratio = SequenceMatcher(None, normalized, cached_query).ratio()
        if ratio > best_ratio:
            best_ratio, best_path = ratio, path
    if best_path and best_ratio >= threshold and Path(best_path).is_file():
        return best_path
    return None
