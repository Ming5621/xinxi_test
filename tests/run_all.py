#!/usr/bin/env python3
"""运行全部测试"""
import subprocess
import sys

tests = [
    ("单元测试", ["python3", "tests/test_typing_utils.py"]),
    ("API 集成测试", ["python3", "tests/test_api.py"]),
    ("边界情况测试", ["python3", "tests/test_edge_cases.py"]),
    ("前端 E2E 测试", ["node", "tests/test_e2e.mjs"]),
]

failed = 0
for name, cmd in tests:
    print(f"\n>>> {name}")
    result = subprocess.run(cmd, cwd="/workspace")
    if result.returncode != 0:
        failed += 1

print(f"\n{'='*50}")
print(f"测试完成: {len(tests) - failed}/{len(tests)} 通过")
sys.exit(1 if failed else 0)
