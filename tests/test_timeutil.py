"""UTC 序列化与本地展示约定。

缺 Asia/Shanghai 时区键时（精简 Windows / 未打包 tzdata），工具函数仍要给出
UTC+8，并且服务能完成导入、健康检查能返回。
"""
import logging
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.schemas import StudentPresenceOut
from app.timeutil import DISPLAY_TZ, format_local, load_display_tz, serialize_utc_datetime


def test_serialize_naive_utc_uses_z():
    dt = datetime(2026, 10, 23, 7, 0, 0)
    assert serialize_utc_datetime(dt) == "2026-10-23T07:00:00Z"


def test_format_local_shanghai():
    dt = datetime(2026, 10, 23, 7, 0, 0)
    assert format_local(dt) == "2026-10-23 15:00"


def test_presence_json_marks_utc():
    payload = StudentPresenceOut(
        id=1,
        username="s1",
        name="张三",
        class_name="微机1班",
        is_active=True,
        is_online=True,
        last_seen_at=datetime(2026, 10, 23, 7, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None),
    )
    data = payload.model_dump(mode="json")
    assert data["last_seen_at"] == "2026-10-23T07:00:00Z"


def test_display_tz_uses_zoneinfo_when_available():
    tz = load_display_tz()
    assert isinstance(tz, ZoneInfo)
    assert tz.key == "Asia/Shanghai"
    assert isinstance(DISPLAY_TZ, ZoneInfo)
    assert DISPLAY_TZ.key == "Asia/Shanghai"
    assert tz.utcoffset(datetime(2026, 10, 23, 7, 0)) == timedelta(hours=8)


def test_load_display_tz_falls_back_when_key_missing():
    import app.timeutil as timeutil

    def missing(_key):
        raise ZoneInfoNotFoundError("No time zone found with key Asia/Shanghai")

    original = timeutil.ZoneInfo
    timeutil.ZoneInfo = missing
    logging.disable(logging.WARNING)
    try:
        tz = timeutil.load_display_tz()
    finally:
        logging.disable(logging.NOTSET)
        timeutil.ZoneInfo = original

    sample = datetime(2026, 10, 23, 7, 0, 0)
    assert not isinstance(tz, ZoneInfo)
    assert tz.utcoffset(sample) == timedelta(hours=8)
    assert tz.tzname(sample) == "Asia/Shanghai"
    assert sample.replace(tzinfo=timezone.utc).astimezone(tz).strftime("%Y-%m-%d %H:%M") == "2026-10-23 15:00"


def test_tzdata_supplies_shanghai_without_system_database():
    """系统时区路径为空、但安装了 tzdata 时，仍然使用真正的 Asia/Shanghai。"""
    script = textwrap.dedent(
        """
        import os
        import sys
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        sys.path.insert(0, os.environ["EXAM_BACKEND"])
        from app.timeutil import DISPLAY_TZ, format_local

        assert isinstance(DISPLAY_TZ, ZoneInfo), type(DISPLAY_TZ)
        assert DISPLAY_TZ.key == "Asia/Shanghai"
        sample = datetime(2026, 10, 23, 7, 0, 0)
        assert DISPLAY_TZ.utcoffset(sample) == timedelta(hours=8)
        assert format_local(sample) == "2026-10-23 15:00"
        print("tzdata-ok")
        """
    )
    result = _run_child(script)
    assert result.returncode == 0, result.stderr
    assert "tzdata-ok" in result.stdout


def test_service_starts_when_shanghai_key_missing():
    """没有 Asia/Shanghai 键时，展示时区是 UTC+8，健康检查能通过。"""
    script = textwrap.dedent(
        """
        import asyncio
        import importlib.abc
        import importlib.machinery
        import json
        import os
        import sys
        import threading
        import time
        import urllib.request
        from datetime import datetime, timedelta, timezone

        class BlockTzdata(importlib.abc.MetaPathFinder, importlib.abc.Loader):
            def find_spec(self, fullname, path, target=None):
                if fullname == "tzdata" or fullname.startswith("tzdata."):
                    return importlib.machinery.ModuleSpec(fullname, self)
                return None

            def create_module(self, spec):
                raise ModuleNotFoundError(spec.name)

            def exec_module(self, module):
                raise ModuleNotFoundError(getattr(module, "__name__", "tzdata"))

        sys.meta_path.insert(0, BlockTzdata())

        import zoneinfo
        from zoneinfo import ZoneInfo

        zoneinfo.reset_tzpath(())
        ZoneInfo.clear_cache()

        sys.path.insert(0, os.environ["EXAM_BACKEND"])
        from app.timeutil import DISPLAY_TZ, format_local, serialize_utc_datetime, utc_now

        sample = datetime(2026, 10, 23, 7, 0, 0)
        assert not isinstance(DISPLAY_TZ, ZoneInfo), type(DISPLAY_TZ)
        assert DISPLAY_TZ.utcoffset(sample) == timedelta(hours=8)
        assert DISPLAY_TZ.tzname(sample) == "Asia/Shanghai"
        assert format_local(sample) == "2026-10-23 15:00"
        assert format_local(None) == ""
        assert serialize_utc_datetime(sample) == "2026-10-23T07:00:00Z"
        assert utc_now().tzinfo is None

        from app.schemas import StudentPresenceOut

        payload = StudentPresenceOut(
            id=1,
            username="s1",
            name="张三",
            class_name="微机1班",
            is_active=True,
            is_online=True,
            last_seen_at=sample,
        )
        assert payload.model_dump(mode="json")["last_seen_at"] == "2026-10-23T07:00:00Z"

        from app.main import app, health

        assert health()["status"] == "ok"

        import uvicorn

        port = int(os.environ["EXAM_PORT"])
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="error",
            access_log=False,
        )
        server = uvicorn.Server(config)
        ready = threading.Event()

        def wait_until_healthy():
            deadline = time.time() + 30
            url = f"http://127.0.0.1:{port}/api/health"
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(url, timeout=0.5) as resp:
                        body = json.loads(resp.read().decode())
                        if resp.status == 200 and body.get("status") == "ok":
                            ready.set()
                            server.should_exit = True
                            return
                except Exception:
                    time.sleep(0.15)
            server.should_exit = True

        threading.Thread(target=wait_until_healthy, daemon=True).start()
        asyncio.run(server.serve())
        if not ready.is_set():
            raise SystemExit("服务未能启动")
        print("service-ok")
        """
    )
    result = _run_child(script)
    assert result.returncode == 0, result.stderr[-2000:]
    assert "service-ok" in result.stdout


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run_child(script: str) -> subprocess.CompletedProcess:
    data_dir = tempfile.mkdtemp(prefix="exam-tz-")
    env = os.environ.copy()
    env["PYTHONTZPATH"] = ""
    env["EXAM_BACKEND"] = str(ROOT / "backend")
    env["EXAM_SYSTEM_DATA_DIR"] = data_dir
    env["EXAM_PORT"] = str(_free_port())
    try:
        return subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    test_serialize_naive_utc_uses_z()
    test_format_local_shanghai()
    test_presence_json_marks_utc()
    test_display_tz_uses_zoneinfo_when_available()
    test_load_display_tz_falls_back_when_key_missing()
    test_tzdata_supplies_shanghai_without_system_database()
    test_service_starts_when_shanghai_key_missing()
    print("timeutil ok")
