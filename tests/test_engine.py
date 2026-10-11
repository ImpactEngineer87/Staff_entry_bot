import json
import tempfile
import threading
import unittest
from pathlib import Path

from staffbot.engine import EntryRunner, FocusLost, Journal, RunOptions, Stopped, Target
from staffbot.readers import Dataset, Record


class FakeDesktop:
    def __init__(self):
        self.clipboard = "previous clipboard"
        self.sent = []
        self.focus = True
        self.position = (100, 100)
        self.focus_after_paste = True
        self.cancel_after_paste = None
        self.activations = []
        self.focus_after_activate = None
        self.activation_error = None

    def activate(self, target):
        self.activations.append(target)
        if self.activation_error:
            raise self.activation_error
        if self.focus_after_activate is not None:
            self.focus = self.focus_after_activate

    def focus_matches(self, target):
        return self.focus

    def mouse_position(self):
        return self.position

    def click(self, x, y):
        self.sent.append(("click", x, y))

    def clipboard_get(self):
        return self.clipboard

    def clipboard_set(self, text):
        self.clipboard = text

    def paste(self):
        self.sent.append(("paste", self.clipboard))
        self.focus = self.focus_after_paste
        if self.cancel_after_paste:
            self.cancel_after_paste.set()

    def select_all(self):
        self.sent.append(("select_all",))

    def key(self, key):
        self.sent.append(("key", key))


class ImmediateEvent(threading.Event):
    # Avoid timing tests: preserve cancellation behavior while making waits immediate.
    def wait(self, timeout=None):
        return self.is_set()


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeDesktop()
        self.cancel = ImmediateEvent()
        self.runner = EntryRunner(self.backend, self.cancel)
        self.target = Target(123, 234, "target-window", "Practice")
        self.data = Dataset([Record("Line 1", ("001", "Mary Jane", "HR")),
                             Record("Line 2", ("002", "José García", "IT"))])

    def options(self, **changes):
        values = dict(countdown=0, field_delay=0, paste_delay=0.05, row_delay=0)
        values.update(changes)
        return RunOptions(**values)

    def test_one_record_default_no_save_keys(self):
        self.assertEqual(self.runner.run(self.data, self.target, self.options()), 1)
        self.assertEqual(self.backend.sent, [("click", 123, 234), ("paste", "001"), ("key", "tab"),
                                            ("paste", "Mary Jane"), ("key", "tab"), ("paste", "HR")])
        self.assertEqual(self.backend.clipboard, "previous clipboard")

    def test_start_activates_locked_target_before_countdown_and_input(self):
        self.backend.focus = False
        self.backend.focus_after_activate = True
        original_wait = self.cancel.wait

        def wait_after_activation(timeout=None):
            self.assertEqual(self.backend.activations, [self.target])
            self.assertTrue(self.backend.focus)
            return original_wait(timeout)

        self.cancel.wait = wait_after_activation
        self.assertEqual(self.runner.run(self.data, self.target, self.options(countdown=3)), 1)
        self.assertIs(self.backend.activations[0], self.target)

    def test_activation_refused_preserves_clipboard_and_sends_no_input(self):
        self.backend.activation_error = FocusLost("Click the captured window and press F9 to retry.")
        with self.assertRaisesRegex(FocusLost, "F9"):
            self.runner.run(self.data, self.target, self.options())
        self.assertEqual(self.backend.activations, [self.target])
        self.assertEqual(self.backend.sent, [])
        self.assertEqual(self.backend.clipboard, "previous clipboard")
        self.assertEqual(self.runner.pasted_rows, 0)

    def test_focus_loss_during_countdown_sends_no_input_or_reactivation(self):
        self.backend.focus_after_activate = True

        def lose_focus(timeout=None):
            self.backend.focus = False
            return False

        self.cancel.wait = lose_focus
        with self.assertRaises(FocusLost):
            self.runner.run(self.data, self.target, self.options(countdown=3))
        self.assertEqual(self.backend.sent, [])
        self.assertEqual(self.backend.activations, [self.target])

    def test_cancelled_start_does_not_activate_or_send_input(self):
        self.cancel.set()
        with self.assertRaises(Stopped):
            self.runner.run(self.data, self.target, self.options())
        self.assertEqual(self.backend.activations, [])
        self.assertEqual(self.backend.sent, [])

    def test_batch_tabs_save_keys_and_first_field_click(self):
        count = self.runner.run(self.data, self.target, self.options(
            row_limit=0, tab_counts=(1, 2), after_row=("tab", "enter")))
        self.assertEqual(count, 2)
        self.assertEqual(self.backend.sent.count(("click", 123, 234)), 2)
        self.assertEqual(self.backend.sent.count(("key", "tab")), 8)
        self.assertEqual(self.backend.sent.count(("key", "enter")), 2)

    def test_batch_requires_record_navigation(self):
        with self.assertRaisesRegex(ValueError, "save/open"):
            self.runner.run(self.data, self.target, self.options(row_limit=0))
        self.assertEqual(self.backend.sent, [])

    def test_focus_loss_before_entry_sends_nothing(self):
        self.backend.focus = False
        with self.assertRaises(FocusLost):
            self.runner.run(self.data, self.target, self.options())
        self.assertEqual(self.backend.sent, [])

    def test_focus_loss_mid_record_stops_before_next_tab(self):
        self.backend.focus_after_paste = False
        with self.assertRaises(FocusLost):
            self.runner.run(self.data, self.target, self.options())
        self.assertEqual(self.backend.sent, [("click", 123, 234), ("paste", "001")])
        self.assertEqual(self.backend.clipboard, "previous clipboard")
        self.assertEqual(self.backend.activations, [self.target])

    def test_escape_interrupts_mid_record_and_restores_clipboard(self):
        self.backend.cancel_after_paste = self.cancel
        with self.assertRaises(Stopped):
            self.runner.run(self.data, self.target, self.options())
        self.assertEqual(self.backend.sent, [("click", 123, 234), ("paste", "001")])
        self.assertEqual(self.backend.clipboard, "previous clipboard")

    def test_top_left_corner_stops_before_click(self):
        self.backend.position = (0, 0)
        with self.assertRaises(Stopped):
            self.runner.run(self.data, self.target, self.options())
        self.assertEqual(self.backend.sent, [])
        self.assertEqual(self.backend.activations, [])

    def test_text_block_preserves_unicode_and_separators(self):
        self.runner.run(self.data, self.target, self.options(mode="block", row_limit=0))
        self.assertEqual(self.backend.sent, [("click", 123, 234),
                         ("paste", "001\tMary Jane\tHR\n002\tJosé García\tIT")])

    def test_start_row_can_skip_already_entered_records(self):
        self.runner.run(self.data, self.target, self.options(start_row=2))
        self.assertIn(("paste", "002"), self.backend.sent)
        self.assertNotIn(("paste", "001"), self.backend.sent)

    def test_replace_is_explicit(self):
        self.runner.run(self.data, self.target, self.options(replace_fields=True))
        self.assertEqual(self.backend.sent.count(("select_all",)), 3)

    def test_runner_can_be_reused_without_accumulating_counts(self):
        self.assertEqual(self.runner.run(self.data, self.target, self.options()), 1)
        self.assertEqual(self.runner.run(self.data, self.target, self.options(start_row=2)), 1)

    def test_monitor_with_negative_coordinates_is_not_the_stop_corner(self):
        self.backend.position = (-200, -100)
        self.assertEqual(self.runner.run(self.data, self.target, self.options()), 1)

    def test_invalid_navigation_sends_nothing(self):
        for settings in [dict(tab_counts=(1,)), dict(start_row=3), dict(after_row=("delete",)),
                         dict(row_limit=-1), dict(field_delay=float("nan"))]:
            with self.assertRaises(ValueError):
                self.runner.run(self.data, self.target, self.options(**settings))
        self.assertEqual(self.backend.sent, [])

    def test_journal_marks_pastes_unverified_and_excludes_staff_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.jsonl"
            runner = EntryRunner(self.backend, self.cancel, journal=Journal(path))
            runner.run(self.data, self.target, self.options())
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("Mary Jane", text)
            entries = [json.loads(line) for line in text.splitlines()]
            self.assertTrue(all(set(entry) == {"time_utc", "status", "row", "field", "message"}
                                for entry in entries))
            self.assertTrue(all("001" not in entry["message"] for entry in entries))
            statuses = [entry["status"] for entry in entries]
            self.assertIn("row_pasted_unverified", statuses)
            self.assertNotIn("saved", statuses)


if __name__ == "__main__":
    unittest.main()
