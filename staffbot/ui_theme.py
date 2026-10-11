"""A restrained, consistent visual system for the desktop application."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


PALETTE = {
    "bg": "#f5f6f8",
    "surface": "#ffffff",
    "ink": "#172f39",
    "muted": "#72838c",
    "border": "#e2e8eb",
    "accent": "#087f72",
    "accent_hover": "#06685d",
    "tint": "#e9f5f1",
    "navy": "#112c35",
    "sidebar_text": "#a9bdc5",
    "danger": "#b44848",
}


def apply_window_icon(root: tk.Tk) -> None:
    """Use the product mark in native title bars without an image dependency."""
    icon = tk.PhotoImage(master=root, width=64, height=64)
    icon.put(PALETTE["navy"], to=(0, 0, 64, 64))
    for x, y in ((12, 34), (27, 23), (42, 12)):
        icon.put("#7ad4bc", to=(x, y, x + 10, 54))
    root.iconphoto(True, icon)
    root._staffbot_icon = icon


def configure_theme(root: tk.Misc) -> ttk.Style:
    """Apply the application theme and return its ttk style manager."""
    colors = PALETTE
    root.configure(background=colors["bg"])
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name, root=root).configure(family="Segoe UI", size=10)
    root.option_add("*Font", "{Segoe UI} 10")
    root.option_add("*TCombobox*Listbox.background", colors["surface"])
    root.option_add("*TCombobox*Listbox.foreground", colors["ink"])
    root.option_add("*TCombobox*Listbox.selectBackground", colors["tint"])
    root.option_add("*TCombobox*Listbox.selectForeground", colors["accent"])
    root.option_add("*TCombobox*Listbox.font", "{Segoe UI} 10")

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        ".", font=("Segoe UI", 10), background=colors["bg"],
        foreground=colors["ink"], bordercolor=colors["border"],
        lightcolor=colors["border"], darkcolor=colors["border"],
        focuscolor=colors["accent"],
    )
    style.configure("TFrame", background=colors["bg"], borderwidth=0)
    style.configure("Card.TFrame", background=colors["surface"], borderwidth=0)
    style.configure("TLabel", background=colors["bg"], foreground=colors["ink"])
    style.configure("Card.TLabel", background=colors["surface"])
    style.configure("Muted.TLabel", foreground=colors["muted"])
    style.configure("CardMuted.TLabel", background=colors["surface"], foreground=colors["muted"])
    style.configure("Title.TLabel", font=("Segoe UI", 26, "bold"))
    style.configure("Heading.TLabel", background=colors["surface"], font=("Segoe UI", 12, "bold"))
    style.configure("Eyebrow.TLabel", foreground=colors["muted"], font=("Segoe UI", 9, "bold"))
    style.configure("TLabelframe", background=colors["surface"], borderwidth=1, relief="solid")
    style.configure("TLabelframe.Label", background=colors["surface"], font=("Segoe UI", 10, "bold"))

    button_styles = {
        "TButton": (colors["surface"], colors["ink"], (14, 9), colors["border"]),
        "Secondary.TButton": (colors["surface"], colors["ink"], (14, 9), colors["border"]),
        "Primary.TButton": (colors["accent"], "#ffffff", (16, 10), colors["accent"]),
        "Ghost.TButton": (colors["bg"], colors["muted"], (10, 8), colors["bg"]),
        "CardGhost.TButton": (colors["surface"], colors["muted"], (10, 8), colors["surface"]),
        "Danger.TButton": ("#faeeee", colors["danger"], (14, 9), "#f1dcdc"),
    }
    for name, (background, foreground, padding, border) in button_styles.items():
        primary = name == "Primary.TButton"
        danger = name == "Danger.TButton"
        hover = colors["accent_hover"] if primary else "#f6e2e2" if danger else "#edf2f3"
        style.configure(
            name, background=background, foreground=foreground, padding=padding,
            borderwidth=1, bordercolor=border, lightcolor=background,
            darkcolor=background, relief="flat", focusthickness=1,
            focuscolor=colors["tint"] if primary else colors["accent"],
            font=("Segoe UI", 10, "bold") if primary else ("Segoe UI", 10),
            anchor="center",
        )
        style.map(
            name,
            background=[("disabled", "#edf1f2"), ("pressed", hover), ("active", hover)],
            foreground=[("disabled", "#89979d"), ("pressed", foreground), ("active", foreground)],
            bordercolor=[("disabled", colors["border"]), ("focus", colors["accent"]), ("active", hover if primary else border)],
            lightcolor=[("disabled", "#edf1f2"), ("pressed", hover), ("active", hover)],
            darkcolor=[("disabled", "#edf1f2"), ("pressed", hover), ("active", hover)],
            relief=[("pressed", "flat"), ("active", "flat")],
        )

    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(
            name, padding=7, foreground=colors["ink"],
            fieldbackground=colors["surface"], background=colors["surface"],
            bordercolor=colors["border"], lightcolor=colors["border"],
            darkcolor=colors["border"], borderwidth=1, relief="flat",
            selectbackground=colors["tint"], selectforeground=colors["ink"],
            arrowcolor=colors["muted"], insertcolor=colors["ink"],
        )
        style.map(
            name,
            foreground=[("disabled", "#89979d"), ("readonly", colors["ink"])],
            fieldbackground=[("disabled", "#f0f3f4"), ("readonly", colors["surface"])],
            background=[("disabled", "#f0f3f4"), ("active", colors["surface"])],
            bordercolor=[("disabled", colors["border"]), ("focus", colors["accent"]), ("active", "#b8c8cd")],
            lightcolor=[("focus", colors["accent"])],
            darkcolor=[("focus", colors["accent"])],
            arrowcolor=[("disabled", "#aab5ba"), ("active", colors["accent"])],
        )

    for name, background in (("TCheckbutton", colors["bg"]), ("Card.TCheckbutton", colors["surface"])):
        style.configure(
            name, background=background, foreground=colors["ink"],
            padding=(0, 3), indicatorbackground=colors["surface"],
            indicatorforeground=colors["accent"], indicatorcolor=colors["surface"],
            bordercolor=colors["border"], focuscolor=colors["accent"],
        )
        style.map(
            name,
            background=[("active", background), ("disabled", background)],
            foreground=[("disabled", "#89979d")],
            indicatorbackground=[("selected", colors["accent"]), ("disabled", "#f0f3f4")],
            indicatorforeground=[("disabled", "#aab5ba"), ("selected", "#ffffff")],
            indicatorcolor=[("disabled", "#f0f3f4"), ("selected", colors["accent"])],
            bordercolor=[("focus", colors["accent"]), ("active", "#b8c8cd")],
        )

    style.configure(
        "Treeview", background=colors["surface"], fieldbackground=colors["surface"],
        foreground=colors["ink"], rowheight=36, borderwidth=0, relief="flat",
        font=("Segoe UI", 10), bordercolor=colors["border"],
        lightcolor=colors["surface"], darkcolor=colors["surface"],
    )
    style.map(
        "Treeview", background=[("selected", colors["tint"])],
        foreground=[("disabled", "#89979d"), ("selected", colors["accent"])],
    )
    style.configure(
        "Treeview.Heading", background="#f5f8f9", foreground=colors["muted"],
        font=("Segoe UI", 9, "bold"), padding=(10, 10), borderwidth=0,
        relief="flat", lightcolor="#f5f8f9", darkcolor="#f5f8f9",
    )
    style.map("Treeview.Heading", background=[("active", "#edf2f3")], relief=[("pressed", "flat")])
    style.configure(
        "Accent.Horizontal.TProgressbar", background=colors["accent"],
        troughcolor=colors["tint"], borderwidth=0, thickness=5,
        lightcolor=colors["accent"], darkcolor=colors["accent"],
    )
    style.configure(
        "TScrollbar", background="#cdd8dc", troughcolor=colors["surface"],
        borderwidth=0, arrowsize=12, arrowcolor=colors["muted"],
        lightcolor="#cdd8dc", darkcolor="#cdd8dc", gripcount=0,
    )
    style.map("TScrollbar", background=[("active", "#aebfc5"), ("pressed", "#91a7af")])
    style.configure("TSeparator", background=colors["border"])
    return style
