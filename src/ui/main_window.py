"""Main parameter, practice and export workflow."""
from dataclasses import asdict
from pathlib import Path
from random import Random

from PySide6.QtCore import QSignalBlocker, QStandardPaths, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from core.cs2_math import (
    PRESETS, cfg_text, cm_per_360, edpi, physical_baseline,
)
from core.blind_test import BlindSession, TRACK_SECONDS
from core.config_export import crosshair_cfg_text
from core.crosshair import Crosshair, STYLES
from core.dpi_measurement import MAX_DPI, MIN_DPI
from core.history import HistoryStore, record
from core.player_crosshairs import CrosshairPreset
from core.player_sensitivity import SensitivityPreset
from core.practice_plan import flick_plan
from core.tracking_path import (
    DEFAULT_DIAMETER_DEG, DEFAULT_DISTANCE, WEAPON_SPEEDS, center_angular_speed,
)
from ui.aim_arena import AimArena, FLICK_TIMEOUT
from ui.comparison import APPLY_BLIND_RESULT, BlindResults, HistoryDialog, milliseconds
from ui.crosshair import CrosshairEditor, CrosshairPreview
from ui.dpi_dialog import DpiDialog
from ui.flick_results import FlickResults, SUPPLEMENT
from ui.preset_panels import PlayerCrosshairPanel, PlayerSensitivityPanel
from ui.toast import Toast

STYLESHEET = """
QWidget { background: #0B0E16; color: #EDF1FB; font-size: 14px;
          font-family: "Segoe UI", "Microsoft YaHei UI"; }
QScrollArea { border: none; }
QFrame#card { background: #141A27; border: 1px solid #283449; border-radius: 12px; }
QFrame#card QLabel, QFrame#card QCheckBox { background: transparent; }
QLabel#title { font-size: 32px; font-weight: 700; }
QLabel#section { font-size: 18px; font-weight: 700; }
QLabel#muted { color: #A5B3C9; }
QLabel#metric { color: #D8F576; font-size: 23px; font-weight: 700; }
QLabel#toast { background: #1C2939; border: 1px solid #62DCE6; border-radius: 9px;
               color: #F1F6FF; font-weight: 600; padding: 10px 13px; }
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


class MainWindow(QWidget):
    def __init__(self, history_path: Path | None = None):
        super().__init__()
        self.setWindowTitle("CS2 Sensitivity Generator")
        self.resize(1050, 910)
        self.setMinimumSize(720, 560)
        self.arena = None
        self.flick = None
        self.tracking = None
        self.crosshair_settings = Crosshair()
        self.recommendation = 0.0
        self.blind = None
        self.last_blind = None
        self.supplementing = False
        self.closing = False
        self.random = Random()
        app_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        self.history = HistoryStore(history_path or Path(app_path) / "practice-history.json")
        self.settings_timer = QTimer(self, singleShot=True, interval=350)
        self.settings_timer.timeout.connect(self.persist_settings)
        self.toast = Toast(self)

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
        shell.addWidget(label("CS2 灵敏度生成器", "title"))

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        shell.addLayout(grid)

        physical, physical_layout = card("参数配置")
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
        physical_layout.addStretch()

        practice, practice_layout = card("全屏训练与盲测")
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
        blind_row = QHBoxLayout()
        blind_row.addWidget(label("盲测浮动"))
        self.blind_step = decimal(.5, 25, 5, 1, .5)
        self.blind_step.setSuffix(" %")
        blind_row.addWidget(self.blind_step)
        self.blind_button = QPushButton("开始 A/B/C 盲测")
        self.blind_button.setObjectName("primary")
        self.blind_button.clicked.connect(self.start_blind)
        blind_row.addWidget(self.blind_button, 1)
        practice_layout.addLayout(blind_row)
        practice_layout.addWidget(label("先测 3 档。有领先候选时换场景复核两档，最后统一揭晓。约 2.5–4.5 分钟。", "muted", True))

        players, players_layout = card("选手灵敏度预设")
        self.sensitivity_panel = PlayerSensitivityPanel()
        self.sensitivity_panel.apply_requested.connect(self.apply_sensitivity_preset)
        players_layout.addWidget(self.sensitivity_panel)
        grid.addWidget(players, 2, 0)
        player_crosshairs, player_crosshairs_layout = card("选手准星预设")
        self.crosshair_panel = PlayerCrosshairPanel()
        self.crosshair_panel.apply_requested.connect(self.apply_crosshair_preset)
        player_crosshairs_layout.addWidget(self.crosshair_panel)
        player_crosshairs_layout.addStretch()
        grid.addWidget(player_crosshairs, 2, 1)

        cross, cross_layout = card("测试准星")
        grid.addWidget(cross, 3, 0)
        self.crosshair_summary = label(style="muted", wrap=True)
        cross_layout.addWidget(self.crosshair_summary)
        edit_crosshair = QPushButton("准星设置／导入分享码…")
        edit_crosshair.clicked.connect(self.edit_crosshair)
        cross_layout.addWidget(edit_crosshair)
        self.preview = CrosshairPreview(self.crosshair)
        cross_layout.addWidget(self.preview, 1)

        export, export_layout = card("推荐与导出")
        grid.addWidget(export, 3, 1)
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
        for index, (kind, name) in enumerate((
            ("sensitivity", "仅复制灵敏度 CFG"), ("crosshair", "仅复制准星 CFG"),
            ("full", "一键复制完整配置"),
        )):
            button = QPushButton(name)
            button.clicked.connect(lambda checked=False, selected=kind: self.copy_cfg(selected))
            commands.addWidget(button, index // 2, index % 2)
        save = QPushButton("保存完整 CFG…")
        save.clicked.connect(self.save_cfg)
        commands.addWidget(save, 1, 1)
        export_layout.addLayout(commands)
        results, results_layout = card("分析与历史")
        grid.addWidget(results, 1, 0, 1, 2)
        result_actions = QHBoxLayout()
        self.analysis_button = QPushButton("16 方向轨迹分析…")
        self.analysis_button.clicked.connect(self.show_flick_results)
        self.clear_button = QPushButton("清除本次测试数据")
        self.clear_button.clicked.connect(self.clear_test_results)
        result_actions.addWidget(self.analysis_button)
        self.history_button = QPushButton()
        self.history_button.clicked.connect(self.show_history)
        result_actions.addWidget(self.history_button)
        self.reveal_button = QPushButton("查看最近盲测结果")
        self.reveal_button.clicked.connect(self.show_blind_results)
        result_actions.addWidget(self.reveal_button)
        result_actions.addWidget(self.clear_button)
        results_layout.addLayout(result_actions)

        self.status = label("测试使用当前 CS2 灵敏度。全屏后移动鼠标开始倒计时，按 Esc 退出。", "muted", True)
        self.status.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        shell.addWidget(self.status)
        shell.addStretch()
        self.restore_settings()
        for widget in (self.dpi, self.initial_sensitivity):
            widget.valueChanged.connect(self.settings_changed)
        for widget in (self.aspect, self.duration):
            widget.currentIndexChanged.connect(self.settings_changed)
        self.pad.valueChanged.connect(self.refresh)
        self.profile.currentIndexChanged.connect(self.refresh)
        self.zoom.valueChanged.connect(self.refresh)
        self.blind_step.valueChanged.connect(self.refresh)
        self.tracking_speed.currentIndexChanged.connect(self.tracking_settings_changed)
        self.tracking_distance.valueChanged.connect(self.tracking_settings_changed)
        self.tracking_diameter.valueChanged.connect(self.tracking_settings_changed)
        self.sensitivity_panel.players.currentTextChanged.connect(
            lambda name: self.notify(f"正在预览 {name} 的灵敏度。"))
        self.crosshair_panel.players.currentTextChanged.connect(
            lambda name: self.notify(f"正在预览 {name} 的准星。"))
        self.refresh()
        if self.history.error:
            self.notify(f"本地历史无法读取：{self.history.error}")

    def crosshair(self) -> Crosshair:
        return self.crosshair_settings

    def notify(self, message: str) -> None:
        self.status.setText(message)
        self.toast.notify(message)

    def snapshot(self) -> dict:
        return {
            "dpi": self.dpi.value(), "sensitivity": self.initial_sensitivity.value(),
            "zoom": self.zoom.value(), "aspect": self.aspect.currentIndex(),
            "duration": self.duration.currentIndex(), "pad": self.pad.value(),
            "profile": self.profile.currentIndex(), "weapon": self.tracking_speed.currentIndex(),
            "distance": self.tracking_distance.value(), "diameter": self.tracking_diameter.value(),
            "step": self.blind_step.value(), "crosshair": asdict(self.crosshair_settings),
        }

    def restore_settings(self) -> None:
        saved = self.history.settings
        for key, widget in (("dpi", self.dpi), ("sensitivity", self.initial_sensitivity), ("zoom", self.zoom),
                            ("pad", self.pad), ("distance", self.tracking_distance),
                            ("diameter", self.tracking_diameter), ("step", self.blind_step)):
            value = saved.get(key)
            if isinstance(value, (int, float)) and widget.minimum() <= value <= widget.maximum():
                widget.setValue(int(value) if isinstance(widget, QSpinBox) else value)
        for key, widget in (("aspect", self.aspect), ("duration", self.duration), ("profile", self.profile),
                            ("weapon", self.tracking_speed)):
            index = saved.get(key)
            if isinstance(index, int) and 0 <= index < widget.count():
                widget.setCurrentIndex(index)
        try:
            appearance = dict(saved.get("crosshair", {}))
            for key in ("color", "outline_color"):
                if key in appearance:
                    appearance[key] = tuple(appearance[key])
            crosshair = Crosshair(**appearance)
            if 0 <= crosshair.style < len(STYLES) and 240 <= crosshair.reference_height <= 65535:
                self.crosshair_settings = crosshair
        except (TypeError, ValueError):
            pass

    def persist_settings(self) -> None:
        if self.history.error:
            return
        try:
            self.history.save(self.snapshot())
        except OSError as error:
            self.notify(f"无法保存本机设置：{error}")

    def save_history(self, *entries) -> str:
        try:
            self.history.append(*entries, settings=self.snapshot())
        except OSError as error:
            return f"本轮完成，但无法保存历史：{error}"
        return ""

    def apply_sensitivity_preset(self, preset: SensitivityPreset, match_current_dpi: bool) -> None:
        dpi = self.dpi.value() if match_current_dpi else preset.dpi
        sensitivity = preset.sensitivity_at(dpi)
        test_changed = (dpi, sensitivity) != (self.dpi.value(), self.initial_sensitivity.value())
        with QSignalBlocker(self.dpi), QSignalBlocker(self.initial_sensitivity), QSignalBlocker(self.zoom):
            self.dpi.setValue(dpi)
            self.initial_sensitivity.setValue(sensitivity)
            self.zoom.setValue(preset.zoom)
        if test_changed:
            self.settings_changed()
        else:
            self.refresh()
        self.notify(f"已应用 {preset.name} 的灵敏度 · {dpi} DPI × {sensitivity:.3f}")

    def apply_crosshair_preset(self, preset: CrosshairPreset) -> None:
        if self.crosshair_settings != preset.crosshair:
            self.crosshair_settings = preset.crosshair
            self.settings_changed()
        self.notify(f"已应用 {preset.name} 的准星。")

    def detect_dpi(self) -> None:
        dialog = DpiDialog(self)
        if dialog.exec() and dialog.measured_dpi is not None:
            self.dpi.setValue(dialog.measured_dpi)
            self.notify(f"已填入检测值 {dialog.measured_dpi} DPI。")
        dialog.deleteLater()

    def edit_crosshair(self) -> None:
        dialog = CrosshairEditor(self.crosshair_settings, self)
        if dialog.exec():
            settings = dialog.settings()
            if settings != self.crosshair_settings:
                self.crosshair_settings = settings
                self.settings_changed()
                self.notify("准星设置已应用。")
        dialog.deleteLater()

    def settings_changed(self) -> None:
        if self.flick is not None or self.tracking is not None:
            self.notify("参数已更改，本次成绩已重置。历史记录仍可对比。")
        self.flick = self.tracking = None
        self.preview.update()
        self.refresh()

    def clear_test_results(self) -> None:
        self.flick = self.tracking = None
        self.last_blind = None
        self.refresh()
        self.notify("已清除本次测试结果。")

    def show_flick_results(self) -> None:
        if self.flick is not None and self.flick.attempts:
            dialog = FlickResults(self.flick, self)
            supplement = dialog.exec() == SUPPLEMENT
            dialog.deleteLater()
            if supplement:
                missing = self.flick.missing_directions()
                if missing:
                    self.supplementing = True
                    plan = flick_plan(missing, self.random, FLICK_TIMEOUT)
                    self.notify(f"方向补测 · {len(missing)} 个目标")
                    self.launch("flick", plan=plan, stage="方向补测")

    def show_history(self) -> None:
        dialog = HistoryDialog(self.history, self)
        dialog.cleared.connect(self.history_cleared)
        dialog.exec()
        dialog.deleteLater()

    def history_cleared(self) -> None:
        self.last_blind = None
        self.refresh()

    def baseline_values(self):
        return physical_baseline(self.dpi.value(), self.pad.value(), self.profile.currentData())

    def tracking_settings_changed(self) -> None:
        if self.tracking is not None:
            self.tracking = None
            self.notify("跟枪参数已更改，请重测跟枪。")
        self.refresh()

    def refresh(self) -> None:
        crosshair = self.crosshair_settings
        self.crosshair_summary.setText(f"{crosshair.style} · {STYLES[crosshair.style]}   ·   "
                                      f"厚度 {crosshair.thickness} px")
        dpi = self.dpi.value()
        self.sensitivity_panel.set_dpi(dpi)
        physical, swing, turn = self.baseline_values()
        physical = round(physical, 3)
        base = self.initial_sensitivity.value()
        angular_speed = center_angular_speed(self.tracking_speed.currentData(), self.tracking_distance.value())
        self.tracking_hint.setText(f"目标全速横穿正前方时约 {angular_speed:.1f}°/秒")
        self.baseline.setText(f"舒适行程 {swing:.1f} cm  ·  转身 {turn:.0f}°\n"
                              f"物理建议 {physical:.3f} sens  ·  {cm_per_360(dpi, physical):.2f} cm/360°")
        flick, track = self.flick, self.tracking
        self.analysis_button.setEnabled(flick is not None and flick.attempts > 0)
        self.clear_button.setEnabled(flick is not None or track is not None or self.last_blind is not None)
        self.reveal_button.setEnabled(self.last_blind is not None)
        self.history_button.setText(f"本地历史 / 对比（{len(self.history.records)}）")
        if flick is None:
            self.flick_line.setText("悬停拉枪 · 划过目标即可命中")
        else:
            reaction, movement = flick.timings()
            overshoot = f"{flick.mean_overshoot:.2f}°" if flick.completed_overshoots else "—"
            sectors = sum(bool(sector.attempts) for sector in flick.sectors)
            self.flick_line.setText(f"拉枪 {flick.hits}/{flick.attempts} · 过冲 {overshoot} · 方向 {sectors}/16\n"
                                   f"启动 {milliseconds(reaction)} · 移动后定位 {milliseconds(movement)}")
        if track is None:
            self.track_line.setText("动态跟枪 · 跟住横移目标，停住时也保持准星在目标内")
        else:
            lag = f"{track.lag_rate:.0%} · 超前 {track.lead_rate:.0%}" if track.motion_time else "—"
            reaction, movement = track.timings()
            self.track_line.setText(f"跟枪 命中时长 {track.accuracy:.0%} · 滞后 {lag}\n"
                                    f"变向反应 {milliseconds(reaction)} · 移动后稳定 {milliseconds(movement)}")

        value = base
        detail = "当前灵敏度 · 运行 A/B/C 盲测获取调整建议"
        if self.last_blind is not None:
            current = self.snapshot()
            match_keys = ("dpi", "sensitivity", "aspect", "crosshair", "weapon", "distance", "diameter")
            if all(self.last_blind.settings[key] == current[key] for key in match_keys):
                decision = self.last_blind.decision()
                value = decision.recommend.sensitivity
                detail = f"盲测 · {decision.reason}"
        self.recommendation = round(value, 3)
        self.metrics.setText(f"{self.recommendation:.3f} sens   ·   {edpi(dpi, self.recommendation):.0f} eDPI\n"
                             f"{cm_per_360(dpi, self.recommendation):.2f} cm/360°")
        self.summary.setText(detail)
        self.cfg.setPlainText(cfg_text(self.recommendation, self.zoom.value()).rstrip())
        self.settings_timer.start()

    def launch(self, mode: str, *, sensitivity=None, plan=None, stage="", reverse_tracking=False) -> None:
        if self.arena is not None:
            return
        duration = self.duration.currentData() if sensitivity is None else TRACK_SECONDS
        self.arena = AimArena(mode, self.initial_sensitivity.value() if sensitivity is None else sensitivity,
                              self.aspect.currentData(), duration, self.crosshair(),
                              self.tracking_speed.currentData(), self.tracking_distance.value(),
                              self.tracking_diameter.value(), plan=plan, stage=stage, reverse_tracking=reverse_tracking)
        self.arena.finished.connect(self.arena_finished)
        self.content.setEnabled(False)
        self.arena.open_on(self.screen())

    def arena_finished(self, stats, error: str) -> None:
        arena, self.arena = self.arena, None
        arena.deleteLater()
        if self.closing:
            return
        if self.blind is not None:
            self.finish_blind_phase(stats, error)
            return
        self.content.setEnabled(True)
        supplemented, self.supplementing = self.supplementing, False
        if stats is not None:
            if supplemented:
                self.flick.merge(stats)
            elif arena.mode == "flick":
                self.flick = stats
            else:
                self.tracking = stats
            kind = "supplement" if supplemented else arena.mode
            error = self.save_history(record(kind, self.snapshot(), self.flick, self.tracking))
            self.refresh()
        self.notify(error or ("已合并方向补测数据。" if supplemented and stats else
                             "已保存本轮测试。" if stats else "测试已取消。"))
        QTimer.singleShot(0, self.activateWindow)

    def start_blind(self) -> None:
        if self.arena is not None or self.blind is not None:
            return
        try:
            self.blind = BlindSession.create(self.initial_sensitivity.value(), self.blind_step.value(), self.random)
        except ValueError as error:
            self.notify(str(error))
            return
        self.blind.settings = self.snapshot()
        self.launch_blind_phase()

    def launch_blind_phase(self) -> None:
        if self.blind is None or self.closing:
            return
        candidate, mode = self.blind.current
        stage = f"盲测 · {self.blind.progress} · {candidate.label} 组"
        self.notify(f"{stage}，移动鼠标开始。")
        self.launch(mode, sensitivity=candidate.sensitivity, plan=self.blind.plan if mode == "flick" else None,
                    stage=stage, reverse_tracking=bool(self.blind.verification))

    def finish_blind_phase(self, stats, error: str) -> None:
        if stats is None:
            self.blind = None
            self.content.setEnabled(True)
            self.notify(error or "盲测已取消。")
            QTimer.singleShot(0, self.activateWindow)
            return
        if not self.blind.record(stats):
            QTimer.singleShot(100, self.launch_blind_phase)
            return
        self.last_blind, self.blind = self.blind, None
        session = self.last_blind
        decision = session.decision()
        entries = [
            record("blind", {**session.settings, "sensitivity": candidate.sensitivity}, candidate.flick,
                   candidate.tracking, name=f"{'复核' if candidate in session.verification else '初筛'} {candidate.label}",
                   score=candidate.score,
                   conclusion=decision.reason)
            for candidate in session.candidates
        ]
        error = self.save_history(*entries)
        self.content.setEnabled(True)
        self.refresh()
        self.notify(error or "盲测完成，数值已揭晓。")
        self.activateWindow()
        QTimer.singleShot(0, self.show_blind_results)

    def show_blind_results(self) -> None:
        if self.last_blind is None or self.closing:
            return
        session = self.last_blind
        decision = session.decision()
        dialog = BlindResults(session, decision, self)
        if dialog.exec() == APPLY_BLIND_RESULT:
            sensitivity = decision.recommend.sensitivity * session.settings["dpi"] / self.dpi.value()
            self.initial_sensitivity.setValue(sensitivity)
            self.notify(f"已应用盲测建议 · {self.initial_sensitivity.value():.3f}")
        dialog.deleteLater()

    def copy_console(self) -> None:
        QApplication.clipboard().setText("; ".join(self.config_text("sensitivity").splitlines()))
        self.notify("已复制 CS2 控制台指令。")

    def config_text(self, kind: str) -> str:
        sensitivity = cfg_text(self.recommendation, self.zoom.value()) if kind != "crosshair" else ""
        crosshair = crosshair_cfg_text(self.crosshair_settings) if kind != "sensitivity" else ""
        return sensitivity + crosshair

    def copy_cfg(self, kind: str = "sensitivity") -> None:
        QApplication.clipboard().setText(self.config_text(kind))
        title = {"sensitivity": "灵敏度 CFG", "crosshair": "准星 CFG", "full": "完整配置"}[kind]
        self.notify(f"已复制{title}。")

    def save_cfg(self) -> None:
        name, _ = QFileDialog.getSaveFileName(self, "保存 CS2 配置片段", "autoexec.cfg", "CS2 CFG (*.cfg)")
        if not name:
            return
        try:
            Path(name).write_text(self.config_text("full"), encoding="ascii")
        except OSError as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return
        self.notify(f"已保存 {name}")

    def closeEvent(self, event) -> None:
        self.closing = True
        self.settings_timer.stop()
        self.persist_settings()
        if self.arena is not None:
            self.arena.close()
        super().closeEvent(event)
