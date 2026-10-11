# Build StaffEntryBot.exe — version 1.1.0

The project now includes a one-file, windowed Windows build. Its output is:

```text
dist/StaffEntryBot.exe
```

Copy this EXE to a matching Windows computer and double-click it. Python,
pip, the wheelhouse, and your Python installer are **not needed to run the
built EXE**. Your input files remain separate so you can select new TXT,
DOCX, or Excel files whenever needed. A remote staff system still needs its
own network connection.

## Build online on your Windows computer

1. Download or pull this version of the repository.
2. Install full **64-bit CPython**, including pip and Tcl/Tk. Use Python **3.13**
   to match the runtime wheelhouse currently stored in this repository.
3. Double-click `build_exe_windows.bat`.
4. Wait for the build and packaged-app check to complete.
5. Open `dist/StaffEntryBot.exe` and test one record in the practice workspace.

The batch script creates `.venv` when needed, installs `requirements-build.txt`,
checks dependencies, and runs the builder. If you already have a working `.venv`,
it uses that interpreter.

Equivalent PowerShell commands, starting in the repository folder:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install --find-links wheelhouse -r requirements-build.txt
.venv\Scripts\python.exe scripts\build_windows.py
```

The compiler step uses `StaffEntryBot.spec`. It includes the dynamic Word/Excel
readers, the Windows pynput backend, Tcl/Tk, sample data, and the practice form.
Installers, wheels, development tests, screenshots, and personal staff files
are not embedded.

## Additional Python packages for EXE creation

`requirements-build.txt` includes the existing runtime requirements and adds:

| Package | Pinned version | Purpose |
| --- | --- | --- |
| `pyinstaller` | 6.22.3 | Bundle Python, libraries, and the app into a Windows EXE |
| `pyinstaller-hooks-contrib` | 2026.8 | Additional package collection hooks |

The dependency resolver also collects build dependencies such as `altgraph`,
`packaging`, `pefile`, `pywin32-ctypes`, and `setuptools`. Their exact versions
are recorded when the offline build package folder is prepared. Do not collect
only the two packages in the table and omit their dependencies.

Official references:

- https://pypi.org/project/pyinstaller/
- https://pypi.org/project/pyinstaller-hooks-contrib/
- https://pyinstaller.org/en/stable/usage.html
- https://pyinstaller.org/en/stable/runtime-information.html

## Prepare an offline EXE build

While connected, run `prepare_exe_offline_windows.bat`. It creates a separate
`wheelhouse-build/` folder containing **runtime plus build** dependencies, a
version lock, checksums, and an environment manifest. It can reuse compatible
runtime wheels from your existing `wheelhouse/` folder.

Keep the entire project, `wheelhouse-build/`, and a matching Python installer
on disk or USB. When disconnected, run `build_exe_offline_windows.bat`. The
installer validates the bundle and installs exclusively from local wheels;
PyInstaller then builds the EXE without package downloads.

To choose Python 3.13 explicitly rather than the launcher's newest installed
Python version:

```powershell
# While online:
py -3.13 scripts\prepare_offline.py --include-build

# Later, while offline:
py -3.13 scripts\install_offline.py --include-build
.venv\Scripts\python.exe scripts\build_windows.py
```

The existing runtime-only wheelhouse is insufficient for compiling an EXE
until the build tools have also been collected. If you use a different Python
version or CPU architecture, prepare the build bundle using that matching
interpreter. The installer rejects an existing virtual environment with a
different Python major/minor version; choose a fresh `--venv` folder in that case.

### Current installer/package mismatch

The repository's current `wheelhouse/offline_manifest.json` identifies
**Windows AMD64 / CPython 3.13**, including an `lxml` wheel tagged `cp313`.
The saved Windows installer archive is named `python-3.12.10-amd64.rar`.
Python 3.12 cannot install the CPython 3.13 lxml wheel.

Use a matching Python 3.13 Windows installer, or keep your Python 3.12 installer
and prepare a new bundle using `py -3.12` instead. Existing uploaded packages
and installer archives remain in the repository; the update adds a separate
build-package route without deleting them.

## Build and download through GitHub

The repository includes **Windows EXE** under GitHub Actions. It:

1. Runs on a Windows x64 runner with Python 3.13.
2. Installs runtime/build packages and runs the tests.
3. Prepares the complete offline build dependency folder.
4. Builds `StaffEntryBot.exe` and runs its packaged-app smoke check.
5. Uploads two downloadable artifacts:
   - `StaffEntryBot-Windows-x64`: executable, SHA-256 checksum, smoke-check
     report, and this guide.
   - `StaffEntryBot-offline-build-Windows-x64-Python313`: complete offline
     runtime/build wheels, version lock, and manifest.

Open **Actions → Windows EXE → a successful run → Artifacts** and download
the artifact you need. Extract the EXE artifact and open `StaffEntryBot.exe`.
For offline rebuilding, extract the package artifact into `wheelhouse-build/`
inside a copy of this source version.

Builds run for pull requests, pushes to `master`, and `v*` tags. After this
workflow is on the default branch, **Run workflow** can also start it manually.
Artifacts are retained for 90 days, so download and keep them for offline use.
GitHub builds need internet; running a downloaded EXE does not.

## Packaged behavior and checks

- Log files persist at `%LOCALAPPDATA%\StaffEntryBot\logs` on Windows.
  They are not written inside the one-file bundle's temporary extraction folder.
- The practice form launches through `StaffEntryBot.exe --practice` as a
  separate instance and can remain open after the main window closes.
- Startup errors are shown in a dialog and saved in the user's log folder
  when the EXE has no console.
- The build invokes `--self-test --report ...`, checking TXT/DOCX/XLSX sample
  readers, leading zeros, Unicode, dynamic imports, the practice launcher,
  persistent-log routing, and real Tk workspace construction on Windows.
- A checksum file and `bundle_check.json` are placed alongside the EXE.
- Native input into your real staff system still needs a one-record check.
  Its Save/Next sequence and validation rules remain specific to that system.

For a troubleshooting build with a console:

```powershell
.venv\Scripts\python.exe scripts\build_windows.py --console
```

PyInstaller builds for the operating system where it runs. Create the Windows
EXE on Windows or through the Windows GitHub runner. macOS/Linux users can
continue using the Python source; a Windows EXE does not run natively on those
platforms.
