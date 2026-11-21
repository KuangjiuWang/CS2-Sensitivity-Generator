"""Exercise native message dispatch with a controlled RAWINPUT packet."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.raw_input import MOUSE_MOVE_ABSOLUTE, MousePacket, RawMouseInput, WM_INPUT


@unittest.skipUnless(sys.platform == "win32", "requires Win32 window messages")
class RawDispatchTests(unittest.TestCase):
    def test_relative_packets_reach_callback_via_native_window(self):
        received = []
        raw = RawMouseInput(lambda dx, dy: received.append((dx, dy)))
        api = raw.api
        api.CreateWindowExW.argtypes = [
            W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int, C.c_int, C.c_int,
            W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p,
        ]
        api.CreateWindowExW.restype = W.HWND
        api.DestroyWindow.argtypes = [W.HWND]
        api.DestroyWindow.restype = W.BOOL
        api.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
        api.SendMessageW.restype = C.c_ssize_t
        hwnd = api.CreateWindowExW(0, "STATIC", "Raw Input regression test", 0, 0, 0, 320, 240,
                                   None, None, None, None)
        self.assertTrue(hwnd, C.get_last_error())
        packet = MousePacket()
        packet.mouse.dx, packet.mouse.dy = 60, -15

        def read_packet(handle, command, destination, size, header_size):
            C.memmove(destination, C.byref(packet), C.sizeof(packet))
            return C.sizeof(packet)

        api.GetRawInputData = read_packet
        api.ClipCursor = lambda rect: True
        try:
            raw.start(hwnd)
            api.SendMessageW(hwnd, WM_INPUT, 1, 0)
            packet.mouse.flags = MOUSE_MOVE_ABSOLUTE
            api.SendMessageW(hwnd, WM_INPUT, 1, 0)
            raw.stop()
            packet.mouse.flags = 0
            api.SendMessageW(hwnd, WM_INPUT, 1, 0)
            self.assertEqual(received, [(60, -15)])
            self.assertFalse(raw.registered)
        finally:
            raw.stop()
            api.DestroyWindow(hwnd)
