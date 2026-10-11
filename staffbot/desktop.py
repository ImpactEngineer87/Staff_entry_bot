"""Desktop backend with a native foreground-window check and Unicode clipboard paste."""
from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable

from .engine import FocusLost, Target


def enable_dpi_awareness() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass


@dataclass(frozen=True)
class Focus:
    key: str
    title: str
    pid: int | None = None
    bounds: tuple[int, int, int, int] | None = None


class NativeFocus:
    def __init__(self):
        if sys.platform == "win32":
            from ctypes import wintypes
            self.user32 = ctypes.WinDLL("user32", use_last_error=True)
            self.user32.GetForegroundWindow.argtypes = []
            self.user32.GetForegroundWindow.restype = wintypes.HWND
            self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
            self.user32.GetWindowTextLengthW.restype = ctypes.c_int
            self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            self.user32.GetWindowTextW.restype = ctypes.c_int
            self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            self.user32.GetWindowRect.restype = wintypes.BOOL
            for name in ("IsWindow", "IsIconic", "SetForegroundWindow"):
                function = getattr(self.user32, name)
                function.argtypes = [wintypes.HWND]
                function.restype = wintypes.BOOL
            self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            self.user32.ShowWindow.restype = wintypes.BOOL
        elif sys.platform == "darwin":
            try:
                from AppKit import NSWorkspace
                self.workspace = NSWorkspace.sharedWorkspace()
            except ImportError as exc:
                raise RuntimeError("Install the requirements first; macOS needs the pynput PyObjC dependencies.") from exc
        elif sys.platform.startswith("linux"):
            if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
                raise RuntimeError("This bot requires an X11 desktop on Linux. Log in using 'Ubuntu on Xorg'.")
            if not os.environ.get("DISPLAY"):
                raise RuntimeError("No desktop display found. Run this app in your local graphical desktop.")
        else:
            raise RuntimeError("Supported systems: Windows, macOS, and Linux with X11.")

    def active(self) -> Focus:
        if sys.platform == "win32":
            from ctypes import wintypes
            handle = self.user32.GetForegroundWindow()
            if not handle:
                raise RuntimeError("No foreground window. Click your target application first.")
            size = self.user32.GetWindowTextLengthW(handle)
            text = ctypes.create_unicode_buffer(size + 1)
            self.user32.GetWindowTextW(handle, text, size + 1)
            pid = wintypes.DWORD()
            self.user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
            rect = wintypes.RECT()
            bounds = None
            if self.user32.GetWindowRect(handle, ctypes.byref(rect)):
                bounds = (rect.left, rect.top, rect.right, rect.bottom)
            return Focus(str(handle), text.value or "Untitled window", int(pid.value), bounds)
        if sys.platform == "darwin":
            app = self.workspace.frontmostApplication()
            if app is None:
                raise RuntimeError("No foreground application found.")
            # This checks the app, not individual windows within the app.
            return Focus(str(app.processIdentifier()), str(app.localizedName()), int(app.processIdentifier()))
        try:
            result = subprocess.run(["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                                    capture_output=True, text=True, timeout=1, check=True)
            match = re.search(r"0x[0-9a-fA-F]+", result.stdout)
            if not match or int(match.group(0), 16) == 0:
                raise RuntimeError("The desktop did not report a foreground window.")
            handle = match.group(0)
            result = subprocess.run(["xprop", "-id", handle, "_NET_WM_NAME", "_NET_WM_PID"],
                                    capture_output=True, text=True, timeout=1, check=True)
            title_match = re.search(r'_NET_WM_NAME[^=]*=\s*"(.*)"', result.stdout)
            pid_match = re.search(r"_NET_WM_PID[^=]*=\s*(\d+)", result.stdout)
            return Focus(handle, title_match.group(1) if title_match else handle,
                         int(pid_match.group(1)) if pid_match else None)
        except FileNotFoundError as exc:
            raise RuntimeError("Install x11-utils (xprop) before using automation on Linux.") from exc
        except subprocess.SubprocessError as exc:
            raise RuntimeError("Could not inspect the active X11 window.") from exc

    def activate(self, target: Target) -> None:
        """Bring the captured Windows handle forward before the run countdown.

        macOS and X11 retain manual activation during the existing countdown.
        Windows can deny foreground requests; no input or workaround is used to
        override that decision, and the caller must still check focus afterwards.
        """
        if sys.platform != "win32":
            return
        from ctypes import wintypes

        unavailable = ("The captured destination window is no longer available or belongs to a different process. "
                       "Open it, use Change destination, capture its first field with F8, "
                       "then press F9 there.")
        try:
            handle = int(target.window_key)
        except (TypeError, ValueError):
            raise FocusLost(unavailable) from None

        def destination_exists():
            if not self.user32.IsWindow(handle):
                return False
            if target.pid is None:
                return True
            pid = wintypes.DWORD()
            thread = self.user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
            return bool(thread) and pid.value == target.pid

        if handle <= 0 or not destination_exists():
            raise FocusLost(unavailable)
        if self.user32.GetForegroundWindow() == handle:
            return
        if self.user32.IsIconic(handle):
            # SW_RESTORE. ShowWindow returns previous visibility, not success.
            self.user32.ShowWindow(handle, 9)
        self.user32.SetForegroundWindow(handle)
        # Check the actual foreground handle even if the request reported success.
        # A brief transition is allowed, without retrying or forcing activation.
        for attempt in range(6):
            if not destination_exists():
                raise FocusLost(unavailable)
            if self.user32.GetForegroundWindow() == handle:
                return
            if attempt < 5:
                time.sleep(0.05)
        raise FocusLost("Windows could not bring the captured destination to the foreground. "
                        "Click the captured window and press F9 there to retry.")


class PynputBackend:
    def __init__(self):
        self.focus = NativeFocus()
        try:
            from pynput import keyboard, mouse
            import pyperclip
        except ImportError as exc:
            raise RuntimeError("Desktop packages are missing or no desktop is available. Run the setup script.") from exc
        self.keyboard, self.mouse_module, self.clipboard = keyboard, mouse, pyperclip
        self.keys = keyboard.Controller()
        self.mouse = mouse.Controller()
        self.modifier = keyboard.Key.cmd if sys.platform == "darwin" else keyboard.Key.ctrl
        self.listener = None

    def capture(self) -> Target:
        focus = self.focus.active()
        if focus.pid == os.getpid():
            raise RuntimeError("Click the first field in your target application, then press F8 there.")
        x, y = self.mouse_position()
        if focus.bounds:
            left, top, right, bottom = focus.bounds
            if not (left <= x < right and top <= y < bottom):
                raise RuntimeError("Move the mouse inside the active target window, over its first input field.")
        return Target(x, y, focus.key, focus.title, pid=focus.pid)

    def focus_matches(self, target: Target) -> bool:
        focus = self.focus.active()
        return focus.key == target.window_key and (target.pid is None or focus.pid == target.pid)

    def activate(self, target: Target) -> None:
        self.focus.activate(target)

    def mouse_position(self) -> tuple[int, int]:
        x, y = self.mouse.position
        return int(x), int(y)

    def click(self, x: int, y: int) -> None:
        self.mouse.position = (x, y)
        self.mouse.click(self.mouse_module.Button.left, 1)

    def clipboard_get(self) -> str:
        return self.clipboard.paste()

    def clipboard_set(self, text: str) -> None:
        self.clipboard.copy(text)

    def _chord(self, modifier, character: str) -> None:
        with self.keys.pressed(modifier):
            self.keys.press(character)
            self.keys.release(character)

    def paste(self) -> None:
        self._chord(self.modifier, "v")

    def select_all(self) -> None:
        self._chord(self.modifier, "a")

    def key(self, key: str) -> None:
        if key in ("ctrl+s", "cmd+s"):
            self._chord(self.keyboard.Key.ctrl if key == "ctrl+s" else self.keyboard.Key.cmd, "s")
            return
        if key == "shift+tab":
            with self.keys.pressed(self.keyboard.Key.shift):
                self.keys.press(self.keyboard.Key.tab)
                self.keys.release(self.keyboard.Key.tab)
            return
        native = {"tab": self.keyboard.Key.tab, "enter": self.keyboard.Key.enter}[key]
        self.keys.press(native)
        self.keys.release(native)

    def listen(self, capture: Callable[[], None], start: Callable[[], None],
               stop: Callable[[], None]) -> None:
        held = set()

        def pressed(key):
            if key in held:
                return
            held.add(key)
            if key == self.keyboard.Key.esc:
                stop()

        def released(key):
            held.discard(key)
            # Capture/start on release so no function key remains held during typing.
            if key == self.keyboard.Key.f8:
                capture()
            elif key == self.keyboard.Key.f9:
                start()

        self.listener = self.keyboard.Listener(on_press=pressed, on_release=released)
        self.listener.start()
        self.listener.wait()
        if sys.platform == "darwin" and not getattr(self.listener, "IS_TRUSTED", True):
            self.listener.stop()
            raise RuntimeError("Grant Accessibility and Input Monitoring permission to Python/Terminal in System Settings.")

    def close(self) -> None:
        if self.listener:
            self.listener.stop()
