"""Thin, best-effort wrappers around the Omarchy desktop.

Every call here is fire-and-forget: a missing command or a shell that is not
running degrades to a no-op, never an exception, so the CLI behaves the same
over ssh, in a TTY or in tests (OMA_CAFFE_HEADLESS=1 silences all of it).
"""
import json
import os
import shutil
import subprocess

from . import paths

PLUGIN_ID = "rohirik.oma-caffe"
HEADLESS = os.environ.get("OMA_CAFFE_HEADLESS") == "1"
# Omarchy already floats and centers windows with this app-id.
TUI_APP_ID = "TUI.float"


def _session_env():
    """The systemd tick runs without the login shell's environment: recover
    OMARCHY_PATH (Omarchy's own fallback location) and put its bin on PATH."""
    omarchy = os.environ.get("OMARCHY_PATH") or ("/usr/share/omarchy" if os.path.isdir("/usr/share/omarchy") else "")
    if not omarchy:
        return
    os.environ["OMARCHY_PATH"] = omarchy
    bins = [os.path.join(omarchy, "bin"), os.path.expanduser("~/.local/bin")]
    path = os.environ.get("PATH", "/usr/bin:/bin").split(os.pathsep)
    os.environ["PATH"] = os.pathsep.join([b for b in bins if b not in path] + path)


_session_env()


def _have(cmd):
    return shutil.which(cmd) is not None


def _spawn(argv):
    if HEADLESS or not _have(argv[0]):
        return False
    try:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def _run(argv, timeout=3):
    if HEADLESS or not _have(argv[0]):
        return None
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def notify(title, body="", urgency="normal", glyph="󰅶"):
    if _have("omarchy-notification-send"):
        return _spawn(["omarchy-notification-send", "--app-name", "oma-caffe", "-g", glyph, "-u", urgency, title, body])
    return _spawn(["notify-send", "-a", "oma-caffe", "-u", urgency, title, body])


def osd(message, progress=None, icon="󰅶", duration=1600):
    argv = ["omarchy-osd", "-i", icon, "-m", message, "-d", str(duration)]
    if progress is not None:
        argv += ["-p", str(int(max(0, min(100, progress))))]
    return _spawn(argv)


_SOUNDS = ["/usr/share/sounds/freedesktop/stereo/{}.oga"]


def chime(kind="step"):
    name = {"step": "message", "done": "complete", "alert": "bell"}.get(kind, "message")
    for pattern in _SOUNDS:
        path = pattern.format(name)
        if os.path.exists(path):
            return _spawn(["pw-play", path]) or _spawn(["paplay", path])
    return False


def refresh_bar():
    """Ask every bar instance to re-read status (instant feedback after CLI use)."""
    return _spawn(["omarchy-shell", "-q", PLUGIN_ID, "refresh"])


def summon_overlay(payload):
    return _spawn(["omarchy-shell", "-q", "shell", "summon", PLUGIN_ID, json.dumps(payload)])


# ---- idle / caffeine lock --------------------------------------------------

def lock_active():
    return paths.stay_awake_file().exists()


def set_lock(on):
    """Drive Omarchy's own stay-awake so the idle service, the indicator and
    the Stay Awake menu item all agree with the bar."""
    if HEADLESS:
        f = paths.stay_awake_file()
        if on:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.touch()
        elif f.exists():
            f.unlink()
        return on
    if _run(["omarchy-shell", "-q", "idle", "disable" if on else "enable"]) is None or lock_active() != on:
        _run(["omarchy-toggle-idle", "stay-awake" if on else "allow-idle"])
    _spawn(["omarchy-shell", "-q", "omarchy.indicators", "refresh"])
    return lock_active()


# ---- themes ----------------------------------------------------------------

def current_theme():
    name_file = paths.omarchy_state_dir() / "current" / "theme.name"
    try:
        return name_file.read_text().strip()
    except OSError:
        return ""


def set_theme(name):
    return _spawn(["omarchy-theme-set", name])


def set_background(path):
    return _spawn(["omarchy-theme-bg-set", path])


# ---- windows ---------------------------------------------------------------

def launch_tui(*args):
    """Open `oma-caffe <args>` in a floating, theme-styled terminal."""
    inner = " ".join(_quote(a) for a in [str(paths.BIN), *args])
    script = f"source omarchy-restart-gum 2>/dev/null; {inner}"
    if _have("xdg-terminal-exec"):
        prefix = ["setsid", "uwsm-app", "--"] if _have("uwsm-app") else ["setsid"]
        return _spawn(prefix + ["xdg-terminal-exec", f"--app-id={TUI_APP_ID}", "--title=oma-caffe", "-e", "bash", "-c", script])
    return _spawn(["omarchy-launch-tui", f"--app-id={TUI_APP_ID}", "bash", "-c", script])


def _quote(s):
    import shlex
    return shlex.quote(str(s))


def fullscreen_focused():
    out = _run(["hyprctl", "activewindow", "-j"], timeout=1)
    if not out:
        return False
    try:
        return int(json.loads(out).get("fullscreen", 0)) > 0
    except (ValueError, AttributeError):
        return False


def reminder(minutes, message):
    return _spawn(["omarchy-reminder", str(int(minutes)), message])
