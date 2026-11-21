from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.crosshair import Crosshair, STYLES, decode_share_code

# Published interoperability fixture from akiver/csgo-sharecode's README.
EXAMPLE = "CSvbPubOq37zTGqtsPTP5QTrp5CB4xFXiKRLfzJsm49ZRe"


class CrosshairTests(unittest.TestCase):
    def test_pixel_one_and_resolution_scaling(self):
        crosshair = Crosshair(length=1, gap=1, thickness=1, reference_height=720)
        self.assertEqual(crosshair.dimensions(720), (1, 1, 1))
        self.assertEqual(crosshair.dimensions(1440), (2, 2, 2))
        self.assertEqual(crosshair.dimensions(360), (1, 1, 1))
        self.assertEqual(Crosshair(length=0, thickness=0).dimensions(1080), (0, 4, 1))

    def test_style_one_and_style_specific_negative_gap(self):
        self.assertEqual(len(STYLES), 10)
        self.assertEqual(STYLES[1], "动态圆形")
        self.assertEqual(Crosshair(style=2, gap=-3).dimensions(1080)[1], -3)
        self.assertEqual(Crosshair(style=4, gap=-3).dimensions(1080)[1], 0)

    def test_decodes_current_cs2_share_code(self):
        crosshair = decode_share_code(EXAMPLE)
        self.assertEqual((crosshair.style, crosshair.length, crosshair.gap, crosshair.thickness), (2, 5, 0, 1))
        self.assertEqual(crosshair.color, (255, 0, 0, 255))
        self.assertEqual(crosshair.outline_color, (0, 0, 0, 255))
        self.assertEqual(crosshair.reference_height, 768)
        self.assertTrue(crosshair.dot)
        self.assertEqual((crosshair.spread_limit, crosshair.split_distance), (181, 3))
        self.assertEqual((crosshair.inner_alpha, crosshair.outer_alpha, crosshair.split_ratio), (1, .35, 0))

    def test_rejects_invalid_codes_and_legacy_container(self):
        for code in ("", "CS" + "9" * 44, EXAMPLE[:-1] + "A", "CSGO-invalid"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                decode_share_code(code)
