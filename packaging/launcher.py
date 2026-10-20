#!/usr/bin/env python3
"""
微机教室考试系统 - Windows 图形化启动器（PyInstaller 入口）
双击 exe 后：初始化数据库 → 启动服务 → 自动打开浏览器
版权所有 © 柴延明
"""
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError:
    tk = None


def get_install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def get_bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return get_install_dir()


def get_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        d = Path(os.environ.get("APPDATA", str(Path.home()))) / "微机教室考试系统"
    else:
        d = get_install_dir() / "backend"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_log_path() -> Path:
    return get_data_dir() / "launcher.log"


def write_log(msg: str) -> None:
    try:
        with open(get_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def is_port_free(port: int, host: str = "0.0.0.0") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
        return True
    except OSError:
        return False


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def pick_port(preferred: int) -> int:
    if is_port_free(preferred):
        return preferred
    for p in range(preferred + 1, preferred + 20):
        if is_port_free(p):
            return p
    return preferred


def setup_environment():
    bundle = get_bundle_dir()
    data = get_data_dir()
    backend = bundle / "backend"

    os.environ["EXAM_SYSTEM_DATA_DIR"] = str(data)
    os.environ["EXAM_SYSTEM_BUNDLE_DIR"] = str(bundle)

    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    os.chdir(str(backend))
    write_log(f"bundle={bundle} data={data} backend={backend}")
    return backend, data


def init_database():
    import seed  # noqa: F401


def run_server(port: int):
    """使用 app 对象启动，避免 PyInstaller 下字符串导入失败。"""
    import uvicorn
    from app.main import app

    write_log(f"uvicorn starting on 0.0.0.0:{port}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
        access_log=False,
    )


class LauncherApp:
    BG = "#1e1b4b"
    CARD = "#312e81"
    ACCENT = "#6366f1"
    TEXT = "#e0e7ff"
    MUTED = "#a5b4fc"

    def __init__(self, port: int = 8000):
        self.port = pick_port(port)
        self.local_ip = get_local_ip()
        self.data_dir = get_data_dir()
        # 使用 127.0.0.1，避免 Windows 上 localhost 优先解析为 ::1 导致拒绝连接
        self.local_url = f"http://127.0.0.1:{self.port}"
        self.lan_url = f"http://{self.local_ip}:{self.port}"
        self.root = tk.Tk()
        self.root.title("微机教室在线考试系统")
        self.root.geometry("520x520")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG)
        self._center_window()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_window(self):
        self.root.update_idletasks()
        w, h = 520, 520
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        header = tk.Frame(self.root, bg=self.BG)
        header.pack(fill="x", padx=28, pady=(28, 12))

        title = tk.Label(
            header,
            text="微机教室在线考试系统",
            font=("Microsoft YaHei UI", 18, "bold"),
            fg="white",
            bg=self.BG,
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            header,
            text="Computer Lab Online Examination System",
            font=("Segoe UI", 10),
            fg=self.MUTED,
            bg=self.BG,
        )
        subtitle.pack(anchor="w", pady=(4, 0))

        card = tk.Frame(self.root, bg=self.CARD, padx=20, pady=18)
        card.pack(fill="both", expand=True, padx=28, pady=8)

        self.status_var = tk.StringVar(value="正在初始化...")
        status = tk.Label(
            card,
            textvariable=self.status_var,
            font=("Microsoft YaHei UI", 11),
            fg=self.TEXT,
            bg=self.CARD,
            wraplength=420,
            justify="left",
        )
        status.pack(anchor="w")

        self.progress = ttk.Progressbar(card, mode="indeterminate", length=420)
        self.progress.pack(fill="x", pady=(14, 18))
        self.progress.start(12)

        info_frame = tk.Frame(card, bg=self.CARD)
        info_frame.pack(fill="x")

        self.url_local = tk.StringVar(value=self.local_url)
        self.url_lan = tk.StringVar(value=self.lan_url)

        tk.Label(info_frame, text="教师机本机访问", font=("Microsoft YaHei UI", 9), fg=self.MUTED, bg=self.CARD).pack(anchor="w")
        tk.Label(info_frame, textvariable=self.url_local, font=("Consolas", 11), fg="white", bg=self.CARD).pack(anchor="w", pady=(2, 10))
        tk.Label(info_frame, text="学生机局域网访问", font=("Microsoft YaHei UI", 9), fg=self.MUTED, bg=self.CARD).pack(anchor="w")
        tk.Label(info_frame, textvariable=self.url_lan, font=("Consolas", 11), fg="white", bg=self.CARD).pack(anchor="w", pady=(2, 10))

        hint = (
            "默认账号\n"
            "  管理员: admin / admin123\n"
            "  教师: teacher / teacher123\n"
            "  学生: student01 / 123456\n"
            f"\n若无法打开，请查看日志:\n  {get_log_path()}"
        )
        tk.Label(
            card,
            text=hint,
            font=("Microsoft YaHei UI", 9),
            fg=self.MUTED,
            bg=self.CARD,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        btn_frame = tk.Frame(self.root, bg=self.BG)
        btn_frame.pack(fill="x", padx=28, pady=(8, 10))

        self.open_btn = tk.Button(
            btn_frame,
            text="打开浏览器",
            font=("Microsoft YaHei UI", 10),
            bg=self.ACCENT,
            fg="white",
            activebackground="#4f46e5",
            activeforeground="white",
            relief="flat",
            padx=16,
            pady=8,
            command=self.open_browser,
            state="disabled",
        )
        self.open_btn.pack(side="left")

        tk.Label(
            self.root,
            text="版权所有 © 柴延明 · 保留所有权利",
            font=("Microsoft YaHei UI", 9),
            fg=self.MUTED,
            bg=self.BG,
        ).pack(pady=(0, 16))

    def set_status(self, text: str, running: bool = False):
        self.status_var.set(text)
        if running:
            self.progress.stop()
            self.progress.pack_forget()
            self.open_btn.config(state="normal")

    def open_browser(self):
        webbrowser.open(self.url_local.get())

    def _on_close(self):
        if messagebox.askokcancel("退出", "关闭窗口将停止考试系统服务，确定退出吗？"):
            self.root.destroy()
            os._exit(0)

    def start_background(self):
        threading.Thread(target=self._bootstrap, daemon=True).start()

    def _bootstrap(self):
        try:
            write_log("bootstrap start")
            setup_environment()
            self.root.after(0, lambda: self.set_status("正在初始化数据库..."))
            init_database()
            write_log("database ready")

            self.root.after(0, lambda: self.set_status(f"服务启动中（端口 {self.port}）..."))
            self.root.after(0, lambda: self.url_local.set(self.local_url))
            self.root.after(0, lambda: self.url_lan.set(self.lan_url))

            # 先在后台线程启动 uvicorn，再等待端口真正就绪
            server_error = {"err": None}

            def _serve():
                try:
                    run_server(self.port)
                except Exception as e:
                    server_error["err"] = e
                    write_log(f"server crashed: {e}\n{traceback.format_exc()}")

            threading.Thread(target=_serve, daemon=True).start()

            if not wait_for_port(self.port, host="127.0.0.1", timeout=45.0):
                err = server_error["err"]
                detail = str(err) if err else f"端口 {self.port} 未能在限定时间内就绪"
                raise RuntimeError(
                    f"服务启动失败：{detail}\n\n"
                    f"请确认端口未被占用，或以管理员身份运行。\n"
                    f"日志文件：{get_log_path()}"
                )

            write_log(f"port {self.port} is ready")
            self.root.after(
                0,
                lambda: self.set_status("服务运行中 · 关闭本窗口即可停止服务", running=True),
            )
            if not os.environ.get("EXAM_NO_BROWSER"):
                self.root.after(300, self.open_browser)
        except Exception as e:
            write_log(f"bootstrap failed: {e}\n{traceback.format_exc()}")
            self.root.after(0, lambda: self._show_error(str(e)))

    def _show_error(self, msg: str):
        self.progress.stop()
        messagebox.showerror("启动失败", msg)
        self.root.destroy()
        sys.exit(1)

    def run(self):
        self.start_background()
        self.root.mainloop()


def main():
    preferred = int(os.environ.get("EXAM_PORT", "8000"))
    port = pick_port(preferred)
    write_log(f"main preferred={preferred} selected={port}")

    if tk is None:
        setup_environment()
        init_database()
        local_url = f"http://127.0.0.1:{port}"
        if not os.environ.get("EXAM_NO_BROWSER"):
            def _open():
                if wait_for_port(port):
                    webbrowser.open(local_url)

            threading.Thread(target=_open, daemon=True).start()
        run_server(port)
        return

    LauncherApp(port).run()


if __name__ == "__main__":
    main()
