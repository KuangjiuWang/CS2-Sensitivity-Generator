"""Sensitivity suggestions from directional and paired aiming evidence."""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from math import exp, hypot
from statistics import median

from core.flick_analysis import MIN_DIRECTION_SAMPLES, SECTOR_LABELS
from core.telemetry import ClickStats

MATCH_KEYS = ("dpi", "aspect", "crosshair", "scenario")
MAX_TRAINING_CHANGE = Decimal('.03')
STATIC_TASKS = {"linear", "six", "wall", "phase"}
MIN_TRAINING_SAMPLES = 6
MIN_SUPPORT = .60


@dataclass(frozen=True)
class TrainingAdvice:
    value: float
    reason: str
    evidence: tuple[str, ...] = ()


def bounded_training_value(base: float, suggested: float) -> float:
    current = Decimal(str(base))
    unit = Decimal(".001")
    low = (current * (1 - MAX_TRAINING_CHANGE)).quantize(unit, rounding=ROUND_CEILING)
    high = (current * (1 + MAX_TRAINING_CHANGE)).quantize(unit, rounding=ROUND_FLOOR)
    proposed = Decimal(str(round(suggested, 3)))
    return float(max(Decimal(".001"), low, min(Decimal("100"), high, proposed)))


def adjustment_indicator(base: float, value: float) -> str:
    if value == base:
        return "保持"
    return f"{'↑' if value > base else '↓'} {abs(value / base - 1):.2%}"


def suite_advice(base: float, results: list[TrainingAdvice]) -> TrainingAdvice:
    higher = [advice.value for advice in results if advice.value > base]
    lower = [advice.value for advice in results if advice.value < base]
    total = len(higher) + len(lower)
    aligned = max((higher, lower), key=len)
    votes = (f"{len(higher)} 项建议调高，{len(lower)} 项建议调低，"
             f"{len(results) - total} 项建议保持。")
    rule = "至少两项支持同一方向，且占所有建议调整项目的三分之二。"
    if total == 0:
        return TrainingAdvice(base, "六项综合 · 各项目均未给出调整建议，保持当前值。", (votes,))
    if len(aligned) < 2:
        return TrainingAdvice(base, "六项综合 · 同方向项目不足两项，保持当前值。", (votes, rule))
    if len(aligned) * 3 < total * 2:
        return TrainingAdvice(base, "六项综合 · 项目间建议方向不一致，保持当前值。", (votes, rule))
    value = bounded_training_value(base, median(aligned))
    direction = "调高" if value > base else "调低"
    reason = f"六项综合 · {len(aligned)}/{total} 项支持{direction}，取同方向建议的中位值。"
    return TrainingAdvice(value, reason, (votes, rule))


def training_score(points: float, elapsed: float, accuracy: float, target_rate: float) -> float:
    pace = points / max(1, elapsed) / target_rate
    return 60 * (1 - exp(-pace)) + 40 * accuracy


def first_pass_error(angles, radius, samples) -> float | None:
    distance = hypot(*angles)
    if not 7 <= distance <= 35 or len(samples) < 5:
        return None
    dx, dy = (component / distance for component in angles)
    if any(abs(x * dy - y * dx) > max(1.5, distance * .12) for _, (x, y) in samples):
        return None
    projected = [(t, x * dx + y * dy) for t, (x, y) in samples]
    edge = max(radius, distance * .035)
    peak = max(progress for _, progress in projected)
    if peak > distance + edge:
        return (peak - distance) / distance
    for (before, progress), (after, next_progress) in zip(projected, projected[1:]):
        if (.55 * distance <= progress < distance - edge and after - before >= .05
                and next_progress > progress):
            return (progress - distance) / distance
    return 0.


def shot_error(angles, aim, radius: float) -> float | None:
    """Estimate signed endpoint bias on a close, roughly aligned shot."""
    distance = hypot(*angles)
    if not 4 <= distance <= 35:
        return None
    dx, dy = (component / distance for component in angles)
    ex, ey = aim[0] - angles[0], aim[1] - angles[1]
    if hypot(ex, ey) > max(1.8, radius * 3) or abs(ex * dy - ey * dx) > radius * 1.3:
        return None
    along = ex * dx + ey * dy
    return along / distance if abs(along) >= radius * .55 else 0.


def training_advice(stats: ClickStats, base: float) -> TrainingAdvice:
    samples = stats.first_pass_errors
    sectors = defaultdict(list)
    for sector, error in samples:
        sectors[sector].append(error)
    sector_errors = {sector: median(errors) for sector, errors in sorted(sectors.items())}
    low_sample = len(SECTOR_LABELS) - sum(len(errors) >= MIN_DIRECTION_SAMPLES for errors in sectors.values())
    coverage = (f"{len(samples)} 个有效样本，覆盖 {len(sectors)}/{len(SECTOR_LABELS)} 个方向。"
                f"{low_sample} 个方向少于 {MIN_DIRECTION_SAMPLES} 个有效样本（含未覆盖方向）。")
    if len(samples) < MIN_TRAINING_SAMPLES:
        return TrainingAdvice(base, f"普通训练 · 有效样本不足 {MIN_TRAINING_SAMPLES} 个，保持当前值。", (coverage,))

    votes = []
    for sign, bias, direction in ((1, "过冲", "调低"), (-1, "偏短", "调高")):
        matching = [index for index, error in sector_errors.items() if error * sign > 0]
        support = sum(error * sign > 0 for _, error in samples)
        count = f"{bias}方向 {len(matching)}/{len(sectors)}，样本 {support}/{len(samples)}"
        votes.append(count)
        if len(matching) < 2 or len(matching) / len(sectors) < MIN_SUPPORT or support / len(samples) < MIN_SUPPORT:
            continue
        offset = abs(median(sector_errors[index] for index in matching)) * .35
        if len(stats.follow_errors) >= MIN_TRAINING_SAMPLES:
            offset = min(.03, offset) / (1 + median(stats.follow_errors))
        value = bounded_training_value(base, base * (1 - sign * offset))
        reason = (f"普通训练 · {len(matching)} 个方向出现{bias}倾向，建议{direction}。"
                  if value != base else "普通训练 · 调整量过小或已到数值边界，保持当前值。")
        names = "、".join(SECTOR_LABELS[index] for index in matching)
        return TrainingAdvice(value, reason, (f"{count}（{names}）。", coverage))
    reason = ("覆盖方向不足两种" if len(sectors) < 2 else "过冲或偏短未同时达到样本及方向的 60%")
    return TrainingAdvice(base, f"普通训练 · {reason}，保持当前值。", ("。".join(votes) + "。", coverage))
