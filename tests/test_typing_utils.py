#!/usr/bin/env python3
"""打字工具单元测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.typing_utils import compare_text, calculate_wpm, score_typing_question, get_typing_level
from app.import_utils import parse_students_text, parse_questions_text

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


print("打字工具单元测试")
print("-" * 40)

# compare_text
r = compare_text("你好世界", "你好世x")
check("compare_text 正确数", r["correct_chars"] == 3, str(r))
check("compare_text 准确率", r["accuracy"] == 75.0, str(r))

r2 = compare_text("abc", "abc")
check("compare_text 全对", r2["correct_chars"] == 3 and r2["accuracy"] == 100)

# calculate_wpm
check("wpm计算", calculate_wpm(30, 60) == 30.0)
check("wpm零时间", calculate_wpm(10, 0) == 0.0)

# score_typing_question
score, passed_flag, remark = score_typing_question(35, 96, 18)
check("打字评分-优秀", score >= 16 and passed_flag, f"score={score}")

score2, _, _ = score_typing_question(5, 96, 18)
check("打字评分-未达标", score2 < 10, f"score={score2}")

score3, _, _ = score_typing_question(30, 70, 18)
check("打字评分-低准确率", score3 < 10, f"score={score3}")

# get_typing_level
check("等级-卓越", get_typing_level(45)["level"] == "卓越")
check("等级-达标", get_typing_level(15)["level"] == "达标")
check("等级-未达标", get_typing_level(5)["level"] == "未达标")

# parse_students_text
students, errs = parse_students_text("s01,张三,1班,123\ns02,李四,2班,", "000000")
check("学生解析", len(students) == 2 and students[1]["password"] == "000000", str(students))

# parse_questions_text - CSV
qs, errs = parse_questions_text("类型,题目,选项A,选项B,选项C,选项D,答案,分值\nchoice,测试,A,B,C,D,A,5")
check("题目CSV解析", len(qs) == 1 and qs[0]["correct_answer"] == "A")

# parse_questions_text - block
block = """[选择] 1+1=?
A. 1
B. 2
C. 3
D. 4
答案：B
分值：10"""
qs2, _ = parse_questions_text(block)
check("题目块解析", len(qs2) == 1 and qs2[0]["correct_answer"] == "B")

print("-" * 40)
print(f"结果: {passed} 通过, {failed} 失败")
sys.exit(1 if failed else 0)
