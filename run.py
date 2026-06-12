#!/usr/bin/env python3
"""启动考试系统服务器"""
import socket
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent / "backend"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    print("=" * 50)
    print("  微机教室在线考试系统")
    print("=" * 50)

    print("\n正在初始化数据库...")
    subprocess.run([sys.executable or "python3", str(BACKEND_DIR / "seed.py")], check=True)

    ip = get_local_ip()
    port = 8000
    print(f"\n服务器启动中...")
    print(f"  教师机访问: http://localhost:{port}")
    print(f"  学生机访问: http://{ip}:{port}")
    print(f"\n默认账号:")
    print(f"  教师: teacher / teacher123")
    print(f"  学生: student01 / 123456")
    print("=" * 50)

    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False, app_dir=str(BACKEND_DIR))


if __name__ == "__main__":
    main()
