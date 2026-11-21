"""Guided DPI measurement using the same foreground Raw Input as the arena."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from core.dpi_measurement import DpiMeasurement
from core.raw_input import RawMouseInput


class DpiDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("检测鼠标 DPI")
        self.setMinimumWidth(460)
        self.measurement = None
        self.measured_dpi = None
        self.raw = RawMouseInput(self.record_delta)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        instructions = QLabel("在鼠标垫旁用尺子标出一段水平距离。将鼠标同一位置从起点滑到终点，"
                              "保持鼠标朝向，途中别抬起或折返。")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        self.distance = QDoubleSpinBox()
        self.distance.setDecimals(1)
        self.distance.setRange(2, 50)
        self.distance.setValue(10)
        self.distance.setSuffix(" cm")
        form = QFormLayout()
        form.addRow("实际滑动距离", self.distance)
        layout.addLayout(form)
        self.status = QLabel("握好鼠标放在起点，按空格开始，到终点停稳后再按空格。")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        actions = QHBoxLayout()
        self.start_button = QPushButton("开始测量")
        self.start_button.clicked.connect(self.toggle_measurement)
        self.apply_button = QPushButton("填入 DPI")
        self.apply_button.setObjectName("primary")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        for button in (self.start_button, self.apply_button, cancel):
            button.setAutoDefault(False)
            actions.addWidget(button)
        layout.addLayout(actions)

        for widget in (self, *self.findChildren(QWidget)):
            widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space:
            if not event.isAutoRepeat():
                self.toggle_measurement()
            return True
        return super().eventFilter(watched, event)

    def toggle_measurement(self) -> None:
        if self.measurement is not None:
            measurement = self.measurement
            if self.release_measurement():
                try:
                    self.measured_dpi = measurement.estimate()
                except ValueError as error:
                    self.status.setText(str(error))
                else:
                    self.status.setText(f"测得约 {self.measured_dpi} DPI。点「填入 DPI」应用结果。")
                    self.apply_button.setEnabled(True)
            return

        self.distance.interpretText()
        self.measured_dpi = None
        self.apply_button.setEnabled(False)
        try:
            self.raw.start(int(self.winId()), confine_cursor=False)
        except OSError as error:
            self.status.setText(f"无法启动鼠标检测：{error}")
            return
        self.measurement = DpiMeasurement(self.distance.value())
        self.distance.setEnabled(False)
        self.start_button.setEnabled(False)
        self.status.setText("正在记录。水平滑到终点，停稳后按空格结束。")

    def record_delta(self, dx: int, dy: int) -> None:
        if self.measurement is not None:
            self.measurement.add(dx, dy)

    def release_measurement(self) -> bool:
        self.measurement = None
        self.distance.setEnabled(True)
        self.start_button.setEnabled(True)
        self.start_button.setText("重新测量")
        try:
            self.raw.stop()
        except OSError as error:
            self.status.setText(f"无法结束鼠标检测：{error}")
            return False
        return True

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if (event.type() == QEvent.Type.ActivationChange and self.measurement is not None
                and not self.isActiveWindow() and self.release_measurement()):
            self.status.setText("窗口失去焦点，本次测量已取消。请从起点重新测量。")

    def done(self, result: int) -> None:
        if self.measurement is not None or self.raw.registered:
            self.release_measurement()
        super().done(result)
