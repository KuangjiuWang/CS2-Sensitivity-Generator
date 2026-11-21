from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.dpi_measurement import DpiMeasurement


class DpiMeasurementTests(unittest.TestCase):
    def test_uses_net_counts_in_either_direction(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                measurement = DpiMeasurement(10)
                measurement.add(1600 * direction, 5)
                measurement.add(-25 * direction, -5)
                self.assertEqual(measurement.estimate(), 400)

    def test_uses_the_measured_distance(self):
        measurement = DpiMeasurement(2.54)
        measurement.add(1600, 0)
        self.assertEqual(measurement.estimate(), 1600)

    def test_rejects_empty_diagonal_and_backtracking_swipes(self):
        for motions in ((), ((3149, 1000),), ((3000, 0), (-1000, 0)), ((10, 0),)):
            with self.subTest(motions=motions):
                measurement = DpiMeasurement(10)
                for dx, dy in motions:
                    measurement.add(dx, dy)
                with self.assertRaises(ValueError):
                    measurement.estimate()
