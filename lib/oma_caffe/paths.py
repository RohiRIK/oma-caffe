"""XDG locations. Nothing in oma-caffe hardcodes an absolute path."""
import os
from pathlib import Path

APP = "oma-caffe"

# The repository (or installed copy) this module was loaded from.
ROOT = Path(__file__).resolve().parent.parent.parent
SEED = ROOT / "data"
ASSETS = ROOT / "assets"
THEMES = ROOT / "themes"
BIN = ROOT / "bin" / "oma-caffe"


def _xdg(var, fallback):
    value = os.environ.get(var, "")
    return Path(value) if value and os.path.isabs(value) else Path.home() / fallback


def config_dir():
    return _xdg("XDG_CONFIG_HOME", ".config") / APP


def data_dir():
    return _xdg("XDG_DATA_HOME", ".local/share") / APP


def runtime_dir():
    base = os.environ.get("XDG_RUNTIME_DIR") or str(data_dir())
    return Path(base) / APP


def config_file():
    return config_dir() / "config.json"


def state_file():
    return data_dir() / "state.json"


def recipes_file():
    return data_dir() / "recipes.json"


def beans_file():
    return data_dir() / "beans.json"


def history_file():
    return data_dir() / "history.jsonl"


def dial_file():
    return data_dir() / "dial.jsonl"


def feeds_file():
    return config_dir() / "feeds.json"


def omarchy_themes_dir():
    return _xdg("XDG_CONFIG_HOME", ".config") / "omarchy" / "themes"


def omarchy_state_dir():
    return _xdg("XDG_STATE_HOME", ".local/state") / "omarchy"


def stay_awake_file():
    return omarchy_state_dir() / "indicators" / "stay-awake"
