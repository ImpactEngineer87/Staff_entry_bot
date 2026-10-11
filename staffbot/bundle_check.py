"""Smoke checks for a built executable. Never types into another application."""
from __future__ import annotations

import importlib
import json
import platform
import sys
from pathlib import Path

from . import __version__
from .readers import ParseOptions, load_file
from .runtime import is_frozen, logs_directory, practice_launch, resource_root


def run_self_test(report: Path | None = None) -> int:
    result = {"ok": False, "version": __version__, "python": platform.python_version(),
              "platform": platform.platform(), "frozen": is_frozen(), "checks": {}}
    try:
        root = resource_root()
        for filename, options in [("staff_spaces.txt", ParseOptions()), ("staff.docx", ParseOptions()),
                                   ("staff.xlsx", ParseOptions(skip_header=True))]:
            dataset = load_file(root / "examples" / filename, options)
            dataset.validate()
            if len(dataset.records) != 3 or dataset.width != 4:
                raise ValueError(f"Unexpected sample contents: {filename}")
            if dataset.records[0].values[0] != "001" or dataset.records[2].values[1] != "José García":
                raise ValueError(f"Text or Unicode was changed when reading {filename}")
            result["checks"][filename] = "passed"
        # These readers are imported through importlib in production; verify their inclusion.
        for module in ("docx", "openpyxl", "xlrd", "pyperclip", "defusedxml"):
            importlib.import_module(module)
            result["checks"][module] = "imported"
        if sys.platform == "win32":
            for module in ("pynput.keyboard._win32", "pynput.mouse._win32", "pynput._util.win32"):
                importlib.import_module(module)
                result["checks"][module] = "imported"
        import demo_form
        if not callable(demo_form.main):
            raise ValueError("Practice entry point missing")
        command, _, environment = practice_launch(root)
        if is_frozen() and (command != [sys.executable, "--practice"] or
                            environment.get("PYINSTALLER_RESET_ENVIRONMENT") != "1"):
            raise ValueError("Practice launcher would not start a separate packaged instance")
        result["checks"]["practice_launcher"] = "passed"
        if is_frozen() and root == logs_directory(root).parent:
            raise ValueError("Logs would be saved in the temporary extraction directory")
        result["checks"]["persistent_logs"] = "passed"
        # Build runners can check real Tcl/Tk and workspace construction without typing.
        if sys.platform == "win32":
            from .gui import Application
            application = Application()
            try:
                application.withdraw()
                application._load_example()
                application.update_idletasks()
                if application.dataset is None:
                    raise ValueError("Packaged sample preview failed")
                result["checks"]["workspace_gui"] = "constructed and sample preview loaded"
            finally:
                application._close()
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
    if sys.stdout is not None:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["ok"] else 1
