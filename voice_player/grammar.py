"""Разбор того, что расслышал Vosk: быстрые команды и запросы к Whisper."""

import logging
import re

from .commands import COMMANDS
from .config import ASK_VERBS, ASK_WORD, DICTATE_WORDS, SEARCH_WORDS

logger = logging.getLogger(__name__)

# режим запросов: «джарвис включи ...»
ASK = "__ask__"
# поиск в Google: «загугли ...»
GOOGLE = "__google__"
# голосовой ввод: «напиши ...» вставляет текст, «отправь» жмёт Enter
DICTATE = "__dictate__"

# подсказка Whisper под режим; для YouTube — своя, с исполнителями (build_prompt)
PROMPTS = {
    GOOGLE: "Загугли, как приготовить борщ.",
    DICTATE: "Напиши: привет, как дела? Буду через 10 минут.",
}

VERB_RE = re.compile(r"(?:" + "|".join(ASK_VERBS) + r")\w*[\s,.:!—–-]*(.*)", re.I | re.S)
SEARCH_RE = re.compile(r"(?:(?:за|по)?гугл|поищ)\w*[\s,.:!—–-]*(.*)", re.I | re.S)
DICTATE_RE = re.compile(r"(?:напиш|набер|введ)\w*[\s,.:!—–-]*(.*)", re.I | re.S)
WAKE_RE = re.compile(r"(?:джарвис|jarvis)\w*[\s,.:!—–-]*(.*)", re.I | re.S)
FILLER_RE = re.compile(r"^(?:(?:мне|пожалуйста|песню|песня|видео|видос|клип|трек)\s+)+", re.I)


def known_words(model, phrases: list[str]) -> list[str]:
    ok = []
    for phrase in phrases:
        missing = [w for w in phrase.split() if model.vosk_model_find_word(w) == -1]
        if missing:
            logger.warning("модель не знает слов %s, фраза «%s» пропущена", missing, phrase)
        else:
            ok.append(phrase)
    return ok


def build_grammar(wake: str | None, phrases: list[str], ask_phrases: list[str]) -> list[str]:
    if wake:
        return [f"{wake} {p}" for p in phrases] + ask_phrases + [wake, "[unk]"]
    return phrases + ask_phrases + ["[unk]"]


def parse_command(text: str, wake: str | None) -> str | None:
    """Финальный результат: вся фраза целиком должна быть командой."""
    text = text.strip()
    if wake:
        if not text.startswith(wake + " "):
            return None
        text = text[len(wake) + 1 :]
    return text if text in COMMANDS else None


def command_at_end(text: str, wake: str | None, ask: bool) -> str | None:
    """Промежуточный результат: команда в конце уже распознанного."""
    words = [w for w in text.split() if w != "[unk]"]
    if not words:
        return None
    if ask and len(words) >= 2 and words[-2] == ASK_WORD and words[-1] in ASK_VERBS:
        return ASK
    for mode, trigger_words in ((GOOGLE, SEARCH_WORDS), (DICTATE, DICTATE_WORDS)):
        if ask and words[-1] in trigger_words and (not wake or (len(words) >= 2 and words[-2] == wake)):
            return mode
    # сначала фразы из двух слов («полный экран»), потом из одного
    for size in (2, 1):
        if len(words) < size:
            continue
        phrase = " ".join(words[-size:])
        if phrase not in COMMANDS:
            continue
        before = words[:-size]
        if wake and (not before or before[-1] != wake):
            return None
        return phrase
    return None


def ask_mode(text: str) -> str | None:
    """Финальный результат: есть ли в нём запрос, и какой — YouTube или Google."""
    words = text.split()
    if any(a == ASK_WORD and b in ASK_VERBS for a, b in zip(words, words[1:])):
        return ASK
    if any(w in DICTATE_WORDS for w in words):
        return DICTATE
    if any(w in SEARCH_WORDS for w in words):
        return GOOGLE
    return None


def extract_query(text: str, mode: str = ASK) -> str:
    """«Джарвис, включи мне Linkin Park — Numb.» -> «Linkin Park — Numb»
    «Загугли погоду в Москве» (mode=GOOGLE) -> «погоду в Москве»"""
    regex = {GOOGLE: SEARCH_RE, DICTATE: DICTATE_RE}.get(mode, VERB_RE)
    m = regex.search(text) or WAKE_RE.search(text)
    if not m:
        return ""  # ни глагола, ни ключевого слова: скорее всего Whisper нафантазировал
    query = m.group(1).strip()
    if mode == DICTATE:
        return query.lstrip(" ,.:;—–-")  # знаки в конце — часть сообщения
    if mode == ASK:
        query = FILLER_RE.sub("", query)
    return query.strip(" .,!?:;—–-«»\"'")


def build_prompt(names: list[str]) -> str:
    # пример с латиницей подсказывает Whisper не транслитерировать английские названия
    prompt = "Джарвис, включи Linkin Park — Numb. Джарвис, поставь плейлист lo-fi hip hop."
    if names:
        prompt += " Исполнители: " + ", ".join(names) + "."
    return prompt
