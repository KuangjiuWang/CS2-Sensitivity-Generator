"""Sensitivity suggestions from directional and paired aiming evidence."""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from math import exp, hypot
from statistics import median

from core.telemetry import ClickStats

MATCH_KEYS = ("dpi", "aspect", "crosshair", "scenario")
MAX_TRAINING_CHANGE = Decimal('.03')
STATIC_TASKS = {"linear", "six", "wall", "phase"}


@dataclass(frozen=True)
class TrainingAdvice:
    value: float
    reason: str


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
    if len(aligned) < 2 or len(aligned) * 3 < total * 2:
        return TrainingAdvice(base, f"六项综合 · {len(higher)} 项支持调高，{len(lower)} 项支持调低，保留当前值。")
    value = bounded_training_value(base, median(aligned))
    return TrainingAdvice(value, f"六项综合 · {len(aligned)} 项方向一致，采用其中位值，调整上限 3%。")


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
    if len(samples) >= 6:
        sectors = defaultdict(list)
        for sector, error in samples:
            sectors[sector].append(error)
        sector_errors = [median(errors) for errors in sectors.values()]
        for sign, label in ((1, "过冲"), (-1, "偏短")):
            matching = [error for error in sector_errors if error * sign > 0]
            support = sum(error * sign > 0 for _, error in samples)
            if len(matching) >= 2 and len(matching) / len(sector_errors) >= .60 and support / len(samples) >= .60:
                offset = abs(median(matching)) * .35
                if len(stats.follow_errors) >= 6:
                    offset = min(.03, offset) / (1 + median(stats.follow_errors))
                value = bounded_training_value(base, base * (1 - sign * offset))
                if value != base:
                    return TrainingAdvice(value, f"本轮建议 · {len(matching)}/{len(sector_errors)} 个方向{label}，{support}/{len(samples)} 个样本支持")
    return TrainingAdvice(base, f"本轮有效样本 {len(samples)}，没有足够一致的偏差，保持当前值。")
