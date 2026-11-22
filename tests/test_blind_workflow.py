from concurrent.futures import ThreadPoolExecutor
from math import dist
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
from core.flick_analysis import FlickTrial
from core.history import HistoryStore, record
from core.recommendation import TrainingAdvice, adjustment_indicator, first_pass_error, shot_error, suite_advice, training_advice
from core.telemetry import ClickStats, FlickStats, TrackingStats, TrackingTiming
from core.scenarios import ClickField, FixedWave, SCENARIOS


def capture_phase(session, candidate_track=8):
    hits = candidate_track if session.current.sensitivity > session.baseline else 8
    return session.record(ClickStats(elapsed=15, hits=8, attempts=8, points=hits))


class BlindWorkflowTests(unittest.TestCase):
    def test_suite_combines_consistent_projects_and_keeps_base_on_conflict(self):
        def results(*values):
            return [TrainingAdvice(value, "") for value in values]
        self.assertEqual(suite_advice(1, results(1.02, 1.04, 1, 1, 1, .98)).value, 1.03)
        self.assertEqual(suite_advice(1, results(1.08, 1.1, 1, 1, 1, 1)).value, 1.03)
        self.assertEqual(suite_advice(1, results(1.02, 1.04, .98, .97, 1, 1)).value, 1)
        self.assertEqual(suite_advice(1, results(.98, 1, 1, 1, 1, 1)).value, 1)

    def test_training_only_suggests_bounded_changes_for_repeated_static_errors(self):
        over = [(t / 100, (x, 0)) for t, x in enumerate((1, 5, 11, 21, 16))]
        short = [(t, (x, 0)) for t, x in ((.01, 1), (.02, 4), (.03, 9), (.04, 12), (.11, 15))]
        self.assertEqual(first_pass_error((16, 0), .8, over), .3125)
        self.assertEqual(first_pass_error((16, 0), .8, short), -.25)
        stats = ClickStats(elapsed=15, attempts=12, hits=12, points=12,
                           first_pass_errors=[(i % 4, .2) for i in range(12)])
        self.assertEqual(training_advice(stats, 1.15).value, 1.116)
        stats.first_pass_errors = [(0, .2)] * 12
        self.assertEqual(training_advice(stats, 1.15).value, 1.15)

    def test_single_round_uses_signed_shot_error_and_displays_direction(self):
        error = shot_error((10, 0), (9, .1), .6)
        self.assertEqual(error, -.1)
        self.assertIsNone(shot_error((10, 0), (9, 2), .6))
        stats = ClickStats(first_pass_errors=[(i % 2, error) for i in range(6)])
        proposed = training_advice(stats, 1.15).value
        self.assertEqual(proposed, 1.184)
        self.assertLessEqual(proposed / 1.15 - 1, .03)
        self.assertEqual(adjustment_indicator(1.15, proposed), "↑ 2.96%")
        self.assertEqual(adjustment_indicator(1.15, 1.116), "↓ 2.96%")
        self.assertEqual(adjustment_indicator(1.15, 1.15), "保持")

    def test_candidates_are_blind_and_share_the_stage_seed(self):
        session = BlindSession.create(1.15, 5, Random(42), SCENARIOS[0])
        self.assertEqual(sorted(candidate.sensitivity for candidate in session.candidates),
                         [1.093, 1.15, 1.208])
        seed = session.seed
        for phase in range(3):
            self.assertEqual(session.seed, seed)
            self.assertEqual(capture_phase(session), phase == 2)
        self.assertEqual(session.decision().recommend.sensitivity, 1.15)

    def test_verifies_with_fresh_seed_and_reversed_order(self):
        session = BlindSession.create(1, 5, Random(12), SCENARIOS[0])
        seed = session.seed
        for _ in range(3):
            self.assertFalse(capture_phase(session, candidate_track=15))
        self.assertEqual(session.progress, "复核 1/2")
        expected = [group.sensitivity for group in reversed(session.screening) if group.sensitivity >= 1]
        self.assertEqual([group.sensitivity for group in session.verification], expected)
        self.assertNotEqual(FixedWave(SCENARIOS[0], seed).targets, FixedWave(SCENARIOS[0], session.seed).targets)
        self.assertFalse(capture_phase(session, candidate_track=15))
        self.assertTrue(capture_phase(session, candidate_track=15))
        self.assertEqual(session.decision().recommend.sensitivity, 1.05)

    def test_keeps_baseline_on_close_verification(self):
        session = BlindSession.create(1, 5, Random(12), SCENARIOS[0])
        for _ in range(3):
            capture_phase(session, candidate_track=15)
        for _ in range(2):
            capture_phase(session, candidate_track=8.4)
        self.assertEqual(session.decision().recommend.sensitivity, 1)

    def test_click_scoring_rejects_faster_but_significantly_less_accurate(self):
        session = BlindSession.create(1, 5, Random(12), SCENARIOS[2])
        for _ in range(3):
            better = session.current.sensitivity > session.baseline
            session.record(ClickStats(elapsed=15, hits=18 if better else 12,
                                      attempts=30 if better else 13, points=18 if better else 12))
        self.assertEqual(session.decision().recommend.sensitivity, 1)

    def test_six_scenarios_keep_order_and_distinct_target_rules(self):
        self.assertEqual([spec.key for spec in SCENARIOS], ["linear", "micro", "six", "wall", "phase", "moving"])
        self.assertEqual([spec.count for spec in SCENARIOS], [5, 2, 6, 6, 2, 5])
        self.assertGreater(SCENARIOS[3].width, SCENARIOS[2].width)
        self.assertGreater(SCENARIOS[3].radius, SCENARIOS[2].radius)
        self.assertEqual(len({spec.radius for spec in SCENARIOS}), 6)
        micro = ClickField(SCENARIOS[1], 5)
        for target in micro.targets:
            self.assertNotEqual(target.position(0), target.position(.2))
            self.assertTrue(all(abs(target.position(t / 10)[0]) <= SCENARIOS[1].width for t in range(200)))
        for spec in SCENARIOS[1:]:
            first, second = ClickField(spec, 17), ClickField(spec, 17)
            self.assertEqual(first.targets, second.targets)
            first.replace(0, .25)
            second.replace(0, .25)
            self.assertEqual(first.targets, second.targets)
        phase = ClickField(SCENARIOS[4], 5)
        radius = phase.targets[0].radius
        for index in range(1, 4):
            phase.replace(0, index / 2)
            self.assertEqual(phase.targets[0].phase, index % 3)
        self.assertEqual(phase.targets[0].radius, radius)
        moving = ClickField(SCENARIOS[5], 5)
        before = tuple(moving.targets)
        self.assertNotEqual(before[0].position(0), before[0].position(.2))
        for target in before:
            self.assertTrue(all(abs(target.position(t)[0]) <= SCENARIOS[5].width for t in range(300)))
        self.assertEqual(tuple(moving.targets), before)
        moving.replace(0, 300.)
        self.assertEqual(moving.targets[0].born, 300.)
        self.assertEqual(tuple(moving.targets[1:]), before[1:])

    def test_fixed_wave_removes_only_hit_targets_and_regenerates_after_clear(self):
        route = FixedWave(SCENARIOS[0], 5)
        initial = tuple(route.targets)
        self.assertEqual(tuple(t.position(0) for t in initial), tuple(t.position(30) for t in initial))
        for slot in range(len(initial) - 1):
            route.replace(slot, 7.)
            self.assertEqual(route.targets[:slot + 1], [None] * (slot + 1))
            self.assertEqual(tuple(route.targets[slot + 1:]), initial[slot + 1:])
        route.replace(len(initial) - 1, 9.)
        self.assertEqual(len(route.targets), len(initial))
        self.assertTrue(all(t.born == 9 for t in route.targets))
        self.assertNotEqual([t.position(9) for t in route.targets], [t.position(9) for t in initial])

    def test_fixed_waves_vary_the_formation_and_keep_targets_apart(self):
        scenario = SCENARIOS[0]
        field = FixedWave(scenario, 8)
        replay = FixedWave(scenario, 8)
        right_counts = set()
        previous = []
        for wave in range(64):
            points = [target.position(wave) for target in field.targets]
            right_counts.add(sum(x > 0 for x, _ in points))
            self.assertEqual(field.targets, replay.targets)
            for i, (x, y) in enumerate(points):
                self.assertLessEqual(abs(x) + scenario.radius, scenario.width)
                self.assertLessEqual(abs(y) + scenario.radius, scenario.height)
                self.assertTrue(all(dist((x, y), point) >= scenario.radius * 5 for point in points[:i]))
                self.assertTrue(all(dist((x, y), point) >= scenario.radius * 3 for point in previous))
            previous = points
            for index in range(scenario.count):
                field.replace(index, wave + 1)
                replay.replace(index, wave + 1)
        self.assertEqual(right_counts, set(range(scenario.count + 1)))

    def test_moving_targets_draw_distinct_continuous_segments_for_a_full_round(self):
        for index in (1, 5):
            scenario = SCENARIOS[index]
            target = ClickField(scenario, 12).targets[0]
            replay = ClickField(scenario, 12).targets[0]
            different = ClickField(scenario, 13).targets[0]
            self.assertEqual(target.motion, replay.motion)
            self.assertNotEqual(target.motion, different.motion)
            self.assertGreaterEqual(target.motion.times[-1], 60)
            times = target.motion.times
            points = target.motion.points
            self.assertTrue(any(a == b for a, b in zip(points, points[1:])))
            self.assertGreater(len({round(b - a, 2) for a, b in zip(times, times[1:])}), 10)
            for t, point in zip(times, points):
                self.assertEqual(target.position(t), point)
                self.assertLess(dist(target.position(max(0, t - .001)), point), .005)
            if index == 1:
                self.assertEqual(len({p[1] for p in points}), 1)
            else:
                self.assertGreater(len({round(p[1], 2) for p in points}), 10)

    def test_moving_replacement_clears_current_positions(self):
        for seed in range(100):
            field = ClickField(SCENARIOS[5], seed)
            timestamp = 3.25
            field.replace(0, timestamp)
            new, *others = field.targets
            for existing in others:
                self.assertGreaterEqual(dist(new.position(timestamp), existing.position(timestamp)),
                                        (new.radius + existing.radius) * 1.7)

    def test_supplement_merges_only_observed_directions(self):
        first, second = FlickStats(attempts=1), FlickStats(attempts=1, hits=1)
        first.sectors[0].add(FlickTrial((20, 0), 1, 0), None)
        trial = FlickTrial((20, 0), 1, 0)
        trial.move((2, 0), .1)
        trial.move((20, 0), .25)
        trial.shoot(.25, True)
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

    def test_history_merges_two_writers_and_does_not_restore_cleared_records(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            first, second = HistoryStore(path), HistoryStore(path)
            with ThreadPoolExecutor(2) as pool:
                writes = [pool.submit(store.append, {"name": name}, settings={})
                          for store, name in ((first, "first"), (second, "second"))]
                for write in writes:
                    write.result()
            self.assertCountEqual([row["name"] for row in HistoryStore(path).records], ["first", "second"])
            first.clear()
            second.save({"dpi": 800})
            self.assertEqual(HistoryStore(path).records, [])

    def test_crosshair_cfg_contains_only_current_crosshair_commands(self):
        cfg = crosshair_cfg_text(Crosshair(length=1, thickness=1, color=(0, 255, 145, 255)))
        self.assertIn('cl_crosshair_length "1"', cfg)
        self.assertIn('cl_crosshaircolor_b "145"', cfg)
        self.assertNotIn("sensitivity", cfg)
        self.assertNotIn("cl_crosshairsize", cfg)
