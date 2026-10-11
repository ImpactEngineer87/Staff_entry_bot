"""Exercise the real Tk workspace with an inert desktop and temporary files."""
import csv
import json
import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from staffbot import gui
from staffbot.engine import FocusLost, Target


PROJECT_ROOT = gui.ROOT


class FakeDesktop:
    """Record automation actions without reading or changing the user's desktop."""

    def __init__(self):
        self.clipboard = "previous clipboard text"
        self.sent = []
        self.closed = False
        self.on_paste = None
        self.capture_count = 0
        self.capture_target = Target(120, 240, "fake-window", "Practice destination")
        self.capture_error = None
        self.activations = []
        self.activation_error = None
        self.focus = True

    def listen(self, capture, start, stop):
        self.callbacks = capture, start, stop

    def capture(self):
        self.capture_count += 1
        if self.capture_error:
            raise self.capture_error
        return self.capture_target

    def focus_matches(self, target):
        return self.focus

    def activate(self, target):
        self.activations.append(target)
        if self.activation_error:
            raise self.activation_error
        self.focus = True

    def mouse_position(self):
        return 120, 240

    def click(self, x, y):
        self.sent.append(("click", x, y))

    def clipboard_get(self):
        return self.clipboard

    def clipboard_set(self, text):
        self.clipboard = text

    def paste(self):
        self.sent.append(("paste", self.clipboard))
        if self.on_paste:
            self.on_paste()

    def select_all(self):
        self.sent.append(("select_all",))

    def key(self, key):
        self.sent.append(("key", key))

    def close(self):
        self.closed = True


class ImmediateEvent(threading.Event):
    """Keep cancellation real while avoiding the configured automation delays."""

    def wait(self, timeout=None):
        return self.is_set()


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A missing display/Tcl installation must not disable reader/engine tests.
        try:
            probe = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tk desktop unavailable: {exc}") from exc
        probe.withdraw()
        probe.destroy()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        examples = self.root / "examples"
        examples.mkdir()
        for name in ("staff_spaces.txt", "staff.csv"):
            (examples / name).write_bytes((PROJECT_ROOT / "examples" / name).read_bytes())
        self.desktop = FakeDesktop()
        self.backend_constructor = self._patch("staffbot.gui.PynputBackend", return_value=self.desktop)
        self._patch("staffbot.gui.ROOT", self.root)
        self.errors = self._patch("staffbot.gui.messagebox.showerror")
        self.open_dialog = self._patch("staffbot.gui.filedialog.askopenfilename", return_value="")
        self.save_dialog = self._patch("staffbot.gui.filedialog.asksaveasfilename", return_value="")
        self.app = gui.Application()
        self.app.withdraw()
        self.addCleanup(self._close_app)
        self.app.cancel = ImmediateEvent()
        self.app.update_idletasks()

    def _patch(self, target, *args, **kwargs):
        patcher = patch(target, *args, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def _close_app(self):
        self.app.cancel.set()
        if self.app.worker:
            self.app.worker.join(timeout=3)
        callbacks = self.app.tk.call("after", "info")
        for callback in self.app.tk.splitlist(callbacks):
            self.app.after_cancel(callback)
        self.app._close()

    def _ready(self):
        self.app._load_example()
        self.app._enable_desktop()
        self.app._capture_hotkey()
        self.app._poll()
        self.assertFalse(self.app.start_button.instate(["disabled"]))

    def _queue_capture(self, target):
        # Model a completed listener capture before desktop readiness is enabled.
        with self.app._capture_lock:
            self.app._capture_generation += 1
            generation = self.app._capture_generation
            self.app._capture_pending = True
        self.app.events.put(("target", (generation, target)))

    def _finish_worker(self):
        self.assertIsNotNone(self.app.worker)
        self.app.worker.join(timeout=3)
        self.assertFalse(self.app.worker.is_alive(), "Mocked automation did not finish")
        self.app._poll()

    def test_json_browse_preview_reorder_and_export(self):
        path = self.root / "staff.json"
        path.write_text(json.dumps([{"id": "001", "name": "Mary Jane"},
                                    {"name": "José García", "id": "002"}]), encoding="utf-8")
        self.open_dialog.return_value = str(path)
        self.app._browse()
        self.assertEqual(self.app.dataset.records[1].values, ("002", "José García"))
        self.assertIn("*.json", self.open_dialog.call_args.kwargs["filetypes"][0][1])
        self.assertIn("JSON", self.app.formats_label.cget("text"))
        self.app.columns.set("2,1")
        self.app._preview()
        self.assertEqual(self.app.dataset.records[0].values, ("Mary Jane", "001"))
        destination = self.root / "from_json.csv"
        self.save_dialog.return_value = str(destination)
        self.app._export()
        with destination.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[1:], [["Mary Jane", "001"], ["José García", "002"]])
        self.errors.assert_not_called()

    def test_start_requires_source_destination_and_desktop(self):
        self.assertEqual(self.app.current_page, "file")
        self.assertTrue(self.app.start_button.instate(["disabled"]))
        self.assertTrue(self.app.stop_button.instate(["disabled"]))
        self.assertTrue(self.app.export_button.instate(["disabled"]))
        self.app._load_example()
        self.assertTrue(self.app.start_button.instate(["disabled"]))
        self._queue_capture(self.desktop.capture_target)
        self.app._poll()
        self.assertTrue(self.app.start_button.instate(["disabled"]))
        self.app._enable_desktop()
        self.assertFalse(self.app.start_button.instate(["disabled"]))
        self.assertTrue(self.app.stop_button.instate(["disabled"]))
        self.assertEqual(self.desktop.sent, [])

    def test_sample_preview_preserves_text_and_generic_fields(self):
        self.app._load_example()
        self.assertEqual(len(self.app.dataset.records), 3)
        self.assertEqual(self.app.dataset.width, 4)
        self.assertEqual(self.app.dataset.records[0].values[:2], ("001", "Mary Jane"))
        self.assertEqual(self.app.row_count.get(), "3")
        self.assertEqual(self.app.field_count.get(), "4")
        self.assertEqual(self.app.preview_badge.get(), "PREVIEW READY")
        self.assertEqual(tuple(self.app.tree["columns"]),
                         ("row", "source", "field_1", "field_2", "field_3", "field_4"))
        self.assertEqual(len(self.app.tree.get_children()), 3)
        self.errors.assert_not_called()

    def test_browse_csv_selects_separator_and_keeps_header_preference(self):
        self.app.skip_header.set(True)
        source = self.root / "examples" / "staff.csv"
        self.open_dialog.return_value = str(source)
        self.app._browse()
        self.assertEqual(self.app.separator.get(), "Comma")
        self.assertEqual(self.app.file.get(), str(source))
        self.assertEqual(len(self.app.dataset.records), 3)
        self.assertEqual(self.app.dataset.records[0].values[0], "001")
        self.errors.assert_not_called()

    def test_import_edits_clear_preview_and_disable_entry(self):
        self._ready()
        captured = self.app.target
        for name, value in (("separator", "Tab"), ("custom", ";"), ("encoding", "utf-16"),
                            ("sheet", "Another sheet"), ("columns", "2,1"), ("skip_header", True),
                            ("file", str(self.root / "other.txt"))):
            with self.subTest(setting=name):
                self.app._load_example()
                getattr(self.app, name).set(value)
                self.assertIsNone(self.app.dataset)
                self.assertIsNone(self.app.preview_signature)
                self.assertEqual(self.app.tree.get_children(), ())
                self.assertTrue(self.app.start_button.instate(["disabled"]))
                self.assertTrue(self.app.export_button.instate(["disabled"]))
                self.assertIs(self.app.target, captured)
        self.assertEqual(self.desktop.sent, [])

    def test_repeated_capture_before_poll_uses_first_request(self):
        self.app._enable_desktop()
        self.app._capture_hotkey()
        self.app._capture_hotkey()
        self.assertEqual(self.desktop.capture_count, 1)
        self.assertTrue(self.app._capture_pending)
        self.assertIsNone(self.app.target)
        self.app._poll()
        self.assertIs(self.app.target, self.desktop.capture_target)
        self.assertFalse(self.app._capture_pending)
        self.errors.assert_not_called()

    def test_locked_destination_ignores_f8_without_recapturing(self):
        self._ready()
        captured = self.app.target
        self.desktop.capture_target = Target(300, 400, "different-window", "Another destination")
        self.app._capture_hotkey()
        self.app._poll()
        self.assertEqual(self.desktop.capture_count, 1)
        self.assertIs(self.app.target, captured)
        self.errors.assert_not_called()

    def test_explicit_release_allows_a_new_destination(self):
        self._ready()
        self.assertFalse(self.app.release_target_button.instate(["disabled"]))
        self.app._release_target()
        self.assertIsNone(self.app.target)
        self.assertFalse(self.app._capture_pending)
        self.assertTrue(self.app.start_button.instate(["disabled"]))
        self.assertTrue(self.app.release_target_button.instate(["disabled"]))
        replacement = Target(300, 400, "different-window", "Another destination")
        self.desktop.capture_target = replacement
        self.app._capture_hotkey()
        self.app._poll()
        self.assertIs(self.app.target, replacement)
        self.assertEqual(self.desktop.capture_count, 2)
        self.assertFalse(self.app.start_button.instate(["disabled"]))
        self.errors.assert_not_called()

    def test_closing_session_ignores_start_capture_and_release(self):
        self._ready()
        captured = self.app.target
        self.app._closing = True
        self.app.events.put(("start", None))
        self.app._capture_hotkey()
        self.app._release_target()
        self.app._poll()
        self.assertIs(self.app.target, captured)
        self.assertIsNone(self.app.worker)
        self.assertFalse(self.app.running)
        self.assertEqual(self.desktop.capture_count, 1)
        self.assertEqual(self.desktop.sent, [])
        self.errors.assert_not_called()

    def test_stale_inflight_result_cannot_replace_or_cancel_new_capture(self):
        self.app._enable_desktop()
        for old_outcome in ("success", "error"):
            with self.subTest(old_outcome=old_outcome):
                self.app._release_target()
                entered = [threading.Event(), threading.Event()]
                proceed = [threading.Event(), threading.Event()]
                threads = []
                calls = []
                targets = [Target(10, 20, "old-window", "Old destination"),
                           Target(30, 40, "new-window", "New destination")]

                def capture(entered=entered, proceed=proceed, calls=calls,
                            targets=targets, old_outcome=old_outcome):
                    index = len(calls)
                    calls.append(index)
                    entered[index].set()
                    if not proceed[index].wait(timeout=3):
                        raise RuntimeError("Test capture timed out")
                    if index == 0 and old_outcome == "error":
                        raise RuntimeError("Stale capture failure")
                    return targets[index]

                def finish_captures(proceed=proceed, threads=threads):
                    for event in proceed:
                        event.set()
                    for thread in threads:
                        thread.join(timeout=3)

                self.addCleanup(finish_captures)
                with patch.object(self.desktop, "capture", side_effect=capture):
                    first = threading.Thread(target=self.app._capture_hotkey, daemon=True)
                    threads.append(first)
                    first.start()
                    self.assertTrue(entered[0].wait(timeout=3))
                    self.app._release_target()
                    second = threading.Thread(target=self.app._capture_hotkey, daemon=True)
                    threads.append(second)
                    second.start()
                    self.assertTrue(entered[1].wait(timeout=3))
                    proceed[0].set()
                    first.join(timeout=3)
                    self.assertFalse(first.is_alive())
                    self.app._poll()
                    self.assertIsNone(self.app.target)
                    self.assertTrue(self.app._capture_pending)
                    self.assertFalse(self.app.release_target_button.instate(["disabled"]))
                    self.errors.assert_not_called()
                    proceed[1].set()
                    second.join(timeout=3)
                    self.assertFalse(second.is_alive())
                    self.app._poll()
                self.assertIs(self.app.target, targets[1])
                self.assertFalse(self.app._capture_pending)
                self.errors.assert_not_called()

    def test_failed_capture_releases_reservation_for_retry(self):
        self.app._enable_desktop()
        self.desktop.capture_error = RuntimeError("Click a destination first")
        self.app._capture_hotkey()
        self.app._poll()
        self.assertIsNone(self.app.target)
        self.assertFalse(self.app._capture_pending)
        self.errors.assert_called_once()
        self.errors.reset_mock()
        self.desktop.capture_error = None
        self.app._capture_hotkey()
        self.app._poll()
        self.assertIs(self.app.target, self.desktop.capture_target)
        self.assertFalse(self.app._capture_pending)
        self.assertEqual(self.desktop.capture_count, 2)
        self.errors.assert_not_called()

    def test_changed_source_is_rejected_before_entry(self):
        self._ready()
        Path(self.app.file.get()).write_text('999 "Changed Person" HR changed@example.com\n', encoding="utf-8")
        self.app._start()
        self.assertFalse(self.app.running)
        self.assertIsNone(self.app.worker)
        self.assertEqual(self.desktop.sent, [])
        self.assertEqual(self.desktop.activations, [])
        self.errors.assert_called_once()
        self.assertEqual(self.errors.call_args.args[0], "Cannot start")

    def test_deleted_source_export_invalidates_preview_without_dialog(self):
        self._ready()
        Path(self.app.file.get()).unlink()
        self.app._export()
        self.assertIsNone(self.app.dataset)
        self.assertTrue(self.app.start_button.instate(["disabled"]))
        self.save_dialog.assert_not_called()
        self.errors.assert_called_once()
        self.assertEqual(self.errors.call_args.args[0], "Preview needed")

    def test_export_includes_records_beyond_preview_limit(self):
        source = self.root / "large.txt"
        source.write_text("".join(f'{index:04d} "Person {index}"\n' for index in range(1002)), encoding="utf-8")
        self.app.file.set(str(source))
        self.app._preview()
        self.assertEqual(len(self.app.tree.get_children()), 1000)
        destination = self.root / "export.csv"
        self.save_dialog.return_value = str(destination)
        self.app._export()
        with destination.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[0], ["field_1", "field_2"])
        self.assertEqual(rows[1], ["0000", "Person 0"])
        self.assertEqual(rows[-1], ["1001", "Person 1001"])
        self.assertEqual(len(rows), 1003)
        self.errors.assert_not_called()

    def test_profile_roundtrip_excludes_source_target_and_staff_values(self):
        self._ready()
        captured = self.app.target
        self.app.columns.set("2,1")
        self.app.after_row.set("tab,enter")
        self.app.row_limit.set("0")
        self.app.replace_fields.set(True)
        destination = self.root / "setup.json"
        self.save_dialog.return_value = str(destination)
        self.app._save_profile()
        saved = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(set(saved), set(self.app.profile_vars))
        self.assertNotIn("file", saved)
        self.assertNotIn("target", saved)
        self.assertNotIn("Mary Jane", destination.read_text(encoding="utf-8"))
        self.assertNotIn("Practice destination", destination.read_text(encoding="utf-8"))
        other_source = str(self.root / "not-part-of-setup.txt")
        self.app.file.set(other_source)
        self.app.columns.set("")
        self.app.after_row.set("")
        self.app.row_limit.set("1")
        self.app.replace_fields.set(False)
        self.open_dialog.return_value = str(destination)
        self.app._load_profile()
        self.assertEqual(self.app.file.get(), other_source)
        self.assertEqual(self.app.columns.get(), "2,1")
        self.assertEqual(self.app.after_row.get(), "tab,enter")
        self.assertEqual(self.app.row_limit.get(), "0")
        self.assertTrue(self.app.replace_fields.get())
        self.assertIsNone(self.app.dataset)
        self.assertIs(self.app.target, captured)
        self.assertTrue(self.app.start_button.instate(["disabled"]))
        self.errors.assert_not_called()

    def test_start_button_activates_locked_destination_and_restores_controls(self):
        self._ready()
        captured = self.app.target
        expected = self.app.dataset.records[0].values
        # The bot is in front when its Start button is clicked.
        self.desktop.focus = False
        self.app.start_button.invoke()
        self.assertEqual(self.app.current_page, "activity")
        self.assertTrue(self.app.start_button.instate(["disabled"]))
        self.assertFalse(self.app.stop_button.instate(["disabled"]))
        self.assertTrue(all(str(widget.cget("state")) == "disabled" for widget, _ in self.app.edit_controls))
        self.assertTrue(self.app.release_target_button.instate(["disabled"]))
        self.app._release_target()
        self.assertIs(self.app.target, captured)
        self._finish_worker()
        self.assertFalse(self.app.running)
        self.assertIs(self.app.target, captured)
        self.assertEqual(self.app.run_state.get(), "RUN COMPLETE")
        self.assertEqual(self.app.run_result.get(), "1 record pasted")
        self.assertEqual(self.app.progress.get(), 100)
        self.assertFalse(self.app.start_button.instate(["disabled"]))
        self.assertTrue(self.app.stop_button.instate(["disabled"]))
        self.assertEqual([action[1] for action in self.desktop.sent if action[0] == "paste"], list(expected))
        self.assertEqual(len(self.desktop.activations), 1)
        self.assertIs(self.desktop.activations[0], captured)
        self.assertEqual(self.desktop.capture_count, 1)
        self.assertEqual(self.desktop.clipboard, "previous clipboard text")
        journal = next((self.root / "logs").glob("run_*.jsonl"))
        statuses = [json.loads(line)["status"] for line in journal.read_text(encoding="utf-8").splitlines()]
        self.assertIn("finished_unverified", statuses)
        self.assertNotIn("Mary Jane", journal.read_text(encoding="utf-8"))
        self.errors.assert_not_called()

    def test_activation_failure_sends_nothing_and_allows_retry_without_recapture(self):
        self._ready()
        captured = self.app.target
        expected = self.app.dataset.records[0].values
        self.desktop.focus = False
        self.desktop.activation_error = FocusLost("Captured window could not be activated")
        self.app.start_button.invoke()
        self._finish_worker()
        self.assertFalse(self.app.running)
        self.assertEqual(self.app.run_state.get(), "RUN STOPPED")
        self.assertEqual(self.app.run_result.get(), "0 records pasted")
        self.assertIn("could not be activated", self.app.run_detail.get())
        self.assertIs(self.app.target, captured)
        self.assertEqual(self.desktop.sent, [])
        self.assertEqual(self.desktop.clipboard, "previous clipboard text")
        self.assertEqual(len(self.desktop.activations), 1)
        self.assertIs(self.desktop.activations[0], captured)
        self.assertFalse(self.app.start_button.instate(["disabled"]))
        self.assertTrue(self.app.stop_button.instate(["disabled"]))
        self.desktop.activation_error = None
        self.app.start_button.invoke()
        self._finish_worker()
        self.assertEqual(self.app.run_state.get(), "RUN COMPLETE")
        self.assertIs(self.app.target, captured)
        self.assertEqual(len(self.desktop.activations), 2)
        self.assertTrue(all(target is captured for target in self.desktop.activations))
        self.assertEqual(self.desktop.capture_count, 1)
        self.assertEqual([action[1] for action in self.desktop.sent if action[0] == "paste"], list(expected))
        self.assertEqual(self.desktop.clipboard, "previous clipboard text")
        self.errors.assert_not_called()

    def test_focus_loss_after_first_paste_stops_without_reactivation_or_rebinding(self):
        self._ready()
        captured = self.app.target
        expected = self.app.dataset.records[0].values

        def lose_focus():
            self.desktop.focus = False

        self.desktop.on_paste = lose_focus
        self.app.start_button.invoke()
        self._finish_worker()
        self.assertFalse(self.app.running)
        self.assertEqual(self.app.run_state.get(), "RUN STOPPED")
        self.assertEqual(self.app.run_result.get(), "0 records pasted")
        self.assertIn("focus changed", self.app.run_detail.get())
        self.assertIs(self.app.target, captured)
        self.assertEqual(self.desktop.sent, [("click", captured.x, captured.y), ("paste", expected[0])])
        self.assertEqual(len(self.desktop.activations), 1)
        self.assertIs(self.desktop.activations[0], captured)
        self.assertEqual(self.desktop.capture_count, 1)
        self.assertEqual(self.desktop.clipboard, "previous clipboard text")
        self.assertFalse(self.app.start_button.instate(["disabled"]))
        self.assertTrue(self.app.stop_button.instate(["disabled"]))
        self.errors.assert_not_called()

    def test_cancelled_partial_record_is_reported_as_stopped(self):
        self._ready()
        captured = self.app.target
        self.desktop.on_paste = self.app._stop
        self.app._start()
        self._finish_worker()
        self.assertFalse(self.app.running)
        self.assertIs(self.app.target, captured)
        self.assertEqual(self.app.run_state.get(), "RUN STOPPED")
        self.assertEqual(self.app.run_result.get(), "0 records pasted")
        self.assertEqual(self.app.progress.get(), 0)
        self.assertEqual(len([action for action in self.desktop.sent if action[0] == "paste"]), 1)
        self.assertEqual(len(self.desktop.activations), 1)
        self.assertIs(self.desktop.activations[0], captured)
        self.assertEqual(self.desktop.clipboard, "previous clipboard text")
        self.assertFalse(self.app.start_button.instate(["disabled"]))
        self.assertTrue(self.app.stop_button.instate(["disabled"]))
        self.assertIn("partially filled", self.app.run_detail.get())
        self.errors.assert_not_called()

    def test_desktop_failure_keeps_preview_available(self):
        self.app._load_example()
        self.backend_constructor.side_effect = RuntimeError("Desktop access unavailable")
        self.app._enable_desktop()
        self.assertIsNotNone(self.app.dataset)
        self.assertIsNone(self.app.backend)
        self.assertFalse(self.app.export_button.instate(["disabled"]))
        self.assertTrue(self.app.start_button.instate(["disabled"]))
        self.assertIn("Desktop access unavailable", self.app.desktop_status.get())
        self.errors.assert_not_called()


if __name__ == "__main__":
    unittest.main()
