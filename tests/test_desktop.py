"""Check native window activation with mocks; never move focus or send input."""
import ctypes
import unittest
from ctypes import wintypes
from unittest.mock import ANY, Mock, call, patch

from staffbot import desktop
from staffbot.engine import FocusLost, Target


class NativeActivationTests(unittest.TestCase):
    def setUp(self):
        self.platform = patch.object(desktop.sys, "platform", "win32")
        self.platform.start()
        self.addCleanup(self.platform.stop)
        sleep = patch("staffbot.desktop.time.sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)
        self.focus = desktop.NativeFocus.__new__(desktop.NativeFocus)
        self.user32 = Mock()
        self.focus.user32 = self.user32
        self.user32.IsWindow.return_value = True
        self.user32.IsIconic.return_value = False
        self.user32.GetForegroundWindow.return_value = 111
        self.user32.SetForegroundWindow.return_value = True
        self.target = Target(120, 240, "4321", "Captured destination")

    def test_already_active_window_needs_no_activation(self):
        self.user32.GetForegroundWindow.return_value = 4321
        self.focus.activate(self.target)
        self.user32.IsWindow.assert_called_once_with(4321)
        self.user32.IsIconic.assert_not_called()
        self.user32.ShowWindow.assert_not_called()
        self.user32.SetForegroundWindow.assert_not_called()
        self.sleep.assert_not_called()

    def test_requests_only_the_captured_handle(self):
        self.user32.GetForegroundWindow.side_effect = [111, 4321]
        self.focus.activate(self.target)
        self.user32.SetForegroundWindow.assert_called_once_with(4321)
        self.user32.ShowWindow.assert_not_called()
        self.sleep.assert_not_called()

    def test_large_window_handle_is_not_truncated(self):
        handle = 0x1000010FF
        self.user32.GetForegroundWindow.side_effect = [111, handle]
        self.focus.activate(Target(120, 240, str(handle), "Captured destination"))
        self.user32.SetForegroundWindow.assert_called_once_with(handle)

    def test_minimized_window_is_restored_before_activation(self):
        self.user32.IsIconic.return_value = True
        self.user32.ShowWindow.return_value = False  # Previous visibility is irrelevant.
        self.user32.GetForegroundWindow.side_effect = [111, 4321]
        self.focus.activate(self.target)
        calls = self.user32.mock_calls
        self.assertLess(calls.index(call.ShowWindow(4321, 9)),
                        calls.index(call.SetForegroundWindow(4321)))
        self.user32.ShowWindow.assert_called_once_with(4321, 9)

    def test_closed_window_is_rejected_without_activation(self):
        self.user32.IsWindow.return_value = False
        with self.assertRaisesRegex(FocusLost, "Change destination.*F8.*F9"):
            self.focus.activate(self.target)
        self.user32.GetForegroundWindow.assert_not_called()
        self.user32.ShowWindow.assert_not_called()
        self.user32.SetForegroundWindow.assert_not_called()

    def test_invalid_window_key_is_rejected_without_native_calls(self):
        for key in ("", "not-a-handle", "0", "-1"):
            with self.subTest(key=key):
                self.user32.reset_mock()
                with self.assertRaisesRegex(FocusLost, "no longer available"):
                    self.focus.activate(Target(120, 240, key, "Captured destination"))
                self.assertEqual(self.user32.mock_calls, [])

    def test_brief_foreground_transition_is_verified(self):
        self.user32.GetForegroundWindow.side_effect = [111, 111, 111, 4321]
        self.focus.activate(self.target)
        self.user32.SetForegroundWindow.assert_called_once_with(4321)
        self.assertEqual(self.sleep.call_args_list, [call(0.05), call(0.05)])

    def test_success_return_without_matching_foreground_is_rejected(self):
        self.user32.SetForegroundWindow.return_value = True
        with self.assertRaisesRegex(FocusLost, "Click the captured window and press F9"):
            self.focus.activate(self.target)
        self.user32.SetForegroundWindow.assert_called_once_with(4321)
        self.assertEqual(self.sleep.call_count, 5)

    def test_denied_activation_does_not_retry_or_force_focus(self):
        self.user32.SetForegroundWindow.return_value = False
        with self.assertRaisesRegex(FocusLost, "Click the captured window and press F9"):
            self.focus.activate(self.target)
        self.user32.SetForegroundWindow.assert_called_once_with(4321)
        self.user32.ShowWindow.assert_not_called()
        self.assertEqual(self.sleep.call_args_list, [call(0.05)] * 5)
        self.assertEqual({item[0] for item in self.user32.mock_calls},
                         {"IsWindow", "IsIconic", "GetForegroundWindow", "SetForegroundWindow"})

    def test_actual_foreground_is_authoritative_if_request_returns_zero(self):
        self.user32.SetForegroundWindow.return_value = False
        self.user32.GetForegroundWindow.side_effect = [111, 4321]
        self.focus.activate(self.target)
        self.user32.SetForegroundWindow.assert_called_once_with(4321)

    def test_window_closing_during_activation_is_rejected(self):
        self.user32.IsWindow.side_effect = [True, False]
        with self.assertRaisesRegex(FocusLost, "no longer available"):
            self.focus.activate(self.target)
        self.user32.SetForegroundWindow.assert_called_once_with(4321)
        self.sleep.assert_not_called()

    def _set_native_pid(self, pid):
        def process(handle, result):
            result._obj.value = pid
            return 123
        self.user32.GetWindowThreadProcessId.side_effect = process

    def test_matching_process_identity_allows_activation(self):
        self._set_native_pid(5678)
        self.user32.GetForegroundWindow.side_effect = [111, 4321]
        self.focus.activate(Target(120, 240, "4321", "Captured destination", pid=5678))
        self.user32.SetForegroundWindow.assert_called_once_with(4321)
        self.assertEqual(self.user32.GetWindowThreadProcessId.call_args_list,
                         [call(4321, ANY), call(4321, ANY)])

    def test_recycled_handle_with_different_process_is_rejected_before_activation(self):
        self._set_native_pid(8765)
        with self.assertRaisesRegex(FocusLost, "different process.*Change destination.*F8"):
            self.focus.activate(Target(120, 240, "4321", "Captured destination", pid=5678))
        self.user32.GetForegroundWindow.assert_not_called()
        self.user32.ShowWindow.assert_not_called()
        self.user32.SetForegroundWindow.assert_not_called()

    def test_unreadable_process_identity_is_rejected(self):
        self.user32.GetWindowThreadProcessId.return_value = 0
        with self.assertRaisesRegex(FocusLost, "Change destination"):
            self.focus.activate(Target(120, 240, "4321", "Captured destination", pid=5678))
        self.user32.SetForegroundWindow.assert_not_called()

    def test_process_change_during_activation_is_rejected(self):
        pids = iter((5678, 8765))
        def process(handle, result):
            result._obj.value = next(pids)
            return 123
        self.user32.GetWindowThreadProcessId.side_effect = process
        with self.assertRaisesRegex(FocusLost, "different process"):
            self.focus.activate(Target(120, 240, "4321", "Captured destination", pid=5678))
        self.user32.SetForegroundWindow.assert_called_once_with(4321)
        self.sleep.assert_not_called()

    def test_other_platforms_keep_manual_activation(self):
        for platform in ("darwin", "linux"):
            with self.subTest(platform=platform), patch.object(desktop.sys, "platform", platform):
                self.user32.reset_mock()
                self.focus.activate(self.target)
                self.assertEqual(self.user32.mock_calls, [])
                self.sleep.assert_not_called()

    def test_backend_delegates_without_creating_input_controllers(self):
        backend = desktop.PynputBackend.__new__(desktop.PynputBackend)
        backend.focus = Mock()
        backend.activate(self.target)
        backend.focus.activate.assert_called_once_with(self.target)

    def test_capture_preserves_native_process_identity(self):
        backend = desktop.PynputBackend.__new__(desktop.PynputBackend)
        backend.focus = Mock()
        backend.focus.active.return_value = desktop.Focus("4321", "Captured destination", 5678,
                                                          (0, 0, 300, 400))
        backend.mouse_position = Mock(return_value=(120, 240))
        with patch("staffbot.desktop.os.getpid", return_value=9999):
            captured = backend.capture()
        self.assertEqual(captured, Target(120, 240, "4321", "Captured destination", pid=5678))

    def test_focus_matches_checks_handle_and_optional_process_identity(self):
        backend = desktop.PynputBackend.__new__(desktop.PynputBackend)
        backend.focus = Mock()
        for handle, pid, captured_pid, expected in (("4321", 5678, 5678, True),
                                                     ("4321", 8765, 5678, False),
                                                     ("111", 5678, 5678, False),
                                                     ("4321", 8765, None, True)):
            with self.subTest(handle=handle, pid=pid, captured_pid=captured_pid):
                backend.focus.active.return_value = desktop.Focus(handle, "Destination", pid)
                target = Target(120, 240, "4321", "Captured destination", pid=captured_pid)
                self.assertEqual(backend.focus_matches(target), expected)

    def test_native_api_signatures_preserve_pointer_sized_handles(self):
        with patch.object(desktop.ctypes, "WinDLL", create=True, return_value=self.user32) as library:
            desktop.NativeFocus()
        library.assert_called_once_with("user32", use_last_error=True)
        self.assertEqual(self.user32.GetForegroundWindow.argtypes, [])
        self.assertIs(self.user32.GetForegroundWindow.restype, wintypes.HWND)
        for name in ("IsWindow", "IsIconic", "SetForegroundWindow"):
            self.assertEqual(getattr(self.user32, name).argtypes, [wintypes.HWND])
            self.assertIs(getattr(self.user32, name).restype, wintypes.BOOL)
        self.assertEqual(self.user32.ShowWindow.argtypes, [wintypes.HWND, ctypes.c_int])
        self.assertIs(self.user32.ShowWindow.restype, wintypes.BOOL)
        self.assertEqual(self.user32.mock_calls, [])


if __name__ == "__main__":
    unittest.main()
