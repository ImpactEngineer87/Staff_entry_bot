# Run on Windows with: python -m PyInstaller --clean --noconfirm StaffEntryBot.spec
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH)
datas = [(str(root / "examples"), "examples"), (str(root / "BUILD_EXE.md"), ".")]
datas += collect_data_files("docx")
for package in ("python-docx", "openpyxl", "xlrd", "pynput", "pyperclip", "defusedxml"):
    datas += copy_metadata(package)

# readers._dependency and pynput select modules dynamically at runtime.
hiddenimports = ["docx", "openpyxl", "xlrd", "pyperclip", "defusedxml",
                 "pynput.keyboard._win32", "pynput.mouse._win32", "pynput._util.win32"]

analysis = Analysis([str(root / "main.py")], pathex=[str(root)], binaries=[], datas=datas,
                    hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[],
                    excludes=[], noarchive=False)
python_archive = PYZ(analysis.pure)
executable = EXE(python_archive, analysis.scripts, analysis.binaries, analysis.datas, [],
                 name="StaffEntryBot", debug=False, bootloader_ignore_signals=False,
                 strip=False, upx=False, console=os.environ.get("STAFFBOT_BUILD_CONSOLE") == "1",
                 disable_windowed_traceback=False)
