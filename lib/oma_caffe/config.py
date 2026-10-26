"""User config: the shipped defaults with ~/.config/oma-caffe/config.json on top."""
import copy

from . import paths, store


def defaults():
    return store.read_json(paths.SEED / "config.default.json", {})


def merge(base, override):
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = value
    return out


def load():
    return merge(defaults(), store.read_json(paths.config_file(), {}))


def _coerce(raw):
    lowered = raw.strip().lower()
    if lowered in ("true", "on", "yes"):
        return True
    if lowered in ("false", "off", "no"):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def set_value(dotted, raw):
    """Set a dotted key ("breaks.interval_min") in the user override file."""
    value = _coerce(raw)

    def mutate(data):
        node = data
        parts = dotted.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        return value

    return store.update_json(paths.config_file(), {}, mutate)


def get_value(cfg, dotted, fallback=None):
    node = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return fallback
        node = node[part]
    return node


def hhmm_to_minutes(text, fallback=0):
    try:
        h, m = str(text).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return fallback
