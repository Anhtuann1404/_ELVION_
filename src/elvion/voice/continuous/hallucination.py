"""Whisper hallucination and noise artifact detector for Vietnamese and English speech."""
import re

_COMMON_HALLUCINATIONS = [
    r"cảm ơn (các bạn|quý vị|mọi người|bạn|anh chị)?\s*(đã|đang)?\s*(xem|theo dõi|lắng nghe|ủng hộ)",
    r"hãy (bấm\s+)?(like|đăng ký|subscribe|chia sẻ)",
    r"hẹn gặp lại",
    r"chúc các bạn",
    r"subtitles? by",
    r"amara\.org",
    r"phụ đề bởi",
    r"^[\s\.\,\!\?\-\_…]+$",
]
_COMPILED_HALLUCINATION_RES = [re.compile(p, re.IGNORECASE) for p in _COMMON_HALLUCINATIONS]


def is_whisper_hallucination(text: str) -> bool:
    """Check if transcribed text is a known Whisper phantom hallucination or repetitive loop."""
    clean = text.strip()
    if not clean or len(clean) < 2:
        return True

    # 1. Match against known hallucination phrases
    for pat in _COMPILED_HALLUCINATION_RES:
        if pat.search(clean):
            return True

    # 2. Check for repetitive word loops (e.g. "à à à à" or "ừm ừm ừm")
    words = clean.lower().split()
    if len(words) >= 3:
        unique_words = set(words)
        if len(unique_words) == 1:
            return True
        # If one word makes up >= 75% of the utterance
        most_common_count = max(words.count(w) for w in unique_words)
        if most_common_count / len(words) >= 0.75:
            return True

    return False
