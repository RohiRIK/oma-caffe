"""Crema Light / Ristretto Dark switching and the Auto-Roast sync.

The palettes are ordinary Omarchy themes (themes/<name>/colors.toml), so one
`omarchy-theme-set` retints the terminal, bar, menus/launcher, gum TUIs,
Hyprland borders and every other templated app at once.

Auto-Roast only ever swaps between the two caffe themes: if the user picks
some other theme by hand, sync leaves it alone until they come back.
"""
import datetime as dt

from . import config, desktop, paths, state


def names(cfg=None):
    cfg = cfg or config.load()
    return cfg["theme"]["light"], cfg["theme"]["dark"]


def installed():
    light, dark = names()
    base = paths.omarchy_themes_dir()
    return (base / light).exists() and (base / dark).exists()


def wanted_for(now=None, cfg=None):
    cfg = cfg or config.load()
    t = dt.datetime.fromtimestamp(now) if now else dt.datetime.now()
    minutes = t.hour * 60 + t.minute
    light_at = config.hhmm_to_minutes(cfg["theme"]["light_at"], 7 * 60)
    dark_at = config.hhmm_to_minutes(cfg["theme"]["dark_at"], 18 * 60 + 30)
    light, dark = names(cfg)
    if light_at <= dark_at:
        return light if light_at <= minutes < dark_at else dark
    return dark if dark_at <= minutes < light_at else light


def apply(name):
    if desktop.current_theme() == name:
        return False
    desktop.set_theme(name)

    def fn(s):
        s["theme"]["applied"] = name
    state.update(fn)
    return True


def toggle():
    light, dark = names()
    target = dark if desktop.current_theme() == light else light
    apply(target)
    return target


def cycle():
    """Crema Light → Ristretto Dark → Strawberry Latte → …"""
    cfg = config.load()
    ring = [cfg["theme"]["light"], cfg["theme"]["dark"], cfg["theme"].get("cute", "strawberry-latte")]
    cur = desktop.current_theme()
    target = ring[(ring.index(cur) + 1) % len(ring)] if cur in ring else ring[0]
    apply(target)
    return target


def sync(now=None, force=False):
    """Called from the minute tick. Returns the theme switched to, or ''."""
    cfg = config.load()
    if not cfg["theme"].get("auto") and not force:
        return ""
    current = desktop.current_theme()
    ours = set(names(cfg)) | {cfg["theme"].get("cute", "strawberry-latte")}
    if current not in ours and not force:
        return ""
    target = wanted_for(now, cfg)
    return target if apply(target) else ""
