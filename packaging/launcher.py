#!/usr/bin/env python3
"""
微机教室考试系统 - Windows 图形化启动器（PyInstaller 入口）
双击 exe 后：初始化数据库 → 启动服务 → 自动打开浏览器
版权所有 © 柴延明
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
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
    """带超时，避免无外网时 connect(8.8.8.8) 卡死导致 exe 一直起不来。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def check_health(port: int, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(health_url(port), timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def wait_for_health(port: int, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check_health(port, timeout=0.8):
            return True
        time.sleep(0.3)
    return False


def setup_environment():
    bundle = get_bundle_dir()
    data = get_data_dir()
    backend = bundle / "backend"

    os.environ["EXAM_SYSTEM_DATA_DIR"] = str(data)
    os.environ["EXAM_SYSTEM_BUNDLE_DIR"] = str(bundle)

    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    os.chdir(str(backend))
    write_log(f"bundle={bundle} data={data} backend={backend} frozen={getattr(sys, 'frozen', False)}")
    return backend, data


def init_database():
    import seed  # noqa: F401


def run_server(port: int, ready_event: threading.Event | None = None, error_box: dict | None = None):
    """用 Config/Server 启动，禁用信号处理器，避免非主线程卡死。"""
    try:
        import uvicorn
        from app.main import app

        write_log(f"creating uvicorn server on 0.0.0.0:{port}")
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=port,
            log_level="warning",
            access_log=False,
            lifespan="on",
        )
        server = uvicorn.Server(config)
        # Windows / 子线程中安装信号处理器会失败或卡住
        server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

        if ready_event is not None:
            # 在启动循环前稍等，实际就绪靠健康检查
            threading.Thread(
                target=lambda: (time.sleep(0.5), ready_event.set()),
                daemon=True,
            ).start()

        write_log("uvicorn.Server.run() begin")
        server.run()
        write_log("uvicorn.Server.run() exited")
    except Exception as e:
        write_log(f"run_server error: {e}\n{traceback.format_exc()}")
        if error_box is not None:
            error_box["err"] = e


class LauncherApp:
    BG = "#1e1b4b"
    CARD = "#312e81"
    ACCENT = "#6366f1"
    TEXT = "#e0e7ff"
    MUTED = "#a5b4fc"

    def __init__(self, preferred_port: int = 8000):
        self.preferred_port = preferred_port
        self.port = preferred_port
        self.local_ip = "127.0.0.1"
        self.data_dir = get_data_dir()
        self.local_url = f"http://127.0.0.1:{self.port}"
        self.lan_url = f"http://{self.local_ip}:{self.port}"
        self.root = tk.Tk()
        self.root.title("微机教室在线考试系统")
        self.root.geometry("540x540")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG)
        self._center_window()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_window(self):
        self.root.update_idletasks()
        w, h = 540, 540
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        header = tk.Frame(self.root, bg=self.BG)
        header.pack(fill="x", padx=28, pady=(28, 12))

        tk.Label(
            header,
            text="微机教室在线考试系统",
            font=("Microsoft YaHei UI", 18, "bold"),
            fg="white",
            bg=self.BG,
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Computer Lab Online Examination System",
            font=("Segoe UI", 10),
            fg=self.MUTED,
            bg=self.BG,
        ).pack(anchor="w", pady=(4, 0))

        card = tk.Frame(self.root, bg=self.CARD, padx=20, pady=18)
        card.pack(fill="both", expand=True, padx=28, pady=8)

        self.status_var = tk.StringVar(value="正在启动，请稍候...")
        tk.Label(
            card,
            textvariable=self.status_var,
            font=("Microsoft YaHei UI", 11),
            fg=self.TEXT,
            bg=self.CARD,
            wraplength=440,
            justify="left",
        ).pack(anchor="w")

        self.progress = ttk.Progressbar(card, mode="indeterminate", length=440)
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
            f"\n日志: {get_log_path()}"
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
            try:
                self.progress.stop()
                self.progress.pack_forget()
            except Exception:
                pass
            self.open_btn.config(state="normal")

    def update_urls(self):
        self.local_url = f"http://127.0.0.1:{self.port}"
        self.lan_url = f"http://{self.local_ip}:{self.port}"
        self.url_local.set(self.local_url)
        self.url_lan.set(self.lan_url)

    def open_browser(self):
        webbrowser.open(self.local_url)

    def _on_close(self):
        if messagebox.askokcancel("退出", "关闭窗口将停止考试系统服务，确定退出吗？"):
            self.root.destroy()
            os._exit(0)

    def start_background(self):
        threading.Thread(target=self._bootstrap, daemon=True).start()

    def _mark_ready(self, reused: bool = False):
        msg = "服务已在运行 · 可直接打开浏览器" if reused else "服务运行中 · 关闭本窗口即可停止服务"
        self.set_status(msg, running=True)
        self.update_urls()
        if not os.environ.get("EXAM_NO_BROWSER"):
            self.open_browser()

    def _bootstrap(self):
        try:
            write_log("bootstrap start")
            self.local_ip = get_local_ip()
            write_log(f"local_ip={self.local_ip}")
            self.root.after(0, self.update_urls)

            # 若本机已有实例在跑，直接复用，避免二次启动失败
            if check_health(self.preferred_port):
                write_log(f"reuse existing server on {self.preferred_port}")
                self.port = self.preferred_port
                self.root.after(0, lambda: self._mark_ready(reused=True))
                return

            self.root.after(0, lambda: self.set_status("正在初始化数据库..."))
            setup_environment()
            init_database()
            write_log("database ready")

            last_err = None
            for port in range(self.preferred_port, self.preferred_port + 15):
                if check_health(port):
                    self.port = port
                    write_log(f"found healthy server while scanning port {port}")
                    self.root.after(0, lambda: self._mark_ready(reused=True))
                    return

                self.port = port
                self.root.after(0, lambda p=port: self.set_status(f"服务启动中（端口 {p}）..."))
                self.root.after(0, self.update_urls)

                error_box: dict = {"err": None}
                t = threading.Thread(
                    target=run_server,
                    args=(port, None, error_box),
                    daemon=True,
                )
                t.start()
                write_log(f"waiting health on {port}")

                if wait_for_health(port, timeout=25.0):
                    write_log(f"health ok on {port}")
                    self.root.after(0, lambda: self._mark_ready(reused=False))
                    return

                last_err = error_box.get("err")
                write_log(f"port {port} not healthy, err={last_err}")
                time.sleep(0.4)

            detail = str(last_err) if last_err else "多个端口均未能成功启动"
            raise RuntimeError(
                f"服务启动失败：{detail}\n\n"
                f"请关闭占用 8000 端口的程序后重试，或以管理员身份运行。\n"
                f"日志：{get_log_path()}"
            )
        except Exception as e:
            write_log(f"bootstrap failed: {e}\n{traceback.format_exc()}")
            self.root.after(0, lambda: self._show_error(str(e)))

    def _show_error(self, msg: str):
        try:
            self.progress.stop()
        except Exception:
            pass
        messagebox.showerror("启动失败", msg)
        self.root.destroy()
        sys.exit(1)

    def run(self):
        # 先显示窗口，再后台初始化，避免用户感觉“点了没反应”
        self.root.after(100, self.start_background)
        self.root.mainloop()


def main():
    preferred = int(os.environ.get("EXAM_PORT", "8000"))
    write_log(f"main preferred={preferred}")

    if tk is None:
        setup_environment()
        init_database()
        if check_health(preferred):
            webbrowser.open(f"http://127.0.0.1:{preferred}")
            while True:
                time.sleep(3600)
        if not os.environ.get("EXAM_NO_BROWSER"):
            threading.Thread(
                target=lambda: (wait_for_health(preferred), webbrowser.open(f"http://127.0.0.1:{preferred}")),
                daemon=True,
            ).start()
        run_server(preferred)
        return

    LauncherApp(preferred).run()


if __name__ == "__main__":
    main()
