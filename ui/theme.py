"""界面配色与 ttk 样式。"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

BG = "#F4F6FA"
CARD = "#FFFFFF"
BORDER = "#E3E8EF"
BORDER_SOFT = "#EEF1F6"
TEXT = "#1C2431"
TEXT_SUB = "#5B6675"
MUTED = "#8A94A6"
PRIMARY = "#3B6EF6"
PRIMARY_DARK = "#2F5BD8"
PRIMARY_PRESS = "#2649B5"
PRIMARY_SOFT = "#EDF2FF"
OK = "#0E9F6E"
WARN = "#C2740B"
DANGER = "#D93B3B"

FONT = "Microsoft YaHei UI"

_CANDIDATES = ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI", "Helvetica")


def font(size: float, bold: bool = False) -> tuple:
    # Tk 只接受整数磅值，这里统一四舍五入
    size = int(round(size))
    return (FONT, size, "bold") if bold else (FONT, size)


def init_font(root: tk.Misc) -> str:
    """挑选一个可用的中文字体。"""
    global FONT
    try:
        available = set(tkfont.families(root))
    except tk.TclError:
        available = set()
    for name in _CANDIDATES:
        if name in available:
            FONT = name
            break
    return FONT


def configure(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        "Treeview",
        background=CARD, fieldbackground=CARD, foreground=TEXT,
        borderwidth=0, rowheight=36, font=font(9.5),
    )
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.map(
        "Treeview",
        background=[("selected", "#E7EFFF")],
        foreground=[("selected", TEXT)],
    )

    style.configure(
        "Treeview.Heading",
        background="#F7F8FB", foreground=MUTED, relief="flat",
        borderwidth=0, font=font(9, bold=True), padding=(12, 9),
    )
    style.map("Treeview.Heading", background=[("active", "#F0F2F8")])

    style.configure(
        "Vertical.TScrollbar",
        background="#DEE4EE", troughcolor=CARD, bordercolor=CARD,
        arrowcolor=TEXT_SUB, relief="flat", width=9, arrowsize=9,
    )
    style.map("Vertical.TScrollbar", background=[("active", "#C9D3E2")])

