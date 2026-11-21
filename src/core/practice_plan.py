"""Immutable flick schedules for matched blind tests and direction supplements."""
from dataclasses import dataclass
from math import cos, radians, sin
from random import Random

from core.cs2_math import Point
from core.flick_analysis import SECTOR_WIDTH


@dataclass(frozen=True)
class FlickPlan:
    targets: tuple[Point, ...]
    interval: float

    @property
    def duration(self) -> float:
        return len(self.targets) * self.interval


def target_at(sector: int, random: Random, distance_range=(16, 28)) -> Point:
    direction = radians(sector * SECTOR_WIDTH + random.uniform(-8, 8))
    distance = random.uniform(*distance_range)
    return cos(direction) * distance, sin(direction) * distance


def flick_plan(sectors, random: Random, interval: float, *, near_parity: int | None = None) -> FlickPlan:
    order = list(sectors)
    random.shuffle(order)
    return FlickPlan(tuple(target_at(sector, random, (6, 12) if sector % 2 == near_parity else (16, 28))
                           for sector in order), interval)
