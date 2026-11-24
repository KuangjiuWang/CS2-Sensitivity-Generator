from math import cos, radians, sin
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.flick_analysis import FlickSector, FlickTrial, SECTOR_WIDTH, sector_index


class FlickAnalysisTests(unittest.TestCase):
    def test_pre_shot_overshoot_tracks_the_farthest_aim_beyond_the_target(self):
        trial = FlickTrial((10, 0), 1, 0)
        trial.move((13, 0), .1)
        trial.move((10, 0), .2)
        trial.shoot(.2, True)
        trial.move((14, 0), .3)
        self.assertAlmostEqual(trial.pre_shot_overshoot, 2.)

    def test_sixteen_clockwise_sectors_and_wraparound(self):
        def index(angle):
            return sector_index((cos(radians(angle)), sin(radians(angle))))

        self.assertEqual([index(i * SECTOR_WIDTH) for i in range(16)], list(range(16)))
        self.assertEqual([index(angle) for angle in (-11.3, -11.2, 11.2, 11.3, 359.9)],
                         [15, 0, 0, 1, 0])

    def test_path_efficiency_and_deviation_stop_at_first_contact(self):
        trial = FlickTrial((20, 0), 1, 10)
        trial.move((0, 3), 10.01)
        trial.move((20, 3), 10.02)
        trial.move((20, 1), 10.03)
        trial.shoot(10.03, True)
        trial.move((24, 8), 10.04)
        self.assertAlmostEqual(trial.efficiency, (20 ** 2 + 1) ** .5 / 25)
        self.assertAlmostEqual(trial.deviation, 3)
        self.assertAlmostEqual(trial.peak, 3)
        trace = trial.trace()
        self.assertEqual(trace.points[trace.contact], (20, 1))
        self.assertEqual(trace.points[-1], (24, 8))
        self.assertAlmostEqual(trace.latency, .03)

    def test_misses_and_incomplete_overshoot_keep_separate_denominators(self):
        stats = FlickSector()
        trial = FlickTrial((20, 0), 1, 0)
        trial.move((20, 0), .12)
        trial.shoot(.12, True)
        stats.add(trial, None)
        for _ in range(7):
            stats.add(FlickTrial((20, 0), 1, 0), None)
        self.assertEqual((stats.attempts, stats.hits, stats.overshoot_count), (8, 1, 0))
        self.assertEqual(len(stats.traces), 6)
        self.assertAlmostEqual(stats.efficiency_sum, 1)

    def test_yaw_wrap_does_not_add_a_full_turn_to_the_path(self):
        trial = FlickTrial((20, 0), 1, 0)
        trial.move((179, 0), .01)
        trial.move((-179, 0), .02)
        self.assertEqual(trial.path_length, 181)
