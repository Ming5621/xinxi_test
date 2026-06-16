#!/usr/bin/env python3
"""
微机教室考试系统 - Windows 启动器（PyInstaller 入口）
双击 exe 后：初始化数据库 → 启动服务 → 自动打开浏览器
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


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


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def setup_environment():
    bundle = get_bundle_dir()
    data = get_data_dir()
    backend = bundle / "backend"

    os.environ["EXAM_SYSTEM_DATA_DIR"] = str(data)
    os.environ["EXAM_SYSTEM_BUNDLE_DIR"] = str(bundle)

    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    os.chdir(str(backend))
    return backend, data


def init_database():
    print("正在初始化数据库...")
    import seed  # noqa: F401 - seed.py 执行初始化


def open_browser_later(port: int):
    if os.environ.get("EXAM_NO_BROWSER"):
        return
    time.sleep(2)
    webbrowser.open(f"http://localhost:{port}")


def main():
    port = int(os.environ.get("EXAM_PORT", "8000"))

    print("=" * 52)
    print("       微机教室在线考试系统")
    print("=" * 52)

    backend_dir, data_dir = setup_environment()
    print(f"\n数据目录: {data_dir}")
    print(f"数据库:   {data_dir / 'exam_system.db'}")

    try:
        init_database()
    except Exception as e:
        print(f"\n[警告] 数据库初始化出现问题: {e}")

    ip = get_local_ip()
    print(f"\n服务器启动中，请稍候...")
    print(f"  教师机本机: http://localhost:{port}")
    print(f"  学生机访问: http://{ip}:{port}")
    print(f"\n默认账号:")
    print(f"  教师: teacher / teacher123")
    print(f"  学生: student01 / 123456")
    print(f"\n关闭本窗口即可停止服务。")
    print("=" * 52)

    threading.Thread(target=open_browser_later, args=(port,), daemon=True).start()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n服务已停止。")
    except Exception as e:
        print(f"\n启动失败: {e}")
        input("\n按回车键退出...")
        sys.exit(1)
