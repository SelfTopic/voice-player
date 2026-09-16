# voice-player

Голосовое управление медиаплеерами и окнами KDE Plasma.

Быстрые команды («пауза», «дальше», «терминал») распознаются офлайн через
[Vosk](https://alphacephei.com/vosk/) по короткому списку слов — без задержек и без сети.
Запросы «Джарвис, включи \<что угодно\>» распознаются через
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) и ищутся на YouTube.

## Требования

- Manjaro / Arch, KDE Plasma (используется KWin для управления окнами через [kdotool](https://github.com/jinliu/kdotool))
- PipeWire или PulseAudio (`parec`/`pw-record` для чтения микрофона, `pactl` для громкости и выходов звука)
- `playerctl` — управление MPRIS-плеерами (браузер, Telegram, и т.д.)
- Python 3.11+

## Установка (в т.ч. после переустановки системы)

```bash
git clone https://github.com/<твой-профиль>/voice-player.git
cd voice-player
./install.sh          # быстрые команды: пауза, дальше, звук, окна...
./install.sh --ask     # плюс «джарвис, включи ...» и «загугли ...» (Whisper + yt-dlp)
```

Скрипт сам:
- доставит недостающие системные пакеты через `pacman`;
- создаст venv в `~/.local/share/voice-player/venv` и установит туда пакет `voice-player`;
- скачает модель Vosk (`~45 МБ`) в `~/.local/share/voice-player/model`, если её там ещё нет;
- скачает `kdotool` (`~800 КБ`) в `~/.local/share/voice-player/bin`, если не установлен системно;
- положит конфиги по умолчанию в `~/.config/voice-player/` (не трогает уже существующие);
- поставит systemd user-unit `~/.config/systemd/user/voice-player.service`.

Модель Whisper (`base` по умолчанию, `~145 МБ`) отдельно не скачивается — `faster-whisper`
сам подтянет её из Hugging Face при первом запуске с `--ask` и закэширует в
`~/.cache/huggingface/hub`. Повторная установка на той же системе ничего заново не скачивает.

Проверка вручную:

```bash
~/.local/share/voice-player/venv/bin/voice-player -v
```

Автозапуск:

```bash
systemctl --user enable --now voice-player
```

## Настройка

Все конфиги лежат в `~/.config/voice-player/` и правятся без пересборки — после
изменения перезапусти сервис (`systemctl --user restart voice-player`):

- `names.txt` — исполнители/названия, которые Whisper должен писать без ошибок.
- `windows.txt` — `слово = регулярка по классу окна` («переключиться на браузер»).
- `sinks.txt` — `слово = регулярка по имени устройства вывода звука` («звук наушники»).

Список быстрых команд («пауза», «дальше», «громче», «полный экран», ...) зашит в
[`voice_player/commands.py`](voice_player/commands.py) — слова должны быть в словаре модели Vosk,
иначе при старте появится предупреждение и команда будет пропущена.

Полезные флаги (`voice-player --help`): `--wake` (ключевое слово перед быстрыми командами),
`--device` (источник звука), `--whisper tiny|base|small`, `--no-ask`, `--no-windows`, `--no-notify`.

## Разработка

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[ask]" pytest ruff
pytest
ruff check voice_player
```

## Структура

| Модуль | Что делает |
|---|---|
| `cli.py` | разбор аргументов, сборка компонентов, точка входа |
| `config.py` | пути и константы |
| `commands.py` | реестр быстрых команд, загрузка `windows.txt`/`sinks.txt` |
| `grammar.py` | разбор распознанного текста в команду/запрос |
| `loop.py` | основной цикл чтения микрофона (`VoiceLoop`) |
| `players.py` | выбор плеера для команды через `playerctl` |
| `windows.py` | переключение окон и полный экран через kdotool/KWin |
| `dictation.py` | голосовой ввод текста («напиши», «отправь») |
| `asker.py` | Whisper + поиск на YouTube («джарвис, включи ...») |
| `uinput.py` | виртуальная клавиатура/мышь через `/dev/uinput` |
| `clipboard.py` | буфер обмена KDE (Klipper) |
| `audio.py` | переключение аудиовыхода, захват микрофона |
