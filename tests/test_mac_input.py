from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from PySide6.QtCore import QCoreApplication


class MacInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.button = Mock()
        self.profile = Mock()
        self.profile.leftButton.return_value = self.button
        mouse = Mock()
        mouse.mouseInput.return_value = self.profile
        self.mice = Mock(return_value=[mouse])
        self.center = Mock()
        self.associate = Mock(return_value=0)
        self.window = Mock()
        self.window.winId.return_value = 42
        self.window.isActiveWindow.return_value = True
        frameworks = {
            "AppKit": SimpleNamespace(NSApplicationWillResignActiveNotification="resign"),
            "Foundation": SimpleNamespace(
                NSNotificationCenter=SimpleNamespace(defaultCenter=lambda: self.center),
                NSOperationQueue=SimpleNamespace(mainQueue=lambda: object()),
            ),
            "GameController": SimpleNamespace(
                GCMouse=SimpleNamespace(mice=self.mice),
                GCMouseDidConnectNotification="connect",
                GCMouseDidDisconnectNotification="disconnect",
            ),
        }
        path = Path(__file__).resolve().parents[1] / "src" / "core" / "mac_input.py"
        spec = spec_from_file_location("mac_input_under_test", path)
        backend = module_from_spec(spec)
        with patch.dict(sys.modules, frameworks):
            spec.loader.exec_module(backend)
        backend.CDLL = Mock(return_value=SimpleNamespace(
            CGAssociateMouseAndMouseCursorPosition=self.associate))
        backend.QApplication = SimpleNamespace(activeWindow=lambda: self.window)
        backend.QCursor = Mock()
        self.events = Mock()
        self.raw = backend.RawMouseInput(self.events.move, on_left_down=self.events.click)
        self.addCleanup(self.raw.stop)

    def test_relative_motion_and_left_press_are_delivered_in_order(self):
        self.raw.start(42)
        motion = self.profile.setMouseMovedHandler_.call_args.args[0]
        button = self.button.setPressedChangedHandler_.call_args.args[0]
        motion(self.profile, 2.5, -1.25)
        button(self.button, 1.0, True)
        button(self.button, 0.0, False)
        self.assertEqual(self.events.mock_calls, [])
        self.app.processEvents()
        self.assertEqual(self.events.mock_calls, [call.move(2.5, 1.25), call.click()])
        resign = self.center.addObserverForName_object_queue_usingBlock_.call_args.args[3]
        resign(None)
        self.assertEqual(self.associate.call_args_list, [call(0), call(1)])
        self.raw.stop()
        self.assertEqual(self.associate.call_args_list, [call(0), call(1)])
        self.profile.setMouseMovedHandler_.assert_called_with(None)
        self.button.setPressedChangedHandler_.assert_called_with(None)
        self.assertEqual(self.center.removeObserver_.call_count, 3)

    def test_motion_from_stopped_capture_or_inactive_window_is_ignored(self):
        self.raw.start(42, confine_cursor=False)
        old_motion = self.profile.setMouseMovedHandler_.call_args.args[0]
        old_motion(self.profile, 1, 2)
        self.raw.stop()
        self.raw.start(42, confine_cursor=False)
        self.app.processEvents()
        self.window.isActiveWindow.return_value = False
        current_motion = self.profile.setMouseMovedHandler_.call_args.args[0]
        current_motion(self.profile, 3, 4)
        self.app.processEvents()
        self.assertEqual(self.events.mock_calls, [])
        self.associate.assert_not_called()

    def test_start_without_mouse_cleans_up_and_can_retry(self):
        mice = self.mice.return_value
        self.mice.return_value = []
        with self.assertRaises(OSError):
            self.raw.start(42)
        self.assertFalse(self.raw.registered)
        self.associate.assert_not_called()
        self.assertEqual(self.center.removeObserver_.call_count, 2)
        self.mice.return_value = mice
        self.raw.start(42)
        self.assertTrue(self.raw.registered)
