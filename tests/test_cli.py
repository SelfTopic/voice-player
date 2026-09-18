"""register_telegram_track_commands: слова из tracks.txt должны получать префикс TRACK_WORD
и числительные — попадать в SLOW_ONLY (иначе быстрый путь стреляет по префиксу вроде «сто»
раньше, чем модель договорит «сто сорок», см. tests/test_grammar.py)."""

import argparse
from contextlib import contextmanager

from voice_player.cli import register_telegram_track_commands
from voice_player.commands import COMMANDS, PLAY_TRACK, SLOW_ONLY
from voice_player.config import TRACK_WORD


@contextmanager
def _registered(tmp_path, content: str):
    """Прогоняет register_telegram_track_commands на временном tracks.txt и откатывает
    все добавленные в COMMANDS/SLOW_ONLY записи после теста."""
    path = tmp_path / "tracks.txt"
    path.write_text(content, encoding="utf-8")
    before = set(COMMANDS)
    register_telegram_track_commands(argparse.Namespace(tracks=path))
    added = [phrase for phrase in COMMANDS if phrase not in before]
    try:
        yield added
    finally:
        for phrase in added:
            del COMMANDS[phrase]
            SLOW_ONLY.discard(phrase)


def test_word_gets_track_prefix(tmp_path):
    with _registered(tmp_path, "вейл = /a/veil.mp3\n") as added:
        assert added == [f"{TRACK_WORD} вейл"]
        assert COMMANDS[f"{TRACK_WORD} вейл"] == [PLAY_TRACK, "/a/veil.mp3"]


def test_number_phrase_is_marked_slow_only(tmp_path):
    with _registered(tmp_path, "сто сорок = /a/track140.mp3\n"):
        assert f"{TRACK_WORD} сто сорок" in SLOW_ONLY


def test_word_phrase_is_not_marked_slow_only(tmp_path):
    with _registered(tmp_path, "вейл = /a/veil.mp3\n"):
        assert f"{TRACK_WORD} вейл" not in SLOW_ONLY


def test_collision_with_existing_command_is_skipped(tmp_path):
    phrase = f"{TRACK_WORD} уже-занято"
    COMMANDS[phrase] = ["__existing__"]
    try:
        with _registered(tmp_path, "уже-занято = /a/x.mp3\n") as added:
            assert added == []  # ничего нового не добавилось
            assert COMMANDS[phrase] == ["__existing__"]  # существующая команда не тронута
    finally:
        del COMMANDS[phrase]
