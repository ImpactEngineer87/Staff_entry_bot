"""Build and check a standalone Windows GUI executable from the current source."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_command(output: Path, work: Path) -> list[str]:
    return [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
            "--distpath", str(output), "--workpath", str(work), str(ROOT / "StaffEntryBot.spec")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--work", type=Path, default=ROOT / "build")
    parser.add_argument("--console", action="store_true", help="Produce a console-enabled build for troubleshooting.")
    args = parser.parse_args()
    if sys.platform != "win32":
        print("Build a Windows EXE on Windows, or use the repository's Windows EXE GitHub Actions workflow.", file=sys.stderr)
        return 1
    output, work = args.output.resolve(), args.work.resolve()
    try:
        importlib.metadata.version("pyinstaller")
        importlib.metadata.version("pyinstaller-hooks-contrib")
        # Detect a Python installation lacking Tcl/Tk before running the packager.
        import tkinter
        del tkinter
        output.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["STAFFBOT_BUILD_CONSOLE"] = "1" if args.console else "0"
        subprocess.run(build_command(output, work), cwd=ROOT, env=environment, check=True)
        executable = output / "StaffEntryBot.exe"
        if not executable.is_file():
            raise ValueError("PyInstaller returned without producing StaffEntryBot.exe.")
        report = output / "bundle_check.json"
        report.unlink(missing_ok=True)
        print("Checking the packaged EXE, sample file readers, imports, and GUI resources…", flush=True)
        subprocess.run([str(executable), "--self-test", "--report", str(report)], cwd=output,
                       check=True, timeout=60)
        checks = json.loads(report.read_text(encoding="utf-8"))
        if not checks.get("ok") or not checks.get("frozen"):
            raise ValueError("The packaged executable failed its bundle check. Inspect dist/bundle_check.json.")
        with executable.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        (output / "StaffEntryBot.exe.sha256").write_text(f"{digest}  StaffEntryBot.exe\n", encoding="utf-8")
        shutil.copyfile(ROOT / "BUILD_EXE.md", output / "BUILD_EXE.md")
        print(f"EXE ready: {executable}\n"
              f"Build computer: {platform.system()} {platform.machine()} / Python {platform.python_version()}\n"
              "Copy StaffEntryBot.exe to another matching Windows computer. Python is not needed to run it.")
        return 0
    except importlib.metadata.PackageNotFoundError:
        print("Install requirements-build.txt first, or install the prepared --include-build offline bundle.", file=sys.stderr)
        return 1
    except (ImportError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"EXE build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
