"""Policy enforcement and safety rules for Apple Music capabilities."""
from typing import Any

from elvion.core.contracts import ActionIntent
from elvion.core.music import (
    MUSIC_APP_ID, MUSIC_APP_OPEN, MUSIC_CAPABILITIES, MUSIC_CURRENT_TRACK,
    MUSIC_PAUSE, MUSIC_PLAY, MUSIC_READ_STATE, MUSIC_RESUME, MUSIC_SEARCH,
    MUSIC_TARGET, valid_persistent_id, valid_track_query,
)
from elvion.policy.rules import CapabilityPolicy


class MusicPolicy(CapabilityPolicy):
    version = "music-v1"

    def __init__(self, *, require_confirmation: bool = False, confirmations=None):
        super().__init__(require_confirmation=require_confirmation, confirmations=confirmations)

    def allows(self, intent: ActionIntent, grants: frozenset[str]) -> bool:
        if (
            intent.capability not in MUSIC_CAPABILITIES
            or intent.capability not in grants
            or intent.target != MUSIC_TARGET
            or intent.preconditions != ()
        ):
            return False

        # Strictly forbid any volume adjustment or mutation of library/playlists
        if "volume" in intent.arguments or "sound_volume" in intent.arguments:
            return False

        if intent.capability == MUSIC_APP_OPEN:
            return (
                intent.risk == "low"
                and intent.arguments == {}
                and intent.postcondition == {"kind": "app_running", "bundle_id": MUSIC_APP_ID}
            )

        elif intent.capability == MUSIC_READ_STATE:
            return (
                intent.risk == "low"
                and intent.arguments == {}
                and intent.postcondition == {"kind": "player_state_read"}
            )

        elif intent.capability == MUSIC_CURRENT_TRACK:
            return (
                intent.risk == "low"
                and intent.arguments == {}
                and intent.postcondition == {"kind": "current_track_read"}
            )

        elif intent.capability == MUSIC_SEARCH:
            if intent.risk != "low":
                return False
            query = intent.arguments.get("query")
            if not valid_track_query(query):
                return False
            limit = intent.arguments.get("limit", 10)
            if not isinstance(limit, int) or limit < 1 or limit > 50:
                return False
            allowed_keys = {"query"} if "limit" not in intent.arguments else {"query", "limit"}
            if set(intent.arguments.keys()) != allowed_keys:
                return False
            return intent.postcondition == {"kind": "music_searched", "query": query}

        elif intent.capability == MUSIC_PLAY:
            if intent.risk not in ("low", "medium"):
                return False
            pid = intent.arguments.get("persistent_id")
            if not valid_persistent_id(pid):
                return False
            extra_keys = set(intent.arguments.keys()) - {"persistent_id", "title", "artist"}
            if extra_keys:
                return False
            for opt_key in ("title", "artist"):
                if opt_key in intent.arguments and not isinstance(intent.arguments[opt_key], str):
                    return False
            return intent.postcondition == {"kind": "track_playing", "persistent_id": pid}

        elif intent.capability == MUSIC_PAUSE:
            return (
                intent.risk in ("low", "medium")
                and intent.arguments == {}
                and intent.postcondition == {"kind": "player_paused"}
            )

        elif intent.capability == MUSIC_RESUME:
            return (
                intent.risk in ("low", "medium")
                and intent.arguments == {}
                and intent.postcondition == {"kind": "player_resumed"}
            )

        return False

    def requires_confirmation(self, intent: ActionIntent) -> bool:
        if not self.require_confirmation:
            return False
        # Playback mutations require confirmation when require_confirmation is True
        return intent.capability in (MUSIC_PLAY, MUSIC_PAUSE, MUSIC_RESUME)

    def confirmation_effects(self, intent: ActionIntent) -> tuple[str, ...]:
        if intent.capability == MUSIC_PLAY:
            pid = intent.arguments.get("persistent_id", "")
            title = intent.arguments.get("title", "")
            detail = f" '{title}'" if title else ""
            return (f"Phát bài hát{detail} trên Apple Music",)
        elif intent.capability == MUSIC_PAUSE:
            return ("Tạm dừng phát nhạc trên Apple Music",)
        elif intent.capability == MUSIC_RESUME:
            return ("Tiếp tục phát nhạc trên Apple Music",)
        return ()
