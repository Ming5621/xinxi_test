#!/usr/bin/env python3
"""
微机教室考试系统 - Windows 图形化启动器（PyInstaller 入口）

启动流程：
1. GUI 进程自动挑选空闲端口（默认优先 18765，避开 8000 等常用端口）
2. 以子进程方式启动 HTTP 服务（避免线程内 uvicorn 在 Windows 卡死）
3. 自动放行 Windows 防火墙入站端口
4. 健康检查通过后自动打开浏览器

用法：
  ExamSystem.exe              # GUI 启动器
  ExamSystem.exe --serve 18765  # 仅启动服务（内部调用）

版权所有 © 柴延明
"""
from __future__ import annotations

import atexit
import os
import queue
import socket
import subprocess
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

# 优先使用的端口：高位、少冲突，不影响常见系统服务
PREFERRED_PORTS = [
    18765, 18766, 18767, 18768, 18769,
    18770, 18771, 18772, 18773, 18774,
    8765, 8766, 9765, 9766, 9788,
]

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

_server_proc: subprocess.Popen | None = None


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
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass
        return "127.0.0.1"


APP_VERSION = "1.2.10"

_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


def health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def sanitized_child_env(base: dict | None = None) -> dict:
    """子进程不继承系统代理。教室电脑的代理会让本机健康检查和启动一直挂起。"""
    env = dict(os.environ if base is None else base)
    for key in _PROXY_ENV_KEYS:
        env.pop(key, None)
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def check_health(port: int, timeout: float = 0.25) -> bool:
    """直连 127.0.0.1，不走系统代理。超时由套接字强制切断，避免界面一直停在 0 秒。"""
    sock = None
    try:
        sock = socket.create_connection(("127.0.0.1", int(port)), timeout=timeout)
        deadline = time.monotonic() + timeout
        sock.settimeout(timeout)
        request = (
            f"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            "Connection: close\r\n\r\n"
        )
        sock.sendall(request.encode("ascii"))
        chunks = []
        total = 0
        while total < 8192 and time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                piece = sock.recv(1024)
            except socket.timeout:
                break
            if not piece:
                break
            chunks.append(piece)
            total += len(piece)
        text = b"".join(chunks).decode("utf-8", errors="ignore")
        head, _, body = text.partition("\r\n\r\n")
        status_line = head.split("\r\n", 1)[0]
        return status_line.startswith("HTTP/") and " 200 " in status_line and "ok" in body.lower()
    except Exception:
        return False
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def wait_for_health(
    port: int,
    timeout: float = 60.0,
    proc: subprocess.Popen | None = None,
    on_tick=None,
) -> bool:
    deadline = time.time() + timeout
    started = time.time()
    last_tick = -1
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            write_log(f"server process exited early code={proc.returncode}")
            return False
        if check_health(port, timeout=0.35):
            write_log(f"health ok after {time.time() - started:.2f}s")
            return True
        elapsed = int(time.time() - started)
        if elapsed != last_tick:
            last_tick = elapsed
            if elapsed == 0 or elapsed % 5 == 0:
                alive = None if proc is None else proc.poll() is None
                write_log(f"health wait {elapsed}s/{int(timeout)}s port={port} proc_alive={alive}")
            if on_tick is not None:
                try:
                    on_tick(elapsed, int(timeout))
                except Exception:
                    pass
        time.sleep(0.2)
    return False


def is_port_free(port: int) -> bool:
    """检测端口是否可绑定（未被占用）。"""
    for host in ("127.0.0.1", "0.0.0.0"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.settimeout(0.2)
                s.bind((host, port))
        except OSError:
            return False
    return True


def choose_port(preferred: int | None = None) -> int:
    """选择空闲端口；若占用端口已是本系统健康服务则直接复用。

    旧逻辑对每个占用端口先做 HTTP 健康检查（超时 ~0.8s），教室环境端口被占时会假死数秒到数十秒。
    现改为：优先端口上「空闲则用 / 占用则短超时看是否可复用」；扩展段只做 bind，不再 HTTP。
    """
    primary: list[int] = []
    if preferred:
        primary.append(preferred)
    primary.extend(PREFERRED_PORTS)

    extended = list(range(18775, 18820))
    t0 = time.time()
    seen: set[int] = set()

    for port in primary:
        if port in seen or port < 1024 or port > 65535:
            continue
        seen.add(port)
        if is_port_free(port):
            write_log(f"selected free port {port} in {time.time() - t0:.3f}s")
            return port
        # 占用时才短超时探测，避免空闲端口也走 HTTP
        if check_health(port, timeout=0.08):
            write_log(f"reuse healthy port {port} in {time.time() - t0:.3f}s")
            return port
        write_log(f"port busy {port}")

    for port in extended:
        if port in seen or port < 1024 or port > 65535:
            continue
        seen.add(port)
        if is_port_free(port):
            write_log(f"selected free port {port} in {time.time() - t0:.3f}s")
            return port
        write_log(f"port busy {port}")
    raise RuntimeError("未找到可用端口，请关闭占用程序后重试")


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
    import seed

    seed.run_seed(quiet=True)


def open_firewall_port(port: int) -> None:
    """自动放行 Windows 防火墙入站端口，便于学生机访问。"""
    if sys.platform != "win32":
        return
    rule = f"微机教室考试系统-{port}"
    exe = str(sys.executable) if getattr(sys, "frozen", False) else ""
    try:
        subprocess.run(
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule}"],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=8,
        )
        r1 = subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule}",
                "dir=in",
                "action=allow",
                "protocol=TCP",
                f"localport={port}",
                "profile=any",
                "enable=yes",
            ],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=8,
        )
        write_log(f"firewall port rule: code={r1.returncode} out={(r1.stdout or r1.stderr or '').strip()}")
        if exe:
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule", "name=微机教室考试系统程序"],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
                timeout=8,
            )
            r2 = subprocess.run(
                [
                    "netsh", "advfirewall", "firewall", "add", "rule",
                    "name=微机教室考试系统程序",
                    "dir=in",
                    "action=allow",
                    f"program={exe}",
                    "enable=yes",
                    "profile=any",
                ],
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW,
                timeout=8,
            )
            write_log(f"firewall program rule: code={r2.returncode}")
    except Exception as e:
        write_log(f"firewall setup failed: {e}")


def stop_server_process() -> None:
    global _server_proc
    proc = _server_proc
    _server_proc = None
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        write_log("server process stopped")
    except Exception as e:
        write_log(f"stop server failed: {e}")


def start_server_process(port: int) -> subprocess.Popen:
    """用独立子进程启动服务，避免 GUI 线程内跑 uvicorn 卡住。"""
    global _server_proc
    stop_server_process()

    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--serve", str(port)]
    else:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--serve", str(port)]

    log_file = get_data_dir() / "server.log"
    write_log(f"starting server process: {cmd}")
    stdout = open(log_file, "a", encoding="utf-8")
    stdout.write(f"\n===== serve port={port} at {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    stdout.flush()

    env = sanitized_child_env()

    popen_kwargs = {
        "args": cmd,
        "stdin": subprocess.DEVNULL,
        "stdout": stdout,
        "stderr": subprocess.STDOUT,
        "cwd": str(get_install_dir()),
        "env": env,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = CREATE_NO_WINDOW

    proc = subprocess.Popen(**popen_kwargs)
    _server_proc = proc
    atexit.register(stop_server_process)
    write_log(f"server pid={proc.pid}")
    return proc


def run_server_foreground(port: int) -> None:
    """--serve 模式：前台运行 uvicorn。"""
    import asyncio

    import uvicorn
    from app.main import app

    write_log(f"serve foreground port={port}")
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True,
        lifespan="on",
        timeout_keep_alive=30,
    )
    server = uvicorn.Server(config)
    # 子进程主线程可安装信号；若失败则忽略
    try:
        server.install_signal_handlers()
    except Exception:
        server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

    asyncio.run(server.serve())


class LauncherApp:
    BG = "#1e1b4b"
    CARD = "#312e81"
    ACCENT = "#6366f1"
    TEXT = "#e0e7ff"
    MUTED = "#a5b4fc"

    def __init__(self):
        self.port = PREFERRED_PORTS[0]
        self.local_ip = "127.0.0.1"
        self.local_url = f"http://127.0.0.1:{self.port}"
        self.lan_url = f"http://{self.local_ip}:{self.port}"
        self.root = tk.Tk()
        self.root.title("微机教室在线考试系统")
        self.root.geometry("560x560")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG)
        self._center_window()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._ui_queue: queue.Queue = queue.Queue()
        self._wait_gen = 0
        self._error_shown = False
        self._ui_running = True
        self._pump_after_id = None
        self._wait_after_id = None

    def _center_window(self):
        self.root.update_idletasks()
        w, h = 560, 560
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
            text="自动选择空闲端口并启动服务",
            font=("Segoe UI", 10),
            fg=self.MUTED,
            bg=self.BG,
        ).pack(anchor="w", pady=(4, 0))

        card = tk.Frame(self.root, bg=self.CARD, padx=20, pady=18)
        card.pack(fill="both", expand=True, padx=28, pady=8)

        self.status_var = tk.StringVar(value="正在准备启动...")
        tk.Label(
            card,
            textvariable=self.status_var,
            font=("Microsoft YaHei UI", 11),
            fg=self.TEXT,
            bg=self.CARD,
            wraplength=460,
            justify="left",
        ).pack(anchor="w")

        self.progress = ttk.Progressbar(card, mode="indeterminate", length=460)
        self.progress.pack(fill="x", pady=(14, 18))
        self.progress.start(12)

        info = tk.Frame(card, bg=self.CARD)
        info.pack(fill="x")
        self.url_local = tk.StringVar(value=self.local_url)
        self.url_lan = tk.StringVar(value=self.lan_url)
        self.port_var = tk.StringVar(value=f"服务端口：{self.port}")

        tk.Label(info, textvariable=self.port_var, font=("Microsoft YaHei UI", 10, "bold"), fg="white", bg=self.CARD).pack(anchor="w", pady=(0, 10))
        tk.Label(info, text="教师机本机访问", font=("Microsoft YaHei UI", 9), fg=self.MUTED, bg=self.CARD).pack(anchor="w")
        tk.Label(info, textvariable=self.url_local, font=("Consolas", 12), fg="white", bg=self.CARD).pack(anchor="w", pady=(2, 10))
        tk.Label(info, text="学生机局域网访问", font=("Microsoft YaHei UI", 9), fg=self.MUTED, bg=self.CARD).pack(anchor="w")
        tk.Label(info, textvariable=self.url_lan, font=("Consolas", 12), fg="white", bg=self.CARD).pack(anchor="w", pady=(2, 10))

        hint = (
            "登录说明\n"
            "  学生：登录页输入姓名即可\n"
            "  教师：teacher1~teacher4\n"
            f"\n日志目录: {get_data_dir()}"
        )
        tk.Label(card, text=hint, font=("Microsoft YaHei UI", 9), fg=self.MUTED, bg=self.CARD, justify="left").pack(anchor="w", pady=(8, 0))

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
            text=f"版权所有 © 柴延明 · 保留所有权利 · v{APP_VERSION}",
            font=("Microsoft YaHei UI", 9),
            fg=self.MUTED,
            bg=self.BG,
        ).pack(pady=(0, 16))

    def post_ui(self, fn) -> None:
        """后台线程只入队，由主线程刷新界面。直接 root.after 在 Windows 上会卡死 Tk。"""
        self._ui_queue.put(fn)

    def _pump_ui(self) -> None:
        try:
            while True:
                fn = self._ui_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    write_log(f"ui callback failed\n{traceback.format_exc()}")
        except queue.Empty:
            pass
        if not self._ui_running:
            return
        try:
            if self.root.winfo_exists():
                self._pump_after_id = self.root.after(100, self._pump_ui)
        except Exception:
            pass

    def set_status(self, text: str, running: bool = False, progress: float | None = None):
        self.status_var.set(text)
        if progress is not None:
            try:
                if str(self.progress["mode"]) != "determinate":
                    self.progress.stop()
                    self.progress.configure(mode="determinate", maximum=100)
                self.progress["value"] = max(0.0, min(100.0, float(progress)))
            except Exception:
                pass
        if running:
            try:
                self.progress.stop()
                self.progress.pack_forget()
            except Exception:
                pass
            self.open_btn.config(state="normal")

    def _arm_wait_progress(self, port: int, total: int) -> None:
        """倒计时只在主线程刷新。后台线程直接调用 Tk 会在 Windows 上把窗口卡在 0 秒。"""
        self._wait_gen += 1
        gen = self._wait_gen
        started = time.time()

        def tick():
            if gen != self._wait_gen or self._error_shown:
                return
            elapsed = int(time.time() - started)
            if elapsed > total:
                self._show_error(
                    f"端口 {port} 服务启动超时（超过 {total} 秒）。\n\n"
                    f"请查看日志：\n{get_log_path()}\n{get_data_dir() / 'server.log'}"
                )
                return
            self.set_status(
                f"正在启动服务（端口 {port}）… 已等待 {elapsed}s / {total}s",
                progress=min(95.0, elapsed * 100 / max(total, 1)),
            )
            try:
                self._wait_after_id = self.root.after(200, tick)
            except Exception:
                pass

        tick()

    def _cancel_wait_progress(self) -> None:
        self._wait_gen += 1
        after_id = self._wait_after_id
        self._wait_after_id = None
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass

    def _stop_ui_timers(self) -> None:
        self._ui_running = False
        self._cancel_wait_progress()
        pump_id = self._pump_after_id
        self._pump_after_id = None
        if pump_id is not None:
            try:
                self.root.after_cancel(pump_id)
            except Exception:
                pass

    def refresh_urls(self):
        self.local_url = f"http://127.0.0.1:{self.port}"
        self.lan_url = f"http://{self.local_ip}:{self.port}"
        self.url_local.set(self.local_url)
        self.url_lan.set(self.lan_url)
        self.port_var.set(f"服务端口：{self.port}")

    def open_browser(self):
        webbrowser.open(self.local_url)

    def _on_close(self):
        if messagebox.askokcancel("退出", "关闭窗口将停止考试系统服务，确定退出吗？"):
            self._stop_ui_timers()
            stop_server_process()
            self.root.destroy()
            os._exit(0)

    def _mark_ready(self, reused: bool = False):
        self._cancel_wait_progress()
        self.refresh_urls()
        msg = (
            f"服务已在运行（端口 {self.port}）"
            if reused
            else f"服务运行中（端口 {self.port}）· 关闭本窗口即停止"
        )
        self.set_status(msg, running=True)
        if not os.environ.get("EXAM_NO_BROWSER"):
            self.open_browser()

    def _bootstrap(self):
        try:
            t_boot = time.time()
            write_log("gui bootstrap start")
            env_port = os.environ.get("EXAM_PORT")
            preferred = int(env_port) if env_port else None

            self.post_ui(lambda: self.set_status("正在检测空闲端口..."))
            self.local_ip = get_local_ip()
            self.port = choose_port(preferred)
            self.post_ui(self.refresh_urls)
            write_log(f"chosen port={self.port} ip={self.local_ip}")

            if check_health(self.port, timeout=0.35):
                self.post_ui(lambda: self._mark_ready(reused=True))
                return

            # 仅确保数据目录存在；数据库初始化在服务子进程中完成，避免重复耗时
            get_data_dir()
            setup_environment()

            # 先拉起服务进程，防火墙放行并行进行，避免 netsh 阻塞服务启动
            port = self.port
            proc = start_server_process(port)
            threading.Thread(target=open_firewall_port, args=(port,), daemon=True).start()
            # 进度条由主线程自己走，后台线程只负责拉起进程和健康检查
            self.post_ui(lambda p=port: self._arm_wait_progress(p, 75))

            if not wait_for_health(self.port, timeout=75.0, proc=proc):
                # 读一点服务日志便于提示
                server_log = get_data_dir() / "server.log"
                tail = ""
                try:
                    text = server_log.read_text(encoding="utf-8", errors="ignore")
                    tail = text[-600:]
                except Exception:
                    pass
                raise RuntimeError(
                    f"端口 {self.port} 服务未能启动。\n\n"
                    f"请查看日志：\n{get_log_path()}\n{server_log}\n\n"
                    f"{tail}"
                )

            write_log(f"health ok port={self.port} bootstrap={time.time() - t_boot:.2f}s")
            self.post_ui(lambda: self._mark_ready(reused=False))
        except Exception as e:
            write_log(f"bootstrap failed: {e}\n{traceback.format_exc()}")
            message = str(e)
            self.post_ui(lambda m=message: self._show_error(m))

    def _show_error(self, msg: str):
        if self._error_shown:
            return
        self._error_shown = True
        self._stop_ui_timers()
        try:
            self.progress.stop()
        except Exception:
            pass
        messagebox.showerror("启动失败", msg)
        stop_server_process()
        self.root.destroy()
        sys.exit(1)

    def run(self):
        self._pump_ui()
        self.root.after(120, lambda: threading.Thread(target=self._bootstrap, daemon=True).start())
        self.root.mainloop()


def serve_main(port: int) -> int:
    try:
        t0 = time.time()
        setup_environment()
        write_log(f"serve setup done {time.time() - t0:.2f}s")
        init_database()
        write_log(f"serve db ready {time.time() - t0:.2f}s")
        # 防火墙已在 GUI 侧并行处理；此处再兜底一次（短超时）
        threading.Thread(target=open_firewall_port, args=(port,), daemon=True).start()
        run_server_foreground(port)
        return 0
    except Exception as e:
        write_log(f"serve_main failed: {e}\n{traceback.format_exc()}")
        print(f"服务启动失败: {e}", file=sys.stderr)
        return 1


def main() -> int:
    # 子进程服务模式
    if len(sys.argv) >= 2 and sys.argv[1] in ("--serve", "serve"):
        port = int(sys.argv[2]) if len(sys.argv) >= 3 else PREFERRED_PORTS[0]
        write_log(f"argv serve port={port}")
        return serve_main(port)

    write_log("argv gui mode")
    if tk is None:
        port = choose_port(int(os.environ["EXAM_PORT"]) if os.environ.get("EXAM_PORT") else None)
        if check_health(port):
            webbrowser.open(f"http://127.0.0.1:{port}")
            while True:
                time.sleep(3600)
        open_firewall_port(port)
        proc = start_server_process(port)
        if wait_for_health(port, timeout=75.0, proc=proc):
            webbrowser.open(f"http://127.0.0.1:{port}")
            try:
                proc.wait()
            except KeyboardInterrupt:
                stop_server_process()
            return 0
        stop_server_process()
        return 1

    LauncherApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
