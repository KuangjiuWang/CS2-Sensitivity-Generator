from math import hypot
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.blind_test import BlindSession
from core.config_export import crosshair_cfg_text
from core.crosshair import Crosshair
from core.flick_analysis import FlickTrial, sector_index
from core.history import HistoryStore, record
from core.telemetry import FlickStats, TrackingStats, TrackingTiming
from core.tracking_path import TrackingPath


def capture_phase(session, baseline_track=8, candidate_track=8, *, candidate_hits=12):
    candidate, mode = session.current
    faster = candidate.sensitivity > session.baseline
    if mode == "flick":
        return session.record(FlickStats(attempts=16, hits=candidate_hits if faster else 12, latency_sum=6))
    return session.record(TrackingStats(elapsed=15, on_target=candidate_track if faster else baseline_track))


class BlindWorkflowTests(unittest.TestCase):
    def test_candidate_order_is_blind_and_the_schedule_is_shared(self):
        session = BlindSession.create(1.15, 5, Random(42))
        self.assertEqual(sorted(candidate.sensitivity for candidate in session.candidates),
                         [1.093, 1.15, 1.208])
        self.assertEqual(sorted(map(sector_index, session.plan.targets)), list(range(16)))
        self.assertEqual(session.plan.duration, 28)
        for phase in range(6):
            _, mode = session.current
            assert mode == ("flick" if phase % 2 == 0 else "tracking")
            stats = FlickStats(attempts=16) if mode == "flick" else TrackingStats(elapsed=15)
            self.assertEqual(session.record(stats), phase == 5)
        self.assertEqual(session.decision().recommend.sensitivity, 1.15)

    def test_verifies_with_fresh_matched_targets_route_and_reversed_order(self):
        session = BlindSession.create(1, 5, Random(12))
        screening_plan = session.plan
        for _ in range(6):
            self.assertFalse(capture_phase(session, candidate_track=12))
        self.assertEqual(session.progress, "复核 1/4")
        expected_order = [group.sensitivity for group in reversed(session.screening) if group.sensitivity >= 1]
        self.assertEqual([group.sensitivity for group in session.verification], expected_order)
        self.assertEqual([group.label for group in session.verification], ["D", "E"])
        self.assertNotEqual(session.plan, screening_plan)
        for plan, near_parity in ((screening_plan, 0), (session.plan, 1)):
            self.assertEqual(sorted(map(sector_index, plan.targets)), list(range(16)))
            for point in plan.targets:
                self.assertEqual(hypot(*point) < 13, sector_index(point) % 2 == near_parity)
        forward, reverse = TrackingPath(), TrackingPath(reverse=True)
        self.assertNotEqual([forward.sample(t) for t in range(15)], [reverse.sample(t) for t in range(15)])
        for phase in range(4):
            self.assertEqual(capture_phase(session, candidate_track=12), phase == 3)
        self.assertEqual(session.decision().recommend.sensitivity, 1.05)

    def test_keeps_baseline_on_close_or_regressing_verification(self):
        for tracking, hits in ((8.4, 12), (12, 10), (0, 12)):
            with self.subTest(tracking=tracking, hits=hits):
                session = BlindSession.create(1, 5, Random(12))
                for _ in range(6):
                    self.assertFalse(capture_phase(session, candidate_track=12))
                for _ in range(4):
                    capture_phase(session, candidate_track=tracking, candidate_hits=hits)
                self.assertEqual(session.decision().recommend.sensitivity, 1)

    def test_equal_candidate_stops_after_screening(self):
        session = BlindSession.create(1, 5, Random(12))
        for phase in range(6):
            self.assertEqual(capture_phase(session), phase == 5)
        self.assertEqual(session.verification, [])
        self.assertEqual(session.decision().recommend.sensitivity, 1)

    def test_supplement_merges_only_observed_directions(self):
        first, second = FlickStats(attempts=1), FlickStats(attempts=1, hits=1)
        first.sectors[0].add(FlickTrial((20, 0), 1, 0), None)
        trial = FlickTrial((20, 0), 1, 0)
        trial.move((2, 0), .1, None)
        trial.move((20, 0), .25, .95)
        second.sectors[0].add(trial, None)
        first.merge(second)
        self.assertEqual(first.missing_directions().count(0), 1)
        reaction, settle = first.timings()
        self.assertAlmostEqual(reaction, .1)
        self.assertAlmostEqual(settle, .15)

    def test_tracking_reports_response_and_lock_separately(self):
        stats = TrackingStats()
        timing = TrackingTiming(stats)
        leg = (1., 1)
        for elapsed, yaw, inside in ((1., 359.9, False), (1.10, 0, False), (1.20, .4, False),
                                     (1.25, .6, True), (1.35, .9, True)):
            timing.observe(leg, elapsed, yaw, inside)
        self.assertAlmostEqual(stats.timings()[0], .2)
        self.assertAlmostEqual(stats.timings()[1], .05)

    def test_history_reload_and_clear_retains_preferences(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            store = HistoryStore(path)
            settings = {"dpi": 800, "sensitivity": 1.15}
            store.append(record("flick", settings, FlickStats(), None), settings=settings)
            reopened = HistoryStore(path)
            self.assertEqual(len(reopened.records[0]["flick"]["sectors"]), 16)
            reopened.clear()
            self.assertEqual(HistoryStore(path).settings, settings)
            self.assertEqual(HistoryStore(path).records, [])

    def test_history_write_denied_leaves_previous_data_intact(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            store = HistoryStore(path)
            store.save({"dpi": 800})
            with patch.object(Path, "open", side_effect=PermissionError) as open_file:
                with self.assertRaises(PermissionError):
                    store.save({"dpi": 1600})
                open_file.assert_called_once()
            self.assertEqual(store.settings, {"dpi": 800})
            self.assertEqual(HistoryStore(path).settings, store.settings)

    def test_crosshair_cfg_contains_only_current_crosshair_commands(self):
        cfg = crosshair_cfg_text(Crosshair(length=1, thickness=1, color=(0, 255, 145, 255)))
        self.assertIn('cl_crosshair_length "1"', cfg)
        self.assertIn('cl_crosshaircolor_b "145"', cfg)
        self.assertNotIn("sensitivity", cfg)
        self.assertNotIn("cl_crosshairsize", cfg)
