import pytest

from voice_player.telegram.numerals import is_number_phrase, number_to_words


class TestNumberToWords:
    def test_zero(self):
        assert number_to_words(0) == "ноль"

    def test_single_digit(self):
        assert number_to_words(7) == "семь"

    def test_teen(self):
        assert number_to_words(13) == "тринадцать"

    def test_round_ten(self):
        assert number_to_words(40) == "сорок"

    def test_compound_ten(self):
        assert number_to_words(42) == "сорок два"

    def test_round_hundred(self):
        assert number_to_words(100) == "сто"

    def test_hundred_plus_teen(self):
        assert number_to_words(113) == "сто тринадцать"

    def test_hundred_plus_compound(self):
        assert number_to_words(227) == "двести двадцать семь"

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            number_to_words(1000)


class TestIsNumberPhrase:
    def test_single_word_number(self):
        assert is_number_phrase("сто") is True

    def test_compound_number(self):
        assert is_number_phrase("двести двадцать семь") is True

    def test_ordinary_word_is_not_a_number(self):
        assert is_number_phrase("вейл") is False

    def test_mixed_words_is_not_a_number(self):
        assert is_number_phrase("трек сто") is False

    def test_empty_string(self):
        assert is_number_phrase("") is False

    def test_every_generated_number_round_trips(self):
        for n in range(0, 300):
            assert is_number_phrase(number_to_words(n)) is True
