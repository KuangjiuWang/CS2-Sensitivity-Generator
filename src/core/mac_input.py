"""Foreground macOS relative mouse input."""
from collections import deque
from ctypes import CDLL, c_int32, c_uint32
from math import isfinite
from platform import machine
from threading import Lock
from time import perf_counter

from AppKit import (
    NSApplicationWillResignActiveNotification, NSEvent, NSEventMaskLeftMouseDown,
    NSEventMaskLeftMouseDragged, NSEventMaskMouseMoved, NSEventMaskOtherMouseDragged,
    NSEventMaskRightMouseDragged, NSEventTypeLeftMouseDown,
)
from Foundation import NSNotificationCenter, NSOperationQueue, NSProcessInfo
from GameController import GCMouse, GCMouseDidConnectNotification, GCMouseDidDisconnectNotification
from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

CORE_GRAPHICS = "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
APPKIT_MASK = (NSEventMaskMouseMoved | NSEventMaskLeftMouseDragged | NSEventMaskRightMouseDragged
               | NSEventMaskOtherMouseDragged | NSEventMaskLeftMouseDown)


class RawMouseInput(QObject):
    ready = Signal()

    def __init__(self, on_move, *, on_left_down=None, timestamped=False):
        super().__init__()
        self.on_move, self.on_left_down = on_move, on_left_down
        self.timestamped = timestamped
        self.packets = deque()
        self.packet_lock = Lock()
        self.device = None
        self.capture_error = ""
        self.registered = False
        self.locked = False
        self.window = None
        self.generation = 0
        self.monitor = None
        self.source = None
        self.pending_delta = None
        self.fallback_timer = QTimer(self, singleShot=True, interval=250)
        self.fallback_timer.timeout.connect(self._select_compatibility)
        self.profiles = {}
        self.observers = []
        self.center = NSNotificationCenter.defaultCenter()
        self.graphics = CDLL(CORE_GRAPHICS)
        self.associate = self.graphics.CGAssociateMouseAndMouseCursorPosition
        self.associate.argtypes = [c_uint32 if machine() == "x86_64" else c_int32]
        self.associate.restype = c_int32
        self.ready.connect(self.drain, Qt.ConnectionType.QueuedConnection)

    @property
    def compatibility_mode(self) -> bool:
        return self.source == "appkit"

    @property
    def input_mode(self) -> str:
        return "mac_compat" if self.compatibility_mode else "mac_raw"

    def start(self, hwnd: int, *, confine_cursor: bool = True) -> None:
        if self.registered:
            return
        window = QApplication.activeWindow()
        if window is None or int(window.winId()) != hwnd:
            raise OSError("目标窗口尚未获得焦点。")
        self.window = window
        self.generation += 1
        self.registered = True
        self.device = None
        self.capture_error = ""
        self.source = None if confine_cursor else "raw"
        try:
            queue = NSOperationQueue.mainQueue()
            self.observers.append(self.center.addObserverForName_object_queue_usingBlock_(
                GCMouseDidConnectNotification, None, queue, lambda note: self._attach(note.object())))
            self.observers.append(self.center.addObserverForName_object_queue_usingBlock_(
                GCMouseDidDisconnectNotification, None, queue, lambda note: self._detach(note.object())))
            for mouse in GCMouse.mice():
                self._attach(mouse)
            if not self.profiles and not confine_cursor:
                raise OSError("macOS 未检测到兼容的鼠标。请连接实体鼠标后重试。")
            if confine_cursor:
                self.observers.append(self.center.addObserverForName_object_queue_usingBlock_(
                    NSApplicationWillResignActiveNotification, None, None,
                    lambda note: self._restore_cursor()))
                generation = self.generation
                self.monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                    APPKIT_MASK, lambda event: self._appkit_event(generation, event))
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
        profile.setMouseMovedHandler_(lambda profile, dx, dy: self._enqueue(generation, mouse, (dx, -dy)))
        if self.on_left_down is not None:
            def button_changed(button, value, pressed):
                if pressed:
                    self._enqueue(generation, mouse, None)
            profile.leftButton().setPressedChangedHandler_(button_changed)

    def _detach(self, mouse) -> None:
        profile = self.profiles.pop(mouse, None)
        if profile is not None:
            if self.registered and self.source == "raw" and (
                    mouse == self.device or (self.device is None and not self.profiles)):
                self.capture_error = "当前鼠标已断开，本轮数据已作废。请重新连接后重试。"
            profile.setMouseMovedHandler_(None)
            if self.on_left_down is not None:
                profile.leftButton().setPressedChangedHandler_(None)

    def stop(self) -> None:
        self.registered = False
        with self.packet_lock:
            self.packets.clear()
        self.window = None
        self.fallback_timer.stop()
        self.pending_delta = None
        try:
            result = self._restore_cursor()
            if result:
                raise OSError(f"macOS 无法恢复鼠标指针（{result}）。")
        finally:
            if self.monitor is not None:
                NSEvent.removeMonitor_(self.monitor)
                self.monitor = None
            for token in self.observers:
                self.center.removeObserver_(token)
            self.observers.clear()
            for mouse in tuple(self.profiles):
                self._detach(mouse)

    def _lock_cursor(self) -> None:
        if self.associate(0) == 0:
            self.locked = True
            QCursor.setPos(self.window.mapToGlobal(self.window.rect().center()))

    def _appkit_event(self, generation, event):
        if not self._is_current(generation) or self.source == "raw":
            return event
        if event.type() == NSEventTypeLeftMouseDown:
            if self.compatibility_mode and self.on_left_down is not None:
                self._press(self._appkit_time(event))
                return None
            return event
        dx, dy = event.deltaX(), event.deltaY()
        if not ((dx or dy) and isfinite(dx) and isfinite(dy)):
            return event
        if self.compatibility_mode:
            self._move(dx, dy, self._appkit_time(event))
        else:
            self.pending_delta = dx, dy, self._appkit_time(event)
            if not self.profiles:
                self._select_compatibility()
            elif not self.fallback_timer.isActive():
                self.fallback_timer.start()
        return event

    def _select_compatibility(self) -> None:
        if self.source is None and self.pending_delta is not None and self._is_current(self.generation):
            dx, dy, stamp = self.pending_delta
            self.pending_delta = None
            self.source = "appkit"
            self._lock_cursor()
            self._move(dx, dy, stamp)

    @staticmethod
    def _appkit_time(event) -> float:
        age = NSProcessInfo.processInfo().systemUptime() - event.timestamp()
        return perf_counter() - max(0., age)

    def _restore_cursor(self) -> int:
        if not self.locked:
            return 0
        result = self.associate(1)
        self.locked = result != 0
        return result

    def _is_current(self, generation: int) -> bool:
        return (self.registered and not self.capture_error and generation == self.generation
                and self.window is not None and self.window.isActiveWindow())

    def _enqueue(self, generation, mouse, delta) -> None:
        with self.packet_lock:
            if not self.registered or generation != self.generation or self.compatibility_mode:
                return
            wake = not self.packets
            self.packets.append((perf_counter(), generation, mouse, delta))
        if wake:
            self.ready.emit()

    @Slot()
    def drain(self) -> None:
        with self.packet_lock:
            packets, self.packets = self.packets, deque()
        for stamp, generation, mouse, delta in packets:
            if (self.compatibility_mode or not self._is_current(generation) or mouse not in self.profiles
                    or (self.device is not None and mouse != self.device)):
                continue
            if delta is None:
                if self.device is not None and self.on_left_down is not None:
                    self._press(stamp)
                continue
            dx, dy = delta
            if not ((dx or dy) and isfinite(dx) and isfinite(dy)):
                continue
            self.device = mouse
            if self.source is None:
                self.source = "raw"
                self.fallback_timer.stop()
                self.pending_delta = None
                self._lock_cursor()
            self._move(dx, dy, stamp)

    def _move(self, dx, dy, stamp) -> None:
        if self.timestamped:
            self.on_move(dx, dy, stamp)
        else:
            self.on_move(dx, dy)

    def _press(self, stamp) -> None:
        if self.timestamped:
            self.on_left_down(stamp)
        else:
            self.on_left_down()
