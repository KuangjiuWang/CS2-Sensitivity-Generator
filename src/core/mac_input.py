"""macOS foreground relative input backed by the Game Controller framework."""
from ctypes import CDLL, c_int32, c_uint32
from math import isfinite
from platform import machine

from AppKit import NSApplicationWillResignActiveNotification
from Foundation import NSNotificationCenter, NSOperationQueue
from GameController import GCMouse, GCMouseDidConnectNotification, GCMouseDidDisconnectNotification
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

CORE_GRAPHICS = "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"


class RawMouseInput(QObject):
    deltas = Signal(int, float, float)
    pressed = Signal(int)

    def __init__(self, on_move, *, on_left_down=None):
        super().__init__()
        self.on_move, self.on_left_down = on_move, on_left_down
        self.registered = False
        self.locked = False
        self.window = None
        self.generation = 0
        self.profiles = {}
        self.observers = []
        self.center = NSNotificationCenter.defaultCenter()
        self.graphics = CDLL(CORE_GRAPHICS)
        self.associate = self.graphics.CGAssociateMouseAndMouseCursorPosition
        self.associate.argtypes = [c_uint32 if machine() == "x86_64" else c_int32]
        self.associate.restype = c_int32
        self.deltas.connect(self._deliver_motion, Qt.ConnectionType.QueuedConnection)
        self.pressed.connect(self._deliver_press, Qt.ConnectionType.QueuedConnection)

    def start(self, hwnd: int, *, confine_cursor: bool = True) -> None:
        if self.registered:
            return
        window = QApplication.activeWindow()
        if window is None or int(window.winId()) != hwnd:
            raise OSError("目标窗口尚未获得焦点。")
        self.window = window
        self.generation += 1
        self.registered = True
        try:
            queue = NSOperationQueue.mainQueue()
            self.observers.append(self.center.addObserverForName_object_queue_usingBlock_(
                GCMouseDidConnectNotification, None, queue, lambda note: self._attach(note.object())))
            self.observers.append(self.center.addObserverForName_object_queue_usingBlock_(
                GCMouseDidDisconnectNotification, None, queue, lambda note: self._detach(note.object())))
            for mouse in GCMouse.mice():
                self._attach(mouse)
            if not self.profiles:
                raise OSError("macOS 未检测到兼容的鼠标。请连接实体鼠标后重试。")
            if confine_cursor:
                self.observers.append(self.center.addObserverForName_object_queue_usingBlock_(
                    NSApplicationWillResignActiveNotification, None, None,
                    lambda note: self._restore_cursor()))
                QCursor.setPos(window.mapToGlobal(window.rect().center()))
                result = self.associate(0)
                if result:
                    raise OSError(f"macOS 无法锁定鼠标指针（{result}）。")
                self.locked = True
        except Exception as error:
            self.stop()
            if isinstance(error, OSError):
                raise
            raise OSError(f"macOS 鼠标初始化失败：{error}") from error

    def _attach(self, mouse) -> None:
        if not self.registered or mouse in self.profiles:
            return
        profile = mouse.mouseInput()
        if profile is None:
            return
        generation = self.generation
        self.profiles[mouse] = profile
        profile.setMouseMovedHandler_(lambda profile, dx, dy: self.deltas.emit(generation, dx, -dy))
        if self.on_left_down is not None:
            def button_changed(button, value, pressed):
                if pressed:
                    self.pressed.emit(generation)
            profile.leftButton().setPressedChangedHandler_(button_changed)

    def _detach(self, mouse) -> None:
        profile = self.profiles.pop(mouse, None)
        if profile is not None:
            profile.setMouseMovedHandler_(None)
            if self.on_left_down is not None:
                profile.leftButton().setPressedChangedHandler_(None)

    def stop(self) -> None:
        self.registered = False
        self.window = None
        try:
            result = self._restore_cursor()
            if result:
                raise OSError(f"macOS 无法恢复鼠标指针（{result}）。")
        finally:
            for token in self.observers:
                self.center.removeObserver_(token)
            self.observers.clear()
            for mouse in tuple(self.profiles):
                self._detach(mouse)

    def _restore_cursor(self) -> int:
        if not self.locked:
            return 0
        result = self.associate(1)
        self.locked = result != 0
        return result

    def _is_current(self, generation: int) -> bool:
        return (self.registered and generation == self.generation
                and self.window is not None and self.window.isActiveWindow())

    @Slot(int, float, float)
    def _deliver_motion(self, generation: int, dx: float, dy: float) -> None:
        if self._is_current(generation) and (dx or dy) and isfinite(dx) and isfinite(dy):
            self.on_move(dx, dy)

    @Slot(int)
    def _deliver_press(self, generation: int) -> None:
        if self._is_current(generation) and self.on_left_down is not None:
            self.on_left_down()
