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
        self.native_events = Mock()
        frameworks = {
            "AppKit": SimpleNamespace(
                NSApplicationWillResignActiveNotification="resign", NSEvent=self.native_events,
                NSEventMaskLeftMouseDown=2, NSEventMaskMouseMoved=32, NSEventMaskLeftMouseDragged=64,
                NSEventMaskRightMouseDragged=128, NSEventMaskOtherMouseDragged=1 << 27,
                NSEventTypeLeftMouseDown=1,
            ),
            "Foundation": SimpleNamespace(
                NSNotificationCenter=SimpleNamespace(defaultCenter=lambda: self.center),
                NSOperationQueue=SimpleNamespace(mainQueue=lambda: object()),
                NSProcessInfo=SimpleNamespace(processInfo=lambda: SimpleNamespace(systemUptime=lambda: 100.0)),
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
        self.backend = backend
        self.events = Mock()
        self.raw = backend.RawMouseInput(self.events.move, on_left_down=self.events.click)
        self.addCleanup(self.raw.stop)

    def local_event(self, event_type, dx=0, dy=0):
        handler = self.native_events.addLocalMonitorForEventsMatchingMask_handler_.call_args.args[1]
        event = SimpleNamespace(type=lambda: event_type, deltaX=lambda: dx, deltaY=lambda: dy,
                                timestamp=lambda: 100.0)
        return handler(event)

    def test_relative_motion_and_left_press_are_delivered_in_order(self):
        self.raw.start(42)
        self.associate.assert_not_called()
        self.local_event(5, 5, 6)
        motion = self.profile.setMouseMovedHandler_.call_args.args[0]
        button = self.button.setPressedChangedHandler_.call_args.args[0]
        motion(self.profile, 2.5, -1.25)
        button(self.button, 1.0, True)
        button(self.button, 0.0, False)
        self.assertEqual(self.events.mock_calls, [])
        self.app.processEvents()
        self.assertEqual(self.events.mock_calls, [call.move(2.5, 1.25), call.click()])
        self.assertFalse(self.raw.compatibility_mode)
        self.assertFalse(self.raw.fallback_timer.isActive())
        resign = self.center.addObserverForName_object_queue_usingBlock_.call_args.args[3]
        resign(None)
        self.assertEqual(self.associate.call_args_list, [call(0), call(1)])
        self.raw.stop()
        self.assertEqual(self.associate.call_args_list, [call(0), call(1)])
        self.profile.setMouseMovedHandler_.assert_called_with(None)
        self.button.setPressedChangedHandler_.assert_called_with(None)
        self.assertEqual(self.center.removeObserver_.call_count, 3)
        self.native_events.removeMonitor_.assert_called_once()

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

    def test_dpi_capture_without_raw_mouse_cleans_up_and_can_retry(self):
        mice = self.mice.return_value
        self.mice.return_value = []
        with self.assertRaises(OSError):
            self.raw.start(42, confine_cursor=False)
        self.assertFalse(self.raw.registered)
        self.associate.assert_not_called()
        self.assertEqual(self.center.removeObserver_.call_count, 2)
        self.mice.return_value = mice
        self.raw.start(42)
        self.assertTrue(self.raw.registered)

    def test_trackpad_motion_can_start_training_without_a_raw_mouse(self):
        self.mice.return_value = []
        self.raw.start(42)
        self.associate.assert_not_called()
        self.local_event(5, 3.25, -2)
        self.assertTrue(self.raw.compatibility_mode)
        self.assertIsNone(self.local_event(1))
        self.assertEqual(self.events.mock_calls, [call.move(3.25, -2), call.click()])
        self.raw.stop()
        self.assertEqual(self.associate.call_args_list, [call(0), call(1)])

    def test_silent_raw_device_falls_back_without_double_counting(self):
        self.raw.start(42)
        self.local_event(5, 4, 6)
        self.associate.assert_not_called()
        self.assertTrue(self.raw.fallback_timer.isActive())
        self.raw.fallback_timer.stop()
        self.raw.fallback_timer.timeout.emit()
        motion = self.profile.setMouseMovedHandler_.call_args.args[0]
        click = self.button.setPressedChangedHandler_.call_args.args[0]
        motion(self.profile, 2, -1)
        click(self.button, 1, True)
        self.app.processEvents()
        self.local_event(5, 1, 2)
        self.assertEqual(self.events.mock_calls, [call.move(4, 6), call.move(1, 2)])

    def test_capture_time_is_retained_until_pending_events_are_drained(self):
        self.raw.timestamped = True
        self.raw.start(42)
        motion = self.profile.setMouseMovedHandler_.call_args.args[0]
        click = self.button.setPressedChangedHandler_.call_args.args[0]
        with patch.object(self.backend, "perf_counter", side_effect=[17.990, 17.995]):
            motion(self.profile, 1, 2)
            click(self.button, 1, True)
        self.raw.drain()
        self.assertEqual(self.events.mock_calls, [call.move(1, -2, 17.990), call.click(17.995)])

    def test_raw_capture_sticks_to_first_moving_mouse_and_flags_disconnect(self):
        first = self.mice.return_value[0]
        other = Mock()
        self.mice.return_value = [first, other]
        self.raw.start(42, confine_cursor=False)
        motion = self.profile.setMouseMovedHandler_.call_args.args[0]
        other_profile = other.mouseInput.return_value
        other_motion = other_profile.setMouseMovedHandler_.call_args.args[0]
        motion(self.profile, 3150, 0)
        other_motion(other_profile, 300, 0)
        self.raw.drain()
        self.assertEqual(self.events.mock_calls, [call.move(3150, 0)])
        self.raw._detach(other)
        self.assertFalse(self.raw.capture_error)
        self.raw._detach(first)
        self.assertIn("已断开", self.raw.capture_error)
