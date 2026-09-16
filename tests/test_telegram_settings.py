from voice_player.telegram.settings import TelegramSettings, load_settings


def test_load_settings_missing_file_returns_none(tmp_path):
    assert load_settings(tmp_path / "нет-такого.toml") is None


def test_load_settings_parses_valid_file(tmp_path):
    path = tmp_path / "telegram.toml"
    path.write_text(
        """
        api_id = 12345
        api_hash = "abc"
        session_name = "voice-player"
        mr_kitty_channel = "@kitty"
        search_bot = "@musicbot"
        """,
        encoding="utf-8",
    )
    assert load_settings(path) == TelegramSettings(
        api_id=12345, api_hash="abc", session_name="voice-player",
        mr_kitty_channel="@kitty", search_bot="@musicbot",
    )


def test_load_settings_missing_field_returns_none(tmp_path, caplog):
    import logging

    path = tmp_path / "telegram.toml"
    path.write_text('api_id = 1\napi_hash = "abc"\n', encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="voice_player.telegram.settings"):
        assert load_settings(path) is None
    assert "не заполнены поля" in caplog.text


def test_load_settings_empty_string_counts_as_missing(tmp_path):
    path = tmp_path / "telegram.toml"
    path.write_text(
        """
        api_id = 1
        api_hash = ""
        session_name = "voice-player"
        mr_kitty_channel = "@kitty"
        search_bot = "@musicbot"
        """,
        encoding="utf-8",
    )
    assert load_settings(path) is None
