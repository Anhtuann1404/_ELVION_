"""Shared contracts, data models, and constants for Apple Music capability."""
from dataclasses import dataclass, field
import re
from typing import Any

from elvion.core.contracts import Contract, ContractError, require_mapping, require_text

MUSIC_APP_ID = "com.apple.Music"
MUSIC_TARGET = {"app": MUSIC_APP_ID}

MUSIC_READ_STATE = "music.read_state"
MUSIC_CURRENT_TRACK = "music.current_track"
MUSIC_SEARCH = "music.search"
MUSIC_PLAY = "music.play"
MUSIC_PAUSE = "music.pause"
MUSIC_RESUME = "music.resume"
MUSIC_APP_OPEN = "app.open"

MUSIC_CAPABILITIES = frozenset({
    MUSIC_READ_STATE,
    MUSIC_CURRENT_TRACK,
    MUSIC_SEARCH,
    MUSIC_PLAY,
    MUSIC_PAUSE,
    MUSIC_RESUME,
    MUSIC_APP_OPEN,
})

_HEX_16_RE = re.compile(r"^[0-9A-Fa-f]{16}$")


def valid_track_query(value: object) -> bool:
    """Validate user search query: non-empty string, reasonable length, no ASCII control chars."""
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped or len(value) > 256:
        return False
    # Disallow non-printable control characters
    return not any(ord(c) < 32 and c not in "\n\t" for c in value)


def valid_persistent_id(value: object) -> bool:
    """Validate 16-hex character Music.app persistent ID."""
    if not isinstance(value, str):
        return False
    return bool(_HEX_16_RE.match(value.strip()))


@dataclass(frozen=True, kw_only=True)
class MusicTrack(Contract):
    persistent_id: str
    name: str
    artist: str = ""
    album: str = ""
    duration: float = 0.0

    def __post_init__(self) -> None:
        require_text(self.persistent_id, "persistent_id")
        require_text(self.name, "name")
        if not valid_persistent_id(self.persistent_id):
            raise ContractError(f"Invalid persistent_id: {self.persistent_id}")
        if not isinstance(self.artist, str) or not isinstance(self.album, str):
            raise ContractError("artist and album must be strings")
        if not isinstance(self.duration, (int, float)) or self.duration < 0:
            raise ContractError("duration must be a non-negative number")


@dataclass(frozen=True, kw_only=True)
class MusicPlayerState(Contract):
    state: str  # "playing", "paused", "stopped"
    running: bool = True
    volume: int = 100
    position: float = 0.0
    current_track: MusicTrack | None = None

    def __post_init__(self) -> None:
        require_text(self.state, "state")
        if self.state not in ("playing", "paused", "stopped"):
            raise ContractError(f"Invalid player state: {self.state}")
        if type(self.running) is not bool:
            raise ContractError("running must be boolean")
        if type(self.volume) is not int or not (0 <= self.volume <= 100):
            raise ContractError("volume must be an integer between 0 and 100")
        if not isinstance(self.position, (int, float)) or self.position < 0:
            raise ContractError("position must be a non-negative number")
        if self.current_track is not None and not isinstance(self.current_track, MusicTrack):
            raise ContractError("current_track must be MusicTrack or None")


class MusicOrchestrator:
    """Orchestrator for Apple Music operations with policy checks and verification."""

    def __new__(
        cls,
        *,
        backend=None,
        require_confirmation: bool = False,
        trace_store=None,
        selection_state=None,
    ):
        from functools import partial
        from elvion.adapters.apple_music import create_music_adapters
        from elvion.adapters.registry import AdapterRegistry
        from elvion.core.orchestrator import TaskOrchestrator
        from elvion.planning.music import plan_music
        from elvion.policy.music import MusicPolicy
        from elvion.verification.music import verify_music_action

        adapters = create_music_adapters(backend=backend)
        planner = (
            partial(plan_music, selection_state=selection_state)
            if selection_state is not None
            else plan_music
        )
        return TaskOrchestrator(
            registry=AdapterRegistry(adapters),
            policy=MusicPolicy(require_confirmation=require_confirmation),
            verifier=verify_music_action,
            simulated=False,
            planner=planner,
            success_message="Thao tác Apple Music đã được kiểm chứng thành công",
            trace_store=trace_store,
        )

