"""Stats, streaks, barista levels, achievements, moods and puns.

Everything is derived from history.jsonl (every cup ever, minus undone ones)
and dial.jsonl, so stats survive state.json's 48-hour pruning.
"""
import datetime as dt
import random
import time
from collections import Counter

from . import paths, store

PUNS = [
    "Espresso yourself! ☕",
    "Bean there, done that.",
    "You mocha me very happy.",
    "Thanks a latte!",
    "Brew-tiful choice.",
    "Deja brew — again?",
    "Sip happens.",
    "Rise and grind ✨",
    "That's the bean's knees.",
    "Hello darkness, my old roast.",
    "Procaffeinating like a pro.",
    "Brewing up something good.",
    "Fresh pot, fresh plot.",
    "Life happens, coffee helps.",
    "Grounds for celebration! 🎉",
]

# Kawaii mood by active caffeine.
MOODS = [
    (0, "(－_－) zzZ", "sleepy"),
    (40, "(˘ᵕ˘)", "cozy"),
    (120, "(◕‿◕)", "happy"),
    (250, "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧", "buzzing"),
    (400, "(⊙_⊙;)", "jittery"),
    (600, "ヽ(°〇°)ﾉ", "vibrating"),
]

LEVELS = [
    (0, "Decaf Dabbler"),
    (5, "Bean Sprout"),
    (15, "Home Brewer"),
    (35, "Latte Artist"),
    (70, "Barista"),
    (120, "Head Barista"),
    (200, "Roast Master"),
    (320, "Caffeine Wizard"),
    (500, "Legend of the Crema"),
]

# id: (emoji, name, description)
BADGES = {
    "first-sip": ("🌱", "First Sip", "Log your first cup"),
    "triple": ("🔱", "Triple Threat", "3 cups in one day"),
    "early-bird": ("🐦", "Early Bird", "A cup before 7:00"),
    "night-owl": ("🦉", "Night Owl", "A cup after 22:00"),
    "explorer": ("🧭", "Bean Explorer", "Try 5 different drinks"),
    "connoisseur": ("🎩", "Connoisseur", "Try 10 different drinks"),
    "method-head": ("⚗️", "Method Head", "Use 4 brew methods"),
    "streak-3": ("🔥", "On Fire", "3-day streak"),
    "streak-7": ("🌋", "Volcanic", "7-day streak"),
    "tea-time": ("🍵", "Tea Time", "Log a tea"),
    "decaf-hero": ("😇", "Decaf Hero", "Choose decaf after the cutoff"),
    "dialer": ("🎯", "Dial Master", "Log 5 dial-in shots"),
    "jitter": ("🫨", "Jitter Bug", "Go over the daily guide"),
    "century": ("💯", "Century", "100 cups all-time"),
}


def history():
    return store.read_jsonl(paths.history_file())


def _day(ts):
    return dt.date.fromtimestamp(ts)


def mood(mg):
    face, name = MOODS[0][1], MOODS[0][2]
    for threshold, f, n in MOODS:
        if mg >= threshold:
            face, name = f, n
    return {"face": face, "name": name}


def level(total):
    idx = 0
    for i, (need, _) in enumerate(LEVELS):
        if total >= need:
            idx = i
    need, name = LEVELS[idx]
    nxt = LEVELS[idx + 1][0] if idx + 1 < len(LEVELS) else None
    progress = 1.0 if nxt is None else (total - need) / (nxt - need)
    return {"level": idx + 1, "name": name, "progress": round(progress, 3),
            "toNext": (nxt - total) if nxt else 0, "nextName": LEVELS[idx + 1][1] if nxt else ""}


def streak(days_with_cups, today=None):
    today = today or dt.date.today()
    day = today if today in days_with_cups else today - dt.timedelta(days=1)
    n = 0
    while day in days_with_cups:
        n += 1
        day -= dt.timedelta(days=1)
    return n


def stats(cfg, cups=None, now=None):
    cups = cups if cups is not None else history()
    now = now or time.time()
    today = _day(now)
    by_day = Counter(_day(c["ts"]) for c in cups)
    mg_by_day = Counter()
    for c in cups:
        mg_by_day[_day(c["ts"])] += c.get("mg", 0)
    week = []
    for i in range(6, -1, -1):
        d = today - dt.timedelta(days=i)
        week.append({"day": d.strftime("%a")[:2], "cups": by_day.get(d, 0), "mg": round(mg_by_day.get(d, 0)), "today": i == 0})
    drinks = Counter(c.get("profile", "?") for c in cups)
    top = drinks.most_common(1)[0][0] if drinks else ""
    profiles = cfg["profiles"]
    methods = {profiles.get(p, {}).get("method", "") for p in drinks} - {"", "Any"}
    week_cups = sum(w["cups"] for w in week)
    hours = Counter(dt.datetime.fromtimestamp(c["ts"]).hour for c in cups)
    return {
        "week": week,
        "weekCups": week_cups,
        "weekMg": sum(w["mg"] for w in week),
        "avgPerDay": round(week_cups / 7, 1),
        "streak": streak(set(by_day), today),
        "total": len(cups),
        "topDrink": profiles.get(top, {}).get("label", top),
        "topDrinkIcon": profiles.get(top, {}).get("icon", "☕"),
        "drinksTried": len(drinks),
        "methodsTried": len(methods),
        "peakHour": f"{hours.most_common(1)[0][0]:02d}:00" if hours else "",
    }


def earned(cfg, cups=None, now=None):
    """Set of badge ids the history qualifies for right now."""
    cups = cups if cups is not None else history()
    now = now or time.time()
    st = stats(cfg, cups, now)
    by_day = Counter(_day(c["ts"]) for c in cups)
    mg_by_day = Counter()
    for c in cups:
        mg_by_day[_day(c["ts"])] += c.get("mg", 0)
    profiles = cfg["profiles"]
    cutoff = int(cfg.get("cutoff_hour", 16))
    hours = [dt.datetime.fromtimestamp(c["ts"]).hour for c in cups]
    got = set()
    if cups:
        got.add("first-sip")
    if by_day and max(by_day.values()) >= 3:
        got.add("triple")
    if any(h < 7 for h in hours):
        got.add("early-bird")
    if any(h >= 22 for h in hours):
        got.add("night-owl")
    if st["drinksTried"] >= 5:
        got.add("explorer")
    if st["drinksTried"] >= 10:
        got.add("connoisseur")
    if st["methodsTried"] >= 4:
        got.add("method-head")
    if st["streak"] >= 3:
        got.add("streak-3")
    if st["streak"] >= 7:
        got.add("streak-7")
    if any(profiles.get(c.get("profile"), {}).get("method") == "Tea" for c in cups):
        got.add("tea-time")
    if any(c.get("profile") == "decaf" and dt.datetime.fromtimestamp(c["ts"]).hour >= cutoff for c in cups):
        got.add("decaf-hero")
    if len(store.read_jsonl(paths.dial_file())) >= 5:
        got.add("dialer")
    if mg_by_day and max(mg_by_day.values()) > float(cfg.get("daily_limit_mg", 400)):
        got.add("jitter")
    if len(cups) >= 100:
        got.add("century")
    return got


def badge_list(unlocked):
    return [{"id": bid, "icon": icon, "name": name, "desc": desc, "unlocked": bid in unlocked}
            for bid, (icon, name, desc) in BADGES.items()]


def pun(seed=None):
    rng = random.Random(seed)
    return rng.choice(PUNS)
