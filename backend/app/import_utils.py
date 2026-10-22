"""批量导入解析工具"""
import csv
import io
import re
from typing import Optional

from .models import QuestionType, TypingDifficulty


STUDENT_HEADERS = {
    "username": {"用户名", "username", "学号", "账号"},
    "name": {"姓名", "name", "名字"},
    "class_name": {"班级", "class_name", "class", "班"},
    "password": {"密码", "password", "pwd"},
}

QUESTION_CSV_HEADERS = {
    "type": {"类型", "type", "题型"},
    "content": {"题目", "content", "题干", "题目内容"},
    "option_a": {"选项a", "option_a", "a"},
    "option_b": {"选项b", "option_b", "b"},
    "option_c": {"选项c", "option_c", "c"},
    "option_d": {"选项d", "option_d", "d"},
    "correct_answer": {"答案", "correct_answer", "正确答案"},
    "score": {"分值", "score", "分数"},
}


def _normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "")


def _map_headers(row_headers: list[str], mapping: dict) -> dict[str, int]:
    result = {}
    for idx, h in enumerate(row_headers):
        norm = _normalize_header(h)
        for field, aliases in mapping.items():
            if norm in {_normalize_header(a) for a in aliases}:
                result[field] = idx
                break
    return result


def parse_students_text(text: str, default_password: str = "123456") -> tuple[list[dict], list[str]]:
    """解析学生批量导入文本，支持 CSV/TSV"""
    text = text.strip()
    if not text:
        return [], ["导入内容为空"]

    errors: list[str] = []
    students: list[dict] = []
    seen_usernames: set[str] = set()

    # 尝试 CSV 解析
    delimiter = "\t" if "\t" in text.split("\n")[0] else ","
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [], ["无法解析内容"]

    header_map = _map_headers(rows[0], STUDENT_HEADERS)
    start_idx = 1 if len(header_map) >= 2 else 0

    if start_idx == 0:
        header_map = {"username": 0, "name": 1, "class_name": 2, "password": 3}

    for line_no, row in enumerate(rows[start_idx:], start=start_idx + 1):
        if not row or all(not cell.strip() for cell in row):
            continue

        try:
            username = row[header_map["username"]].strip() if header_map.get("username") is not None and header_map["username"] < len(row) else ""
            name = row[header_map["name"]].strip() if header_map.get("name") is not None and header_map["name"] < len(row) else ""
            class_name = ""
            if header_map.get("class_name") is not None and header_map["class_name"] < len(row):
                class_name = row[header_map["class_name"]].strip()
            password = default_password
            if header_map.get("password") is not None and header_map["password"] < len(row):
                pwd = row[header_map["password"]].strip()
                if pwd:
                    password = pwd

            if not username:
                errors.append(f"第 {line_no} 行：用户名不能为空")
                continue
            if not name:
                errors.append(f"第 {line_no} 行：姓名不能为空")
                continue
            if username in seen_usernames:
                errors.append(f"第 {line_no} 行：用户名 {username} 重复")
                continue

            seen_usernames.add(username)
            students.append({
                "username": username,
                "name": name,
                "class_name": class_name,
                "password": password,
            })
        except Exception as e:
            errors.append(f"第 {line_no} 行：解析失败 - {e}")

    return students, errors


def _parse_question_type(raw: str) -> Optional[QuestionType]:
    raw = raw.strip().lower()
    if raw in {"choice", "选择", "选择题", "单选", "单选题"}:
        return QuestionType.choice
    if raw in {"judge", "判断", "判断题", "对错", "是非"}:
        return QuestionType.judge
    return None


def normalize_answer(answer: str, qtype: QuestionType) -> str:
    answer = answer.strip()
    if qtype == QuestionType.judge:
        if answer in {"对", "正确", "true", "t", "√", "是", "yes", "1"}:
            return "正确"
        if answer in {"错", "错误", "false", "f", "×", "否", "no", "0"}:
            return "错误"
        return answer
    return answer.upper()


def parse_questions_text(text: str, default_score: float = 10.0) -> tuple[list[dict], list[str]]:
    """解析题目批量导入文本，支持块格式和 CSV 格式"""
    text = text.strip()
    if not text:
        return [], ["导入内容为空"]

    # 优先尝试 CSV 格式
    first_line = text.split("\n")[0]
    if "," in first_line or "\t" in first_line:
        csv_questions, csv_errors = _parse_questions_csv(text, default_score)
        if csv_questions:
            return csv_questions, csv_errors
        block_questions, block_errors = _parse_questions_block(text, default_score)
        if block_questions:
            return block_questions, csv_errors + block_errors
        return [], csv_errors + block_errors

    return _parse_questions_block(text, default_score)


def _parse_questions_csv(text: str, default_score: float) -> tuple[list[dict], list[str]]:
    delimiter = "\t" if "\t" in text.split("\n")[0] else ","
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [], []

    header_map = _map_headers(rows[0], QUESTION_CSV_HEADERS)
    start_idx = 1 if "type" in header_map and "content" in header_map else 0

    if start_idx == 0:
        # 无表头：类型,题目,A,B,C,D,答案,分值
        header_map = {
            "type": 0, "content": 1,
            "option_a": 2, "option_b": 3, "option_c": 4, "option_d": 5,
            "correct_answer": 6, "score": 7,
        }

    questions: list[dict] = []
    errors: list[str] = []

    for line_no, row in enumerate(rows[start_idx:], start=start_idx + 1):
        if not row or all(not cell.strip() for cell in row):
            continue
        try:
            qtype_raw = row[header_map["type"]].strip() if header_map["type"] < len(row) else ""
            qtype = _parse_question_type(qtype_raw)
            if not qtype:
                errors.append(f"第 {line_no} 行：题型无效（{qtype_raw}）")
                continue

            content = row[header_map["content"]].strip() if header_map["content"] < len(row) else ""
            if not content:
                errors.append(f"第 {line_no} 行：题目内容不能为空")
                continue

            answer = row[header_map["correct_answer"]].strip() if header_map["correct_answer"] < len(row) else ""
            if not answer:
                errors.append(f"第 {line_no} 行：答案不能为空")
                continue
            answer = normalize_answer(answer, qtype)

            score = default_score
            if header_map.get("score") is not None and header_map["score"] < len(row):
                score_raw = row[header_map["score"]].strip()
                if score_raw:
                    score = float(score_raw)

            options: list[str] = []
            if qtype == QuestionType.choice:
                labels = ["A", "B", "C", "D"]
                opt_keys = ["option_a", "option_b", "option_c", "option_d"]
                for label, key in zip(labels, opt_keys):
                    val = row[header_map[key]].strip() if header_map[key] < len(row) else ""
                    if val:
                        options.append(f"{label}. {val}" if not val.startswith(f"{label}.") else val)
                if len(options) < 2:
                    errors.append(f"第 {line_no} 行：选择题至少需要 2 个选项")
                    continue
            else:
                options = ["正确", "错误"]

            questions.append({
                "type": qtype,
                "content": content,
                "options": options,
                "correct_answer": answer,
                "score": score,
                "order_num": len(questions),
            })
        except Exception as e:
            errors.append(f"第 {line_no} 行：解析失败 - {e}")

    return questions, errors


def _parse_questions_block(text: str, default_score: float) -> tuple[list[dict], list[str]]:
    """块格式解析：
    [选择] 题目内容
    A. 选项A
    B. 选项B
    答案：B
    分值：10
    """
    blocks = re.split(r"\n\s*\n", text.strip())
    questions: list[dict] = []
    errors: list[str] = []

    for idx, block in enumerate(blocks, start=1):
        lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
        if not lines:
            continue

        qtype: Optional[QuestionType] = None
        content = ""
        options: list[str] = []
        answer = ""
        score = default_score

        first = lines[0]
        type_match = re.match(r"^\[(选择|判断|choice|judge)\]\s*(.*)", first, re.I)
        if type_match:
            qtype = _parse_question_type(type_match.group(1))
            content = type_match.group(2).strip()
            body_lines = lines[1:]
        else:
            body_lines = lines

        if not qtype:
            # 尝试从内容推断
            for ln in body_lines:
                if re.match(r"^[A-Da-d][.、:：]", ln):
                    qtype = QuestionType.choice
                    break
            if not qtype:
                qtype = QuestionType.judge

        if not content:
            for ln in body_lines:
                if re.match(r"^(答案|分值|分数|score)[：:]", ln, re.I):
                    continue
                if not re.match(r"^[A-Da-d][.、:：]", ln):
                    content = ln
                    break

        for ln in body_lines:
            ans_match = re.match(r"^答案[：:]\s*(.+)", ln, re.I)
            if ans_match:
                answer = ans_match.group(1).strip()
                continue
            score_match = re.match(r"^(分值|分数|score)[：:]\s*([\d.]+)", ln, re.I)
            if score_match:
                score = float(score_match.group(2))
                continue
            opt_match = re.match(r"^([A-Da-d])[.、:：]\s*(.+)", ln)
            if opt_match and qtype == QuestionType.choice:
                options.append(f"{opt_match.group(1).upper()}. {opt_match.group(2).strip()}")
                continue
            if not content and ln != answer:
                content = ln

        if not content:
            errors.append(f"第 {idx} 题：题目内容不能为空")
            continue
        if not answer:
            errors.append(f"第 {idx} 题：缺少答案")
            continue

        answer = normalize_answer(answer, qtype)

        if qtype == QuestionType.choice:
            if len(options) < 2:
                errors.append(f"第 {idx} 题：选择题至少需要 2 个选项")
                continue
        else:
            options = ["正确", "错误"]

        questions.append({
            "type": qtype,
            "content": content,
            "options": options,
            "correct_answer": answer,
            "score": score,
            "order_num": len(questions),
        })

    return questions, errors


TYPING_CSV_HEADERS = {
    "title": {"标题", "title", "文章", "篇名", "文章标题"},
    "content": {"正文", "content", "内容", "文章内容", "练习正文"},
    "difficulty": {"难度", "difficulty"},
    "time_limit": {"建议时长", "时长", "time_limit", "建议时长(秒)", "秒"},
}

_TYPING_DIFFICULTY = {
    "入门": TypingDifficulty.beginner,
    "初级": TypingDifficulty.beginner,
    "beginner": TypingDifficulty.beginner,
    "基础": TypingDifficulty.basic,
    "basic": TypingDifficulty.basic,
    "达标": TypingDifficulty.standard,
    "标准": TypingDifficulty.standard,
    "standard": TypingDifficulty.standard,
    "进阶": TypingDifficulty.advanced,
    "高级": TypingDifficulty.advanced,
    "advanced": TypingDifficulty.advanced,
}

_TITLE_RE = re.compile(r"^【标题】\s*[:：]?\s*(.*)$")
_DIFF_RE = re.compile(r"^【难度】\s*[:：]?\s*(.*)$")
_TIME_RE = re.compile(r"^【时长】\s*[:：]?\s*(.*)$")

MAX_TYPING_ARTICLES = 100
MAX_TYPING_CONTENT = 20000
MAX_TYPING_TITLE = 200


def decode_uploaded_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("文件编码无法识别，请使用 UTF-8 或 GBK 编码")


def _parse_typing_difficulty(raw: str, default: TypingDifficulty) -> tuple[Optional[TypingDifficulty], Optional[str]]:
    text = (raw or "").strip().lower()
    if not text:
        return default, None
    value = _TYPING_DIFFICULTY.get(text)
    if value is None:
        return None, f"难度无效（{raw.strip()}），可选：入门、基础、达标、进阶"
    return value, None


def _parse_typing_time_limit(raw: str, default: int) -> tuple[Optional[int], Optional[str]]:
    text = re.sub(r"秒$", "", (raw or "").strip())
    if not text:
        return default, None
    if not text.isdigit():
        return None, f"时长无效（{raw.strip()}）"
    value = int(text)
    if value < 30 or value > 600:
        return None, "建议时长需在 30 到 600 秒之间"
    return value, None


def _typing_article(title: str, content: str, difficulty: TypingDifficulty, time_limit: int) -> dict:
    return {
        "title": title.strip()[:MAX_TYPING_TITLE],
        "content": content.strip(),
        "difficulty": difficulty,
        "time_limit": time_limit,
    }


def _looks_like_typing_csv(text: str) -> bool:
    first = next((ln for ln in text.split("\n") if ln.strip()), "")
    if not first or "【标题】" in first:
        return False
    delimiter = "\t" if "\t" in first else ("," if "," in first else None)
    if not delimiter:
        return False
    try:
        headers = next(csv.reader([first], delimiter=delimiter))
    except csv.Error:
        return False
    mapped = _map_headers(headers, TYPING_CSV_HEADERS)
    return "title" in mapped and "content" in mapped


def _parse_typing_csv(
    text: str,
    default_difficulty: TypingDifficulty,
    default_time_limit: int,
) -> tuple[list[dict], list[str]]:
    first = next((ln for ln in text.split("\n") if ln.strip()), "")
    delimiter = "\t" if "\t" in first else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not rows:
        return [], ["无法解析表格"]

    header_map = _map_headers(rows[0], TYPING_CSV_HEADERS)
    articles: list[dict] = []
    errors: list[str] = []

    for line_no, row in enumerate(rows[1:], start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        title = row[header_map["title"]].strip() if header_map["title"] < len(row) else ""
        content = row[header_map["content"]].strip() if header_map["content"] < len(row) else ""
        if not title:
            errors.append(f"第 {line_no} 行：标题不能为空")
            continue
        if len(title) > MAX_TYPING_TITLE:
            errors.append(f"第 {line_no} 行：标题不能超过 {MAX_TYPING_TITLE} 字")
            continue
        if not content:
            errors.append(f"第 {line_no} 行：正文不能为空")
            continue
        if len(content) > MAX_TYPING_CONTENT:
            errors.append(f"第 {line_no} 行：正文过长（上限 {MAX_TYPING_CONTENT} 字）")
            continue

        difficulty = default_difficulty
        if header_map.get("difficulty") is not None and header_map["difficulty"] < len(row):
            difficulty, err = _parse_typing_difficulty(row[header_map["difficulty"]], default_difficulty)
            if err:
                errors.append(f"第 {line_no} 行：{err}")
                continue
        time_limit = default_time_limit
        if header_map.get("time_limit") is not None and header_map["time_limit"] < len(row):
            time_limit, err = _parse_typing_time_limit(row[header_map["time_limit"]], default_time_limit)
            if err:
                errors.append(f"第 {line_no} 行：{err}")
                continue
        articles.append(_typing_article(title, content, difficulty, time_limit))

    return articles, errors


def _parse_typing_blocks(
    text: str,
    default_difficulty: TypingDifficulty,
    default_time_limit: int,
) -> tuple[list[dict], list[str]]:
    articles: list[dict] = []
    errors: list[str] = []
    current: Optional[dict] = None
    body: list[str] = []
    saw_leading = False

    def flush() -> None:
        nonlocal current, body
        if current is None:
            return
        title = (current.get("title") or "").strip()
        content = "\n".join(body).strip()
        label = f"第 {current['index']} 篇"
        if not title:
            errors.append(f"{label}：标题不能为空")
        elif len(title) > MAX_TYPING_TITLE:
            errors.append(f"{label}：标题不能超过 {MAX_TYPING_TITLE} 字")
        elif not content:
            errors.append(f"「{title}」：正文不能为空")
        elif len(content) > MAX_TYPING_CONTENT:
            errors.append(f"「{title}」：正文过长（上限 {MAX_TYPING_CONTENT} 字）")
        elif current.get("error"):
            errors.append(f"「{title}」：{current['error']}")
        else:
            articles.append(_typing_article(title, content, current["difficulty"], current["time_limit"]))
        current = None
        body = []

    index = 0
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        title_match = _TITLE_RE.match(line)
        if title_match:
            flush()
            index += 1
            current = {
                "index": index,
                "title": title_match.group(1),
                "difficulty": default_difficulty,
                "time_limit": default_time_limit,
                "error": "",
            }
            body = []
            continue
        if current is None:
            if line and not saw_leading:
                errors.append("批量导入请以【标题】开头，或使用表格格式")
                saw_leading = True
            continue
        if not line:
            if body:
                body.append(raw_line)
            continue
        if not body:
            diff_match = _DIFF_RE.match(line)
            if diff_match:
                difficulty, err = _parse_typing_difficulty(diff_match.group(1), default_difficulty)
                if err:
                    current["error"] = err
                else:
                    current["difficulty"] = difficulty
                continue
            time_match = _TIME_RE.match(line)
            if time_match:
                time_limit, err = _parse_typing_time_limit(time_match.group(1), default_time_limit)
                if err:
                    current["error"] = err
                else:
                    current["time_limit"] = time_limit
                continue
        body.append(raw_line)
    flush()
    return articles, errors


def parse_typing_articles(
    text: str,
    default_title: str = "",
    default_difficulty: TypingDifficulty = TypingDifficulty.basic,
    default_time_limit: int = 120,
) -> tuple[list[dict], list[str]]:
    """解析打字文章导入文本。

    支持：
    - 【标题】分段（可选【难度】【时长】）
    - CSV/TSV 表头：标题,正文,难度,建议时长
    - 单篇纯文本（使用 default_title，通常来自表单或文件名）
    """
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return [], ["导入内容为空"]

    if default_time_limit < 30 or default_time_limit > 600:
        return [], ["建议时长需在 30 到 600 秒之间"]

    if _looks_like_typing_csv(text):
        return _parse_typing_csv(text, default_difficulty, default_time_limit)

    if any(_TITLE_RE.match(ln.strip()) for ln in text.split("\n")):
        return _parse_typing_blocks(text, default_difficulty, default_time_limit)

    title = (default_title or "").strip()
    if not title:
        return [], ["单篇文章请填写标题，或使用【标题】分段 / CSV 表格批量导入"]
    if len(title) > MAX_TYPING_TITLE:
        return [], [f"标题不能超过 {MAX_TYPING_TITLE} 字"]
    if len(text) > MAX_TYPING_CONTENT:
        return [], [f"正文过长（上限 {MAX_TYPING_CONTENT} 字）"]
    return [_typing_article(title, text, default_difficulty, default_time_limit)], []
