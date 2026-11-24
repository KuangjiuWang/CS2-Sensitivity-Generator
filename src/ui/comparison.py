"""Blind reveal and two-entry history comparison."""
from datetime import datetime
from math import isfinite

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.blind_test import performance
from core.crosshair import STYLES
from core.flick_analysis import MIN_DIRECTION_SAMPLES, SECTOR_LABELS
from core.scenarios import SCENARIOS
from core.recommendation import adjustment_indicator
from ui.toast import Toast

APPLY_BLIND_RESULT = 2
DASH = "—"
INPUT_NAMES = {
    "win32_raw": "Windows 原始输入",
    "mac_raw": "macOS 原始输入",
    "mac_compat": "macOS 兼容输入（受系统指针设置影响）",
}


def milliseconds(seconds) -> str:
    return DASH if seconds is None else f"{seconds * 1000:.0f} ms"


def make_table(headers, rows):
    table = QTableWidget(rows, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().hide()
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    return table


def set_row(table, row, values):
    for column, text in enumerate(values):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, column, item)


class BlindResults(QDialog):
    def __init__(self, session, decision, parent, *, can_apply=True):
        super().__init__(parent)
        self.setWindowTitle("盲测揭晓")
        self.resize(1000, 570)
        layout = QVBoxLayout(self)
        title = QLabel(decision.reason)
        title.setObjectName("metric")
        title.setWordWrap(True)
        layout.addWidget(title)
        mode = next((stats.input_mode for group in session.candidates for stats in group.rounds.values()
                     if stats.input_mode), "")
        if mode:
            layout.addWidget(QLabel(INPUT_NAMES[mode]))
        evidence = QLabel("\n".join(decision.evidence))
        evidence.setWordWrap(True)
        evidence.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if decision.evidence:
            layout.addWidget(evidence)
        table = make_table(("阶段 · 组别", "灵敏度", "有效项目", "命中 / 射击", "成绩中位分"),
                           len(session.candidates))
        for index, candidate in enumerate(session.candidates):
            stage = "复核" if candidate in session.verification else "初筛"
            marker = " · 当前值" if candidate.sensitivity == session.baseline else ""
            if candidate is decision.recommend and not marker:
                marker = " · 建议值"
            hits = sum(stats.hits for stats in candidate.rounds.values())
            attempts = sum(stats.attempts for stats in candidate.rounds.values())
            set_row(table, index, (f"{stage} {candidate.label}{marker}", f"{candidate.sensitivity:.3f}",
                                  f"{len(candidate.valid_indices)}/6", f"{hits}/{attempts}", f"{candidate.score:.1f}"))
        layout.addWidget(table)
        rounds = make_table(("项目", *(candidate.label for candidate in session.candidates)), len(SCENARIOS))
        for index, scenario in enumerate(SCENARIOS):
            set_row(rounds, index, (scenario.title, *(f"{performance(index, candidate.rounds[index]):.1f}"
                                                     for candidate in session.candidates)))
        rounds.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(rounds)
        detail = QLabel("决策使用同项目的配对分差。命中和单位时间得分是基础，两档的有效样本充足时加入静态瞄准误差"
                        "或移动靶跟随误差。至少四项可比较，候选至少赢三项。")
        detail.setWordWrap(True)
        layout.addWidget(detail)
        buttons = QHBoxLayout()
        buttons.addStretch()
        if decision.recommend.sensitivity != session.baseline and can_apply:
            apply_button = QPushButton("应用到当前步枪灵敏度")
            apply_button.setObjectName("primary")
            apply_button.clicked.connect(lambda: self.done(APPLY_BLIND_RESULT))
            buttons.addWidget(apply_button)
        elif not can_apply:
            buttons.addWidget(QLabel("当前设置与本轮盲测不同，仅供查看。"))
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)


class SuiteResults(QDialog):
    def __init__(self, base, rounds, advice, parent):
        super().__init__(parent)
        self.setWindowTitle("六项综合测试结果")
        self.resize(1000, 430)
        layout = QVBoxLayout(self)
        summary = QLabel(f"步枪 {base:.3f} → {advice.value:.3f} {adjustment_indicator(base, advice.value)}   ·   {advice.reason}")
        summary.setObjectName("metric")
        summary.setWordWrap(True)
        layout.addWidget(summary)
        if rounds and rounds[0][0].input_mode:
            layout.addWidget(QLabel(INPUT_NAMES[rounds[0][0].input_mode]))
        evidence = QLabel("\n".join(advice.evidence))
        evidence.setWordWrap(True)
        if advice.evidence:
            layout.addWidget(evidence)
        table = make_table(("训练项目", "命中 / 射击", "准确率", "单项建议", "判断依据"), len(rounds))
        for column in range(4):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        for index, (stats, result) in enumerate(rounds):
            set_row(table, index, (SCENARIOS[index].title, f"{stats.hits}/{stats.attempts}",
                                   f"{stats.accuracy:.1%}", f"{result.value:.3f} {adjustment_indicator(base, result.value)}",
                                   "\n".join((result.reason, *result.evidence))))
        layout.addWidget(table)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)


HISTORY_KINDS = {"scenario": "训练", "suite": "六项综合", "flick": "拉枪", "tracking": "动态跟枪",
                 "supplement": "方向补测", "blind": "盲测"}
HISTORY_METRICS = (
    ("命中率", "hits", "attempts", ".0%"),
    ("启动反应", "reaction_sum", "starts", "ms"),
    ("移动后定位", "movement_sum", "movement_hits", "ms"),
    ("平均过冲", "overshoot_sum", "overshoot_count", ".2f°"),
    ("轨迹直达率", "efficiency_sum", "hits", ".0%"),
    ("最大横偏均值", "deviation_sum", "hits", ".2f°"),
)


def history_label(entry: dict) -> str:
    """Validate the fields used by the comparison before exposing the record."""
    time = datetime.fromisoformat(entry["time"]).astimezone().strftime("%m-%d %H:%M:%S")
    settings = entry["settings"]
    crosshair = settings["crosshair"]
    if not 0 <= crosshair["style"] < len(STYLES) or not isinstance(crosshair["style"], int):
        raise ValueError("invalid crosshair style")
    numbers = [settings["dpi"], settings["sensitivity"]]
    numbers.extend(crosshair[key] for key in ("length", "thickness", "gap", "outline_mode", "reference_height"))
    _ = crosshair["color"]
    flick, track = entry["flick"], entry["tracking"]
    if flick is not None:
        numbers.extend((flick["hits"], flick["attempts"]))
        sectors = flick["sectors"]
        if len(sectors) != len(SECTOR_LABELS):
            raise ValueError("invalid direction count")
        keys = {key for _, total, count, _ in HISTORY_METRICS for key in (total, count)}
        numbers.extend(sector[key] for sector in sectors for key in keys)
    if track is not None:
        reaction, settle = track["timings"]
        numbers.extend(value for value in (reaction, settle) if value is not None)
        numbers.append(track["accuracy"])
    if entry["score"] is not None:
        numbers.append(entry["score"])
        _ = entry["conclusion"]
    if not all(isinstance(value, (int, float)) and isfinite(value) for value in numbers):
        raise ValueError("invalid numeric history value")
    kind = HISTORY_KINDS.get(entry["kind"], entry["kind"])
    detail = f" · {entry['name']}" if entry["name"] else ""
    return f"{time} · {kind}{detail} · {settings['sensitivity']:.3f}"


class HistoryDialog(QDialog):
    cleared = Signal()

    def __init__(self, store, parent):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("本地历史 · 对比测试")
        self.resize(970, 695)
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("选择两轮测试对比"))
        toolbar.addStretch()
        self.clear_button = QPushButton("清除所有历史")
        self.clear_button.clicked.connect(self.clear_history)
        toolbar.addWidget(self.clear_button)
        layout.addLayout(toolbar)
        selectors = QHBoxLayout()
        self.selectors = [QComboBox(), QComboBox()]
        self.summaries = [QLabel(), QLabel()]
        for index, (selector, summary) in enumerate(zip(self.selectors, self.summaries)):
            selector.setAccessibleName(("参考轮次", "对比轮次")[index])
            summary.setWordWrap(True)
            column = QVBoxLayout()
            column.addWidget(selector)
            column.addWidget(summary)
            selectors.addLayout(column, 1)
            selector.currentIndexChanged.connect(self.refresh)
        layout.addLayout(selectors)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("方向对比指标"))
        self.metric_picker = QComboBox()
        self.metric_picker.addItems(tuple(metric[0] for metric in HISTORY_METRICS))
        filter_row.addWidget(self.metric_picker)
        filter_row.addStretch()
        layout.addLayout(filter_row)
        self.table = make_table(("方向", "参考 · 命中/次数", "参考 · 指标", "对比 · 命中/次数", "对比 · 指标"), 16)
        self.metric_picker.currentIndexChanged.connect(self.refresh)
        layout.addWidget(self.table, 1)
        self.legend = QLabel()
        self.legend.setWordWrap(True)
        layout.addWidget(self.legend)
        self.toast = Toast(self)
        self.populate()

    def populate(self) -> None:
        entries = []
        for entry in reversed(self.store.records):
            try:
                entries.append((history_label(entry), entry))
            except (KeyError, IndexError, TypeError, ValueError, OverflowError, OSError):
                continue
        skipped = len(self.store.records) - len(entries)
        warning = f"有 {skipped} 条记录无法读取，已跳过。" if skipped else ""
        self.legend.setText("＊表示该方向少于 3 个目标。 " + warning)
        for offset, selector in enumerate(self.selectors):
            selector.blockSignals(True)
            selector.clear()
            for label, entry in entries:
                selector.addItem(label, entry)
            if not entries:
                selector.addItem("暂无测试历史")
            selector.setCurrentIndex(min(offset, max(0, len(entries) - 1)))
            selector.blockSignals(False)
        self.clear_button.setEnabled(bool(self.store.records) or bool(self.store.error))
        self.refresh()

    def refresh(self) -> None:
        entries = [selector.currentData() for selector in self.selectors]
        for summary, entry in zip(self.summaries, entries):
            if entry is None:
                summary.setText(self.store.error or "完成测试后会自动保存到这里。")
                continue
            settings = entry["settings"]
            crosshair = settings["crosshair"]
            text = (f'{settings["dpi"]} DPI × {settings["sensitivity"]:.3f}  ·  '
                    f'{STYLES[crosshair["style"]]}  {crosshair["length"]}/{crosshair["thickness"]}/{crosshair["gap"]} px')
            text += "\n" + INPUT_NAMES.get(entry.get("input_mode"), "输入来源未记录")
            if entry["flick"]:
                method = {"scenario": "点靶", "click": "旧版点击拉枪"}.get(entry["flick"].get("method"), "旧版悬停拉枪")
                text += f'\n{method} {entry["flick"]["hits"]}/{entry["flick"]["attempts"]}'
            if entry["tracking"]:
                track = entry["tracking"]
                reaction, settle = track["timings"]
                text += f'\n跟枪 {track["accuracy"]:.0%}  ·  反应 {milliseconds(reaction)}  ·  稳定 {milliseconds(settle)}'
            if entry["score"] is not None:
                text += f'\n盲测 {entry["score"]:.1f} 分 · {entry["conclusion"]}'
            elif entry.get("conclusion"):
                text += f'\n{entry["conclusion"]}'
            summary.setText(text)
            summary.setToolTip(f'准星 RGBA {crosshair["color"]} · 描边 {crosshair["outline_mode"]} · '
                               f'参考高度 {crosshair["reference_height"]} px')
        for index, direction in enumerate(SECTOR_LABELS):
            set_row(self.table, index, (direction, *self.direction_stats(entries[0], index),
                                       *self.direction_stats(entries[1], index)))

    def direction_stats(self, entry, index):
        if not entry or not entry["flick"]:
            return DASH, DASH
        sample = entry["flick"]["sectors"][index]
        attempts = sample["attempts"]
        _, total, count, formatting = HISTORY_METRICS[self.metric_picker.currentIndex()]
        value = DASH
        if sample[count]:
            average = sample[total] / sample[count]
            value = milliseconds(average) if formatting == "ms" else (
                f"{average:.2f}°" if formatting == ".2f°" else f"{average:.0%}"
            )
        mark = " ＊" if attempts < MIN_DIRECTION_SAMPLES else ""
        return f'{sample["hits"]}/{attempts}{mark}', value

    def clear_history(self) -> None:
        answer = QMessageBox.question(self, "确认清除所有历史", "所有已保存的测试和盲测记录都会从本机删除。确定清除？",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.clear()
        except OSError as error:
            self.toast.notify(f"无法清除历史：{error}")
            return
        self.populate()
        self.cleared.emit()
        self.toast.notify("已清除所有本地历史。")
