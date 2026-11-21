"""Matched sensitivity screening and verification, independent of the UI."""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from random import Random

from core.flick_analysis import SECTOR_LABELS
from core.practice_plan import FlickPlan, flick_plan
from core.telemetry import FlickStats, TrackingStats

BLIND_INTERVAL = 1.75
TRACK_SECONDS = 15
TARGET_COUNT = len(SECTOR_LABELS)
MODES = ("flick", "tracking")
SCREEN_GAIN = 1.0
VERIFY_GAIN = 2.0
MEAN_GAIN = 3.0


@dataclass
class Candidate:
    label: str
    sensitivity: float
    flick: FlickStats = field(default_factory=FlickStats)
    tracking: TrackingStats = field(default_factory=TrackingStats)

    @property
    def hit_rate(self) -> float:
        return self.flick.hits / self.flick.attempts if self.flick.attempts else 0

    @property
    def score(self) -> float:
        attempts = max(1, self.flick.attempts)
        # Give misses zero credit; time before movement does not contribute to movement speed.
        _, movement = self.flick.timings()
        movement_hits = sum(sector.movement_hits for sector in self.flick.sectors)
        speed = 0 if movement is None else movement_hits / attempts * max(0, 1 - movement / BLIND_INTERVAL)
        # Aiming past the target loses up to one quarter of the flick hit component.
        overshoot = min(self.flick.mean_overshoot / 3, 1)
        flick_precision = self.hit_rate * (1 - .25 * overshoot)
        return (35 * flick_precision + 15 * speed +
                35 * self.tracking.accuracy + 15 * self.tracking.centering)

    @property
    def enough_data(self) -> bool:
        return (self.flick.attempts == TARGET_COUNT and self.flick.hits >= 6
                and self.tracking.elapsed >= TRACK_SECONDS - .05 and self.tracking.accuracy >= .10)

    def eligible_against(self, baseline: "Candidate", gain: float) -> bool:
        return (self.enough_data and baseline.enough_data and self.score - baseline.score >= gain
                and self.flick.hits >= baseline.flick.hits - 1
                and self.tracking.accuracy >= baseline.tracking.accuracy - .05)


@dataclass(frozen=True)
class Decision:
    recommend: Candidate
    reason: str


@dataclass
class BlindSession:
    baseline: float
    screening: list[Candidate]
    plan: FlickPlan
    random: Random = field(repr=False)
    verification: list[Candidate] = field(default_factory=list)
    phase: int = 0
    settings: dict = field(default_factory=dict)
    result: Decision | None = None

    @classmethod
    def create(cls, baseline: float, step: float, random: Random):
        start = Decimal(str(baseline))
        fraction = Decimal(str(step)) / 100
        low, middle, high = (float((start * (1 + factor * fraction)).quantize(Decimal(".001"), rounding=ROUND_HALF_UP))
                             for factor in (-1, 0, 1))
        if not .001 <= low < middle < high <= 100:
            raise ValueError("候选值重合或超出灵敏度范围。请调整当前灵敏度或对比步长。")
        values = [low, middle, high]
        random.shuffle(values)
        candidates = [Candidate(label, value) for label, value in zip("ABC", values)]
        return cls(middle, candidates, flick_plan(range(TARGET_COUNT), random, BLIND_INTERVAL, near_parity=0), random)

    @property
    def candidates(self) -> list[Candidate]:
        return self.screening + self.verification

    @property
    def current(self) -> tuple[Candidate, str]:
        return self.candidates[self.phase // len(MODES)], MODES[self.phase % len(MODES)]

    @property
    def progress(self) -> str:
        if not self.verification:
            return f"初筛 {self.phase + 1}/6"
        return f"复核 {self.phase - len(self.screening) * len(MODES) + 1}/4"

    def record(self, stats: FlickStats | TrackingStats) -> bool:
        candidate, mode = self.current
        setattr(candidate, mode, stats)
        self.phase += 1
        if self.phase < len(self.candidates) * len(MODES):
            return False
        if self.verification:
            self.finish_verification()
        else:
            self.start_verification()
        return self.result is not None

    def start_verification(self) -> None:
        baseline = next(candidate for candidate in self.screening if candidate.sensitivity == self.baseline)
        eligible = [candidate for candidate in self.screening if candidate.eligible_against(baseline, SCREEN_GAIN)]
        if not eligible:
            reason = ("有效样本不足，保留当前值。" if not baseline.enough_data
                      else "初筛没有候选达到领先和命中表现要求，保留当前值。")
            self.result = Decision(baseline, reason)
            return

        best = max(eligible, key=lambda candidate: candidate.score)
        # Flip the pair's relative order to reduce consistent warm-up and fatigue effects.
        ordered = [candidate for candidate in reversed(self.screening) if candidate is baseline or candidate is best]
        self.verification = [Candidate(label, candidate.sensitivity) for label, candidate in zip("DE", ordered)]
        self.plan = flick_plan(range(TARGET_COUNT), self.random, BLIND_INTERVAL, near_parity=1)

    def finish_verification(self) -> None:
        baseline = next(candidate for candidate in self.verification if candidate.sensitivity == self.baseline)
        best = next(candidate for candidate in self.verification if candidate is not baseline)
        first_baseline = next(candidate for candidate in self.screening if candidate.sensitivity == self.baseline)
        first_best = next(candidate for candidate in self.screening if candidate.sensitivity == best.sensitivity)
        gain = best.score - baseline.score
        mean_gain = (gain + first_best.score - first_baseline.score) / 2
        if not best.enough_data or not baseline.enough_data:
            self.result = Decision(baseline, "复核有效样本不足，保留当前值。")
        elif not best.eligible_against(baseline, VERIFY_GAIN) or mean_gain < MEAN_GAIN:
            self.result = Decision(baseline, f"复核差值 {gain:+.1f} 分，未达到推荐条件，保留当前值。")
        else:
            self.result = Decision(best, f"复核领先 {gain:.1f} 分，两轮平均领先 {mean_gain:.1f} 分。"
                                         f"建议试用 {best.sensitivity:.3f}。")

    def decision(self) -> Decision:
        if self.result is None:
            raise RuntimeError("Blind comparison is still in progress")
        return self.result
