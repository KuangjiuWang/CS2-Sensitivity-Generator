"""Matched six-project sensitivity screening and verification."""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from random import Random
from statistics import median

from core.scenarios import SCENARIOS, Scenario
from core.telemetry import ClickStats
from core.recommendation import training_score

ROUND_SECONDS = 15
SCREEN_GAIN = 1.0
VERIFY_GAIN = 2.0
MEAN_GAIN = 3.0


def performance(index: int, stats: ClickStats) -> float:
    return training_score(stats.points, stats.elapsed, stats.accuracy, SCENARIOS[index].target_rate)


def precision(samples: list[float]) -> float:
    return 100 * max(0., 1 - median(samples))


def paired_gain(index: int, first: ClickStats, second: ClickStats) -> float:
    gain = performance(index, first) - performance(index, second)
    if SCENARIOS[index].key in ("micro", "moving"):
        first_errors = first.follow_errors
        second_errors = second.follow_errors
    else:
        first_errors = [abs(error) / .15 for _, error in first.first_pass_errors]
        second_errors = [abs(error) / .15 for _, error in second.first_pass_errors]
    if min(len(first_errors), len(second_errors)) >= 6:
        return .8 * gain + .2 * (precision(first_errors) - precision(second_errors))
    return gain


@dataclass
class Candidate:
    label: str
    sensitivity: float
    rounds: dict[int, ClickStats] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return median(performance(index, stats) for index, stats in self.rounds.items())

    @property
    def valid_indices(self) -> set[int]:
        return {index for index, stats in self.rounds.items()
                if stats.elapsed >= ROUND_SECONDS - .05 and stats.hits >= 6}

    def gains_against(self, baseline: "Candidate") -> dict[int, float]:
        return {index: paired_gain(index, self.rounds[index], baseline.rounds[index])
                for index in sorted(self.valid_indices & baseline.valid_indices)}

    def eligible_against(self, baseline: "Candidate", threshold: float) -> bool:
        gains = self.gains_against(baseline)
        return (len(gains) >= 4 and median(gains.values()) >= threshold
                and sum(gain > 0 for gain in gains.values()) >= 3
                and median(self.rounds[i].accuracy - baseline.rounds[i].accuracy for i in gains) >= -.05)


@dataclass(frozen=True)
class Decision:
    recommend: Candidate
    reason: str


@dataclass
class BlindSession:
    baseline: float
    screening: list[Candidate]
    seeds: tuple[int, ...]
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
        return cls(middle, candidates, tuple(random.getrandbits(64) for _ in SCENARIOS), random)

    @property
    def candidates(self) -> list[Candidate]:
        return self.screening + self.verification

    @property
    def current(self) -> Candidate:
        return self.candidates[self.phase // len(SCENARIOS)]

    @property
    def index(self) -> int:
        return self.phase % len(SCENARIOS)

    @property
    def scenario(self) -> Scenario:
        return SCENARIOS[self.index]

    @property
    def seed(self) -> int:
        return self.seeds[self.index]

    @property
    def progress(self) -> str:
        if not self.verification:
            return f"初筛 {self.phase + 1}/{len(self.screening) * len(SCENARIOS)}"
        screening_count = len(self.screening) * len(SCENARIOS)
        return f"复核 {self.phase - screening_count + 1}/{len(self.verification) * len(SCENARIOS)}"

    def record(self, stats: ClickStats) -> bool:
        self.current.rounds[self.index] = stats
        self.phase += 1
        if self.phase < len(self.candidates) * len(SCENARIOS):
            return False
        if self.verification:
            self.finish_verification()
        else:
            self.start_verification()
        return self.result is not None

    def start_verification(self) -> None:
        baseline = next(group for group in self.screening if group.sensitivity == self.baseline)
        eligible = [group for group in self.screening if group.eligible_against(baseline, SCREEN_GAIN)]
        if not eligible:
            reason = ("可比较项目不足四项，保留当前值。" if len(baseline.valid_indices) < 4
                      else "初筛没有候选同时满足项目胜场、分差和准确率要求，保留当前值。")
            self.result = Decision(baseline, reason)
            return
        best = max(eligible, key=lambda group: median(group.gains_against(baseline).values()))
        ordered = [group for group in reversed(self.screening) if group is baseline or group is best]
        self.verification = [Candidate(label, group.sensitivity) for label, group in zip("DE", ordered)]
        self.seeds = tuple(self.random.getrandbits(64) for _ in SCENARIOS)

    def finish_verification(self) -> None:
        baseline = next(group for group in self.verification if group.sensitivity == self.baseline)
        best = next(group for group in self.verification if group is not baseline)
        first_base = next(group for group in self.screening if group.sensitivity == self.baseline)
        first_best = next(group for group in self.screening if group.sensitivity == best.sensitivity)
        gains = best.gains_against(baseline)
        first_gains = first_best.gains_against(first_base)
        shared = gains.keys() & first_gains.keys()
        if len(shared) < 4:
            self.result = Decision(baseline, "两轮共有的有效项目不足四项，保留当前值。")
            return
        gain = median(gains.values())
        combined = median((gains[i] + first_gains[i]) / 2 for i in shared)
        if not best.eligible_against(baseline, VERIFY_GAIN) or combined < MEAN_GAIN:
            self.result = Decision(baseline, f"复核中位差 {gain:+.1f} 分，未达到推荐条件，保留当前值。")
        else:
            self.result = Decision(best, f"复核中位差 {gain:+.1f} 分，两阶段合计中位差 {combined:+.1f} 分。"
                                         f"建议试用 {best.sensitivity:.3f}。")

    def decision(self) -> Decision:
        if self.result is None:
            raise RuntimeError("Blind comparison is still in progress")
        return self.result
