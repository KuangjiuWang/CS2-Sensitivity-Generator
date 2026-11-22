"""Borderless camera-based practice arena and monotonic scoring."""
from collections import deque
from math import ceil, cos, hypot, radians, tan
import sys
from time import perf_counter

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget

from core.cs2_math import Camera, Preset, VERTICAL_TANGENT
from core.crosshair import Crosshair
from core.flick_analysis import FlickTrial, TRACE_INTERVAL, local_angles
from core.platform_input import RawMouseInput
from core.recommendation import STATIC_TASKS, first_pass_error, shot_error
from core.scenarios import ClickField, FixedWave, Scenario
from core.telemetry import ClickStats
from ui.crosshair import draw_crosshair
from ui.practice_scene import ROOMS, draw_room
from ui.toast import Toast

ARENA_BACKGROUND = QColor("#151920")
ACTIVATION_TIMEOUT = 5.0 if sys.platform == "darwin" else 2.0


def ball_sprite() -> QPixmap:
    sprite = QPixmap(64, 64)
    sprite.fill(Qt.GlobalColor.transparent)
    painter = QPainter(sprite)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    shade = QRadialGradient(24, 21, 39)
    for stop, color in ((0., "#F8DF79"), (.62, "#D7AF39"), (1., "#87601A")):
        shade.setColorAt(stop, QColor(color))
    painter.setBrush(shade)
    painter.drawEllipse(QRectF(0, 0, 64, 64))
    painter.end()
    return sprite


class AimArena(QWidget):
    finished = Signal(object, str)
    round_finished = Signal(object)

    def __init__(self, scenario: Scenario, sensitivity: float, preset: Preset,
                 duration: int, crosshair: Crosshair,
                 *, seed: int, stage: str = "", continuous: bool = False):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.preset, self.crosshair = preset, crosshair
        self.continuous = continuous
        self.stage_toast = Toast(self) if stage else None
        self.setWindowTitle("CS2 Sensitivity Generator · 测试场")
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.raw = RawMouseInput(self.move_camera, on_left_down=self.shoot)
        self.world = Camera()
        self.sprite = ball_sprite()
        self.room_pixmap = None
        self.timer = QTimer(self, timerType=Qt.TimerType.PreciseTimer, interval=8)
        self.timer.timeout.connect(self.tick)
        self.input_deadline = None
        self.set_round(scenario, sensitivity, duration, seed, stage)

    def set_round(self, scenario: Scenario, sensitivity: float, duration: int, seed: int, stage: str) -> None:
        self.scenario, self.sensitivity, self.duration, self.stage = scenario, sensitivity, duration, stage
        self.camera = Camera()
        self.field = FixedWave(scenario, seed) if scenario.key == "linear" else ClickField(scenario, seed)
        self.stats = ClickStats()
        self.moving_targets = scenario.key in ("micro", "moving")
        self.frame_dirty = True
        self.last_clock_label = None
        self.room_key = None
        self.room_cached = False
        self.start_time = None
        self.end_time = None
        self.test_started = False
        self.trace = deque(maxlen=400)
        self.shot_start = 0.
        self.shot_basis = self.camera.basis()
        self.done = False
        self.error = ""
        if self.input_deadline is not None:
            self.input_deadline = perf_counter() + 12.
            if self.stage_toast is not None:
                self.stage_toast.notify(f"{self.stage} · 移动鼠标开始")
            self.update()

    def open_on(self, screen) -> None:
        self.winId()
        self.windowHandle().setScreen(screen)
        self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.activateWindow()
        self.timer.setInterval(max(4, int(1000 / max(60, screen.refreshRate()))))
        self.timer.start()
        self.activation_deadline = perf_counter() + ACTIVATION_TIMEOUT

    def tick(self) -> None:
        if self.done:
            return
        now = perf_counter()
        if self.input_deadline is None:
            if self.isActiveWindow():
                self.input_deadline = now + 12.0
                try:
                    self.raw.start(int(self.winId()))
                except OSError as error:
                    self.error = f"无法启动原始鼠标输入：{error}"
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
        if self.done:
            return
        clock_label = None
        if self.start_time is not None:
            clock_label = int(max(0., self.end_time - now) * 10)
        if self.frame_dirty or clock_label != self.last_clock_label or (self.test_started and self.moving_targets):
            self.frame_dirty = False
            self.last_clock_label = clock_label
            self.update()

    def advance(self, now: float) -> None:
        if now < self.start_time:
            return
        if not self.test_started:
            self.camera.yaw = self.camera.pitch = 0
            self.shot_basis = self.camera.basis()
            self.shot_start = self.start_time
            self.test_started = True
            self.frame_dirty = True
        until = min(now, self.end_time)
        self.stats.elapsed = until - self.start_time
        if now >= self.end_time:
            self.done = True
            if self.continuous:
                self.round_finished.emit(self.stats)
            else:
                self.close()

    def move_camera(self, dx: float, dy: float) -> None:
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
        self.frame_dirty = True
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
                if target.motion is not None:
                    self.sample_follow(target, angles, aim, now)
                if fixed and hit:
                    self.stats.points += .5 + .5 * trial.efficiency
            elif fixed and hit:
                self.stats.points += .5
        self.shot_start = now
        self.shot_basis = self.camera.basis()
        self.trace.clear()
        self.update()

    def sample_follow(self, target, end_target, end_aim, now: float) -> None:
        radius = target.radius
        if hypot(end_aim[0] - end_target[0], end_aim[1] - end_target[1]) > 2 * radius:
            return
        earliest = max(self.start_time + target.born, now - .22)
        for stamp, aim in self.trace:
            if stamp < earliest or now - stamp < .06:
                continue
            ray = self.world_ray(*target.position(stamp - self.start_time))
            start_target = local_angles(ray, self.shot_basis)
            if hypot(aim[0] - start_target[0], aim[1] - start_target[1]) > 2 * radius:
                continue
            dx, dy = end_target[0] - start_target[0], end_target[1] - start_target[1]
            distance = hypot(dx, dy)
            if distance >= .30:
                mismatch = hypot((end_aim[0] - aim[0]) - dx, (end_aim[1] - aim[1]) - dy)
                self.stats.follow_errors.append(mismatch / distance)
                return

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        x, y, w, h = self.preset.viewport(self.width(), self.height())
        viewport = QRectF(x, y, w, h)
        center = viewport.center()
        sx, sy = w / (2 * self.preset.horizontal_tangent), h / (2 * VERTICAL_TANGENT)
        key = self.width(), self.height(), self.devicePixelRatioF(), self.camera.yaw, self.camera.pitch
        if key != self.room_key:
            self.room_key = key
            self.room_cached = False
            painter.fillRect(self.rect(), ARENA_BACKGROUND)
            painter.setClipRect(viewport)
            draw_room(painter, viewport, self.camera, sx, sy, ROOMS[self.scenario.key])
        else:
            if not self.room_cached:
                dpr = self.devicePixelRatioF()
                physical = ceil(self.width() * dpr), ceil(self.height() * dpr)
                room = self.room_pixmap
                if room is None or (room.width(), room.height()) != physical or room.devicePixelRatio() != dpr:
                    room = QPixmap(*physical)
                    room.setDevicePixelRatio(dpr)
                room.fill(ARENA_BACKGROUND)
                background = QPainter(room)
                background.setClipRect(viewport)
                draw_room(background, viewport, self.camera, sx, sy, ROOMS[self.scenario.key])
                background.end()
                self.room_pixmap, self.room_cached = room, True
            painter.drawPixmap(0, 0, self.room_pixmap)
        painter.setClipRect(viewport)

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
                        rx, ry = sx * radius, sy * radius
                        painter.drawPixmap(QRectF(pixel.x() - rx, pixel.y() - ry, rx * 2, ry * 2),
                                           self.sprite, QRectF(0, 0, 64, 64))

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
            label = f"{remaining:04.1f} s   ·   {score}"
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
        self.finished.emit(self.stats if self.done and not self.continuous and not self.error else None, self.error)
