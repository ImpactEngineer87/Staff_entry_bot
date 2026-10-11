"""Preview the UI without global hotkeys, clipboard access or desktop entry.

Run with --screenshots on Windows to capture example-only product screenshots.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from staffbot.desktop import enable_dpi_awareness
from staffbot.gui import Application


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, help="Directory for Windows PNG screenshots; exits afterward.")
    args = parser.parse_args()
    enable_dpi_awareness()
    with patch.object(Application, "_enable_desktop", lambda self: None):
        app = Application()
        app.geometry("1380x920+30+30")
        app.desktop_status.set("UI preview · desktop entry is disabled.")
        errors = []
        def callback_error(exc_type, exc, traceback):
            errors.append(str(exc))
            print(f"UI callback error: {exc}", file=sys.stderr)
            app.after_idle(app._close)
        app.report_callback_exception = callback_error

        if not args.screenshots:
            app.mainloop()
            return
        if sys.platform != "win32":
            raise SystemExit("Automatic screenshots currently require Windows.")
        args.screenshots.mkdir(parents=True, exist_ok=True)
        app.lift()
        captures = iter(("empty", "preview", "settings", "target", "activity", "compact", "compact_empty"))

        def capture_next():
            try:
                name = next(captures)
            except StopIteration:
                app._close()
                return
            if name == "preview":
                app._load_example()
            elif name == "settings":
                app._toggle_import()
            elif name == "target":
                app._hide_import()
                app._show_page("target")
            elif name == "activity":
                app._show_page("activity")
            elif name == "compact":
                app.geometry("1040x720+30+30")
                app._show_page("file")
            elif name == "compact_empty":
                app.file.set("")
            app.update_idletasks()
            app.after(300, lambda: screenshot(name))

        def screenshot(name):
            output = str((args.screenshots / f"{name}.png").resolve()).replace("'", "''")
            x, y = app.winfo_rootx(), app.winfo_rooty()
            width, height = app.winfo_width(), app.winfo_height()
            command = f"""
Add-Type -AssemblyName System.Drawing
$image = New-Object System.Drawing.Bitmap({width}, {height})
$graphics = [System.Drawing.Graphics]::FromImage($image)
$graphics.CopyFromScreen({x}, {y}, 0, 0, $image.Size)
$image.Save('{output}', [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$image.Dispose()
"""
            subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            bounds = {"window": [width, height], "tree": [app.tree.winfo_width(), app.tree.winfo_height()],
                      "preview": [app.tree.winfo_rootx()-x, app.tree.winfo_rooty()-y],
                      "footer": [app.start_button.winfo_rootx()-x, app.start_button.winfo_rooty()-y,
                                 app.start_button.winfo_width(), app.start_button.winfo_height()],
                      "session_panel_visible": bool(app.session_panel.winfo_ismapped())}
            print(name, json.dumps(bounds))
            app.after(100, capture_next)

        app.after(350, capture_next)
        app.mainloop()
        if errors:
            raise SystemExit("UI callback errors: " + "; ".join(errors))


if __name__ == "__main__":
    main()
