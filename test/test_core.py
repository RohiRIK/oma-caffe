"""Core behaviour: caffeine math, ratio scaling, import parsing, breaks, races."""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

SANDBOX = tempfile.mkdtemp(prefix="oma-caffe-test-")
os.environ.update(HOME=SANDBOX, XDG_CONFIG_HOME="", XDG_DATA_HOME="", XDG_STATE_HOME="",
                  XDG_RUNTIME_DIR="", OMA_CAFFE_HEADLESS="1")

from oma_caffe import breaks, caffeine, config, importer, recipes, state  # noqa: E402


def at(hour, minute=0):
    return dt.datetime.combine(dt.date.today(), dt.time(hour, minute)).timestamp()


class CaffeineTest(unittest.TestCase):
    def test_half_life(self):
        cups = [{"ts": 0, "mg": 200}]
        self.assertAlmostEqual(caffeine.active_mg(cups, 5 * 3600, 5), 100, places=6)
        self.assertAlmostEqual(caffeine.active_mg(cups, 10 * 3600, 5), 50, places=6)

    def test_future_cups_ignored_and_sum(self):
        cups = [{"ts": 0, "mg": 100}, {"ts": 3600, "mg": 100}, {"ts": 99999, "mg": 500}]
        expected = 100 * 0.5 ** (2 / 5) + 100 * 0.5 ** (1 / 5)
        self.assertAlmostEqual(caffeine.active_mg(cups, 7200, 5), expected, places=6)

    def test_hours_until_sleep_safe(self):
        self.assertAlmostEqual(caffeine.hours_until(200, 50, 5), 10)
        self.assertEqual(caffeine.hours_until(40, 50, 5), 0)


class ScaleTest(unittest.TestCase):
    def test_dose_change_rescales_yield_and_pours(self):
        r = recipes.normalize(json.loads((ROOT / "data/recipes.json").read_text())["recipes"][4])  # 4:6
        s = recipes.scale(r, 30)
        self.assertEqual(s["dose_g"], 30)
        self.assertEqual(s["water_ml"], 450)
        self.assertEqual([st.get("target_g") for st in s["steps"] if "target_g" in st], [75, 180, 270, 360, 450])
        self.assertEqual([st["at"] for st in s["steps"]], [st["at"] for st in r["steps"]])

    def test_espresso_18_to_20(self):
        r = recipes.get("classic-espresso-1-2")
        s = recipes.scale(r, 20)
        self.assertEqual(s["yield_g"], 40)
        self.assertEqual(s["steps"][-1]["target_g"], 40)
        self.assertEqual(s["ratio"], "1:2")

    def test_scale_to_output(self):
        s = recipes.scale_to_output(recipes.get("hoffmann-ultimate-v60"), 500)
        self.assertEqual(s["dose_g"], 30)

    def test_clone_tweaks(self):
        child = recipes.clone("turbo-shot-1-3", {"temp_c": "+2", "dose_g": "20"})
        self.assertEqual(child["temp_c"], 95)
        self.assertEqual(child["yield_g"], 60)
        self.assertEqual(child["parent"], "turbo-shot-1-3")
        self.assertEqual(child["status"], "testing")

    def test_rating_and_top(self):
        recipes.rate("chemex-classic", {"acidity": 3, "sweetness": 4, "body": 4, "bitterness": 2, "overall": 4})
        recipes.rate("kasuya-4-6", {"overall": 5})
        self.assertEqual(recipes.top_rated()["id"], "kasuya-4-6")
        with self.assertRaises(ValueError):
            recipes.rate("kasuya-4-6", {"overall": 6})


class ImportTest(unittest.TestCase):
    def test_freeform(self):
        text = """My Sunday V60
        15g coffee, 250g water at 94°C, medium-fine grind
        0:00 - Bloom to 45g
        0:45 - First pour to 150g
        1:30 - Final pour to 250g
        3:00 - Done"""
        r = importer.parse(text)[0]
        self.assertEqual((r["method"], r["dose_g"], r["water_ml"], r["temp_c"]), ("V60", 15, 250, 94))
        self.assertEqual([s["at"] for s in r["steps"]], [0, 45, 90, 180])
        self.assertEqual(r["steps"][1]["target_g"], 150)
        self.assertEqual(r["steps"][-1]["kind"], "stop")

    def test_jsonld(self):
        page = """<html><script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Recipe",
        "name":"Bright AeroPress","author":{"@type":"Person","name":"A. Barista"},
        "recipeIngredient":["17g coffee","230g water at 88°C"],
        "recipeInstructions":[{"@type":"HowToStep","text":"Bloom with 50g water"},{"@type":"HowToStep","text":"Press slowly"}]}]}</script></html>"""
        r = importer.parse(page, "https://example.test/r")[0]
        self.assertEqual(r["name"], "Bright AeroPress")
        self.assertEqual(r["author"], "A. Barista")
        self.assertEqual((r["method"], r["dose_g"], r["water_ml"], r["temp_c"]), ("AeroPress", 17, 230, 88))
        self.assertEqual(len(r["steps"]), 2)

    def test_espresso_ratio_only(self):
        r = importer.parse("Morning espresso: 18g coffee, 1:2.5 ratio, 30s")[0]
        self.assertEqual((r["method"], r["yield_g"]), ("Espresso", 45))

    def test_oma_json_roundtrip(self):
        data = json.dumps({"recipes": [recipes.get("allonge-1-4")]})
        self.assertEqual(importer.parse(data)[0]["name"], "Allongé 1:4.5")


class BreakTest(unittest.TestCase):
    def test_cutoff_copy(self):
        self.assertEqual(breaks.payload(at(10))["headline"], "Time to dial in a shot")
        late = breaks.payload(at(17))
        self.assertEqual(late["mode"], "decaf")
        self.assertIn("Hydrate or Decaf", late["headline"])

    def test_tick_schedules_then_shows(self):
        def reset(s):
            s["break"] = {"next_due": 0, "snoozed_until": 0, "pomodoro": False, "last_shown": 0}
        state.update(reset)
        self.assertEqual(breaks.tick(at(10)), "scheduled")
        self.assertEqual(breaks.tick(at(10, 30)), "waiting")
        self.assertEqual(breaks.tick(at(11, 31)), "shown")
        breaks.snooze(15, now=at(11, 31))
        self.assertEqual(breaks.tick(at(11, 40)), "waiting")

    def test_outside_hours(self):
        breaks.schedule_next(1, now=at(21))
        self.assertEqual(breaks.tick(at(21, 5)), "outside-hours")


class RaceTest(unittest.TestCase):
    def test_parallel_clicks_lose_nothing(self):
        before = len(state.load()["cups"])
        procs = [subprocess.Popen([sys.executable, str(ROOT / "bin/oma-caffe"), "log"],
                                  stdout=subprocess.DEVNULL, env=os.environ) for _ in range(12)]
        for p in procs:
            self.assertEqual(p.wait(), 0)
        self.assertEqual(len(state.load()["cups"]), before + 12)


class ConfigTest(unittest.TestCase):
    def test_set_value_coerces(self):
        config.set_value("breaks.interval_min", "45")
        self.assertEqual(config.load()["breaks"]["interval_min"], 45)
        self.assertEqual(config.load()["breaks"]["snooze_min"], 15)


if __name__ == "__main__":
    unittest.main()


class GearTest(unittest.TestCase):
    def setUp(self):
        from oma_caffe import gear
        self.gear = gear

    def test_fuzzy_search(self):
        self.assertEqual(self.gear.find("grinders", "comandante c40")["id"], "comandante-c40")
        self.assertEqual(self.gear.find("grinders", "jx pro")["id"], "1zpresso-jx-pro")
        self.assertEqual(self.gear.find("machines", "gaggia classic")["id"], "gaggia-classic-pro")
        self.assertEqual(self.gear.find("machines", "bambino plus")["id"], "breville-bambino")

    def test_recommend_and_calibrate(self):
        self.gear.set_gear("grinder", "comandante")
        self.gear.set_gear("machine", "gaggia classic pro")
        rec = self.gear.recommend(recipes.get("classic-espresso-1-2"))
        self.assertEqual((rec["grind"]["low"], rec["grind"]["high"]), ("7", "12"))
        self.assertTrue(any("temperature-surf" in t["text"] for t in rec["machine"]))
        self.gear.calibrate("espresso", 14)
        rec = self.gear.recommend(recipes.get("classic-espresso-1-2"))
        self.assertEqual((rec["grind"]["low"], rec["grind"]["high"]), ("12", "16"))
        self.assertEqual(self.gear.next_setting("12", -1), "11")
        config.set_value("gear.offset", "0")

    def test_filter_grinder_warns_on_espresso(self):
        self.gear.set_gear("grinder", "baratza encore")
        rec = self.gear.recommend(recipes.get("classic-espresso-1-2"))
        self.assertIsNone(rec["grind"])
        self.assertIn("can't grind for espresso", rec["warnings"][0])
        self.gear.clear("grinder")
        self.gear.clear("machine")

    def test_gear_db_ranges_sane(self):
        for g in self.gear.db()["grinders"]:
            for cat, (lo, hi) in g["methods"].items():
                with self.subTest(g["id"], cat=cat):
                    self.assertTrue(g["min"] <= lo < hi <= g["max"])
            self.assertEqual("espresso" in g["methods"], g["espresso_capable"])


class BeansTest(unittest.TestCase):
    def test_saving_grinder_never_duplicates(self):
        from oma_caffe import beans
        beans.set_grinder("My grinder")
        beans.set_grinder("Niche Zero", "63mm conical")
        beans.set_grinder("niche zero")
        names = [g["name"] for g in beans.load()["grinders"]]
        self.assertEqual(names.count("Niche Zero"), 1)
        self.assertNotIn("My grinder", names[1:])
        self.assertEqual(beans.active_grinder()["burrs"], "63mm conical")
