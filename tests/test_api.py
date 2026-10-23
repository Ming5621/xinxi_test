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


def student_login(name, class_name="课堂"):
    code, data = req("POST", "/auth/student-login", {"name": name, "class_name": class_name})
    if code == 200:
        return data["access_token"], data["user"]
    return None, None


print("=" * 50)

# 清理上次测试残留
_teacher_token, _ = login("teacher1", "teacher123")
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
teacher_token, teacher = login("teacher1", "teacher123")
student_token, student = student_login("测试生甲")
check("教师登录", teacher_token and teacher["role"] == "teacher")
check("学生姓名登录", student_token and student["role"] == "student" and student["name"] == "测试生甲")
check("学生默认班级为课堂", student and student.get("class_name") == "课堂")

# 同名再次登录应复用账号
token2, student2_same = student_login("测试生甲")
check("同名学生复用账号", token2 and student2_same["id"] == student["id"])

code, _ = req("POST", "/auth/login", {"username": "teacher1", "password": "wrong"})
check("错误密码拒绝", code == 401)

code, detail = req("POST", "/auth/login", {"username": student["username"], "password": "x"})
check("学生密码登录被拒绝", code == 400, str(detail))

code, _ = req("POST", "/auth/student-login", {"name": "  "})
check("空姓名拒绝", code == 400)

# 四个教师账号均可登录
for i in range(1, 5):
    t, u = login(f"teacher{i}", "teacher123")
    check(f"教师 teacher{i} 登录", t and u["role"] == "teacher")

# 额外姓名登录，保证在线/统计人数足够
extra_students = []
for name in ["测试生乙", "测试生丙", "测试生丁", "测试生戊"]:
    tok, usr = student_login(name)
    if tok:
        extra_students.append((tok, usr))
check("批量姓名登录", len(extra_students) == 4)

# 3. 用户管理
code, users = req("GET", "/users?role=student", token=teacher_token)
check("获取学生列表", code == 200 and len(users) >= 1, f"code={code}, count={len(users) if code==200 else 0}")

code, new_user = req("POST", "/users", {
    "username": "test_student_99",
    "name": "测试学生",
    "password": "123456",
    "role": "student",
    "class_name": "课堂",
}, token=teacher_token)
check("创建学生", code == 200 and new_user.get("username") == "test_student_99")

code, _ = req("POST", "/users", {
    "username": "test_student_99",
    "name": "重复",
    "password": "123456",
    "role": "student",
    "class_name": "课堂",
}, token=teacher_token)
check("重复用户名拒绝", code == 400)

admin_token, admin = login("admin", "admin123")
check("管理员登录", admin_token and admin["role"] == "admin")

code, teachers = req("GET", "/users?role=teacher", token=admin_token)
check("管理员查看教师列表", code == 200 and len(teachers) >= 4)

# 3b. 管理员管理全部账号
TEST_ACCOUNT_NAMES = {"账号测生", "账号测生乙", "账号测师", "账号测师乙", "转学生甲"}


def purge_test_accounts():
    code, rows = req("GET", "/users", token=admin_token)
    if code != 200:
        return
    for row in rows:
        if row.get("role") == "admin":
            continue
        username = row.get("username") or ""
        if username.startswith("test_acct_") or row.get("name") in TEST_ACCOUNT_NAMES:
            req("DELETE", f"/users/{row['id']}", token=admin_token)


purge_test_accounts()

code, all_users = req("GET", "/users", token=admin_token)
roles = {u["role"] for u in all_users} if code == 200 else set()
check("管理员查看全部账号", code == 200 and {"admin", "teacher", "student"} <= roles, str(roles))

code, teacher_view = req("GET", "/users", token=teacher_token)
teacher_roles = {u["role"] for u in teacher_view} if code == 200 else {"error"}
check("教师用户列表仅含学生", code == 200 and teacher_roles <= {"student"}, str(teacher_roles))

code, _ = req("POST", "/users", {
    "username": "test_acct_admin2",
    "name": "第二个管理员",
    "password": "admin123",
    "role": "admin",
}, token=admin_token)
check("不能创建管理员", code == 400)

code, new_teacher = req("POST", "/users", {
    "username": "test_acct_teacher",
    "name": "账号测师",
    "password": "pass1234",
    "role": "teacher",
    "assigned_classes": ["课堂"],
}, token=admin_token)
check("管理员创建教师", code == 200 and new_teacher.get("role") == "teacher", str(new_teacher))
acct_teacher_id = new_teacher.get("id") if code == 200 else None

code, new_student = req("POST", "/users", {
    "username": "test_acct_student",
    "name": "账号测生",
    "role": "student",
    "class_name": "课堂",
}, token=admin_token)
check(
    "管理员创建学生可无密码",
    code == 200 and new_student.get("role") == "student" and new_student.get("class_name") == "课堂",
    str(new_student),
)
acct_student_id = new_student.get("id") if code == 200 else None

code, _ = req("POST", "/users", {
    "username": "test_acct_student_b",
    "name": "账号测生",
    "role": "student",
    "class_name": "课堂",
}, token=admin_token)
check("同班同名学生拒绝", code == 400)

if acct_student_id:
    code, renamed = req("PUT", f"/users/{acct_student_id}", {
        "username": "test_acct_student_renamed",
        "name": "账号测生乙",
        "class_name": "课堂",
    }, token=admin_token)
    check(
        "管理员修改学生姓名和用户名",
        code == 200 and renamed.get("name") == "账号测生乙" and renamed.get("username") == "test_acct_student_renamed",
        str(renamed),
    )
    code, _ = req("PUT", f"/users/{acct_student_id}", {"username": "hacked_by_teacher"}, token=teacher_token)
    check("教师不能修改用户名", code == 403)
    code, _ = req("PUT", f"/users/{acct_student_id}", {"role": "teacher"}, token=teacher_token)
    check("教师不能修改角色", code == 403)
    code, teacher_edit = req("PUT", f"/users/{acct_student_id}", {
        "name": "账号测生乙",
        "class_name": "课堂",
    }, token=teacher_token)
    check("教师仍可修改本班学生", code == 200 and teacher_edit.get("name") == "账号测生乙", str(teacher_edit))
    tok, usr = student_login("账号测生乙")
    check("改名后姓名登录命中原账号", bool(tok) and usr and usr.get("id") == acct_student_id, str(usr))
    tok, usr = student_login("账号测生")
    check("旧姓名不再指向原账号", bool(tok) and usr and usr.get("id") != acct_student_id, str(usr))

if acct_teacher_id:
    code, updated = req("PUT", f"/users/{acct_teacher_id}", {
        "username": "test_acct_teacher2",
        "name": "账号测师乙",
        "password": "newpass123",
        "assigned_classes": ["课堂", "微机1班"],
    }, token=admin_token)
    classes_ok = "微机1班" in (updated.get("assigned_classes") or []) if code == 200 else False
    check(
        "管理员重置教师密码并改用户名",
        code == 200 and updated.get("username") == "test_acct_teacher2" and classes_ok,
        str(updated),
    )
    tok, usr = login("test_acct_teacher2", "newpass123")
    check("新密码可登录", bool(tok) and usr and usr.get("id") == acct_teacher_id)
    tok, _ = login("test_acct_teacher2", "pass1234")
    check("旧密码失效", tok is None)

    code, disabled = req("PUT", f"/users/{acct_teacher_id}", {"is_active": False}, token=admin_token)
    check("管理员禁用教师", code == 200 and disabled.get("is_active") is False, str(disabled))
    tok, _ = login("test_acct_teacher2", "newpass123")
    check("禁用后无法登录", tok is None)
    code, enabled = req("PUT", f"/users/{acct_teacher_id}", {"is_active": True}, token=admin_token)
    check("管理员重新启用教师", code == 200 and enabled.get("is_active") is True, str(enabled))

    code, as_student = req("PUT", f"/users/{acct_teacher_id}", {
        "role": "student",
        "name": "转学生甲",
        "class_name": "课堂",
    }, token=admin_token)
    check(
        "教师可改为学生",
        code == 200 and as_student.get("role") == "student" and as_student.get("class_name") == "课堂",
        str(as_student),
    )
    tok, usr = student_login("转学生甲")
    check("转成学生后可姓名登录", bool(tok) and usr and usr.get("id") == acct_teacher_id, str(usr))

    code, back = req("PUT", f"/users/{acct_teacher_id}", {
        "role": "teacher",
        "name": "账号测师乙",
        "password": "newpass123",
        "assigned_classes": ["课堂"],
    }, token=admin_token)
    check(
        "学生可改回教师",
        code == 200 and back.get("role") == "teacher" and back.get("class_name") == "",
        str(back),
    )
    tok, _ = login("test_acct_teacher2", "newpass123")
    check("改回教师后密码登录", bool(tok))
    code, _ = req("PUT", f"/users/{acct_teacher_id}", {"role": "admin"}, token=admin_token)
    check("不能把账号升为管理员", code == 400)
    code, _ = req("DELETE", f"/users/{acct_teacher_id}", token=teacher_token)
    check("教师不能删除教师账号", code == 403)
    code, _ = req("DELETE", f"/users/{acct_teacher_id}", token=admin_token)
    check("管理员删除教师", code == 200)

if acct_student_id:
    code, _ = req("DELETE", f"/users/{acct_student_id}", token=admin_token)
    check("管理员删除学生", code == 200)

admin_id = admin["id"]
code, renamed_admin = req("PUT", f"/users/{admin_id}", {"name": "临时管理员"}, token=admin_token)
check("管理员可改自己的姓名", code == 200 and renamed_admin.get("name") == "临时管理员", str(renamed_admin))
code, _ = req("PUT", f"/users/{admin_id}", {"password": "admin123temp"}, token=admin_token)
check("管理员可重置自己的密码", code == 200)
temp_token, _ = login("admin", "admin123temp")
check("管理员新密码可登录", bool(temp_token))
code, _ = req("PUT", f"/users/{admin_id}", {"name": "系统管理员", "password": "admin123"}, token=admin_token)
check("管理员姓名和密码已恢复", code == 200)
admin_token, admin = login("admin", "admin123")
check("默认管理员密码仍可用", bool(admin_token) and admin and admin.get("name") == "系统管理员")

code, _ = req("PUT", f"/users/{admin_id}", {"is_active": False}, token=admin_token)
check("不能禁用自己", code == 400)
code, _ = req("DELETE", f"/users/{admin_id}", token=admin_token)
check("不能删除自己", code == 400)
code, _ = req("PUT", f"/users/{admin_id}", {"role": "teacher"}, token=admin_token)
check("不能修改管理员角色", code == 400)
code, me = req("GET", "/auth/me", token=admin_token)
check("管理员账号仍可用", code == 200 and me.get("role") == "admin" and me.get("is_active") is True, str(me))
code, _ = req("GET", "/users", token=student_token)
check("学生仍不能管理账号", code == 403)

purge_test_accounts()

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
    "text": "test_import01,导入一,课堂,123456\ntest_import02,导入二,微机2班,",
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

def multipart_req(path, fields, file_field, filename, content, token, mime="text/plain"):
    boundary = "----ExamBoundary7d3a"
    body = bytearray()
    for key, val in fields.items():
        body.extend(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{val}\r\n".encode()
        )
    payload = content if isinstance(content, bytes) else content.encode("utf-8")
    body.extend(
        (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"{file_field}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode()
    )
    body.extend(payload)
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            detail = json.loads(raw)
        except Exception:
            detail = raw
        return e.code, detail


# 9. 打字练习
code, teacher_texts = req("GET", "/typing/texts", token=teacher_token)
if code == 200:
    for old in teacher_texts:
        if str(old.get("title", "")).startswith("API导入"):
            req("DELETE", f"/typing/texts/{old['id']}", token=teacher_token)

code, texts = req("GET", "/typing/texts", token=student_token)
check("获取打字素材", code == 200 and len(texts) >= 1)

code, imported = req("POST", "/typing/texts/import", {
    "title": "",
    "difficulty": "basic",
    "time_limit": 120,
    "text": "【标题】API导入春晓\n【难度】入门\n【时长】60\n春眠不觉晓，处处闻啼鸟。\n\n【标题】API导入静夜思\n床前明月光，疑是地上霜。",
}, token=teacher_token)
imported_ids = {item["id"] for item in (imported.get("texts") or [])} if code == 200 else set()
check("教师导入文章", code == 200 and imported.get("success_count") == 2, str(imported))

code, student_texts = req("GET", "/typing/texts", token=student_token)
student_ids = {item["id"] for item in student_texts} if code == 200 else set()
check("学生可见导入文章", code == 200 and imported_ids <= student_ids, str(student_texts)[:300])

code, denied = req("POST", "/typing/texts/import", {"text": "不能导入", "title": "API导入越权"}, token=student_token)
check("学生不能导入文章", code == 403, str(denied))

code, file_imported = multipart_req(
    "/typing/texts/import/file?difficulty=basic&time_limit=90",
    {},
    "file",
    "API导入文件.txt",
    "信息技术课程帮助我们学习与交流。".encode("gbk"),
    teacher_token,
)
file_rows = (file_imported.get("texts") or []) if isinstance(file_imported, dict) else []
file_ids = {item["id"] for item in file_rows} if code == 200 else set()
check(
    "教师上传文本导入文章",
    code == 200 and isinstance(file_imported, dict) and file_imported.get("success_count") == 1
    and file_rows and file_rows[0].get("title") == "API导入文件",
    str(file_imported),
)
imported_ids |= file_ids
for tid in imported_ids:
    code, _ = req("DELETE", f"/typing/texts/{tid}", token=teacher_token)
check("教师删除导入文章", imported_ids and code == 200)
code, student_texts = req("GET", "/typing/texts", token=student_token)
left = {item["id"] for item in student_texts} if code == 200 else set()
check("删除后学生不可见导入文章", code == 200 and imported_ids.isdisjoint(left))

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

code, low_acc = req("POST", "/typing/submit", {
    "reference_text": "测" * 200,
    "typed_text": "测" * 17,
    "duration_seconds": 10,
    "source": "practice",
}, token=student_token)
check(
    "高速低准确率不得卓越",
    code == 200
    and abs(float(low_acc.get("accuracy", 0)) - 8.5) < 0.05
    and float(low_acc.get("wpm", 0)) >= 40
    and low_acc.get("level") not in ("良好", "优秀", "卓越")
    and "卓越" not in (low_acc.get("remark") or ""),
    str(low_acc),
)

code, records = req("GET", "/typing/records/my", token=student_token)
latest_low = records[0] if code == 200 and records else {}
check("查看打字记录", code == 200)
check(
    "历史记录低准确率不得卓越",
    abs(float(latest_low.get("accuracy") or 0) - 8.5) < 0.05
    and float(latest_low.get("wpm") or 0) >= 40
    and latest_low.get("level") not in ("良好", "优秀", "卓越"),
    str(latest_low),
)

code, class_stats = req("GET", "/typing/records/stats", token=teacher_token)
check("教师打字统计", code == 200)

code, class_stats_filtered = req(
    "GET",
    f"/typing/records/stats?{urllib.parse.urlencode({'class_name': '课堂'})}",
    token=teacher_token,
)
check("按班级打字统计", code == 200)

# 课堂打字测试
if texts:
    code, typing_session = req("POST", "/typing/sessions", {
        "text_id": texts[0]["id"],
        "class_name": "课堂",
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
hb_student = next((s for s in presence_list if s.get("is_online") and s.get("last_seen_at")), None)
check("心跳时间带 UTC 时区标记", bool(hb_student) and str(hb_student["last_seen_at"]).endswith("Z"))

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
