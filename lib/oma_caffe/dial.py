"""Shot dial-in log: one line per pull in dial.jsonl, linked to the active recipe."""
import time

from . import beans, paths, recipes, state, store

PREP = ["WDT", "Puck screen", "RDT (spritz)", "Paper filter", "Leveler", "Calibrated tamp", "Dosing cup shake"]
TASTES = ["sour", "balanced", "bitter", "thin", "astringent"]


def advise(dose, out, seconds, taste="", recipe=None, grind=None):
    """Plain-language next move for an espresso-style pull. With your grinder
    set (oma-caffe gear) and a numeric grind, it names the exact next setting."""
    from . import gear
    finer = gear.next_setting(grind, -1) if grind not in (None, "") else None
    coarser = gear.next_setting(grind, +1) if grind not in (None, "") else None
    tips = []
    target_ratio = None
    target_time = (25, 32)
    if recipe and recipe.get("dose_g") and recipe.get("yield_g"):
        target_ratio = recipe["yield_g"] / recipe["dose_g"]
        last = (recipe.get("steps") or [{}])[-1].get("at")
        if last:
            target_time = (max(5, last - 3), last + 3)
    ratio = out / dose if dose else 0
    if target_ratio and abs(ratio - target_ratio) > 0.25:
        tips.append(f"Ratio 1:{ratio:.1f} vs target 1:{target_ratio:.1f} — stop the shot at {dose * target_ratio:.0f}g.")
    fast, slow = seconds < target_time[0], seconds > target_time[1]
    if taste == "sour" or (fast and taste != "bitter"):
        tips.append("Under-extracted: grind finer" + (f" — {grind} → {finer}" if finer else "") + " (or raise temp +1°C / extend the ratio).")
    elif taste in ("bitter", "astringent") or (slow and taste != "sour"):
        tips.append("Over-extracted: grind coarser" + (f" — {grind} → {coarser}" if coarser else "") + " (or lower temp −1°C / shorten the ratio).")
    elif taste == "thin":
        tips.append("Thin body: tighten the ratio or try a slightly finer grind.")
    if not tips:
        tips.append("Dialed in — save it as your Favorite.")
    return tips


def log(entry):
    s = state.load()
    b = beans.load()
    bean = beans.active_bean(b)
    grinder = beans.active_grinder(b)
    record = {
        "ts": int(time.time()),
        "recipe": entry.get("recipe") or s.get("active_recipe"),
        "bean": entry.get("bean") or (bean or {}).get("id"),
        "roaster": entry.get("roaster") or (bean or {}).get("roaster", ""),
        "grinder": (grinder or {}).get("name", ""),
        "grind": str(entry.get("grind") or (bean or {}).get("grind_setting", "")),
        "dose_g": float(entry["dose_g"]),
        "yield_g": float(entry["yield_g"]),
        "time_s": float(entry["time_s"]),
        "prep": list(entry.get("prep") or []),
        "taste": entry.get("taste", ""),
        "notes": entry.get("notes", ""),
    }
    record["ratio"] = recipes.ratio_of(record["dose_g"], record["yield_g"])
    record["flow_gps"] = round(record["yield_g"] / record["time_s"], 2) if record["time_s"] else None
    store.append_jsonl(paths.dial_file(), record)
    if record["grind"] and bean:
        beans.set_grind(record["grind"], bean["id"])
    return record


def recent(n=10):
    return store.read_jsonl(paths.dial_file(), limit=n)


def line(r):
    when = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
    return (f"{when}  {r['dose_g']:g}g → {r['yield_g']:g}g  {r['time_s']:g}s  {r.get('ratio', '')}  "
            f"grind {r.get('grind') or '?'}  {r.get('taste') or ''}  {r.get('recipe') or ''}")
