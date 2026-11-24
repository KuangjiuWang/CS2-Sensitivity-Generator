"""Direction-by-direction results and replayable aim traces."""
from math import cos, radians, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHeaderView, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.flick_analysis import MIN_DIRECTION_SAMPLES, SECTOR_LABELS, SECTOR_WIDTH, FlickTrace
from ui.comparison import milliseconds

CYAN = "#6ADCE8"
LIME = "#D8F576"


class SectorPlot(QWidget):
    def __init__(self, sectors):
        super().__init__()
        self.sectors = sectors
        self.selected = 0
        self.setMinimumHeight(194)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().toRectF().center()
        radius = min(self.width(), self.height()) / 2 - 24
        circle = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        for index, stats in enumerate(self.sectors):
            color = QColor("#253449")
            if stats.attempts:
                rate = stats.hits / stats.attempts
                color = QColor.fromHslF(.52, .49, .26 + .28 * rate)
            painter.setPen(QPen(QColor(LIME if index == self.selected else "#0B0E16"),
                                2 if index == self.selected else 1))
            painter.setBrush(color)
            painter.drawPie(circle, round((SECTOR_WIDTH / 2 - index * SECTOR_WIDTH) * 16),
                            round(-SECTOR_WIDTH * 16))
        for index in (0, 4, 8, 12):
            angle = radians(index * SECTOR_WIDTH)
            point = center + QPointF((radius + 13) * cos(angle), (radius + 13) * sin(angle))
            painter.setPen(QColor("#EDF1FB"))
            painter.drawText(QRectF(point.x() - 10, point.y() - 10, 20, 20),
                             Qt.AlignmentFlag.AlignCenter, SECTOR_LABELS[index])


class AimTracePlot(QWidget):
    def __init__(self):
        super().__init__()
        self.trace: FlickTrace | None = None
        self.setMinimumSize(270, 215)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#121824"))
        if self.trace is None:
            painter.setPen(QColor("#A5B3C9"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "该方向暂无轨迹")
            return
        trace = self.trace
        extent = max(max(abs(x), abs(y)) for x, y in (*trace.points, trace.target)) + trace.radius
        center = self.rect().toRectF().center()
        scale = (min(self.width(), self.height()) / 2 - 12) / extent

        def point(pair):
            return center + QPointF(pair[0] * scale, pair[1] * scale)

        target = point(trace.target)
        painter.setPen(QPen(QColor("#54637C"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(center, target)
        painter.setBrush(QColor("#233242"))
        painter.setPen(QPen(QColor("#A5B3C9"), 1))
        painter.drawEllipse(target, scale * trace.radius, scale * trace.radius)
        bounds = len(trace.points) if trace.contact is None else trace.contact + 1
        painter.setPen(QPen(QColor(CYAN), 2))
        painter.drawPolyline(QPolygonF([point(pair) for pair in trace.points[:bounds]]))
        if trace.contact is not None:
            painter.setPen(QPen(QColor(LIME), 2))
            painter.drawPolyline(QPolygonF([point(pair) for pair in trace.points[trace.contact:]]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#EDF1FB"))
        painter.drawEllipse(center, 3, 3)


class FlickResults(QDialog):
    def __init__(self, stats, parent):
        super().__init__(parent)
        self.setWindowTitle("16 方向 · 轨迹与点靶分析")
        self.resize(1140, 660)
        self.sectors = stats.sectors
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"点靶命中 {stats.hits}/{stats.attempts}   ·   "
                                f"覆盖 {sum(bool(sector.attempts) for sector in self.sectors)}/16 个方向"))
        columns = QHBoxLayout()
        layout.addLayout(columns, 1)
        self.table = QTableWidget(len(self.sectors), 8)
        self.table.setHorizontalHeaderLabels(("方向", "命中/次数", "命中率", "启动反应", "移动后定位",
                                               "过冲", "直达率", "横偏"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMinimumWidth(555)
        columns.addWidget(self.table, 3)
        for row, sector in enumerate(self.sectors):
            hits = sector.hits
            low_sample = sector.attempts < MIN_DIRECTION_SAMPLES
            values = (
                SECTOR_LABELS[row] + (" ＊" if low_sample else ""), f"{hits}/{sector.attempts}",
                f"{hits / sector.attempts:.0%}" if sector.attempts else "—",
                milliseconds(sector.reaction_sum / sector.starts if sector.starts else None),
                milliseconds(sector.movement_sum / sector.movement_hits if sector.movement_hits else None),
                f"{sector.overshoot_sum / sector.overshoot_count:.2f}°" if sector.overshoot_count else "—",
                f"{sector.efficiency_sum / hits:.0%}" if hits else "—",
                f"{sector.deviation_sum / hits:.2f}°" if hits else "—",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if low_sample and column == 0:
                    item.setForeground(QColor("#FFBD7B"))
                    item.setToolTip(f"样本不足，至少需要 {MIN_DIRECTION_SAMPLES} 个目标")
                if column == 5 and sector.overshoot_count:
                    item.setToolTip(f"计算 {sector.overshoot_count} 次有效击中在开枪前越过目标远缘的角度。")
                self.table.setItem(row, column, item)

        charts = QVBoxLayout()
        columns.addLayout(charts, 2)
        self.sector_plot = SectorPlot(self.sectors)
        charts.addWidget(self.sector_plot, 1)
        charts.addWidget(QLabel("选中左侧方向查看轨迹 · 扇区颜色越亮，命中率越高"))
        self.samples = QComboBox()
        charts.addWidget(self.samples)
        self.trace_plot = AimTracePlot()
        charts.addWidget(self.trace_plot, 1)
        charts.addWidget(QLabel("白点为起点 · 青色为命中前轨迹 · 黄绿色为命中后轨迹"))
        help_text = QLabel("＊表示该方向少于 3 个目标。启动反应从目标出现到准星移动 0.35°；移动后定位从启动到首次命中。"
                           "直达率为直线距离 ÷ 实际路径，横偏取每次命中前的最大侧偏后求平均。")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        close.rejected.connect(self.reject)

        layout.addWidget(close)
        self.samples.currentIndexChanged.connect(self.show_trace)
        self.table.currentCellChanged.connect(self.show_sector)
        most_sampled = max(range(len(self.sectors)), key=lambda index: self.sectors[index].attempts)
        self.table.selectRow(most_sampled)
        self.show_sector(most_sampled)

    def show_sector(self, row: int) -> None:
        if row < 0:
            return
        self.sector_plot.selected = row
        self.sector_plot.update()
        self.samples.blockSignals(True)
        self.samples.clear()
        for index, trace in enumerate(reversed(self.sectors[row].traces)):
            detail = "未命中" if trace.latency is None else f"命中 · {trace.latency * 1000:.0f} ms"
            self.samples.addItem(f"{SECTOR_LABELS[row]} · 轨迹 {index + 1} · {detail}", trace)
        if not self.samples.count():
            self.samples.addItem(f"{SECTOR_LABELS[row]} · 无样本")
        self.samples.blockSignals(False)
        self.show_trace()

    def show_trace(self) -> None:
        self.trace_plot.trace = self.samples.currentData()
        self.trace_plot.update()
