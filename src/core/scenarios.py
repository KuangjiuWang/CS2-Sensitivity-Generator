"""Original training scenarios with seeded target streams."""
from bisect import bisect_right
from dataclasses import dataclass
from math import hypot
from random import Random


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    instruction: str
    count: int
    radius: float
    width: float
    height: float
    target_rate: float = 2.0


SCENARIOS = (
    Scenario("linear", "多段直线追枪", "点完五颗固定金球再生成一组。", 5, .88, 20, 12),
    Scenario("micro", "VT sky Dots Micro Csgo", "两颗小球在窄走廊内分段变速横移，跟住并点中。", 2, .67, 10, 5, 3.0),
    Scenario("six", "六目标终极", "点击六个细小静止靶，命中后补入新靶。", 6, .46, 21, 13, 2.5),
    Scenario("wall", "Wide wide wall 6 targets", "用大幅转向找到六个较大的静止球，再做微调。", 6, 1.02, 52, 16, 2.2),
    Scenario("phase", "VT Phaseshot Wide Small", "先转向点中主靶，再微调击中两个更小的后续靶。", 2, .96, 38, 15, 2.2),
    Scenario("moving", "VCT NA-YAY", "五颗小球会变速、短停和变向，点中后才补靶。", 5, .58, 29, 10, 1.8),
)
PHASE_SIZE = (1., .65, .39)
TRAINING_DURATIONS = (15, 30, 60)


@dataclass(frozen=True)
class MotionPath:
    times: tuple[float, ...]
    points: tuple[tuple[float, float], ...]

    def position(self, elapsed: float) -> tuple[float, float]:
        index = bisect_right(self.times, max(0., elapsed))
        if index == len(self.times):
            return self.points[-1]
        start, end = self.times[index - 1], self.times[index]
        t = (max(0., elapsed) - start) / (end - start)
        weight = t * t * (3 - 2 * t)
        x, y = self.points[index - 1]
        dx, dy = self.points[index]
        return x + weight * (dx - x), y + weight * (dy - y)


def motion_path(spec: Scenario, random: Random, x: float, y: float, bottom: float, top: float) -> MotionPath:
    times = [0.]
    points = [(x, y)]
    horizontal_only = spec.key == "micro"
    while times[-1] < max(TRAINING_DURATIONS):
        if random.random() < (.10 if horizontal_only else .24):
            times.append(times[-1] + random.uniform(.06, .24))
            points.append((x, y))
        direction = random.choice((-1, 1))
        distance = random.uniform(2., 7.) if horizontal_only else random.uniform(2.5, 10.)
        if abs(x + direction * distance) > spec.width:
            direction = -direction
        next_x = x + direction * distance
        next_y = y if horizontal_only else max(bottom, min(top, y + random.uniform(-1.6, 1.6)))
        speed = random.uniform(6, 10) if horizontal_only else random.uniform(4.5, 9)
        times.append(times[-1] + hypot(next_x - x, next_y - y) / speed)
        x, y = next_x, next_y
        points.append((x, y))
    return MotionPath(tuple(times), tuple(points))


@dataclass(frozen=True)
class Target:
    x: float
    y: float
    radius: float
    born: float
    phase: int = 0
    motion: MotionPath | None = None

    def position(self, now: float) -> tuple[float, float]:
        if self.motion is not None:
            return self.motion.position(now - self.born)
        return self.x, self.y


class ClickField:
    def __init__(self, scenario: Scenario, seed: int):
        self.scenario = scenario
        random = Random(seed)
        self.streams = [Random(random.getrandbits(64)) for _ in range(scenario.count)]
        self.targets: list[Target | None] = [None] * scenario.count
        for slot in range(scenario.count):
            self.replace(slot, 0)

    def replace(self, slot: int, now: float) -> None:
        spec, random = self.scenario, self.streams[slot]
        previous = self.targets[slot]
        phase = (previous.phase + 1) % 3 if previous is not None and spec.key == "phase" else 0
        radius = spec.radius * PHASE_SIZE[phase]
        occupied = [(t.position(now), (radius + t.radius) * 1.7)
                    for i, t in enumerate(self.targets) if t is not None and i != slot]
        if previous is not None:
            occupied.append((previous.position(now), radius * 2.5))
        bottom, top = -spec.height, spec.height
        if spec.key == "micro":
            bottom, top = (-4.2, -1.3) if slot == 0 else (1.3, 4.2)
        elif spec.key == "moving":
            bottom, top = 3.5 - spec.height * .8, 3.5 + spec.height * .8
        for _ in range(48):
            x = random.uniform(-spec.width, spec.width)
            y = random.uniform(bottom, top)
            if spec.key == "phase":
                if phase:
                    x, y = previous.x + random.uniform(-3, 3), previous.y + random.uniform(-2.6, 2.6)
                else:
                    x = random.uniform(spec.width * .40, spec.width) * (-1 if slot == 0 else 1)
            x = max(-spec.width, min(spec.width, x))
            y = max(bottom, min(top, y))
            if all(hypot(x - px, y - py) >= spacing for (px, py), spacing in occupied):
                break
        else:
            # An open position is guaranteed by the field size and the small target count.
            x, y = next((x, y) for x in (-spec.width, 0, spec.width)
                        for y in (bottom, (bottom + top) / 2, top)
                        if all(hypot(x - px, y - py) >= spacing for (px, py), spacing in occupied))
        motion = None
        if spec.key in ("micro", "moving"):
            motion = motion_path(spec, Random(random.getrandbits(64)), x, y, bottom, top)
        self.targets[slot] = Target(x, y, radius, now, phase, motion)


class FixedWave:
    """Stationary targets are removed on hit, and a clear board starts a new wave."""
    def __init__(self, scenario: Scenario, seed: int):
        self.scenario = scenario
        self.random = Random(seed)
        self.previous_layout: list[tuple[float, float]] = []
        self.targets = self.spawn(0)

    def spawn(self, now: float) -> list[Target | None]:
        spec = self.scenario
        spacing = spec.radius * 5
        previous_spacing = spec.radius * 3
        layout = []
        while len(layout) < spec.count:
            point = (self.random.uniform(-spec.width + spec.radius, spec.width - spec.radius),
                     self.random.uniform(-spec.height + spec.radius, spec.height - spec.radius))
            x, y = point
            if any(hypot(x - px, y - py) < spacing for px, py in layout):
                continue
            if any(hypot(x - px, y - py) < previous_spacing for px, py in self.previous_layout):
                continue
            layout.append(point)
        self.previous_layout = layout
        return [Target(x, y, spec.radius, now) for x, y in layout]

    def replace(self, slot: int, now: float) -> None:
        self.targets[slot] = None
        if all(target is None for target in self.targets):
            self.targets = self.spawn(now)
