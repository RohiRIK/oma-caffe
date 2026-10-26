"""Coffee Time breaks: when to interrupt, and what the overlay says.

A systemd user timer runs `oma-caffe tick` once a minute; nothing here loops
or sleeps. Each tick decides in O(1) whether a break is due, and if so asks
the running shell to summon the overlay with a JSON payload.
"""
import datetime as dt
import time

from . import caffeine, config, desktop, paths, recipes, state


def _in_active_hours(cfg, now):
    t = dt.datetime.fromtimestamp(now)
    minutes = t.hour * 60 + t.minute
    start = config.hhmm_to_minutes(cfg["breaks"]["active_from"], 9 * 60)
    end = config.hhmm_to_minutes(cfg["breaks"]["active_until"], 19 * 60)
    return start <= minutes < end if start <= end else (minutes >= start or minutes < end)


def payload(now=None):
    now = now or time.time()
    cfg = config.load()
    s = state.load()
    mg = caffeine.active_mg(s.get("cups", []), now, cfg["half_life_hours"])
    late = state.past_cutoff(cfg, now)
    all_r = recipes.all_recipes()
    pick = recipes.suggestion_of_the_day(recipes=all_r, method="Milk Drink" if late else None)
    if late:
        headline = "Hydrate or Decaf"
        subline = f"Protect your sleep — it's past {cfg['cutoff_hour']}:00 and {mg:.0f} mg is still active."
        enter = "Log Decaf & Start Break"
    else:
        headline = "Time to dial in a shot"
        subline = f"{len(state.cups_today(s, now))} cups today · {mg:.0f} mg active. Step away for {cfg['breaks']['break_min']} minutes."
        enter = "Log Cup & Start Break"
    return {
        "mode": "decaf" if late else "caffeine",
        "headline": headline,
        "subline": subline,
        "enterLabel": enter,
        "breakMin": cfg["breaks"]["break_min"],
        "snoozeMin": cfg["breaks"]["snooze_min"],
        "recipe": {"id": pick["id"], "name": pick["name"], "summary": recipes.summary(pick),
                   "steps": [recipes.step_line(st).strip() for st in pick.get("steps", [])[:6]]} if pick else None,
        "cli": str(paths.BIN),
    }


def schedule_next(minutes, pomodoro=False, now=None):
    now = now or time.time()

    def fn(s):
        s["break"]["next_due"] = int(now + minutes * 60)
        s["break"]["pomodoro"] = pomodoro
    state.update(fn)
    return int(now + minutes * 60)


def tick(now=None):
    """Returns a short description of what happened, for logs and tests."""
    now = now or time.time()
    cfg = config.load()
    bcfg = cfg["breaks"]
    s = state.load()
    b = s["break"]

    if not bcfg.get("enabled") and not b.get("pomodoro"):
        return "disabled"
    if not b.get("next_due"):
        schedule_next(bcfg["interval_min"], now=now)
        return "scheduled"
    if now < b["next_due"] or now < b.get("snoozed_until", 0):
        return "waiting"
    if not b.get("pomodoro") and not _in_active_hours(cfg, now):
        schedule_next(bcfg["interval_min"], now=now)
        return "outside-hours"
    if desktop.fullscreen_focused():
        # A fullscreen video call or presentation: try again shortly.
        schedule_next(bcfg.get("defer_fullscreen_min", 10), pomodoro=b.get("pomodoro", False), now=now)
        return "deferred-fullscreen"

    show(now)
    return "shown"


def show(now=None):
    now = now or time.time()
    cfg = config.load()

    def fn(s):
        s["break"]["last_shown"] = int(now)
        s["break"]["next_due"] = int(now + cfg["breaks"]["interval_min"] * 60)
        s["break"]["pomodoro"] = False
        s["break"]["snoozed_until"] = 0
    state.update(fn)
    p = payload(now)
    if not desktop.summon_overlay(p):
        # No shell (TTY/ssh): fall back to a plain notification.
        desktop.notify(p["headline"], p["subline"], urgency="normal")
    return p


def snooze(minutes=None, now=None):
    now = now or time.time()
    minutes = minutes or config.load()["breaks"]["snooze_min"]

    def fn(s):
        s["break"]["snoozed_until"] = int(now + minutes * 60)
        s["break"]["next_due"] = int(now + minutes * 60)
    state.update(fn)
    return int(now + minutes * 60)


def skip(now=None):
    return schedule_next(config.load()["breaks"]["interval_min"], now=now)


def start_break(minutes=None, decaf=False):
    cfg = config.load()
    minutes = minutes or cfg["breaks"]["break_min"]
    state.log_cup(profile="decaf" if decaf else None)
    desktop.reminder(minutes, "Break's over — back to the code")
    desktop.refresh_bar()
    return minutes


def ascii_screen(now=None, frames=None):
    """Terminal rendition of the overlay: animated steam over the ASCII cup.

    Same keys as the overlay. Returns the action taken.
    """
    import shutil
    import sys

    from . import timer

    p = payload(now)
    cup = (paths.ASSETS / "ascii" / "cup.txt").read_text().rstrip("\n").splitlines()
    steam = [f.strip("\n").splitlines() for f in (paths.ASSETS / "ascii" / "steam.txt").read_text().split("---FRAME---")]
    cols = shutil.get_terminal_size((80, 24)).columns
    pad = " " * max(0, (cols - max(len(l) for l in cup)) // 2)
    hints = f"[Enter] {p['enterLabel']}   [R] Try Suggested Recipe   [S] Snooze {p['snoozeMin']}m   [Esc] Skip"
    keymap = {"\r": "enter", "\n": "enter", "r": "recipe", "R": "recipe", "s": "snooze", "S": "snooze", "\x1b": "skip", "q": "skip"}
    i = 0
    with timer._Keys() as keys:
        while frames is None or i < frames:
            out = [""] + [pad + l for l in steam[i % len(steam)]] + [pad + l for l in cup] + ["", p["headline"].center(cols), p["subline"].center(cols), ""]
            if p["recipe"]:
                out += [f"Suggested: {p['recipe']['name']} — {p['recipe']['summary']}".center(cols)]
            out += ["", hints.center(cols)]
            sys.stdout.write("\033[H" + "\033[K\n".join(out) + "\033[J")
            sys.stdout.flush()
            action = keymap.get(keys.read(0.35), "")
            i += 1
            if action:
                break
        else:
            return ""
    if action == "enter":
        start_break(p["breakMin"], decaf=p["mode"] == "decaf")
    elif action == "recipe" and p["recipe"]:
        desktop.launch_tui("brew", p["recipe"]["id"])
    elif action == "snooze":
        snooze(p["snoozeMin"])
    elif action == "skip":
        skip()
    return action
