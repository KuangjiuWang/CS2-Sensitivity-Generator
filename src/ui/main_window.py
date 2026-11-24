"""Main parameter, practice and export workflow."""
from dataclasses import asdict, dataclass, field
from pathlib import Path
from random import Random

from PySide6.QtCore import QSignalBlocker, QStandardPaths, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QStyle, QVBoxLayout, QWidget,
)

from core.cs2_math import (
    PRESETS, cfg_text, cm_per_360, console_text, edpi, physical_baseline,
)
from core.blind_test import BlindSession, ROUND_SECONDS, performance
from core.config_export import crosshair_cfg_text
from core.crosshair import Crosshair, STYLES
from core.dpi_measurement import MAX_DPI, MIN_DPI
from core.history import HistoryStore, record
from core.player_crosshairs import CrosshairPreset
from core.player_sensitivity import SensitivityPreset
from core.recommendation import MATCH_KEYS, TrainingAdvice, adjustment_indicator, suite_advice, training_advice
from core.scenarios import SCENARIOS, TRAINING_DURATIONS
from core.sensitivity_conversion import PUBG_FOV_DEFAULT, PUBG_FOV_MAX, PUBG_FOV_MIN, hipfire_values
from core.telemetry import ClickStats
from ui.aim_arena import AimArena
from ui.comparison import APPLY_BLIND_RESULT, INPUT_NAMES, BlindResults, HistoryDialog, SuiteResults, milliseconds
from ui.crosshair import CrosshairEditor, CrosshairPreview
from ui.dpi_dialog import DpiDialog
from ui.flick_results import FlickResults
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


@dataclass
class SuiteRun:
    settings: dict
    seconds: int
    rounds: list[tuple[ClickStats, TrainingAdvice]] = field(default_factory=list)
    save_error: str = ""


class MainWindow(QWidget):
    def __init__(self, history_path: Path | None = None):
        super().__init__()
        self.setWindowTitle("CS2 Sensitivity Generator")
        self.resize(1050, 910)
        self.setMinimumSize(720, 560)
        self.arena = None
        self.flick = None
        self.crosshair_settings = Crosshair()
        self.recommendation = 0.0
        self.blind = None
        self.last_blind = None
        self.last_training = None
        self.suite = None
        self.last_suite = None
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
        form.addRow("CS2 步枪灵敏度", self.initial_sensitivity)
        form.addRow(label("这是鼠标输入换算成游戏内转向速度的倍数。设为 1.150，同样移动距离下，"
                          "视角转动量是 1.000 的 1.15 倍。", "muted", True))
        form.addRow("鼠标垫有效横向宽度", self.pad)
        form.addRow("发力习惯", self.profile)
        form.addRow("CS2 画面比例", self.aspect)
        self.baseline = label(style="muted", wrap=True)
        physical_layout.addWidget(self.baseline)
        use_physical = QPushButton("用物理建议填入灵敏度")
        use_physical.clicked.connect(lambda: self.initial_sensitivity.setValue(self.baseline_values()[0]))
        physical_layout.addWidget(use_physical)
        physical_layout.addStretch()

        conversion, conversion_layout = card("跨游戏腰射换算")
        grid.addWidget(conversion, 0, 1)
        self.conversion_distance = label(style="muted", wrap=True)
        conversion_layout.addWidget(self.conversion_distance)
        conversion_grid = QGridLayout()
        conversion_grid.setHorizontalSpacing(8)
        conversion_grid.setVerticalSpacing(7)
        conversion_grid.setColumnStretch(0, 1)
        conversion_grid.addWidget(label("游戏内设置", "muted"), 0, 0)
        conversion_grid.addWidget(label("填入值", "muted"), 0, 1, Qt.AlignmentFlag.AlignRight)
        self.conversion_values = {}
        for row, (key, text) in enumerate((
            ("valorant", "无畏契约 · 瞄准灵敏度"),
            ("battlefield", "战地 6 · 步兵鼠标瞄准"),
            ("pubg", "PUBG · 常规灵敏度（FPP）"),
            ("apex", "Apex Legends · 鼠标灵敏度"),
        ), 1):
            conversion_grid.addWidget(label(text, wrap=True), row, 0)
            value = label("—")
            value.setAccessibleName(text)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            conversion_grid.addWidget(value, row, 1, Qt.AlignmentFlag.AlignRight)
            self.conversion_values[key] = value
        conversion_layout.addLayout(conversion_grid)
        pubg_form = QFormLayout()
        self.pubg_fov = integer(PUBG_FOV_MIN, PUBG_FOV_MAX, PUBG_FOV_DEFAULT)
        self.pubg_fov.setSuffix("°")
        self.pubg_fov.valueChanged.connect(self.refresh_conversions)
        pubg_form.addRow("PUBG 第一人称 FOV", self.pubg_fov)
        conversion_layout.addLayout(pubg_form)
        conversion_layout.addWidget(label("战地 6 和 PUBG 为估算值，可在游戏训练场核对转身距离。",
                                          "muted", True))
        conversion_layout.addStretch()

        practice, practice_layout = card("全屏训练与盲测")
        grid.addWidget(practice, 1, 0)
        self.duration = QComboBox()
        for seconds in TRAINING_DURATIONS:
            self.duration.addItem(f"{seconds} 秒 / 项", seconds)
        duration_form = QFormLayout()
        self.scenario = QComboBox()
        for index, scenario in enumerate(SCENARIOS, 1):
            self.scenario.addItem(f"{index}. {scenario.title}", scenario)
        duration_form.addRow("训练项目", self.scenario)
        duration_form.addRow("单项时长", self.duration)
        practice_layout.addLayout(duration_form)
        self.scenario_hint = label(style="muted", wrap=True)
        practice_layout.addWidget(self.scenario_hint)
        self.practice_button = QPushButton("开始所选训练")
        self.practice_button.setObjectName("primary")
        self.practice_button.clicked.connect(lambda: self.launch(self.scenario.currentData()))
        practice_layout.addWidget(self.practice_button)
        self.suite_button = QPushButton("一键测试六项")
        self.suite_button.clicked.connect(self.start_suite)
        practice_layout.addWidget(self.suite_button)
        practice_layout.addWidget(label("按顺序测试全部六项，每项使用所选时长与当前灵敏度。",
                                        "muted", True))
        self.flick_line = label(style="muted", wrap=True)
        practice_layout.addWidget(self.flick_line)
        blind_row = QHBoxLayout()
        blind_row.addWidget(label("盲测浮动"))
        self.blind_step = decimal(.5, 25, 5, 1, .5)
        self.blind_step.setSuffix(" %")
        blind_row.addWidget(self.blind_step)
        self.blind_button = QPushButton("开始六项 A/B/C 盲测")
        self.blind_button.setObjectName("primary")
        self.blind_button.clicked.connect(self.start_blind)
        blind_row.addWidget(self.blind_button, 1)
        practice_layout.addLayout(blind_row)
        practice_layout.addWidget(label("每档按原顺序测六项，每项 15 秒。初筛约 5 分钟，复核另需约 4 分钟。", "muted", True))

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
        self.recommendation_evidence = label(style="muted", wrap=True)
        self.recommendation_evidence.setAccessibleName("推荐依据")
        self.recommendation_evidence.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        export_layout.addWidget(self.metrics)
        export_layout.addWidget(self.summary)
        export_layout.addWidget(self.recommendation_evidence)
        self.apply_recommendation = QPushButton("应用建议到当前步枪灵敏度")
        self.apply_recommendation.clicked.connect(self.apply_current_recommendation)
        self.recommendation_help = QPushButton("推荐说明")
        self.recommendation_help.clicked.connect(self.show_recommendation_help)
        recommendation_actions = QHBoxLayout()
        recommendation_actions.addWidget(self.apply_recommendation, 1)
        recommendation_actions.addWidget(self.recommendation_help)
        export_layout.addLayout(recommendation_actions)
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
        grid.addWidget(results, 1, 1)
        result_actions = QGridLayout()
        self.analysis_button = QPushButton("16 方向轨迹分析…")
        self.analysis_button.clicked.connect(self.show_flick_results)
        self.clear_button = QPushButton("清除本次测试数据")
        self.clear_button.clicked.connect(self.clear_test_results)
        self.history_button = QPushButton()
        self.history_button.clicked.connect(self.show_history)
        self.reveal_button = QPushButton("查看最近盲测结果")
        self.reveal_button.clicked.connect(self.show_blind_results)
        self.suite_results_button = QPushButton("查看六项结果")
        self.suite_results_button.clicked.connect(self.show_suite_results)
        for index, button in enumerate((self.analysis_button, self.history_button, self.reveal_button,
                                        self.suite_results_button, self.clear_button)):
            result_actions.addWidget(button, index // 2, index % 2)
        results_layout.addLayout(result_actions)
        results_layout.addStretch()
        self.dashboard_grid = grid
        self.dashboard_cards = (physical, conversion, practice, results, players, player_crosshairs, cross, export)
        self.dashboard_columns = 2

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
        self.blind_step.valueChanged.connect(self.refresh)
        self.scenario.currentIndexChanged.connect(self.refresh)
        self.sensitivity_panel.players.currentTextChanged.connect(
            lambda name: self.notify(f"正在预览 {name} 的灵敏度。"))
        self.crosshair_panel.players.currentTextChanged.connect(
            lambda name: self.notify(f"正在预览 {name} 的准星。"))
        self.refresh()
        self.arrange_dashboard()
        if self.history.error:
            self.notify(f"本地历史无法读取：{self.history.error}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "dashboard_grid"):
            self.arrange_dashboard()

    def arrange_dashboard(self) -> None:
        grid = self.dashboard_grid
        cards = self.dashboard_cards
        left_width = max(card.minimumSizeHint().width() for card in cards[::2])
        right_width = max(card.minimumSizeHint().width() for card in cards[1::2])
        margins = self.content.layout().contentsMargins()
        gutter = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        minimum = left_width + right_width + margins.left() + margins.right() + grid.spacing() + gutter
        columns = 2 if self.width() >= minimum else 1
        if columns != self.dashboard_columns:
            self.dashboard_columns = columns
            grid.setColumnStretch(1, int(columns == 2))
            for index, widget in enumerate(cards):
                grid.removeWidget(widget)
                grid.addWidget(widget, index // columns, index % columns)

    def crosshair(self) -> Crosshair:
        return self.crosshair_settings

    def notify(self, message: str) -> None:
        self.status.setText(message)
        self.toast.notify(message)

    def snapshot(self) -> dict:
        return {
            "dpi": self.dpi.value(), "sensitivity": self.initial_sensitivity.value(),
            "aspect": self.aspect.currentIndex(),
            "duration": self.duration.currentIndex(), "pad": self.pad.value(),
            "profile": self.profile.currentIndex(),
            "step": self.blind_step.value(), "scenario": self.scenario.currentIndex(), "crosshair": asdict(self.crosshair_settings),
        }

    def restore_settings(self) -> None:
        saved = self.history.settings
        for key, widget in (("dpi", self.dpi), ("sensitivity", self.initial_sensitivity),
                            ("pad", self.pad),
                            ("step", self.blind_step)):
            value = saved.get(key)
            if isinstance(value, (int, float)) and widget.minimum() <= value <= widget.maximum():
                widget.setValue(int(value) if isinstance(widget, QSpinBox) else value)
        for key, widget in (("aspect", self.aspect), ("duration", self.duration), ("profile", self.profile),
                            ("scenario", self.scenario)):
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
        with QSignalBlocker(self.dpi), QSignalBlocker(self.initial_sensitivity):
            self.dpi.setValue(dpi)
            self.initial_sensitivity.setValue(sensitivity)
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
        if self.flick is not None:
            self.notify("参数已更改，本次成绩已重置。历史记录仍可对比。")
        self.flick = None
        self.preview.update()
        self.refresh()

    def clear_test_results(self) -> None:
        self.flick = None
        self.last_blind = None
        self.last_training = None
        self.last_suite = None
        self.refresh()
        self.notify("已清除本次测试结果。")

    def show_flick_results(self) -> None:
        if self.flick is not None and self.flick.attempts:
            dialog = FlickResults(self.flick, self)
            dialog.exec()
            dialog.deleteLater()

    def show_history(self) -> None:
        self.history.reload()
        dialog = HistoryDialog(self.history, self)
        dialog.cleared.connect(self.history_cleared)
        dialog.exec()
        dialog.deleteLater()
        self.refresh()

    def history_cleared(self) -> None:
        self.last_blind = None
        self.last_training = None
        self.last_suite = None
        self.refresh()

    def baseline_values(self):
        return physical_baseline(self.dpi.value(), self.pad.value(), self.profile.currentData())

    def refresh_conversions(self) -> None:
        sensitivity = self.initial_sensitivity.value()
        dpi = self.dpi.value()
        distance = cm_per_360(dpi, sensitivity)
        self.conversion_distance.setText(f"同为 {dpi} DPI · 匹配水平转身距离 {distance:.2f} cm/360°")
        values = hipfire_values(sensitivity, self.pubg_fov.value())
        for key, places in (("valorant", 3), ("battlefield", 0), ("pubg", 0), ("apex", 2)):
            value = values[key]
            self.conversion_values[key].setText(f"{value:.{places}f}" if value is not None else "超出范围")

    def refresh(self) -> None:
        self.refresh_conversions()
        crosshair = self.crosshair_settings
        self.crosshair_summary.setText(f"{crosshair.style} · {STYLES[crosshair.style]}   ·   "
                                      f"厚度 {crosshair.thickness} px")
        dpi = self.dpi.value()
        self.sensitivity_panel.set_dpi(dpi)
        physical, swing, turn = self.baseline_values()
        physical = round(physical, 3)
        base = self.initial_sensitivity.value()
        selected = self.scenario.currentData()
        self.scenario_hint.setText(selected.instruction)
        self.baseline.setText(f"舒适行程 {swing:.1f} cm  ·  转身 {turn:.0f}°\n"
                              f"物理建议 {physical:.3f} sens  ·  {cm_per_360(dpi, physical):.2f} cm/360°")
        flick = self.flick
        self.analysis_button.setEnabled(flick is not None and flick.attempts > 0)
        self.clear_button.setEnabled(flick is not None or self.last_blind is not None or self.last_suite is not None)
        self.reveal_button.setEnabled(self.last_blind is not None)
        self.suite_results_button.setEnabled(self.last_suite is not None)
        self.history_button.setText(f"本地历史 / 对比（{len(self.history.records)}）")
        if flick is None:
            self.flick_line.clear()
        else:
            reaction, movement = flick.timings()
            sectors = sum(bool(sector.attempts) for sector in flick.sectors)
            self.flick_line.setText(f"上轮点靶 {flick.hits}/{flick.attempts} · {flick.points:g} 分 · 方向 {sectors}/16\n"
                                   f"启动 {milliseconds(reaction)} · 移动后定位 {milliseconds(movement)}")
        value = base
        detail = f"当前步枪 {base:.3f} · 完成普通训练或 A/B/C 盲测获取建议"
        evidence = ()
        input_mode = ""
        advice = None
        if self.last_training is not None:
            settings, training = self.last_training
            if self.settings_match(settings) and settings["duration"] == self.duration.currentIndex():
                advice = training
                input_mode = settings.get("input_mode", "")
        blind_valid = self.last_blind is not None and self.blind_matches_current(self.last_blind)
        if advice is not None:
            value = advice.value
            detail = f"步枪 {base:.3f} → {value:.3f}（{value - base:+.3f}） · {advice.reason}"
            evidence = advice.evidence
        elif blind_valid:
            decision = self.last_blind.decision()
            value = decision.recommend.sensitivity
            detail = f"步枪 {base:.3f} → {value:.3f}（{value - base:+.3f}） · {decision.reason}"
            evidence = decision.evidence
            input_mode = self.last_blind.settings.get("input_mode", "")
        self.recommendation = round(value, 3)
        self.apply_recommendation.setEnabled(self.recommendation != base)
        self.metrics.setText(f"{self.recommendation:.3f} sens · {adjustment_indicator(base, self.recommendation)}   ·   {edpi(dpi, self.recommendation):.0f} eDPI\n"
                             f"{cm_per_360(dpi, self.recommendation):.2f} cm/360°")
        self.summary.setText(detail)
        if input_mode in INPUT_NAMES:
            evidence = (INPUT_NAMES[input_mode], *evidence)
        self.recommendation_evidence.setText("\n".join(evidence))
        self.recommendation_evidence.setVisible(bool(evidence))
        self.cfg.setPlainText(cfg_text(self.recommendation).rstrip())
        self.settings_timer.start()

    def launch(self, scenario, *, sensitivity=None, seed=None, stage="", seconds=None) -> None:
        duration = seconds if seconds is not None else (
            self.duration.currentData() if sensitivity is None else ROUND_SECONDS)
        value = self.initial_sensitivity.value() if sensitivity is None else sensitivity
        seed = self.random.getrandbits(64) if seed is None else seed
        continuous = self.suite is not None or self.blind is not None
        if self.arena is not None:
            if continuous and self.arena.done:
                self.arena.set_round(scenario, value, duration, seed, stage)
            return
        self.arena = AimArena(scenario, value, self.aspect.currentData(), duration, self.crosshair(),
                              seed=seed, stage=stage, continuous=continuous)
        self.arena.finished.connect(self.arena_finished)
        if continuous:
            self.arena.round_finished.connect(self.continuous_round_finished)
        self.content.setEnabled(False)
        self.arena.open_on(self.screen())

    def continuous_round_finished(self, stats) -> None:
        if self.blind is not None:
            self.finish_blind_phase(stats, "")
        elif self.suite is not None:
            self.finish_suite_round(stats, "")

    def close_completed_arena(self) -> None:
        arena, self.arena = self.arena, None
        arena.finished.disconnect(self.arena_finished)
        arena.close()
        arena.deleteLater()

    def arena_finished(self, stats, error: str) -> None:
        arena, self.arena = self.arena, None
        arena.deleteLater()
        if self.closing:
            return
        if self.blind is not None:
            self.finish_blind_phase(stats, error)
            return
        if self.suite is not None:
            self.finish_suite_round(stats, error)
            return
        self.content.setEnabled(True)
        if stats is not None:
            self.flick = stats
            settings = {**self.snapshot(), "input_mode": stats.input_mode}
            self.last_training = (settings, training_advice(stats, settings["sensitivity"]))
            error = self.save_history(record("scenario", settings, stats, None,
                                             name=arena.scenario.title))
            self.refresh()
        self.notify(error or ("已保存本轮测试。" if stats else "测试已取消。"))
        QTimer.singleShot(0, self.activateWindow)

    def start_suite(self) -> None:
        if self.arena is not None or self.blind is not None or self.suite is not None:
            return
        self.suite = SuiteRun(self.snapshot(), self.duration.currentData())
        self.launch_suite_round()

    def launch_suite_round(self) -> None:
        if self.suite is None or self.closing:
            return
        index = len(self.suite.rounds)
        stage = f"六项测试 · {index + 1}/{len(SCENARIOS)}"
        self.launch(SCENARIOS[index], sensitivity=self.suite.settings["sensitivity"],
                    stage=stage, seconds=self.suite.seconds)

    def finish_suite_round(self, stats, error: str) -> None:
        suite = self.suite
        if stats is None:
            self.suite = None
            self.content.setEnabled(True)
            self.refresh()
            self.notify(error or suite.save_error or "六项测试已取消，已完成的项目保留成绩。")
            QTimer.singleShot(0, self.activateWindow)
            return
        index = len(suite.rounds)
        scenario = SCENARIOS[index]
        settings = {**suite.settings, "scenario": index}
        advice = training_advice(stats, settings["sensitivity"])
        suite.rounds.append((stats, advice))
        save_error = self.save_history(record("scenario", settings, stats, None, name=scenario.title))
        suite.save_error = save_error or suite.save_error
        if len(suite.rounds) < len(SCENARIOS):
            QTimer.singleShot(100, self.launch_suite_round)
            return
        self.close_completed_arena()
        self.suite = None
        base = suite.settings["sensitivity"]
        advice = suite_advice(base, [result for _, result in suite.rounds])
        self.last_suite = (base, suite.rounds, advice)
        context = {key: value for key, value in suite.settings.items() if key != "scenario"}
        context["input_mode"] = stats.input_mode
        self.last_training = (context, advice)
        conclusion = f"步枪 {base:.3f} → {advice.value:.3f} · {advice.reason}"
        save_error = self.save_history(record("suite", suite.settings, None, None, conclusion=conclusion,
                                              input_mode=stats.input_mode))
        self.content.setEnabled(True)
        self.refresh()
        self.notify(save_error or suite.save_error or "六项测试完成，已生成综合建议。")
        self.activateWindow()
        QTimer.singleShot(0, self.show_suite_results)

    def show_suite_results(self) -> None:
        if self.last_suite is not None and not self.closing:
            dialog = SuiteResults(*self.last_suite, self)
            dialog.exec()
            dialog.deleteLater()

    def start_blind(self) -> None:
        if self.arena is not None or self.blind is not None or self.suite is not None:
            return
        try:
            self.blind = BlindSession.create(self.initial_sensitivity.value(), self.blind_step.value(), self.random)
        except ValueError as error:
            self.notify(str(error))
            return
        self.blind.settings = {key: value for key, value in self.snapshot().items() if key != "scenario"}
        self.launch_blind_phase()

    def launch_blind_phase(self) -> None:
        if self.blind is None or self.closing:
            return
        candidate = self.blind.current
        stage = f"盲测 · {self.blind.progress} · {candidate.label} 组"
        self.notify(f"{stage}，移动鼠标开始。")
        self.launch(self.blind.scenario, sensitivity=candidate.sensitivity, seed=self.blind.seed, stage=stage)

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
        self.close_completed_arena()
        self.last_blind, self.blind = self.blind, None
        self.last_training = None
        session = self.last_blind
        session.settings["input_mode"] = stats.input_mode
        decision = session.decision()
        entries = [
            record("blind", {**session.settings, "sensitivity": candidate.sensitivity, "scenario": index},
                   stats, None,
                   name=f"{SCENARIOS[index].title} · {'复核' if candidate in session.verification else '初筛'} {candidate.label}",
                   score=performance(index, stats),
                   conclusion=decision.reason)
            for candidate in session.candidates
            for index, stats in candidate.rounds.items()
        ]
        error = self.save_history(*entries)
        self.content.setEnabled(True)
        self.refresh()
        self.notify(error or "盲测完成，数值已揭晓。")
        self.activateWindow()
        QTimer.singleShot(0, self.show_blind_results)

    def blind_matches_current(self, session: BlindSession) -> bool:
        return self.settings_match(session.settings)

    def settings_match(self, settings: dict) -> bool:
        current = self.snapshot()
        keys = (*MATCH_KEYS, "sensitivity")
        return all(settings.get(key) == current[key] for key in keys if key != "scenario" or key in settings)

    def show_recommendation_help(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("推荐灵敏度说明")
        dialog.resize(620, 405)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(9)
        layout.addWidget(label("如何读推荐值", "section"))
        layout.addWidget(label(
            "「当前值 → 建议值」是训练前的步枪灵敏度和建议试用的值。↑ 表示调高，↓ 表示调低。"
            "eDPI 是 DPI × 灵敏度，cm/360° 是游戏内转一整圈所需移动的距离。"
            "应用建议后，跨游戏换算表会跟随输入框更新。", wrap=True))
        layout.addWidget(label("普通训练", "section"))
        layout.addWidget(label(
            "完成一轮就根据本轮瞄准表现给建议，最多调整 3%。固定靶看首段位移，移动靶看开枪瞬间的偏差。至少有 6 个有效样本，且偏差在多个方向一致时才调整。", wrap=True))
        layout.addWidget(label("六项综合", "section"))
        layout.addWidget(label(
            "至少两项支持同一方向，而且占所有给出调整建议的项目至少三分之二，才会调整。"
            "取同方向建议的中位值，幅度最多 3%。", wrap=True))
        layout.addWidget(label("A/B/C 盲测", "section"))
        layout.addWidget(label(
            f"比较当前值和两档候选，每档依次完成六项，每项 {ROUND_SECONDS} 秒。"
            "候选需在多项领先，并用新种子完成六项复核。评分结合命中、得分效率和有效瞄准误差。", wrap=True))
        layout.addWidget(label(
            "证据不足时会保留当前值。点击「应用建议」会更新软件里的步枪灵敏度。"
            "复制灵敏度 CFG 后，可把 sensitivity 指令粘贴到 CS2 控制台。", "muted", True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        dialog.deleteLater()

    def apply_current_recommendation(self) -> None:
        self.initial_sensitivity.setValue(self.recommendation)
        self.notify(f"已应用步枪灵敏度 · {self.initial_sensitivity.value():.3f}")

    def show_blind_results(self) -> None:
        if self.last_blind is None or self.closing:
            return
        session = self.last_blind
        decision = session.decision()
        dialog = BlindResults(session, decision, self, can_apply=self.blind_matches_current(session))
        if dialog.exec() == APPLY_BLIND_RESULT:
            if self.blind_matches_current(session) and self.last_blind is session:
                self.initial_sensitivity.setValue(decision.recommend.sensitivity)
                self.notify(f"已应用盲测建议 · {self.initial_sensitivity.value():.3f}")
            else:
                self.notify("当前设置已改变，请重新盲测。")
        dialog.deleteLater()

    def copy_console(self) -> None:
        QApplication.clipboard().setText(console_text(self.recommendation))
        self.notify("已复制 CS2 控制台指令。")

    def config_text(self, kind: str) -> str:
        sensitivity = cfg_text(self.recommendation) if kind != "crosshair" else ""
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
