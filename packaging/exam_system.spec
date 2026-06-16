# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 - 在 Windows 上运行 build_windows.bat 生成 exe"""
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"

block_cipher = None

# 打包数据文件
datas = [
    (str(FRONTEND_DIST), "frontend/dist"),
    (str(BACKEND / "app"), "backend/app"),
    (str(BACKEND / "seed.py"), "backend"),
]

# 隐式导入
hiddenimports = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "fastapi",
    "starlette",
    "starlette.routing",
    "starlette.responses",
    "starlette.staticfiles",
    "starlette.middleware",
    "starlette.middleware.cors",
    "sqlalchemy",
    "sqlalchemy.sql.default_comparator",
    "pydantic",
    "pydantic.deprecated",
    "pydantic.deprecated.decorator",
    "jose",
    "jose.jwt",
    "passlib",
    "passlib.handlers",
    "passlib.handlers.bcrypt",
    "bcrypt",
    "multipart",
    "email_validator",
    "app",
    "app.main",
    "app.database",
    "app.models",
    "app.schemas",
    "app.auth",
    "app.paths",
    "app.typing_utils",
    "app.import_utils",
    "app.routers",
    "app.routers.auth",
    "app.routers.users",
    "app.routers.exams",
    "app.routers.stats",
    "app.routers.typing",
    "app.routers.import_data",
]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(BACKEND), str(ROOT / "packaging")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy", "PIL"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ExamSystem",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可放置 packaging/icon.ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="微机教室考试系统",
)
