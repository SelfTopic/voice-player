from voice_player.grammar import (
    ASK,
    DICTATE,
    GOOGLE,
    ask_mode,
    build_grammar,
    command_at_end,
    extract_query,
    parse_command,
)


class TestParseCommand:
    def test_plain_command(self):
        assert parse_command("пауза", None) == "пауза"

    def test_unknown_phrase(self):
        assert parse_command("сделай мне бутерброд", None) is None

    def test_requires_wake_word(self):
        assert parse_command("пауза", "джарвис") is None
        assert parse_command("джарвис пауза", "джарвис") == "пауза"

    def test_two_word_command(self):
        assert parse_command("полный экран", None) == "полный экран"

    def test_wake_word_alone_is_not_a_command(self):
        assert parse_command("джарвис", "джарвис") is None


class TestCommandAtEnd:
    def test_single_word_command_at_end_of_partial(self):
        assert command_at_end("э я хочу сказать пауза", None, False) == "пауза"

    def test_two_word_command_preferred_over_one_word_tail(self):
        # «экран» само по себе не команда, а «полный экран» — команда
        assert command_at_end("сделай полный экран", None, False) == "полный экран"

    def test_wake_word_required_right_before_command(self):
        assert command_at_end("джарвис пауза", "джарвис", False) == "пауза"
        assert command_at_end("пауза", "джарвис", False) is None
        assert command_at_end("что-то джарвис слово пауза", "джарвис", False) is None

    def test_unk_tokens_are_ignored(self):
        assert command_at_end("[unk] [unk] пауза", None, False) == "пауза"

    def test_empty_partial(self):
        assert command_at_end("", None, False) is None

    def test_ask_trigger_requires_ask_enabled(self):
        assert command_at_end("джарвис включи", None, True) == ASK
        assert command_at_end("джарвис включи", None, False) is None

    def test_search_and_dictate_triggers(self):
        assert command_at_end("сегодня погугли", None, True) == GOOGLE
        assert command_at_end("сейчас напиши", None, True) == DICTATE

    def test_search_trigger_after_wake_word(self):
        assert command_at_end("джарвис погугли", "джарвис", True) == GOOGLE
        assert command_at_end("погугли", "джарвис", True) is None


class TestAskMode:
    def test_ask(self):
        assert ask_mode("джарвис включи мне линкин парк") == ASK

    def test_dictate(self):
        assert ask_mode("напиши привет как дела") == DICTATE

    def test_google(self):
        assert ask_mode("погугли погоду в москве") == GOOGLE

    def test_none_for_plain_command(self):
        assert ask_mode("пауза") is None

    def test_ask_takes_priority_over_dictate_word_reuse(self):
        # «включи» сразу после «джарвис» -> ASK, даже если дальше встретится другое триггер-слово
        assert ask_mode("джарвис включи напиши мне текст") == ASK


class TestExtractQuery:
    def test_ask_strips_verb_and_fillers(self):
        assert extract_query("джарвис включи мне песню линкин парк намб") == "линкин парк намб"

    def test_google_strips_trigger_word(self):
        assert extract_query("загугли погоду в москве", GOOGLE) == "погоду в москве"

    def test_dictate_keeps_trailing_punctuation(self):
        assert extract_query("напиши привет, как дела?", DICTATE) == "привет, как дела?"

    def test_no_verb_returns_empty(self):
        assert extract_query("случайный шум без команды") == ""

    def test_ask_strips_quotes_and_dashes(self):
        assert extract_query("джарвис включи «намб» —") == "намб"


def test_build_grammar_with_wake_word():
    grammar = build_grammar("джарвис", ["пауза", "дальше"], ["джарвис включи"])
    assert grammar == ["джарвис пауза", "джарвис дальше", "джарвис включи", "джарвис", "[unk]"]


def test_build_grammar_without_wake_word():
    grammar = build_grammar(None, ["пауза", "дальше"], ["погугли"])
    assert grammar == ["пауза", "дальше", "погугли", "[unk]"]
