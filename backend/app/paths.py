"""应用路径配置（开发模式 / PyInstaller 打包模式）"""
import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_data_dir() -> Path:
    """可写数据目录（数据库等）"""
    env = os.environ.get("EXAM_SYSTEM_DATA_DIR")
    if env:
        p = Path(env)
    elif is_frozen():
        p = Path(os.environ.get("APPDATA", Path.home())) / "微机教室考试系统"
    else:
        p = Path(__file__).resolve().parent.parent
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_bundle_dir() -> Path:
    """只读资源目录（前端静态文件等）"""
    env = os.environ.get("EXAM_SYSTEM_BUNDLE_DIR")
    if env:
        return Path(env)
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def get_backend_dir() -> Path:
    if is_frozen():
        return get_bundle_dir() / "backend"
    return Path(__file__).resolve().parent.parent


def get_db_path() -> Path:
    return get_data_dir() / "exam_system.db"


def get_static_dir() -> Path:
    bundle = get_bundle_dir()
    static = bundle / "frontend" / "dist"
    if static.exists():
        return static
    # 开发模式回退
    dev_static = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    return dev_static
