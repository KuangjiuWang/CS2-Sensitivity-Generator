from math import tan, radians
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.cs2_math import (Camera, PRESETS, PROFILES, cfg_text, cm_per_360,
                           console_text, edpi,
                           physical_baseline, segment_hit, sensitivity_for_cm)
from core.telemetry import FlickStats, TrackingStats


class SensitivityTests(unittest.TestCase):
    def test_edpi_and_physical_round_trip(self):
        self.assertEqual(edpi(800, 1.25), 1000)
        self.assertAlmostEqual(cm_per_360(800, 1.25), 41.563636, places=6)
        self.assertAlmostEqual(sensitivity_for_cm(800, cm_per_360(800, 1.25)), 1.25)

    def test_profile_turn_and_travel(self):
        for profile, (fraction, expected_turn) in PROFILES.items():
            with self.subTest(profile=profile):
                sens, swing, turn = physical_baseline(800, 40, profile)
                self.assertAlmostEqual(swing, 40 * fraction)
                self.assertEqual(turn, expected_turn)
                self.assertAlmostEqual(swing / cm_per_360(800, sens) * 360, turn)

    def test_invalid_numbers(self):
        for value in (0, -1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cm_per_360(value, 1)

    def test_export_uses_same_three_decimal_values(self):
        self.assertEqual(cfg_text(1.2344, 1), 'sensitivity "1.234"\nzoom_sensitivity_ratio "1.000"\n')
        self.assertEqual(console_text(1.2344, 1), 'sensitivity "1.234"; zoom_sensitivity_ratio "1.000"')


class ProjectionTests(unittest.TestCase):
    def test_horizontal_fov(self):
        self.assertEqual([round(p.horizontal_fov, 2) for p in PRESETS], [106.26, 90.00, 100.39])
        for preset in PRESETS:
            with self.subTest(preset=preset):
                edge = Camera(preset.horizontal_fov / 2).ray(0, 0)
                self.assertAlmostEqual(Camera().project(edge)[0], preset.horizontal_tangent)

    def test_scaled_and_stretched_viewports(self):
        self.assertEqual(PRESETS[0].viewport(1920, 1080), (0, 0, 1920, 1080))
        self.assertEqual(PRESETS[1].viewport(1920, 1080), (0, 0, 1920, 1080))
        self.assertEqual(PRESETS[2].viewport(1920, 1080), (96, 0, 1728, 1080))
        self.assertEqual(PRESETS[2].viewport(1280, 720), (64, 0, 1152, 720))

    def test_raw_counts_rotate_and_perspective_projects(self):
        camera = Camera()
        world_forward = camera.ray(0, 0)
        camera.move(1000, 0, 2)
        self.assertAlmostEqual(camera.yaw, 44)
        self.assertAlmostEqual(camera.project(world_forward)[0], -tan(radians(44)))
        self.assertIsNone(Camera(180).project(world_forward))

    def test_ray_projection_round_trip_at_nonzero_angles(self):
        camera = Camera(312, -38)
        x, y = camera.project(camera.ray(-.22, .43))
        self.assertAlmostEqual(x, -.22)
        self.assertAlmostEqual(y, .43)

    def test_segment_crossing_registers_even_when_both_ends_are_outside(self):
        self.assertAlmostEqual(segment_hit((-.2, 0), (.2, 0), .04), .4)
        self.assertIsNone(segment_hit((-.2, .1), (.2, .1), .04))
        self.assertEqual(segment_hit((0, 0), (0, 0), .04), 0)


class TelemetryTests(unittest.TestCase):
    def test_flick_excludes_incomplete_overshoot_windows(self):
        flick = FlickStats()
        flick.hit(.1)
        flick.record_overshoot(2)
        flick.hit(.3)
        self.assertAlmostEqual(flick.mean_latency, .2)
        self.assertEqual(flick.mean_overshoot, 2)

    def test_tracking_weights_by_duration_and_filters_stationary_direction(self):
        track = TrackingStats()
        track.sample(.3, True, 0, .05, error_radii=0)
        track.sample(.4, False, .1, .05, error_radii=2)
        track.sample(.1, False, -.1, .05, error_radii=4)
        track.sample(.2, False, None, .05, error_radii=float("inf"))
        self.assertAlmostEqual(track.centering, .5)
        self.assertAlmostEqual(track.accuracy, .3)
        self.assertAlmostEqual(track.lag_rate, .5)
        self.assertAlmostEqual(track.lead_rate, .125)


if __name__ == "__main__":
    unittest.main()
