#!/usr/bin/env python3
"""考试系统 API 集成测试"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8000/api"
passed = 0
failed = 0
errors = []


def req(method, path, data=None, token=None):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
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


def login(username, password):
    code, data = req("POST", "/auth/login", {"username": username, "password": password})
    if code == 200:
        return data["access_token"], data["user"]
    return None, None


print("=" * 50)

# 清理上次测试残留
_teacher_token, _ = login("teacher", "teacher123")
if _teacher_token:
    for username in ["test_student_99", "test_import01", "test_import02", "test_cross_class"]:
        code, users = req("GET", "/users?role=student", token=_teacher_token)
        if code == 200:
            for u in users:
                if u["username"] == username:
                    req("DELETE", f"/users/{u['id']}", token=_teacher_token)

print("考试系统 API 测试")
print("=" * 50)

# 1. 健康检查
code, data = req("GET", "/health")
check("健康检查", code == 200 and data.get("status") == "ok", str(data))

# 2. 登录
teacher_token, teacher = login("teacher", "teacher123")
student_token, student = login("student01", "123456")
check("教师登录", teacher_token and teacher["role"] == "teacher")
check("学生登录", student_token and student["role"] == "student")

code, _ = req("POST", "/auth/login", {"username": "teacher", "password": "wrong"})
check("错误密码拒绝", code == 401)

# 3. 用户管理
code, users = req("GET", "/users?role=student", token=teacher_token)
check("获取学生列表", code == 200 and len(users) >= 1, f"code={code}, count={len(users) if code==200 else 0}")

code, new_user = req("POST", "/users", {
    "username": "test_student_99",
    "name": "测试学生",
    "password": "123456",
    "role": "student",
    "class_name": "微机1班",
}, token=teacher_token)
check("创建学生", code == 200 and new_user.get("username") == "test_student_99")

code, _ = req("POST", "/users", {
    "username": "test_student_99",
    "name": "重复",
    "password": "123456",
    "role": "student",
}, token=teacher_token)
check("重复用户名拒绝", code == 400)

admin_token, admin = login("admin", "admin123")
check("管理员登录", admin_token and admin["role"] == "admin")

code, teachers = req("GET", "/users?role=teacher", token=admin_token)
check("管理员查看教师列表", code == 200 and len(teachers) >= 1)

code, classes = req("GET", "/classes", token=teacher_token)
check("教师获取班级列表", code == 200 and "classes" in classes)

code, _ = req("POST", "/users", {
    "username": "test_cross_class",
    "name": "跨班学生",
    "password": "123456",
    "role": "student",
    "class_name": "微机2班",
}, token=teacher_token)
check("教师无法创建其他班级学生", code == 403)

code, _ = req("GET", "/users?role=teacher", token=teacher_token)
check("教师无法查看教师列表", code == 403)

# 4. 批量导入
code, result = req("POST", "/import/students", {
    "text": "test_import01,导入一,微机1班,123456\ntest_import02,导入二,微机2班,",
    "default_password": "123456",
}, token=teacher_token)
check("批量导入学生", code == 200 and result.get("success_count", 0) >= 1, str(result))

code, parsed = req("POST", "/import/questions/parse", {
    "text": "类型,题目,选项A,选项B,选项C,选项D,答案,分值\nchoice,测试题,A,B,C,D,A,5",
    "default_score": 10,
}, token=teacher_token)
check("批量解析题目", code == 200 and len(parsed.get("questions", [])) == 1)

# 5. 考试管理
code, exams = req("GET", "/exams", token=teacher_token)
check("获取考试列表", code == 200 and len(exams) >= 1)

# 创建测试考试
code, new_exam = req("POST", "/exams", {
    "title": "自动化测试考试",
    "description": "测试用",
    "duration_minutes": 30,
    "pass_score": 60,
    "questions": [
        {"type": "choice", "content": "2+2=?", "options": ["A.3", "B.4", "C.5", "D.6"], "correct_answer": "B", "score": 10, "order_num": 0},
        {"type": "judge", "content": "地球是圆的", "options": ["正确", "错误"], "correct_answer": "正确", "score": 10, "order_num": 1},
        {"type": "typing", "content": "信息技术改变生活", "options": {"time_limit": 60, "min_wpm": 10, "min_accuracy": 95}, "correct_answer": "信息技术改变生活", "score": 18, "order_num": 2},
    ],
}, token=teacher_token)
check("创建考试(含打字题)", code == 200 and new_exam.get("question_count") == 3, str(new_exam))
test_exam_id = new_exam.get("id") if code == 200 else None

if test_exam_id:
    code, _ = req("POST", f"/exams/{test_exam_id}/publish", token=teacher_token)
    check("发布考试", code == 200)

    # 6. 学生考试流程
    code, session = req("POST", f"/exams/{test_exam_id}/start", token=student_token)
    check("学生开始考试", code == 200 and session.get("status") == "in_progress")

    code, questions = req("GET", f"/exams/{test_exam_id}/questions", token=student_token)
    check("获取考试题目", code == 200 and len(questions) == 3)

    # 检查打字题配置
    typing_q = next((q for q in questions if q.get("type") == "typing"), None)
    check("打字题包含typing_config", typing_q and typing_q.get("typing_config") is not None, str(typing_q))

    # 提交答卷
    answers = []
    for q in questions:
        if q["type"] == "choice":
            answers.append({"question_id": q["id"], "student_answer": "B"})
        elif q["type"] == "judge":
            answers.append({"question_id": q["id"], "student_answer": "正确"})
        elif q["type"] == "typing":
            answers.append({
                "question_id": q["id"],
                "student_answer": "信息技术改变生活",
                "answer_meta": {"duration_seconds": 30, "wpm": 20, "accuracy": 100, "correct_chars": 8},
            })

    code, submit_result = req("POST", f"/exams/{test_exam_id}/submit", {"answers": answers}, token=student_token)
    check("提交考试", code == 200 and submit_result.get("status") == "submitted", str(submit_result))
    check("考试得分正确", submit_result.get("total_score", 0) > 0, f"score={submit_result.get('total_score')}")

    # 重复提交应拒绝
    code, _ = req("POST", f"/exams/{test_exam_id}/submit", {"answers": answers}, token=student_token)
    check("重复提交拒绝", code == 400)

    # 7. 成绩查询
    code, sessions = req("GET", "/exams/sessions/my", token=student_token)
    check("学生查看成绩", code == 200 and any(s["exam_id"] == test_exam_id for s in sessions))

    if sessions:
        sid = next(s["id"] for s in sessions if s["exam_id"] == test_exam_id)
        code, detail = req("GET", f"/exams/sessions/{sid}", token=student_token)
        check("成绩详情", code == 200 and len(detail.get("answers", [])) == 3)
        typing_ans = next((a for a in detail.get("answers", []) if a.get("answer_meta")), None)
        check("打字题答案含meta", typing_ans and typing_ans.get("answer_meta", {}).get("wpm") is not None)

    code, exam_sessions = req("GET", f"/exams/{test_exam_id}/sessions", token=teacher_token)
    check("教师查看考试成绩", code == 200 and len(exam_sessions) >= 1)

    # 8. 统计
    code, stats = req("GET", f"/stats/exam/{test_exam_id}", token=teacher_token)
    check("考试统计", code == 200 and stats.get("submitted_count", 0) >= 1)

    code, dash = req("GET", "/stats/dashboard", token=teacher_token)
    check("控制台统计", code == 200 and dash.get("total_students", 0) >= 5)
    check("控制台含在线人数", "online_students" in dash)

    # 清理：结束并删除测试考试
    code, _ = req("POST", f"/exams/{test_exam_id}/end", token=teacher_token)
    code, _ = req("DELETE", f"/exams/{test_exam_id}", token=teacher_token)
    check("删除测试考试", code == 200)

# 9. 打字练习
code, texts = req("GET", "/typing/texts", token=student_token)
check("获取打字素材", code == 200 and len(texts) >= 1)

code, standards = req("GET", "/typing/standards", token=student_token)
check("获取打字标准", code == 200 and len(standards.get("levels", [])) >= 5)

if texts:
    code, typing_result = req("POST", "/typing/submit", {
        "text_id": texts[0]["id"],
        "reference_text": texts[0]["content"],
        "typed_text": texts[0]["content"][:20],
        "duration_seconds": 30,
        "source": "practice",
    }, token=student_token)
    check("提交打字练习", code == 200 and typing_result.get("wpm", 0) >= 0)
    check("打字练习返回评分", code == 200 and float(typing_result.get("score") or 0) > 0)

code, records = req("GET", "/typing/records/my", token=student_token)
check("查看打字记录", code == 200)

code, class_stats = req("GET", "/typing/records/stats", token=teacher_token)
check("教师打字统计", code == 200)

code, class_stats_filtered = req(
    "GET",
    f"/typing/records/stats?{urllib.parse.urlencode({'class_name': '微机1班'})}",
    token=teacher_token,
)
check("按班级打字统计", code == 200)

# 课堂打字测试
if texts:
    code, typing_session = req("POST", "/typing/sessions", {
        "text_id": texts[0]["id"],
        "class_name": "微机1班",
        "title": "自动化课堂测试",
        "duration_seconds": 300,
    }, token=teacher_token)
    check("创建课堂打字测试", code == 200 and typing_session.get("status") == "pending")
    session_id = typing_session.get("id") if code == 200 else None
    if session_id:
        code, _ = req("POST", f"/typing/sessions/{session_id}/start", token=teacher_token)
        check("开始课堂打字测试", code == 200)
        code, active = req("GET", "/typing/sessions/active", token=student_token)
        check("学生获取进行中的课堂测试", code == 200 and active and active.get("id") == session_id)
        code, class_submit = req("POST", "/typing/submit", {
            "text_id": texts[0]["id"],
            "reference_text": texts[0]["content"],
            "typed_text": texts[0]["content"][:30],
            "duration_seconds": 60,
            "typing_session_id": session_id,
        }, token=student_token)
        check("学生提交课堂打字测试", code == 200 and float(class_submit.get("score") or 0) > 0)
        code, detail = req("GET", f"/typing/sessions/{session_id}", token=teacher_token)
        check("教师查看课堂测试成绩", code == 200 and len(detail.get("records", [])) >= 1)
        req("POST", f"/typing/sessions/{session_id}/end", token=teacher_token)

# 10b. Excel 导出
import urllib.request
export_req = urllib.request.Request(
    f"{BASE}/export/students",
    headers={"Authorization": f"Bearer {teacher_token}"},
)
try:
    with urllib.request.urlopen(export_req, timeout=10) as resp:
        export_ok = resp.status == 200 and "spreadsheet" in resp.headers.get("Content-Type", "")
except Exception:
    export_ok = False
check("导出学生 Excel", export_ok)

# 10. 在线状态
code, hb = req("POST", "/presence/heartbeat", token=student_token)
check("学生心跳", code == 200 and hb.get("ok") is True)

code, _ = req("POST", "/presence/heartbeat", token=teacher_token)
check("教师无法发送心跳", code == 403)

code, presence_list = req("GET", "/presence/students", token=teacher_token)
check("教师查看学生在线状态", code == 200 and len(presence_list) >= 5)
online = [s for s in presence_list if s.get("is_online")]
check("学生登录后显示在线", len(online) >= 1)

code, summary = req("GET", "/presence/summary", token=teacher_token)
check("在线汇总", code == 200 and summary.get("online_students", 0) >= 1)

# 11. 权限测试
code, _ = req("GET", "/users", token=student_token)
check("学生无法访问用户管理", code == 403)

code, _ = req("GET", "/stats/dashboard", token=student_token)
check("学生无法访问教师统计", code == 403)

code, _ = req("GET", "/presence/students", token=student_token)
check("学生无法查看在线状态", code == 403)

# 12. 无 token 访问
code, _ = req("GET", "/exams")
check("未登录拒绝", code == 401)

# 清理测试用户
for username in ["test_student_99", "test_import01", "test_import02", "test_cross_class"]:
    code, users = req("GET", "/users?role=student", token=teacher_token)
    if code == 200:
        for u in users:
            if u["username"] == username:
                req("DELETE", f"/users/{u['id']}", token=teacher_token)

print("=" * 50)
print(f"结果: {passed} 通过, {failed} 失败")
if errors:
    print("\n失败项:")
    for e in errors:
        print(e)
print("=" * 50)
sys.exit(1 if failed else 0)
