"""Interactive guided brew timer.

Renders a live progress view in the terminal and cues every step through a
chime, the Omarchy OSD and a notification, so the cue lands even when the
terminal is behind the browser. Keys: space pause/resume, n skip to the next
step, q quit. Brews longer than an hour (cold brew) hand their steps to
`omarchy-reminder` instead of holding a terminal open overnight.
"""
import os
import select
import sys
import termios
import time
import tty

from . import config, desktop, recipes

GLYPH = {"pour": "󰖌", "swirl": "󰑓", "stir": "󰑐", "press": "󰁅", "stop": "󰓛", "wait": "󰔟", "preinfuse": "󰖌", "shot": "󰅶"}
BAR_WIDTH = 46
LONG_BREW_S = 3600

ACC = "\033[1;33m"
OK = "\033[32m"
DIM = "\033[2m"
RST = "\033[0m"


def cue_text(step):
    target = f" → {step['target_g']:g}g" if step.get("target_g") is not None else ""
    return f"{step['label']}{target}"


def total_time(recipe):
    steps = recipe.get("steps") or []
    if not steps:
        return 0
    last = steps[-1]["at"]
    # The final step is a moment (stop/remove); give non-stop finales 30s.
    return last if steps[-1].get("kind") == "stop" else last + 30


def bar(frac, width=BAR_WIDTH):
    frac = max(0.0, min(1.0, frac))
    full = int(frac * width)
    return "━" * full + ("╸" if full < width else "") + DIM + "━" * max(0, width - full - 1) + RST


def current_index(steps, elapsed):
    idx = -1
    for i, s in enumerate(steps):
        if s["at"] <= elapsed:
            idx = i
    return idx


def frame(recipe, elapsed, paused):
    steps = recipe["steps"]
    total = max(1, total_time(recipe))
    idx = current_index(steps, elapsed)
    lines = [f"  {ACC}{recipe['name']}{RST}", f"  {DIM}{recipes.summary(recipe)} · grind {recipe.get('grind_setting') or '—'}{RST}", ""]
    lines.append(f"  {bar(elapsed / total)}  {recipes.clock(elapsed)} / {recipes.clock(total)}" + ("   ⏸ paused" if paused else ""))
    lines.append("")
    if idx >= 0:
        lines.append(f"  {ACC}NOW{RST}   {GLYPH.get(steps[idx]['kind'], '•')}  {cue_text(steps[idx])}")
        if steps[idx].get("note"):
            lines.append(f"        {DIM}{steps[idx]['note']}{RST}")
    if idx + 1 < len(steps):
        nxt = steps[idx + 1]
        lines.append(f"  NEXT  {GLYPH.get(nxt['kind'], '•')}  {cue_text(nxt)}   in {recipes.clock(max(0, nxt['at'] - elapsed))}")
    lines.append("")
    for i, s in enumerate(steps):
        mark, color = ("✓", OK) if i < idx else (("▶", ACC) if i == idx else ("·", DIM))
        lines.append(f"  {color}{mark} {recipes.step_line(s)}{RST}")
    lines += ["", f"  {DIM}[space] pause  [n] next step  [q] quit{RST}"]
    return "\n".join(lines)


def cue(step, progress, cfg, final=False):
    cues = cfg.get("cues", {})
    text = cue_text(step)
    if cues.get("sound", True):
        desktop.chime("done" if final else "step")
    if cues.get("osd", True):
        desktop.osd(text, progress=progress, icon=GLYPH.get(step.get("kind"), "󰅶"))
    if cues.get("notify", True) and (final or step.get("kind") in ("pour", "stop", "press", "shot")):
        desktop.notify("Brew done" if final else text, step.get("note", ""), glyph=GLYPH.get(step.get("kind"), "󰅶"))


class _Keys:
    """cbreak stdin for single-key controls; restores the tty on exit."""

    def __enter__(self):
        self.fd = sys.stdin.fileno() if sys.stdin.isatty() else None
        if self.fd is not None:
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        sys.stdout.write("\033[?25l\033[2J")
        return self

    def read(self, timeout):
        if self.fd is None:
            time.sleep(timeout)
            return ""
        ready, _, _ = select.select([self.fd], [], [], timeout)
        return os.read(self.fd, 8).decode(errors="ignore") if ready else ""

    def __exit__(self, *exc):
        if self.fd is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()


def run(recipe, speed=1.0):
    """Run the timer. Returns True if the brew finished, False if quit."""
    cfg = config.load()
    steps = recipe.get("steps") or []
    if not steps:
        print("This recipe has no steps to time.")
        return False
    total = total_time(recipe)
    if total > LONG_BREW_S:
        return schedule_long(recipe)

    fired = set()
    start = time.monotonic()
    paused_at = None
    offset = 0.0
    with _Keys() as keys:
        while True:
            now = time.monotonic()
            elapsed = ((paused_at or now) - start) * speed + offset
            idx = current_index(steps, elapsed)
            for i in range(idx + 1):
                if i not in fired:
                    fired.add(i)
                    final = i == len(steps) - 1 and steps[i].get("kind") == "stop"
                    cue(steps[i], min(100, 100 * elapsed / max(1, total)), cfg, final=final)
            # Home + per-line clear repaints in place without the flicker of a full clear.
            text = frame(recipe, int(elapsed), paused_at is not None).replace("\n", "\033[K\n")
            sys.stdout.write("\033[H" + text + "\033[K\033[J")
            sys.stdout.flush()
            if elapsed >= total:
                if steps[-1].get("kind") != "stop":
                    desktop.chime("done")
                    desktop.notify("Brew done", recipe["name"])
                return True
            key = keys.read(0.2)
            if key in ("q", "\x1b"):
                return False
            if key == " ":
                if paused_at is None:
                    paused_at = time.monotonic()
                else:
                    start += time.monotonic() - paused_at
                    paused_at = None
            if key == "n" and idx + 1 < len(steps):
                offset += steps[idx + 1]["at"] - elapsed


def schedule_long(recipe):
    steps = recipe["steps"]
    print(f"{recipe['name']} runs {recipes.clock(total_time(recipe))}; scheduling reminders instead of a live timer.")
    first = steps[0]
    cue(first, 0, config.load())
    for s in steps[1:]:
        minutes = max(1, round(s["at"] / 60))
        desktop.reminder(minutes, f"{recipe['name']}: {cue_text(s)}")
        print(f"  reminder in {recipes.clock(s['at'])}: {cue_text(s)}")
    return True
