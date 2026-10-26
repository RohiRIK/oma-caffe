"""Recipe research: the curated library, URL/file import and community feeds.

Three input shapes are understood, tried in order:
  1. oma-caffe JSON (a recipe, a list of recipes, or {"recipes"|"library": [...]})
  2. schema.org Recipe JSON-LD embedded in a web page
  3. free text — doses, water, temperature, ratio and "m:ss" step lines are
     pulled out with patterns, and whatever is missing stays blank for the
     user to fill in rather than being guessed.
"""
import html
import json
import re
import subprocess
import urllib.request

from . import paths, recipes, store

UA = "oma-caffe/0.1 (+https://omarchy.org)"


def library():
    return store.read_json(paths.SEED / "library.json", {"library": []}).get("library", [])


def research(query):
    """Search the curated library and every synced feed recipe."""
    pool = library() + feed_recipes()
    hits = recipes.search(query, pool) if query.strip() else pool
    owned = {r["id"] for r in recipes.all_recipes()}
    return [dict(r, in_db=r["id"] in owned) for r in hits]


# ---- fetching --------------------------------------------------------------

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(4_000_000).decode(resp.headers.get_content_charset() or "utf-8", "replace")
    except Exception:
        # Some hosts reject urllib's TLS fingerprint; curl is always on Omarchy.
        out = subprocess.run(["curl", "-fsSL", "--max-time", str(timeout), "-A", UA, url],
                             capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(f"could not fetch {url}: {out.stderr.strip() or out.returncode}")
        return out.stdout


def from_source(source):
    """Return normalized recipes parsed from a URL, a file path, or raw text."""
    if re.match(r"^https?://", source):
        text = fetch(source)
        origin = source
    else:
        try:
            with open(source, encoding="utf-8") as fh:
                text = fh.read()
            origin = source
        except OSError:
            text, origin = source, ""
    found = parse(text, origin)
    if not found:
        raise ValueError("no recipe found — try pasting the recipe text instead")
    return found


def parse(text, origin=""):
    as_json = _try_json(text)
    if as_json is not None:
        items = _oma_items(as_json)
        if items:
            return [recipes.normalize(dict(i, source=i.get("source") or origin)) for i in items]
        ld = _ld_recipes(as_json)
        if ld:
            return [from_jsonld(r, origin) for r in ld]
    ld = []
    for block in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", text, re.S | re.I):
        data = _try_json(html.unescape(block).strip())
        if data is not None:
            ld.extend(_ld_recipes(data))
    if ld:
        return [from_jsonld(r, origin) for r in ld]
    plain = _strip_html(text) if "<" in text and ">" in text else text
    guess = from_text(plain, origin)
    return [guess] if guess else []


def _try_json(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _oma_items(data):
    if isinstance(data, dict):
        for key in ("recipes", "library"):
            if isinstance(data.get(key), list):
                return [r for r in data[key] if isinstance(r, dict) and "dose_g" in r]
        return [data] if "dose_g" in data and "name" in data else []
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict) and "dose_g" in r and "name" in r]
    return []


def _ld_recipes(data):
    out = []
    if isinstance(data, list):
        for item in data:
            out.extend(_ld_recipes(item))
    elif isinstance(data, dict):
        kind = data.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "Recipe" in kinds:
            out.append(data)
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in data:
                out.extend(_ld_recipes(data[key]))
    return out


def _strip_html(text):
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"[ \t]+", " ", text))


def _ld_text(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        if value.get("@type") == "HowToSection":
            return [t for item in value.get("itemListElement", []) for t in _ld_text(item)]
        return [value.get("text") or value.get("name") or ""]
    if isinstance(value, list):
        return [t for v in value for t in _ld_text(v)]
    return []


def from_jsonld(data, origin=""):
    ingredients = " \n".join(_ld_text(data.get("recipeIngredient")))
    instructions = _ld_text(data.get("recipeInstructions"))
    body = "\n".join([data.get("name", ""), data.get("description", ""), ingredients] + instructions)
    r = from_text(body, origin) or recipes.normalize({"name": data.get("name")})
    r["name"] = html.unescape(str(data.get("name") or r["name"])).strip()
    author = data.get("author")
    if isinstance(author, list):
        author = author[0] if author else ""
    r["author"] = author.get("name", "") if isinstance(author, dict) else str(author or "")
    r["source"] = origin or data.get("url", "")
    if not r["steps"]:
        r["steps"] = _numbered_steps(instructions)
    return r


def _numbered_steps(lines):
    """Instructions without timestamps become untimed steps 30s apart."""
    steps = []
    for i, line in enumerate(l for l in lines if l.strip()):
        line = re.sub(r"\s+", " ", line).strip()
        step = {"at": i * 30, "label": line[:80], "kind": recipes.guess_kind(line)}
        g = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|grams?|ml)\b", line, re.I)
        if g and step["kind"] == "pour":
            step["target_g"] = float(g.group(1))
        steps.append(step)
    return steps


_METHOD_WORDS = [("AeroPress", r"aero\s?press"), ("Chemex", r"chemex"), ("V60", r"\bv60\b|hario"),
                 ("Cold Brew", r"cold\s?brew"), ("French Press", r"french press|cafeti[eè]re"),
                 ("Moka Pot", r"moka"), ("Milk Drink", r"latte|cappuccino|flat white|cortado|milk"),
                 ("Espresso", r"espresso|shot|portafilter"), ("Pour-Over", r"pour[\s-]?over|kalita|origami|orea")]


def from_text(text, origin=""):
    t = text.replace(" ", " ")
    low = t.lower()
    method = next((m for m, pat in _METHOD_WORDS if re.search(pat, low)), "Pour-Over")

    dose = _first(r"(\d+(?:\.\d+)?)\s*(?:g|grams?)\s*(?:of\s+)?(?:ground\s+|whole\s+bean\s+)?(?:coffee|beans|grounds|dose)", low) \
        or _first(r"dose[:\s]+(\d+(?:\.\d+)?)\s*g", low)
    water = _first(r"(\d+(?:\.\d+)?)\s*(?:g|grams?|ml)\s*(?:of\s+)?(?:hot\s+|filtered\s+|cold\s+)?water", low)
    yld = _first(r"(?:yield|out|beverage|output)[:\s]+(\d+(?:\.\d+)?)\s*g", low) \
        or _first(r"(\d+(?:\.\d+)?)\s*g\s*(?:yield|out\b|in the cup|beverage)", low)
    temp = _first(r"(\d{2,3})\s*°\s*c\b", low) or _first(r"(\d{2,3})\s*(?:degrees\s*)?c(?:elsius)?\b", low)
    if temp is None:
        f = _first(r"(\d{3})\s*°?\s*f\b", low)
        temp = round((f - 32) * 5 / 9) if f else None
    ratio = re.search(r"\b1\s*:\s*(\d+(?:\.\d+)?)", low)
    grind = re.search(r"((?:extra[\s-]?)?(?:fine|medium[\s-]?fine|medium[\s-]?coarse|medium|coarse))\s+grind|grind[:\s]+([^\n.,;]{2,40})", low)

    if dose and not (water or yld) and ratio:
        out = dose * float(ratio.group(1))
        if method in ("Espresso", "Milk Drink"):
            yld = out
        else:
            water = out
    if method in ("Espresso", "Milk Drink") and water and not yld:
        yld, water = water, None

    steps = []
    for line in t.splitlines():
        step = recipes.parse_step_text(line.strip("•*- \t"))
        if step:
            steps.append(step)

    if not dose and not steps:
        return None
    name = next((l.strip() for l in t.splitlines() if l.strip()), "Imported recipe")[:70]
    return recipes.normalize({
        "name": name, "method": method, "source": origin, "dose_g": dose, "water_ml": water, "yield_g": yld,
        "temp_c": temp, "ratio": f"1:{ratio.group(1)}" if ratio else "",
        "grind_setting": (grind.group(1) or grind.group(2)).strip().capitalize() if grind else "",
        "steps": steps, "tags": ["imported"],
    })


def _first(pattern, text):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


# ---- importing into the db -------------------------------------------------

def import_recipes(items, status="to_try"):
    added = []
    for item in items:
        item = dict(item)
        item.pop("in_db", None)
        item["status"] = status
        added.append(recipes.add(item))
    return added


def adopt(library_id):
    """Copy a library/feed recipe into the user's database."""
    for r in library() + feed_recipes():
        if r["id"] == library_id:
            return import_recipes([dict(r, id=r["id"].removeprefix("lib-"))])[0]
    raise KeyError(f"no library recipe {library_id!r}")


# ---- community feeds -------------------------------------------------------

def feeds():
    return store.read_json(paths.feeds_file(), {"feeds": []})


def add_feed(url):
    def fn(data):
        data.setdefault("feeds", [])
        if not any(f["url"] == url for f in data["feeds"]):
            data["feeds"].append({"url": url, "recipes": [], "synced": 0})
    store.update_json(paths.feeds_file(), {"feeds": []}, fn)


def remove_feed(url):
    def fn(data):
        data["feeds"] = [f for f in data.get("feeds", []) if f["url"] != url]
    store.update_json(paths.feeds_file(), {"feeds": []}, fn)


def sync_feeds():
    import time
    report = []
    for feed in feeds().get("feeds", []):
        try:
            found = parse(fetch(feed["url"]), feed["url"])
            report.append((feed["url"], len(found), ""))
        except Exception as exc:  # one dead feed must not stop the rest
            found = None
            report.append((feed["url"], 0, str(exc)))
        if found is None:
            continue

        def fn(data, url=feed["url"], found=found):
            for f in data.get("feeds", []):
                if f["url"] == url:
                    f["recipes"] = [dict(r, id="feed-" + r["id"]) for r in found]
                    f["synced"] = int(time.time())
        store.update_json(paths.feeds_file(), {"feeds": []}, fn)
    return report


def feed_recipes():
    return [r for f in feeds().get("feeds", []) for r in f.get("recipes", [])]
