from typing import List

from app.models.schemas import SafetyResult


PROHIBITED_PHRASES = [
    # Vietnamese advice wording
    "bạn nên",
    "tôi khuyên",
    "khuyến nghị bạn",
    "hãy đầu tư",
    "nên đầu tư",
    "nên tiết kiệm",
    "nên vay",

    # English advice wording
    "you should",
    "we recommend",
    "i recommend",
    "you need to",
    "you must",
    "invest now",

    # Specific action / allocation wording
    "chuyển 5%",
    "chuyển 10%",
    "move 5%",
    "move 10%",
    "allocate",
    "put your money",
    "move your balance",

    # Return / profit claims
    "tối ưu lợi nhuận",
    "tối đa hóa lợi nhuận",
    "lợi nhuận đảm bảo",
    "không rủi ro",
    "risk-free",
    "guaranteed return",
    "maximize return",
    "optimize profit",
]


def _normalize(text: str) -> str:
    return text.lower().strip()


def validate_text_safety(
    item_id: str,
    item_type: str,
    text: str,
) -> SafetyResult:
    normalized = _normalize(text)
    violations: List[str] = []

    for phrase in PROHIBITED_PHRASES:
        if phrase in normalized:
            violations.append(f"Contains prohibited phrase: {phrase}")

    # Simple rule: block percentage-based action suggestions.
    # This catches phrases like "move 5%", "save 20%", "allocate 10%".
    if "%" in normalized and any(
        verb in normalized
        for verb in ["move", "save", "allocate", "invest", "chuyển", "tiết kiệm", "đầu tư"]
    ):
        violations.append("Contains percentage-based financial action suggestion.")

    passed = len(violations) == 0

    return SafetyResult(
        checked_item_id=item_id,
        item_type=item_type,
        passed=passed,
        violations=violations,
        notes=None if passed else "Text failed non-advisory safety rules.",
    )


def validate_observation(item_id: str, text: str) -> SafetyResult:
    return validate_text_safety(
        item_id=item_id,
        item_type="observation",
        text=text,
    )


def validate_nudge(item_id: str, text: str) -> SafetyResult:
    return validate_text_safety(
        item_id=item_id,
        item_type="nudge",
        text=text,
    )


UNSAFE_CHALLENGE_VERBS = [
    "deposit into",
    "move money to",
    "activate",
    "invest in",
    "transfer to",
    "borrow more",

    "nạp tiền vào",
    "chuyển tiền vào",
    "đầu tư vào",
    "kích hoạt khoản vay",
    "vay thêm",
    "mở khoản vay",
]


def validate_challenge(item_id: str, text: str) -> SafetyResult:
    result = validate_text_safety(
        item_id=item_id,
        item_type="challenge",
        text=text,
    )
    
    normalized = _normalize(text)
    violations = list(result.violations)

    for verb in UNSAFE_CHALLENGE_VERBS:
        if verb in normalized:
            violations.append(f"Contains prohibited challenge action verb: {verb}")

    passed = len(violations) == 0

    return SafetyResult(
        checked_item_id=item_id,
        item_type="challenge",
        passed=passed,
        violations=violations,
        notes=None if passed else "Text failed challenge safety rules.",
    )
