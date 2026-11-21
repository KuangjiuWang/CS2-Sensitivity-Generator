"""Measurements in angle, elapsed seconds and duration ratios."""
from dataclasses import dataclass, field

from core.flick_analysis import FlickSector, MIN_DIRECTION_SAMPLES, REACTION_THRESHOLD_DEG, SECTOR_LABELS


@dataclass
class FlickStats:
    attempts: int = 0
    hits: int = 0
    latency_sum: float = 0
    completed_overshoots: int = 0
    overshoot_sum: float = 0
    sectors: list[FlickSector] = field(default_factory=lambda: [FlickSector() for _ in SECTOR_LABELS])

    def hit(self, latency: float) -> None:
        self.hits += 1
        self.latency_sum += latency

    def record_overshoot(self, degrees: float) -> None:
        self.completed_overshoots += 1
        self.overshoot_sum += degrees

    @property
    def mean_latency(self) -> float:
        return self.latency_sum / self.hits if self.hits else 0

    @property
    def mean_overshoot(self) -> float:
        return self.overshoot_sum / self.completed_overshoots if self.completed_overshoots else 0

    def missing_directions(self) -> list[int]:
        return [index for index, sector in enumerate(self.sectors)
                for _ in range(max(0, MIN_DIRECTION_SAMPLES - sector.attempts))]

    def timings(self) -> tuple[float | None, float | None]:
        starts = sum(sector.starts for sector in self.sectors)
        hits = sum(sector.movement_hits for sector in self.sectors)
        return (sum(sector.reaction_sum for sector in self.sectors) / starts if starts else None,
                sum(sector.movement_sum for sector in self.sectors) / hits if hits else None)

    def merge(self, supplement: "FlickStats") -> None:
        self.attempts += supplement.attempts
        self.hits += supplement.hits
        self.latency_sum += supplement.latency_sum
        self.completed_overshoots += supplement.completed_overshoots
        self.overshoot_sum += supplement.overshoot_sum
        for old, new in zip(self.sectors, supplement.sectors):
            old.merge(new)


@dataclass
class TrackingStats:
    elapsed: float = 0
    on_target: float = 0
    behind: float = 0
    ahead: float = 0
    motion_time: float = 0
    starts: int = 0
    reaction_sum: float = 0
    locks: int = 0
    movement_sum: float = 0
    centering_sum: float = 0

    def sample(self, duration: float, inside: bool, along: float | None, radius: float,
               *, error_radii: float) -> None:
        self.elapsed += duration
        self.centering_sum += duration * max(0.0, 1.0 - error_radii / 4)
        if inside:
            self.on_target += duration
        if along is None:
            return
        self.motion_time += duration
        if along > radius:
            self.behind += duration
        elif along < -radius:
            self.ahead += duration

    @property
    def accuracy(self) -> float:
        return self.on_target / self.elapsed if self.elapsed else 0

    @property
    def centering(self) -> float:
        return self.centering_sum / self.elapsed if self.elapsed else 0

    @property
    def lag_rate(self) -> float:
        return self.behind / self.motion_time if self.motion_time else 0

    @property
    def lead_rate(self) -> float:
        return self.ahead / self.motion_time if self.motion_time else 0

    def timings(self) -> tuple[float | None, float | None]:
        return (self.reaction_sum / self.starts if self.starts else None,
                self.movement_sum / self.locks if self.locks else None)


class TrackingTiming:
    """Measure a response after the target starts a new strafe."""
    def __init__(self, stats: TrackingStats):
        self.stats = stats
        self.motion = None
        self.initial_yaw = 0.0
        self.response = None
        self.inside_since = None
        self.locked = False

    def observe(self, motion: tuple[float, int] | None, elapsed: float, yaw: float, inside: bool) -> None:
        if motion != self.motion:
            self.motion = motion
            self.initial_yaw = yaw
            self.response = self.inside_since = None
            self.locked = False
        if motion is None or self.locked:
            return
        started, direction = motion
        moved = (yaw - self.initial_yaw + 180) % 360 - 180
        if self.response is None:
            if moved * direction < REACTION_THRESHOLD_DEG:
                return
            self.response = elapsed
            self.stats.starts += 1
            self.stats.reaction_sum += elapsed - started
        if not inside:
            self.inside_since = None
        elif self.inside_since is None:
            self.inside_since = elapsed
        elif elapsed - self.inside_since >= .080:
            self.stats.locks += 1
            self.stats.movement_sum += self.inside_since - self.response
            self.locked = True
