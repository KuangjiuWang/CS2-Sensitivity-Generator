"""Crosshair editor and pixel-based practice renderer."""
from math import floor

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QTransform
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from core.crosshair import (
    ANIMATED_STYLES, GAP_STYLES, LENGTH_STYLES, SPREAD_STYLES, STYLES, Crosshair, decode_share_code,
)


def arm_path(length, gap, width, t_style):
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.WindingFill)
    if length:
        path.addRect(QRectF(gap, -width / 2, length, width))
        path.addRect(QRectF(-gap - length, -width / 2, length, width))
        path.addRect(QRectF(-width / 2, gap, width, length))
        if not t_style:
            path.addRect(QRectF(-width / 2, -gap - length, width, length))
    return path


def ring_path(radius, thickness, circle):
    path = QPainterPath()
    inner = QPainterPath()
    outer_bounds = QRectF(-radius - thickness, -radius - thickness,
                          2 * (radius + thickness), 2 * (radius + thickness))
    inner_bounds = QRectF(-radius, -radius, 2 * radius, 2 * radius)
    if circle:
        path.addEllipse(outer_bounds)
        inner.addEllipse(inner_bounds)
    else:
        path.addRect(outer_bounds)
        inner.addRect(inner_bounds)
    return path.subtracted(inner)


def quadrant_path(length, gap, width, t_style):
    path = QPainterPath()
    if length <= 0:
        return path
    edge = gap + length + width
    for x_sign, y_sign in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        if t_style and y_sign < 0:
            continue
        corner = QPainterPath()
        corner.addRect(QRectF(gap, edge - width, length, width))
        corner.addRect(QRectF(edge - width, gap, width, length + width))
        path.addPath(QTransform.fromScale(x_sign, y_sign).map(corner))
    return path


def draw_crosshair(painter: QPainter, center: QPointF, settings: Crosshair, height: float,
                   stretch: float = 1.0, magnification: float = 1.0, expanded: bool = False) -> None:
    dpr = painter.device().devicePixelRatioF()
    height_px = height * dpr
    length, gap, thickness = settings.dimensions(height_px)
    scale = height_px / settings.reference_height
    style = settings.style
    spread = 0
    if expanded and style in ANIMATED_STYLES:
        spread = round(scale * (.12 * (64 + settings.spread_limit) if style in SPREAD_STYLES else 5))
    parts = []
    if style == 1:
        parts.append((ring_path(round(4 * scale) + spread, thickness, True), 1))
    elif style in (3, 8):
        parts.append((ring_path(gap, thickness, style == 3), 1))
    elif style in (7, 9):
        corner_length = length if style == 7 else round((gap + thickness) * settings.split_ratio)
        parts.append((quadrant_path(corner_length, gap + spread, thickness,
                                    settings.t_style and style == 7), 1))
    elif style == 2 and expanded:
        outer_length = round(length * settings.split_ratio)
        split = round(scale * settings.split_distance)
        parts.append((arm_path(length - outer_length, gap, thickness, settings.t_style), settings.inner_alpha))
        parts.append((arm_path(outer_length, gap + length - outer_length + split + spread,
                               thickness, settings.t_style), settings.outer_alpha))
    elif style != 6:
        parts.append((arm_path(length, gap + spread, thickness, settings.t_style), 1))
    if settings.dot or style == 6:
        dot = QPainterPath()
        dot.addRect(QRectF(-thickness / 2, -thickness / 2, thickness, thickness))
        if len(parts) == 1 and parts[0][1] == 1:
            parts[0] = (parts[0][0].united(dot), 1)
        else:
            parts.append((dot, 1))

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, style in (1, 3))
    pixel_offset = (thickness % 2) / 2
    painter.translate((floor(center.x() * dpr) + pixel_offset) / dpr,
                      (floor(center.y() * dpr) + pixel_offset) / dpr)
    painter.scale(stretch * magnification / dpr, magnification / dpr)
    for path, alpha in parts:
        if path.isEmpty() or alpha == 0:
            continue
        color = QColor(*settings.color)
        color.setAlphaF(color.alphaF() * alpha)
        if settings.outline_mode == 1:
            stroker = QPainterPathStroker()
            stroker.setWidth(2)
            outline = stroker.createStroke(path).subtracted(path)
            painter.fillPath(outline, QColor(*settings.outline_color))
        elif settings.outline_mode == 2:
            outline = path.translated(-1, -1).subtracted(path)
            painter.fillPath(outline, QColor(*settings.outline_color))
        painter.fillPath(path, color)
    painter.restore()


class CrosshairPreview(QWidget):
    def __init__(self, read_settings, expanded=None, parent=None):
        super().__init__(parent)
        self.read_settings = read_settings
        self.expanded = expanded
        self.setMinimumHeight(83)
        self.setAccessibleName("准星放大预览")

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#121824"))
        settings = self.read_settings()
        expanded = self.expanded is not None and self.expanded.isChecked()
        draw_crosshair(painter, self.rect().toRectF().center(), settings,
                       settings.reference_height / self.devicePixelRatioF(), magnification=2,
                       expanded=expanded)


class CrosshairEditor(QDialog):
    def __init__(self, settings: Crosshair, parent):
        super().__init__(parent)
        self.setWindowTitle("CS2 准星设置")
        self.setMinimumWidth(520)
        self.controls = {}
        self.colors = {"color": settings.color, "outline_color": settings.outline_color}
        layout = QVBoxLayout(self)
        import_line = QHBoxLayout()
        self.share = QLineEdit()
        self.share.setPlaceholderText("粘贴新版 CS2 准星分享码")
        self.share.setAccessibleName("CS2 准星分享码")
        import_line.addWidget(self.share, 1)
        import_button = QPushButton("导入")
        import_button.setAutoDefault(False)
        import_button.clicked.connect(self.import_code)
        self.share.returnPressed.connect(self.import_code)
        import_line.addWidget(import_button)
        layout.addLayout(import_line)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        basic, advanced = QWidget(), QWidget()
        tabs.addTab(basic, "外观")
        tabs.addTab(advanced, "动态与开镜")
        self.basic = QFormLayout(basic)
        self.advanced = QFormLayout(advanced)
        self.add_field(self.basic, "style", "样式", choices=tuple(f"{index} · {name}" for index, name in enumerate(STYLES)))
        self.add_field(self.basic, "length", "长度（px）", bounds=(0, 255))
        self.add_field(self.basic, "thickness", "厚度（px）", bounds=(0, 32))
        self.add_field(self.basic, "gap", "间隙（px）", bounds=(-3840, 3840))
        self.add_field(self.basic, "dot", "中心点")
        self.add_field(self.basic, "t_style", "T 形")
        self.add_field(self.basic, "outline_mode", "描边", choices=("无", "完整", "半描边"))
        for name, title in (("color", "准星颜色和透明度"), ("outline_color", "描边颜色和透明度")):
            button = QPushButton("选择颜色")
            button.clicked.connect(lambda checked=False, key=name: self.pick_color(key))
            self.controls[name] = button
            self.basic.addRow(title, button)
        self.add_field(self.basic, "reference_height", "设置时的游戏画面高度（px）", bounds=(240, 65535))
        self.add_field(self.advanced, "spread_limit", "动态扩散上限", bounds=(0, 255))
        self.add_field(self.advanced, "split_distance", "分离距离", bounds=(0, 127))
        self.add_field(self.advanced, "inner_alpha", "内侧透明度", bounds=(0., 1.))
        self.add_field(self.advanced, "outer_alpha", "外侧透明度", bounds=(.30, 1.))
        self.add_field(self.advanced, "split_ratio", "分离／象限比例", bounds=(0., 1.))
        self.add_field(self.advanced, "follow_recoil", "跟随后坐力")
        self.add_field(self.advanced, "scope_scale", "开镜中心点大小", bounds=(.10, 2.))
        self.add_field(self.advanced, "scope_color", "开镜中心点使用准星颜色")
        detail = QLabel("测试场为无开镜、无射击环境。后坐力和开镜参数可导入查看。")
        detail.setWordWrap(True)
        self.advanced.addRow(detail)
        self.expanded = QCheckBox("预览动态展开")
        layout.addWidget(self.expanded)
        self.preview = CrosshairPreview(self.settings, self.expanded)
        layout.addWidget(self.preview)
        self.expanded.toggled.connect(self.preview.update)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("应用")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.load_settings(settings)

    def add_field(self, form, name, title, bounds=None, choices=None):
        if choices:
            widget = QComboBox()
            widget.addItems(choices)
            widget.currentIndexChanged.connect(self.refresh)
        elif bounds is None:
            widget = QCheckBox()
            widget.toggled.connect(self.refresh)
        else:
            widget = QDoubleSpinBox() if isinstance(bounds[0], float) else QSpinBox()
            if isinstance(widget, QDoubleSpinBox):
                widget.setDecimals(2)
                widget.setSingleStep(.01)
            widget.setRange(*bounds)
            widget.valueChanged.connect(self.refresh)
        self.controls[name] = widget
        form.addRow(title, widget)

    def load_settings(self, settings):
        for name, widget in self.controls.items():
            value = getattr(settings, name)
            widget.blockSignals(True)
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(value)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, QPushButton):
                self.colors[name] = value
                widget.setText(" / ".join(str(channel) for channel in value))
            else:
                widget.setValue(value)
            widget.blockSignals(False)
        self.refresh()

    def settings(self) -> Crosshair:
        values = dict(self.colors)
        for name, widget in self.controls.items():
            if isinstance(widget, QComboBox):
                values[name] = widget.currentIndex()
            elif isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif not isinstance(widget, QPushButton):
                values[name] = widget.value()
        return Crosshair(**values)

    def refresh(self) -> None:
        settings = self.settings()
        style = settings.style
        for name, visible in (
            ("length", style in LENGTH_STYLES), ("gap", style in GAP_STYLES), ("dot", style != 6),
            ("t_style", style in LENGTH_STYLES), ("outline_color", settings.outline_mode != 0),
        ):
            self.basic.setRowVisible(self.controls[name], visible)
        for name, visible in (
            ("spread_limit", style in SPREAD_STYLES), ("split_ratio", style in (2, 9)),
            ("split_distance", style == 2), ("inner_alpha", style == 2), ("outer_alpha", style == 2),
        ):
            self.advanced.setRowVisible(self.controls[name], visible)
        self.expanded.setVisible(style in ANIMATED_STYLES)
        self.preview.update()

    def pick_color(self, name) -> None:
        color = QColorDialog.getColor(QColor(*self.colors[name]), self, "颜色与透明度",
                                      QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.colors[name] = color.getRgb()
            self.controls[name].setText(" / ".join(str(channel) for channel in self.colors[name]))
            self.refresh()

    def import_code(self) -> None:
        try:
            settings = decode_share_code(self.share.text())
        except ValueError as error:
            self.message.setText(str(error))
        else:
            self.load_settings(settings)
            self.message.setText("已载入分享码。点击「应用」用于测试。")
