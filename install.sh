#!/usr/bin/env bash
# Установка голосового управления плеером (Manjaro / Arch)
#   ./install.sh                     быстрые команды (пауза, дальше, ...)
#   ./install.sh --ask               плюс запросы «джарвис, включи ...» (Whisper + yt-dlp, ~110 МБ)
#   ./install.sh --telegram          плюс поиск музыки через Telegram (Pyrogram) + офлайн-каталог Mr. Kitty
#   ./install.sh --big-model         вместо маленькой модели Vosk (~45 МБ) — большая (~1.8 ГБ, ru-0.42):
#                                    заметно точнее и знает куда больше заимствованных/иностранных слов.
#                                    Vosk сама называет её моделью "для серверов" — в памяти весит
#                                    сильно больше 1.8 ГБ; на машине с 8 ГБ RAM и открытым браузером/IDE
#                                    может увести систему в своп. Нужно несколько свободных гигабайт RAM.
#   ./install.sh --ask --telegram    любые флаги сочетаются (--telegram без --ask бессмысленен)
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DATA="$HOME/.local/share/voice-player"
MODEL_SMALL="vosk-model-small-ru-0.22"
MODEL_BIG="vosk-model-ru-0.42"
ASK=0
TELEGRAM=0
BIG_MODEL=0
for arg in "$@"; do
  case "$arg" in
    --ask) ASK=1 ;;
    --telegram) TELEGRAM=1 ;;
    --big-model) BIG_MODEL=1 ;;
    *) echo "неизвестный флаг: $arg" >&2; exit 1 ;;
  esac
done
MODEL_NAME="$MODEL_SMALL"
[ "$BIG_MODEL" = 1 ] && MODEL_NAME="$MODEL_BIG"

echo "==> пакеты"
# ставим только отсутствующее; уже установленные пакеты не трогаем (без частичных обновлений)
declare -A NEED=([playerctl]=playerctl [notify-send]=libnotify [parec]=libpulse [python]=python [xdg-open]=xdg-utils)
# vlc — проигрывание того, что скачал voice-player-telegram-sync/бот-поиск; MPRIS у vlc
# встроен (плагин control/dbus в самом пакете), в отличие от mpv не тянет отдельный AUR-пакет
[ "$TELEGRAM" = 1 ] && NEED[vlc]=vlc
missing=()
for bin in "${!NEED[@]}"; do
  command -v "$bin" >/dev/null || missing+=("${NEED[$bin]}")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "не хватает: ${missing[*]}"
  echo "если pacman ругается на версии — сначала обнови систему: sudo pacman -Syu"
  sudo pacman -S --needed "${missing[@]}"
else
  echo "всё уже установлено"
fi

echo "==> python-окружение"
mkdir -p "$DATA"
[ -x "$DATA/venv/bin/python" ] || python -m venv "$DATA/venv"
extras=()
[ "$ASK" = 1 ] && extras+=("ask")
[ "$TELEGRAM" = 1 ] && extras+=("telegram")
if [ ${#extras[@]} -gt 0 ]; then
  spec="$SRC[$(IFS=,; echo "${extras[*]}")]"
  echo "==> voice-player + ${extras[*]}"
else
  spec="$SRC"
fi
"$DATA/venv/bin/pip" install --upgrade --quiet "$spec"

MODEL_SIZE="~45 МБ"
[ "$BIG_MODEL" = 1 ] && MODEL_SIZE="~1.8 ГБ"
echo "==> модель распознавания ($MODEL_SIZE, $MODEL_NAME)"
CURRENT_MODEL="$(cat "$DATA/model/.voice-player-model-name" 2>/dev/null || true)"
if [ -d "$DATA/model" ] && [ "$CURRENT_MODEL" != "$MODEL_NAME" ]; then
  echo "уже стоит другая модель ($CURRENT_MODEL) — чтобы сменить на $MODEL_NAME, удали $DATA/model и запусти install.sh заново"
elif [ ! -d "$DATA/model" ]; then
  "$DATA/venv/bin/python" - "$DATA" "$MODEL_NAME" <<'EOF'
import shutil, sys, tempfile, urllib.request, zipfile
from pathlib import Path

data, name = Path(sys.argv[1]), sys.argv[2]
with tempfile.TemporaryDirectory() as tmp:
    archive = Path(tmp) / "model.zip"
    urllib.request.urlretrieve(f"https://alphacephei.com/vosk/models/{name}.zip", archive)
    zipfile.ZipFile(archive).extractall(tmp)
    shutil.move(str(Path(tmp) / name), data / "model")
(data / "model" / ".voice-player-model-name").write_text(name)
print("модель скачана")
EOF
else
  echo "уже есть"
fi

echo "==> kdotool для переключения окон (~800 КБ)"
KDOTOOL_VER=0.3.0
KDOTOOL_SHA=2079cc1d492b6e83e04def4d9376e34fcb36a4e3bdc637c8c2ee6fa547ce90ff
if [ -x "$DATA/bin/kdotool" ] || command -v kdotool >/dev/null; then
  echo "уже есть"
else
  "$DATA/venv/bin/python" - "$DATA/bin" "$KDOTOOL_VER" "$KDOTOOL_SHA" <<'EOF' || echo "не удалось поставить kdotool, окна работать не будут"
import hashlib, io, sys, tarfile, urllib.request
from pathlib import Path

dest, ver, sha = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
url = f"https://github.com/jinliu/kdotool/releases/download/v{ver}/kdotool-{ver}-x86_64-unknown-linux-gnu.tar.gz"
data = urllib.request.urlopen(url).read()
if hashlib.sha256(data).hexdigest() != sha:
    sys.exit("kdotool: контрольная сумма не совпала")
with tarfile.open(fileobj=io.BytesIO(data)) as tar:
    member = next(m for m in tar.getmembers() if m.isfile() and Path(m.name).name == "kdotool")
    binary = tar.extractfile(member).read()
dest.mkdir(parents=True, exist_ok=True)
(dest / "kdotool").write_bytes(binary)
(dest / "kdotool").chmod(0o755)
print("kdotool установлен")
EOF
fi

echo "==> конфиги"
# свой список исполнителей не перезаписываем
[ -f "$HOME/.config/voice-player/names.txt" ] || install -Dm 644 "$SRC/names.txt" "$HOME/.config/voice-player/names.txt"
[ -f "$HOME/.config/voice-player/windows.txt" ] || install -Dm 644 "$SRC/windows.txt" "$HOME/.config/voice-player/windows.txt"
[ -f "$HOME/.config/voice-player/sinks.txt" ] || install -Dm 644 "$SRC/sinks.txt" "$HOME/.config/voice-player/sinks.txt"
if [ "$TELEGRAM" = 1 ]; then
  [ -f "$HOME/.config/voice-player/telegram.toml" ] || install -Dm 600 "$SRC/telegram.toml.example" "$HOME/.config/voice-player/telegram.toml"
fi
install -Dm 644 "$SRC/voice-player.service" "$HOME/.config/systemd/user/voice-player.service"
systemctl --user daemon-reload

cat <<EOF

Готово. Проверка вручную:
  $DATA/venv/bin/voice-player -v
EOF
[ "$ASK" = 1 ] && echo "  (при первом запуске скачается модель Whisper base, ~145 МБ)"
if [ "$TELEGRAM" = 1 ]; then
  cat <<EOF

Telegram: заполни ~/.config/voice-player/telegram.toml (api_id/api_hash с my.telegram.org,
канал Mr. Kitty, бот для поиска), затем один раз ВРУЧНУЮ из терминала (не через systemd —
это интерактивный логин с кодом подтверждения):
  $DATA/venv/bin/voice-player-telegram-sync
EOF
fi
cat <<EOF

Автозапуск:
  systemctl --user enable --now voice-player
EOF
