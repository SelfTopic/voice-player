import subprocess
from pathlib import Path

from voice_player.local_playback import LocalPlayer
from voice_player.players import Players


class FakeProcess:
    """Имитирует subprocess.Popen ровно настолько, насколько нужно LocalPlayer."""

    def __init__(self, hangs: bool = False):
        self.alive = True
        self.hangs = hangs  # не реагирует на terminate() — придётся kill()
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.terminated = True
        if not self.hangs:
            self.alive = False

    def wait(self, timeout=None):
        if self.hangs:
            raise subprocess.TimeoutExpired(cmd="vlc", timeout=timeout)

    def kill(self):
        self.killed = True
        self.alive = False


def _patch_run_quiet(monkeypatch, processes: list[FakeProcess]) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run_quiet(cmd):
        calls.append(cmd)
        return processes.pop(0)

    monkeypatch.setattr("voice_player.local_playback.run_quiet", fake_run_quiet)
    return calls


def test_play_launches_vlc_and_registers_player(monkeypatch):
    calls = _patch_run_quiet(monkeypatch, [FakeProcess()])
    players = Players()

    LocalPlayer().play(Path("/tmp/track.mp3"), players, "трек", notify_on=False)

    assert calls == [["vlc", "--intf", "dummy", "--no-video", "--play-and-exit", "/tmp/track.mp3"]]
    assert players.named == "vlc"


def test_play_notifies_when_enabled(monkeypatch):
    _patch_run_quiet(monkeypatch, [FakeProcess()])
    notified = []
    monkeypatch.setattr("voice_player.local_playback.notify", lambda text: notified.append(text))

    LocalPlayer().play(Path("/tmp/track.mp3"), Players(), "название трека", notify_on=True)

    assert notified == ["название трека"]


def test_play_silent_when_notify_disabled(monkeypatch):
    _patch_run_quiet(monkeypatch, [FakeProcess()])
    notified = []
    monkeypatch.setattr("voice_player.local_playback.notify", lambda text: notified.append(text))

    LocalPlayer().play(Path("/tmp/track.mp3"), Players(), "название трека", notify_on=False)

    assert notified == []


def test_second_track_stops_first_still_running_process(monkeypatch):
    # раньше play_local_file просто запускала новый VLC, ничего не останавливая -- несколько
    # названных подряд треков играли одновременно. Теперь второй play() должен погасить первый.
    first, second = FakeProcess(), FakeProcess()
    _patch_run_quiet(monkeypatch, [first, second])
    player, players = LocalPlayer(), Players()

    player.play(Path("/tmp/a.mp3"), players, "a", notify_on=False)
    player.play(Path("/tmp/b.mp3"), players, "b", notify_on=False)

    assert first.terminated is True
    assert first.killed is False
    assert player.process is second


def test_does_not_touch_process_that_already_finished(monkeypatch):
    first = FakeProcess()
    first.alive = False  # трек уже сам доиграл до конца
    second = FakeProcess()
    _patch_run_quiet(monkeypatch, [first, second])
    player, players = LocalPlayer(), Players()

    player.play(Path("/tmp/a.mp3"), players, "a", notify_on=False)
    player.play(Path("/tmp/b.mp3"), players, "b", notify_on=False)

    assert first.terminated is False


def test_kills_process_that_ignores_terminate(monkeypatch):
    hanging, second = FakeProcess(hangs=True), FakeProcess()
    _patch_run_quiet(monkeypatch, [hanging, second])
    player, players = LocalPlayer(), Players()

    player.play(Path("/tmp/a.mp3"), players, "a", notify_on=False)
    player.play(Path("/tmp/b.mp3"), players, "b", notify_on=False)

    assert hanging.terminated is True
    assert hanging.killed is True
