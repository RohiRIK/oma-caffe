"""WCAG AA contrast for both oma-caffe palettes.

Text keys must reach 4.5:1 against every surface text sits on (background,
the elevated card surface, and the selection highlight). Border keys are
non-text UI and need 3:1 against the background.
"""
import pathlib
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
THEMES = ["crema-light", "ristretto-dark", "strawberry-latte"]
TEXT = ["foreground", "light_foreground", "bright_foreground", "dark_foreground", "muted", "accent",
        "red", "yellow", "orange", "green", "cyan", "blue", "magenta", "brown",
        "bright_red", "bright_yellow", "bright_green", "bright_cyan", "bright_blue", "bright_magenta"]
SURFACES = ["background", "lighter_background", "selection", "dark_background"]
BORDERS = ["hyprland_active_border"]


def luminance(hex_color):
    h = hex_color.lstrip("#")
    def channel(c):
        c = int(c, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(h[i:i + 2]) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def palette(name):
    return tomllib.loads((ROOT / "themes" / name / "colors.toml").read_text())


class ContrastTest(unittest.TestCase):
    def test_text_on_surfaces(self):
        for theme in THEMES:
            p = palette(theme)
            for key in TEXT:
                for surface in SURFACES:
                    with self.subTest(theme=theme, key=key, surface=surface):
                        self.assertGreaterEqual(contrast(p[key], p[surface]), 4.5)

    def test_borders(self):
        for theme in THEMES:
            p = palette(theme)
            for key in BORDERS:
                with self.subTest(theme=theme, key=key):
                    self.assertGreaterEqual(contrast(p[key], p["background"]), 3.0)

    def test_spec_colors_present(self):
        light, dark = palette("crema-light"), palette("ristretto-dark")
        self.assertEqual(light["background"], "#F5EBE6")
        self.assertEqual(light["lighter_background"], "#E6D2B5")
        self.assertEqual(light["hyprland_active_border"], "#A67B5B")
        self.assertEqual(light["foreground"], "#2C1A12")
        self.assertEqual(dark["background"], "#140D0B")
        self.assertEqual(dark["lighter_background"], "#231712")
        self.assertEqual(dark["accent"], "#D48C46")
        self.assertEqual(dark["foreground"], "#F2E8DF")


if __name__ == "__main__":
    unittest.main()
