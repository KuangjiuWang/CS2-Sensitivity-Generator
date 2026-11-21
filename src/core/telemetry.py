"""Measurements in angle, elapsed seconds and duration ratios."""
from dataclasses import dataclass


@dataclass
class FlickStats:
    attempts: int = 0
    hits: int = 0
    latency_sum: float = 0
    completed_overshoots: int = 0
    overshoot_sum: float = 0

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


@dataclass
class TrackingStats:
    elapsed: float = 0
    on_target: float = 0
    behind: float = 0
    ahead: float = 0
    motion_time: float = 0

    def sample(self, duration: float, inside: bool, along: float | None, radius: float) -> None:
        self.elapsed += duration
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
    def lag_rate(self) -> float:
        return self.behind / self.motion_time if self.motion_time else 0

    @property
    def lead_rate(self) -> float:
        return self.ahead / self.motion_time if self.motion_time else 0
