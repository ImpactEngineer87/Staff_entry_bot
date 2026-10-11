from __future__ import annotations

import csv
import json
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .desktop import PynputBackend
from .engine import EntryRunner, FocusLost, Journal, RunOptions, Stopped, Target
from .readers import Dataset, ParseOptions, load_file
from .runtime import logs_directory, practice_launch, resource_root
from .ui import WorkspaceUI
from .ui_theme import PALETTE as C

ROOT = resource_root()
SEPARATORS = {"Spaces (quoted names supported)": "whitespace", "Tab": "tab", "Comma": "comma",
              "Semicolon": "semicolon", "Pipe |": "pipe", "Custom character": "custom"}


class Application(WorkspaceUI, tk.Tk):
    separator_choices = SEPARATORS

    def __init__(self):
        super().__init__()
        self.title("Staff Entry Bot")
        width = min(1380, self.winfo_screenwidth() - 80)
        height = min(920, self.winfo_screenheight() - 100)
        self.geometry(f"{width}x{height}")
        self.minsize(1040, 720)
        self.configure(background=C["bg"])
        self.events: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.backend: PynputBackend | None = None
        self.target: Target | None = None
        self._capture_lock = threading.Lock()
        self._capture_pending = False
        self._capture_generation = 0
        self._closing = False
        self.dataset: Dataset | None = None
        self.running = False
        self.worker: threading.Thread | None = None
        self.preview_signature = None
        self.edit_controls = []
        self.run_total = 0
        self.last_run = "No runs yet"
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll)
        self.after(250, self._enable_desktop)

    def _parse_options(self):
        return ParseOptions(SEPARATORS[self.separator.get()], self.custom.get(), self.encoding.get(),
                            self.skip_header.get(), self.sheet.get(),
                            tuple(int(c.strip()) for c in self.columns.get().split(",") if c.strip()))

    def _signature(self):
        path = Path(self.file.get())
        stat = path.stat()
        return self.file.get(), self._parse_options(), stat.st_mtime_ns, stat.st_size

    def _browse(self):
        if self.running:
            return
        path = filedialog.askopenfilename(title="Choose staff data", filetypes=[
            ("Supported data", "*.txt *.docx *.xlsx *.xlsm *.xls *.csv *.tsv"), ("All files", "*.*")], parent=self)
        if path:
            self.file.set(path)
            if Path(path).suffix.lower() == ".csv":
                self.separator.set("Comma")
            elif Path(path).suffix.lower() == ".tsv":
                self.separator.set("Tab")
            self._preview()

    def _load_example(self):
        if self.running:
            return
        self.file.set(str(ROOT / "examples" / "staff_spaces.txt"))
        self.separator.set(next(iter(SEPARATORS)))
        self.encoding.set("auto")
        self.columns.set("")
        self.sheet.set("")
        self.skip_header.set(False)
        self._preview()

    def _preview(self):
        if self.running:
            return
        try:
            self._invalidate_preview()
            if not self.file.get().strip():
                raise ValueError("Choose a source file with Browse files, or explore with sample data.")
            signature = self._signature()
            dataset = load_file(signature[0], signature[1])
            dataset.validate()
            self.tree.delete(*self.tree.get_children())
            columns = ["row", "source"] + [f"field_{i}" for i in range(1, dataset.width + 1)]
            self.tree.configure(columns=columns)
            for name in columns:
                self.tree.heading(name, text=name.replace("_", " ").title())
                self.tree.column(name, width=58 if name == "row" else 140 if name == "source" else 175,
                                 minwidth=50, stretch=name not in ("row", "source"),
                                 anchor="center" if name == "row" else "w")
            for index, record in enumerate(dataset.records[:1000], 1):
                self.tree.insert("", "end", values=(index, record.source, *record.values),
                                 tags=("even",) if index % 2 == 0 else ())
            self.summary.set(f"{len(dataset.records):,} records  ·  {dataset.width} fields  ·  All values preserved as text")
            self.notes.set(" ".join(dataset.warnings) + (" Preview shows the first 1,000 rows." if len(dataset.records) > 1000 else ""))
            self.dataset, self.preview_signature = dataset, signature
            self.row_count.set(f"{len(dataset.records):,}")
            self.field_count.set(str(dataset.width))
            self.preview_badge.set("PREVIEW READY")
            self.badge_label.configure(background=C["tint"], foreground=C["accent"])
            size = signature[3]
            file_size = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
            self.source_detail.set(f"{Path(signature[0]).suffix.upper().lstrip('.')} file  ·  {file_size}  ·  Preview ready")
            self.empty_preview.grid_remove()
            for scrollbar in self.preview_scrollbars:
                scrollbar.grid()
            self._refresh_readiness()
            self._message("Preview ready. Your destination stays locked; start entry when ready."
                          if self.target else "Preview ready. Set your destination, then capture its first field with F8.")
        except Exception as exc:
            self._error("Check the input", str(exc))

    def _run_options(self):
        block_delimiters = {"Tab": "\t", "Space": " ", "Comma": ",", "Pipe": "|"}
        return RunOptions(mode="form" if self.mode.get() == "Form fields" else "block",
                          start_row=int(self.start_row.get()), row_limit=int(self.row_limit.get()),
                          countdown=float(self.countdown.get()), field_delay=float(self.field_delay.get()),
                          paste_delay=float(self.paste_delay.get()), row_delay=float(self.row_delay.get()),
                          tab_counts=tuple(int(c.strip()) for c in self.tab_counts.get().split(",") if c.strip()),
                          after_row=tuple(c.strip().lower() for c in self.after_row.get().split(",") if c.strip()),
                          replace_fields=self.replace_fields.get(),
                          block_field_separator=block_delimiters[self.block_separator.get()])

    def _enable_desktop(self):
        if self.running or self.backend:
            return
        backend = None
        try:
            backend = PynputBackend()
            backend.listen(self._capture_hotkey, lambda: self.events.put(("start", None)), self._stop)
            self.backend = backend
            self.desktop_status.set("Desktop controls ready: F8 captures · F9 starts · Esc stops")
        except Exception as exc:
            if backend:
                backend.close()
            self.desktop_status.set(f"Desktop controls unavailable: {exc}")
            self._message("File preview is available. Resolve desktop setup before starting entry.")
        self._refresh_readiness()

    def _capture_hotkey(self):
        # Reserve the first capture before polling, so repeated F8 releases cannot
        # queue different windows while Tk has yet to accept the first result.
        with self._capture_lock:
            if self.running or self._closing or not self.backend or self._capture_pending:
                return
            if self.target is not None:
                self.events.put(("capture_locked", self._capture_generation))
                return
            self._capture_generation += 1
            generation = self._capture_generation
            self._capture_pending = True
            backend = self.backend
        self.events.put(("capture_pending", generation))
        try:
            # Capture now, on the listener thread, before UI polling could change focus.
            target = backend.capture()
            self.events.put(("target", (generation, target)))
        except Exception as exc:
            self.events.put(("capture_error", (generation, str(exc))))

    def _release_target(self):
        with self._capture_lock:
            if self.running or self._closing:
                return
            # Invalidate outcomes from captures that were already in flight.
            self._capture_generation += 1
            self._capture_pending = False
            self.target = None
        self.target_text.set("No destination captured yet")
        self._refresh_readiness()
        self.status_title.configure(text="●  Choose your new destination", foreground=C["accent"])
        self._message("Destination released. Click the first field in the new window, then press F8.")

    def _finish_capture(self, generation, target=None):
        """Apply a capture outcome only to the session that requested it."""
        with self._capture_lock:
            if generation != self._capture_generation or not self._capture_pending:
                return False
            self._capture_pending = False
            if self.running or self._closing or self.target is not None:
                return False
            if target is not None:
                self.target = target
        self._refresh_readiness()
        return True

    def _start(self):
        if self.running or self._closing:
            return
        try:
            try:
                current_signature = self._signature() if self.dataset else None
            except OSError:
                self._invalidate_preview()
                raise ValueError("The source file is no longer available. Choose it again and preview it.") from None
            if not self.dataset or self.preview_signature != current_signature:
                self._invalidate_preview()
                raise ValueError("Preview the current file and parsing settings first.")
            if not self.target:
                raise ValueError("Click the first field in the target system and press F8 first.")
            if not self.backend:
                raise ValueError("Enable desktop controls before starting.")
            options = self._run_options()
            options.validate(self.dataset.width, len(self.dataset.records))
            count = len(self.dataset.records) - options.start_row + 1
            if options.row_limit:
                count = min(count, options.row_limit)
            if options.mode == "form" and count > 1 and not options.after_row:
                raise ValueError("Set after-record keys to save/open the next form, or fill one row for manual review.")
            self.cancel.clear()
            self.running = True
            self.run_total = count
            self.progress.set(0)
            self.run_state.set("ENTRY IN PROGRESS")
            self.run_result.set(f"Filling {count:,} record{'s' if count != 1 else ''}")
            self.status_title.configure(text="●  Entry in progress", foreground=C["accent"])
            self._set_controls()
            self._show_page("activity")
            self._message(f"Starting {count} row(s) in the locked destination: '{self.target.title}'.")
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            journal = Journal(logs_directory(ROOT) / f"run_{stamp}.jsonl")
            def notify(text):
                self.events.put(("message", text))
                fraction = ((runner.current_field or 1) - 1) / dataset.width
                self.events.put(("progress", min(99, (runner.pasted_rows + fraction) / count * 100)))

            runner = EntryRunner(self.backend, self.cancel, notify, journal)
            dataset, target = self.dataset, self.target

            def work():
                try:
                    pasted = runner.run(dataset, target, options)
                    self.events.put(("done", {"message": "Finished. Verify the target fields and saved records.",
                                              "count": pasted, "success": True, "stopped": False}))
                except Exception as exc:
                    self.events.put(("done", {"message": str(exc), "count": runner.pasted_rows,
                                              "success": False, "stopped": isinstance(exc, (Stopped, FocusLost))}))

            self.worker = threading.Thread(target=work, name="entry-worker", daemon=True)
            self.worker.start()
        except Exception as exc:
            self.running = False
            self._set_controls()
            self._error("Cannot start", str(exc))

    def _stop(self):
        self.cancel.set()
        if self.running:
            self.events.put(("message", "Stop requested. Check the partial record before resuming."))

    def _poll(self):
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "message":
                    self._message(payload)
                elif event == "target":
                    generation, target = payload
                    if self._finish_capture(generation, target):
                        self.target_text.set(f"{target.title}\nWindow handle: {target.window_key} · First field: ({target.x}, {target.y})")
                        self.status_title.configure(text="●  Destination locked for this session", foreground=C["accent"])
                        self._message("Destination locked. Use Start entry or F9 to begin. Use Change destination to capture another window.")
                elif event == "capture_pending":
                    if payload == self._capture_generation and self._capture_pending and not self._closing:
                        self._refresh_readiness()
                elif event == "capture_locked":
                    if payload == self._capture_generation and self.target and not self.running and not self._closing:
                        self._message("Destination stays locked. Use Change destination before capturing another window.")
                elif event == "capture_error":
                    generation, error = payload
                    if self._finish_capture(generation):
                        self._error("Target capture", error)
                elif event == "start":
                    self._start()
                elif event == "done":
                    self.running = False
                    success, count = payload["success"], payload["count"]
                    self.progress.set(100 if success else count / max(1, self.run_total) * 100)
                    self.run_state.set("RUN COMPLETE" if success else "RUN STOPPED" if payload["stopped"] else "NEEDS ATTENTION")
                    self.run_result.set(f"{count:,} record{'s' if count != 1 else ''} pasted")
                    self.run_detail.set(payload["message"])
                    self.last_run = payload["message"]
                    self.status_title.configure(text="●  Run complete · review your records" if success else "●  Entry stopped · review before resuming",
                                                foreground=C["accent"] if success else C["danger"])
                    self._set_controls()
                    self._message(payload["message"])
                elif event == "progress":
                    self.progress.set(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _message(self, text):
        self.status.set(text)
        if self.running:
            self.run_detail.set(text)
        self.activity_events += 1
        self.activity_count.set(f"{self.activity_events:,} events")
        self.activity.configure(state="normal")
        self.activity.insert("end", f"{datetime.now():%H:%M:%S}    ", "time")
        self.activity.insert("end", f"{text}\n")
        self.activity.see("end")
        self.activity.configure(state="disabled")

    def _error(self, title, text):
        self._message(text)
        self.status_title.configure(text="●  A quick check is needed", foreground=C["danger"])
        messagebox.showerror(title, text, parent=self)

    def _export(self):
        if self.running:
            return
        try:
            if not self.dataset or self.preview_signature != self._signature():
                raise ValueError("Preview the current file and settings first.")
        except Exception as exc:
            self._invalidate_preview()
            self._error("Preview needed", str(exc))
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="staff_text.csv",
                                          filetypes=[("CSV", "*.csv")], parent=self)
        if path:
            try:
                if Path(path).resolve() == Path(self.file.get()).resolve():
                    raise ValueError("Choose a different filename from the source file.")
                with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow([f"field_{i}" for i in range(1, self.dataset.width + 1)])
                    writer.writerows(record.values for record in self.dataset.records)
                self._message("CSV exported with generic field names.")
            except Exception as exc:
                self._error("Export failed", str(exc))

    def _save_profile(self):
        if self.running:
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="form_setup.json",
                                          filetypes=[("Setup", "*.json")], parent=self)
        if path:
            try:
                # Excludes input path, target window, coordinates, and staff data.
                data = {name: variable.get() for name, variable in self.profile_vars.items()}
                Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
                self._message("Setup saved. Capture the target again whenever you reopen the app.")
            except Exception as exc:
                self._error("Save failed", str(exc))

    def _load_profile(self):
        if self.running:
            return
        path = filedialog.askopenfilename(filetypes=[("Setup", "*.json")], parent=self)
        if path:
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Setup must contain a JSON object.")
                for name, variable in self.profile_vars.items():
                    if name in data:
                        variable.set(data[name])
                self.dataset = None
                self.preview_signature = None
                self._invalidate_preview()
                self._refresh_readiness()
                self._message("Setup loaded. Preview the file again; your destination stays locked."
                              if self.target else "Setup loaded. Preview the file and capture a destination with F8.")
            except Exception as exc:
                self._error("Load failed", str(exc))

    def _demo(self):
        if self.running:
            return
        import subprocess
        try:
            command, directory, environment = practice_launch(ROOT)
            subprocess.Popen(command, cwd=directory, env=environment)
        except OSError as exc:
            self._error("Cannot open practice form", str(exc))

    def _close(self):
        with self._capture_lock:
            self._closing = True
            self._capture_generation += 1
            self._capture_pending = False
        self.cancel.set()
        if self.worker and self.worker.is_alive():
            self.status.set("Stopping before closing…")
            self.after(100, self._close)
            return
        if self.backend:
            self.backend.close()
        self.destroy()


def run():
    Application().mainloop()
