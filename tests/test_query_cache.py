from voice_player.telegram import query_cache


def _use_tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(query_cache, "QUERY_CACHE", tmp_path / "query_cache.json")


def test_normalize_lowercases_and_collapses_whitespace():
    assert query_cache.normalize("  Григорий   ЛЕПС \n самый лучший день  ") == "григорий лепс самый лучший день"


def test_load_query_cache_missing_file_returns_empty(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    assert query_cache.load_query_cache() == {}


def test_load_query_cache_recovers_from_corrupted_file(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    query_cache.QUERY_CACHE.write_text("не json", encoding="utf-8")
    assert query_cache.load_query_cache() == {}


def test_remember_query_then_load_roundtrips(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    query_cache.remember_query("Григорий Лепс самый лучший день", "/a/song.m4a")
    assert query_cache.load_query_cache() == {"григорий лепс самый лучший день": "/a/song.m4a"}


class TestFindSimilar:
    def test_exact_match(self, tmp_path, monkeypatch):
        _use_tmp_cache(tmp_path, monkeypatch)
        (tmp_path / "song.m4a").write_bytes(b"")
        query_cache.remember_query("григорий лепс самый лучший день", str(tmp_path / "song.m4a"))

        assert query_cache.find_similar("григорий лепс самый лучший день") == str(tmp_path / "song.m4a")

    def test_one_letter_difference_still_matches(self, tmp_path, monkeypatch):
        # ровно жалоба пользователя: Whisper слышит одну другую букву в той же фразе
        _use_tmp_cache(tmp_path, monkeypatch)
        (tmp_path / "song.m4a").write_bytes(b"")
        query_cache.remember_query("григорий лепс самый лучший день", str(tmp_path / "song.m4a"))

        assert query_cache.find_similar("григорий лепс самый лучший ден") == str(tmp_path / "song.m4a")

    def test_unrelated_query_does_not_match(self, tmp_path, monkeypatch):
        _use_tmp_cache(tmp_path, monkeypatch)
        (tmp_path / "song.m4a").write_bytes(b"")
        query_cache.remember_query("григорий лепс самый лучший день", str(tmp_path / "song.m4a"))

        assert query_cache.find_similar("виктор цой группа крови") is None

    def test_different_song_by_same_artist_does_not_match(self, tmp_path, monkeypatch):
        # общее слово ("григорий лепс") не должно перевешивать явно разное продолжение запроса
        _use_tmp_cache(tmp_path, monkeypatch)
        (tmp_path / "song.m4a").write_bytes(b"")
        query_cache.remember_query("григорий лепс самый лучший день", str(tmp_path / "song.m4a"))

        assert query_cache.find_similar("григорий лепс кукушка") is None

    def test_returns_none_when_cached_file_was_deleted(self, tmp_path, monkeypatch):
        _use_tmp_cache(tmp_path, monkeypatch)
        # намеренно НЕ создаём файл на диске
        query_cache.remember_query("григорий лепс самый лучший день", str(tmp_path / "missing.m4a"))

        assert query_cache.find_similar("григорий лепс самый лучший день") is None

    def test_empty_cache_returns_none(self, tmp_path, monkeypatch):
        _use_tmp_cache(tmp_path, monkeypatch)
        assert query_cache.find_similar("что угодно") is None

    def test_picks_the_closest_match_among_several(self, tmp_path, monkeypatch):
        _use_tmp_cache(tmp_path, monkeypatch)
        (tmp_path / "a.m4a").write_bytes(b"")
        (tmp_path / "b.m4a").write_bytes(b"")
        query_cache.remember_query("виктор цой группа крови", str(tmp_path / "a.m4a"))
        query_cache.remember_query("григорий лепс самый лучший день", str(tmp_path / "b.m4a"))

        assert query_cache.find_similar("григорий лепс самый лучший ден") == str(tmp_path / "b.m4a")
