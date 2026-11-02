"""Whisper hallucination and noise artifact detector for Vietnamese and English speech."""
import re

_STANDALONE_HALLUCINATION_PATTERNS = [
    r"^(?:cảm\s+ơn\s+(?:các\s+bạn|quý\s+vị|mọi\s+người|bạn|anh\s+chị)?\s*(?:đã|đang)?\s*(?:xem|theo\s+dõi|lắng\s+nghe|ủng\s+hộ)?(?:\s+(?:video|kênh|chúng\s+tôi))?(?:\s+(?:nhé|nha|ạ))?[\.\!\?]?\s*)+$",
    r"^(?:(?:hãy\s+)?(?:bấm\s+)?(?:like|đăng\s+ký|subscribe|chia\s+sẻ)(?:\s+(?:và|hoặc)\s+(?:like|đăng\s+ký|subscribe|chia\s+sẻ))?(?:\s+(?:kênh|video))?(?:\s+(?:nhé|nha|ạ))?[\.\!\?]?\s*)+$",
    r"^(?:hẹn\s+gặp\s+lại(?:\s+(?:các\s+bạn|quý\s+vị|mọi\s+người))?(?:\s+(?:trong|ở)\s+(?:các\s+)?(?:video|clip|tập)\s+tiếp\s+theo)?(?:\s+(?:nhé|nha|ạ))?[\.\!\?]?\s*)+$",
    r"^(?:chúc\s+(?:các\s+bạn|quý\s+vị|mọi\s+người)\s+một\s+ngày\s+(?:tốt\s+lành|vui\s+vẻ)[\.\!\?]?\s*)+$",
    r"^(?:subtitles?\s+by\s+.*|amara\.org|phụ\s+đề\s+bởi\s+.*)$",
    r"^[\s\.\,\!\?\-\_…]+$",
]
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _STANDALONE_HALLUCINATION_PATTERNS]

COMMAND_PREFIXES = (
    "dịch", "mở", "tạo", "tìm", "nhắc", "hỏi", "bật", "tắt", "phát", "cho", "xem",
    "thời tiết", "chào", "xin chào", "làm sao", "hát", "chơi",
)


def is_whisper_hallucination(text: str) -> bool:
    """Check if transcribed text is a known Whisper phantom hallucination or repetitive loop."""
    clean = text.strip()
    if not clean or len(clean) < 2:
        return True

    lowered = clean.lower()
    # Legitimate task or command queries should never be discarded as hallucination
    if any(lowered.startswith(cmd + " ") for cmd in COMMAND_PREFIXES):
        return False

    # 1. Match against standalone hallucination phrases
    for pat in _COMPILED_PATTERNS:
        if pat.match(clean):
            return True

    # 2. Check for repetitive word loops (e.g. "à à à à" or "ừm ừm ừm")
    words = lowered.split()
    if len(words) >= 3:
        unique_words = set(words)
        if len(unique_words) == 1:
            return True
        # If one word makes up >= 75% of the utterance
        most_common_count = max(words.count(w) for w in unique_words)
        if most_common_count / len(words) >= 0.75:
            return True

    return False
