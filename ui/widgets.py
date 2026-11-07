"""自绘的圆角控件（按钮、拖放区）。"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

from . import theme as T


def _bg_of(widget: tk.Misc) -> str:
    try:
        return widget.cget("bg")
    except tk.TclError:
        return T.BG


def round_fill(cv: tk.Canvas, x1, y1, x2, y2, r, fill: str) -> None:
    r = int(max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2)))
    if r <= 0:
        cv.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")
        return
    cv.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="")
    cv.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="")
    for cx, cy in ((x1 + r, y1 + r), (x2 - r, y1 + r), (x1 + r, y2 - r), (x2 - r, y2 - r)):
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline="")


def round_outline(cv: tk.Canvas, x1, y1, x2, y2, r, color: str, width: int = 1) -> None:
    r = int(max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2)))
    if r <= 0:
        cv.create_rectangle(x1, y1, x2, y2, outline=color, width=width)
        return
    cv.create_line(x1 + r, y1, x2 - r, y1, fill=color, width=width)
    cv.create_line(x1 + r, y2, x2 - r, y2, fill=color, width=width)
    cv.create_line(x1, y1 + r, x1, y2 - r, fill=color, width=width)
    cv.create_line(x2, y1 + r, x2, y2 - r, fill=color, width=width)
    corners = (
        (x1, y1, 90),
        (x2 - 2 * r, y1, 0),
        (x1, y2 - 2 * r, 180),
        (x2 - 2 * r, y2 - 2 * r, 270),
    )
    for bx, by, start in corners:
        cv.create_arc(bx, by, bx + 2 * r, by + 2 * r, start=start, extent=90,
                      style="arc", outline=color, width=width)


class RoundedButton(tk.Canvas):
    """圆角按钮，kind: primary / ghost / soft / quiet。"""

    def __init__(self, master, text: str, command=None, kind: str = "ghost",
                 width: int | None = None, height: int = 36, radius: int = 9,
                 padx: int = 18, font=None, parent_bg: str | None = None):
        self._parent_bg = parent_bg or _bg_of(master)
        self._font = font or T.font(9.5, bold=(kind == "primary"))
        self._text = text
        self._command = command
        self._kind = kind
        self._enabled = True
        self._hover = False
        self._pressed = False
        self._radius = radius
        self._height = height

        measured = tkfont.Font(font=self._font).measure(text)
        w = width or measured + padx * 2

        super().__init__(master, width=w, height=height, bg=self._parent_bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._cw, self._ch = w, height

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    # ---- 外观 ----
    def _palette(self) -> tuple[str, str, str]:
        if not self._enabled:
            border = "#E7EBF2" if self._kind in ("ghost", "quiet") else ""
            return "#F3F5F9", "#B3BCC9", border
        base = {
            "primary": (T.PRIMARY, "#FFFFFF", "", T.PRIMARY_DARK, T.PRIMARY_PRESS),
            "ghost": (T.CARD, T.TEXT, T.BORDER, "#F3F6FB", "#E9EEF7"),
            "soft": (T.PRIMARY_SOFT, T.PRIMARY, "", "#E3EBFF", "#D7E2FF"),
            "quiet": (self._parent_bg, T.TEXT_SUB, "", "#ECF0F7", "#E3E9F2"),
        }[self._kind]
        bg, fg, border, hover, press = base
        if self._pressed:
            return press, fg, border
        if self._hover:
            return hover, fg, border
        return bg, fg, border

    def _draw(self) -> None:
        self.delete("all")
        w, h = self._cw, self._ch
        fill, fg, border = self._palette()
        r = self._radius
        round_fill(self, 0, 0, w, h, r, fill)
        if border:
            round_outline(self, 0, 0, w, h, r, border, 1)
        self.create_text(w / 2, h / 2 + 0.5, text=self._text, fill=fg, font=self._font)

    # ---- 状态 ----
    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        if not enabled:
            self._hover = self._pressed = False
        self._draw()

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self._draw()

    def invoke(self) -> None:
        if self._enabled and self._command:
            self._command()

    # ---- 事件 ----
    def _on_enter(self, _evt=None):
        if not self._enabled:
            return
        self._hover = True
        self._draw()

    def _on_leave(self, _evt=None):
        self._hover = self._pressed = False
        self._draw()

    def _on_press(self, _evt=None):
        if not self._enabled:
            return
        self._pressed = True
        self._draw()

    def _on_release(self, evt=None):
        if not self._enabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if was_pressed and evt is not None:
            if 0 <= evt.x <= self._cw and 0 <= evt.y <= self._ch:
                self.invoke()


def draw_r_mark(cv: tk.Canvas, size: float, x: float = 0, y: float = 0,
                tile: str = T.PRIMARY, ink: str = "#FFFFFF") -> None:
    """在画布上绘制 R 字母标志（圆角方块 + 白色 R）。"""
    s = size / 96.0
    round_fill(cv, x, y, x + size, y + size, size * 0.25, tile)
    w = 9 * s

    def X(v: float) -> float:
        return x + v * s

    def Y(v: float) -> float:
        return y + v * s

    cv.create_line(X(30), Y(22), X(30), Y(72), fill=ink, width=w, capstyle="round")
    cv.create_line(X(30), Y(22), X(50), Y(22), fill=ink, width=w, capstyle="round")
    cv.create_arc(X(34), Y(22), X(66), Y(54), start=270, extent=180,
                  style="arc", outline=ink, width=w)
    cv.create_line(X(50), Y(54), X(30), Y(54), fill=ink, width=w, capstyle="round")
    cv.create_line(X(48), Y(54), X(68), Y(74), fill=ink, width=w, capstyle="round")


def _draw_drop_icon(cv: tk.Canvas, cx: float, cy: float, color: str) -> None:
    w = 2.4
    cv.create_line(cx - 17, cy + 3, cx - 17, cy + 14, cx + 17, cy + 14, cx + 17, cy + 3,
                   fill=color, width=w, capstyle="round", joinstyle="round")
    cv.create_line(cx, cy - 16, cx, cy + 2, fill=color, width=w, capstyle="round")
    cv.create_line(cx - 7, cy - 5, cx, cy + 2, cx + 7, cy - 5,
                   fill=color, width=w, capstyle="round", joinstyle="round")


class DropZone(tk.Canvas):
    """圆角拖放区域。"""

    def __init__(self, master, height: int = 156, bg: str | None = None):
        self._bg = bg or _bg_of(master)
        super().__init__(master, height=height, bg=self._bg, highlightthickness=0, bd=0)
        self._state = "idle"
        self._title = "拖拽图片 / 视频 / 文件夹到这里"
        self._hint = "支持 JPG、PNG、HEIC、MP4、MOV 等常见格式，也可以用下方按钮选择"
        self.bind("<Configure>", lambda _e: self._draw())

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self._draw()

    def set_hint(self, text: str) -> None:
        self._hint = text
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 20 or h < 20:
            return

        if self._state == "hover":
            fill, border, icon, title, hint, bw = "#F2F7FF", T.PRIMARY, T.PRIMARY, T.PRIMARY, T.PRIMARY, 2
        else:
            fill, border, icon, title, hint, bw = "#FBFCFE", T.BORDER, T.PRIMARY, T.TEXT, T.MUTED, 1

        round_fill(self, 1, 1, w - 1, h - 1, 14, fill)
        round_outline(self, 1, 1, w - 1, h - 1, 14, border, bw)

        cx = w / 2
        _draw_drop_icon(self, cx, 46, icon)
        self.create_text(cx, 98, text=self._title, fill=title, font=T.font(11.5, bold=True))
        self.create_text(cx, 123, text=self._hint, fill=hint, font=T.font(9))


class CheckBox(tk.Canvas):
    """自绘圆角勾选框。"""

    def __init__(self, master, text: str, variable: tk.BooleanVar,
                 command=None, font=None):
        self._var = variable
        self._text = text
        self._command = command
        self._font = font or T.font(9)
        self._size = 16
        self._h = 24
        measured = tkfont.Font(font=self._font).measure(text)
        w = self._size + 8 + measured + 2

        super().__init__(master, width=w, height=self._h, bg=_bg_of(master),
                         highlightthickness=0, bd=0, cursor="hand2")
        self.bind("<Button-1>", self._toggle)
        self.bind("<Enter>", lambda _e: self._draw(hover=True))
        self.bind("<Leave>", lambda _e: self._draw(hover=False))
        self._var.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _draw(self, hover: bool = False) -> None:
        self.delete("all")
        on = bool(self._var.get())
        size, pad, y1 = self._size, 1, (self._h - self._size) / 2
        if on:
            color = T.PRIMARY_DARK if hover else T.PRIMARY
            round_fill(self, pad, y1, pad + size, y1 + size, 5, color)
            self.create_line(pad + 4.5, y1 + 8.5, pad + 7.2, y1 + 11.2,
                             pad + 12, y1 + 5, fill="#FFFFFF", width=2,
                             capstyle="round", joinstyle="round")
        else:
            round_fill(self, pad, y1, pad + size, y1 + size, 5, "#FFFFFF")
            round_outline(self, pad, y1, pad + size, y1 + size, 5,
                          T.PRIMARY if hover else "#C6CFDD", 1)
        self.create_text(size + 9, self._h / 2, text=self._text, anchor="w",
                         fill=T.TEXT_SUB, font=self._font)

    def _toggle(self, _event=None) -> None:
        self._var.set(not self._var.get())
        if self._command:
            self._command()
