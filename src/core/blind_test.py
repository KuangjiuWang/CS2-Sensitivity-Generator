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
MIN_PAIRED_PROJECTS = 4
MIN_WINS = 3
MAX_ACCURACY_DROP = .05


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
        return not self.compare(baseline).blockers(threshold)

    def compare(self, baseline: "Candidate") -> "PairEvidence":
        gains = self.gains_against(baseline)
        accuracy = median(self.rounds[i].accuracy - baseline.rounds[i].accuracy for i in gains) if gains else None
        return PairEvidence(gains, accuracy)


@dataclass(frozen=True)
class PairEvidence:
    gains: dict[int, float]
    accuracy: float | None

    @property
    def wins(self) -> int:
        return sum(gain > 0 for gain in self.gains.values())

    @property
    def gain(self) -> float:
        return median(self.gains.values()) if self.gains else 0.

    def blockers(self, threshold: float) -> tuple[str, ...]:
        if len(self.gains) < MIN_PAIRED_PROJECTS:
            return ("可比较项目不足四项",)
        blockers = []
        if self.wins < MIN_WINS:
            blockers.append("领先项目不足三项")
        if self.gain < threshold:
            blockers.append(f"中位分差低于 {threshold:g} 分")
        if self.accuracy < -MAX_ACCURACY_DROP:
            blockers.append("准确率下降超过 5 个百分点")
        return tuple(blockers)

    def summary(self, heading: str, threshold: float) -> str:
        counts = f"{heading} · {len(self.gains)}/{len(SCENARIOS)} 项可比较，{self.wins} 项领先"
        if self.gains:
            counts += f"，中位分差 {self.gain:+.2f} 分，准确率变化 {self.accuracy * 100:+.2f} 个百分点"
        blockers = self.blockers(threshold)
        return counts + ("。未达标项为" + "、".join(blockers) + "。" if blockers else "。")


@dataclass(frozen=True)
class Decision:
    recommend: Candidate
    reason: str
    evidence: tuple[str, ...] = ()


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
        comparisons = [(group, group.compare(baseline)) for group in self.screening if group is not baseline]
        eligible = [(group, evidence) for group, evidence in comparisons if not evidence.blockers(SCREEN_GAIN)]
        if not eligible:
            reason = ("盲测初筛 · 两档候选都不足四项可比较，保持当前值。"
                      if all(len(evidence.gains) < MIN_PAIRED_PROJECTS for _, evidence in comparisons)
                      else "盲测初筛 · 没有候选通过初筛，保持当前值。")
            details = tuple(evidence.summary(f"初筛 {group.label}", SCREEN_GAIN) for group, evidence in comparisons)
            self.result = Decision(baseline, reason, details)
            return
        best, _ = max(eligible, key=lambda item: item[1].gain)
        ordered = [group for group in reversed(self.screening) if group is baseline or group is best]
        self.verification = [Candidate(label, group.sensitivity) for label, group in zip("DE", ordered)]
        self.seeds = tuple(self.random.getrandbits(64) for _ in SCENARIOS)

    def finish_verification(self) -> None:
        baseline = next(group for group in self.verification if group.sensitivity == self.baseline)
        best = next(group for group in self.verification if group is not baseline)
        first_base = next(group for group in self.screening if group.sensitivity == self.baseline)
        first_best = next(group for group in self.screening if group.sensitivity == best.sensitivity)
        first = first_best.compare(first_base)
        second = best.compare(baseline)
        shared = first.gains.keys() & second.gains.keys()
        details = (first.summary(f"初筛 {first_best.label}", SCREEN_GAIN),
                   second.summary(f"复核 {best.label}", VERIFY_GAIN))
        if len(shared) < MIN_PAIRED_PROJECTS:
            self.result = Decision(baseline, f"盲测复核 · 两阶段共同有效项目只有 {len(shared)} 项，保持当前值。", details)
            return
        combined = median((second.gains[i] + first.gains[i]) / 2 for i in shared)
        details += (f"共同有效项目 {len(shared)} 项，两阶段合计中位差 {combined:+.2f} 分（要求 ≥{MEAN_GAIN:g} 分）。",)
        failed_verification = bool(second.blockers(VERIFY_GAIN))
        if failed_verification or combined < MEAN_GAIN:
            reason = ("盲测复核 · 初筛优势未通过复核门槛，保持当前值。" if failed_verification
                      else "盲测复核 · 两阶段合计优势不足，保持当前值。")
            self.result = Decision(baseline, reason, details)
        else:
            self.result = Decision(best, f"盲测复核 · 候选通过两阶段比较，建议试用 {best.sensitivity:.3f}。", details)

    def decision(self) -> Decision:
        if self.result is None:
            raise RuntimeError("Blind comparison is still in progress")
        return self.result
