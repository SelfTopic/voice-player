"""Настройка логирования на весь пакет: обычный статус — в stdout, предупреждения — в stderr.

Модули просто берут `logging.getLogger(__name__)` и не думают о `-v` — фильтрацию
по уровню и форматирование делает эта настройка один раз при старте.
"""

import logging
import sys

_FORMATS = {
    logging.DEBUG: "  %(message)s",  # детали, видны только с --verbose
    logging.WARNING: "! %(message)s",
    logging.ERROR: "! %(message)s",
    logging.CRITICAL: "! %(message)s",
}
_DEFAULT_FORMAT = "%(message)s"  # INFO и всё остальное


class _LevelFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        self._style._fmt = _FORMATS.get(record.levelno, _DEFAULT_FORMAT)
        return super().format(record)


def configure(verbose: bool) -> None:
    logger = logging.getLogger("voice_player")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = _LevelFormatter()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)
