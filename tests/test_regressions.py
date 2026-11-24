"""隔离数据库的 API 回归测试：不访问开发/生产数据，也无需外部服务。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
_test_dir = tempfile.TemporaryDirectory(prefix="exam-regressions-")
os.environ["EXAM_SYSTEM_DATA_DIR"] = _test_dir.name
os.environ["EXAM_SYSTEM_BUNDLE_DIR"] = _test_dir.name
static = Path(_test_dir.name) / "frontend" / "dist"
(static / "assets").mkdir(parents=True)
(static / "index.html").write_text("test app", encoding="utf-8")
(static.parent / "secret.txt").write_text("private-data", encoding="utf-8")

from fastapi.testclient import TestClient
from app.auth import get_current_user, require_student, require_teacher
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Answer, ExamSession, Question, TypingClassSession, TypingRecord, TypingText, User


class RegressionTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        self.db = SessionLocal()
        self.teacher = User(username="teacher", name="教师", password_hash="unused", role="teacher", assigned_classes=["1班"])
        self.other = User(username="other", name="同班其他教师", password_hash="unused", role="teacher", assigned_classes=["1班"])
        self.student = User(username="student", name="学生", password_hash="unused", role="student", class_name="1班")
        self.db.add_all([self.teacher, self.other, self.student])
        self.db.commit()
        self.current = self.teacher
        for dependency in (get_current_user, require_student, require_teacher):
            app.dependency_overrides[dependency] = lambda: self.current
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()

    def exam(self):
        response = self.client.post("/api/exams", json={"title": "测试", "questions": [{"type": "judge", "content": "测试题", "correct_answer": "正确", "score": 10}]})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def typing_session(self, status="pending"):
        text = TypingText(teacher_id=self.teacher.id, title="文章", content="指定的文章", char_count=5)
        self.db.add(text)
        self.db.flush()
        session = TypingClassSession(teacher_id=self.teacher.id, text_id=text.id, class_name="1班", status=status)
        self.db.add(session)
        self.db.commit()
        return session

    def test_editing_answered_exam_preserves_results(self):
        exam = self.exam()
        self.client.post(f"/api/exams/{exam['id']}/publish")
        self.current = self.student
        session = self.client.post(f"/api/exams/{exam['id']}/start").json()
        result = self.client.post(f"/api/exams/{exam['id']}/submit", json={"answers": [{"question_id": exam['questions'][0]['id'], "student_answer": "正确"}]})
        self.assertEqual(result.status_code, 200)
        self.current = self.teacher
        response = self.client.put(f"/api/exams/{exam['id']}", json={"questions": [{"type": "judge", "content": "替换后的题", "correct_answer": "错误"}]})
        self.assertEqual(response.status_code, 400, response.text)
        detail = self.client.get(f"/api/exams/sessions/{session['id']}")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()['answers'][0]['question_content'], "测试题")
        self.assertEqual(detail.json()['total_score'], 10)

    def test_started_exam_cannot_change_grading_or_return_to_draft(self):
        exam = self.exam()
        self.db.add(ExamSession(exam_id=exam['id'], student_id=self.student.id))
        self.db.commit()
        for payload in ({"duration_minutes": 1}, {"pass_score": 100}, {"status": "draft"}):
            with self.subTest(payload=payload):
                response = self.client.put(f"/api/exams/{exam['id']}", json=payload)
                self.assertEqual(response.status_code, 400, response.text)

    def test_publish_cannot_remove_all_questions_in_same_request(self):
        exam = self.exam()
        response = self.client.put(f"/api/exams/{exam['id']}", json={"status": "published", "questions": []})
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.client.get(f"/api/exams/{exam['id']}").json()['status'], 'draft')

    def test_other_teacher_cannot_control_session(self):
        session = self.typing_session()
        self.current = self.other
        self.assertEqual(self.client.post(f"/api/typing/sessions/{session.id}/start").status_code, 403)
        session.status = "active"
        self.db.commit()
        self.assertEqual(self.client.post(f"/api/typing/sessions/{session.id}/end").status_code, 403)

    def test_two_pending_sessions_cannot_both_start(self):
        first = self.typing_session()
        second = self.typing_session()
        self.assertEqual(self.client.post(f"/api/typing/sessions/{first.id}/start").status_code, 200)
        self.assertEqual(self.client.post(f"/api/typing/sessions/{second.id}/start").status_code, 400)

    def test_class_submission_uses_server_article_when_text_id_omitted(self):
        session = self.typing_session("active")
        self.current = self.student
        response = self.client.post('/api/typing/submit', json={"typing_session_id": session.id, "reference_text": "伪造", "typed_text": "伪造", "duration_seconds": 60})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['correct_chars'], 0)
        record = self.db.query(TypingRecord).one()
        self.assertEqual(record.text_id, session.text_id)
        self.assertEqual(record.reference_text, "指定的文章")

    def test_bound_student_cannot_join_other_teacher_session(self):
        session = self.typing_session("active")
        self.student.managed_by_teacher_id = self.other.id
        self.db.commit()
        self.current = self.student
        response = self.client.post('/api/typing/submit', json={"typing_session_id": session.id, "reference_text": "伪造", "typed_text": "伪造", "duration_seconds": 60})
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.client.get(f'/api/typing/sessions/{session.id}').status_code, 403)

    def test_student_session_detail_hides_classmates_records(self):
        session = self.typing_session("active")
        classmate = User(username="classmate", name="同学", password_hash="unused", role="student", class_name="1班")
        self.db.add(classmate)
        self.db.flush()
        for student in (self.student, classmate):
            self.db.add(TypingRecord(student_id=student.id, text_id=session.text_id, typing_session_id=session.id, reference_text="指定的文章"))
        self.db.commit()
        self.current = self.student
        response = self.client.get(f'/api/typing/sessions/{session.id}')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([r['student_id'] for r in response.json()['records']], [self.student.id])

    def test_nonpositive_typing_duration_rejected(self):
        self.current = self.student
        for seconds in (0, -1):
            response = self.client.post('/api/typing/submit', json={"reference_text": "测试", "typed_text": "测试", "duration_seconds": seconds})
            self.assertEqual(response.status_code, 422, response.text)

    def test_delete_student_with_results_cleans_related_records(self):
        exam = self.exam()
        session = ExamSession(exam_id=exam['id'], student_id=self.student.id)
        self.db.add(session)
        self.db.flush()
        self.db.add(Answer(session_id=session.id, question_id=exam['questions'][0]['id']))
        self.db.add(TypingRecord(student_id=self.student.id, reference_text="测试"))
        self.db.commit()
        response = self.client.delete(f'/api/users/{self.student.id}')
        self.assertEqual(response.status_code, 200, response.text)
        for model in (Answer, ExamSession, TypingRecord):
            self.assertEqual(self.db.query(model).count(), 0)

    def test_delete_teacher_with_resources_is_rejected(self):
        self.typing_session()
        self.current = self.other
        self.current.role = "admin"
        self.db.commit()
        response = self.client.delete(f'/api/users/{self.teacher.id}')
        self.assertEqual(response.status_code, 400, response.text)

    def test_staff_password_reset_revokes_old_token(self):
        from app.auth import _get_session_user, get_password_hash
        from app.routers.auth import _issue_token
        self.teacher.password_hash = get_password_hash('old-password')
        self.db.commit()
        token = _issue_token(self.teacher, self.db).access_token
        self.assertEqual(_get_session_user(token, self.db).id, self.teacher.id)
        self.teacher.password_hash = get_password_hash('new-password')
        self.db.commit()
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            _get_session_user(token, self.db)
        self.assertEqual(error.exception.status_code, 401)

    def test_teacher_cannot_export_other_teacher_session(self):
        session = self.typing_session()
        self.current = self.other
        response = self.client.get(f'/api/export/typing/sessions/{session.id}')
        self.assertEqual(response.status_code, 403, response.text)

    def test_student_filtered_export_does_not_include_other_summary(self):
        import io
        from openpyxl import load_workbook
        classmate = User(username="classmate", name="不应导出的同学", password_hash="unused", role="student", class_name="1班")
        self.db.add(classmate)
        self.db.commit()
        response = self.client.get(f'/api/export/typing/records?student_id={self.student.id}')
        self.assertEqual(response.status_code, 200, response.text)
        rows = list(load_workbook(io.BytesIO(response.content)).worksheets[0].values)
        self.assertEqual([row[0] for row in rows[1:]], [self.student.name])

    def test_export_treats_names_as_text_not_formulas(self):
        import io
        from openpyxl import load_workbook
        self.student.name = '=1+1'
        self.db.commit()
        response = self.client.get('/api/export/students')
        cell = load_workbook(io.BytesIO(response.content)).active['B2']
        self.assertEqual(cell.value, '=1+1')
        self.assertEqual(cell.data_type, 's')

    def test_statistics_count_unanswered_questions(self):
        exam = self.exam()
        session = ExamSession(exam_id=exam['id'], student_id=self.student.id, status='submitted')
        self.db.add(session)
        self.db.add(User(username="classmate", name="同学", password_hash="unused", role="student", class_name="1班"))
        self.db.flush()
        other = self.db.query(User).filter_by(username="classmate").one()
        answered = ExamSession(exam_id=exam['id'], student_id=other.id, status='submitted')
        self.db.add(answered)
        self.db.flush()
        self.db.add(Answer(session_id=answered.id, question_id=exam['questions'][0]['id'], is_correct=True, score=10))
        self.db.commit()
        response = self.client.get(f"/api/stats/exam/{exam['id']}").json()
        self.assertEqual(response['question_stats'][0]['total_count'], 2)
        self.assertEqual(response['question_stats'][0]['correct_rate'], 50)

    def test_blank_submitted_questions_are_retained_at_zero_score(self):
        exam = self.exam()
        self.client.post(f"/api/exams/{exam['id']}/publish")
        self.current = self.student
        session = self.client.post(f"/api/exams/{exam['id']}/start").json()
        self.assertEqual(self.client.post(f"/api/exams/{exam['id']}/submit", json={"answers": []}).status_code, 200)
        detail = self.client.get(f"/api/exams/sessions/{session['id']}").json()
        self.assertEqual(len(detail['answers']), 1)
        self.assertEqual(detail['answers'][0]['score'], 0)

    def test_pack_zero_scores_survive_import(self):
        payload = {"format": "xinxi_teacher_pack", "version": 1, "exams": [{"title": "零分线", "pass_score": 0, "questions": [{"type": "judge", "content": "零分题", "correct_answer": "正确", "score": 0}]}]}
        response = self.client.post('/api/import/teacher-pack', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        exam = self.client.get('/api/exams').json()[0]
        self.assertEqual(exam['pass_score'], 0)
        self.assertEqual(exam['total_score'], 0)

    def test_pack_does_not_overwrite_until_confirmed(self):
        self.student.managed_by_teacher_id = self.teacher.id
        self.db.commit()
        first = {"format": "xinxi_teacher_pack", "version": 2, "students": [{"username": "student", "name": "新名字", "class_name": "1班"}], "exams": [{"title": "测试", "questions": [{"type": "judge", "content": "新题", "correct_answer": "错误", "score": 5}]}], "typing_texts": [{"title": "文章", "content": "新的正文内容", "time_limit": 60}]}
        self.exam()
        self.db.add(TypingText(teacher_id=self.teacher.id, title="文章", content="旧正文", char_count=3))
        self.db.commit()
        skipped = self.client.post('/api/import/teacher-pack', json=first)
        self.assertEqual(skipped.status_code, 200, skipped.text)
        self.assertEqual(skipped.json()['student_updated'], 0)
        self.assertTrue(any('未覆盖' in item for item in skipped.json()['errors']))
        self.db.refresh(self.student)
        self.assertEqual(self.student.name, '学生')
        replaced = self.client.post('/api/import/teacher-pack?overwrite=true', json=first)
        self.assertEqual(replaced.status_code, 200, replaced.text)
        self.assertEqual(replaced.json()['student_updated'], 1)
        self.db.expire_all()
        self.assertEqual(self.db.get(User, self.student.id).name, '新名字')
        self.assertEqual(self.db.query(Question).one().content, '新题')
        text = self.db.query(TypingText).filter_by(title='文章', teacher_id=self.teacher.id).one()
        self.assertEqual(text.content, '新的正文内容')

    def test_admin_pack_overwrites_teacher_account_and_bound_students(self):
        admin = User(username='admin', name='管理员', password_hash='unused', role='admin')
        self.db.add(admin)
        self.student.managed_by_teacher_id = self.teacher.id
        self.db.commit()
        self.current = admin
        payload = {
            'format': 'xinxi_teacher_pack',
            'version': 2,
            'teachers': [{'username': 'teacher', 'name': '改名教师', 'assigned_classes': ['1班', '2班'], 'is_active': True}],
            'students': [{'username': 'sync-student', 'name': '同步学生', 'class_name': '2班', 'teacher_username': 'teacher', 'is_active': True}],
            'exams': [],
            'typing_texts': [],
        }
        response = self.client.post('/api/import/teacher-pack?overwrite=true', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['teacher_updated'], 1)
        self.assertEqual(response.json()['student_removed'], 1)
        self.db.expire_all()
        teacher = self.db.query(User).filter_by(username='teacher').one()
        self.assertEqual(teacher.name, '改名教师')
        self.assertEqual(teacher.assigned_classes, ['1班', '2班'])
        self.assertIsNone(self.db.query(User).filter_by(username='student').one_or_none())
        created = self.db.query(User).filter_by(username='sync-student').one()
        self.assertEqual(created.managed_by_teacher_id, teacher.id)
        self.assertEqual(created.class_name, '2班')

    def test_pack_invalid_numbers_report_errors_without_partial_exam(self):
        payload = {"format": "xinxi_teacher_pack", "version": 1, "exams": [{"title": "无效考试", "duration_minutes": "非法数字"}], "typing_texts": [{"title": "无效文章", "content": "正文", "time_limit": "非法数字"}]}
        response = self.client.post('/api/import/teacher-pack', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['errors']), 2)
        self.assertEqual(response.json()['exam_count'], 0)
        self.assertEqual(response.json()['text_count'], 0)

    def test_invalid_exam_and_typing_config_rejected(self):
        for payload in ({"title": "测试", "duration_minutes": 0}, {"title": "测试", "pass_score": -1}, {"title": "测试", "questions": [{"type": "typing", "content": "正文", "options": {"time_limit": "非法数字"}}]}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/api/exams', json=payload).status_code, 422)

    def test_typing_answer_invalid_duration_rejected(self):
        exam = self.exam()
        self.client.post(f"/api/exams/{exam['id']}/publish")
        self.current = self.student
        self.client.post(f"/api/exams/{exam['id']}/start")
        response = self.client.post(f"/api/exams/{exam['id']}/submit", json={"answers": [{"question_id": exam['questions'][0]['id'], "student_answer": "正确", "answer_meta": {"duration_seconds": "not-a-number"}}]})
        self.assertEqual(response.status_code, 422, response.text)

    def test_question_import_supports_tsv_and_uppercase_judge(self):
        from app.import_utils import parse_questions_text, normalize_answer
        questions, errors = parse_questions_text("类型\t题目\t答案\t分值\njudge\t测试题\tTRUE\t10")
        self.assertEqual(len(questions), 1, errors)
        self.assertEqual(questions[0]['correct_answer'], '正确')
        self.assertEqual(normalize_answer('FALSE', 'judge'), '错误')

    def test_invalid_question_score_reports_error_and_keeps_valid_blocks(self):
        from app.import_utils import parse_questions_text
        text = "[判断] 错误分值\n答案：正确\n分值：1.2.3\n\n[判断] 正常题\n答案：正确\n分值：10"
        questions, errors = parse_questions_text(text)
        self.assertEqual(len(errors), 1)
        self.assertEqual([q['content'] for q in questions], ['正常题'])
        response = self.client.post('/api/import/questions/parse', json={"text": "类型,题目,答案,分值\njudge,非法分值,正确,NaN"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['questions'], [])
        self.assertTrue(response.json()['errors'])

    def test_class_test_roster_excludes_other_teachers_bound_students(self):
        import io
        from openpyxl import load_workbook
        session = self.typing_session()
        classmate = User(username="classmate", name="其他教师的学生", password_hash="unused", role="student", class_name="1班", managed_by_teacher_id=self.other.id)
        self.db.add(classmate)
        self.db.commit()
        detail = self.client.get(f'/api/typing/sessions/{session.id}').json()
        self.assertEqual(detail['participant_count'], 1)
        response = self.client.get(f'/api/export/typing/sessions/{session.id}')
        self.assertEqual(response.status_code, 200)
        rows = list(load_workbook(io.BytesIO(response.content)).active.values)
        self.assertNotIn(classmate.name, [row[0] for row in rows])

    def test_old_class_session_list_remains_readable_after_unassignment(self):
        session = self.typing_session("ended")
        self.teacher.assigned_classes = []
        self.db.commit()
        response = self.client.get('/api/typing/sessions')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()[0]['id'], session.id)
        self.assertEqual(response.json()[0]['participant_count'], 0)

    def test_static_route_cannot_escape_dist(self):
        response = self.client.get('/%2e%2e/secret.txt')
        self.assertEqual(response.status_code, 404, response.text)
        self.assertNotIn('private-data', response.text)
        self.assertEqual(self.client.get('/student/results').status_code, 200)


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        engine.dispose()
        _test_dir.cleanup()
