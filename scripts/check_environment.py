"""Read-only local diagnostics. No typing, clicking, or network requests."""
import importlib.metadata
import importlib.util
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    print(f"Python {platform.python_version()} | {platform.system()} | {platform.machine()}")
    missing = []
    for package, module in [("python-docx", "docx"), ("openpyxl", "openpyxl"), ("xlrd", "xlrd"),
                            ("pynput", "pynput"), ("pyperclip", "pyperclip"), ("defusedxml", "defusedxml")]:
        try:
            version = importlib.metadata.version(package)
            print(f"OK  {package} {version}")
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
            print(f"MISSING  {package}")
    if importlib.util.find_spec("tkinter") is None:
        missing.append("tkinter (install with Python / OS package manager)")
        print("MISSING  tkinter")
    else:
        print("OK  tkinter found (a working graphical desktop is still required)")
    if missing:
        print("\nInstall dependencies before using the desktop app.")
        return 1
    if "--desktop" in sys.argv:
        try:
            from staffbot.desktop import PynputBackend, enable_dpi_awareness
            enable_dpi_awareness()
            backend = PynputBackend()
            backend.focus.active()
            backend.clipboard_get()  # Deliberately do not print clipboard contents.
            backend.close()
            print("OK  desktop focus and clipboard access")
        except Exception as exc:
            print(f"DESKTOP SETUP NEEDED  {exc}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
