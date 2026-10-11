# Staff Entry Bot

**Version 1.1.0 adds a standalone Windows EXE build.** Double-click
`build_exe_windows.bat` to create `dist/StaffEntryBot.exe`, or download a build
from **Actions → Windows EXE → Artifacts**. For the complete package list,
offline build instructions, and the current Python 3.12 installer / Python
3.13 wheelhouse mismatch, read [BUILD_EXE.md](BUILD_EXE.md).

A local Python desktop app that reads staff data from Notepad, Word, or Excel,
turns each record into text fields, and pastes those fields into the window you
point at. No fixed employee schema and no database credentials are required.

**The destination must accept clipboard paste and have a predictable field order.**
Configure the order and Save/Next keys for your particular system. The bot fills
the visible form; the staff application performs any database save. The bot
cannot confirm server validation or database commits. Start with the included
practice form, then one record in your real system.

## Quick start on Windows

1. Install **64-bit CPython 3.12** from https://www.python.org/downloads/.
   Include pip, the Python launcher, and Tcl/Tk. Python 3.11+ is supported;
   development checks were run on Python 3.12.
2. Unzip this project into a writable folder.
3. While connected, run `install_online_windows.bat`.
4. Run `run_windows.bat`.
5. Click **Browse files** to open your data, or **Explore with sample data**
   to try `examples/staff_spaces.txt`. Check the **Import & preview** workspace.
6. Click **Open practice form**. Click its Employee ID field, keep the mouse
   over that field, then release **F8** to capture the destination.
7. Click **Start entry** in the bot, or release **F9** in the practice form.
   Windows brings the locked destination forward before the countdown. The bot fills one row.
   Check the fields and click **Save record** manually.
8. For a practice batch, set **Rows to fill** to `0`, and **Keys after each
   record** to `tab,enter`. This activates the practice form's Save button.
   Keep the form at the same position and start again using the locked destination.

Use **Esc** or move the pointer to the top-left screen corner to stop. Focus
changes stop the next action. A stopped record may already be partly filled or
saved; check it before rerunning. There is no automatic retry or rollback.

On Windows, Start activates the exact captured window once, restoring it if
minimized. If Windows refuses activation, click that window and press F9 to
retry. On macOS and Linux/X11, activate the destination manually during the
countdown. Some laptops need Fn+F8 / Fn+F9. If your target uses these shortcuts
itself, test capture on a practice window first.

## Desktop workspace

Use the sidebar to move between **Import & preview**, **Target & entry**, and
**Activity**. The session overview shows record and field counts and the three
readiness checks: a current preview, a captured destination, and desktop controls.
**Start entry** becomes available when all three are ready. Import and setup
controls stay disabled during entry; **Stop** remains available.

The source card keeps separator and header settings close to your file. Open
**Import settings** for encoding, custom separators, Excel sheets, and field
order. Changing an import setting clears the old preview, so you can check the
new result before entry. **Timing settings** in Target & entry contains the
field, paste, and record delays. **Save setup** and **Load setup** are in the
top bar and remain compatible with existing setup JSON files.

The first **F8** capture locks the destination window and first-field position
for the whole app session. Further F8 presses, loading a setup, changing the
source file, and completing or stopping a run keep that destination. To switch
windows or update the captured field position, click **Change destination** in
Target & entry, then capture the new first field with F8. This control is
disabled during entry. Closing the app ends the session; a new session needs
a new capture. Setup files never store the destination. If the captured window
closes, use **Change destination** to capture its replacement. Windows activation
also checks the captured process identity; it never searches for another window
by title. Entry does not bring the window forward again after the initial
activation: subsequent focus changes stop entry.

Activity shows run progress, pasted-record counts, and completion or stop
details. Pasted counts are not confirmation of database saves. Smaller windows
use a compact layout; the destination settings scroll vertically. The redesign
uses the existing Tk installation and adds no runtime dependencies.

For a visual preview without desktop entry or global hotkeys:

```powershell
.venv\Scripts\python.exe scripts/preview_ui.py
```

On Windows, add `--screenshots artifacts/ui` to capture the empty workspace,
sample preview, import settings, destination, activity, and compact layouts.

## Input formats and text rules

| Input | How records and fields are read |
| --- | --- |
| `.txt` | One nonblank line per record; spaces separate fields by default |
| `.csv`, `.tsv` | Choose comma or tab; GUI Browse selects the matching separator |
| `.docx` paragraphs | One nonblank paragraph line per record; selected text separator |
| `.docx` tables | One table row per record, one cell per field, in document body order |
| `.xlsx`, `.xlsm` | One worksheet row per record, one cell per field; macros are not executed |
| `.xls` | Legacy Excel via xlrd; uses saved cell values |
| `.doc` | Save as `.docx` in Word or LibreOffice before importing |

Notepad/Word example:

```text
001 "Mary Jane" Accounting mary@example.com
002 "John O'Neil" Engineering john@example.com
003 "José García" Operations jose@example.com
```

Each line above has four fields. Double quotes keep spaces inside a field;
`""` represents an empty field, and doubled quotes inside a quoted field
represent a literal quote. Ordinary apostrophes and Windows backslashes survive.

For unquoted full names, choose another separator, for example `|`:

```text
001|Mary Jane|Accounting|mary@example.com
002|John O'Neil|Engineering|john@example.com
```

- Every output field is a **Python string**. The app does not guess which field
  is an ID, date, phone number, department, or email address.
- Text such as `001` remains `001`. For Excel IDs/phone numbers, store the
  original cells as **Text** before entry. Simple number formats such as `000`
  are also supported, but digits Excel already discarded cannot be recovered.
- Excel numeric integers become `123`, not `123.0`. Date cells become ISO text.
  Currency, percentage, scientific, and locale display formats are not recreated.
  Use source Text cells when exact display is required.
- Excel formulas use the last saved result. Missing results and Excel error
  cells block import; recalculate and save in Excel/LibreOffice first. XLS cannot
  check whether a saved formula result is current.
- Empty Excel fields remain empty. Entirely blank rows and unused rightmost
  columns are omitted. Rows must have consistent field counts.
- Auto text decoding supports UTF-8 and UTF-16 with a BOM. Select another
  encoding explicitly for older Notepad files.
- Word headers, footers, text boxes, pictures, nested tables, and tracked
  changes are outside this reader's scope. Unmerge table cells first.
- Embedded line breaks/tabs inside individual fields block form entry. Replace
  them with spaces in the source. Tabs/newlines as separators are supported.

## Adapting the destination form

1. Preview the source and use **Field order** to select/reorder columns:
   `2,1,4` means source field 2, then 1, then 4. Blank uses all fields.
2. Skip the first data row if it is a header. Enter an Excel sheet name if the
   first sheet is not the sheet you want.
3. Choose **Form fields** to paste one field at a time, moving with Tab, or
   **Text block** to paste selected records into one multiline control.
4. For four destination fields, the default is one Tab between fields. If an
   unrelated control occurs between fields 3 and 4, use `1,1,2`.
5. Set **Keys after each record** to your application's actual Save/Next
   sequence. Supported actions: `tab`, `shift+tab`, `enter`, `ctrl+s`, `cmd+s`.
   These keys also run after the last record. Blank means manual saving;
   batch form mode requires a sequence before allowing multiple records.
6. Increase field/paste/record delays if your staff system is slow. A fixed
   delay does not confirm that Save succeeded.
7. **Replace existing field text** selects all before pasting. Use it only in
   an ordinary text input. Date pickers, dropdowns, rich text editors, dynamic
   forms, and controls that reject paste may need a system-specific adapter.
8. Save a setup JSON to reuse these settings. It excludes employee data,
   input filename, coordinates, and target identity. Recapture each session.

The foreground guard checks window identity on Windows and X11. On macOS it
checks the active application, so changing windows within that app is not
detected. It does not verify the focused field, page/tab, or form layout. Keep
the destination in front and avoid manual input while running. If you move,
resize, scroll, or change the destination, choose **Change destination** and
capture its first field again. If saving opens a dialog
or new window, entry stops and may need a custom workflow.

Run journals under `logs/` record row/field numbers and unverified paste
statuses. Staff values are not logged. Previous **text** clipboard content is
restored; non-text clipboard formats are not preserved. A force-killed process
may leave the most recently pasted text on the clipboard.

## Required Python packages

| Package | Pinned version | Purpose |
| --- | --- | --- |
| `python-docx` | 1.2.0 | Read Word DOCX paragraphs and tables |
| `openpyxl` | 3.1.5 | Read Excel XLSX/XLSM |
| `xlrd` | 2.0.2 | Read older XLS files |
| `pynput` | 1.8.2 | Mouse/keyboard control and F8/F9/Esc hotkeys |
| `pyperclip` | 1.11.0 | Paste Unicode text through the local clipboard |
| `defusedxml` | 0.7.1 | XML parser support for openpyxl |

`tkinter`, `csv`, `json`, `threading`, `ctypes`, and the other standard modules
come from Python, not pip. Install Tcl/Tk with your Python/OS installation.
Transitive dependencies include `lxml`, `typing_extensions`, `et-xmlfile`,
`six`, and platform-specific pynput packages. **Do not download only the six
packages above**: the preparation script collects their dependency tree.

### Prepare now, install later without internet

The supplied ZIP contains source, examples, and setup scripts. **It does not
contain dependency wheels or a Python installer.** Complete this step while
you have a connection. Use the same OS, CPU architecture, and Python major/minor
version as the offline computer. Prepare separate bundles for Windows, macOS,
and Ubuntu; Windows wheels do not install on macOS or Linux.

On Windows, run `prepare_offline_windows.bat`, or run:

```powershell
py -3.12 scripts/prepare_offline.py
```

On macOS/Ubuntu:

```bash
python3 scripts/prepare_offline.py
```

The script builds/downloads all runtime wheels into `wheelhouse/`, tests package
resolution using `--no-index`, locks every resolved version, and records file
checksums and the target environment. It retries slow downloads. Run again
after a connection failure; existing completed wheels can be reused.

Keep these items on disk or a USB drive:

- This complete project, including its prepared `wheelhouse/` folder.
- The matching Python installer, including pip and Tcl/Tk.
- Your staff input files and any saved form setup JSON.
- On Linux: preinstalled desktop/system packages described below. They are
  **not** included in pip wheels.

While offline on Windows, run `install_offline_windows.bat`, or:

```powershell
py -3.12 scripts/install_offline.py
.venv\Scripts\python.exe main.py
```

While offline on macOS/Ubuntu:

```bash
python3 scripts/install_offline.py
.venv/bin/python main.py
```

The offline installer verifies the OS/CPU/Python version and checksums, creates
`.venv`, installs only from local wheels, and runs `pip check`. It makes no
package-index requests. Recreate the virtual environment after copying the
project to another computer; virtual environments are not portable.

**The bot itself works offline after setup.** Your destination staff system
still needs its own server/network access if it is a web or remote application.

### macOS setup

Use a Python installation that includes Tk. Before going offline, install the
requirements normally or prepare the wheelhouse on a matching Mac. Pynput
installs its macOS PyObjC dependencies.

Grant **Accessibility** and **Input Monitoring** to the Python/Terminal app
under System Settings → Privacy & Security, then restart the bot. A Mac's
default media keys may require Fn with F8/F9.

Online installation:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

### Ubuntu setup

Use a local graphical **X11/Xorg** session. Wayland is not supported by this
implementation. From the login screen, select **Ubuntu on Xorg**.

Install these system packages while online:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-tk xclip x11-utils build-essential python3-dev
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

`xclip` supplies clipboard access and `x11-utils` supplies `xprop` for the focus
guard. Build tools may be needed to prepare an evdev wheel. An offline Ubuntu
computer must already have these packages; copying Python wheels alone does
not install operating-system packages. The graphical session must stay open.

## Preview/export without desktop automation

You can inspect or export files even without desktop-control packages:

```bash
python3 main.py --preview examples/staff_spaces.txt
python3 main.py --preview examples/staff.csv --separator comma --skip-header
python3 main.py --preview examples/staff.xlsx --skip-header --columns 2,1,4
python3 main.py --preview examples/staff_spaces.txt --export staff_text.csv
```

The exported UTF-8 CSV uses generic names `field_1`, `field_2`, etc. If the staff
system supports a CSV importer, you can map these columns there manually.

## Diagnostics and checks

```bash
python3 scripts/check_environment.py
python3 scripts/check_environment.py --desktop
python3 -m unittest discover -s tests -v
```

On Windows, use `.venv\Scripts\python.exe` in place of `python3`.
File-reader tests use real DOCX/XLSX fixtures. Engine tests use a simulated
desktop to verify focus-loss stops, cancellation, navigation, Unicode paste,
and clipboard restoration. Offline tests check dependency locking, local-only
install commands, environment mismatch, and changed/missing package detection.
UI tests exercise the real Tk controls with simulated desktop actions and
temporary files, including preview invalidation, setup reuse, complete exports,
run results, and the practice form's Tab/Enter workflow. They skip on machines
without a working Tk display.

Native mouse/keyboard actions and your actual staff form must be checked on
your computer; they cannot be exercised on a server without a graphical desktop.

## Files

- `main.py`: GUI launcher and read-only command-line preview/export.
- `staffbot/readers.py`: configurable readers and all-text representation.
- `staffbot/engine.py`: cancellable, focus-checked form entry and status journal.
- `staffbot/desktop.py`: native focus inspection, clipboard, and desktop controls.
- `staffbot/gui.py`: preview, setup, capture, entry, and profile controls.
- `staffbot/ui.py`: native workspace layout and interface states.
- `staffbot/ui_theme.py`: shared colors, typography, and control styles.
- `demo_form.py`: disposable staff-registration practice destination.
- `scripts/`: offline preparation/installation and environment diagnostics.
- `examples/`: sample TXT, CSV, DOCX, XLSX, and form setup.
- `tests/`: standard-library unittest checks; pytest is not required.

No cloud API, AI model, database server, or internet service is used by the bot.
