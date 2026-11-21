from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.player_sensitivity import SENSITIVITY_PRESETS
from core.player_crosshairs import CROSSHAIR_PRESETS
from core.player_source import SNAPSHOT_DATE


class PlayerPresetTests(unittest.TestCase):
    def test_snapshot_roster_and_effective_dpi(self):
        expected = {
            "donk": 1000, "m0NESY": 920, "ZywOo": 760, "s1mple": 1236, "ropz": 708,
            "NiKo": 640, "flameZ": 1200, "Twistzz": 636, "coldzera": 880, "GeT_RiGhT": 1200,
            "f0rest": 1400, "olofmeister": 1000, "device": 760, "NEO": 840,
        }
        self.assertEqual(len(SENSITIVITY_PRESETS), len(expected))
        self.assertEqual({player.name for player in CROSSHAIR_PRESETS}, set(expected))
        for player in SENSITIVITY_PRESETS:
            self.assertLessEqual(date.fromisoformat(player.updated), date.fromisoformat(SNAPSHOT_DATE))
            self.assertAlmostEqual(player.effective_dpi, expected[player.name])
            self.assertEqual(player.sensitivity_at(player.dpi), player.sensitivity)
        self.assertEqual(set(expected), {player.name for player in SENSITIVITY_PRESETS})
        self.assertTrue(all(player.crosshair.length > 0 for player in CROSSHAIR_PRESETS))

    def test_converts_sensitivity_to_current_dpi(self):
        presets = {player.name: player for player in SENSITIVITY_PRESETS}
        self.assertEqual(presets["donk"].sensitivity_at(1600), .625)
        self.assertEqual(presets["m0NESY"].sensitivity_at(800), 1.15)
        self.assertEqual(presets["Twistzz"].sensitivity_at(800), .795)

    def test_legacy_records_are_marked_and_renderable(self):
        legacy = [player for player in CROSSHAIR_PRESETS if player.legacy]
        self.assertEqual({player.name for player in legacy}, {"coldzera", "GeT_RiGhT", "olofmeister", "NEO"})
        for player in legacy:
            length, gap, thickness = player.crosshair.dimensions(player.crosshair.reference_height)
            self.assertGreaterEqual(length, 1)
            self.assertGreaterEqual(gap, 0)
            self.assertGreaterEqual(thickness, 1)
