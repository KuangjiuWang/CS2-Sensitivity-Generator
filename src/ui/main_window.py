"""Main parameter, practice and export workflow."""
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from core.cs2_math import (
    PRESETS, cfg_text, cm_per_360, console_text, corrected_sensitivity, edpi, physical_baseline,
)
from core.dpi_measurement import MAX_DPI, MIN_DPI
from core.tracking_path import (
    DEFAULT_DIAMETER_DEG, DEFAULT_DISTANCE, WEAPON_SPEEDS, center_angular_speed,
)
from ui.aim_arena import AimArena, Crosshair
from ui.dpi_dialog import DpiDialog

STYLESHEET = """
QWidget { background: #0B0E16; color: #EDF1FB; font-size: 14px;
          font-family: "Segoe UI", "Microsoft YaHei UI"; }
QScrollArea { border: none; }
QFrame#card { background: #141A27; border: 1px solid #283449; border-radius: 12px; }
QFrame#card QLabel, QFrame#card QCheckBox { background: transparent; }
QLabel#badge { color: #D8F576; font-weight: 700; font-size: 13px; }
QLabel#title { font-size: 32px; font-weight: 700; }
QLabel#section { font-size: 18px; font-weight: 700; }
QLabel#muted { color: #A5B3C9; }
QLabel#metric { color: #D8F576; font-size: 23px; font-weight: 700; }
QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {
    background: #0D121E; border: 1px solid #35435A; border-radius: 6px; padding: 6px; }
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #D8F576; }
QPlainTextEdit { color: #96E9F1; font-family: Consolas; }
QPushButton { background: #25344A; border: 1px solid #3B4F67; border-radius: 7px;
              padding: 8px 12px; font-weight: 600; }
QPushButton:hover, QPushButton:focus { border-color: #96E9F1; }
QPushButton:pressed { background: #1A2536; }
QPushButton#primary { background: #D8F576; color: #131A23; border-color: #D8F576; }
QPushButton#primary:hover, QPushButton#primary:focus { background: #F0FFA8; }
QPushButton:disabled { background: #202837; color: #93A3B8; border-color: #303B4B; }
"""


def label(text: str = "", style: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(style)
    widget.setWordWrap(wrap)
    return widget


def card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 15, 18, 15)
    layout.setSpacing(9)
    layout.addWidget(label(title, "section"))
    return frame, layout


def integer(minimum: int, maximum: int, value: int) -> QSpinBox:
    widget = QSpinBox()
    widget.setRange(minimum, maximum)
    widget.setValue(value)
    return widget


def decimal(minimum: float, maximum: float, value: float, places: int, step: float) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setDecimals(places)
    widget.setRange(minimum, maximum)
    widget.setSingleStep(step)
    widget.setValue(value)
    return widget


class CrosshairPreview(QWidget):
    def __init__(self, read_crosshair):
        super().__init__()
        self.read_crosshair = read_crosshair
        self.setMinimumSize(70, 44)
        self.setAccessibleName("准星预览")

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#121824"))
        self.read_crosshair().draw(painter, self.rect().toRectF().center())


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CS2 Sensitivity Generator")
        self.resize(1000, 825)
        self.setMinimumSize(720, 560)
        self.arena = None
        self.flick = None
        self.tracking = None
        self.color = Crosshair().color
        self.recommendation = 0.0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        self.content = content
        shell = QVBoxLayout(content)
        shell.setContentsMargins(26, 22, 26, 20)
        shell.setSpacing(12)
        shell.addWidget(label("COUNTER-STRIKE 2  /  AIM CALIBRATION", "badge"))
        shell.addWidget(label("CS2 灵敏度生成器", "title"))
        shell.addWidget(label("输入你在 CS2 使用的灵敏度，再用无开镜瞄准测试校准。", "muted"))

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        shell.addLayout(grid)

        physical, physical_layout = card("灵敏度起点")
        grid.addWidget(physical, 0, 0)
        form = QFormLayout()
        physical_layout.addLayout(form)
        self.dpi = integer(MIN_DPI, MAX_DPI, 800)
        self.dpi.setSingleStep(50)
        detect_dpi = QPushButton("检测 DPI")
        detect_dpi.clicked.connect(self.detect_dpi)
        dpi_controls = QHBoxLayout()
        dpi_controls.addWidget(self.dpi, 1)
        dpi_controls.addWidget(detect_dpi)
        self.initial_sensitivity = decimal(.001, 100, 1.15, 3, .05)
        self.pad = decimal(10, 100, 40, 1, 1)
        self.pad.setSuffix(" cm")
        self.profile = QComboBox()
        for name, value in (("混合流", "hybrid"), ("手臂流", "arm"), ("手腕流", "wrist")):
            self.profile.addItem(name, value)
        self.aspect = QComboBox()
        for preset in PRESETS:
            self.aspect.addItem(f"{preset.label} · {preset.horizontal_fov:.2f}°", preset)
        form.addRow("鼠标 DPI", dpi_controls)
        form.addRow("当前 CS2 灵敏度", self.initial_sensitivity)
        form.addRow("鼠标垫有效横向宽度", self.pad)
        form.addRow("发力习惯", self.profile)
        form.addRow("CS2 画面比例", self.aspect)
        self.baseline = label(style="muted", wrap=True)
        physical_layout.addWidget(self.baseline)
        use_physical = QPushButton("用物理建议填入灵敏度")
        use_physical.clicked.connect(lambda: self.initial_sensitivity.setValue(self.baseline_values()[0]))
        physical_layout.addWidget(use_physical)

        practice, practice_layout = card("全屏测试")
        grid.addWidget(practice, 0, 1)
        self.duration = QComboBox()
        for seconds in (15, 30, 60):
            self.duration.addItem(f"{seconds} 秒 / 项", seconds)
        self.tracking_speed = QComboBox()
        for title, speed in WEAPON_SPEEDS:
            self.tracking_speed.addItem(f"{title} · {speed} u/s", speed)
        self.tracking_distance = integer(300, 1600, DEFAULT_DISTANCE)
        self.tracking_distance.setSingleStep(50)
        self.tracking_distance.setSuffix(" u")
        self.tracking_diameter = decimal(.5, 5, DEFAULT_DIAMETER_DEG, 1, .1)
        self.tracking_diameter.setSuffix("°")
        duration_form = QFormLayout()
        duration_form.addRow("单项时长", self.duration)
        duration_form.addRow("跟枪目标移速", self.tracking_speed)
        duration_form.addRow("跟枪目标距离", self.tracking_distance)
        duration_form.addRow("跟枪目标直径", self.tracking_diameter)
        practice_layout.addLayout(duration_form)
        self.tracking_hint = label(style="muted")
        practice_layout.addWidget(self.tracking_hint)
        self.flick_button = QPushButton("开始悬停拉枪")
        self.flick_button.setObjectName("primary")
        self.flick_button.clicked.connect(lambda: self.launch("flick"))
        self.tracking_button = QPushButton("开始动态跟枪")
        self.tracking_button.clicked.connect(lambda: self.launch("tracking"))
        buttons = QHBoxLayout()
        buttons.addWidget(self.flick_button)
        buttons.addWidget(self.tracking_button)
        practice_layout.addLayout(buttons)
        self.flick_line = label(style="muted", wrap=True)
        self.track_line = label(style="muted", wrap=True)
        practice_layout.addWidget(self.flick_line)
        practice_layout.addWidget(self.track_line)
        practice_layout.addStretch()

        cross, cross_layout = card("测试准星")
        grid.addWidget(cross, 1, 0)
        cross_form = QFormLayout()
        self.length = integer(2, 20, 8)
        self.gap = integer(1, 12, 4)
        self.thickness = integer(1, 5, 2)
        self.dot = QCheckBox("显示中心点")
        self.dot.setChecked(True)
        self.pick = QPushButton("选择颜色")
        self.pick.clicked.connect(self.pick_color)
        cross_form.addRow("线长", self.length)
        cross_form.addRow("间隙", self.gap)
        cross_form.addRow("线宽", self.thickness)
        cross_form.addRow(self.dot, self.pick)
        cross_layout.addLayout(cross_form)
        self.preview = CrosshairPreview(self.crosshair)
        cross_layout.addWidget(self.preview, 1)

        export, export_layout = card("推荐与导出")
        grid.addWidget(export, 1, 1)
        self.metrics = label(style="metric", wrap=True)
        self.summary = label(style="muted", wrap=True)
        export_layout.addWidget(self.metrics)
        export_layout.addWidget(self.summary)
        self.zoom = decimal(.01, 10, 1, 3, .01)
        zoom_form = QFormLayout()
        zoom_form.addRow("开镜倍率（手动设定）", self.zoom)
        export_layout.addLayout(zoom_form)
        self.cfg = QPlainTextEdit()
        self.cfg.setAccessibleName("autoexec.cfg 配置片段")
        self.cfg.setReadOnly(True)
        self.cfg.setFixedHeight(62)
        export_layout.addWidget(self.cfg)
        commands = QGridLayout()
        for index, (name, action) in enumerate((
            ("复制控制台指令", self.copy_console), ("复制 CFG", self.copy_cfg), ("保存 CFG…", self.save_cfg),
        )):
            button = QPushButton(name)
            button.clicked.connect(action)
            commands.addWidget(button, 0, index)
        export_layout.addLayout(commands)

        self.status = label("测试使用当前 CS2 灵敏度。全屏后移动鼠标开始倒计时，按 Esc 退出。", "muted", True)
        self.status.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        shell.addWidget(self.status)
        shell.addStretch()
        for widget in (self.dpi, self.initial_sensitivity, self.length, self.gap, self.thickness):
            widget.valueChanged.connect(self.settings_changed)
        for widget in (self.aspect, self.duration):
            widget.currentIndexChanged.connect(self.settings_changed)
        self.dot.toggled.connect(self.settings_changed)
        self.pad.valueChanged.connect(self.refresh)
        self.profile.currentIndexChanged.connect(self.refresh)
        self.zoom.valueChanged.connect(self.refresh)
        self.tracking_speed.currentIndexChanged.connect(self.tracking_settings_changed)
        self.tracking_distance.valueChanged.connect(self.tracking_settings_changed)
        self.tracking_diameter.valueChanged.connect(self.tracking_settings_changed)
        self.refresh()

    def crosshair(self) -> Crosshair:
        return Crosshair(self.color, self.length.value(), self.gap.value(),
                         self.thickness.value(), self.dot.isChecked())

    def detect_dpi(self) -> None:
        dialog = DpiDialog(self)
        if dialog.exec() and dialog.measured_dpi is not None:
            self.dpi.setValue(dialog.measured_dpi)
            self.status.setText(f"已填入检测值 {dialog.measured_dpi} DPI。")
        dialog.deleteLater()

    def pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.color), self, "选择准星颜色")
        if color.isValid() and color.name() != self.color:
            self.color = color.name()
            self.settings_changed()

    def settings_changed(self) -> None:
        if self.flick is not None or self.tracking is not None:
            self.status.setText("参数已更改，上一组测试数据已清空。")
        self.flick = self.tracking = None
        self.preview.update()
        self.refresh()

    def baseline_values(self):
        return physical_baseline(self.dpi.value(), self.pad.value(), self.profile.currentData())

    def tracking_settings_changed(self) -> None:
        if self.tracking is not None:
            self.tracking = None
            self.status.setText("跟枪参数已更改，请重测跟枪。")
        self.refresh()

    def refresh(self) -> None:
        dpi = self.dpi.value()
        physical, swing, turn = self.baseline_values()
        physical = round(physical, 3)
        base = self.initial_sensitivity.value()
        angular_speed = center_angular_speed(self.tracking_speed.currentData(), self.tracking_distance.value())
        self.tracking_hint.setText(f"目标全速横穿正前方时约 {angular_speed:.1f}°/秒")
        self.baseline.setText(f"舒适行程 {swing:.1f} cm  ·  转身 {turn:.0f}°\n"
                              f"物理建议 {physical:.3f} sens  ·  {cm_per_360(dpi, physical):.2f} cm/360°")
        flick, track = self.flick, self.tracking
        if flick is None:
            self.flick_line.setText("悬停拉枪 · 划过目标即可命中")
        else:
            latency = f"{flick.mean_latency * 1000:.0f} ms" if flick.hits else "—"
            overshoot = f"{flick.mean_overshoot:.2f}°" if flick.completed_overshoots else "—"
            self.flick_line.setText(f"拉枪 {flick.hits}/{flick.attempts} · 定位 {latency} · 平均过冲 {overshoot}")
        if track is None:
            self.track_line.setText("动态跟枪 · 跟住横移目标，停住时也保持准星在目标内")
        else:
            lag = f"{track.lag_rate:.0%} · 超前 {track.lead_rate:.0%}" if track.motion_time else "—"
            self.track_line.setText(f"跟枪 命中时长 {track.accuracy:.0%} · 滞后 {lag}")

        value = base
        detail = "当前灵敏度 · 完成两项测试后计算修正"
        if flick is not None and track is not None:
            valid_flick = flick.completed_overshoots >= 3
            valid_track = track.motion_time >= max(2.5, track.elapsed / 4) and track.accuracy >= .10
            if valid_flick or valid_track:
                value = corrected_sensitivity(base, flick.mean_overshoot if valid_flick else 0,
                                              track.lag_rate if valid_track else 0,
                                              track.lead_rate if valid_track else 0)
                evidence = "拉枪和跟枪" if valid_flick and valid_track else "拉枪" if valid_flick else "跟枪"
                detail = f"{evidence}修正 · 较输入值 {round(value, 3) / base - 1:+.1%}"
            else:
                detail = "有效样本不足 · 使用当前灵敏度"
        self.recommendation = round(value, 3)
        self.metrics.setText(f"{self.recommendation:.3f} sens   ·   {edpi(dpi, self.recommendation):.0f} eDPI\n"
                             f"{cm_per_360(dpi, self.recommendation):.2f} cm/360°")
        self.summary.setText(detail)
        self.cfg.setPlainText(cfg_text(self.recommendation, self.zoom.value()).rstrip())

    def launch(self, mode: str) -> None:
        if self.arena is not None:
            return
        self.arena = AimArena(mode, self.initial_sensitivity.value(), self.aspect.currentData(),
                              self.duration.currentData(), self.crosshair(),
                              self.tracking_speed.currentData(), self.tracking_distance.value(),
                              self.tracking_diameter.value())
        self.arena.finished.connect(self.arena_finished)
        self.content.setEnabled(False)
        self.arena.open_on(self.screen())

    def arena_finished(self, stats, error: str) -> None:
        arena, self.arena = self.arena, None
        arena.deleteLater()
        self.content.setEnabled(True)
        self.status.setText(error or ("已记录本轮测试。" if stats else "测试已取消。"))
        if stats is not None:
            if arena.mode == "flick":
                self.flick = stats
            else:
                self.tracking = stats
            self.refresh()
        QTimer.singleShot(0, self.activateWindow)

    def copy_console(self) -> None:
        QApplication.clipboard().setText(console_text(self.recommendation, self.zoom.value()))
        self.status.setText("已复制 CS2 控制台指令。")

    def copy_cfg(self) -> None:
        QApplication.clipboard().setText(cfg_text(self.recommendation, self.zoom.value()))
        self.status.setText("已复制 autoexec.cfg 配置片段。")

    def save_cfg(self) -> None:
        name, _ = QFileDialog.getSaveFileName(self, "保存 CS2 配置片段", "autoexec.cfg", "CS2 CFG (*.cfg)")
        if not name:
            return
        try:
            Path(name).write_text(cfg_text(self.recommendation, self.zoom.value()), encoding="ascii")
        except OSError as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return
        self.status.setText(f"已保存 {name}")

    def closeEvent(self, event) -> None:
        if self.arena is not None:
            self.arena.close()
        super().closeEvent(event)
