#!/bin/bash
# oma-caffe installer. Everything is linked from this checkout into XDG
# locations, so `git pull` updates the install and uninstall.sh reverses it.
#
#   ./install.sh                 full install
#   ./install.sh --no-hypr       skip the Hyprland blur/float snippet
#   ./install.sh --no-timer      skip the minute tick (no breaks / Auto-Roast)
#   ./install.sh --no-bar        don't put the widget on the bar
#   ./install.sh --no-restart    don't restart the Omarchy shell at the end

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ID="rohirik.oma-caffe"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="$HOME/.local/bin"

DO_HYPR=1 DO_TIMER=1 DO_BAR=1 DO_RESTART=1
for arg in "$@"; do
  case "$arg" in
    --no-hypr) DO_HYPR=0 ;;
    --no-timer) DO_TIMER=0 ;;
    --no-bar) DO_BAR=0 ;;
    --no-restart) DO_RESTART=0 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1;33m󰅶\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!\033[0m %s\n' "$*" >&2; }

# Link $1 -> $2, refusing to replace anything that isn't already ours.
link() {
  local src=$1 dst=$2
  mkdir -p "$(dirname "$dst")"
  if [[ -L $dst ]]; then
    ln -sfn "$src" "$dst"
  elif [[ -e $dst ]]; then
    warn "$dst exists and is not a symlink; leaving it alone"
    return 1
  else
    ln -s "$src" "$dst"
  fi
}

# ---- dependencies -------------------------------------------------------------
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || { echo "oma-caffe needs Python 3.9+" >&2; exit 1; }
missing=()
for tool in gum mpv curl notify-send; do
  command -v "$tool" >/dev/null || missing+=("$tool")
done
if ((${#missing[@]})); then
  warn "optional tools missing: ${missing[*]} (install with: omarchy pkg add ${missing[*]})"
fi

# ---- CLI, plugin, themes ------------------------------------------------------
chmod +x "$REPO/bin/oma-caffe"
link "$REPO/bin/oma-caffe" "$BIN_DIR/oma-caffe"
say "CLI → $BIN_DIR/oma-caffe"

# Installed with `omarchy plugin add`, the checkout already *is* the plugin dir.
if [[ $(readlink -f "$CONFIG_HOME/omarchy/plugins/$PLUGIN_ID") != "$REPO" ]]; then
  link "$REPO" "$CONFIG_HOME/omarchy/plugins/$PLUGIN_ID"
fi
say "Shell plugin → $CONFIG_HOME/omarchy/plugins/$PLUGIN_ID"

for theme in crema-light ristretto-dark strawberry-latte; do
  link "$REPO/themes/$theme" "$CONFIG_HOME/omarchy/themes/$theme" && say "Theme → $theme"
done

# ---- data -------------------------------------------------------------------
mkdir -p "$CONFIG_HOME/oma-caffe" "$DATA_HOME/oma-caffe"
[[ -f $CONFIG_HOME/oma-caffe/config.json ]] || echo '{}' > "$CONFIG_HOME/oma-caffe/config.json"
OMA_CAFFE_HEADLESS=1 "$REPO/bin/oma-caffe" status >/dev/null   # seeds recipes.json / beans.json
say "Data in $DATA_HOME/oma-caffe (recipes.json, beans.json, state.json)"

# ---- Hyprland: overlay blur + floating windows --------------------------------
if ((DO_HYPR)) && [[ -f $CONFIG_HOME/hypr/hyprland.lua ]]; then
  link "$REPO/hypr/oma-caffe.lua" "$CONFIG_HOME/hypr/oma-caffe.lua"
  hypr_main="$CONFIG_HOME/hypr/hyprland.lua"
  if ! grep -q 'require("hypr.oma-caffe")' "$hypr_main"; then
    backup="$hypr_main.bak.$(date +%s)"
    cp "$hypr_main" "$backup"
    printf '\nrequire("hypr.oma-caffe")\n' >> "$hypr_main"
    if command -v hyprctl >/dev/null && [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]]; then
      hyprctl reload >/dev/null
      sleep 0.5
      errors=$(hyprctl configerrors 2>/dev/null | grep -v '^\s*$' || true)
      if [[ -n $errors ]]; then
        warn "Hyprland reported config errors; restoring $backup"
        printf '%s\n' "$errors" >&2
        cp "$backup" "$hypr_main"
        hyprctl reload >/dev/null
      else
        say "Hyprland snippet loaded (break overlay blur)"
      fi
    fi
  fi
fi

# ---- minute tick: breaks + Auto-Roast ------------------------------------------
if ((DO_TIMER)) && command -v systemctl >/dev/null; then
  for unit in oma-caffe-tick.service oma-caffe-tick.timer; do
    link "$REPO/systemd/$unit" "$CONFIG_HOME/systemd/user/$unit"
  done
  systemctl --user daemon-reload
  systemctl --user enable --now oma-caffe-tick.timer >/dev/null 2>&1 && say "Tick timer enabled (oma-caffe-tick.timer)"
fi

# ---- bar --------------------------------------------------------------------
if ((DO_BAR)) && command -v omarchy-bar >/dev/null; then
  if ! grep -q "\"$PLUGIN_ID\"" "$CONFIG_HOME/omarchy/shell.json" 2>/dev/null; then
    omarchy-bar put "$PLUGIN_ID" --section right --index 1 && say "Bar widget added (right section)"
  fi
fi

# The shell doesn't follow symlinked plugin dirs for hot reload; a restart
# loads the new code.
if ((DO_RESTART)) && command -v omarchy-restart-shell >/dev/null && [[ -n ${WAYLAND_DISPLAY:-} ]]; then
  omarchy-restart-shell >/dev/null 2>&1 || true
  say "Omarchy shell restarted"
fi

cat <<EOF

  ☕  oma-caffe is ready. Powered by caffeine and questionable life choices.

  Bar        left: log cup · middle: quick brew · right: Caffeine Lock · scroll: profile
  Lab        oma-caffe lab          (recipes, research, experiments, guided timer)
  Dial-in    oma-caffe dial
  Themes     oma-caffe theme light | dark | toggle | auto on
  Breaks     oma-caffe break now    (every 90 min, 09:00–19:00 by default; see oma-caffe break status)
  Ambience   oma-caffe ambience
  Health     oma-caffe doctor

EOF
