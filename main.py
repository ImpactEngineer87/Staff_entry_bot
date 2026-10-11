from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

from staffbot.readers import ParseOptions, load_file


def startup_error(message: str) -> None:
    if sys.stderr is not None:
        print(message, file=sys.stderr)
        return
    # Windowed PyInstaller programs do not have stderr. Keep errors reviewable.
    try:
        from staffbot.runtime import logs_directory
        directory = logs_directory()
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "startup_errors.log").open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")
    except OSError:
        pass
    try:
        from tkinter import messagebox
        messagebox.showerror("Staff Entry Bot could not start", message)
    except Exception:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "Staff Entry Bot", 16)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read local files and fill a selected desktop form.")
    parser.add_argument("--preview", metavar="FILE", help="Read data without opening a GUI or sending keystrokes.")
    parser.add_argument("--separator", choices=["whitespace", "tab", "comma", "semicolon", "pipe", "custom"],
                        default="whitespace")
    parser.add_argument("--custom-separator", default="|")
    parser.add_argument("--encoding", default="auto")
    parser.add_argument("--skip-header", action="store_true")
    parser.add_argument("--sheet", default="")
    parser.add_argument("--columns", default="", help="1-based field indexes, for example 2,1,4.")
    parser.add_argument("--export", metavar="CSV", help="With --preview: write a UTF-8 CSV for manual import.")
    parser.add_argument("--practice", action="store_true", help="Open the standalone practice registration form.")
    parser.add_argument("--self-test", action="store_true", help="Check bundled readers, desktop imports, and GUI resources.")
    parser.add_argument("--report", metavar="JSON", help="With --self-test: save the result without needing a console.")
    args = parser.parse_args()
    if args.self_test:
        from staffbot.bundle_check import run_self_test
        return run_self_test(Path(args.report) if args.report else None)
    if args.practice:
        try:
            from demo_form import main as practice_main
            practice_main()
            return 0
        except Exception as exc:
            startup_error(f"Cannot open the practice form: {exc}")
            return 1
    if args.preview:
        try:
            options = ParseOptions(args.separator, args.custom_separator, args.encoding,
                                   args.skip_header, args.sheet,
                                   tuple(int(c.strip()) for c in args.columns.split(",") if c.strip()))
            dataset = load_file(args.preview, options)
            dataset.validate()
            if args.export:
                destination = Path(args.export)
                if destination.resolve() == Path(args.preview).resolve():
                    raise ValueError("Choose a different export filename from the input file.")
                with destination.open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow([f"field_{i}" for i in range(1, dataset.width + 1)])
                    writer.writerows(record.values for record in dataset.records)
            if sys.stdout is not None:
                print(json.dumps({"records": [asdict(record) for record in dataset.records],
                                  "warnings": dataset.warnings}, ensure_ascii=True, indent=2))
            return 0
        except Exception as exc:
            startup_error(f"Error: {exc}")
            return 1
    try:
        from staffbot.desktop import enable_dpi_awareness
        enable_dpi_awareness()
        from staffbot.gui import run
        run()
        return 0
    except Exception as exc:
        startup_error(f"Cannot start the desktop app: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
