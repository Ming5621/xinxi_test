#!/usr/bin/env python3
"""启动器健康检查与界面倒计时。不启动完整考试服务。"""
import importlib.util
import os
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("exam_launcher", ROOT / "packaging" / "launcher.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)

passed = 0
failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} — {detail}")


def serve_once(payload: bytes):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def run():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        try:
            conn.settimeout(1.0)
            try:
                conn.recv(1024)
            except socket.timeout:
                pass
            conn.sendall(payload)
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
            srv.close()

    threading.Thread(target=run, daemon=True).start()
    return srv, port


print("启动器健康检查")
print("-" * 40)

body = b'{"status":"ok","message":"up"}'
resp = (
    b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode("ascii")
    + b"\r\nConnection: close\r\n\r\n" + body
)
srv, port = serve_once(resp)
try:
    check("健康接口 200 且正文含 ok", launcher.check_health(port, timeout=1.0) is True)
finally:
    srv.close()

closed = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
closed.bind(("127.0.0.1", 0))
closed_port = closed.getsockname()[1]
closed.close()
check("未监听端口返回失败", launcher.check_health(closed_port, timeout=0.3) is False)

hang = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
hang.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
hang.bind(("127.0.0.1", 0))
hang.listen(1)
hang_port = hang.getsockname()[1]
stop_hang = threading.Event()


def accept_and_hold():
    try:
        conn, _ = hang.accept()
    except OSError:
        return
    stop_hang.wait(2.0)
    try:
        conn.close()
    except OSError:
        pass


threading.Thread(target=accept_and_hold, daemon=True).start()
t0 = time.monotonic()
hung_result = launcher.check_health(hang_port, timeout=0.3)
elapsed = time.monotonic() - t0
stop_hang.set()
hang.close()
check("对端不回包时在超时内返回", hung_result is False and elapsed < 1.2, f"result={hung_result} elapsed={elapsed:.2f}s")

bad_body = b"HTTP/1.1 500 ERR\r\nContent-Length: 5\r\nConnection: close\r\n\r\nnope\n"
srv, port = serve_once(bad_body)
try:
    check("非 200 不算健康", launcher.check_health(port, timeout=1.0) is False)
finally:
    srv.close()

env = launcher.sanitized_child_env({
    "HTTP_PROXY": "http://127.0.0.1:9",
    "https_proxy": "http://127.0.0.1:9",
    "ALL_PROXY": "socks5://127.0.0.1:9",
    "PATH": "/usr/bin",
})
check(
    "子进程环境去掉代理",
    "HTTP_PROXY" not in env and "https_proxy" not in env and "ALL_PROXY" not in env
    and env.get("NO_PROXY") == "*" and env.get("no_proxy") == "*"
    and env.get("PYTHONUNBUFFERED") == "1" and env.get("PATH") == "/usr/bin",
    str({k: env.get(k) for k in ("HTTP_PROXY", "https_proxy", "ALL_PROXY", "NO_PROXY", "PYTHONUNBUFFERED")}),
)

# 界面倒计时必须在主线程推进，且能从「已等待 0s」继续往前走。
has_display = sys.platform == "win32" or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
if launcher.tk is None or not has_display:
    print("  - 跳过界面倒计时（当前环境没有图形界面）")
else:
    os.environ["EXAM_NO_BROWSER"] = "1"
    app = launcher.LauncherApp()
    app.root.withdraw()
    samples = []

    def sample():
        samples.append(app.status_var.get())
        if len(samples) >= 8:
            app._cancel_wait_progress()
            app.root.quit()
            return
        app.root.after(250, sample)

    app._pump_ui()
    app._arm_wait_progress(18765, 75)
    app.root.after(250, sample)
    app.root.after(5000, app.root.quit)
    app.root.mainloop()
    joined = " | ".join(samples)
    button_state = str(app.open_btn["state"])
    app._stop_ui_timers()
    try:
        app.root.destroy()
    except Exception:
        pass
    check("倒计时从 0 秒继续增加", any("已等待 0s" in s for s in samples) and any("已等待 1s" in s for s in samples), joined)
    check("等待过程中打开浏览器保持禁用", button_state == "disabled", button_state)

    app = launcher.LauncherApp()
    app.root.withdraw()
    app.port = 18765
    holder = {}

    def worker():
        # 模拟服务进程：只入队，不直接碰界面
        time.sleep(0.3)
        app.post_ui(lambda: app._arm_wait_progress(18765, 75))
        time.sleep(1.1)
        app.post_ui(lambda: app._mark_ready(reused=False))

    threading.Thread(target=worker, daemon=True).start()

    def watch():
        text = app.status_var.get()
        if "服务运行中" in text and str(app.open_btn["state"]) == "normal":
            seen = holder.get("seen_ready")
            if seen is None:
                holder["seen_ready"] = time.monotonic()
            elif time.monotonic() - seen > 0.6:
                holder["final"] = text
                holder["state"] = str(app.open_btn["state"])
                app.root.quit()
                return
        app.root.after(100, watch)

    app._pump_ui()
    app.root.after(100, watch)
    app.root.after(6000, app.root.quit)
    app.root.mainloop()
    final_text = holder.get("final", app.status_var.get())
    final_state = holder.get("state", str(app.open_btn["state"]))
    app._stop_ui_timers()
    try:
        app.root.destroy()
    except Exception:
        pass
    check("服务就绪后离开等待页并启用按钮", "服务运行中" in final_text and "已等待" not in final_text and final_state == "normal", f"{final_text} / {final_state}")

print("-" * 40)
print(f"通过 {passed}，失败 {failed}")
sys.exit(1 if failed else 0)
