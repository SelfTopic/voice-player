"""Маршрутизация ASK/ASK_YOUTUBE в Asker — без реального Whisper/yt-dlp/Pyrogram.

Asker.__init__ грузит Whisper и лениво импортирует numpy/yt_dlp, поэтому тестируемый
экземпляр собирается в обход __init__ (Asker.__new__), а self.transcribe/self.search
подменяются напрямую — тестируется только маршрутизация (Telegram -> YouTube-фоллбэк),
а не сама транскрипция/поиск.
"""

from pathlib import Path

from voice_player.asker import Asker
from voice_player.config import BROWSER_PATTERN
from voice_player.grammar import ASK
from voice_player.players import Players


class FakeTelegram:
    def __init__(self, track: Path | None):
        self.track = track
        self.queries: list[str] = []

    def find_track(self, query: str) -> Path | None:
        self.queries.append(query)
        return self.track


def _make_asker(players: Players, telegram=None) -> Asker:
    asker = Asker.__new__(Asker)
    asker.players = players
    asker.kdotool = None
    asker.keyboard = None
    asker.dictation = None
    asker.notify_on = False
    asker.telegram = telegram
    return asker


def test_play_from_telegram_found(monkeypatch):
    played = []
    monkeypatch.setattr(
        "voice_player.asker.play_local_file",
        lambda path, players, label, notify_on: played.append((path, label)),
    )
    telegram = FakeTelegram(Path("/tmp/track.mp3"))
    asker = _make_asker(Players(), telegram=telegram)

    assert asker._play_from_telegram("bloodlust") is True
    assert telegram.queries == ["bloodlust"]
    assert played == [(Path("/tmp/track.mp3"), "bloodlust")]


def test_play_from_telegram_not_found():
    telegram = FakeTelegram(None)
    asker = _make_asker(Players(), telegram=telegram)

    assert asker._play_from_telegram("неизвестная песня") is False
    assert telegram.queries == ["неизвестная песня"]


def test_search_youtube_found(monkeypatch):
    asker = _make_asker(Players())
    asker.search = lambda query: {"id": "abc123", "title": "Some Video"}
    monkeypatch.setattr("voice_player.asker.replace_youtube_tab", lambda kdotool, keyboard, url: False)
    opened = []
    monkeypatch.setattr("voice_player.asker.run_quiet", lambda cmd: opened.append(cmd))

    assert asker._search_youtube("some query") is True
    assert opened == [["xdg-open", "https://www.youtube.com/watch?v=abc123"]]
    assert asker.players.named == BROWSER_PATTERN


def test_search_youtube_not_found():
    asker = _make_asker(Players())
    asker.search = lambda query: None

    assert asker._search_youtube("nothing") is False


def test_handle_ask_falls_back_to_youtube_when_telegram_finds_nothing(monkeypatch):
    telegram = FakeTelegram(None)
    asker = _make_asker(Players(), telegram=telegram)
    asker.transcribe = lambda audio, mode: "джарвис включи неизвестную песню"
    asker.search = lambda query: {"id": "xyz", "title": "Found On YouTube"}
    monkeypatch.setattr("voice_player.asker.replace_youtube_tab", lambda *a: False)
    monkeypatch.setattr("voice_player.asker.playerctl", lambda *a: True)
    opened = []
    monkeypatch.setattr("voice_player.asker.run_quiet", lambda cmd: opened.append(cmd))

    asker.handle(b"", paused=[], mode=ASK)

    assert telegram.queries  # телеграм спросили первым
    assert opened == [["xdg-open", "https://www.youtube.com/watch?v=xyz"]]


def test_handle_ask_goes_straight_to_youtube_when_telegram_not_configured(monkeypatch):
    asker = _make_asker(Players(), telegram=None)
    asker.transcribe = lambda audio, mode: "джарвис включи что-нибудь"
    asker.search = lambda query: {"id": "id1", "title": "T"}
    monkeypatch.setattr("voice_player.asker.replace_youtube_tab", lambda *a: False)
    monkeypatch.setattr("voice_player.asker.playerctl", lambda *a: True)
    opened = []
    monkeypatch.setattr("voice_player.asker.run_quiet", lambda cmd: opened.append(cmd))

    asker.handle(b"", paused=[], mode=ASK)

    assert opened == [["xdg-open", "https://www.youtube.com/watch?v=id1"]]
