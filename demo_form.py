"""A practice destination. Records stay in memory and disappear when closed."""
import tkinter as tk
from tkinter import ttk

from staffbot.desktop import enable_dpi_awareness
from staffbot.ui_theme import apply_window_icon


BACKGROUND = "#f5f6f8"
SURFACE = "#ffffff"
INK = "#132c35"
MUTED = "#667983"
BORDER = "#e1e7eb"
TEAL = "#087f72"


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    apply_window_icon(root)
    root.title("Staff Entry Bot | Practice workspace")
    root.geometry("940x820")
    root.minsize(740, 740)
    root.configure(background=BACKGROUND)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Practice.TLabel", background=BACKGROUND, foreground=INK,
                    font=("Segoe UI", 10))
    style.configure("Practice.Muted.TLabel", background=BACKGROUND, foreground=MUTED,
                    font=("Segoe UI", 10))
    style.configure("Practice.Brand.TLabel", background=BACKGROUND, foreground=INK,
                    font=("Segoe UI", 12, "bold"))
    style.configure("Practice.Title.TLabel", background=BACKGROUND, foreground=INK,
                    font=("Segoe UI", 25, "bold"))
    style.configure("Practice.Card.TLabel", background=SURFACE, foreground=INK,
                    font=("Segoe UI", 10))
    style.configure("Practice.CardTitle.TLabel", background=SURFACE, foreground=INK,
                    font=("Segoe UI", 13, "bold"))
    style.configure("Practice.CardMuted.TLabel", background=SURFACE, foreground=MUTED,
                    font=("Segoe UI", 9))
    style.configure("Practice.TEntry", fieldbackground=SURFACE, foreground=INK,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    padding=(12, 9), font=("Segoe UI", 10))
    style.map("Practice.TEntry", bordercolor=[("focus", TEAL)],
              lightcolor=[("focus", TEAL)], darkcolor=[("focus", TEAL)])
    style.configure("Practice.Primary.TButton", background=TEAL, foreground=SURFACE,
                    borderwidth=0, focusthickness=2, focuscolor="#9dd7d0",
                    padding=(20, 11), font=("Segoe UI", 10, "bold"))
    style.map("Practice.Primary.TButton", background=[("pressed", "#056357"),
              ("active", "#096f65")], foreground=[("disabled", "#accbc7")])
    style.configure("Practice.Treeview", background=SURFACE, fieldbackground=SURFACE,
                    foreground=INK, borderwidth=0, rowheight=34,
                    font=("Segoe UI", 10))
    style.configure("Practice.Treeview.Heading", background="#f7f9fa", foreground=MUTED,
                    borderwidth=0, padding=(12, 10), font=("Segoe UI", 9, "bold"))
    style.map("Practice.Treeview", background=[("selected", "#e5f4f0")],
              foreground=[("selected", INK)])
    style.map("Practice.Treeview.Heading", background=[("active", "#f7f9fa")])
    style.configure("Practice.Vertical.TScrollbar", background="#dbe3e7",
                    troughcolor=SURFACE, borderwidth=0, arrowsize=12)

    frame = tk.Frame(root, background=BACKGROUND, padx=30, pady=24)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    brand = tk.Frame(frame, background=BACKGROUND)
    brand.grid(row=0, column=0, sticky="ew", pady=(0, 22))
    ttk.Label(brand, text="Staff Entry Bot", style="Practice.Brand.TLabel").pack(side="left")
    tk.Label(brand, text="  PRACTICE WORKSPACE  ", background="#e5f4f0", foreground=TEAL,
             font=("Segoe UI", 8, "bold"), padx=9, pady=5).pack(side="right")

    intro = tk.Frame(frame, background=BACKGROUND)
    intro.grid(row=1, column=0, sticky="ew", pady=(0, 20))
    ttk.Label(intro, text="Practice your workflow", style="Practice.Title.TLabel").pack(anchor="w")
    intro_copy = ttk.Label(
        intro, text="A safe place to test automated entry. All records disappear when you close this window.",
        style="Practice.Muted.TLabel", wraplength=820)
    intro_copy.pack(anchor="w", pady=(7, 0))
    intro.bind("<Configure>", lambda event: intro_copy.configure(wraplength=max(360, event.width)))

    form_card = tk.Frame(frame, background=SURFACE, highlightbackground=BORDER,
                         highlightthickness=1, padx=22, pady=18)
    form_card.grid(row=2, column=0, sticky="ew", pady=(0, 18))
    form_card.columnconfigure(1, weight=1)
    ttk.Label(form_card, text="Staff registration", style="Practice.CardTitle.TLabel").grid(
        row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(form_card, text="Enter a record manually, or let Staff Entry Bot fill these fields.",
              style="Practice.CardMuted.TLabel").grid(row=1, column=0, columnspan=2,
                                                     sticky="w", pady=(5, 15))

    labels = ["Employee ID", "Full name", "Department", "Email"]
    variables = [tk.StringVar() for _ in labels]
    entries = []
    for i, (label, variable) in enumerate(zip(labels, variables)):
        ttk.Label(form_card, text=label, width=16, style="Practice.Card.TLabel").grid(
            row=i + 2, column=0, sticky="w", pady=5, padx=(0, 16))
        entry = ttk.Entry(form_card, textvariable=variable, width=60,
                          style="Practice.TEntry", font=("Segoe UI", 10))
        entry.grid(row=i + 2, column=1, sticky="ew", pady=5)
        entries.append(entry)

    status = tk.StringVar(value="Ready for your first practice record.")
    record_count = tk.StringVar(value="0 records")
    records_card = tk.Frame(frame, background=SURFACE, highlightbackground=BORDER,
                            highlightthickness=1)
    records_card.grid(row=3, column=0, sticky="nsew")
    records_card.columnconfigure(0, weight=1)
    records_card.rowconfigure(2, weight=1)
    records_header = tk.Frame(records_card, background=SURFACE, padx=22, pady=16)
    records_header.grid(row=0, column=0, columnspan=2, sticky="ew")
    ttk.Label(records_header, text="Saved records", style="Practice.CardTitle.TLabel").pack(side="left")
    ttk.Label(records_header, textvariable=record_count,
              style="Practice.CardMuted.TLabel").pack(side="right")
    tk.Frame(records_card, background=BORDER, height=1).grid(row=1, column=0, columnspan=2, sticky="ew")

    table = ttk.Treeview(records_card, columns=labels, show="headings", height=4,
                         takefocus=False, style="Practice.Treeview")
    for label in labels:
        table.heading(label, text=label)
        table.column(label, width=165, minwidth=100, anchor="w")
    table.grid(row=2, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(records_card, orient="vertical", command=table.yview,
                              takefocus=False, style="Practice.Vertical.TScrollbar")
    scrollbar.grid(row=2, column=1, sticky="ns")
    table.configure(yscrollcommand=scrollbar.set)
    empty_state = tk.Label(table, text="Your practice records will appear here.\nSave your first entry to see the result.",
                           background=SURFACE, foreground=MUTED, font=("Segoe UI", 10),
                           justify="center", pady=14)
    empty_state.place(relx=0.5, rely=0.60, anchor="center")

    def save(event=None):
        values = tuple(variable.get() for variable in variables)
        if not values[0]:
            status.set("Employee ID is required. Nothing saved.")
            return "break"
        record = table.insert("", "end", values=values)
        table.see(record)
        empty_state.place_forget()
        for variable in variables:
            variable.set("")
        entries[0].focus_set()
        count = len(table.get_children())
        record_count.set(f"{count} record{'s' if count != 1 else ''}")
        status.set(f"Record saved. {count} practice record{'s' if count != 1 else ''} in memory.")
        return "break"

    # Created after the four entries to preserve the bot's Tab, Enter save sequence.
    form_actions = tk.Frame(form_card, background=SURFACE)
    form_actions.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(15, 0))
    save_button = ttk.Button(form_actions, text="Save record", command=save,
                             style="Practice.Primary.TButton")
    save_button.pack(side="left")
    save_button.bind("<Return>", save)
    ttk.Label(form_actions, text="Saves this row and clears the fields.",
              style="Practice.CardMuted.TLabel").pack(side="left", padx=16)
    ttk.Label(form_card, textvariable=status, style="Practice.CardMuted.TLabel",
              wraplength=790).grid(row=7, column=0, columnspan=2, sticky="w", pady=(13, 0))

    footer = tk.Frame(frame, background=BACKGROUND)
    footer.grid(row=4, column=0, sticky="ew", pady=(15, 0))
    ttk.Label(footer, text="BOT SETUP", style="Practice.Brand.TLabel").pack(side="left", padx=(0, 14))
    ttk.Label(footer, text="Leave Tab counts blank  /  Keys after each record: tab,enter",
              style="Practice.Muted.TLabel", wraplength=650).pack(side="left")
    entries[0].focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()
