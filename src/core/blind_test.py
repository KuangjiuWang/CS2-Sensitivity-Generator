"""Matched sensitivity screening and verification, independent of the UI."""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from random import Random

from core.scenarios import Scenario
from core.telemetry import ClickStats
from core.recommendation import training_score

ROUND_SECONDS = 15
SCREEN_GAIN = 1.0
VERIFY_GAIN = 2.0
MEAN_GAIN = 3.0


@dataclass
class Candidate:
    label: str
    sensitivity: float
    scenario: Scenario
    stats: ClickStats | None = None

    @property
    def score(self) -> float:
        stats = self.stats
        return training_score(stats.points, stats.elapsed, stats.accuracy, self.scenario.target_rate)

    @property
    def enough_data(self) -> bool:
        stats = self.stats
        return stats.elapsed >= ROUND_SECONDS - .05 and stats.hits >= 6

    def eligible_against(self, baseline: "Candidate", gain: float) -> bool:
        return (self.enough_data and baseline.enough_data and self.score - baseline.score >= gain
                and self.stats.accuracy >= baseline.stats.accuracy - .05)


@dataclass(frozen=True)
class Decision:
    recommend: Candidate
    reason: str


@dataclass
class BlindSession:
    baseline: float
    screening: list[Candidate]
    scenario: Scenario
    seed: int
    random: Random = field(repr=False)
    verification: list[Candidate] = field(default_factory=list)
    phase: int = 0
    settings: dict = field(default_factory=dict)
    result: Decision | None = None

    @classmethod
    def create(cls, baseline: float, step: float, random: Random, scenario: Scenario):
        start = Decimal(str(baseline))
        fraction = Decimal(str(step)) / 100
        low, middle, high = (float((start * (1 + factor * fraction)).quantize(Decimal(".001"), rounding=ROUND_HALF_UP))
                             for factor in (-1, 0, 1))
        if not .001 <= low < middle < high <= 100:
            raise ValueError("候选值重合或超出灵敏度范围。请调整当前灵敏度或对比步长。")
        values = [low, middle, high]
        random.shuffle(values)
        candidates = [Candidate(label, value, scenario) for label, value in zip("ABC", values)]
        return cls(middle, candidates, scenario, random.getrandbits(64), random)

    @property
    def candidates(self) -> list[Candidate]:
        return self.screening + self.verification

    @property
    def current(self) -> Candidate:
        return self.candidates[self.phase]

    @property
    def progress(self) -> str:
        if not self.verification:
            return f"初筛 {self.phase + 1}/3"
        return f"复核 {self.phase - len(self.screening) + 1}/2"

    def record(self, stats: ClickStats) -> bool:
        self.current.stats = stats
        self.phase += 1
        if self.phase < len(self.candidates):
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
        self.verification = [Candidate(label, candidate.sensitivity, self.scenario) for label, candidate in zip("DE", ordered)]
        self.seed = self.random.getrandbits(64)

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
