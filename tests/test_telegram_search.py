"""load_saved_index/remember_saved: чтобы искать один и тот же трек дважды не значило
скачать его дважды (file_unique_id -> путь на диске)."""

import json

from voice_player.telegram import search


def test_load_saved_index_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(search, "SAVED_INDEX", tmp_path / "saved_index.json")
    assert search.load_saved_index() == {}


def test_remember_saved_then_load_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setattr(search, "SAVED_INDEX", tmp_path / "saved_index.json")
    search.remember_saved("abc123", "/a/song.m4a")
    assert search.load_saved_index() == {"abc123": "/a/song.m4a"}


def test_remember_saved_accumulates_multiple_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(search, "SAVED_INDEX", tmp_path / "saved_index.json")
    search.remember_saved("id1", "/a/one.m4a")
    search.remember_saved("id2", "/a/two.m4a")
    assert search.load_saved_index() == {"id1": "/a/one.m4a", "id2": "/a/two.m4a"}


def test_remember_saved_overwrites_same_id(tmp_path, monkeypatch):
    monkeypatch.setattr(search, "SAVED_INDEX", tmp_path / "saved_index.json")
    search.remember_saved("id1", "/a/old.m4a")
    search.remember_saved("id1", "/a/new.m4a")
    assert search.load_saved_index() == {"id1": "/a/new.m4a"}


def test_remember_saved_creates_parent_dirs(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "saved_index.json"
    monkeypatch.setattr(search, "SAVED_INDEX", path)
    search.remember_saved("id1", "/a/one.m4a")
    assert path.is_file()


def test_load_saved_index_recovers_from_corrupted_file(tmp_path, monkeypatch):
    path = tmp_path / "saved_index.json"
    path.write_text("не json вообще", encoding="utf-8")
    monkeypatch.setattr(search, "SAVED_INDEX", path)
    assert search.load_saved_index() == {}


def test_index_file_is_valid_json(tmp_path, monkeypatch):
    path = tmp_path / "saved_index.json"
    monkeypatch.setattr(search, "SAVED_INDEX", path)
    search.remember_saved("id1", "/a/one.m4a")
    assert json.loads(path.read_text(encoding="utf-8")) == {"id1": "/a/one.m4a"}


class _FakeWorker:
    """coro.close() — чтобы не ловить "coroutine was never awaited": реальный поход в Telegram
    (self._find_track(query), запущенный на настоящем воркере) тут никогда не исполняется."""

    def __init__(self, result):
        self.result = result

    def run(self, coro, timeout=None):
        coro.close()
        return self.result


class TestFindTrackCaching:
    """find_track(): кэш запросов (query_cache) проверяется ДО обращения к боту."""

    def test_returns_cached_result_without_touching_worker(self, monkeypatch, tmp_path):
        cached_path = tmp_path / "cached.m4a"
        cached_path.write_bytes(b"")
        monkeypatch.setattr(search, "find_similar", lambda query: str(cached_path))

        ts = search.TelegramSearch.__new__(search.TelegramSearch)
        ts.worker = None  # если код полезет в worker -- тест упадёт с AttributeError

        assert ts.find_track("что угодно") == cached_path

    def test_remembers_successful_fresh_search(self, monkeypatch, tmp_path):
        monkeypatch.setattr(search, "find_similar", lambda query: None)
        fresh_path = tmp_path / "fresh.m4a"
        remembered = {}
        monkeypatch.setattr(
            search, "remember_query",
            lambda query, path: remembered.update(query=query, path=path),
        )

        ts = search.TelegramSearch.__new__(search.TelegramSearch)
        ts.worker = _FakeWorker(fresh_path)
        ts.bot = "@bot"

        assert ts.find_track("тест запрос") == fresh_path
        assert remembered == {"query": "тест запрос", "path": str(fresh_path)}

    def test_does_not_remember_when_search_finds_nothing(self, monkeypatch):
        monkeypatch.setattr(search, "find_similar", lambda query: None)
        remembered = []
        monkeypatch.setattr(search, "remember_query", lambda query, path: remembered.append((query, path)))

        ts = search.TelegramSearch.__new__(search.TelegramSearch)
        ts.worker = _FakeWorker(None)
        ts.bot = "@bot"

        assert ts.find_track("тест запрос") is None
        assert remembered == []
