"""UTC 序列化与本地展示约定。"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas import StudentPresenceOut
from app.timeutil import format_local, serialize_utc_datetime


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


if __name__ == "__main__":
    test_serialize_naive_utc_uses_z()
    test_format_local_shanghai()
    test_presence_json_marks_utc()
    print("timeutil ok")
