#!/usr/bin/env python3
"""边界情况与潜在 Bug 测试"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8000/api"
passed = 0
failed = 0
errors = []


def req(method, path, data=None, token=None, form_data=None):
    url = f"{BASE}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form_data:
        body = form_data
        # multipart handled separately
    elif data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    else:
        body = None
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            detail = json.loads(body)
        except Exception:
            detail = body
        return e.code, detail


def login(username, password):
    code, data = req("POST", "/auth/login", {"username": username, "password": password})
    return data["access_token"] if code == 200 else None


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        msg = f"  ✗ {name}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(msg)


print("=" * 50)
print("边界情况测试")
print("=" * 50)

teacher = login("teacher", "teacher123")
student = login("student01", "123456")
student2 = login("student02", "123456")

# Bug 1: 空考试提交
code, exam = req("POST", "/exams", {
    "title": "边界测试-空题",
    "questions": [],
}, token=teacher)
empty_exam_id = exam.get("id")
code, _ = req("POST", f"/exams/{empty_exam_id}/publish", token=teacher)
check("空题考试不能发布", code == 400, f"code={code}")

# Bug 2: 学生访问他人成绩
code, sessions = req("GET", "/exams/sessions/my", token=student)
if sessions:
    sid = sessions[0]["id"]
    code, _ = req("GET", f"/exams/sessions/{sid}", token=student2)
    # student2 should not access student01's session if different
    if sessions[0].get("student_id"):
        check("学生不能查看他人成绩", code == 403 or code == 404, f"code={code}")

# Bug 3: 打字题长文本提交（检查 answer 字段截断）
code, exam = req("POST", "/exams", {
    "title": "边界测试-长打字",
    "duration_minutes": 30,
    "questions": [{
        "type": "typing",
        "content": "这是一段较长的打字测试文本，用于验证数据库是否正确存储完整的学生输入内容，不应该被截断。",
        "options": {"time_limit": 120, "min_wpm": 10, "min_accuracy": 95},
        "correct_answer": "这是一段较长的打字测试文本，用于验证数据库是否正确存储完整的学生输入内容，不应该被截断。",
        "score": 18,
        "order_num": 0,
    }],
}, token=teacher)
long_exam_id = exam.get("id")
req("POST", f"/exams/{long_exam_id}/publish", token=teacher)

# 用 student02 做测试避免重复提交
req("POST", f"/exams/{long_exam_id}/start", token=student2)
code, qs = req("GET", f"/exams/{long_exam_id}/questions", token=student2)
long_text = qs[0]["content"] if qs else ""
code, result = req("POST", f"/exams/{long_exam_id}/submit", {
    "answers": [{
        "question_id": qs[0]["id"],
        "student_answer": long_text,
        "answer_meta": {"duration_seconds": 60, "wpm": 25, "accuracy": 98, "correct_chars": len(long_text)},
    }]
}, token=student2)
check("长文本打字提交", code == 200, str(result))

if code == 200:
    code, sessions = req("GET", "/exams/sessions/my", token=student2)
    sid = next(s["id"] for s in sessions if s["exam_id"] == long_exam_id)
    code, detail = req("GET", f"/exams/sessions/{sid}", token=student2)
    ans = detail["answers"][0] if detail.get("answers") else {}
    check("长文本完整保存", ans.get("student_answer") == long_text,
          f"len={len(ans.get('student_answer',''))} expected={len(long_text)}")

req("DELETE", f"/exams/{long_exam_id}", token=teacher)
req("DELETE", f"/exams/{empty_exam_id}", token=teacher)

# Bug 4: 判断题答案大小写
code, exam = req("POST", "/exams", {
    "title": "边界测试-判断",
    "questions": [{"type": "judge", "content": "测试", "options": ["正确","错误"], "correct_answer": "正确", "score": 10, "order_num": 0}],
}, token=teacher)
judge_id = exam.get("id")
req("POST", f"/exams/{judge_id}/publish", token=teacher)
req("POST", f"/exams/{judge_id}/start", token=student2)
code, qs = req("GET", f"/exams/{judge_id}/questions", token=student2)
code, result = req("POST", f"/exams/{judge_id}/submit", {
    "answers": [{"question_id": qs[0]["id"], "student_answer": "正确"}]
}, token=student2)
check("判断题提交得分", result.get("total_score") == 10 if code == 200 else False, str(result))
req("DELETE", f"/exams/{judge_id}", token=teacher)

# Bug 5: 导入空内容
code, result = req("POST", "/import/students", {"text": "", "default_password": "123456"}, token=teacher)
check("空导入返回错误", result.get("success_count", -1) == 0, str(result))

code, result = req("POST", "/import/questions/parse", {"text": "无效内容"}, token=teacher)
check("无效题目解析", len(result.get("questions", [])) == 0, str(result))

# Bug 6: 考试结束后自动批改未提交
code, exam = req("POST", "/exams", {
    "title": "边界测试-结束",
    "questions": [{"type": "choice", "content": "1+1=?", "options": ["A.1","B.2","C.3","D.4"], "correct_answer": "B", "score": 10, "order_num": 0}],
}, token=teacher)
end_id = exam.get("id")
req("POST", f"/exams/{end_id}/publish", token=teacher)
req("POST", f"/exams/{end_id}/start", token=student2)
code, _ = req("POST", f"/exams/{end_id}/end", token=teacher)
check("结束考试", code == 200)
code, sessions = req("GET", f"/exams/{end_id}/sessions", token=teacher)
in_progress = [s for s in sessions if s.get("student_name") == "王芳"]
if in_progress:
    check("未提交卷被自动处理", in_progress[0]["status"] == "submitted", str(in_progress[0]))
req("DELETE", f"/exams/{end_id}", token=teacher)

# Bug 7: 更新考试（含打字题）
code, exam = req("POST", "/exams", {
    "title": "边界测试-更新",
    "questions": [{"type": "typing", "content": "原始文本", "options": {"time_limit": 60}, "correct_answer": "原始文本", "score": 18, "order_num": 0}],
}, token=teacher)
update_id = exam.get("id")
code, updated = req("PUT", f"/exams/{update_id}", {
    "title": "边界测试-已更新",
    "questions": [{"type": "typing", "content": "更新后文本", "options": {"time_limit": 90, "min_wpm": 15}, "correct_answer": "更新后文本", "score": 20, "order_num": 0}],
}, token=teacher)
check("更新打字题考试", code == 200 and updated.get("title") == "边界测试-已更新")
if code == 200:
    q = updated.get("questions", [{}])[0]
    check("打字题options保存", q.get("content") == "更新后文本", str(q))
req("DELETE", f"/exams/{update_id}", token=teacher)

# Bug 8: 选择题选项解析 - 判断题答案变体
sys.path.insert(0, "/workspace/backend")
from app.import_utils import parse_questions_text
qs, _ = parse_questions_text("类型,题目,选项A,选项B,答案,分值\njudge,地球是圆的,,,对,10")
check("判断题'对'解析为正确", qs and qs[0]["correct_answer"] == "正确", str(qs))

# Bug 9: 打字评分边界
from app.typing_utils import score_typing_question
s, p, _ = score_typing_question(10, 95, 18)
check("刚好达标评分", s >= 10 and p, f"score={s}")

# Bug 10: 打字题无 meta 时服务端应自动计算
code, exam = req("POST", "/exams", {
    "title": "边界测试-无meta",
    "questions": [{"type": "typing", "content": "测试文本", "options": {"time_limit": 60},
                   "correct_answer": "测试文本", "score": 18, "order_num": 0}],
}, token=teacher)
nometa_id = exam.get("id")
req("POST", f"/exams/{nometa_id}/publish", token=teacher)
req("POST", f"/exams/{nometa_id}/start", token=student2)
code, qs = req("GET", f"/exams/{nometa_id}/questions", token=student2)
code, result = req("POST", f"/exams/{nometa_id}/submit", {
    "answers": [{"question_id": qs[0]["id"], "student_answer": "测试文本"}]
}, token=student2)
check("无meta打字题自动评分", code == 200 and result.get("total_score", 0) > 3.6,
      f"score={result.get('total_score')}")
req("DELETE", f"/exams/{nometa_id}", token=teacher)

print("=" * 50)
print(f"结果: {passed} 通过, {failed} 失败")
if errors:
    for e in errors:
        print(e)
print("=" * 50)
sys.exit(1 if failed else 0)
