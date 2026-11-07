"""媒体文件批量重命名 —— 启动入口。"""
from __future__ import annotations

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
# 内置的拖拽支持库（tkinterdnd2），免安装即可用
_VENDOR = os.path.join(BASE_DIR, "vendor")
if os.path.isdir(_VENDOR):
    sys.path.insert(0, _VENDOR)


def _resource(rel: str) -> str:
    """打包成 exe 后资源在临时解包目录，开发时在脚本同级目录。"""
    base = getattr(sys, "_MEIPASS", BASE_DIR)
    return os.path.join(base, rel)


def _set_window_icon(root: "tk.Tk") -> None:
    for rel in ("app.ico", os.path.join("build", "app.ico")):
        path = _resource(rel)
        if os.path.exists(path):
            try:
                root.iconbitmap(default=path)
            except tk.TclError:
                pass
            return


def _enable_dpi() -> None:
    """仅在 100% 缩放时开启 DPI 感知，其余交给系统等比放大，避免控件错位。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
        except Exception:
            dpi = 96
        if dpi == 96:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


import tkinter as tk  # noqa: E402

DND = None
try:
    import tkinterdnd2 as DND  # noqa: F811
except Exception:
    DND = None


def main() -> None:
    _enable_dpi()

    if DND is not None:
        root = DND.TkinterDnD.Tk()
    else:
        root = tk.Tk()

    from ui.app import RenameApp

    _set_window_icon(root)
    app = RenameApp(root, dnd_enabled=DND is not None, dnd_module=DND)
    app.attach_dnd()

    initial = [a for a in sys.argv[1:] if os.path.exists(a)]
    if initial:
        root.after(150, lambda: app.add_paths(initial))

    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # 便于 pythonw 下也能看到错误
        try:
            from tkinter import messagebox
            messagebox.showerror("启动失败", f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        raise
