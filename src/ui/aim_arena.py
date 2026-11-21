"""Borderless camera-based practice arena and monotonic scoring."""
from math import atan, ceil, cos, degrees, hypot, radians, tan
from random import Random
from time import perf_counter

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from core.cs2_math import Camera, M_YAW, Preset, VERTICAL_TANGENT, segment_hit
from core.crosshair import Crosshair
from core.flick_analysis import FlickTrial, SECTOR_LABELS, local_angles
from core.practice_plan import FlickPlan, target_at
from core.raw_input import RawMouseInput
from core.telemetry import FlickStats, TrackingStats, TrackingTiming
from core.tracking_path import DEFAULT_DIAMETER_DEG, DEFAULT_DISTANCE, DEFAULT_WEAPON_SPEED, TrackingPath
from ui.crosshair import draw_crosshair
from ui.toast import Toast

FLICK_RADIUS = 0.037
TRACK_BIAS_DEADZONE = tan(radians(1))
OVERSHOOT_WINDOW = 0.18
FLICK_TIMEOUT = 2.5


class AimArena(QWidget):
    finished = Signal(object, str)

    def __init__(self, mode: str, sensitivity: float, preset: Preset,
                 duration: int, crosshair: Crosshair, tracking_speed: int = DEFAULT_WEAPON_SPEED,
                 tracking_distance: int = DEFAULT_DISTANCE, tracking_diameter: float = DEFAULT_DIAMETER_DEG,
                 *, plan: FlickPlan | None = None, stage: str = "", reverse_tracking: bool = False):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.mode, self.sensitivity, self.preset = mode, sensitivity, preset
        self.duration, self.crosshair = plan.duration if plan is not None else duration, crosshair
        self.plan, self.stage = plan, stage
        self.stage_toast = Toast(self) if stage else None
        self.plan_index = -1
        self.setWindowTitle("CS2 Sensitivity Generator · 测试场")
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.raw = RawMouseInput(self.move_camera)
        self.camera = Camera()
        self.tracking_path = TrackingPath(tracking_speed, tracking_distance, reverse=reverse_tracking)
        self.tracking_radius = tan(radians(tracking_diameter / 2))
        self.stats = FlickStats() if mode == "flick" else TrackingStats()
        self.tracking_timing = TrackingTiming(self.stats) if mode == "tracking" else None
        self.random = Random()
        self.timer = QTimer(self, timerType=Qt.TimerType.PreciseTimer, interval=8)
        self.timer.timeout.connect(self.tick)
        self.start_time = None
        self.end_time = None
        self.input_deadline = None
        self.test_started = False
        self.track_camera = None
        self.target = None
        self.last_sample = 0.0
        self.flick_trial = None
        self.flick_basis = self.camera.basis()
        self.sector_order = []
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
                if self.stage_toast is not None:
                    self.stage_toast.notify(f"{self.stage} · 移动鼠标开始")
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
        elif self.plan is not None:
            self.advance_plan(until)
        else:
            self.advance_flick(until)
        if now >= self.end_time:
            self.done = True
            self.close()

    def advance_flick(self, until: float) -> None:
        trial = self.flick_trial
        if trial is not None:
            hit = trial.hit_time is not None
            overshoot_ready = hit and until >= trial.hit_time + OVERSHOOT_WINDOW
            timed_out = not hit and until >= trial.started + FLICK_TIMEOUT
            if overshoot_ready or timed_out or until >= self.end_time:
                self.finish_target(until, timed_out)
        if self.flick_trial is None and until < self.end_time:
            self.spawn_flick(until)

    def advance_plan(self, until: float) -> None:
        count = len(self.plan.targets)
        due = min(count, int((until - self.start_time) / self.plan.interval + 1e-8))
        while self.plan_index < due:
            self.plan_index += 1
            boundary = self.start_time + self.plan_index * self.plan.interval
            if self.flick_trial is not None:
                self.finish_target(boundary, True)
            if self.plan_index < count:
                self.camera.yaw = self.camera.pitch = 0
                self.spawn_flick(boundary, self.plan.targets[self.plan_index])

    def finish_target(self, until: float, full_attempt: bool) -> None:
        trial = self.flick_trial
        hit = trial.hit_time is not None
        if hit or full_attempt:
            overshoot = trial.peak if hit and until >= trial.hit_time + OVERSHOOT_WINDOW else None
            self.stats.sectors[trial.sector].add(trial, overshoot)
            if overshoot is not None:
                self.stats.record_overshoot(overshoot)
        else:
            self.stats.attempts -= 1
        self.flick_trial = self.target = None

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
        trial = self.flick_trial
        if trial.hit_time is not None and now >= trial.hit_time + OVERSHOOT_WINDOW:
            self.camera.move(dx, dy, self.sensitivity)
            return
        # Subdivide unusually large packets so a fast flick can cross a small target.
        steps = max(1, ceil(max(abs(dx), abs(dy)) * self.sensitivity * M_YAW / 2))
        before = self.camera.project(self.target)
        for _ in range(steps):
            self.camera.move(dx / steps, dy / steps, self.sensitivity)
            after = self.camera.project(self.target)
            hit_fraction = None
            if trial.hit_time is None and before is not None and after is not None:
                hit_fraction = segment_hit(before, after, FLICK_RADIUS)
                if hit_fraction is not None:
                    self.stats.hit(now - trial.started)
            trial.move(local_angles(self.camera.basis()[0], self.flick_basis), now, hit_fraction)
            before = after

    def spawn_flick(self, now: float, target=None) -> None:
        if target is None:
            if not self.sector_order:
                self.sector_order = list(range(len(SECTOR_LABELS)))
                self.random.shuffle(self.sector_order)
            target = target_at(self.sector_order.pop(), self.random)
        yaw, pitch = (radians(value) for value in target)
        self.flick_basis = self.camera.basis()
        self.target = self.camera.ray(tan(yaw), tan(pitch) / cos(yaw))
        self.flick_trial = FlickTrial(target, degrees(atan(FLICK_RADIUS)), now)
        self.stats.attempts += 1

    def tracking_ray(self, elapsed: float):
        x, _ = self.tracking_path.sample(elapsed)
        return self.track_camera.ray(x, 0)

    def integrate_tracking(self, until: float) -> None:
        while self.last_sample < until:
            end = min(until, self.last_sample + 1 / 120)
            elapsed = (end + self.last_sample) / 2 - self.start_time
            x, direction, motion = self.tracking_path.frame(elapsed)
            point = self.camera.project(self.track_camera.ray(x, 0))
            error_radii = hypot(*point) / self.tracking_radius if point is not None else float("inf")
            inside = error_radii <= 1
            self.tracking_timing.observe(motion, elapsed, self.camera.yaw, inside)
            along = None
            if point is not None and direction:
                ahead = self.camera.project(self.track_camera.ray(x + direction * .001, 0))
                if ahead is not None:
                    vx, vy = ahead[0] - point[0], ahead[1] - point[1]
                    length = hypot(vx, vy)
                    if length > 0:
                        along = (point[0] * vx + point[1] * vy) / length
            self.stats.sample(end - self.last_sample, inside, along, TRACK_BIAS_DEADZONE, error_radii=error_radii)
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
                active = (self.flick_trial is not None and self.flick_trial.hit_time is not None
                          or hypot(*point) <= radius)
                color = QColor("#D8F576" if active else "#63DCE8")
                pixel = screen_point(point)
                if viewport.adjusted(-sx * radius, -sy * radius, sx * radius, sy * radius).contains(pixel):
                    painter.setPen(QPen(color, 2))
                    color.setAlpha(50)
                    painter.setBrush(color)
                    painter.drawEllipse(pixel, sx * radius, sy * radius)

        stretch = w / (h * self.preset.ratio) if self.preset.stretched else 1.0
        draw_crosshair(painter, center, self.crosshair, h, stretch)
        painter.setPen(QColor("#ECF1FA"))
        title = "悬停拉枪" if self.mode == "flick" else "动态跟枪"
        painter.drawText(QRectF(x + 24, y + 20, w - 48, 28), Qt.AlignmentFlag.AlignLeft,
                         f"{self.stage}  ·  {title}" if self.stage else title)
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
