"""_dispatch_player_action: «дальше»/«назад» должны уходить в LocalPlayer, когда активен VLC
(playlist из одного файла — родных Next/Previous там нечем листать), и в обычный playerctl
во всех остальных случаях. Собирается в обход VoiceLoop.__init__ (см. test_asker_routing.py)."""

from voice_player.loop import VoiceLoop


class FakePlayers:
    def __init__(self, targets_result):
        self.targets_result = targets_result
        self.run_calls: list[tuple] = []

    def targets(self, action):
        return self.targets_result, []

    def run(self, action, label, notify_on):
        self.run_calls.append((action, label, notify_on))


class FakeLocalPlayer:
    def __init__(self):
        self.next_calls = 0
        self.previous_calls = 0

    def next(self, players, notify_on):
        self.next_calls += 1

    def previous(self, players, notify_on):
        self.previous_calls += 1


def _make_loop(players, local_player) -> VoiceLoop:
    loop = VoiceLoop.__new__(VoiceLoop)
    loop.players = players
    loop.local_player = local_player
    loop.notify_on = False
    return loop


def test_next_goes_to_local_player_when_vlc_is_the_target():
    players = FakePlayers(["vlc"])
    local_player = FakeLocalPlayer()
    loop = _make_loop(players, local_player)

    loop._dispatch_player_action(["next"], "дальше")

    assert local_player.next_calls == 1
    assert players.run_calls == []


def test_previous_goes_to_local_player_when_vlc_is_the_target():
    players = FakePlayers(["vlc"])
    local_player = FakeLocalPlayer()
    loop = _make_loop(players, local_player)

    loop._dispatch_player_action(["previous"], "назад")

    assert local_player.previous_calls == 1


def test_next_goes_to_playerctl_when_target_is_not_vlc():
    players = FakePlayers(["chromium.instance123"])
    local_player = FakeLocalPlayer()
    loop = _make_loop(players, local_player)

    loop._dispatch_player_action(["next"], "дальше")

    assert local_player.next_calls == 0
    assert players.run_calls == [(["next"], "дальше", False)]


def test_pause_is_never_intercepted_by_local_player():
    players = FakePlayers(["vlc"])
    local_player = FakeLocalPlayer()
    loop = _make_loop(players, local_player)

    loop._dispatch_player_action(["pause"], "пауза")

    assert players.run_calls == [(["pause"], "пауза", False)]
    assert local_player.next_calls == 0
    assert local_player.previous_calls == 0
