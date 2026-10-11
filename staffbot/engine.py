"""Small, testable automation engine; backend is injected rather than imported."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from .readers import Dataset


class Stopped(RuntimeError):
    pass


class FocusLost(RuntimeError):
    pass


@dataclass(frozen=True)
class Target:
    x: int
    y: int
    window_key: str
    title: str
    pid: int | None = None


@dataclass(frozen=True)
class RunOptions:
    mode: str = "form"  # form: separate controls; block: all selected rows into one control
    start_row: int = 1
    row_limit: int = 1  # default is one record, for calibration
    countdown: float = 3.0
    field_delay: float = 0.25
    paste_delay: float = 0.15
    row_delay: float = 1.0
    tab_counts: tuple[int, ...] = ()  # between fields, default one Tab each
    after_row: tuple[str, ...] = ()  # manual review by default
    replace_fields: bool = False
    block_field_separator: str = "\t"
    block_row_separator: str = "\n"

    def validate(self, width: int, total: int) -> None:
        if self.mode not in ("form", "block"):
            raise ValueError("Mode must be form or block.")
        if not 1 <= self.start_row <= total:
            raise ValueError(f"Start row must be between 1 and {total}.")
        if self.row_limit < 0:
            raise ValueError("Row limit must be zero (all) or a positive integer.")
        for value in (self.countdown, self.field_delay, self.paste_delay, self.row_delay):
            if not 0 <= value <= 120:
                raise ValueError("Delays must be between 0 and 120 seconds.")
        if self.paste_delay < 0.05:
            raise ValueError("Paste delay must be at least 0.05 seconds.")
        if self.tab_counts and len(self.tab_counts) != max(0, width - 1):
            raise ValueError(f"Provide {width - 1} Tab counts between the {width} fields.")
        if any(n < 0 or n > 30 for n in self.tab_counts):
            raise ValueError("Tab counts must be between 0 and 30.")
        valid_keys = {"tab", "shift+tab", "enter", "ctrl+s", "cmd+s"}
        if any(key not in valid_keys for key in self.after_row):
            raise ValueError("After-row keys: tab, shift+tab, enter, ctrl+s, or cmd+s.")


class Backend(Protocol):
    def activate(self, target: Target) -> None: ...
    def focus_matches(self, target: Target) -> bool: ...
    def mouse_position(self) -> tuple[int, int]: ...
    def click(self, x: int, y: int) -> None: ...
    def clipboard_get(self) -> str: ...
    def clipboard_set(self, text: str) -> None: ...
    def paste(self) -> None: ...
    def select_all(self) -> None: ...
    def key(self, key: str) -> None: ...


class Journal:
    """Record row/field numbers and status, never staff values or clipboard content."""
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, status: str, row: int | None = None, field: int | None = None,
              message: str = "") -> None:
        data = {"time_utc": datetime.now(timezone.utc).isoformat(), "status": status,
                "row": row, "field": field, "message": message}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(data, ensure_ascii=False) + "\n")


class EntryRunner:
    def __init__(self, backend: Backend, cancel: threading.Event,
                 notify: Callable[[str], None] = lambda message: None,
                 journal: Journal | None = None):
        self.backend, self.cancel, self.notify, self.journal = backend, cancel, notify, journal
        self.current_row: int | None = None
        self.current_field: int | None = None
        self.pasted_rows = 0

    def _log(self, status: str, message: str = "") -> None:
        if self.journal:
            self.journal.write(status, self.current_row, self.current_field, message)

    def _check_stop(self) -> None:
        if self.cancel.is_set():
            raise Stopped("Stopped. Check the partially filled record before starting again.")
        x, y = self.backend.mouse_position()
        if 0 <= x <= 5 and 0 <= y <= 5:
            raise Stopped("Stopped by the top-left mouse corner.")

    def _check(self, target: Target) -> None:
        self._check_stop()
        if not self.backend.focus_matches(target):
            raise FocusLost("Target focus changed. Return to the captured window and check the partial record before restarting.")

    def _wait(self, seconds: float, target: Target | None = None) -> None:
        # Event.wait wakes immediately on Esc; focus is checked after every delay.
        if self.cancel.wait(seconds):
            raise Stopped("Stopped. Check the partially filled record before starting again.")
        if target:
            self._check(target)

    def _paste(self, text: str, target: Target, options: RunOptions) -> None:
        self._check(target)
        if options.replace_fields:
            self.backend.select_all()
            self._wait(options.field_delay, target)
        self.backend.clipboard_set(text)
        self._wait(options.paste_delay, target)
        self.backend.paste()
        self._wait(options.paste_delay, target)

    def run(self, dataset: Dataset, target: Target, options: RunOptions) -> int:
        dataset.validate()
        options.validate(dataset.width, len(dataset.records))
        if not target.window_key:
            raise ValueError("Capture a target before starting.")
        rows = list(enumerate(dataset.records, 1))[options.start_row - 1:]
        if options.row_limit:
            rows = rows[:options.row_limit]
        if options.mode == "form" and len(rows) > 1 and not options.after_row:
            raise ValueError("For multiple form records, configure the keys that save/open the next record.")
        self.current_row = self.current_field = None
        self.pasted_rows = 0
        old_clipboard: str | None = None
        try:
            self._log("started")
            self._check_stop()
            # Activate only at the start: subsequent focus changes must stop entry.
            self.backend.activate(target)
            self.notify(f"Starting in {options.countdown:g}s. Bring the captured destination forward if needed. Esc stops.")
            self._wait(options.countdown)
            self._check(target)
            old_clipboard = self.backend.clipboard_get()
            self._check(target)
            self.backend.click(target.x, target.y)
            self._wait(options.field_delay, target)
            if options.mode == "block":
                self.current_row = rows[0][0]
                self.current_field = 1
                text = options.block_row_separator.join(
                    options.block_field_separator.join(record.values) for _, record in rows)
                self._paste(text, target, options)
                self.pasted_rows = len(rows)
                self._log("block_pasted_unverified")
                self.notify(f"Pasted {len(rows)} rows as a text block. Verify the target content.")
            else:
                tab_counts = options.tab_counts or (1,) * max(0, dataset.width - 1)
                for row_number, record in rows:
                    self.current_row, self.current_field = row_number, 1
                    self._log("row_started")
                    if self.pasted_rows:
                        self._check(target)
                        self.backend.click(target.x, target.y)
                        self._wait(options.field_delay, target)
                    for column, value in enumerate(record.values, 1):
                        self.current_field = column
                        self.notify(f"Row {row_number}/{len(dataset.records)}, field {column}/{dataset.width}")
                        self._paste(value, target, options)
                        if column <= len(tab_counts):
                            for _ in range(tab_counts[column - 1]):
                                self._check(target)
                                self.backend.key("tab")
                                self._wait(options.field_delay, target)
                    for key in options.after_row:
                        self._check(target)
                        self.backend.key(key)
                        self._wait(options.field_delay, target)
                    self._wait(options.row_delay, target)
                    self.pasted_rows += 1
                    self._log("row_pasted_unverified")
                self.notify(f"Filled {self.pasted_rows} record(s). Verify them in the staff system.")
            self._log("finished_unverified")
            return self.pasted_rows
        except (Stopped, FocusLost) as exc:
            self._log("interrupted", str(exc))
            raise
        except Exception:
            # Exception text can contain source data, so never put it in the journal.
            self._log("failed", "Automation failed; inspect the partially filled record.")
            raise
        finally:
            if old_clipboard is not None:
                try:
                    self.backend.clipboard_set(old_clipboard)
                except Exception:
                    self.notify("Clipboard restoration failed. Your previous clipboard text could not be restored.")
