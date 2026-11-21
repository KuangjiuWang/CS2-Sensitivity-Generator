"""Lateral movement in CS2 world units, projected at a fixed forward depth."""
from dataclasses import dataclass
from math import degrees, sqrt

# m_flMaxSpeed in the CS2 weapons.vdata mirror linked in README.md.
WEAPON_SPEEDS = (("AK-47", 215), ("M4A4 / M4A1-S", 225), ("AWP 未开镜", 200),
                 ("AWP 开镜", 100), ("持刀", 250))
DEFAULT_WEAPON_SPEED = WEAPON_SPEEDS[0][1]
DEFAULT_DISTANCE = 600
DEFAULT_DIAMETER_DEG = 1.6
RAMP_SECONDS = 0.18
REACTION_SECONDS = 0.20

# Offsets as fractions of depth. Short reversals interrupt longer strafes.
STOPS = ((0, .16), (.21, .10), (-.20, .12), (-.12, .06), (-.22, .09),
         (.19, .08), (-.16, .14), (.22, .07), (.13, .06), (.19, .12), (0, 0))


def center_angular_speed(speed: float, depth: float) -> float:
    """Degrees per second for a perpendicular crossing at x=0."""
    return degrees(speed / depth)


@dataclass(frozen=True)
class Strafe:
    start: float
    end: float
    ramp: float
    travel: float
    rest: float
    speed: float

    def sample(self, seconds: float) -> tuple[float, int]:
        """Return lateral world position and signed direction during settled cruise."""
        sign = 1 if self.end > self.start else -1
        if seconds >= self.travel:
            return self.end, 0
        if seconds < self.ramp:
            distance = self.speed * seconds ** 2 / (2 * self.ramp)
        elif seconds >= self.travel - self.ramp:
            remaining = self.travel - seconds
            distance = abs(self.end - self.start) - self.speed * remaining ** 2 / (2 * self.ramp)
        else:
            distance = self.speed * (seconds - self.ramp / 2)
            settled = seconds >= REACTION_SECONDS
            return self.start + sign * distance, sign if settled else 0
        return self.start + sign * distance, 0


class TrackingPath:
    def __init__(self, speed: int = DEFAULT_WEAPON_SPEED, depth: int = DEFAULT_DISTANCE) -> None:
        if speed not in dict(WEAPON_SPEEDS).values() or depth <= 0:
            raise ValueError("Expected a supported weapon speed and positive forward distance")
        self.depth = depth
        self.initial_hold = STOPS[0][1]
        self.strafes = []
        acceleration = speed / RAMP_SECONDS
        for (from_offset, _), (to_offset, rest) in zip(STOPS, STOPS[1:]):
            start, end = from_offset * depth, to_offset * depth
            distance = abs(end - start)
            peak = min(speed, sqrt(distance * acceleration))
            ramp = peak / acceleration
            travel = distance / peak + ramp
            self.strafes.append(Strafe(start, end, ramp, travel, rest, peak))
        self.cycle = self.initial_hold + sum(strafe.travel + strafe.rest for strafe in self.strafes)

    def sample(self, elapsed: float) -> tuple[float, int]:
        """Return fixed-height projection-plane x and a qualified direction sign."""
        cycle_number, phase = divmod(max(0.0, elapsed), self.cycle)
        mirror = -1 if cycle_number % 2 else 1
        remaining = phase - self.initial_hold
        if remaining < 0:
            return 0.0, 0
        for strafe in self.strafes:
            leg = strafe.travel + strafe.rest
            if remaining < leg:
                x, direction = strafe.sample(remaining)
                return mirror * x / self.depth, mirror * direction
            remaining -= leg
        return 0.0, 0  # Floating-point rounding at the cycle boundary.
