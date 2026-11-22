"""Foreground-only Win32 Raw Input. Qt mouse events never move the camera."""
import ctypes as C
import sys
from ctypes import wintypes as W

DPI_PER_MONITOR_V2 = C.c_void_p(-4)
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_REMOVE = 0x0001
MOUSE_MOVE_ABSOLUTE = 0x0001
RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
SUBCLASS_ID = 1


class RawInputDevice(C.Structure):
    _fields_ = [("usage_page", W.USHORT), ("usage", W.USHORT),
                ("flags", W.DWORD), ("target", W.HWND)]


class RawHeader(C.Structure):
    _fields_ = [("kind", W.DWORD), ("size", W.DWORD),
                ("device", W.HANDLE), ("wparam", W.WPARAM)]


class RawMouse(C.Structure):
    # The DWORD occupies the aligned button flags/data union.
    _fields_ = [("flags", W.USHORT), ("buttons", W.ULONG), ("raw_buttons", W.ULONG),
                ("dx", W.LONG), ("dy", W.LONG), ("extra", W.ULONG)]


class MousePacket(C.Structure):
    _fields_ = [("header", RawHeader), ("mouse", RawMouse)]


def enable_high_dpi() -> None:
    if sys.platform != "win32":
        raise OSError("此应用需要 Windows 10（1703 或更新）或 Windows 11。")
    user32 = C.WinDLL("user32", use_last_error=True)
    user32.SetProcessDpiAwarenessContext.argtypes = [C.c_void_p]
    user32.SetProcessDpiAwarenessContext.restype = W.BOOL
    if user32.SetProcessDpiAwarenessContext(DPI_PER_MONITOR_V2):
        return
    error = C.get_last_error()
    # An executable manifest may have already enabled this exact mode.
    user32.GetThreadDpiAwarenessContext.argtypes = []
    user32.GetThreadDpiAwarenessContext.restype = C.c_void_p
    user32.AreDpiAwarenessContextsEqual.argtypes = [C.c_void_p, C.c_void_p]
    user32.AreDpiAwarenessContextsEqual.restype = W.BOOL
    context = user32.GetThreadDpiAwarenessContext()
    if not user32.AreDpiAwarenessContextsEqual(context, DPI_PER_MONITOR_V2):
        raise C.WinError(error)


class RawMouseInput:
    def __init__(self, on_move, *, on_left_down=None) -> None:
        self.on_move = on_move
        self.on_left_down = on_left_down
        self.api = C.WinDLL("user32", use_last_error=True)
        self.controls = C.WinDLL("comctl32", use_last_error=True)
        subclass_proc = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM,
                                      C.c_size_t, C.c_size_t)
        self.window_proc = subclass_proc(self._window_proc)
        self.controls.SetWindowSubclass.argtypes = [W.HWND, subclass_proc, C.c_size_t, C.c_size_t]
        self.controls.SetWindowSubclass.restype = W.BOOL
        self.controls.RemoveWindowSubclass.argtypes = [W.HWND, subclass_proc, C.c_size_t]
        self.controls.RemoveWindowSubclass.restype = W.BOOL
        self.controls.DefSubclassProc.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
        self.controls.DefSubclassProc.restype = C.c_ssize_t
        self.api.RegisterRawInputDevices.argtypes = [C.POINTER(RawInputDevice), W.UINT, W.UINT]
        self.api.RegisterRawInputDevices.restype = W.BOOL
        self.api.GetRawInputData.argtypes = [W.HANDLE, W.UINT, C.c_void_p, C.POINTER(W.UINT), W.UINT]
        self.api.GetRawInputData.restype = W.UINT
        self.api.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
        self.api.DefWindowProcW.restype = C.c_ssize_t
        self.api.GetClientRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
        self.api.GetClientRect.restype = W.BOOL
        self.api.ClientToScreen.argtypes = [W.HWND, C.POINTER(W.POINT)]
        self.api.ClientToScreen.restype = W.BOOL
        self.api.ClipCursor.argtypes = [C.POINTER(W.RECT)]
        self.api.ClipCursor.restype = W.BOOL
        self.hwnd = None
        self.packet = MousePacket()
        self.clipped = False
        self.registered = False

    def _register(self, flags: int, hwnd: int | None) -> None:
        registration = RawInputDevice(1, 2, flags, hwnd)
        if not self.api.RegisterRawInputDevices(C.byref(registration), 1, C.sizeof(registration)):
            raise C.WinError(C.get_last_error())

    def start(self, hwnd: int, *, confine_cursor: bool = True) -> None:
        if not self.controls.SetWindowSubclass(hwnd, self.window_proc, SUBCLASS_ID, 0):
            raise OSError("无法安装测试窗口的 Win32 鼠标监听。")
        self.hwnd = hwnd
        try:
            self._register(0, hwnd)
            self.registered = True
            if not confine_cursor:
                return
            rect = W.RECT()
            if not self.api.GetClientRect(hwnd, C.byref(rect)):
                raise C.WinError(C.get_last_error())
            top_left = W.POINT(rect.left, rect.top)
            bottom_right = W.POINT(rect.right, rect.bottom)
            if not (self.api.ClientToScreen(hwnd, C.byref(top_left))
                    and self.api.ClientToScreen(hwnd, C.byref(bottom_right))):
                raise C.WinError(C.get_last_error())
            bounds = W.RECT(top_left.x, top_left.y, bottom_right.x, bottom_right.y)
            if not self.api.ClipCursor(C.byref(bounds)):
                raise C.WinError(C.get_last_error())
            self.clipped = True
        except OSError:
            self.stop()
            raise

    def stop(self) -> None:
        try:
            if self.clipped:
                self.api.ClipCursor(None)
                self.clipped = False
            if self.registered:
                self._register(RIDEV_REMOVE, None)
                self.registered = False
        finally:
            if self.hwnd is not None:
                self.controls.RemoveWindowSubclass(self.hwnd, self.window_proc, SUBCLASS_ID)
                self.hwnd = None

    def _window_proc(self, hwnd, message, wparam, lparam, subclass_id, ref_data) -> int:
        if message != WM_INPUT:
            return self.controls.DefSubclassProc(hwnd, message, wparam, lparam)
        size = W.UINT(C.sizeof(self.packet))
        read = self.api.GetRawInputData(lparam, RID_INPUT, C.byref(self.packet),
                                        C.byref(size), C.sizeof(RawHeader))
        if (wparam & 0xFF) == 0:
            self.api.DefWindowProcW(hwnd, message, wparam, lparam)
        mouse = self.packet.mouse
        if read != C.sizeof(self.packet) or self.packet.header.kind != 0:
            return 0
        pressed = mouse.buttons & RI_MOUSE_LEFT_BUTTON_DOWN
        if not mouse.flags & MOUSE_MOVE_ABSOLUTE and (mouse.dx or mouse.dy):
            self.on_move(mouse.dx, mouse.dy)
        if pressed and self.on_left_down is not None:
            self.on_left_down()
        return 0
