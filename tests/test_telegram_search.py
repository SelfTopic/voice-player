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
