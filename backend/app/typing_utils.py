"""初中打字测试评分标准与计算工具

参考标准：
- 中考信息技术：中文录入约 10 字/分钟
- 义务教育信息科技课标（第三学段）：基础达标 ≥30 字/分钟，准确率 ≥95%
- 技能训练：良好 20 字/分钟，卓越 40 字/分钟
"""
from typing import Optional

# 速度等级（字/分钟）
TYPING_LEVELS = [
    {"level": "卓越", "min_wpm": 40, "color": "#7c3aed", "desc": "远超课标要求"},
    {"level": "优秀", "min_wpm": 30, "color": "#10b981", "desc": "达到课标基础达标"},
    {"level": "良好", "min_wpm": 20, "color": "#3b82f6", "desc": "高于中考基本要求"},
    {"level": "达标", "min_wpm": 10, "color": "#f59e0b", "desc": "达到中考信息技术要求"},
    {"level": "未达标", "min_wpm": 0, "color": "#ef4444", "desc": "需继续练习"},
]

DEFAULT_TYPING_CONFIG = {
    "time_limit": 120,
    "min_wpm": 10,
    "pass_wpm": 20,
    "excellent_wpm": 30,
    "min_accuracy": 95,
}


def get_typing_level(wpm: float) -> dict:
    for item in TYPING_LEVELS:
        if wpm >= item["min_wpm"]:
            return item
    return TYPING_LEVELS[-1]


def compare_text(reference: str, typed: str) -> dict:
    """逐字比对，计算正确字数和错误详情"""
    reference = reference.strip()
    typed = typed.strip()
    correct = 0
    errors = 0
    details = []

    max_len = max(len(reference), len(typed))
    for i in range(max_len):
        ref_char = reference[i] if i < len(reference) else ""
        typed_char = typed[i] if i < len(typed) else ""
        if ref_char and typed_char:
            if ref_char == typed_char:
                correct += 1
                details.append({"index": i, "char": ref_char, "status": "correct"})
            else:
                errors += 1
                details.append({"index": i, "char": typed_char, "expected": ref_char, "status": "wrong"})
        elif ref_char and not typed_char:
            details.append({"index": i, "char": ref_char, "status": "missing"})
        elif typed_char and not ref_char:
            errors += 1
            details.append({"index": i, "char": typed_char, "status": "extra"})

    typed_len = len(typed) if typed else 1
    ref_len = len(reference) if reference else 1
    accuracy = round(correct / ref_len * 100, 1) if ref_len else 0
    accuracy_by_typed = round(correct / typed_len * 100, 1) if typed_len else 0

    return {
        "correct_chars": correct,
        "error_chars": errors,
        "total_chars": ref_len,
        "typed_chars": len(typed),
        "accuracy": accuracy,
        "accuracy_by_typed": accuracy_by_typed,
        "details": details[:50],
    }


def calculate_wpm(correct_chars: int, duration_seconds: float) -> float:
    if duration_seconds <= 0:
        return 0.0
    minutes = duration_seconds / 60
    return round(correct_chars / minutes, 1)


def parse_typing_config(options) -> dict:
    if isinstance(options, dict):
        config = {**DEFAULT_TYPING_CONFIG, **options}
    elif isinstance(options, list) and options and isinstance(options[0], dict):
        config = {**DEFAULT_TYPING_CONFIG, **options[0]}
    else:
        config = dict(DEFAULT_TYPING_CONFIG)
    return config


def score_typing_question(
    wpm: float,
    accuracy: float,
    max_score: float,
    config: Optional[dict] = None,
) -> tuple[float, bool, str]:
    """根据初中标准计算打字题得分"""
    config = config or DEFAULT_TYPING_CONFIG
    min_accuracy = config.get("min_accuracy", 95)
    min_wpm = config.get("min_wpm", 10)

    level = get_typing_level(wpm)
    passed = wpm >= min_wpm and accuracy >= min_accuracy

    if accuracy < 80:
        score = max_score * 0.2
    elif accuracy < min_accuracy:
        score = max_score * 0.4 * (accuracy / min_accuracy)
    elif wpm >= 40:
        score = max_score
    elif wpm >= 30:
        score = max_score * 0.9
    elif wpm >= 20:
        score = max_score * 0.75
    elif wpm >= min_wpm:
        score = max_score * 0.6
    else:
        score = max_score * (wpm / min_wpm) * 0.4 if min_wpm else 0

    score = round(min(score, max_score), 1)
    remark = f"{level['level']}（{wpm} 字/分，准确率 {accuracy}%）"
    return score, passed, remark
