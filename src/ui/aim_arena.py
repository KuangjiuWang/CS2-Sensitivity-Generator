"""Borderless camera-based practice arena and monotonic scoring."""
from collections import deque
from math import ceil, cos, hypot, radians, tan
from time import perf_counter

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from core.cs2_math import Camera, Preset, VERTICAL_TANGENT
from core.crosshair import Crosshair
from core.flick_analysis import FlickTrial, TRACE_INTERVAL, local_angles
from core.raw_input import RawMouseInput
from core.recommendation import STATIC_TASKS, first_pass_error, shot_error
from core.scenarios import ClickField, FixedWave, Scenario
from core.telemetry import ClickStats
from ui.crosshair import draw_crosshair
from ui.practice_scene import ROOMS, draw_room
from ui.toast import Toast

ARENA_BACKGROUND = QColor("#151920")


class AimArena(QWidget):
    finished = Signal(object, str)

    def __init__(self, scenario: Scenario, sensitivity: float, preset: Preset,
                 duration: int, crosshair: Crosshair,
                 *, seed: int, stage: str = ""):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.scenario, self.sensitivity, self.preset = scenario, sensitivity, preset
        self.duration, self.crosshair, self.stage = duration, crosshair, stage
        self.stage_toast = Toast(self) if stage else None
        self.setWindowTitle("CS2 Sensitivity Generator · 测试场")
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.raw = RawMouseInput(self.move_camera, on_left_down=self.shoot)
        self.camera = Camera()
        self.world = Camera()
        self.field = FixedWave(scenario, seed) if scenario.key == "linear" else ClickField(scenario, seed)
        self.stats = ClickStats()
        self.timer = QTimer(self, timerType=Qt.TimerType.PreciseTimer, interval=8)
        self.timer.timeout.connect(self.tick)
        self.start_time = None
        self.end_time = None
        self.input_deadline = None
        self.test_started = False
        self.trace = deque(maxlen=400)
        self.shot_start = 0.
        self.shot_basis = self.camera.basis()
        self.done = False
        self.error = ""

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
            self.shot_basis = self.camera.basis()
            self.shot_start = self.start_time
            self.test_started = True
        until = min(now, self.end_time)
        self.stats.elapsed = until - self.start_time
        if now >= self.end_time:
            self.done = True
            self.close()

    def move_camera(self, dx: int, dy: int) -> None:
        if self.input_deadline is None or self.done or not self.isActiveWindow():
            return
        now = perf_counter()
        if self.start_time is None:
            self.start_time = now + 3.
            self.end_time = self.start_time + self.duration
        if now < self.start_time:
            return
        self.advance(now)
        if self.done:
            return
        self.camera.move(dx, dy, self.sensitivity)
        if not self.trace or now - self.trace[-1][0] >= TRACE_INTERVAL:
            self.trace.append((now, local_angles(self.camera.basis()[0], self.shot_basis)))

    def world_ray(self, x: float, y: float):
        yaw, pitch = radians(x), radians(y)
        return self.world.ray(tan(yaw), tan(pitch) / cos(yaw))

    def click_targets(self, elapsed: float):
        for slot, target in enumerate(self.field.targets):
            if target is not None:
                yield slot, target, self.world_ray(*target.position(elapsed)), tan(radians(target.radius))

    def shoot(self) -> None:
        if self.done or self.start_time is None or not self.isActiveWindow():
            return
        now = perf_counter()
        if now < self.start_time:
            return
        self.advance(now)
        if self.done:
            return
        choices = []
        fixed = isinstance(self.field, FixedWave)
        for slot, target, ray, radius in self.click_targets(now - self.start_time):
            point = self.camera.project(ray)
            if point is not None:
                choices.append((hypot(*point) / radius, slot, target, ray))
        self.stats.attempts += 1
        hit = False
        if choices:
            error, slot, target, ray = min(choices)
            hit = error <= 1
            if hit:
                self.stats.hit(now - self.shot_start)
                if not fixed:
                    self.stats.points += (1, 1.25, 1.65)[target.phase]
                self.field.replace(slot, now - self.start_time)
            angles = local_angles(ray, self.shot_basis)
            if hypot(*angles) >= .1:
                trial = FlickTrial(angles, target.radius, self.shot_start)
                for stamp, point in self.trace:
                    trial.move(point, stamp)
                aim = local_angles(self.camera.basis()[0], self.shot_basis)
                trial.move(aim, now)
                trial.shoot(now, hit)
                self.stats.sectors[trial.sector].add(trial, None)
                error = first_pass_error(angles, target.radius, self.trace) if hit and self.scenario.key in STATIC_TASKS else None
                if error is None:
                    error = shot_error(angles, aim, target.radius)
                if error is not None:
                    self.stats.first_pass_errors.append((trial.sector, error))
                if fixed and hit:
                    self.stats.points += .5 + .5 * trial.efficiency
            elif fixed and hit:
                self.stats.points += .5
        self.shot_start = now
        self.shot_basis = self.camera.basis()
        self.trace.clear()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), ARENA_BACKGROUND)
        x, y, w, h = self.preset.viewport(self.width(), self.height())
        viewport = QRectF(x, y, w, h)
        center = viewport.center()
        sx, sy = w / (2 * self.preset.horizontal_tangent), h / (2 * VERTICAL_TANGENT)
        painter.setClipRect(viewport)
        draw_room(painter, viewport, self.camera, sx, sy, ROOMS[self.scenario.key])

        def screen_point(point):
            return QPointF(center.x() + point[0] * sx, center.y() + point[1] * sy)

        now = perf_counter()
        if self.test_started:
            elapsed = min(now, self.end_time) - self.start_time
            for _, _, ray, radius in self.click_targets(elapsed):
                point = self.camera.project(ray)
                if point is not None:
                    pixel = screen_point(point)
                    if viewport.adjusted(-sx * radius, -sy * radius, sx * radius, sy * radius).contains(pixel):
                        painter.setPen(Qt.PenStyle.NoPen)
                        rx, ry = sx * radius, sy * radius
                        painter.save()
                        painter.translate(pixel)
                        painter.scale(rx, ry)
                        shade = QRadialGradient(-.24, -.33, 1.24)
                        shade.setColorAt(0, QColor("#F8DF79"))
                        shade.setColorAt(.62, QColor("#D7AF39"))
                        shade.setColorAt(1, QColor("#87601A"))
                        painter.setBrush(shade)
                        painter.drawEllipse(QPointF(), 1, 1)
                        painter.restore()

        stretch = w / (h * self.preset.ratio) if self.preset.stretched else 1.0
        draw_crosshair(painter, center, self.crosshair, h, stretch)
        painter.setPen(QColor("#DCE4EF"))
        title = self.scenario.title
        painter.drawText(QRectF(x + 24, y + 20, w - 48, 28), Qt.AlignmentFlag.AlignLeft,
                         f"{self.stage}  ·  {title}" if self.stage else title)
        painter.drawText(QRectF(x + 24, y + 20, w - 48, 28), Qt.AlignmentFlag.AlignRight, "ESC  退出")
        if self.start_time is None:
            label = "移动鼠标以开始测试"
        elif now < self.start_time:
            label = f"已收到鼠标输入   ·   {ceil(self.start_time - now)}"
        else:
            remaining = max(0, self.end_time - now)
            score = f"{self.stats.hits} 命中   ·   {self.stats.accuracy:.0%} 准确率   ·   {self.stats.points:.1f} 分"
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
