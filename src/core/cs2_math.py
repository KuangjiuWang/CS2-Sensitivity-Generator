"""Physical sensitivity and rectilinear camera geometry."""
from dataclasses import dataclass
from math import atan, cos, degrees, isfinite, radians, sin, sqrt, tan

M_YAW = 0.022
M_PITCH = 0.022
VERTICAL_TANGENT = 3 / 4
PITCH_LIMIT = 89.0
Point = tuple[float, float]
Ray = tuple[float, float, float]

PROFILES = {
    "arm": (0.90, 270),
    "wrist": (0.42, 180),
    "hybrid": (0.67, 225),
}


@dataclass(frozen=True)
class Preset:
    label: str
    ratio: float
    stretched: bool = False

    @property
    def horizontal_tangent(self) -> float:
        return self.ratio * VERTICAL_TANGENT

    @property
    def horizontal_fov(self) -> float:
        return degrees(2 * atan(self.horizontal_tangent))

    def viewport(self, width: float, height: float) -> tuple[float, float, float, float]:
        if self.stretched:
            return 0, 0, width, height
        render_width = min(width, height * self.ratio)
        render_height = min(height, width / self.ratio)
        return (width - render_width) / 2, (height - render_height) / 2, render_width, render_height


PRESETS = (
    Preset("16:9 原生", 16 / 9),
    Preset("4:3 拉伸", 4 / 3, stretched=True),
    Preset("16:10", 16 / 10),
)


def positive(value: float) -> float:
    if not isfinite(value) or value <= 0:
        raise ValueError("Expected a finite positive value")
    return value


def edpi(dpi: float, sensitivity: float) -> float:
    return positive(dpi) * positive(sensitivity)


def cm_per_360(dpi: float, sensitivity: float) -> float:
    return 360 * 2.54 / (edpi(dpi, sensitivity) * M_YAW)


def sensitivity_for_cm(dpi: float, cm360: float) -> float:
    return 360 * 2.54 / (positive(dpi) * positive(cm360) * M_YAW)


def physical_baseline(dpi: float, pad_cm: float, profile: str) -> tuple[float, float, float]:
    fraction, turn = PROFILES[profile]
    swing_cm = positive(pad_cm) * fraction
    sensitivity = sensitivity_for_cm(dpi, swing_cm * 360 / turn)
    return sensitivity, swing_cm, turn


def cfg_text(sensitivity: float, zoom: float) -> str:
    return f'sensitivity "{positive(sensitivity):.3f}"\nzoom_sensitivity_ratio "{positive(zoom):.3f}"\n'


def console_text(sensitivity: float, zoom: float) -> str:
    return "; ".join(cfg_text(sensitivity, zoom).splitlines())


def dot(first: Ray, second: Ray) -> float:
    return sum(a * b for a, b in zip(first, second))


@dataclass
class Camera:
    yaw: float = 0
    pitch: float = 0

    def move(self, dx: float, dy: float, sensitivity: float) -> None:
        self.yaw = (self.yaw + dx * sensitivity * M_YAW) % 360
        self.pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, self.pitch + dy * sensitivity * M_PITCH))

    def basis(self) -> tuple[Ray, Ray, Ray]:
        yaw, pitch = radians(self.yaw), radians(self.pitch)
        sy, cy, sp, cp = sin(yaw), cos(yaw), sin(pitch), cos(pitch)
        return (sy * cp, sp, cy * cp), (cy, 0, -sy), (-sy * sp, cp, -cy * sp)

    def ray(self, x: float, y: float) -> Ray:
        forward, right, down = self.basis()
        return tuple(f + x * r + y * d for f, r, d in zip(forward, right, down))

    def project(self, target: Ray) -> Point | None:
        forward, right, down = self.basis()
        depth = dot(target, forward)
        if depth <= 1e-6:
            return None
        return dot(target, right) / depth, dot(target, down) / depth


def segment_hit(before: Point, after: Point, radius: float) -> float | None:
    """Fraction of a projected segment at first contact with the aim region."""
    x, y = before
    dx, dy = after[0] - x, after[1] - y
    offset = x * x + y * y - radius * radius
    if offset <= 0:
        return 0.0
    length_squared = dx * dx + dy * dy
    approach = x * dx + y * dy
    discriminant = approach * approach - length_squared * offset
    if length_squared == 0 or approach >= 0 or discriminant < 0:
        return None
    fraction = (-approach - sqrt(discriminant)) / length_squared
    return fraction if fraction <= 1 else None
