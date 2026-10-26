#!/usr/bin/env bash
# End-to-end: drive every CLI command the bar panel and Studio buttons call,
# in a throwaway HOME with desktop side effects silenced. Exits non-zero on the
# first failing step and prints a summary.
set -uo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
CLI="$ROOT/bin/oma-caffe"
SANDBOX="$(mktemp -d -t oma-caffe-e2e.XXXXXX)"
trap 'rm -rf "$SANDBOX"' EXIT
export HOME="$SANDBOX" XDG_CONFIG_HOME="$SANDBOX/.config" XDG_DATA_HOME="$SANDBOX/.local/share" \
  XDG_STATE_HOME="$SANDBOX/.local/state" XDG_CACHE_HOME="$SANDBOX/.cache" OMA_CAFFE_HEADLESS=1
# Reuse already-downloaded gallery thumbnails so the run stays offline-friendly.
REAL_CACHE="${REAL_XDG_CACHE_HOME:-$(getent passwd "$(id -un)" | cut -d: -f6)/.cache}/oma-caffe/wallpapers"
[ -d "$REAL_CACHE" ] && mkdir -p "$XDG_CACHE_HOME/oma-caffe" && cp -r "$REAL_CACHE" "$XDG_CACHE_HOME/oma-caffe/"

pass=0 fail=0
step() {  # step "label" args...  (expects exit 0)
  local label="$1"; shift
  if out="$("$CLI" "$@" 2>&1)"; then pass=$((pass + 1)); printf '  ✓ %s\n' "$label"
  else fail=$((fail + 1)); printf '  ✗ %s\n    $ oma-caffe %s\n%s\n' "$label" "$*" "$(sed 's/^/    /' <<<"$out" | tail -8)"; fi
}
json() {  # json "label" jq-filter args...  (expects valid JSON matching the filter)
  local label="$1" filter="$2"; shift 2
  if out="$("$CLI" "$@" 2>&1)" && jq -e "$filter" >/dev/null 2>&1 <<<"$out"; then pass=$((pass + 1)); printf '  ✓ %s\n' "$label"
  else fail=$((fail + 1)); printf '  ✗ %s\n    $ oma-caffe %s  (filter %s)\n%s\n' "$label" "$*" "$filter" "$(head -c 600 <<<"$out" | sed 's/^/    /')"; fi
}

echo "▸ status & bar"
json "status --json" '.cups >= 0 and (.mood|length>0) and .level' status --json
step "log (+1 / middle-click)" log
step "log --profile" log --profile espresso
json "two cups today" '.cups == 2' status --json
json "cups list" 'length == 2' cups list --json
cup=$("$CLI" cups list --json | jq -r '.[0].id')
step "cups rm (✕ in TODAY)" cups rm "$cup"
step "undo" undo
json "back to zero" '.cups == 0' status --json
step "profile next (wheel)" profile next
step "profile prev (wheel)" profile prev
step "lock toggle on" lock toggle
step "lock toggle off" lock toggle
step "stats" stats
step "badges" badges

echo "▸ drinks"
json "drinks list" 'length >= 20' drinks list --json
step "drinks add" drinks add "E2E Cortado" --mg 90 --method espresso --icon "☕"
did=$("$CLI" drinks list --json | jq -r '.[] | select(.label=="E2E Cortado") | .id')
[ -n "$did" ] && step "drinks remove" drinks remove "$did" || { fail=$((fail+1)); echo "  ✗ added drink not found"; }

echo "▸ recipes (Studio → Recipes)"
json "lab list" 'length >= 10' lab list --json
rid=classic-espresso-1-2
step "lab active" lab active "$rid"
step "lab rate" lab rate "$rid" --acidity 3 --sweetness 4 --body 4 --bitterness 2 --overall 5 --notes "e2e"
clone_out=$("$CLI" lab clone "$rid" --grind -0.5 --temp +2 --dose 19 --name "E2E branch" 2>&1); cid=$(awk '{print $1; exit}' <<<"$clone_out")
json "lab clone created" ".[] | select(.id==\"$cid\") | .dose_g == 19" lab list --json
step "lab status" lab status "$cid" favorite
step "lab adopt (library)" lab adopt "$("$ROOT/bin/oma-caffe" lab research --json 2>/dev/null | jq -r '.[0].id' 2>/dev/null || echo x)" || true
step "lab delete" lab delete "$cid"
json "gear recommend (no gear)" 'type=="object"' gear recommend "$rid" --json
tmp="$SANDBOX/r.txt"; printf 'Sunday V60\n15g coffee, 250g water at 94°C\n0:00 - Bloom to 45g\n0:45 - Pour to 250g\n3:00 - Done\n' >"$tmp"
json "lab import --dry-run" '.[0].method == "V60"' lab import "$tmp" --dry-run --json
json "lab import" 'length == 1' lab import "$tmp" --json
json "feed list" 'type=="array"' lab feed list --json

echo "▸ brew & dial-in"
step "cue" cue "Bloom to 45g" --kind pour --progress 10
step "log --recipe (Brew done)" log --recipe "$rid"
json "dial log + tips" '.tips|length>0' dial --dose 18 --yield 36 --time 22 --taste sour --grind 10 --prep wdt,rdt --notes e2e --recipe "$rid" --json
json "dial --list" 'length >= 1' dial --list 12 --json

echo "▸ beans"
json "beans list" 'type=="object"' beans list --json
step "beans grind" beans grind 12
step "beans grinder" beans grinder "E2E Grinder" --burrs "64mm flat"

echo "▸ gear (Settings → My gear)"
json "gear search grinder" '.[0].id == "eureka-mignon-specialita"' gear search grinder eureka specialita --json
json "gear search machine" '.[0].id == "ecm-mechanika-vi-slim"' gear search machine ecm mechanika vi slim --json
step "gear set grinder" gear set grinder eureka-mignon-specialita
step "gear set machine" gear set machine ecm-mechanika-vi-slim
step "gear upgrade add" gear upgrade add flow-control
step "gear basket" gear basket 18
step "gear calibrate" gear calibrate espresso 9
json "gear show" '.machine.id == "ecm-mechanika-vi-slim" and ([.upgrades[]|select(.installed)|.id]|sort) == ["flow-control","precision-basket"]' gear show --json
json "recommend uses flow control" '[.machine[].text]|join(" ")|test("flow")' gear recommend turbo-shot-1-3 --json
step "gear upgrade remove" gear upgrade remove flow-control
step "config gear.offset reset" config set gear.offset 0
step "gear custom" gear custom "name=E2E Machine" kind=single-boiler pressure=vibratory preinfusion=none e61=0 portafilter_mm=58 basket_g=18 temp_min=88 temp_max=96
json "custom machine active" '.machine.name == "E2E Machine"' gear show --json
step "gear clear" gear clear machine

echo "▸ settings"
json "config show" '.bar and .breaks and .theme' config show --json
step "config bar.show_mg" config set bar.show_mg false
step "config bar.show_cups" config set bar.show_cups true
step "config breaks.interval_min" config set breaks.interval_min 60
step "theme auto on" theme auto on
step "theme auto off" theme auto off
step "ambience toggle" ambience toggle
step "ambience toggle off" ambience toggle

echo "▸ breaks"
step "break now" break now
step "break start" break start 5
step "break snooze" break snooze 15
step "break skip" break skip
step "break pomodoro" break pomodoro 25
step "tick" tick

echo "▸ wallpapers"
json "wallpapers list" 'length >= 25 and all(.[]; .name and .license)' wallpapers list --json
step "doctor" doctor

echo
echo "e2e: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
