from voice_player.check_words import check_phrase


class FakeModel:
    """Достаточно для known_words(): только vosk_model_find_word."""

    def __init__(self, known_words: set[str]):
        self.known = known_words

    def vosk_model_find_word(self, word: str) -> int:
        return 0 if word in self.known else -1


def test_check_phrase_known_word():
    model = FakeModel({"вейл"})
    assert check_phrase(model, "вейл") is True


def test_check_phrase_unknown_word():
    model = FakeModel({"вейл"})
    assert check_phrase(model, "неизвестное") is False


def test_check_phrase_all_words_of_multi_word_phrase_must_be_known():
    model = FakeModel({"птицы", "добычи"})
    assert check_phrase(model, "птицы добычи") is True
    assert check_phrase(model, "птицы жертвы") is False
