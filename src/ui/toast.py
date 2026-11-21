"""Non-blocking, animated feedback for local actions."""
from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QTimer, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setWordWrap(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.fade = QPropertyAnimation(self.effect, b"opacity", self)
        self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.finished.connect(self.finish_animation)
        self.timer = QTimer(self, singleShot=True, interval=2900)
        self.timer.timeout.connect(self.fade_out)
        parent.installEventFilter(self)
        self.hide()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize and self.isVisible():
            self.place()
        return super().eventFilter(watched, event)

    def place(self):
        self.move(self.parentWidget().width() - self.width() - 24,
                  self.parentWidget().height() - self.height() - 20)

    def notify(self, message: str):
        self.fade.stop()
        self.setText(message)
        self.setAccessibleName(message)
        self.setFixedWidth(min(390, self.parentWidget().width() - 48))
        self.setFixedHeight(max(42, self.heightForWidth(self.width())))
        self.place()
        self.raise_()
        self.show()
        self.animate(0, 1, 190)
        self.timer.start()

    def animate(self, start: float, end: float, duration: int):
        self.fade.setDuration(duration)
        self.fade.setStartValue(start)
        self.fade.setEndValue(end)
        self.fade.start()

    def fade_out(self):
        self.animate(1, 0, 220)

    def finish_animation(self):
        if self.effect.opacity() == 0:
            self.hide()
