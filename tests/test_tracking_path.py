from math import atan, degrees
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.tracking_path import REACTION_SECONDS, WEAPON_SPEEDS, TrackingPath, center_angular_speed


class TrackingPathTests(unittest.TestCase):
    def test_weapon_speeds_bound_world_motion_and_view_speed(self):
        for _, speed in WEAPON_SPEEDS:
            for depth in (300, 600, 1600):
                with self.subTest(speed=speed, depth=depth):
                    path = TrackingPath(speed, depth)
                    step = .01
                    previous = 0
                    peak = 0
                    for index in range(1, int(2 * path.cycle / step)):
                        x, _ = path.sample(index * step)
                        self.assertLessEqual(abs(x), .22 + 1e-9)
                        peak = max(peak, abs(x - previous) * depth / step)
                        previous = x
                    self.assertAlmostEqual(peak, speed)

    def test_distance_changes_angular_speed(self):
        self.assertAlmostEqual(center_angular_speed(215, 600), 20.531, places=3)
        self.assertAlmostEqual(center_angular_speed(215, 400), center_angular_speed(215, 800) * 2)

    def test_reaction_and_braking_do_not_contribute_directional_samples(self):
        path = TrackingPath()
        first, second = path.strafes[:2]
        start = path.initial_hold
        self.assertEqual(path.sample(start / 2), (0, 0))
        self.assertEqual(path.sample(start + first.ramp / 2)[1], 0)
        self.assertEqual(path.sample(start + REACTION_SECONDS - .01)[1], 0)
        self.assertEqual(path.sample(start + REACTION_SECONDS + .01)[1], 1)
        self.assertEqual(path.sample(start + first.travel - first.ramp / 2)[1], 0)
        hold_x, hold_direction = path.sample(start + first.travel + first.rest / 2)
        self.assertAlmostEqual(degrees(atan(hold_x)), degrees(atan(.21)))
        self.assertEqual(hold_direction, 0)
        second_start = start + first.travel + first.rest
        self.assertEqual(path.sample(second_start + REACTION_SECONDS + .01)[1], -1)
        self.assertEqual(path.sample(path.cycle), (0, 0))
        self.assertEqual(path.sample(path.cycle + start + REACTION_SECONDS + .01)[1], -1)
