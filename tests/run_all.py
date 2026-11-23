#!/usr/bin/env python3
"""运行全部测试"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

tests = [
    ("启动器健康检查", [sys.executable, "tests/test_launcher_health.py"]),
    ("时区", [sys.executable, "tests/test_timeutil.py"]),
    ("单元测试", [sys.executable, "tests/test_typing_utils.py"]),
    ("隔离 API 回归测试", [sys.executable, "tests/test_regressions.py"]),
    ("API 集成测试", [sys.executable, "tests/test_api.py"]),
    ("边界情况测试", [sys.executable, "tests/test_edge_cases.py"]),
    ("前端 E2E 测试", ["node", "tests/test_e2e.mjs"]),
    ("前端打字回归测试", ["node", "tests/test_typing_e2e.mjs"]),
]

failed = 0
for name, cmd in tests:
    print(f"\n>>> {name}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        failed += 1

print(f"\n{'='*50}")
print(f"测试完成: {len(tests) - failed}/{len(tests)} 通过")
sys.exit(1 if failed else 0)
