"""Разбор аргументов, сборка компонентов и запуск основного цикла."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from vosk import KaldiRecognizer, Model, SetLogLevel

from . import __doc__ as description
from .asker import Asker
from .audio import mic_process
from .commands import COMMANDS, FULLSCREEN, SCROLL, SEND, SINK, load_mapping, read_lines
from .config import (
    ASK_VERBS,
    ASK_WORD,
    DEFAULT_MODEL,
    DEFAULT_NAMES,
    DEFAULT_SINKS,
    DEFAULT_WINDOWS,
    DICTATE_WORDS,
    SAMPLE_RATE,
    SEARCH_WORDS,
    SINK_WORD,
)
from .dictation import Dictation
from .grammar import build_grammar, known_words
from .loop import VoiceLoop
from .players import Players
from .uinput import (
    BTN_LEFT,
    BTN_RIGHT,
    KEY_ENTER,
    KEY_ESC,
    KEY_F,
    KEY_L,
    KEY_LEFTCTRL,
    KEY_LEFTSHIFT,
    KEY_V,
    REL_WHEEL,
    REL_X,
    REL_Y,
    UInputDevice,
)
from .windows import WINDOWS_FALLBACK, find_kdotool, window_command


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="папка с моделью Vosk")
    ap.add_argument("--wake", help="ключевое слово перед быстрыми командами, например «джарвис»")
    ap.add_argument("--device", help="источник звука (pactl list short sources)")
    ap.add_argument("--min-conf", type=float, default=0.7, help="порог уверенности 0..1 (для медленного режима)")
    ap.add_argument(
        "--stable", type=int, default=3,
        help="быстрый режим: сколько кусков по 50 мс слово должно продержаться; 0 = ждать конца фразы",
    )
    ap.add_argument("--whisper", default="base", help="модель Whisper для запросов: tiny, base, small")
    ap.add_argument(
        "--names", type=Path, default=DEFAULT_NAMES,
        help="файл с исполнителями и названиями для Whisper, по одному в строке",
    )
    ap.add_argument("--windows", type=Path, default=DEFAULT_WINDOWS, help="файл «слово = класс окна»")
    ap.add_argument("--sinks", type=Path, default=DEFAULT_SINKS, help="файл «слово = имя устройства вывода звука»")
    ap.add_argument("--no-ask", action="store_true", help="выключить запросы «джарвис, включи ...»")
    ap.add_argument("--no-windows", action="store_true", help="выключить переключение окон")
    ap.add_argument("--no-notify", action="store_true", help="не показывать уведомления")
    ap.add_argument("-v", "--verbose", action="store_true", help="печатать всё распознанное")
    return ap.parse_args()


def load_model(args: argparse.Namespace) -> tuple[Model, str | None]:
    if not args.model.is_dir():
        sys.exit(f"модель не найдена: {args.model} (запусти install.sh)")
    SetLogLevel(-1)
    model = Model(str(args.model))
    wake = args.wake.lower() if args.wake else None
    if wake and model.vosk_model_find_word(wake) == -1:
        sys.exit(f"модель не знает слово «{wake}», выбери другое ключевое слово")
    return model, wake


def register_window_commands(args: argparse.Namespace, kdotool: str | None) -> dict[str, str]:
    """Добавляет в COMMANDS слова для переключения окон, возвращает слово -> регулярка."""
    window_patterns: dict[str, str] = {}
    if args.no_windows:
        return window_patterns
    if not kdotool:
        print("! переключение окон выключено: нет kdotool (запусти install.sh)", file=sys.stderr)
        return window_patterns
    for word, pattern in load_mapping(args.windows, WINDOWS_FALLBACK).items():
        if word in COMMANDS:
            print(f"! «{word}» уже занято командой плеера, окно пропущено", file=sys.stderr)
            continue
        COMMANDS[word] = window_command(kdotool, pattern)
        window_patterns[word] = pattern
    return window_patterns


def register_sink_commands(args: argparse.Namespace) -> None:
    for word, pattern in load_mapping(args.sinks, {}).items():
        COMMANDS[f"{SINK_WORD} {word}"] = [SINK, pattern, word]


def make_input_devices(kdotool: str | None) -> tuple[UInputDevice | None, UInputDevice | None]:
    keyboard = mouse = None
    try:
        mouse = UInputDevice("voice-player mouse", keys=(BTN_LEFT, BTN_RIGHT), rels=(REL_X, REL_Y, REL_WHEEL))
        if kdotool:
            keyboard = UInputDevice(
                "voice-player keyboard", keys=(KEY_ESC, KEY_ENTER, KEY_LEFTCTRL, KEY_LEFTSHIFT, KEY_F, KEY_L, KEY_V),
            )
    except OSError as e:
        print(f"! полный экран и прокрутка выключены: нет доступа к /dev/uinput ({e.strerror})", file=sys.stderr)
    disabled = ([] if keyboard else [FULLSCREEN, SEND]) + ([] if mouse else [SCROLL])
    for word in [w for w, argv in COMMANDS.items() if argv[0] in disabled]:
        del COMMANDS[word]
    return keyboard, mouse


def make_asker(
    args: argparse.Namespace, players: Players, kdotool: str | None,
    keyboard: UInputDevice | None, dictation: Dictation,
) -> Asker | None:
    if args.no_ask:
        return None
    print(f"загружаю Whisper «{args.whisper}» (в первый раз скачается)…", flush=True)
    names = read_lines(args.names)
    if names:
        print(f"подсказки для Whisper: {', '.join(names)}", flush=True)
    try:
        return Asker(args.whisper, names, players, kdotool, keyboard, dictation, not args.no_notify, args.verbose)
    except ImportError as e:
        print(f"! запросы выключены: {e} (запусти install.sh --ask)", file=sys.stderr)
        return None


def build_recognizers(
    model: Model, wake: str | None, asker: Asker | None, keyboard: UInputDevice | None,
) -> tuple[KaldiRecognizer, KaldiRecognizer | None, list[str]]:
    phrases = known_words(model, list(COMMANDS))
    trigger_words = SEARCH_WORDS + (DICTATE_WORDS if keyboard else [])  # вставке текста нужны kdotool и uinput
    search_phrases = [f"{wake} {w}" for w in trigger_words] if wake else trigger_words
    ask_phrases = known_words(model, [f"{ASK_WORD} {v}" for v in ASK_VERBS] + search_phrases) if asker else []
    grammar = build_grammar(wake, phrases, ask_phrases)
    rec = KaldiRecognizer(model, SAMPLE_RATE, json.dumps(grammar, ensure_ascii=False))
    rec.SetWords(True)
    free = KaldiRecognizer(model, SAMPLE_RATE) if asker else None  # только чтобы понять, что фраза закончилась
    return rec, free, phrases


def print_startup_summary(
    wake: str | None, phrases: list[str], window_patterns: dict[str, str], asker: Asker | None, keyboard,
) -> None:
    hint = f"«{wake} <команда>»" if wake else "команды"
    print(f"слушаю {hint}: {', '.join(p for p in phrases if p not in window_patterns)}", flush=True)
    active_windows = [p for p in phrases if p in window_patterns]
    if active_windows:
        print(f"окна: {', '.join(active_windows)}", flush=True)
    if asker:
        extra = ", «напиши <текст>» и «отправь»" if keyboard else ""
        print(f"и запросы: «{ASK_WORD}, включи <песня или видео>», «загугли <запрос>»{extra}", flush=True)


def main() -> None:
    args = parse_args()
    model, wake = load_model(args)

    players = Players(args.verbose)
    dictation = Dictation()
    kdotool = find_kdotool()

    window_patterns = register_window_commands(args, kdotool)
    register_sink_commands(args)
    keyboard, mouse = make_input_devices(kdotool)
    asker = make_asker(args, players, kdotool, keyboard, dictation)

    rec, free, phrases = build_recognizers(model, wake, asker, keyboard)

    # playerctld помнит последний активный плеер — запасной вариант, когда больше ничего не известно
    subprocess.run(["playerctld", "daemon"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    mic = mic_process(args.device)
    print_startup_summary(wake, phrases, window_patterns, asker, keyboard)

    loop = VoiceLoop(
        mic=mic, rec=rec, free=free, players=players, dictation=dictation, asker=asker,
        kdotool=kdotool, keyboard=keyboard, mouse=mouse, window_patterns=window_patterns,
        wake=wake, stable=args.stable, min_conf=args.min_conf, notify_on=not args.no_notify, verbose=args.verbose,
    )
    loop.run()


if __name__ == "__main__":
    main()
