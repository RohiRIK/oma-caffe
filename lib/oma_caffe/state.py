"""state.json: today's cups, the active profile and break bookkeeping."""
import datetime as dt
import time

import os

from . import beans, caffeine, config, desktop, fun, paths, recipes, store

SCHEMA = 1


def default():
    return {"schema": SCHEMA, "profile": "espresso", "cups": [], "active_recipe": None,
            "break": {"next_due": 0, "snoozed_until": 0, "pomodoro": False, "last_shown": 0},
            "theme": {"applied": ""}, "ambience_pid": 0, "badges": {}}


def load():
    s = store.read_json(paths.state_file(), default)
    base = default()
    for key, value in base.items():
        s.setdefault(key, value)
    for key, value in base["break"].items():
        s["break"].setdefault(key, value)
    return s


def update(fn):
    def wrapped(data):
        for key, value in default().items():
            data.setdefault(key, value)
        return fn(data)
    return store.update_json(paths.state_file(), default, wrapped)


def _day_start(now):
    d = dt.datetime.fromtimestamp(now).date()
    return dt.datetime.combine(d, dt.time()).timestamp()


def cups_today(s, now=None):
    now = now or time.time()
    start = _day_start(now)
    return [c for c in s.get("cups", []) if c.get("ts", 0) >= start]


def log_cup(profile=None, mg=None, recipe_id=None, now=None):
    cfg = config.load()
    now = now or time.time()

    def fn(s):
        prof = profile or s.get("profile") or "espresso"
        pdef = cfg["profiles"].get(prof, {"label": prof, "mg": 100})
        amount = mg
        rid = recipe_id or s.get("active_recipe")
        if amount is None and recipe_id:
            r = recipes.get(recipe_id)
            amount = (r or {}).get("caffeine_mg")
        if amount is None:
            amount = pdef.get("mg", 100)
        cup = {"id": f"{int(now * 1000):x}{os.urandom(2).hex()}", "ts": int(now), "profile": prof,
               "mg": float(amount), "recipe": rid}
        s["cups"] = caffeine.prune(s.get("cups", []) + [cup], now)
        return cup

    cup = update(fn)
    store.append_jsonl(paths.history_file(), cup)
    cup["unlocked"] = check_badges(cfg)
    return cup


def _same(a, b):
    if a.get("id") and b.get("id"):
        return a["id"] == b["id"]
    return a.get("ts") == b.get("ts") and a.get("profile") == b.get("profile")


def remove_cup(cup_id=None):
    """Remove one cup (the latest when cup_id is None) from state and history,
    so stats and badges forget it too."""
    def fn(s):
        cups = s.get("cups", [])
        if not cups:
            return None
        if cup_id is None:
            return cups.pop()
        for i, c in enumerate(cups):
            if c.get("id") == cup_id or str(c.get("ts")) == str(cup_id):
                return cups.pop(i)
        return None

    gone = update(fn)
    if gone:
        removed = [False]

        def keep(r):
            if not removed[0] and _same(r, gone):
                removed[0] = True
                return False
            return True
        store.rewrite_jsonl(paths.history_file(), keep)
    return gone


def undo_cup():
    return remove_cup(None)


def check_badges(cfg=None):
    """Record newly earned badges; returns them (and celebrates each)."""
    cfg = cfg or config.load()
    earned = fun.earned(cfg)

    def fn(s):
        new = [b for b in sorted(earned) if b not in s["badges"]]
        for b in new:
            s["badges"][b] = int(time.time())
        return new

    new = update(fn)
    for b in new:
        icon, name, desc = fun.BADGES[b]
        desktop.notify(f"{icon}  Achievement unlocked: {name}", desc, glyph="󰓎")
    return new


def cycle_profile(step):
    order = config.load()["profile_order"]

    def fn(s):
        cur = s.get("profile", order[0])
        idx = order.index(cur) if cur in order else 0
        s["profile"] = order[(idx + step) % len(order)]
        return s["profile"]
    return update(fn)


def set_profile(name):
    cfg = config.load()
    if name not in cfg["profiles"]:
        raise ValueError(f"unknown profile {name!r}; known: {', '.join(cfg['profiles'])}")

    def fn(s):
        s["profile"] = name
    update(fn)
    return name


def set_active_recipe(recipe_id):
    def fn(s):
        s["active_recipe"] = recipe_id
    update(fn)


def past_cutoff(cfg, now=None):
    hour = dt.datetime.fromtimestamp(now or time.time()).hour
    return hour >= int(cfg.get("cutoff_hour", 16))


def status(now=None):
    """Everything the bar renders, in one JSON object."""
    now = now or time.time()
    cfg = config.load()
    s = load()
    today = cups_today(s, now)
    mg = caffeine.active_mg(s.get("cups", []), now, cfg["half_life_hours"])
    total_today = sum(c.get("mg", 0) for c in today)
    prof = s.get("profile", "espresso")
    pdef = cfg["profiles"].get(prof, {"label": prof})
    b = beans.load()
    bean = beans.active_bean(b)
    grinder = beans.active_grinder(b)
    all_r = recipes.all_recipes()
    top = recipes.top_rated(all_r)
    active = next((r for r in all_r if r["id"] == s.get("active_recipe")), None)
    suggestion = recipes.suggestion_of_the_day(recipes=all_r)
    lock = desktop.lock_active()
    hours_safe = caffeine.hours_until(mg, caffeine.SLEEP_SAFE_MG, cfg["half_life_hours"])
    safe_at = _when(now, now + hours_safe * 3600) if hours_safe else ""
    cutoff = past_cutoff(cfg, now)
    limit = float(cfg.get("daily_limit_mg", 400))
    nxt = s["break"].get("next_due", 0)

    lines = [
        f"Today's cups   {len(today)}  ({total_today:.0f} mg logged)",
        f"Active         {mg:.0f} mg" + (f"  · sleep-safe after {safe_at}" if safe_at else "  · sleep-safe"),
        f"Profile        {pdef.get('label', prof)}",
        f"Bean / grind   {beans.bean_label(bean)} · {beans.grind_label(bean, grinder)}",
        f"Top recipe     {_recipe_label(top)}",
    ]
    if active:
        lines.append(f"Active recipe  {active['name']}")
    if cutoff:
        lines.append(f"Past {cfg['cutoff_hour']}:00 cutoff — hydrate or decaf")
    if total_today > limit:
        lines.append(f"Over the {limit:.0f} mg daily guide")
    lines.append(f"Caffeine Lock  {'ON — idle and sleep held off' if lock else 'off'}")
    if cfg["breaks"].get("enabled") and nxt > now:
        lines.append(f"Next break     {dt.datetime.fromtimestamp(nxt).strftime('%H:%M')}")
    lines.append("")
    lines.append("L menu · M +1 cup · R lock · scroll drink")

    profiles = cfg["profiles"]
    st = fun.stats(cfg, now=now)
    mood = fun.mood(mg)
    lines.insert(0, f"{mood['face']}  feeling {mood['name']}")
    favs = sorted(all_r, key=lambda r: (r.get("status") != "favorite", -(recipes.score(r) or 0), r["name"]))
    favs = [r for r in favs if r.get("status") == "favorite" or recipes.score(r) is not None][:4]

    return {
        "cups": len(today),
        "mg": round(mg),
        "mgToday": round(total_today),
        "profile": prof,
        "profileLabel": pdef.get("label", prof),
        "profileIcon": pdef.get("icon", "☕"),
        "showMg": (cfg.get("bar") or {}).get("show_mg", True) is not False,
        "showCups": (cfg.get("bar") or {}).get("show_cups", True) is not False,
        "dailyLimit": round(limit),
        "drinks": [{"id": k, "label": v.get("label", k), "icon": v.get("icon", "☕"), "mg": v.get("mg", 0),
                    "method": v.get("method", "")} for k, v in profiles.items()],
        "todayCups": [{"id": c.get("id") or str(c["ts"]), "time": dt.datetime.fromtimestamp(c["ts"]).strftime("%H:%M"),
                       "label": profiles.get(c.get("profile"), {}).get("label", c.get("profile")),
                       "icon": profiles.get(c.get("profile"), {}).get("icon", "☕"), "mg": round(c.get("mg", 0))}
                      for c in reversed(today)],
        "stats": st,
        "level": fun.level(st["total"]),
        "badges": fun.badge_list(set(s.get("badges", {})) | fun.earned(cfg, now=now)),
        "mood": mood,
        "pun": fun.pun(len(today) + st["total"]),
        "favorites": [{"id": r["id"], "name": r["name"], "summary": recipes.summary(r),
                       "score": round(recipes.score(r), 1) if recipes.score(r) is not None else None} for r in favs],
        "nextBreakText": dt.datetime.fromtimestamp(nxt).strftime("%H:%M") if cfg["breaks"].get("enabled") and nxt > now else "",
        "lock": lock,
        "cutoff": cutoff,
        "overLimit": total_today > limit,
        "bean": beans.bean_label(bean),
        "grind": beans.grind_label(bean, grinder),
        "topRecipe": _recipe_label(top),
        "activeRecipe": active["name"] if active else "",
        "suggestion": {"id": suggestion["id"], "name": suggestion["name"], "summary": recipes.summary(suggestion)} if suggestion else None,
        "sleepSafeAt": safe_at,
        "nextBreak": nxt,
        "ambience": _ambience_on(s),
        "theme": desktop.current_theme(),
        "tooltip": "\n".join(lines),
    }


def _when(now, ts):
    """"14:06", or "tomorrow 14:06" / "Wed 14:06" once it crosses midnight."""
    d0, d1 = dt.datetime.fromtimestamp(now), dt.datetime.fromtimestamp(ts)
    days = (d1.date() - d0.date()).days
    hm = d1.strftime("%H:%M")
    return hm if days == 0 else f"tomorrow {hm}" if days == 1 else d1.strftime("%a %H:%M")


def _ambience_on(s):
    from . import ambience
    return ambience.running(s)


def _recipe_label(r):
    if not r:
        return "rate a brew to crown one"
    sc = recipes.score(r)
    return f"{r['name']}" + (f" ({sc:.1f}★)" if sc is not None else "")
