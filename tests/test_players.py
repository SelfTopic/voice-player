"""players.py дёргает playerctl через subprocess — здесь он подменяется, тестируется только выбор цели."""

import logging
import time

from voice_player.players import Players


def _patch_all_players(monkeypatch, players_status):
    monkeypatch.setattr(Players, "all_players", staticmethod(lambda: players_status))


def _patch_playerctl(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "voice_player.players.playerctl",
        lambda instance, *action: calls.append((instance, action)) or True,
    )
    return calls


class TestTargetsNext:
    def test_playing_wins_over_named(self, monkeypatch):
        _patch_all_players(monkeypatch, [("vlc", "Playing"), ("telegram", "Paused")])
        players = Players()
        players.name("telegram")
        target, to_pause = players.targets("next")
        assert target == ["vlc"]
        assert to_pause == []

    def test_named_used_when_nothing_playing(self, monkeypatch):
        _patch_all_players(monkeypatch, [("vlc", "Paused"), ("telegram", "Paused")])
        players = Players()
        players.name("telegram")
        target, _ = players.targets("next")
        assert target == ["telegram"]

    def test_playerctld_fallback_when_nothing_known(self, monkeypatch):
        _patch_all_players(monkeypatch, [])
        players = Players()
        target, _ = players.targets("next")
        assert target == ["playerctld"]


class TestTargetsPlay:
    def test_resumes_paused_players(self, monkeypatch):
        _patch_all_players(monkeypatch, [("vlc", "Paused"), ("telegram", "Paused")])
        players = Players()
        players.paused, players.paused_at = ["vlc", "telegram"], time.monotonic()
        target, to_pause = players.targets("play")
        assert target == ["vlc", "telegram"]
        assert to_pause == []

    def test_newer_named_wins_over_older_pause(self, monkeypatch):
        _patch_all_players(monkeypatch, [("vlc", "Paused"), ("chrome", "Paused")])
        players = Players()
        players.paused, players.paused_at = ["vlc"], time.monotonic()
        players.name("chrome")  # назван уже после того, как «vlc» поставили на паузу
        target, _ = players.targets("play")
        assert target == ["chrome"]

    def test_older_named_loses_to_newer_pause(self, monkeypatch):
        _patch_all_players(monkeypatch, [("vlc", "Paused"), ("chrome", "Paused")])
        players = Players()
        players.name("chrome")
        players.paused, players.paused_at = ["vlc"], time.monotonic()  # пауза случилась позже
        target, _ = players.targets("play")
        assert target == ["vlc"]

    def test_falls_back_to_currently_playing_when_nothing_named_or_paused(self, monkeypatch):
        _patch_all_players(monkeypatch, [("vlc", "Playing")])
        players = Players()
        target, _ = players.targets("play")
        assert target == ["vlc"]


def test_pause_playing_records_paused_players(monkeypatch):
    _patch_all_players(monkeypatch, [("vlc", "Playing"), ("telegram", "Paused")])
    calls = _patch_playerctl(monkeypatch)
    players = Players()
    paused = players.pause_playing()
    assert paused == ["vlc"]
    assert players.paused == ["vlc"]
    assert calls == [("vlc", ("pause",))]


def test_run_pause_sends_pause_to_every_playing_instance(monkeypatch, caplog):
    _patch_all_players(monkeypatch, [("vlc", "Playing"), ("chrome", "Playing")])
    calls = _patch_playerctl(monkeypatch)
    players = Players()
    with caplog.at_level(logging.DEBUG, logger="voice_player.players"):
        players.run(["pause"], "пауза", notify_on=False)
    assert sorted(calls) == [("chrome", ("pause",)), ("vlc", ("pause",))]
    assert "vlc" in caplog.text
