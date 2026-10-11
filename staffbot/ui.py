"""Native workspace layout, kept separate from file and automation behavior."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .ui_theme import PALETTE as C, apply_window_icon, configure_theme


class WorkspaceUI:
    def _label(self, parent, text="", *, variable=None, color=None, size=10, bold=False,
               bg=None, **kwargs):
        kwargs.setdefault("anchor", "w")
        label = tk.Label(parent, text=text, textvariable=variable, background=bg or parent.cget("background"),
                         foreground=color or C["ink"], font=("Segoe UI", size, "bold" if bold else "normal"),
                         borderwidth=0, **kwargs)
        return label

    def _card(self, parent, padding=20, bg=None):
        return tk.Frame(parent, background=bg or C["surface"], padx=padding, pady=padding,
                        highlightbackground=C["border"], highlightthickness=1, borderwidth=0)

    def _button(self, parent, text, command, style="Secondary.TButton", editable=False, **kwargs):
        button = ttk.Button(parent, text=text, command=command, style=style, cursor="hand2", **kwargs)
        if editable:
            self.edit_controls.append((button, "normal"))
        return button

    def _icon(self, parent, kind, *, size=40, bg=None, color=None):
        bg = bg or parent.cget("background")
        color = color or C["accent"]
        icon = tk.Canvas(parent, width=size, height=size, background=bg, highlightthickness=0)
        scale = size / 40
        def line(*points, **kwargs):
            return icon.create_line(*(p * scale for p in points), fill=color, width=max(1.5, 2 * scale),
                                    capstyle="round", joinstyle="round", **kwargs)
        if kind == "file":
            line(11, 5, 25, 5, 31, 11, 31, 35, 11, 35, 11, 5)
            line(25, 5, 25, 12, 31, 12)
            line(16, 20, 26, 20)
            line(16, 26, 26, 26)
        elif kind == "target":
            icon.create_oval(7*scale, 7*scale, 33*scale, 33*scale, outline=color, width=2*scale)
            icon.create_oval(15*scale, 15*scale, 25*scale, 25*scale, outline=color, width=2*scale)
            for points in ((20, 2, 20, 10), (20, 30, 20, 38), (2, 20, 10, 20), (30, 20, 38, 20)):
                line(*points)
        elif kind == "activity":
            line(5, 22, 12, 22, 17, 11, 23, 30, 28, 19, 35, 19)
        elif kind == "shield":
            line(20, 5, 32, 10, 32, 23, 28, 30, 20, 36, 12, 30, 8, 23, 8, 10, 20, 5)
            line(14, 21, 18, 25, 26, 16)
        elif kind == "logo":
            for x, y, height in ((6, 20, 14), (16, 12, 22), (26, 5, 29)):
                icon.create_rectangle(x*scale, y*scale, (x+6)*scale, (y+height)*scale,
                                      fill=color, outline="")
        return icon

    def _build(self):
        configure_theme(self)
        apply_window_icon(self)
        self._variables()
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_sidebar()
        shell = tk.Frame(self, background=C["bg"])
        shell.grid(row=0, column=1, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(2, weight=1)
        self._build_topbar(shell)

        heading = tk.Frame(shell, background=C["bg"], padx=28, pady=18)
        self.heading_frame = heading
        heading.grid(row=1, column=0, sticky="ew")
        self.page_eyebrow = self._label(heading, "YOUR WORKSPACE", color=C["muted"], size=9, bold=True)
        self.page_eyebrow.pack(anchor="w")
        self.page_title = self._label(heading, "Import & preview", size=25, bold=True)
        self.page_title.pack(anchor="w", pady=(5, 3))
        self.page_description = self._label(heading, "Great data entry starts with a clear view of your data.",
                                            color=C["muted"])
        self.page_description.pack(anchor="w")

        content = tk.Frame(shell, background=C["bg"])
        content.grid(row=2, column=0, sticky="nsew", padx=28, pady=(0, 16))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)
        self._build_steps(content)
        self.page_host = tk.Frame(content, background=C["bg"])
        self.page_host.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        self.page_host.columnconfigure(0, weight=1)
        self.page_host.rowconfigure(0, weight=1)
        self.pages = {name: tk.Frame(self.page_host, background=C["bg"])
                      for name in ("file", "target", "activity")}
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self._build_file_page(self.pages["file"])
        self._build_target_page(self.pages["target"])
        self._build_activity_page(self.pages["activity"])
        self._build_session_panel(content)
        self._build_footer(shell)
        self._show_page("file")
        for variable in (self.file, self.separator, self.custom, self.encoding, self.sheet,
                         self.columns, self.skip_header):
            variable.trace_add("write", self._invalidate_preview)
        self.mode.trace_add("write", self._mode_changed)
        self._mode_changed()
        self._refresh_readiness()
        self.bind("<Configure>", self._responsive, add="+")
        self.bind("<MouseWheel>", self._scroll_target, add="+")
        self.bind("<Button-4>", lambda event: self._scroll_target(event, -1), add="+")
        self.bind("<Button-5>", lambda event: self._scroll_target(event, 1), add="+")

    def _variables(self):
        defaults = {"file": "", "separator": next(iter(self.separator_choices)), "custom": "|",
                    "encoding": "auto", "sheet": "", "columns": "", "mode": "Form fields",
                    "start_row": "1", "row_limit": "1", "countdown": "3", "field_delay": "0.25",
                    "paste_delay": "0.15", "row_delay": "1", "tab_counts": "", "after_row": "",
                    "block_separator": "Tab"}
        for name, value in defaults.items():
            setattr(self, name, tk.StringVar(self, value=value))
        self.skip_header = tk.BooleanVar(self, value=False)
        self.replace_fields = tk.BooleanVar(self, value=False)
        self.profile_vars = {name: getattr(self, name) for name in defaults if name != "file"}
        self.profile_vars.update(skip_header=self.skip_header, replace_fields=self.replace_fields)
        for name, value in {"summary": "Your records will appear here once you preview a file.",
                            "notes": "Values stay as text, including leading zeros and special characters.",
                            "target_text": "No destination captured yet",
                            "target_lock_status": "AWAITING CAPTURE",
                            "desktop_status": "Checking desktop controls…",
                            "status": "Choose a source file to get started.",
                            "source_name": "Choose your source file",
                            "source_detail": "Spreadsheets, documents and plain text. All in one place.",
                            "row_count": "—", "field_count": "—",
                            "preview_badge": "AWAITING FILE", "activity_count": "0 events",
                            "run_result": "No runs yet", "run_detail": "Your next run will appear here.",
                            "run_count": "—", "run_state": "READY WHEN YOU ARE"}.items():
            setattr(self, name, tk.StringVar(self, value=value))
        self.progress = tk.DoubleVar(self, value=0)
        self.activity_events = 0

    def _build_sidebar(self):
        sidebar = tk.Frame(self, background=C["navy"], width=208)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(3, weight=1)
        brand = tk.Frame(sidebar, background=C["navy"])
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(26, 36))
        self._icon(brand, "logo", size=32, color="#7ad4bc").pack(side="left", padx=(0, 8))
        names = tk.Frame(brand, background=C["navy"])
        names.pack(side="left")
        self._label(names, "Staff Entry", color="white", size=15, bold=True).pack(anchor="w")
        self._label(names, "BOT / DESKTOP", color=C["sidebar_text"], size=8).pack(anchor="w", pady=(1, 0))
        self._label(sidebar, "WORKSPACE", color="#6f909c", size=8, bold=True).grid(
            row=1, column=0, sticky="w", padx=26, pady=(0, 12))
        navigation = tk.Frame(sidebar, background=C["navy"])
        navigation.grid(row=2, column=0, sticky="ew", padx=12)
        self.nav_buttons = {}
        for page, symbol, text in (("file", "▤", "Import & preview"), ("target", "◎", "Target & entry"),
                                    ("activity", "≋", "Activity")):
            button = tk.Button(navigation, text=f"{symbol}    {text}", command=lambda p=page: self._show_page(p),
                               font=("Segoe UI", 10), foreground=C["sidebar_text"], background=C["navy"],
                               activebackground="#1e414a", activeforeground="white", anchor="w",
                               relief="flat", borderwidth=0, padx=14, pady=13, cursor="hand2",
                               highlightthickness=1, highlightbackground=C["navy"], highlightcolor="#7ad4bc")
            button.pack(fill="x", pady=3)
            self.nav_buttons[page] = button

        bottom = tk.Frame(sidebar, background=C["navy"])
        bottom.grid(row=4, column=0, sticky="ew", padx=22, pady=24)
        tk.Frame(bottom, background="#2a4650", height=1).pack(fill="x", pady=(0, 18))
        self._label(bottom, "A LITTLE PRACTICE GOES FAR", color="#7ad4bc", size=8, bold=True).pack(anchor="w")
        self._label(bottom, "Test your workflow with\nthe included practice form.", color=C["sidebar_text"],
                    size=9, justify="left", pady=8).pack(anchor="w")
        self.practice_button = tk.Button(bottom, text="Open practice form  ↗", command=self._demo,
                                        background="#24444d", foreground="white", activebackground="#31545e",
                                        activeforeground="white", font=("Segoe UI", 9), cursor="hand2",
                                        borderwidth=0, padx=10, pady=10, highlightthickness=0)
        self.practice_button.pack(fill="x", pady=(2, 24))
        self.edit_controls.append((self.practice_button, "normal"))
        self._label(bottom, "●  Runs on your computer", color="#9abbb8", size=9).pack(anchor="w")
        self._label(bottom, "Local files. No cloud uploads.", color="#6f909c", size=8).pack(anchor="w", pady=(4, 0))

    def _build_topbar(self, shell):
        top = tk.Frame(shell, background="white", padx=28, pady=14,
                       highlightbackground=C["border"], highlightthickness=1)
        top.grid(row=0, column=0, sticky="ew")
        self._label(top, "Workspace", size=10, bold=True).pack(side="left")
        self._label(top, "  /  Staff operations", color=C["muted"], size=9).pack(side="left")
        self._button(top, "Save setup", self._save_profile, editable=True).pack(side="right")
        self._button(top, "Load setup", self._load_profile, "CardGhost.TButton", editable=True).pack(
            side="right", padx=(0, 8))

    def _build_steps(self, content):
        rail = tk.Frame(content, background="white", padx=16, pady=12,
                        highlightbackground=C["border"], highlightthickness=1)
        rail.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.step_labels = {}
        for index, (page, title) in enumerate((("file", "Import data"), ("target", "Set destination"),
                                              ("activity", "Run & review"))):
            rail.columnconfigure(index * 2, weight=1)
            item = tk.Frame(rail, background="white")
            item.grid(row=0, column=index * 2, sticky="ew")
            circle = self._label(item, f"0{index + 1}", size=9, bold=True, padx=8, pady=4,
                                 color=C["muted"], bg="#f0f3f5")
            circle.pack(side="left", padx=(0, 10))
            text = self._label(item, title, size=10, bold=True)
            text.pack(side="left")
            for widget in (circle, text, item):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda event, p=page: self._show_page(p))
            self.step_labels[page] = (circle, text)
            if index < 2:
                self._label(rail, "→", color="#becbd0").grid(row=0, column=index * 2 + 1, padx=16)

    def _build_file_page(self, page):
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        source = self._card(page, padding=16)
        self.source_card = source
        source.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        source.columnconfigure(1, weight=1)
        tile = tk.Frame(source, background=C["tint"], padx=10, pady=10)
        tile.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="n")
        self._icon(tile, "file", size=32).pack()
        self._label(source, variable=self.source_name, size=13, bold=True).grid(row=0, column=1, sticky="w")
        self._label(source, variable=self.source_detail, color=C["muted"], size=9).grid(
            row=1, column=1, sticky="w", pady=(3, 10))
        self._button(source, "Browse files", self._browse, "Primary.TButton", editable=True).grid(
            row=0, column=2, rowspan=2, sticky="e", padx=(12, 0))
        self.file_entry = ttk.Entry(source, textvariable=self.file)
        self.file_entry.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(2, 8))
        self.edit_controls.append((self.file_entry, "normal"))
        self.file_entry.bind("<Return>", lambda event: self._preview())
        self.formats_label = self._label(source, "TXT  ·  CSV  ·  TSV  ·  WORD  ·  EXCEL", color=C["muted"], size=8)
        self.formats_label.grid(row=3, column=0, columnspan=3, sticky="w")
        option_bar = tk.Frame(source, background="white")
        option_bar.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self._label(option_bar, "Text separator", size=9).pack(side="left", padx=(0, 8))
        combo = ttk.Combobox(option_bar, textvariable=self.separator, values=list(self.separator_choices),
                             state="readonly", width=29)
        combo.pack(side="left")
        self.edit_controls.append((combo, "readonly"))
        self.options_button = self._button(option_bar, "Import settings  ↗", self._toggle_import,
                                            "CardGhost.TButton")
        self.options_button.pack(side="right", padx=(8, 0))
        header_check = ttk.Checkbutton(option_bar, text="First row is a header", variable=self.skip_header,
                                       style="Card.TCheckbutton")
        header_check.pack(side="left", padx=(12, 0))
        self.edit_controls.append((header_check, "normal"))
        self.import_window = tk.Toplevel(self)
        self.import_window.withdraw()
        self.import_window.title("Import settings · Staff Entry Bot")
        self.import_window.configure(background="white")
        self.import_window.resizable(False, False)
        self.import_window.transient(self)
        self.import_window.protocol("WM_DELETE_WINDOW", self._hide_import)
        settings = tk.Frame(self.import_window, background="white", padx=24, pady=22)
        settings.pack(fill="both", expand=True)
        self._label(settings, "Import settings", size=18, bold=True).pack(anchor="w")
        self._label(settings, "Fine-tune how your source file becomes text fields.",
                    size=9, color=C["muted"]).pack(anchor="w", pady=(6, 20))
        path = tk.Frame(settings, background="white")
        path.pack(fill="x", pady=(0, 16))
        self._label(path, "Source file path", size=9, color=C["muted"]).pack(anchor="w", pady=(0, 6))
        path_entry = ttk.Entry(path, textvariable=self.file)
        path_entry.pack(fill="x")
        self.edit_controls.append((path_entry, "normal"))
        self.import_options = tk.Frame(settings, background="white", width=510)
        self.import_options.pack(fill="x")
        self.import_options.columnconfigure((0, 1), weight=1, uniform="import")
        self._field(self.import_options, 0, 0, "Text encoding", self.encoding,
                    choices=["auto", "utf-8-sig", "utf-16", "cp1252", "latin-1"], editable=True)
        self.custom_entry = self._field(self.import_options, 0, 1, "Custom separator", self.custom)
        self._field(self.import_options, 1, 0, "Excel sheet · blank uses the first", self.sheet)
        self._field(self.import_options, 1, 1, "Field order · e.g. 2,1,4", self.columns)
        self.import_expanded = False
        self._label(settings, "Excel and Word tables use one cell per field.\nLeave field order blank to include every column.",
                    size=9, color=C["muted"], justify="left").pack(anchor="w", pady=(0, 20))
        self._button(settings, "Done", self._hide_import, "Primary.TButton").pack(anchor="e")
        self.separator.trace_add("write", self._separator_changed)
        self._separator_changed()

        preview = self._card(page, padding=0)
        preview.grid(row=1, column=0, sticky="nsew")
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(1, weight=1)
        bar = tk.Frame(preview, background="white", padx=18, pady=14)
        bar.grid(row=0, column=0, sticky="ew")
        self._label(bar, "Data preview", size=12, bold=True).pack(side="left")
        self._button(bar, "Preview data", self._preview, editable=True).pack(side="right")
        self.export_button = self._button(bar, "Export CSV", self._export, "CardGhost.TButton", editable=True)
        self.export_button.pack(side="right", padx=(0, 8))
        grid = tk.Frame(preview, background="white")
        grid.grid(row=1, column=0, sticky="nsew")
        grid.rowconfigure(0, weight=1)
        grid.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(grid, show="headings", height=4)
        self.tree.tag_configure("even", background="#f8fafb")
        vertical = ttk.Scrollbar(grid, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(grid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.preview_scrollbars = (vertical, horizontal)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.empty_preview = tk.Frame(grid, background="white")
        self.empty_preview.grid(row=0, column=0, sticky="nsew")
        empty = tk.Frame(self.empty_preview, background="white")
        empty.place(relx=0.5, rely=0.5, anchor="center")
        self.empty_icon = self._icon(empty, "file", size=32, color="#9dbcb8")
        self.empty_icon.pack(pady=(0, 8))
        self.empty_title = self._label(empty, "A clear view before you begin", size=13, bold=True, anchor="center")
        self.empty_title.pack()
        self.empty_description = self._label(empty, "Load a file to review your records and field order.",
                                              color=C["muted"], size=9, anchor="center")
        self.empty_description.pack(pady=(6, 12))
        self.sample_button = self._button(empty, "Explore with sample data  →", self._load_example,
                                          "CardGhost.TButton", editable=True)
        self.sample_button.pack()
        self.empty_preview.bind("<Configure>", self._resize_empty_preview)
        for scrollbar in self.preview_scrollbars:
            scrollbar.grid_remove()
        foot = tk.Frame(preview, background="white", padx=18, pady=12,
                        highlightbackground=C["border"], highlightthickness=1)
        foot.grid(row=2, column=0, sticky="ew")
        self.summary_label = self._label(foot, variable=self.summary, color=C["muted"], size=9)
        self.summary_label.pack(anchor="w")
        self.notes_label = self._label(foot, variable=self.notes, color=C["muted"], size=8, justify="left")
        self.notes_label.pack(anchor="w", pady=(4, 0))

    def _field(self, parent, row, column, title, variable, choices=None, editable=False):
        holder = tk.Frame(parent, background="white")
        holder.grid(row=row, column=column, sticky="ew", padx=(0, 16 if column == 0 else 0), pady=(0, 14))
        self._label(holder, title, size=9, color=C["muted"]).pack(anchor="w", pady=(0, 6))
        if choices:
            state = "normal" if editable else "readonly"
            widget = ttk.Combobox(holder, textvariable=variable, values=choices, state=state, width=12)
        else:
            state = "normal"
            widget = ttk.Entry(holder, textvariable=variable, width=12)
        widget.pack(fill="x")
        self.edit_controls.append((widget, state))
        return widget

    def _build_target_page(self, page):
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        self.target_canvas = tk.Canvas(page, background=C["bg"], highlightthickness=0, borderwidth=0)
        self.target_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=self.target_canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.target_canvas.configure(yscrollcommand=scrollbar.set)
        form = tk.Frame(self.target_canvas, background=C["bg"])
        self.target_window = self.target_canvas.create_window(0, 0, window=form, anchor="nw")
        form.bind("<Configure>", lambda event: self.target_canvas.configure(scrollregion=self.target_canvas.bbox("all")))
        self.target_canvas.bind("<Configure>", lambda event: self.target_canvas.itemconfigure(self.target_window, width=event.width))

        destination = self._card(form)
        destination.pack(fill="x", pady=(0, 16))
        target_heading = tk.Frame(destination, background="white")
        target_heading.pack(fill="x")
        self._label(target_heading, "Connect your destination", size=13, bold=True).pack(side="left")
        self._label(target_heading, variable=self.target_lock_status, size=8, bold=True,
                    color=C["accent"], bg=C["tint"], padx=8, pady=5).pack(side="right")
        self._label(destination, "Capture the first empty field in the staff system you want to fill.",
                    color=C["muted"], size=9, wraplength=570, justify="left").pack(anchor="w", pady=(5, 16))
        instructions = tk.Frame(destination, background=C["tint"], padx=16, pady=12)
        instructions.pack(fill="x")
        self._label(instructions, "01  Open your staff system and click the first empty field.", size=9).pack(anchor="w")
        self._label(instructions, "02  Keep your pointer over that field, then release F8.", size=9).pack(anchor="w", pady=(6, 0))
        self.target_label = self._label(destination, variable=self.target_text, color=C["accent"], size=10,
                                       wraplength=570, justify="left")
        self.target_label.pack(anchor="w", pady=(16, 8))
        self.desktop_label = self._label(destination, variable=self.desktop_status, color=C["muted"], size=9,
                                        wraplength=570, justify="left")
        self.desktop_label.pack(anchor="w")
        target_actions = tk.Frame(destination, background="white")
        target_actions.pack(fill="x", pady=(12, 0))
        self.release_target_button = self._button(target_actions, "Change destination", self._release_target,
                                                   editable=True)
        self.release_target_button.pack(side="left")
        self._button(target_actions, "Retry desktop connection", self._enable_desktop, "CardGhost.TButton",
                     editable=True).pack(side="left", padx=(10, 0))
        self._label(destination, "The first captured window stays locked for this session. Change destination releases it for a new F8 capture.",
                    size=9, color=C["muted"], wraplength=570, justify="left").pack(anchor="w", pady=(12, 0))

        behavior = self._card(form)
        behavior.pack(fill="x", pady=(0, 16))
        self._label(behavior, "Make it fit your workflow", size=13, bold=True).pack(anchor="w")
        self._label(behavior, "Start with one record. Scale up when your field order is right.",
                    color=C["muted"], size=9).pack(anchor="w", pady=(5, 18))
        fields = tk.Frame(behavior, background="white")
        fields.pack(fill="x")
        fields.columnconfigure((0, 1), weight=1, uniform="behavior")
        self._field(fields, 0, 0, "Output mode", self.mode, choices=["Form fields", "Text block"])
        self.block_combo = self._field(fields, 0, 1, "Text block separator", self.block_separator,
                                       choices=["Tab", "Space", "Comma", "Pipe"])
        self._field(fields, 1, 0, "Start at preview row", self.start_row)
        self._field(fields, 1, 1, "Rows to fill · 0 = all records", self.row_limit)
        self._field(fields, 2, 0, "Start countdown · seconds", self.countdown)
        self._field(fields, 2, 1, "Tabs between fields · blank = 1", self.tab_counts)
        self._field(fields, 3, 0, "Keys after each record", self.after_row)
        self._label(fields, "Example: tab,enter to save and continue.\nFor 4 fields, Tab counts can be 1,1,2.",
                    color=C["muted"], size=8, justify="left").grid(row=3, column=1, sticky="w", pady=(6, 14))
        replace = ttk.Checkbutton(behavior, text="Replace existing text before pasting (Ctrl+A / Cmd+A)",
                                  variable=self.replace_fields, style="Card.TCheckbutton")
        replace.pack(anchor="w")
        self.edit_controls.append((replace, "normal"))
        advanced_bar = tk.Frame(behavior, background="white")
        advanced_bar.pack(fill="x", pady=(12, 0))
        self.timing_button = self._button(advanced_bar, "Timing settings  +", self._toggle_timing, "CardGhost.TButton")
        self.timing_button.pack(anchor="w")
        self.timing_options = tk.Frame(behavior, background="white")
        self.timing_options.columnconfigure((0, 1), weight=1, uniform="timing")
        self._field(self.timing_options, 0, 0, "Delay between fields · seconds", self.field_delay)
        self._field(self.timing_options, 0, 1, "Clipboard / paste delay · seconds", self.paste_delay)
        self._field(self.timing_options, 1, 0, "Delay after each record · seconds", self.row_delay)
        self.timing_expanded = False
        tip = self._card(form, padding=16, bg=C["tint"])
        tip.pack(fill="x", pady=(0, 4))
        self._label(tip, "You're in control", size=10, bold=True, color=C["accent"]).pack(anchor="w")
        self._label(tip, "Keep the destination in front and in the same position. Esc or moving the pointer to the top-left corner stops entry. Verify pasted records and save them in your staff system.",
                    color="#52756e", size=9, wraplength=560, justify="left").pack(anchor="w", pady=(6, 0))

    def _build_activity_page(self, page):
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        result = self._card(page)
        result.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self._label(result, variable=self.run_state, size=8, bold=True, color=C["accent"]).pack(anchor="w")
        self._label(result, variable=self.run_result, size=20, bold=True).pack(anchor="w", pady=(8, 4))
        self.run_detail_label = self._label(result, variable=self.run_detail, color=C["muted"], size=9,
                                            wraplength=700, justify="left")
        self.run_detail_label.pack(anchor="w")
        ttk.Progressbar(result, variable=self.progress, maximum=100,
                        style="Accent.Horizontal.TProgressbar").pack(fill="x", pady=(16, 0))
        events = self._card(page, padding=0)
        events.grid(row=1, column=0, sticky="nsew")
        events.columnconfigure(0, weight=1)
        events.rowconfigure(1, weight=1)
        header = tk.Frame(events, background="white", padx=18, pady=14)
        header.grid(row=0, column=0, sticky="ew")
        self._label(header, "Session activity", size=12, bold=True).pack(side="left")
        self._label(header, variable=self.activity_count, color=C["muted"], size=9).pack(side="right")
        body = tk.Frame(events, background="white")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.activity = tk.Text(body, height=5, background="white", foreground=C["ink"],
                                font=("Segoe UI", 10), wrap="word", state="disabled", borderwidth=0,
                                highlightthickness=0, padx=18, pady=10, spacing1=6, spacing3=8,
                                selectbackground=C["tint"], selectforeground=C["ink"])
        self.activity.grid(row=0, column=0, sticky="nsew")
        self.activity.tag_configure("time", foreground="#99a7ae", font=("Consolas", 9))
        self.activity.tag_configure("error", foreground=C["danger"])
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.activity.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.activity.configure(yscrollcommand=scroll.set)
        self._label(events, "Journals record row numbers and statuses. Staff values stay out of logs.",
                    color=C["muted"], size=8, padx=18, pady=12).grid(row=2, column=0, sticky="w")

    def _build_session_panel(self, content):
        self.session_panel = tk.Frame(content, background=C["bg"], width=252)
        self.session_panel.grid(row=1, column=1, sticky="ns", padx=(20, 0), pady=(16, 0))
        self.session_panel.grid_propagate(False)
        self.session_panel.columnconfigure(0, weight=1)
        session = self._card(self.session_panel, padding=16)
        session.grid(row=0, column=0, sticky="ew")
        self._label(session, "SESSION OVERVIEW", size=8, bold=True, color=C["muted"]).pack(anchor="w")
        self.readiness_label = self._label(session, "Let's get you ready", size=13, bold=True)
        self.readiness_label.pack(anchor="w", pady=(9, 12))
        numbers = tk.Frame(session, background="white")
        numbers.pack(fill="x")
        for index, (variable, text) in enumerate(((self.row_count, "RECORDS"), (self.field_count, "FIELDS"))):
            holder = tk.Frame(numbers, background="white")
            holder.pack(side="left", fill="x", expand=True)
            self._label(holder, variable=variable, size=22, bold=True).pack(anchor="w")
            self._label(holder, text, size=8, color=C["muted"]).pack(anchor="w", pady=(2, 0))
        self.badge_label = self._label(session, variable=self.preview_badge, color=C["muted"], size=8,
                                       bold=True, bg="#f2f5f6", padx=8, pady=6)
        self.badge_label.pack(anchor="w", pady=(10, 12))
        tk.Frame(session, background=C["border"], height=1).pack(fill="x", pady=(0, 12))
        self.check_labels = []
        for title in ("Source previewed", "Destination captured", "Desktop connected"):
            label = self._label(session, "○   " + title, color=C["muted"], size=9)
            label.pack(anchor="w", pady=4)
            self.check_labels.append((label, title))
        self.next_button = self._button(session, "Set destination  →", lambda: self._show_page("target"))
        self.next_button.pack(fill="x", pady=(12, 0))
        self._label(session, "Run scope", size=8, color=C["muted"]).pack(anchor="w", pady=(12, 4))
        self._label(session, variable=self.run_count, size=9).pack(anchor="w")
        shortcuts = self._card(self.session_panel, padding=14)
        self.shortcuts_card = shortcuts
        shortcuts.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        self._label(shortcuts, "At your fingertips", size=10, bold=True).pack(anchor="w", pady=(0, 7))
        for key, title in (("F8", "Capture destination"), ("F9", "Start entry"), ("Esc", "Stop immediately")):
            row = tk.Frame(shortcuts, background="white")
            row.pack(fill="x", pady=3)
            self._label(row, key, size=8, bold=True, color="#58707c", bg="#f0f4f5", width=4,
                        anchor="center", pady=1).pack(side="left", padx=(0, 10))
            self._label(row, title, color=C["muted"], size=9).pack(side="left")
        self.row_limit.trace_add("write", lambda *args: self._refresh_scope())
        self.start_row.trace_add("write", lambda *args: self._refresh_scope())
        self._refresh_scope()

    def _build_footer(self, shell):
        footer = tk.Frame(shell, background="white", padx=28, pady=16,
                          highlightbackground=C["border"], highlightthickness=1)
        footer.grid(row=3, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        status = tk.Frame(footer, background="white")
        status.grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.status_title = self._label(status, "●  Ready for your next step", color=C["accent"], size=9, bold=True)
        self.status_title.pack(anchor="w")
        self.status_label = self._label(status, variable=self.status, size=9, color=C["muted"],
                                        wraplength=500, justify="left")
        self.status_label.pack(anchor="w", pady=(4, 0))
        self.stop_button = self._button(footer, "Stop  ·  Esc", self._stop, "Danger.TButton")
        self.stop_button.grid(row=0, column=1, padx=(0, 10))
        self.start_button = self._button(footer, "Start entry  ·  F9", self._start, "Primary.TButton")
        self.start_button.grid(row=0, column=2)
        ttk.Progressbar(shell, variable=self.progress, maximum=100,
                        style="Accent.Horizontal.TProgressbar").grid(row=4, column=0, sticky="ew")

    def _show_page(self, page):
        self.current_page = page
        self.pages[page].tkraise()
        titles = {"file": ("Import & preview", "Great data entry starts with a clear view of your data."),
                  "target": ("Set up your destination", "Your system. Your field order. A workflow that fits."),
                  "activity": ("Every run, in view", "Follow your session and review the outcome of each run.")}
        self.page_title.configure(text=titles[page][0])
        self.page_description.configure(text=titles[page][1])
        for name, button in self.nav_buttons.items():
            button.configure(background="#24464e" if name == page else C["navy"],
                             foreground="white" if name == page else C["sidebar_text"],
                             highlightbackground="#24464e" if name == page else C["navy"])
        self._refresh_steps()

    def _refresh_steps(self):
        for index, (name, (circle, label)) in enumerate(self.step_labels.items()):
            done = bool(self.dataset) if name == "file" else bool(self.target) if name == "target" else False
            selected = name == self.current_page
            circle.configure(text="✓" if done else f"0{index+1}",
                             background=C["accent"] if selected else C["tint"] if done else "#f0f3f5",
                             foreground="white" if selected else C["accent"] if done else C["muted"])
            label.configure(foreground=C["ink"] if selected or done else C["muted"])

    def _toggle_import(self):
        if self.import_expanded:
            self._hide_import()
            return
        self.import_expanded = True
        self.import_window.update_idletasks()
        width = max(560, self.import_window.winfo_reqwidth())
        height = self.import_window.winfo_reqheight()
        x = min(self.winfo_rootx() + 250, self.winfo_screenwidth() - width - 24)
        y = min(self.winfo_rooty() + 130, self.winfo_screenheight() - height - 60)
        self.import_window.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        self.import_window.deiconify()
        self.import_window.lift()
        self.import_window.grab_set()

    def _hide_import(self):
        self.import_window.grab_release()
        self.import_window.withdraw()
        self.import_expanded = False

    def _separator_changed(self, *args):
        if args and self.separator.get() == "Custom character" and not self.import_expanded and not self.running:
            self._toggle_import()
        self.custom_entry.configure(state="normal" if self.separator.get() == "Custom character" and not self.running else "disabled")

    def _toggle_timing(self):
        self.timing_expanded = not self.timing_expanded
        if self.timing_expanded:
            self.timing_options.pack(fill="x", pady=(14, 0))
        else:
            self.timing_options.pack_forget()
        self.timing_button.configure(text="Timing settings  −" if self.timing_expanded else "Timing settings  +")

    def _mode_changed(self, *args):
        block = self.mode.get() == "Text block"
        self.block_combo.configure(state="readonly" if block and not self.running else "disabled")

    def _refresh_scope(self):
        try:
            start, limit = int(self.start_row.get()), int(self.row_limit.get())
            if start < 1 or limit < 0:
                raise ValueError
            count = max(0, len(self.dataset.records) - start + 1) if self.dataset else None
            count = min(count, limit) if count is not None and limit else count
            if count is not None:
                self.run_count.set(f"{count:,} record{'s' if count != 1 else ''} · from row {start}")
            else:
                self.run_count.set(f"{'All records' if limit == 0 else str(limit) + ' record(s)'} · from row {start}")
        except ValueError:
            self.run_count.set("Check row settings")

    def _set_controls(self):
        if self.running and self.import_expanded:
            self._hide_import()
        for widget, state in self.edit_controls:
            widget.configure(state="disabled" if self.running else state)
        self._separator_changed()
        self._mode_changed()
        self._refresh_readiness()

    def _refresh_readiness(self):
        checks = (bool(self.dataset), bool(self.target), bool(self.backend))
        for (label, title), done in zip(self.check_labels, checks):
            label.configure(text=("✓   " if done else "○   ") + title,
                            foreground=C["accent"] if done else C["muted"])
        ready = all(checks)
        self.readiness_label.configure(text="Entry in progress" if self.running else "You're ready to go" if ready else "Let's get you ready")
        self.start_button.configure(state="normal" if ready and not self.running else "disabled")
        self.stop_button.configure(state="normal" if self.running else "disabled")
        self.export_button.configure(state="normal" if self.dataset and not self.running else "disabled")
        self.release_target_button.configure(state="normal" if (self.target or self._capture_pending) and not self.running else "disabled")
        self.target_lock_status.set("LOCKED FOR THIS SESSION" if self.target else
                                    "CAPTURING DESTINATION" if self._capture_pending else "AWAITING CAPTURE")
        self.next_button.configure(state="normal" if self.dataset else "disabled")
        if self.target and self.dataset:
            self.next_button.configure(text="Review activity  →", command=lambda: self._show_page("activity"))
        else:
            self.next_button.configure(text="Set destination  →", command=lambda: self._show_page("target"))
        self._refresh_scope()
        self._refresh_steps()

    def _invalidate_preview(self, *args):
        had_preview = self.dataset is not None
        self.dataset = None
        self.preview_signature = None
        name = Path(self.file.get()).name if self.file.get().strip() else "Choose your source file"
        self.source_name.set(name if len(name) < 42 else name[:38] + "…")
        self.source_detail.set("Ready to preview · " + Path(self.file.get()).suffix.upper().lstrip(".") if self.file.get().strip()
                               else "Spreadsheets, documents and plain text. All in one place.")
        self.row_count.set("—")
        self.field_count.set("—")
        self.tree.delete(*self.tree.get_children())
        self.empty_preview.grid()
        for scrollbar in self.preview_scrollbars:
            scrollbar.grid_remove()
        self.summary.set("Preview the current file and settings to continue.")
        self.notes.set("Excel and Word tables use one cell per field. Blank field order includes every column.")
        self.preview_badge.set("NEEDS PREVIEW" if self.file.get().strip() else "AWAITING FILE")
        self.badge_label.configure(background="#f2f5f6", foreground=C["muted"])
        if had_preview:
            self.status.set("Import settings changed. Refresh your preview before starting.")
        self.status_title.configure(text="●  Ready for your next step", foreground=C["accent"])
        self._refresh_readiness()

    def _responsive(self, event):
        if event.widget is not self:
            return
        wide = event.width >= 1230
        short = event.height < 830
        if wide:
            self.session_panel.grid()
        else:
            self.session_panel.grid_remove()
        if event.height < 890:
            self.shortcuts_card.grid_remove()
        else:
            self.shortcuts_card.grid()
        self.heading_frame.configure(pady=10 if short else 18)
        self.page_title.configure(font=("Segoe UI", 22 if short else 25, "bold"))
        if short:
            self.page_eyebrow.pack_forget()
            self.page_description.pack_forget()
            self.formats_label.grid_remove()
            self.file_entry.grid_remove()
        else:
            self.page_eyebrow.pack(anchor="w", before=self.page_title)
            self.page_description.pack(anchor="w")
            self.formats_label.grid()
            self.file_entry.grid()
        available = event.width - 208 - 56 - (272 if wide else 0)
        for label in (self.summary_label, self.notes_label, self.run_detail_label):
            label.configure(wraplength=max(300, available - 48))
        self.status_label.configure(wraplength=max(220, event.width - 208 - 380))

    def _resize_empty_preview(self, event):
        for widget in (self.empty_icon, self.empty_title, self.empty_description, self.sample_button):
            widget.pack_forget()
        if event.height >= 145:
            self.empty_icon.pack(pady=(0, 8))
        self.empty_title.pack()
        if event.height >= 105:
            self.empty_description.pack(pady=(6, 8))
        if event.height >= 70:
            self.sample_button.pack()

    def _scroll_target(self, event, direction=None):
        if self.current_page != "target":
            return
        widget = event.widget
        while widget is not None:
            if widget is self.pages["target"]:
                if self.target_canvas.bbox("all")[3] > self.target_canvas.winfo_height():
                    units = direction if direction is not None else (-1 if event.delta > 0 else 1)
                    self.target_canvas.yview_scroll(units * 3, "units")
                break
            widget = getattr(widget, "master", None)
