"""recipes.json: the normalized recipe database, experiments and scorecards."""
import copy
import datetime as dt
import hashlib
import re
import time

from . import paths, store

STATUSES = {"to_try": "To Try", "testing": "Testing", "favorite": "Dialed-In Favorite"}
METHODS = ["Espresso", "V60", "Chemex", "AeroPress", "Milk Drink", "Pour-Over", "French Press", "Moka Pot", "Cold Brew"]
ROASTS = ["Light", "Medium", "Dark"]
SCORES = ["acidity", "sweetness", "body", "bitterness", "overall"]


def _seed():
    return store.read_json(paths.SEED / "recipes.json", {"schema": 1, "recipes": []})


def ensure_db():
    """First run copies the seed database into the XDG data dir."""
    path = paths.recipes_file()
    if not path.exists():
        with store.locked(path):
            if not path.exists():
                store.write_json(path, _seed())


def load():
    ensure_db()
    db = store.read_json(paths.recipes_file(), _seed)
    db.setdefault("recipes", [])
    return db


def all_recipes():
    return load()["recipes"]


def get(recipe_id):
    for r in all_recipes():
        if r.get("id") == recipe_id:
            return r
    return None


def mutate(fn):
    ensure_db()
    return store.update_json(paths.recipes_file(), _seed, fn)


def _find(db, recipe_id):
    for r in db["recipes"]:
        if r.get("id") == recipe_id:
            return r
    raise KeyError(f"no recipe {recipe_id!r}")


# ---- normalization ---------------------------------------------------------

def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s[:48] or "recipe"


def unique_id(base, existing):
    candidate, n = base, 2
    while candidate in existing:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def ratio_of(dose, out):
    if not dose or not out:
        return ""
    r = out / dose
    return f"1:{r:.1f}".replace(".0", "") if abs(r - round(r)) < 0.05 else f"1:{r:.1f}"


def output_g(recipe):
    """The recipe's output: yield for espresso-style, water for brewed."""
    return recipe.get("yield_g") or recipe.get("water_ml") or 0


def normalize(raw):
    """Coerce any partial recipe (import, hand-written) into the full schema."""
    r = {
        "id": raw.get("id") or slug(raw.get("name", "recipe")),
        "name": str(raw.get("name") or "Untitled recipe").strip(),
        "method": raw.get("method") or "Pour-Over",
        "author": raw.get("author", ""),
        "source": raw.get("source", ""),
        "roast_level": raw.get("roast_level") or "Medium",
        "bean_profile": raw.get("bean_profile", ""),
        "dose_g": _num(raw.get("dose_g")),
        "yield_g": _num(raw.get("yield_g")),
        "water_ml": _num(raw.get("water_ml")),
        "ratio": raw.get("ratio", ""),
        "temp_c": _num(raw.get("temp_c")),
        "grind_setting": str(raw.get("grind_setting") or ""),
        "steps": [],
        "tags": list(raw.get("tags") or []),
        "status": raw.get("status") if raw.get("status") in STATUSES else "to_try",
        "parent": raw.get("parent"),
        "tweaks": dict(raw.get("tweaks") or {}),
        "ratings": list(raw.get("ratings") or []),
        "notes": raw.get("notes", ""),
    }
    if raw.get("caffeine_mg") is not None:
        r["caffeine_mg"] = _num(raw.get("caffeine_mg"))
    for step in raw.get("steps") or []:
        if isinstance(step, str):
            step = parse_step_text(step)
        if not step:
            continue
        s = {"at": int(_num(step.get("at")) or 0), "kind": step.get("kind") or "pour",
             "label": str(step.get("label") or step.get("kind") or "Step")}
        if step.get("target_g") is not None:
            s["target_g"] = _num(step.get("target_g"))
        if step.get("note"):
            s["note"] = step["note"]
        r["steps"].append(s)
    r["steps"].sort(key=lambda s: s["at"])
    if not r["ratio"] and r["dose_g"]:
        r["ratio"] = ratio_of(r["dose_g"], output_g(r))
    return r


def _num(value):
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else round(f, 2)


_STEP_RE = re.compile(r"^\s*(?:(\d+):(\d{2})|(\d+)\s*s)\s*[-–—:]?\s*(.+)$")


def parse_step_text(text):
    """'0:45 - First pour to 200g' -> {'at': 45, 'label': ..., 'target_g': 200}."""
    m = _STEP_RE.match(text)
    if not m:
        return None
    at = int(m.group(1)) * 60 + int(m.group(2)) if m.group(1) else int(m.group(3))
    label = m.group(4).strip()
    step = {"at": at, "label": label, "kind": guess_kind(label)}
    g = re.search(r"(\d+(?:\.\d+)?)\s*g\b", label)
    if g:
        step["target_g"] = float(g.group(1))
    return step


def guess_kind(label):
    l = label.lower()
    for kind, words in (("swirl", ["swirl", "spin"]), ("stir", ["stir", "shake"]), ("press", ["press", "plunge"]),
                        ("stop", ["stop", "done", "remove", "finish", "drawdown"]), ("preinfuse", ["pre-infus", "preinfus"]),
                        ("wait", ["wait", "steep", "rest"]), ("shot", ["pull", "shot", "bar"])):
        if any(w in l for w in words):
            return kind
    return "pour"


# ---- scaling -------------------------------------------------------------

def scale(recipe, new_dose):
    """Return a copy scaled to new_dose: output and every pour weight follow.

    Timings are kept: they describe the extraction curve, and a 10-20% dose
    change moves drawdown by seconds, not stages.
    """
    r = copy.deepcopy(recipe)
    old = float(recipe.get("dose_g") or 0)
    new = float(new_dose)
    if old <= 0 or new <= 0:
        raise ValueError("dose must be positive")
    k = new / old
    r["dose_g"] = _num(round(new, 1))
    for key in ("yield_g", "water_ml"):
        if r.get(key):
            r[key] = _num(round(r[key] * k))
    for step in r.get("steps", []):
        if step.get("target_g") is not None:
            step["target_g"] = _num(round(step["target_g"] * k))
    if r.get("caffeine_mg"):
        r["caffeine_mg"] = _num(round(r["caffeine_mg"] * k))
    r["scaled_from"] = old
    return r


def scale_to_output(recipe, new_output):
    out = output_g(recipe)
    if not out:
        raise ValueError("recipe has no yield or water target")
    return scale(recipe, float(recipe["dose_g"]) * float(new_output) / out)


# ---- experiments -----------------------------------------------------------

def clone(recipe_id, tweaks, name=None):
    """Branch a recipe. tweaks: {"grind": "-0.5", "temp_c": "+2", "dose_g": "20", ...}."""
    def fn(db):
        parent = _find(db, recipe_id)
        child = copy.deepcopy(parent)
        applied = {}
        for key, raw in tweaks.items():
            raw = str(raw).strip()
            if key in ("grind", "grind_setting"):
                child["grind_setting"] = _tweak_text(parent.get("grind_setting", ""), raw)
                applied["grind"] = raw
            elif key in ("temp_c", "dose_g", "yield_g", "water_ml"):
                base = float(parent.get(key) or 0)
                val = base + float(raw) if raw[:1] in "+-" else float(raw)
                if key == "dose_g":
                    scaled = scale(child, val)
                    child.update({k: scaled[k] for k in ("dose_g", "yield_g", "water_ml", "steps") if k in scaled})
                else:
                    child[key] = _num(val)
                applied[key] = raw
        child["ratio"] = ratio_of(child.get("dose_g"), output_g(child)) or child.get("ratio", "")
        child["id"] = unique_id(f"{parent['id']}-exp", {r["id"] for r in db["recipes"]})
        child["name"] = name or f"{parent['name']} ({_describe(applied)})"
        child["parent"] = parent["id"]
        child["tweaks"] = applied
        child["ratings"] = []
        child["status"] = "testing"
        if parent.get("status") == "to_try":
            parent["status"] = "testing"
        db["recipes"].append(child)
        return child
    return mutate(fn)


def _tweak_text(grind, delta):
    """Shift the first number in a grind description, or append the delta."""
    m = re.search(r"-?\d+(?:\.\d+)?", grind or "")
    if m and delta[:1] in "+-":
        val = float(m.group(0)) + float(delta)
        txt = f"{val:g}"
        return grind[:m.start()] + txt + grind[m.end():]
    if delta[:1] in "+-":
        return f"{grind} ({delta} steps)".strip()
    return delta


def _describe(applied):
    if not applied:
        return "branch"
    names = {"grind": "grind", "temp_c": "°C", "dose_g": "g dose", "yield_g": "g out", "water_ml": "ml"}
    return ", ".join(f"{v}{names.get(k, k)}" if k != "grind" else f"grind {v}" for k, v in applied.items())


def rate(recipe_id, scores, notes=""):
    record = {"ts": int(time.time())}
    for key in SCORES:
        if key in scores and scores[key] is not None:
            val = int(scores[key])
            if not 1 <= val <= 5:
                raise ValueError(f"{key} must be 1-5")
            record[key] = val
    record["notes"] = notes

    def fn(db):
        r = _find(db, recipe_id)
        r.setdefault("ratings", []).append(record)
        if r.get("status") == "to_try":
            r["status"] = "testing"
        return record
    return mutate(fn)


def set_status(recipe_id, status):
    if status not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")

    def fn(db):
        _find(db, recipe_id)["status"] = status
    mutate(fn)


def add(raw):
    def fn(db):
        r = normalize(raw)
        r["id"] = unique_id(r["id"], {x["id"] for x in db["recipes"]})
        db["recipes"].append(r)
        return r
    return mutate(fn)


def delete(recipe_id):
    def fn(db):
        before = len(db["recipes"])
        db["recipes"] = [r for r in db["recipes"] if r.get("id") != recipe_id]
        return before != len(db["recipes"])
    return mutate(fn)


def score(recipe):
    """Mean 'overall' (falling back to the mean of all axes except bitterness)."""
    vals = []
    for rating in recipe.get("ratings") or []:
        if "overall" in rating:
            vals.append(rating["overall"])
        else:
            axes = [rating[k] for k in ("acidity", "sweetness", "body") if k in rating]
            if axes:
                vals.append(sum(axes) / len(axes))
    return sum(vals) / len(vals) if vals else None


def top_rated(recipes=None):
    recipes = recipes if recipes is not None else all_recipes()
    scored = [(score(r), r) for r in recipes]
    scored = [(s, r) for s, r in scored if s is not None]
    if scored:
        return max(scored, key=lambda x: (x[0], x[1].get("status") == "favorite"))[1]
    favs = [r for r in recipes if r.get("status") == "favorite"]
    return favs[0] if favs else None


def suggestion_of_the_day(day=None, recipes=None, method=None):
    """Deterministic per day, drawn from the untested (To Try) queue first."""
    recipes = recipes if recipes is not None else all_recipes()
    day = day or dt.date.today().isoformat()
    pool = [r for r in recipes if r.get("status") == "to_try"] or [r for r in recipes if r.get("status") == "testing"] or recipes
    if method:
        pool = [r for r in pool if r.get("method") == method] or pool
    if not pool:
        return None
    pool = sorted(pool, key=lambda r: r["id"])
    idx = int(hashlib.sha1(day.encode()).hexdigest(), 16) % len(pool)
    return pool[idx]


# ---- presentation ----------------------------------------------------------

def clock(seconds):
    seconds = int(seconds)
    if seconds >= 3600:
        return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}"
    return f"{seconds // 60}:{seconds % 60:02d}"


def step_line(step):
    target = f" → {step['target_g']:g}g" if step.get("target_g") is not None else ""
    return f"{clock(step['at']):>6}  {step['label']}{target}"


def summary(recipe):
    out = output_g(recipe)
    unit = "g out" if recipe.get("yield_g") else "g water"
    bits = [recipe.get("method", "")]
    if recipe.get("dose_g"):
        bits.append(f"{recipe['dose_g']:g}g in")
    if out:
        bits.append(f"{out:g}{unit}")
    if recipe.get("ratio"):
        bits.append(recipe["ratio"])
    if recipe.get("temp_c"):
        bits.append(f"{recipe['temp_c']:g}°C")
    return " · ".join(b for b in bits if b)


def describe(recipe):
    lines = [recipe["name"], summary(recipe)]
    if recipe.get("author"):
        lines.append(f"by {recipe['author']}")
    lines.append(f"Roast {recipe.get('roast_level', '?')} · {recipe.get('bean_profile') or 'any bean'}")
    lines.append(f"Grind {recipe.get('grind_setting') or '—'}")
    lines.append(f"Status {STATUSES.get(recipe.get('status'), recipe.get('status'))}")
    if recipe.get("parent"):
        lines.append(f"Branch of {recipe['parent']} ({_describe(recipe.get('tweaks') or {})})")
    s = score(recipe)
    if s is not None:
        lines.append(f"Score {s:.1f}/5 over {len(recipe.get('ratings', []))} brews")
    lines.append("")
    lines.extend(step_line(st) for st in recipe.get("steps", []))
    if recipe.get("source"):
        lines += ["", f"Source: {recipe['source']}"]
    return "\n".join(lines)


def search(query, recipes):
    q = query.lower().split()
    def hay(r):
        return " ".join(str(r.get(k, "")) for k in ("name", "method", "author", "bean_profile", "roast_level", "source")).lower() + " " + " ".join(r.get("tags", []))
    return [r for r in recipes if all(t in hay(r) for t in q)]
