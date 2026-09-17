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


def _patch_run_quiet(monkeypatch, count: int = 20) -> list[list[str]]:
    """count с запасом — next()/previous() внутри теста может запустить несколько треков."""
    calls: list[list[str]] = []
    processes = [FakeProcess() for _ in range(count)]

    def fake_run_quiet(cmd):
        calls.append(cmd)
        return processes.pop(0)

    monkeypatch.setattr("voice_player.local_playback.run_quiet", fake_run_quiet)
    return calls


def _make_pool(tmp_path: Path, names: list[str]) -> Path:
    d = tmp_path / "pool"
    d.mkdir()
    for name in names:
        (d / name).write_bytes(b"")
    return d


def test_play_launches_vlc_and_registers_player(monkeypatch, tmp_path):
    calls = _patch_run_quiet(monkeypatch)
    players = Players()

    LocalPlayer([tmp_path]).play(Path("/tmp/track.mp3"), players, "трек", notify_on=False)

    assert calls == [["vlc", "--intf", "dummy", "--no-video", "--play-and-exit", "/tmp/track.mp3"]]
    assert players.named == "vlc"


def test_play_notifies_when_enabled(monkeypatch, tmp_path):
    _patch_run_quiet(monkeypatch)
    notified = []
    monkeypatch.setattr("voice_player.local_playback.notify", lambda text: notified.append(text))

    LocalPlayer([tmp_path]).play(Path("/tmp/track.mp3"), Players(), "название трека", notify_on=True)

    assert notified == ["название трека"]


def test_play_silent_when_notify_disabled(monkeypatch, tmp_path):
    _patch_run_quiet(monkeypatch)
    notified = []
    monkeypatch.setattr("voice_player.local_playback.notify", lambda text: notified.append(text))

    LocalPlayer([tmp_path]).play(Path("/tmp/track.mp3"), Players(), "название трека", notify_on=False)

    assert notified == []


def test_second_track_stops_first_still_running_process(monkeypatch, tmp_path):
    # раньше play() просто запускала новый VLC, ничего не останавливая -- несколько
    # названных подряд треков играли одновременно. Теперь второй play() должен погасить первый.
    calls = _patch_run_quiet(monkeypatch)
    player, players = LocalPlayer([tmp_path]), Players()

    player.play(Path("/tmp/a.mp3"), players, "a", notify_on=False)
    first_process = player.process
    player.play(Path("/tmp/b.mp3"), players, "b", notify_on=False)

    assert first_process.terminated is True
    assert first_process.killed is False
    assert len(calls) == 2


def test_does_not_touch_process_that_already_finished(monkeypatch, tmp_path):
    _patch_run_quiet(monkeypatch)
    player, players = LocalPlayer([tmp_path]), Players()

    player.play(Path("/tmp/a.mp3"), players, "a", notify_on=False)
    first_process = player.process
    first_process.alive = False  # трек уже сам доиграл до конца
    player.play(Path("/tmp/b.mp3"), players, "b", notify_on=False)

    assert first_process.terminated is False


def test_kills_process_that_ignores_terminate(monkeypatch, tmp_path):
    _patch_run_quiet(monkeypatch)
    player, players = LocalPlayer([tmp_path]), Players()

    player.play(Path("/tmp/a.mp3"), players, "a", notify_on=False)
    first_process = player.process
    first_process.hangs = True
    player.play(Path("/tmp/b.mp3"), players, "b", notify_on=False)

    assert first_process.terminated is True
    assert first_process.killed is True


class TestNextPrevious:
    def test_next_picks_random_track_from_pool(self, monkeypatch, tmp_path):
        pool = _make_pool(tmp_path, ["a.mp3", "b.mp3"])
        _patch_run_quiet(monkeypatch)
        player, players = LocalPlayer([pool]), Players()

        player.next(players, notify_on=False)

        assert len(player.history) == 1
        assert player.history[0] in {pool / "a.mp3", pool / "b.mp3"}
        assert player.position == 0

    def test_pool_includes_non_mp3_audio_formats(self, monkeypatch, tmp_path):
        # бот-поиск в Telegram присылает аудио в чём попало (m4a, ogg, ...), не только mp3
        pool = _make_pool(tmp_path, ["a.m4a"])
        _patch_run_quiet(monkeypatch)
        player, players = LocalPlayer([pool]), Players()

        player.next(players, notify_on=False)

        assert player.history == [pool / "a.m4a"]

    def test_next_avoids_repeating_current_track_when_pool_has_alternatives(self, monkeypatch, tmp_path):
        pool = _make_pool(tmp_path, ["a.mp3", "b.mp3"])
        _patch_run_quiet(monkeypatch)
        player, players = LocalPlayer([pool]), Players()

        player.play(pool / "a.mp3", players, "a", notify_on=False)
        player.next(players, notify_on=False)

        assert player.history[-1] == pool / "b.mp3"

    def test_next_replays_forward_history_after_going_back(self, monkeypatch, tmp_path):
        pool = _make_pool(tmp_path, ["a.mp3", "b.mp3", "c.mp3"])
        _patch_run_quiet(monkeypatch)
        player, players = LocalPlayer([pool]), Players()

        player.play(pool / "a.mp3", players, "a", notify_on=False)
        player.play(pool / "b.mp3", players, "b", notify_on=False)
        player.play(pool / "c.mp3", players, "c", notify_on=False)
        player.previous(players, notify_on=False)  # -> b
        player.previous(players, notify_on=False)  # -> a
        player.next(players, notify_on=False)  # должен вернуть b, а не выбрать случайный

        assert player.history == [pool / "a.mp3", pool / "b.mp3", pool / "c.mp3"]
        assert player.position == 1

    def test_next_does_nothing_when_pool_is_empty(self, monkeypatch, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        calls = _patch_run_quiet(monkeypatch)
        player = LocalPlayer([empty])

        player.next(Players(), notify_on=False)

        assert calls == []
        assert player.history == []

    def test_previous_steps_back_through_history(self, monkeypatch, tmp_path):
        pool = _make_pool(tmp_path, ["a.mp3", "b.mp3"])
        _patch_run_quiet(monkeypatch)
        player, players = LocalPlayer([pool]), Players()

        player.play(pool / "a.mp3", players, "a", notify_on=False)
        player.play(pool / "b.mp3", players, "b", notify_on=False)
        player.previous(players, notify_on=False)

        assert player.history[player.position] == pool / "a.mp3"

    def test_previous_does_nothing_at_start_of_history(self, monkeypatch, tmp_path):
        pool = _make_pool(tmp_path, ["a.mp3"])
        calls = _patch_run_quiet(monkeypatch)
        player, players = LocalPlayer([pool]), Players()

        player.play(pool / "a.mp3", players, "a", notify_on=False)
        calls_before = len(calls)
        player.previous(players, notify_on=False)

        assert len(calls) == calls_before  # ничего нового не запустилось

    def test_play_after_going_back_discards_forward_history(self, monkeypatch, tmp_path):
        pool = _make_pool(tmp_path, ["a.mp3", "b.mp3", "c.mp3"])
        _patch_run_quiet(monkeypatch)
        player, players = LocalPlayer([pool]), Players()

        player.play(pool / "a.mp3", players, "a", notify_on=False)
        player.play(pool / "b.mp3", players, "b", notify_on=False)
        player.previous(players, notify_on=False)  # -> a
        player.play(pool / "c.mp3", players, "c", notify_on=False)  # новый явный выбор

        assert player.history == [pool / "a.mp3", pool / "c.mp3"]
        assert player.position == 1
