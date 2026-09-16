from pathlib import Path

from voice_player.local_playback import play_local_file
from voice_player.players import Players


def test_play_local_file_launches_mpv_and_registers_player(monkeypatch):
    calls = []
    monkeypatch.setattr("voice_player.local_playback.run_quiet", lambda cmd: calls.append(cmd))
    players = Players()

    play_local_file(Path("/tmp/track.mp3"), players, "трек", notify_on=False)

    assert calls == [["mpv", "--no-video", "/tmp/track.mp3"]]
    assert players.named == "mpv"


def test_play_local_file_notifies_when_enabled(monkeypatch):
    monkeypatch.setattr("voice_player.local_playback.run_quiet", lambda cmd: None)
    notified = []
    monkeypatch.setattr("voice_player.local_playback.notify", lambda text: notified.append(text))

    play_local_file(Path("/tmp/track.mp3"), Players(), "название трека", notify_on=True)

    assert notified == ["название трека"]


def test_play_local_file_silent_when_notify_disabled(monkeypatch):
    monkeypatch.setattr("voice_player.local_playback.run_quiet", lambda cmd: None)
    notified = []
    monkeypatch.setattr("voice_player.local_playback.notify", lambda text: notified.append(text))

    play_local_file(Path("/tmp/track.mp3"), Players(), "название трека", notify_on=False)

    assert notified == []
