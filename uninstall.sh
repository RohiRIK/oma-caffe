#!/bin/bash
# Reverse install.sh. Your recipes, ratings and logs in ~/.local/share/oma-caffe
# are kept unless you pass --purge.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ID="rohirik.oma-caffe"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
PURGE=0
[[ ${1:-} == "--purge" ]] && PURGE=1

# Remove $1 only if it is a symlink into this checkout.
unlink_ours() {
  [[ -L $1 && $(readlink -f "$1") == "$REPO"* ]] && rm "$1" && echo "removed $1"
  return 0
}

"$REPO/bin/oma-caffe" ambience off >/dev/null 2>&1 || true
"$REPO/bin/oma-caffe" lock off >/dev/null 2>&1 || true

if command -v systemctl >/dev/null; then
  systemctl --user disable --now oma-caffe-tick.timer >/dev/null 2>&1 || true
  unlink_ours "$CONFIG_HOME/systemd/user/oma-caffe-tick.timer"
  unlink_ours "$CONFIG_HOME/systemd/user/oma-caffe-tick.service"
  systemctl --user daemon-reload || true
fi

hypr_main="$CONFIG_HOME/hypr/hyprland.lua"
if [[ -f $hypr_main ]] && grep -q 'require("hypr.oma-caffe")' "$hypr_main"; then
  cp "$hypr_main" "$hypr_main.bak.$(date +%s)"
  sed -i '/^require("hypr.oma-caffe")$/d' "$hypr_main"
  echo "removed require from $hypr_main"
fi
unlink_ours "$CONFIG_HOME/hypr/oma-caffe.lua"
command -v hyprctl >/dev/null && [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] && hyprctl reload >/dev/null || true

# Leave the user on a theme that will still exist.
current=$(cat "${XDG_STATE_HOME:-$HOME/.local/state}/omarchy/current/theme.name" 2>/dev/null || true)
if [[ $current == crema-light || $current == ristretto-dark || $current == strawberry-latte ]] && command -v omarchy-theme-set >/dev/null; then
  omarchy-theme-set tokyo-night || true
fi
for theme in crema-light ristretto-dark strawberry-latte; do
  unlink_ours "$CONFIG_HOME/omarchy/themes/$theme"
done

if command -v python3 >/dev/null && [[ -f $CONFIG_HOME/omarchy/shell.json ]]; then
  python3 - "$CONFIG_HOME/omarchy/shell.json" "$PLUGIN_ID" <<'PY'
import json, sys
path, pid = sys.argv[1], sys.argv[2]
cfg = json.load(open(path))
layout = cfg.get("bar", {}).get("layout", {})
changed = False
for section, entries in layout.items():
    kept = [e for e in entries if e.get("id") != pid]
    changed |= len(kept) != len(entries)
    layout[section] = kept
if changed:
    json.dump(cfg, open(path, "w"), indent=2)
    print(f"removed {pid} from the bar")
PY
fi

unlink_ours "$CONFIG_HOME/omarchy/plugins/$PLUGIN_ID"
unlink_ours "$HOME/.local/bin/oma-caffe"

if ((PURGE)); then
  rm -rf "$DATA_HOME/oma-caffe" "$CONFIG_HOME/oma-caffe"
  echo "purged data and config"
else
  echo "kept your data in $DATA_HOME/oma-caffe (use --purge to delete)"
fi
