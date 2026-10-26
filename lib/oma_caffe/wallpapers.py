"""The wallpaper gallery: curated coffee photos and paintings.

data/wallpapers.json lists the catalog (Wikimedia Commons, public domain /
CC0 / CC BY-SA, credited). Thumbnails are cached under ~/.cache/oma-caffe;
adding one to a theme downloads the full image, crops it to 16:9 (never
upscales) and drops it in ~/.config/omarchy/backgrounds/<theme>/, where
Omarchy's own background cycling picks it up.
"""
import concurrent.futures
import json
import os
import shutil
import subprocess
import urllib.parse
from pathlib import Path

from . import desktop, paths, store

UA = "oma-caffe/0.1 (https://omarchy.org; wallpaper gallery)"
THEMES = ["crema-light", "ristretto-dark", "strawberry-latte"]
DEFAULTS = {
    "ristretto-dark": ["dark-cup-pencil", "fireplace-book", "latte-macro", "bulb-bokeh", "night-cafe"],
    "crema-light": ["anker-still-life", "beans-and-cup", "black-coffee-top", "latte-succulent", "bag-of-coffee"],
    "strawberry-latte": ["snowy-window-cup", "white-espresso", "vangogh-still-life", "hands-latte", "cappuccinos-cake"],
}


def catalog():
    return store.read_json(paths.SEED / "wallpapers.json", {"wallpapers": []})["wallpapers"]


def get(wid):
    w = next((w for w in catalog() if w["id"] == wid), None)
    if not w:
        raise KeyError(f"no wallpaper {wid!r} (see `oma-caffe wallpapers`)")
    return w


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "oma-caffe" / "wallpapers"


def user_bg_dir(theme):
    return paths.omarchy_themes_dir().parent / "backgrounds" / theme


def thumb_path(wid):
    return cache_dir() / f"{wid}.jpg"


def _urls(items, width):
    """Commons file URLs (scaled to `width`) for catalog items, batched."""
    out = {}
    for k in range(0, len(items), 25):
        batch = items[k:k + 25]
        q = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "imageinfo",
                                    "titles": "|".join("File:" + w["title"] for w in batch),
                                    "iiprop": "url", "iiurlwidth": width})
        res = subprocess.run(["curl", "-fsSL", "-A", UA, f"https://commons.wikimedia.org/w/api.php?{q}"],
                             capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            continue
        data = json.loads(res.stdout)
        norm = {n["to"]: n["from"] for n in data["query"].get("normalized", [])}
        for p in data["query"]["pages"].values():
            if "imageinfo" not in p:
                continue
            title = norm.get(p["title"], p["title"])[5:]
            ii = p["imageinfo"][0]
            out[title] = ii.get("thumburl") or ii["url"]
    return out


def _download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".part.jpg")
    subprocess.run(["curl", "-fsSL", "-A", UA, "-o", str(tmp), url], check=True, timeout=120)
    return tmp


def ensure_thumbs():
    """Fetch any missing gallery thumbnails (in parallel). Returns how many."""
    missing = [w for w in catalog() if not thumb_path(w["id"]).exists()]
    if not missing:
        return 0
    urls = _urls(missing, 640)

    def one(w):
        url = urls.get(w["title"])
        if not url:
            return False
        tmp = _download(url, thumb_path(w["id"]))
        subprocess.run(["magick", str(tmp), "-auto-orient", "-gravity", "center", "-crop", "16:9", "+repage",
                        "-resize", "480x270^", "-extent", "480x270", "-strip", "-quality", "82",
                        str(thumb_path(w["id"]))], check=True)
        tmp.unlink()
        return True

    with concurrent.futures.ThreadPoolExecutor(6) as ex:
        return sum(1 for ok in ex.map(one, missing) if ok)


def _render(w, dest):
    """Full image -> 16:9 centre crop, shrink-only to 3840 wide, JPEG."""
    url = _urls([w], 3840 if w["width"] > 3840 else w["width"]).get(w["title"])
    if not url:
        raise RuntimeError(f"couldn't reach Wikimedia for {w['name']}")
    tmp = _download(url, dest)
    subprocess.run(["magick", str(tmp), "-auto-orient", "-gravity", "center", "-crop", "16:9", "+repage",
                    "-resize", "3840x2160>", "-strip", "-quality", "90", str(dest)], check=True)
    tmp.unlink()
    return dest


def _bundled(theme):
    d = paths.THEMES / theme / "backgrounds"
    return {p.stem.split("-", 1)[1]: p for p in d.glob("*.jpg") if "-" in p.stem} if d.exists() else {}


def installed_in(wid):
    """Themes whose rotation already includes this wallpaper."""
    out = []
    for t in THEMES:
        if (user_bg_dir(t) / f"oma-caffe-{wid}.jpg").exists() or wid in _bundled(t):
            out.append(t)
    return out


def path_for(wid, theme):
    user = user_bg_dir(theme) / f"oma-caffe-{wid}.jpg"
    if user.exists():
        return user
    return _bundled(theme).get(wid)


def add(wid, theme):
    w = get(wid)
    existing = path_for(wid, theme)
    if existing:
        return existing
    return _render(w, user_bg_dir(theme) / f"oma-caffe-{wid}.jpg")


def remove(wid, theme):
    p = user_bg_dir(theme) / f"oma-caffe-{wid}.jpg"
    if p.exists():
        p.unlink()
        return True
    return False


def set_now(wid):
    """Use it right now: add to the current theme (if it's ours) and set it."""
    theme = desktop.current_theme()
    target = theme if theme in THEMES else None
    if target:
        path = add(wid, target)
    else:
        path = _render(get(wid), cache_dir() / "full" / f"{wid}.jpg") if not (cache_dir() / "full" / f"{wid}.jpg").exists() \
            else cache_dir() / "full" / f"{wid}.jpg"
    desktop.set_background(str(path))
    return path


def listing():
    out = []
    for w in catalog():
        tp = thumb_path(w["id"])
        out.append(dict(w, thumb=str(tp) if tp.exists() else "", themes=installed_in(w["id"])))
    return out


def build_defaults():
    """Rebuild the repo's bundled theme backgrounds + previews + CREDITS.md."""
    cat = {w["id"]: w for w in catalog()}
    lines = ["# Wallpaper credits", "", "From Wikimedia Commons; licences as listed on each file page.", ""]
    for theme, ids in DEFAULTS.items():
        d = paths.THEMES / theme / "backgrounds"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        lines.append(f"## {theme}")
        for n, wid in enumerate(ids, 1):
            w = cat[wid]
            dest = _render(w, d / f"{n}-{wid}.jpg")
            lines.append(f"- `{dest.name}` — {w['name']} · [{w['title']}]({w['page']}) · {w['artist'] or 'unknown'} · {w['license']}")
        first = sorted(d.glob("*.jpg"))[0]
        subprocess.run(["magick", str(first), "-resize", "960x540", str(paths.THEMES / theme / "preview.png")], check=True)
        lines.append("")
    lines += ["## Gallery", "", "Everything in Studio → Wallpapers:", ""]
    lines += [f"- {w['name']} · [{w['title']}]({w['page']}) · {w['artist'] or 'unknown'} · {w['license']}" for w in catalog()]
    (paths.THEMES / "CREDITS.md").write_text("\n".join(lines) + "\n")
