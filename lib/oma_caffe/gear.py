"""Your grinder and machine: what they can do, and what to set for a recipe.

data/gear.json knows ~20 grinders (scale, unit, per-method ranges) and ~20
machines (portafilter, basket, temperature control, pressure, pre-infusion,
quirks). Pick yours by name; `calibrate` shifts every grinder range so the
one you've actually dialled in lands where you say it does.
"""
import difflib
import json
import re

from . import config, paths, store

# Recipe method -> grind category in gear.json.
METHOD_CATEGORY = {
    "Espresso": "espresso", "Milk Drink": "espresso", "AeroPress": "aeropress", "V60": "v60",
    "Pour-Over": "v60", "Chemex": "chemex", "French Press": "french_press", "Immersion": "french_press",
    "Moka Pot": "moka", "Cold Brew": "cold_brew",
}
CATEGORY_LABELS = {"espresso": "Espresso", "moka": "Moka pot", "aeropress": "AeroPress", "v60": "Pour-over / V60",
                   "chemex": "Chemex", "french_press": "French press", "cold_brew": "Cold brew"}


def db():
    return store.read_json(paths.SEED / "gear.json", {"grinders": [], "machines": []})


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def search(kind, query, limit=8):
    """Fuzzy search grinders or machines by name, brand or alias."""
    items = db()[kind]
    q = _norm(query)
    if not q:
        return items[:limit]
    scored = []
    for item in items:
        names = [item["name"], item["id"], item.get("brand", "")] + item.get("aliases", [])
        best = 0.0
        qt = set(q.split())
        for n in map(_norm, names):
            if not n:
                continue
            if q == n:
                best = max(best, 2.0)
                continue
            nt = set(n.split())
            # Word overlap and whole-string similarity; a short alias inside a
            # long query ("ecm" in "ecm mechanika vi slim") only counts by
            # how much of the query it covers.
            score = max(1.5 * len(qt & nt) / len(qt | nt), difflib.SequenceMatcher(None, q, n).ratio())
            if q in n:
                score = max(score, 0.6 + 0.9 * len(q) / len(n))
            elif n in q:
                score = max(score, 0.4 + 0.6 * len(n) / len(q))
            best = max(best, score)
        if best >= 0.5:
            scored.append((best, item))
    scored.sort(key=lambda x: -x[0])
    return [i for _, i in scored[:limit]]


def find(kind, query):
    hits = search(kind, query, 1)
    return hits[0] if hits else None


def by_id(kind, gid):
    return next((g for g in db()[kind] if g["id"] == gid), None)


# ---- the user's gear --------------------------------------------------------

def _write_gear(mutate):
    def fn(data):
        return mutate(data.setdefault("gear", {}))
    return store.update_json(paths.config_file(), {}, fn)


def upgrades():
    return db().get("upgrades", [])


def compatible(machine):
    """Upgrades that physically fit this machine."""
    if not machine:
        return []
    out = []
    for u in upgrades():
        a = u.get("applies", {})
        if machine.get("group") in a.get("exclude_groups", []):
            continue
        if (a.get("any") or machine.get("group") in a.get("groups", []) or machine.get("kind") in a.get("kinds", [])
                or machine.get("id") in a.get("ids", []) or machine.get("pump") in a.get("pumps", [])):
            out.append(u)
    return out


def effective(machine, installed, basket_override=None):
    """The machine as it actually behaves with the user's upgrades fitted."""
    if not machine:
        return None
    m = json.loads(json.dumps(machine))
    names = []
    extra_tips = []
    for u in compatible(machine):
        if u["id"] not in installed:
            continue
        names.append(u["name"])
        e = u.get("effects", {})
        if "pressure" in e:
            m["pressure"]["type"] = e["pressure"]
        if "bar" in e:
            m["pressure"]["bar"] = e["bar"]
        if "preinfusion" in e:
            m["preinfusion"] = e["preinfusion"]
        if "temp" in e:
            m["temp"] = {"adjustable": True, "range": e["temp"], "default": m["temp"].get("default", 93)}
        if e.get("thermometer"):
            m["thermometer"] = True
        if e.get("gauge"):
            m["gauge"] = True
        extra_tips += u.get("tips", [])
    if basket_override:
        m["basket_g"] = float(basket_override)
    m["upgrades"] = names
    m["upgrade_tips"] = extra_tips
    return m


def mine(cfg=None):
    cfg = cfg or config.load()
    g = cfg.get("gear", {}) or {}
    base = g.get("custom") if g.get("machine") == "custom" and g.get("custom") else by_id("machines", g.get("machine", ""))
    installed = list(g.get("upgrades") or [])
    return {
        "grinder": by_id("grinders", g.get("grinder", "")),
        "base_machine": base,
        "machine": effective(base, installed, g.get("basket_g")),
        "installed": installed,
        "basket_g": g.get("basket_g"),
        "offset": float(g.get("offset", 0) or 0),
    }


def toggle_upgrade(uid, on):
    if not any(u["id"] == uid for u in upgrades()):
        raise ValueError(f"unknown upgrade {uid!r}")

    def fn(g):
        ups = [x for x in (g.get("upgrades") or []) if x != uid]
        if on:
            ups.append(uid)
        g["upgrades"] = ups
        if uid == "precision-basket" and not on:
            g.pop("basket_g", None)
        return ups
    return _write_gear(fn)


def set_basket(grams):
    def fn(g):
        if grams in (None, "", 0, "0"):
            g.pop("basket_g", None)
        else:
            g["basket_g"] = float(grams)
            if "precision-basket" not in (g.get("upgrades") or []):
                g.setdefault("upgrades", []).append("precision-basket")
    _write_gear(fn)


def set_custom(fields):
    """A machine that isn't in the database, described by hand."""
    temp_lo, temp_hi = fields.get("temp_min"), fields.get("temp_max")
    m = {
        "id": "custom", "name": fields.get("name") or "My machine", "brand": "", "kind": fields.get("kind") or "single boiler",
        "portafilter_mm": int(fields.get("portafilter_mm") or 58), "basket_g": float(fields.get("basket_g") or 18),
        "temp": {"adjustable": bool(temp_lo and temp_hi), "range": [float(temp_lo), float(temp_hi)] if temp_lo and temp_hi else None, "default": 93},
        "pressure": {"type": fields.get("pressure") or "fixed", "bar": float(fields.get("bar") or 9)},
        "preinfusion": fields.get("preinfusion") or "none", "tips": [], "aliases": [],
        "pump": fields.get("pump") or "vibration",
    }
    if fields.get("e61"):
        m["group"] = "E61"

    def fn(g):
        g["machine"] = "custom"
        g["custom"] = m
        g["upgrades"] = []
        g.pop("basket_g", None)
    _write_gear(fn)
    return m


def set_gear(kind, query):
    item = find("grinders" if kind == "grinder" else "machines", query)
    if not item:
        raise ValueError(f"no {kind} matching {query!r} (try `oma-caffe gear search {kind} <name>`)")
    config.set_value(f"gear.{kind}", item["id"])
    if kind == "grinder":
        config.set_value("gear.offset", "0")
    else:
        # A different machine: forget upgrades that don't fit it.
        fits = {u["id"] for u in compatible(item)}
        _write_gear(lambda g: g.__setitem__("upgrades", [x for x in (g.get("upgrades") or []) if x in fits]))
    return item


def clear(kind):
    config.set_value(f"gear.{kind}", "")


def calibrate(category, setting, cfg=None):
    """Your sweet spot for `category` is `setting`: shift all ranges to match."""
    gear = mine(cfg)
    g = gear["grinder"]
    if not g:
        raise ValueError("set your grinder first")
    rng = g["methods"].get(category)
    if not rng:
        raise ValueError(f"{g['name']} has no {category} range")
    mid = (rng[0] + rng[1]) / 2
    offset = round(float(setting) - mid, 2)
    config.set_value("gear.offset", str(offset))
    return offset


def ranges(gear=None):
    """Per-category [lo, hi] on the user's grinder, calibration applied and clamped."""
    gear = gear or mine()
    g = gear["grinder"]
    if not g:
        return {}
    off = gear["offset"]
    out = {}
    for cat, (lo, hi) in g["methods"].items():
        out[cat] = [_clamp(lo + off, g), _clamp(hi + off, g)]
    return out


def _clamp(v, g):
    return round(max(g["min"], min(g["max"], v)), 2)


def _fmt(v, g):
    step = g.get("step", 1)
    v = round(round(v / step) * step, 2) if step else v
    return f"{v:g}"


# Where in a category's range a recipe's grind words put it (0 = fine end).
_GRIND_WORDS = [("extra coarse", 1.0), ("medium-coarse", 0.75), ("medium coarse", 0.75), ("medium-fine", 0.3),
                ("medium fine", 0.3), ("coarser", 0.8), ("coarse", 0.85), ("finer", 0.2), ("fine", 0.25), ("medium", 0.5)]


def _position(recipe):
    text = (recipe.get("grind_setting") or "").lower()
    name = (recipe.get("name") or "").lower()
    if "turbo" in name or "allong" in name:
        return 0.9
    if "ristretto" in name:
        return 0.15
    for word, pos in _GRIND_WORDS:
        if word in text:
            return pos
    return 0.5


def recommend(recipe, cfg=None):
    """Grind setting + machine advice for one recipe on the user's gear."""
    cfg = cfg or config.load()
    gear = mine(cfg)
    g, m = gear["grinder"], gear["machine"]
    cat = METHOD_CATEGORY.get(recipe.get("method"), "v60")
    out = {"category": cat, "categoryLabel": CATEGORY_LABELS.get(cat, cat), "grind": None, "machine": [], "warnings": []}

    if g:
        rng = ranges(gear).get(cat)
        if rng:
            pos = _position(recipe)
            start = rng[0] + (rng[1] - rng[0]) * pos
            out["grind"] = {"grinder": g["name"], "unit": g["unit"], "low": _fmt(rng[0], g), "high": _fmt(rng[1], g),
                            "start": _fmt(start, g), "text": f"{_fmt(rng[0], g)}–{_fmt(rng[1], g)} {g['unit']}, start at {_fmt(start, g)}"}
        else:
            msg = f"{g['name']} can't grind for {CATEGORY_LABELS.get(cat, cat).lower()}"
            if cat == "espresso" and not g.get("espresso_capable", True):
                msg += " — try the AeroPress or moka pot recipes instead"
            out["warnings"].append(msg)

    if m and cat == "espresso":
        tips = out["machine"]
        dose = float(recipe.get("dose_g") or 0)
        basket = float(m.get("basket_g") or 0)
        if dose and basket and abs(dose - basket) >= 1.5:
            tips.append({"kind": "dose", "text": f"Your {m['name']} basket holds ~{basket:g} g — scale this recipe to {basket:g} g.",
                         "dose": basket})
        want_t = recipe.get("temp_c")
        t = m["temp"]
        if want_t:
            if t.get("adjustable") and m["kind"] != "heat exchanger":
                lo, hi = t["range"]
                setting = max(lo, min(hi, want_t))
                note = "" if setting == want_t else f" (closest your machine goes; recipe wants {want_t:g}°C)"
                tips.append({"kind": "temp", "text": f"Set brew temperature to {setting:g}°C{note}."})
            elif m["kind"] == "heat exchanger":
                if m.get("thermometer"):
                    tips.append({"kind": "temp", "text": f"Flush until the group thermometer reads ~{want_t:g}°C, then pull within 30 s."})
                elif t.get("adjustable"):
                    tips.append({"kind": "temp", "text": f"HX with PID: set ~{want_t + 25:g}°C steam-boiler target, then a short cooling flush (≈{want_t:g}°C at the group)."})
                else:
                    tips.append({"kind": "temp", "text": "Heat exchanger: cooling flush 3–5 s (until it stops spitting) right before the shot."})
            elif m["kind"] in ("single boiler",):
                tips.append({"kind": "temp", "text": f"No PID: temperature-surf for ~{want_t:g}°C (flush until the heat light cycles, wait ~30s)."})
            elif "lever" in m["kind"]:
                tips.append({"kind": "temp", "text": f"Preheat thoroughly; aim for ~{want_t:g}°C water."})
        name = (recipe.get("name") or "").lower()
        p = m["pressure"]
        flow_ctl = "Flow control / pressure profiling" in m.get("upgrades", [])
        if "turbo" in name:
            if p["type"] in ("profiling", "manual"):
                how = " with the flow-control paddle" if flow_ctl else ""
                tips.append({"kind": "pressure", "text": f"Turbo shot: cap pressure around 6 bar{how} — open fast, hold, don't go to full 9."})
            else:
                tips.append({"kind": "pressure", "text": f"Fixed {p['bar']:g} bar pump: grind coarser and let it flow fast; a flow-control or OPV mod helps turbo shots."})
        elif "allong" in name and p["type"] in ("profiling", "manual"):
            tips.append({"kind": "pressure", "text": "Allongé: low and long — ~6 bar the whole shot."})
        elif p["type"] in ("profiling", "manual"):
            tips.append({"kind": "pressure", "text": "Profile: 2–3 bar pre-infusion until the first drops, ramp to 9 bar, ease to ~6 bar for the last third."})
        pre = m.get("preinfusion")
        light = recipe.get("roast_level") == "Light"
        if pre in ("adjustable", "manual") and light:
            tips.append({"kind": "preinfusion", "text": "Light roast: try a long soft bloom (~10–15 s at 2–3 bar) before opening up."})
        elif pre == "passive" and light:
            tips.append({"kind": "preinfusion", "text": "E61 passive pre-infusion helps; for light roasts also grind a touch coarser and use a puck screen."})
        elif pre == "none" and light:
            tips.append({"kind": "preinfusion", "text": "No pre-infusion: a slightly coarser grind and puck screen help light roasts even out."})
        if m.get("gauge"):
            tips.append({"kind": "machine", "text": "Watch your gauge: 9 bar at peak; if it pins higher, grind coarser or check the OPV."})
        # Upgrade tips, then machine tips, minus repeats of the advice above.
        has_temp = any(t["kind"] == "temp" for t in tips)
        has_pressure = any(t["kind"] == "pressure" for t in tips)
        has_pre = any(t["kind"] == "preinfusion" for t in tips)
        temp_text = " ".join(t["text"] for t in tips if t["kind"] == "temp")
        for tip in m.get("upgrade_tips", []):
            if (has_pressure and "bar" in tip and "Light" not in tip) or ("Light" in tip and (has_pre or not light)) \
                    or ("thermometer" in tip.lower() and "thermometer" in temp_text):
                continue
            tips.append({"kind": "upgrade", "text": tip})
        for tip in m.get("tips", []):
            if has_temp and re.search(r"temperature-surf|cooling flush|PID|temperature", tip, re.I):
                continue
            tips.append({"kind": "machine", "text": tip})
            if sum(1 for t in tips if t["kind"] == "machine") >= 2:
                break
    return out


def next_setting(current, direction, cfg=None):
    """One step finer (-1) or coarser (+1) on the user's grinder, as text."""
    gear = mine(cfg)
    g = gear["grinder"]
    try:
        cur = float(current)
    except (TypeError, ValueError):
        return None
    if not g:
        return None
    step = g.get("step", 1) or 1
    jump = step if g["adjust"] == "stepped" else max(step, (g["max"] - g["min"]) / 50)
    return _fmt(_clamp(cur + direction * jump, g), g)


def profile(cfg=None):
    """Everything Studio's My gear card shows."""
    gear = mine(cfg)
    g, m = gear["grinder"], gear["machine"]
    out = {"grinder": g, "machine": m, "offset": gear["offset"], "disclaimer": db().get("disclaimer", ""),
           "basket_g": gear["basket_g"], "machine_kinds": db().get("machine_kinds", []),
           "upgrades": [dict(u, installed=u["id"] in gear["installed"]) for u in compatible(gear["base_machine"])]}
    if g:
        out["ranges"] = [{"category": c, "label": CATEGORY_LABELS.get(c, c), "low": lo, "high": hi}
                         for c, (lo, hi) in ranges(gear).items()]
    return out
