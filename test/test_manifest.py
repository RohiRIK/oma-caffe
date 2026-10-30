"""Manifest, entry point, and packaging contract checks for rohirik.oma-caffe."""
import json
import os
import pathlib
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.m = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_schema_version_and_id(self):
        self.assertEqual(self.m["schemaVersion"], 1)
        self.assertEqual(self.m["id"], "rohirik.oma-caffe")
        self.assertEqual(self.m["name"], "oma-caffe")

    def test_kinds_and_entry_points_exist(self):
        self.assertEqual(self.m["kinds"], ["bar-widget", "overlay"])
        entries = self.m["entryPoints"]
        self.assertEqual(entries["barWidget"], "BarWidget.qml")
        self.assertEqual(entries["overlay"], "Overlay.qml")
        for rel in entries.values():
            self.assertTrue((ROOT / rel).is_file(), f"missing entry point {rel}")

    def test_bar_widget_metadata(self):
        bw = self.m["barWidget"]
        for field in ("displayName", "description", "category", "defaultSection", "defaults", "schema"):
            self.assertIn(field, bw)
        self.assertFalse(bw["allowMultiple"])
        keys = {item["key"] for item in bw["schema"]}
        self.assertEqual(keys, set(bw["defaults"].keys()))

    def test_required_files_and_scripts(self):
        for rel in ("Model.js", "BreakOverlay.qml", "preview.png", "README.md", "LICENSE"):
            self.assertTrue((ROOT / rel).is_file(), f"missing {rel}")
        for rel in ("bin/oma-caffe", "bin/oma-caffe-float", "install.sh", "uninstall.sh"):
            p = ROOT / rel
            self.assertTrue(p.is_file(), f"missing {rel}")
            self.assertTrue(os.access(p, os.X_OK), f"{rel} is not executable")
        for script in ("bin/oma-caffe-float", "install.sh", "uninstall.sh", "test/e2e.sh"):
            res = subprocess.run(["bash", "-n", str(ROOT / script)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"bash -n failed for {script}:\n{res.stderr}")

    def test_omarchy_plugin_validate_passes(self):
        if shutil.which("omarchy") is None:
            self.skipTest("Omarchy is not installed")
        res = subprocess.run(
            ["omarchy", "plugin", "validate", str(ROOT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
