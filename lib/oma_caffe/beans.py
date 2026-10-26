"""beans.json: the coffees on the shelf and the grinders that dial them in."""
import re
import time

from . import paths, store


def _seed():
    return store.read_json(paths.SEED / "beans.json", {"schema": 1, "beans": [], "grinders": []})


def load():
    path = paths.beans_file()
    if not path.exists():
        with store.locked(path):
            if not path.exists():
                store.write_json(path, _seed())
    data = store.read_json(path, _seed)
    data.setdefault("beans", [])
    data.setdefault("grinders", [])
    return data


def mutate(fn):
    load()
    return store.update_json(paths.beans_file(), _seed, fn)


def active_bean(data=None):
    data = data or load()
    return next((b for b in data["beans"] if b["id"] == data.get("active_bean")), data["beans"][0] if data["beans"] else None)


def active_grinder(data=None):
    data = data or load()
    return next((g for g in data["grinders"] if g["id"] == data.get("active_grinder")), data["grinders"][0] if data["grinders"] else None)


def bean_label(bean):
    if not bean:
        return "no bean set"
    return f"{bean.get('roaster', '').strip()} {bean.get('name', '').strip()}".strip()


def grind_label(bean, grinder):
    setting = (bean or {}).get("grind_setting") or "?"
    return f"{grinder['name']} @ {setting}" if grinder else f"grind {setting}"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "bean"


def add_bean(fields, activate=True):
    def fn(data):
        base = slug(f"{fields.get('roaster', '')} {fields.get('name', '')}")
        ids = {b["id"] for b in data["beans"]}
        bid, n = base, 2
        while bid in ids:
            bid, n = f"{base}-{n}", n + 1
        bean = {"id": bid, "roaster": "", "name": "", "origin": "", "process": "", "roast_level": "Medium",
                "roast_date": "", "notes": "", "grind_setting": "", "grinder": data.get("active_grinder"),
                "added": int(time.time())}
        bean.update({k: v for k, v in fields.items() if v not in (None, "")})
        data["beans"].append(bean)
        if activate:
            data["active_bean"] = bid
        return bean
    return mutate(fn)


def set_active(bean_id):
    def fn(data):
        if not any(b["id"] == bean_id for b in data["beans"]):
            raise KeyError(bean_id)
        data["active_bean"] = bean_id
    mutate(fn)


def set_grind(setting, bean_id=None):
    def fn(data):
        bid = bean_id or data.get("active_bean")
        for b in data["beans"]:
            if b["id"] == bid:
                b["grind_setting"] = str(setting)
    mutate(fn)


def set_grinder(name, burrs=""):
    def fn(data):
        gid = slug(name)
        found = next((g for g in data["grinders"] if g["id"] == gid or g["name"].lower() == name.lower()), None)
        placeholder = next((g for g in data["grinders"] if g["id"] == "main" and g["name"] == "My grinder"), None)
        if not found and placeholder:   # first save renames the seed grinder instead of adding a second
            placeholder.update(name=name, burrs=burrs or placeholder.get("burrs", ""), notes="")
            found = placeholder
        if found:
            gid = found["id"]
        if not found:
            found = {"id": gid, "name": name, "burrs": burrs, "notes": ""}
            data["grinders"].append(found)
        elif burrs:
            found["burrs"] = burrs
        data["active_grinder"] = gid
        return found
    return mutate(fn)
