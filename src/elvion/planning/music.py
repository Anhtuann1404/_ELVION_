"""Planning rules and natural language command parsing for Apple Music."""
from dataclasses import dataclass, field
import re
import time
import unicodedata

from elvion.core.contracts import ActionIntent, TaskRequest
from elvion.core.music import (
    MUSIC_APP_ID, MUSIC_APP_OPEN, MUSIC_CURRENT_TRACK, MUSIC_PAUSE,
    MUSIC_PLAY, MUSIC_READ_STATE, MUSIC_RESUME, MUSIC_SEARCH, MUSIC_TARGET,
    valid_persistent_id, valid_track_query,
)
from elvion.planning.rules import UnsupportedCommand


@dataclass
class MusicSelectionState:
    """Tracks candidate tracks returned from a previous search for disambiguation."""
    candidates: list[dict] = field(default_factory=list)
    query: str = ""
    created_at: float = field(default_factory=time.monotonic)
    ttl_seconds: float = 300.0  # 5 minutes validity

    def is_valid(self, clock=time.monotonic) -> bool:
        return bool(self.candidates) and (clock() - self.created_at <= self.ttl_seconds)

    def get_candidate(self, index_1_based: int, clock=time.monotonic) -> dict:
        if not self.is_valid(clock=clock):
            raise UnsupportedCommand("Danh sách kết quả tìm kiếm đã hết hiệu lực hoặc chưa có")
        if index_1_based < 1 or index_1_based > len(self.candidates):
            raise UnsupportedCommand(
                f"Lựa chọn số {index_1_based} không hợp lệ; chỉ có {len(self.candidates)} kết quả"
            )
        return self.candidates[index_1_based - 1]


def is_music_command(utterance: str) -> bool:
    """Quick check whether an utterance is directed at Apple Music."""
    text = unicodedata.normalize("NFC", utterance).strip().lower()
    keywords = (
        "apple music", "nhạc", "music", "bài hát", "phát", "tạm dừng",
        "tiếp tục", "pause", "resume", "play", "đang phát"
    )
    return any(kw in text for kw in keywords)


def plan_music(
    request: TaskRequest,
    *,
    selection_state: MusicSelectionState | None = None,
    clock=time.monotonic,
) -> ActionIntent:
    """Parse Vietnamese natural language utterance into a validated ActionIntent."""
    raw = unicodedata.normalize("NFC", request.utterance).strip()
    text = raw.lower()

    # 1. Open Apple Music
    if re.fullmatch(r"(?:mở|open)\s+(?:ứng\s+dụng\s+)?(?:apple\s+music|music|nhạc)", text):
        return ActionIntent(
            task_id=request.task_id,
            capability=MUSIC_APP_OPEN,
            target=MUSIC_TARGET,
            arguments={},
            postcondition={"kind": "app_running", "bundle_id": MUSIC_APP_ID},
            risk="low",
        )

    # 2. Query currently playing track / "Đang phát bài gì?"
    if re.fullmatch(
        r"(?:đang\s+phát\s+bài\s+gì\??|đang\s+phát\s+gì\??|bài\s+gì\s+đang\s+phát\??|kiểm\s+tra\s+bài\s+hát|what'?s\s+playing\??)",
        text,
    ):
        return ActionIntent(
            task_id=request.task_id,
            capability=MUSIC_CURRENT_TRACK,
            target=MUSIC_TARGET,
            arguments={},
            postcondition={"kind": "current_track_read"},
            risk="low",
        )

    # 3. Read player state
    if re.fullmatch(r"(?:trạng\s+thái\s+nhạc|trạng\s+thái\s+player|player\s+status)", text):
        return ActionIntent(
            task_id=request.task_id,
            capability=MUSIC_READ_STATE,
            target=MUSIC_TARGET,
            arguments={},
            postcondition={"kind": "player_state_read"},
            risk="low",
        )

    # 4. Pause music
    if re.fullmatch(r"(?:tạm\s+dừng\s+nhạc|tạm\s+dừng|dừng\s+nhạc|pause|pause\s+music)", text):
        return ActionIntent(
            task_id=request.task_id,
            capability=MUSIC_PAUSE,
            target=MUSIC_TARGET,
            arguments={},
            postcondition={"kind": "player_paused"},
            risk="low",
        )

    # 5. Resume music
    if re.fullmatch(r"(?:tiếp\s+tục\s+phát|tiếp\s+tục|phát\s+tiếp|resume|resume\s+music)", text):
        return ActionIntent(
            task_id=request.task_id,
            capability=MUSIC_RESUME,
            target=MUSIC_TARGET,
            arguments={},
            postcondition={"kind": "player_resumed"},
            risk="low",
        )

    # 6. Play by direct 16-hex persistent ID (checked before candidate index to avoid misclassifying numeric hex IDs)
    direct_id_match = re.fullmatch(r"(?:phát|play)\s+([0-9a-fA-F]{16})", raw, flags=re.IGNORECASE)
    if direct_id_match:
        pid = direct_id_match.group(1).upper()
        return ActionIntent(
            task_id=request.task_id,
            capability=MUSIC_PLAY,
            target=MUSIC_TARGET,
            arguments={"persistent_id": pid},
            postcondition={"kind": "track_playing", "persistent_id": pid},
            risk="medium",
        )

    # 7. Select candidate from previous search results: "Phát kết quả số 2", "Phát bài số 1"
    pick_match = re.fullmatch(
        r"(?:phát|chọn)\s+(?:kết\s+quả|bài)?\s*(?:số|thứ)?\s*(\d{1,3})",
        text,
    )
    if pick_match:
        idx = int(pick_match.group(1))
        if selection_state is None or not selection_state.is_valid(clock=clock):
            raise UnsupportedCommand("Lựa chọn không hợp lệ hoặc đã hết hiệu lực")
        candidate = selection_state.get_candidate(idx, clock=clock)
        pid = candidate["persistent_id"]
        return ActionIntent(
            task_id=request.task_id,
            capability=MUSIC_PLAY,
            target=MUSIC_TARGET,
            arguments={
                "persistent_id": pid,
                "title": candidate.get("name", ""),
                "artist": candidate.get("artist", ""),
            },
            postcondition={"kind": "track_playing", "persistent_id": pid},
            risk="medium",
        )

    # 8. Search query: "Tìm bài <tên bài> của <nghệ sĩ>", "Tìm bài <tên bài>", "Tìm kiếm bài <tên bài>"
    search_match = re.fullmatch(
        r"(?:tìm\s+kiếm\s+bài|tìm\s+bài|tìm)\s+(.+)",
        raw,
        flags=re.IGNORECASE,
    )
    if search_match:
        query = search_match.group(1).strip()
        if not valid_track_query(query):
            raise UnsupportedCommand("Tên bài hoặc truy vấn tìm kiếm không hợp lệ")
        return ActionIntent(
            task_id=request.task_id,
            capability=MUSIC_SEARCH,
            target=MUSIC_TARGET,
            arguments={"query": query},
            postcondition={"kind": "music_searched", "query": query},
            risk="low",
        )

    raise UnsupportedCommand(f"Lệnh không được hỗ trợ trong phạm vi Apple Music: {raw}")
