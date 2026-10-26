"""Seed data integrity against schemas/*.schema.json enums and invariants."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schemas/recipes.schema.json").read_text())["$defs"]


def load(name, key):
    return json.loads((ROOT / "data" / name).read_text())[key]


class SeedTest(unittest.TestCase):
    def test_counts(self):
        rs = load("recipes.json", "recipes")
        self.assertTrue(8 <= len(rs) <= 10)
        methods = {r["method"] for r in rs}
        self.assertTrue({"Espresso", "V60", "Chemex", "AeroPress", "Milk Drink"} <= methods)
        names = " ".join(r["name"] for r in rs)
        for must in ("1:2", "Turbo", "Allongé"):
            self.assertIn(must, names)

    def test_fields_and_steps(self):
        kinds = set(SCHEMA["step"]["properties"]["kind"]["enum"])
        required = SCHEMA["recipe"]["required"]
        for r in load("recipes.json", "recipes") + load("library.json", "library"):
            with self.subTest(r["id"]):
                for f in required:
                    self.assertIn(f, r)
                ats = [s["at"] for s in r["steps"]]
                self.assertEqual(ats, sorted(ats))
                self.assertTrue(all(s["kind"] in kinds for s in r["steps"]))
                out = r.get("yield_g") or r.get("water_ml")
                self.assertTrue(out, "recipe needs a yield or water target")
                targets = [s["target_g"] for s in r["steps"] if s.get("target_g") is not None]
                self.assertEqual(targets, sorted(targets), "pour targets are cumulative")
                if targets:
                    self.assertLessEqual(max(targets), out)
                if r.get("ratio"):
                    want = float(r["ratio"].split(":")[1])
                    self.assertAlmostEqual(out / r["dose_g"], want, delta=0.1)

    def test_ids_unique(self):
        ids = [r["id"] for r in load("recipes.json", "recipes") + load("library.json", "library")]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
