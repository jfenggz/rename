"""主窗口。"""
from __future__ import annotations

import os
import subprocess
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from core import renamer
from core.renamer import (
    MEDIA_EXTS, STATUS_CN, STATUS_DONE, STATUS_FAILED, STATUS_NO_TIME,
    STATUS_READY, STATUS_STD, TARGET_EXAMPLE,
)

from . import theme as T
from .widgets import CheckBox, DropZone, RoundedButton, draw_r_mark

STATUS_TEXT = {
    STATUS_READY: "待重命名",
    STATUS_STD: "已是标准格式",
    STATUS_NO_TIME: "未发现时间",
    STATUS_CN: "中文日期，保持原样",
    STATUS_DONE: "已重命名",
    STATUS_FAILED: "失败",
}

_ORDER = {STATUS_READY: 0, STATUS_STD: 1, STATUS_CN: 2, STATUS_NO_TIME: 3,
          STATUS_DONE: 4, STATUS_FAILED: 5}

HELP_TEXT = f"""哪些文件会被处理？

    只处理图片和视频（jpg / png / heic / mp4 / mov 等），其它文件一律忽略。

什么时候会改名？

    文件名里能读出「年月日 + 时分秒」才会改，并统一成：

        {TARGET_EXAMPLE}.jpg     即  YYYYMMDD_HHMMSS

    可以识别的常见写法：

        IMG_20170118_102952.jpg          已有日期时间
        Screenshot 2017-01-18 10.29.52   带分隔符
        20170118102952.jpg               紧凑 14 位
        mmexport1794065790035.jpg        13 位毫秒时间戳
        wx_camera_1698765432.jpg         10 位秒时间戳

什么情况下不动它？

    1. 文件名已经是 20170118_102952 这种格式；
    2. 中文日期命名的文件（例如 2017年1月18日 10时29分52秒.jpg）保持原样；
    3. 文件名里根本没有时间信息（例如 DSC_0421.jpg）；
    4. 只有日期没有时分秒（例如 IMG-20240101-WA0001.jpg）。

其它说明

    · 重命名只在原文件夹内进行，不会移动文件；
    · 同一秒的多个文件会自动加上 _1、_2 后缀，不会互相覆盖；
    · 所有操作都会先预览，点击「开始重命名」才真正执行，执行后可一键撤销。"""


class RenameApp:
    def __init__(self, root: tk.Tk, dnd_enabled: bool = False, dnd_module=None):
        self.root = root
        self.dnd_enabled = dnd_enabled
        self.dnd_module = dnd_module

        self.sources: list[str] = []
        self.items: list[renamer.Item] = []
        self.undo_records: list[tuple[Path, Path]] = []
        self.msg = ""
        self._busy = False

        T.init_font(root)
        T.configure(root)

        self.recursive = tk.BooleanVar(master=root, value=True)
        self._build()
        self._refresh()
        self._bind_shortcuts()

    # ------------------------------------------------------------------ 构建
    def _build(self) -> None:
        root = self.root
        root.title("媒体文件批量重命名")
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w = min(1020, int(sw * 0.9))
        h = min(780, int(sh * 0.86))
        root.geometry(f"{w}x{h}")
        root.minsize(min(880, w), min(560, h))
        root.configure(bg=T.BG)

        outer = tk.Frame(root, bg=T.BG)
        outer.pack(fill="both", expand=True, padx=24, pady=(18, 18))

        self._build_header(outer)
        self._build_dropzone(outer)
        self._build_toolbar(outer)
        # 底栏先占位，保证窗口变小时不会被表格挤掉
        self._build_footer(outer)
        self._build_table(outer)

    def _build_header(self, parent: tk.Frame) -> None:
        head = tk.Frame(parent, bg=T.BG)
        head.pack(fill="x")

        logo = tk.Canvas(head, width=42, height=42, bg=T.BG, highlightthickness=0, bd=0)
        logo.pack(side="left")
        draw_r_mark(logo, 42)

        titles = tk.Frame(head, bg=T.BG)
        titles.pack(side="left", padx=(12, 0))
        tk.Label(titles, text="媒体文件批量重命名", bg=T.BG, fg=T.TEXT,
                 font=T.font(13.5, bold=True)).pack(anchor="w")
        tk.Label(titles, text=f"把文件名里的时间统一成 {TARGET_EXAMPLE} 这种格式",
                 bg=T.BG, fg=T.MUTED, font=T.font(9)).pack(anchor="w", pady=(2, 0))

        RoundedButton(head, "规则说明", self._show_help, kind="quiet",
                      height=30, padx=12, radius=8, font=T.font(9)).pack(side="right")

    def _build_dropzone(self, parent: tk.Frame) -> None:
        self.dropzone = DropZone(parent, height=156)
        self.dropzone.pack(fill="x", pady=(16, 14))
        if not self.dnd_enabled:
            self.dropzone.set_hint("当前环境不支持拖拽，请用下方按钮选择文件或文件夹")

    def _build_toolbar(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg=T.BG)
        bar.pack(fill="x")

        RoundedButton(bar, "选择文件", self.choose_files, kind="soft",
                      height=36, radius=9).pack(side="left")
        RoundedButton(bar, "选择文件夹", self.choose_folder, kind="ghost",
                      height=36, radius=9).pack(side="left", padx=(8, 0))
        RoundedButton(bar, "清空列表", self.clear, kind="quiet",
                      height=36, radius=9, padx=14, font=T.font(9)).pack(side="left", padx=(8, 0))

        CheckBox(bar, "包含子文件夹", self.recursive,
                 command=self._rescan).pack(side="right")

    def _build_table(self, parent: tk.Frame) -> None:
        card = tk.Frame(parent, bg=T.CARD, highlightthickness=1,
                        highlightbackground=T.BORDER, highlightcolor=T.BORDER)
        card.pack(fill="both", expand=True, pady=(12, 0))

        wrap = tk.Frame(card, bg=T.CARD)
        wrap.pack(fill="both", expand=True, padx=4, pady=(4, 6))

        self.tree = ttk.Treeview(wrap, columns=("old", "new", "status"),
                                 show="headings", selectmode="browse", height=8)
        self.tree.heading("old", text="原文件名", anchor="w")
        self.tree.heading("new", text="新文件名", anchor="w")
        self.tree.heading("status", text="状态", anchor="w")
        self.tree.column("old", width=390, minwidth=200, anchor="w", stretch=True)
        self.tree.column("new", width=390, minwidth=200, anchor="w", stretch=True)
        self.tree.column("status", width=196, minwidth=120, anchor="w", stretch=False)

        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview,
                           style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.tag_configure(STATUS_READY, foreground=T.TEXT)
        self.tree.tag_configure(STATUS_STD, foreground=T.MUTED)
        self.tree.tag_configure(STATUS_CN, foreground=T.MUTED)
        self.tree.tag_configure(STATUS_NO_TIME, foreground=T.WARN)
        self.tree.tag_configure(STATUS_DONE, foreground=T.OK)
        self.tree.tag_configure(STATUS_FAILED, foreground=T.DANGER)

        self.empty_label = tk.Label(
            card,
            text="还没有待处理的文件\n把图片、视频或整个文件夹拖进来试试",
            bg=T.CARD, fg=T.MUTED, font=T.font(10), justify="center",
        )
        self.tree.bind("<Double-1>", self._open_location)

    def _build_footer(self, parent: tk.Frame) -> None:
        foot = tk.Frame(parent, bg=T.BG)
        foot.pack(side="bottom", fill="x", pady=(14, 0))

        self.btn_run = RoundedButton(foot, f"开始重命名", self.do_rename, kind="primary",
                                     width=148, height=40, radius=10, font=T.font(10, bold=True))
        self.btn_run.pack(side="right")
        self.btn_undo = RoundedButton(foot, "撤销上次", self.do_undo, kind="ghost",
                                      width=104, height=40, radius=10, font=T.font(9.5))
        self.btn_undo.pack(side="right", padx=(0, 10))

        self.stats = tk.Label(foot, text="", bg=T.BG, fg=T.TEXT_SUB,
                              font=T.font(9.5), anchor="w", justify="left")
        self.stats.pack(side="left", fill="x", expand=True)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda e: self.choose_files())
        self.root.bind("<Control-O>", lambda e: self.choose_folder())
        self.root.bind("<Control-Return>", lambda e: self.do_rename())
        self.root.bind("<Control-z>", lambda e: self.do_undo())

    # ------------------------------------------------------------------ 拖拽
    def attach_dnd(self) -> None:
        if not self.dnd_enabled:
            return
        files = self.dnd_module.DND_FILES
        for widget in (self.dropzone, self.tree):
            widget.drop_target_register(files)
            widget.dnd_bind("<<Drop>>", self._on_drop)
            widget.dnd_bind("<<DropEnter>>", self._on_drag_enter)
            widget.dnd_bind("<<DropLeave>>", self._on_drag_leave)

    def _on_drag_enter(self, _event=None):
        self.dropzone.set_state("hover")
        return "copy"

    def _on_drag_leave(self, _event=None):
        self.dropzone.set_state("idle")
        return "copy"

    def _on_drop(self, event):
        self.dropzone.set_state("idle")
        try:
            raw = self.root.tk.splitlist(event.data)
        except tk.TclError:
            raw = [event.data]
        paths = [p for p in raw if os.path.exists(p)]
        if paths:
            self.add_paths(paths)
        return event.action

    # ------------------------------------------------------------------ 数据
    def add_paths(self, paths: list[str]) -> None:
        existing = {os.path.normcase(os.path.abspath(p)) for p in self.sources}
        added = 0
        for p in paths:
            key = os.path.normcase(os.path.abspath(p))
            if key in existing:
                continue
            existing.add(key)
            self.sources.append(os.path.abspath(p))
            added += 1
        if not added:
            self.msg = "这些文件已经在列表里了"
            self._refresh()
            return
        self._rescan()

    def choose_files(self) -> None:
        patterns = " ".join("*" + e for e in sorted(MEDIA_EXTS))
        paths = filedialog.askopenfilenames(
            title="选择图片或视频",
            filetypes=[("图片 / 视频", patterns), ("所有文件", "*.*")],
        )
        if paths:
            self.add_paths(list(paths))

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="选择文件夹")
        if folder:
            self.add_paths([folder])

    def clear(self) -> None:
        self.sources.clear()
        self.items = []
        self.undo_records = []
        self.msg = ""
        self._refresh()

    def _rescan(self) -> None:
        self.undo_records = []
        self.msg = ""
        if not self.sources:
            self.items = []
            self._refresh()
            return

        self._set_busy(True, "正在扫描…")
        try:
            files = renamer.collect(self.sources, recursive=self.recursive.get())
            items = renamer.build_plan(files)
        finally:
            self._set_busy(False)

        items.sort(key=lambda i: (
            _ORDER.get(i.status, 9),
            i.dt or datetime.max,
            i.path.name.lower(),
        ))
        self.items = items
        if not items:
            self.msg = "没有找到可处理的图片或视频文件"
        self._refresh()

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self._busy = busy
        try:
            self.root.configure(cursor="watch" if busy else "")
            if text:
                self.stats.configure(text=text)
            self.root.update_idletasks()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ 渲染
    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for idx, item in enumerate(self.items):
            self.tree.insert(
                "", "end", iid=str(idx),
                values=(item.display_old, item.display_new, self._status_text(item)),
                tags=(item.status,),
            )

        if self.items:
            self.empty_label.place_forget()
        else:
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
            self.empty_label.lift()

        counts = renamer.summarize(self.items)
        if self.items:
            parts = [f"共 {len(self.items)} 个媒体文件"]
            for key, label in ((STATUS_READY, "待重命名"), (STATUS_STD, "已是标准格式"),
                               (STATUS_CN, "中文日期"), (STATUS_NO_TIME, "未发现时间"),
                               (STATUS_DONE, "已重命名"), (STATUS_FAILED, "失败")):
                if counts.get(key):
                    parts.append(f"{label} {counts[key]}")
            text = "   ·   ".join(parts)
        else:
            text = "还没有添加文件"

        if self.msg:
            text = f"{text}        {self.msg}"
        self.stats.configure(text=text)

        self.btn_run.set_enabled(counts.get(STATUS_READY, 0) > 0 and not self._busy)
        self.btn_undo.set_enabled(bool(self.undo_records))

    def _status_text(self, item: renamer.Item) -> str:
        if item.status == STATUS_READY:
            return "待重命名 · 加序号" if "序号" in item.note else "待重命名"
        if item.status == STATUS_FAILED:
            return "失败（见提示）"
        return STATUS_TEXT.get(item.status, item.status)

    # ------------------------------------------------------------------ 操作
    def do_rename(self) -> None:
        ready = [i for i in self.items if i.status == STATUS_READY]
        if not ready:
            messagebox.showinfo("没有可重命名的文件", "当前列表里没有需要重命名的文件。", parent=self.root)
            return

        if not messagebox.askyesno(
            "确认重命名",
            f"即将重命名 {len(ready)} 个文件。\n\n"
            f"规则：统一改为 {TARGET_EXAMPLE}.后缀 格式，不改动其它文件。\n"
            "执行后可以点击「撤销上次」还原。\n\n是否继续？",
            parent=self.root,
        ):
            return

        self._set_busy(True, "正在重命名…")
        try:
            records, errors = renamer.execute(ready)
        finally:
            self._set_busy(False)

        self.undo_records = records
        if errors:
            messagebox.showwarning(
                "部分文件重命名失败",
                f"成功 {len(records)} 个，失败 {len(errors)} 个。\n\n" + "\n".join(errors[:10]),
                parent=self.root,
            )
            self.msg = f"成功 {len(records)} 个，失败 {len(errors)} 个"
        else:
            self.msg = f"已完成 {len(records)} 个文件的重命名"
        self._refresh()

    def do_undo(self) -> None:
        if not self.undo_records:
            return
        ok, problems = renamer.undo(self.undo_records)
        self.undo_records = []
        self.msg = f"已撤销 {ok} 个文件的重命名"
        if problems:
            self.msg += f"，{len(problems)} 个未处理"
            messagebox.showwarning("撤销未全部完成", "\n".join(problems[:10]), parent=self.root)
        self._rescan()

    def _open_location(self, _event=None) -> None:
        iid = self.tree.focus()
        if not iid:
            return
        try:
            path = self.items[int(iid)].path
        except (ValueError, IndexError):
            return
        try:
            if path.exists():
                subprocess.Popen(["explorer", f"/select,{path}"])
            else:
                subprocess.Popen(["explorer", str(path.parent)])
        except OSError:
            pass

    def _show_help(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("规则说明")
        win.configure(bg=T.CARD)
        win.transient(self.root)
        win.resizable(False, False)

        tk.Label(win, text="重命名规则", bg=T.CARD, fg=T.TEXT,
                 font=T.font(12, bold=True)).pack(anchor="w", padx=24, pady=(20, 10))
        tk.Label(win, text=HELP_TEXT, bg=T.CARD, fg=T.TEXT_SUB, justify="left",
                 font=T.font(9.2), anchor="w").pack(anchor="w", padx=24)
        RoundedButton(win, "知道了", win.destroy, kind="primary",
                      width=110, height=36, radius=9).pack(anchor="e", padx=24, pady=(14, 20))

        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + 60
        win.geometry(f"+{max(x, 40)}+{max(y, 40)}")
        win.grab_set()
        win.focus_set()
