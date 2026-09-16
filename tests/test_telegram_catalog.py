from voice_player.telegram.catalog import merge_tracks, slugify_title, write_tracks


class TestSlugifyTitle:
    def test_lowercases_and_strips_punctuation(self):
        assert slugify_title("Bloodlust (Remix)") == "bloodlust remix"

    def test_collapses_multiple_separators(self):
        assert slugify_title("Faded -- Slowed & Reverb") == "faded slowed reverb"

    def test_keeps_cyrillic(self):
        assert slugify_title("Тест Трек") == "тест трек"

    def test_empty_title(self):
        assert slugify_title("   ") == ""


class TestMergeTracks:
    def test_adds_new_words(self):
        existing = {"старое": "/a.mp3"}
        new = {"новое": "/b.mp3"}
        assert merge_tracks(existing, new) == {"старое": "/a.mp3", "новое": "/b.mp3"}

    def test_never_overwrites_existing_word(self):
        # пользователь мог руками поправить слово на то, что реально знает модель
        existing = {"блъадласт": "/a.mp3"}
        new = {"блъадласт": "/a-redownloaded.mp3"}
        assert merge_tracks(existing, new) == {"блъадласт": "/a.mp3"}

    def test_empty_existing(self):
        assert merge_tracks({}, {"слово": "/a.mp3"}) == {"слово": "/a.mp3"}


def test_write_tracks_roundtrips_through_load_mapping(tmp_path):
    from voice_player.commands import load_mapping

    path = tmp_path / "tracks.txt"
    tracks = {"бэ": "/b.mp3", "а": "/a.mp3"}
    write_tracks(path, tracks)
    assert load_mapping(path, {}) == tracks


def test_write_tracks_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "tracks.txt"
    write_tracks(path, {"слово": "/a.mp3"})
    assert path.is_file()
