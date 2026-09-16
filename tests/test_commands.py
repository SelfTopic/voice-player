from voice_player.commands import load_mapping, read_lines


def test_read_lines_skips_comments_and_blanks(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("# комментарий\nслово\n\n  другое слово  \n", encoding="utf-8")
    assert read_lines(path) == ["слово", "другое слово"]


def test_read_lines_missing_file_returns_empty(tmp_path):
    assert read_lines(tmp_path / "нет-такого.txt") == []


def test_load_mapping_parses_word_equals_pattern(tmp_path):
    path = tmp_path / "windows.txt"
    path.write_text("терминал = konsole|kitty\nбраузер = chrome|chromium\n", encoding="utf-8")
    assert load_mapping(path, {}) == {"терминал": "konsole|kitty", "браузер": "chrome|chromium"}


def test_load_mapping_lowercases_word(tmp_path):
    path = tmp_path / "windows.txt"
    path.write_text("ТЕРМИНАЛ = konsole\n", encoding="utf-8")
    assert load_mapping(path, {}) == {"терминал": "konsole"}


def test_load_mapping_skips_malformed_line(tmp_path, capsys):
    path = tmp_path / "windows.txt"
    path.write_text("это не тот формат\nбраузер = chrome\n", encoding="utf-8")
    assert load_mapping(path, {}) == {"браузер": "chrome"}
    assert "не понял строку" in capsys.readouterr().err


def test_load_mapping_missing_file_uses_fallback(tmp_path):
    fallback = {"терминал": "konsole"}
    assert load_mapping(tmp_path / "нет-такого.txt", fallback) == fallback
