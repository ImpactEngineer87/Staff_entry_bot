"""Controlled Windows activation smoke; owned Tk windows and sample data only."""
from __future__ import annotations

import csv
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
SAMPLE = ("000731", 'Renée "QA" Иванова', "People Operations", "renee.qa@example.test")


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return None


def native():
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    api.GetAncestor.restype = wintypes.HWND
    api.GetForegroundWindow.argtypes = []
    api.GetForegroundWindow.restype = wintypes.HWND
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.GetWindowThreadProcessId.restype = wintypes.DWORD
    api.SetForegroundWindow.argtypes = [wintypes.HWND]
    api.SetForegroundWindow.restype = wintypes.BOOL
    api.IsWindow.argtypes = [wintypes.HWND]
    api.IsWindow.restype = wintypes.BOOL
    api.IsIconic.argtypes = [wintypes.HWND]
    api.IsIconic.restype = wintypes.BOOL
    api.WindowFromPoint.argtypes = [wintypes.POINT]
    api.WindowFromPoint.restype = wintypes.HWND
    return api


def target_process(folder):
    import tkinter as tk
    from tkinter import ttk
    from staffbot.desktop import enable_dpi_awareness

    enable_dpi_awareness()
    api = native()
    root = tk.Tk()
    root.title("DISPOSABLE activation smoke target - sample data only")
    root.geometry("660x430+90+90")
    ttk.Label(root, text="Disposable practice destination", font=("Segoe UI", 18, "bold")).pack(
        anchor="w", padx=24, pady=(20, 8))
    ttk.Label(root, text="Temporary sample data only. This window closes after validation.").pack(
        anchor="w", padx=24, pady=(0, 16))
    panel = ttk.Frame(root, padding=24)
    panel.pack(fill="x")
    panel.columnconfigure(1, weight=1)
    entries = []
    for index, title in enumerate(("Employee ID", "Full name", "Department", "Email")):
        ttk.Label(panel, text=title, width=18).grid(row=index, column=0, sticky="w", pady=10)
        entry = ttk.Entry(panel, width=52)
        entry.grid(row=index, column=1, sticky="ew", pady=10)
        entries.append(entry)
    sequence = 0

    def tick():
        nonlocal sequence
        command = read_json(folder / "command.json")
        if command and command["sequence"] > sequence:
            sequence = command["sequence"]
            if command["action"] == "quit":
                root.destroy()
                return
            if command["action"] == "reset":
                for entry in entries:
                    entry.delete(0, "end")
                root.deiconify()
                root.lift()
                entries[0].focus_force()
                root.update_idletasks()
                api.SetForegroundWindow(api.GetAncestor(root.winfo_id(), 2))
            elif command["action"] == "minimize":
                root.iconify()
        root.update_idletasks()
        handle = int(api.GetAncestor(root.winfo_id(), 2))
        atomic_json(folder / "state.json", {
            "pid": os.getpid(), "handle": handle, "sequence": sequence,
            "first_field": [entries[0].winfo_rootx() + 30,
                            entries[0].winfo_rooty() + entries[0].winfo_height() // 2],
            "values": [entry.get() for entry in entries],
            "iconic": bool(api.IsIconic(handle)),
        })
        root.after(30, tick)

    root.after(50, tick)
    root.mainloop()


def controller():
    from unittest.mock import patch
    from staffbot.desktop import PynputBackend, enable_dpi_awareness
    from staffbot.gui import Application
    import staffbot.gui as gui

    enable_dpi_awareness()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    folder = WORKSPACE / "artifacts" / f"activation_smoke_{stamp}_{os.getpid()}"
    folder.mkdir(parents=True)
    report = {"sample_data_only": True, "global_listener_installed": False, "cases": []}
    api = native()
    target_child = None
    app = None
    backend = None
    old_clipboard = None
    sequence = 0
    errors = []

    def pump_until(condition, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if app is not None:
                app.update()
            if condition():
                return
            time.sleep(0.01)
        raise AssertionError("Timed out waiting for a controlled smoke condition")

    def state():
        return read_json(folder / "state.json")

    def command(action):
        nonlocal sequence
        sequence += 1
        atomic_json(folder / "command.json", {"sequence": sequence, "action": action})
        pump_until(lambda: state() and state()["sequence"] == sequence)
        return state()

    def assert_owned(handle, expected_pid):
        assert api.IsWindow(handle), "Owned smoke window no longer exists"
        pid = wintypes.DWORD()
        api.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        assert pid.value == expected_pid, "Window process identity changed"

    def foreground_bot():
        handle = int(api.GetAncestor(app.winfo_id(), 2))
        assert_owned(handle, os.getpid())
        app.lift()
        app.focus_force()
        api.SetForegroundWindow(handle)
        pump_until(lambda: api.GetForegroundWindow() == handle, 3)
        return handle

    class GuardedBackend(PynputBackend):
        """Real desktop input, gated to the verified disposable destination."""
        def __init__(self):
            super().__init__()
            self.expected = None
            self.activation_count = 0
            self.input_audit = []
            self.first_paste = threading.Event()

        def verify_destination(self, focused=True):
            assert self.expected is not None, "No owned target guard installed"
            assert target_child.poll() is None, "Disposable target exited"
            assert_owned(int(self.expected.window_key), target_child.pid)
            assert self.expected.pid == target_child.pid, "Captured unexpected process"
            if focused:
                assert self.focus_matches(self.expected), "Synthetic input blocked: owned destination lost focus"

        def activate(self, target):
            assert target == self.expected, "Activation target identity changed"
            self.verify_destination(focused=False)
            self.activation_count += 1
            super().activate(target)

        def click(self, x, y):
            self.verify_destination()
            clicked = api.WindowFromPoint(wintypes.POINT(x, y))
            assert api.GetAncestor(clicked, 2) == int(self.expected.window_key), "Click is outside owned target"
            self.input_audit.append("click")
            super().click(x, y)

        def paste(self):
            self.verify_destination()
            self.input_audit.append("paste")
            super().paste()
            self.first_paste.set()

        def key(self, key):
            self.verify_destination()
            self.input_audit.append(f"key:{key}")
            super().key(key)

        def select_all(self):
            self.verify_destination()
            self.input_audit.append("select_all")
            super().select_all()

    try:
        with patch.object(Application, "_enable_desktop", lambda self: None), \
                patch.object(gui.messagebox, "showerror", lambda *args, **kwargs: errors.append(str(args))), \
                patch.object(gui, "ROOT", folder):
            app = Application()
            app.title("Staff Entry Bot - controlled activation smoke")
            app.geometry("1040x740+780+80")
            app.update()
            backend = GuardedBackend()
            app.backend = backend
            assert backend.listener is None
            old_clipboard = backend.clipboard_get()
            target_child = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--target", str(folder)],
                cwd=str(WORKSPACE), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            pump_until(lambda: state() is not None)
            first = command("reset")
            assert first["pid"] == target_child.pid
            assert_owned(first["handle"], target_child.pid)
            pump_until(lambda: api.GetForegroundWindow() == first["handle"], 3)
            point = first["first_field"]
            clicked = api.WindowFromPoint(wintypes.POINT(*point))
            assert api.GetAncestor(clicked, 2) == first["handle"]
            backend.mouse.position = tuple(point)
            app._capture_hotkey()
            pump_until(lambda: app.target is not None)
            captured = app.target
            assert captured.pid == target_child.pid
            assert int(captured.window_key) == first["handle"]
            backend.expected = captured
            report["capture"] = {"pid": captured.pid, "handle": captured.window_key}

            source = folder / "sample.csv"
            with source.open("w", encoding="utf-8", newline="") as stream:
                csv.writer(stream).writerow(SAMPLE)
            app.file.set(str(source))
            app.separator.set("Comma")
            app._preview()
            assert app.dataset and tuple(app.dataset.records[0].values) == SAMPLE
            app.countdown.set("0.3")
            app.field_delay.set("0.12")
            app.paste_delay.set("0.3")
            app.row_delay.set("0.1")
            app.after_row.set("")
            app._refresh_readiness()

            def run_case(name, *, minimized=False, interrupt=False):
                reset = command("reset")
                assert reset["handle"] == int(captured.window_key)
                foreground_bot()
                if minimized:
                    command("minimize")
                    assert api.IsIconic(int(captured.window_key)), "Target did not minimize"
                    foreground_bot()
                assert api.GetForegroundWindow() == api.GetAncestor(app.winfo_id(), 2)
                backend.first_paste.clear()
                start_activations = backend.activation_count
                start_audit = len(backend.input_audit)
                app.start_button.invoke()
                assert app.running, f"Start did not launch: {errors}"
                interrupted = False
                if interrupt:
                    pump_until(backend.first_paste.is_set, 8)
                    foreground_bot()
                    interrupted = True
                pump_until(lambda: not app.running and not app.worker.is_alive(), 15)
                # Allow the child to publish the final field values.
                final_sequence = command("snapshot")["sequence"]
                pump_until(lambda: state()["sequence"] == final_sequence)
                final = state()
                assert app.target is captured, "Locked target object was replaced"
                assert app.target == captured, "Locked target identity changed"
                assert backend.activation_count - start_activations == 1, "Destination was reactivated during entry"
                assert backend.clipboard_get() == old_clipboard, "Clipboard text was not restored"
                assert not final["iconic"], "Destination remained minimized"
                if interrupt:
                    assert final["values"][0] == SAMPLE[0], "First sample field was not pasted before interruption"
                    assert final["values"][1:] == ["", "", ""], "Input continued after deliberate focus loss"
                    assert app.run_state.get() == "RUN STOPPED", app.run_detail.get()
                    assert "focus changed" in app.run_detail.get().lower(), app.run_detail.get()
                    assert api.GetForegroundWindow() == api.GetAncestor(app.winfo_id(), 2), "Target reclaimed foreground after focus loss"
                else:
                    assert tuple(final["values"]) == SAMPLE, "Target fields differ from exact sample row"
                    assert app.run_state.get() == "RUN COMPLETE", app.run_detail.get()
                outcome = {
                    "name": name, "passed": True, "exact_sample_fields": not interrupt,
                    "locked_target_unchanged": True, "activation_calls": 1,
                    "clipboard_text_restored": True, "input_actions": backend.input_audit[start_audit:],
                    "run_state": app.run_state.get(), "deliberate_focus_loss": interrupted,
                }
                if interrupt:
                    outcome.update(first_field_only=True, no_reactivation_after_focus_loss=True)
                if minimized:
                    outcome["minimized_window_restored"] = True
                report["cases"].append(outcome)
                atomic_json(folder / "report.json", report)
                print(json.dumps(outcome), flush=True)

            run_case("Start invoked while bot is foreground")
            run_case("Minimized captured destination", minimized=True)
            run_case("Later focus loss stops entry", interrupt=True)
            assert not errors, f"Application reported modal errors: {errors}"
            report["passed"] = True
    except Exception as exc:
        report["passed"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    finally:
        if app is not None:
            app.cancel.set()
            if app.worker is not None:
                app.worker.join(timeout=5)
        if backend is not None:
            if old_clipboard is not None:
                backend.clipboard_set(old_clipboard)
                report["original_clipboard_text_restored_on_exit"] = backend.clipboard_get() == old_clipboard
            backend.close()
        if target_child is not None:
            if target_child.poll() is None:
                sequence += 1
                atomic_json(folder / "command.json", {"sequence": sequence, "action": "quit"})
                try:
                    target_child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    target_child.terminate()
                    target_child.wait(timeout=3)
            output, child_errors = target_child.communicate(timeout=3)
            report["owned_target_closed"] = target_child.poll() is not None
            if child_errors:
                report["child_errors"] = child_errors
        if app is not None:
            app.destroy()
            report["owned_bot_closed"] = True
        atomic_json(folder / "report.json", report)
        print(f"REPORT {folder / 'report.json'}", flush=True)
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    if Path(__file__).with_suffix(".cancelled").exists():
        print("Desktop smoke validation is cancelled; no windows or input will be created.", flush=True)
        raise SystemExit(2)
    if len(sys.argv) > 1 and sys.argv[1] == "--target":
        target_process(Path(sys.argv[2]))
    else:
        raise SystemExit(controller())
