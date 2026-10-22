#!/usr/bin/env python3
"""打字工具单元测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.typing_utils import compare_text, calculate_wpm, score_typing_question, get_typing_level
from app.import_utils import decode_uploaded_text, parse_students_text, parse_questions_text, parse_typing_articles

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
check("等级-卓越", get_typing_level(45, 100)["level"] == "卓越")
check("等级-达标", get_typing_level(15, 100)["level"] == "达标")
check("等级-未达标", get_typing_level(5, 100)["level"] == "未达标")
check("准确率95可评卓越", get_typing_level(40, 95)["level"] == "卓越")
low_level = get_typing_level(45, 8.5)
check(
    "高速低准确率不得卓越",
    low_level["level"] not in ("良好", "优秀", "卓越") and low_level["level"] == "达标",
    low_level["level"],
)
check("准确率94.9高速仅为达标", get_typing_level(40, 94.9)["level"] == "达标")
check("中速低准确率保持达标", get_typing_level(15, 50)["level"] == "达标")
check("低速低准确率未达标", get_typing_level(5, 8.5)["level"] == "未达标")

# 长文只打对一小段：速度高、准确率约 8.5%，不能记为卓越
partial = compare_text("测" * 200, "测" * 17)
partial_wpm = calculate_wpm(partial["correct_chars"], 10)
partial_level = get_typing_level(partial_wpm, partial["accuracy"])
_, partial_passed, partial_remark = score_typing_question(partial_wpm, partial["accuracy"], 100)
check(
    "8.5%准确率高速成绩不得卓越",
    partial["accuracy"] == 8.5
    and partial_wpm >= 40
    and partial_level["level"] != "卓越"
    and partial_level["level"] not in ("良好", "优秀", "卓越")
    and not partial_passed
    and "卓越" not in partial_remark
    and "良好" not in partial_remark
    and "优秀" not in partial_remark,
    f"acc={partial['accuracy']} wpm={partial_wpm} level={partial_level['level']} remark={partial_remark}",
)

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

# 打字文章导入
block_articles = """【标题】春晓
【难度】入门
【时长】60

春眠不觉晓，处处闻啼鸟。

【标题】静夜思
床前明月光，疑是地上霜。
"""
articles, art_errs = parse_typing_articles(block_articles)
check(
    "文章分段导入",
    len(articles) == 2 and not art_errs and articles[0]["title"] == "春晓"
    and articles[0]["difficulty"].value == "beginner" and articles[0]["time_limit"] == 60
    and "春眠不觉晓" in articles[0]["content"] and articles[1]["difficulty"].value == "basic",
    str(articles) + str(art_errs),
)

csv_articles, csv_errs = parse_typing_articles("标题,正文,难度,建议时长\n静夜思,\"床前明月光，疑是地上霜。\",进阶,90\n,空标题,基础,60")
check(
    "文章表格导入",
    len(csv_articles) == 1 and csv_articles[0]["difficulty"].value == "advanced" and csv_articles[0]["time_limit"] == 90
    and any("标题不能为空" in e for e in csv_errs),
    str(csv_articles) + str(csv_errs),
)

single, single_errs = parse_typing_articles("信息技术改变生活。", default_title="单篇练习")
check("文章单篇导入", len(single) == 1 and single[0]["title"] == "单篇练习" and not single_errs)

missing, missing_errs = parse_typing_articles("只有正文没有标题")
check("文章缺少标题", not missing and missing_errs)

gbk = decode_uploaded_text("春眠不觉晓".encode("gbk"))
check("文章 GBK 解码", gbk == "春眠不觉晓")

print("-" * 40)
print(f"结果: {passed} 通过, {failed} 失败")
sys.exit(1 if failed else 0)
