"""Borderless camera-based practice arena and monotonic scoring."""
from dataclasses import dataclass
from math import atan, ceil, cos, degrees, hypot, pi, radians, sin, tan
from random import Random
from time import perf_counter

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from core.cs2_math import Camera, M_YAW, Preset, VERTICAL_TANGENT, segment_hit
from core.raw_input import RawMouseInput
from core.telemetry import FlickStats, TrackingStats
from core.tracking_path import DEFAULT_DIAMETER_DEG, DEFAULT_DISTANCE, DEFAULT_WEAPON_SPEED, TrackingPath

FLICK_RADIUS = 0.037
TRACK_BIAS_DEADZONE = tan(radians(1))
OVERSHOOT_WINDOW = 0.18


@dataclass(frozen=True)
class Crosshair:
    color: str = "#E7FD8B"
    length: int = 8
    gap: int = 4
    width: int = 2
    dot: bool = True

    def draw(self, painter: QPainter, center: QPointF) -> None:
        for color, width in (("#10131D", self.width + 2), (self.color, self.width)):
            painter.setPen(QPen(QColor(color), width))
            for x, y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                start = center + QPointF(x * self.gap, y * self.gap)
                end = center + QPointF(x * (self.gap + self.length), y * (self.gap + self.length))
                painter.drawLine(start, end)
            if self.dot:
                painter.drawPoint(center)


class AimArena(QWidget):
    finished = Signal(object, str)

    def __init__(self, mode: str, sensitivity: float, preset: Preset,
                 duration: int, crosshair: Crosshair, tracking_speed: int = DEFAULT_WEAPON_SPEED,
                 tracking_distance: int = DEFAULT_DISTANCE, tracking_diameter: float = DEFAULT_DIAMETER_DEG):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.mode, self.sensitivity, self.preset = mode, sensitivity, preset
        self.duration, self.crosshair = duration, crosshair
        self.setWindowTitle("CS2 Sensitivity Generator · 测试场")
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.raw = RawMouseInput(self.move_camera)
        self.camera = Camera()
        self.tracking_path = TrackingPath(tracking_speed, tracking_distance)
        self.tracking_radius = tan(radians(tracking_diameter / 2))
        self.stats = FlickStats() if mode == "flick" else TrackingStats()
        self.random = Random()
        self.timer = QTimer(self, timerType=Qt.TimerType.PreciseTimer, interval=8)
        self.timer.timeout.connect(self.tick)
        self.start_time = None
        self.end_time = None
        self.input_deadline = None
        self.test_started = False
        self.track_camera = None
        self.target = None
        self.spawn_time = 0.0
        self.last_sample = 0.0
        self.hit_time = None
        self.peak = 0.0
        self.direction = (0.0, 0.0)
        self.done = False
        self.error = ""
        # Static reference dots give visible camera motion even after losing the target.
        self.landmarks = [Camera(yaw, pitch).ray(0, 0)
                          for pitch in range(-60, 61, 15) for yaw in range(0, 360, 15)]

    def open_on(self, screen) -> None:
        self.winId()
        self.windowHandle().setScreen(screen)
        self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.activateWindow()
        self.timer.start()
        self.activation_deadline = perf_counter() + 2.0

    def tick(self) -> None:
        now = perf_counter()
        if self.input_deadline is None:
            if self.isActiveWindow():
                self.input_deadline = now + 12.0
                try:
                    self.raw.start(int(self.winId()))
                except OSError as error:
                    self.error = f"无法启动 Win32 Raw Input：{error}"
                    self.close()
                    return
            elif now >= self.activation_deadline:
                self.error = "测试窗口未获得焦点，请重试。"
                self.close()
                return
        else:
            if not self.isActiveWindow():
                self.error = "测试窗口失去焦点，本轮已取消。"
                self.close()
                return
            if self.start_time is not None:
                self.advance(now)
            elif now >= self.input_deadline:
                self.error = "12 秒内未收到鼠标原始移动。本轮未计分，请连接鼠标后重试。"
                self.close()
                return
        self.update()

    def advance(self, now: float) -> None:
        if now < self.start_time:
            return
        if not self.test_started:
            self.camera.yaw = self.camera.pitch = 0
            self.test_started = True
        until = min(now, self.end_time)
        if self.mode == "tracking":
            if self.track_camera is None:
                self.track_camera = Camera(self.camera.yaw, self.camera.pitch)
            self.integrate_tracking(until)
        elif self.target is None:
            self.spawn_flick(until)
        elif self.hit_time is not None and until >= self.hit_time + OVERSHOOT_WINDOW:
            self.stats.record_overshoot(self.peak)
            if until < self.end_time:
                self.spawn_flick(until)
        elif self.hit_time is None and until >= self.spawn_time + 2.5 and until < self.end_time:
            self.spawn_flick(until)
        if now >= self.end_time:
            self.done = True
            self.close()

    def move_camera(self, dx: int, dy: int) -> None:
        if self.input_deadline is None or self.done or not self.isActiveWindow():
            return
        now = perf_counter()
        if self.start_time is None:
            self.start_time = now + 3.0
            self.end_time = self.start_time + self.duration
            self.last_sample = self.start_time
        if now < self.start_time:
            self.camera.move(dx, dy, self.sensitivity)
            return
        self.advance(now)
        if self.done:
            return
        if self.mode != "flick" or self.target is None:
            self.camera.move(dx, dy, self.sensitivity)
            return
        # Subdivide unusually large packets so a fast flick can cross a small target.
        steps = max(1, ceil(max(abs(dx), abs(dy)) * self.sensitivity * M_YAW / 2))
        for _ in range(steps):
            before = self.camera.project(self.target)
            self.camera.move(dx / steps, dy / steps, self.sensitivity)
            after = self.camera.project(self.target)
            if before is None or after is None:
                continue
            if self.hit_time is None and segment_hit(before, after, FLICK_RADIUS) is not None:
                self.hit_time = now
                self.stats.hit(now - self.spawn_time)
            if self.hit_time is not None:
                beyond = -(after[0] * self.direction[0] + after[1] * self.direction[1])
                angle = degrees(atan(beyond) - atan(FLICK_RADIUS))
                self.peak = max(self.peak, angle)

    def spawn_flick(self, now: float) -> None:
        angle = self.random.uniform(0, 2 * pi)
        distance = self.random.uniform(.28, .57)
        x, y = cos(angle), .72 * sin(angle)
        if abs(self.camera.pitch) > 32:
            y = -abs(y) if self.camera.pitch > 0 else abs(y)
        length = hypot(x, y)
        self.direction = (x / length, y / length)
        self.target = self.camera.ray(x * distance, y * distance)
        self.spawn_time = now
        self.hit_time = None
        self.peak = 0
        self.stats.attempts += 1

    def tracking_ray(self, elapsed: float):
        x, _ = self.tracking_path.sample(elapsed)
        return self.track_camera.ray(x, 0)

    def integrate_tracking(self, until: float) -> None:
        while self.last_sample < until:
            end = min(until, self.last_sample + 1 / 120)
            elapsed = (end + self.last_sample) / 2 - self.start_time
            x, direction = self.tracking_path.sample(elapsed)
            point = self.camera.project(self.track_camera.ray(x, 0))
            inside = point is not None and hypot(*point) <= self.tracking_radius
            along = None
            if point is not None and direction:
                ahead = self.camera.project(self.track_camera.ray(x + direction * .001, 0))
                if ahead is not None:
                    vx, vy = ahead[0] - point[0], ahead[1] - point[1]
                    length = hypot(vx, vy)
                    if length > 0:
                        along = (point[0] * vx + point[1] * vy) / length
            self.stats.sample(end - self.last_sample, inside, along, TRACK_BIAS_DEADZONE)
            self.last_sample = end

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#080A11"))
        x, y, w, h = self.preset.viewport(self.width(), self.height())
        viewport = QRectF(x, y, w, h)
        center = viewport.center()
        sx, sy = w / (2 * self.preset.horizontal_tangent), h / (2 * VERTICAL_TANGENT)
        painter.setClipRect(viewport)
        painter.fillRect(viewport, QColor("#121824"))

        def screen_point(point):
            return QPointF(center.x() + point[0] * sx, center.y() + point[1] * sy)

        painter.setPen(QPen(QColor("#324256"), 2))
        for ray in self.landmarks:
            point = self.camera.project(ray)
            if point is not None:
                pixel = screen_point(point)
                if viewport.contains(pixel):
                    painter.drawPoint(pixel)

        target = self.target
        radius = FLICK_RADIUS
        now = perf_counter()
        if self.track_camera is not None:
            target = self.tracking_ray(min(now, self.end_time) - self.start_time)
            radius = self.tracking_radius
        if target is not None:
            point = self.camera.project(target)
            if point is not None:
                active = self.hit_time is not None or hypot(*point) <= radius
                color = QColor("#D8F576" if active else "#63DCE8")
                pixel = screen_point(point)
                if viewport.adjusted(-sx * radius, -sy * radius, sx * radius, sy * radius).contains(pixel):
                    painter.setPen(QPen(color, 2))
                    color.setAlpha(50)
                    painter.setBrush(color)
                    painter.drawEllipse(pixel, sx * radius, sy * radius)

        self.crosshair.draw(painter, center)
        painter.setPen(QColor("#ECF1FA"))
        painter.drawText(QRectF(x + 24, y + 20, w - 48, 28), Qt.AlignmentFlag.AlignLeft,
                         "HOVER FLICK  ·  悬停拉枪" if self.mode == "flick" else "SMOOTH TRACKING  ·  动态跟枪")
        painter.drawText(QRectF(x + 24, y + 20, w - 48, 28), Qt.AlignmentFlag.AlignRight, "ESC  退出")
        if self.start_time is None:
            label = "移动鼠标以开始测试"
        elif now < self.start_time:
            label = f"已收到鼠标输入   ·   {ceil(self.start_time - now)}"
        else:
            remaining = max(0, self.end_time - now)
            score = f"{self.stats.hits} 次命中" if self.mode == "flick" else f"{self.stats.accuracy:.0%} 命中时长"
            label = f"{remaining:05.2f} s   ·   {score}"
        painter.drawText(QRectF(x, y + 52, w, 28), Qt.AlignmentFlag.AlignHCenter, label)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        try:
            self.raw.stop()
        except OSError as error:
            self.error = str(error)
        super().closeEvent(event)
        self.finished.emit(self.stats if self.done and not self.error else None, self.error)
