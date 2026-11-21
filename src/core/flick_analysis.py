"""Direction bins and per-attempt aim traces in degrees from target spawn."""
from collections import deque
from dataclasses import dataclass, field
from math import atan2, degrees, hypot

from core.cs2_math import Point, Ray, dot

SECTOR_LABELS = (
    "右", "右偏下", "右下", "下偏右", "下", "下偏左", "左下", "左偏下",
    "左", "左偏上", "左上", "上偏左", "上", "上偏右", "右上", "右偏上",
)
SECTOR_WIDTH = 360 / len(SECTOR_LABELS)
TRACE_INTERVAL = .008
REACTION_THRESHOLD_DEG = .35
MIN_DIRECTION_SAMPLES = 3


def sector_index(target: Point) -> int:
    angle = degrees(atan2(target[1], target[0]))
    return int(((angle + SECTOR_WIDTH / 2) % 360) // SECTOR_WIDTH)


def local_angles(ray: Ray, basis: tuple[Ray, Ray, Ray]) -> Point:
    forward, right, down = (dot(ray, axis) for axis in basis)
    return degrees(atan2(right, forward)), degrees(atan2(down, hypot(forward, right)))


@dataclass(frozen=True)
class FlickTrace:
    target: Point
    radius: float
    points: tuple[Point, ...]
    contact: int | None
    latency: float | None


@dataclass
class FlickSector:
    attempts: int = 0
    hits: int = 0
    latency_sum: float = 0
    starts: int = 0
    reaction_sum: float = 0
    movement_hits: int = 0
    movement_sum: float = 0
    overshoot_count: int = 0
    overshoot_sum: float = 0
    efficiency_sum: float = 0
    deviation_sum: float = 0
    traces: deque[FlickTrace] = field(default_factory=lambda: deque(maxlen=6))

    def add(self, trial: "FlickTrial", overshoot: float | None) -> None:
        self.attempts += 1
        if trial.onset is not None:
            self.starts += 1
            self.reaction_sum += trial.onset - trial.started
        if trial.hit_time is not None:
            self.hits += 1
            self.latency_sum += trial.hit_time - trial.started
            self.efficiency_sum += trial.efficiency
            self.deviation_sum += trial.deviation
            if trial.onset is not None:
                self.movement_hits += 1
                self.movement_sum += trial.hit_time - trial.onset
        if overshoot is not None:
            self.overshoot_count += 1
            self.overshoot_sum += overshoot
        self.traces.append(trial.trace())

    def merge(self, other: "FlickSector") -> None:
        for field in self.__dataclass_fields__:
            if field != "traces":
                setattr(self, field, getattr(self, field) + getattr(other, field))
        self.traces.extend(other.traces)


class FlickTrial:
    def __init__(self, target: Point, radius: float, started: float):
        self.target, self.radius, self.started = target, radius, started
        self.sector = sector_index(target)
        self.distance = hypot(*target)
        self.direction = (target[0] / self.distance, target[1] / self.distance)
        self.hit_time = None
        self.onset = None
        self.points = [(0.0, 0.0)]
        self.contact = None
        self.last_sample = started
        self.last_point = self.points[0]
        self.path_length = 0.0
        self.efficiency = 0.0
        self.deviation = 0.0
        self.peak = 0.0

    def move(self, point: Point, now: float, hit_fraction: float | None) -> None:
        last_x, last_y = self.last_point
        x, y = point
        x = last_x + ((x - last_x + 180) % 360 - 180)
        point = (x, y)
        if self.hit_time is None:
            fraction = 1.0 if hit_fraction is None else hit_fraction
            end_x = last_x + fraction * (x - last_x)
            end_y = last_y + fraction * (y - last_y)
            if self.onset is None and hypot(end_x, end_y) >= REACTION_THRESHOLD_DEG:
                self.onset = now
            self.path_length += hypot(end_x - last_x, end_y - last_y)
            direction_x, direction_y = self.direction
            self.deviation = max(self.deviation, abs(end_x * direction_y - end_y * direction_x))
            if hit_fraction is not None:
                self.hit_time = now
                self.contact = len(self.points)
                self.points.append((end_x, end_y))
                self.efficiency = min(1.0, hypot(end_x, end_y) / self.path_length) if self.path_length else 0
        if self.hit_time is not None:
            along = x * self.direction[0] + y * self.direction[1]
            self.peak = max(self.peak, along - self.distance - self.radius)
        if now - self.last_sample >= TRACE_INTERVAL:
            self.points.append(point)
            self.last_sample = now
        self.last_point = point

    def trace(self) -> FlickTrace:
        points = self.points if self.last_point == self.points[-1] else [*self.points, self.last_point]
        latency = None if self.hit_time is None else self.hit_time - self.started
        return FlickTrace(self.target, self.radius, tuple(points), self.contact, latency)
