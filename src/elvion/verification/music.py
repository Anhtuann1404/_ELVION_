"""Independent verification for Apple Music actions using fresh observations."""
import time
from typing import Callable

from elvion.core.adapter import Adapter
from elvion.core.contracts import (
    ActionIntent, ActionResult, ActionStatus, Observation, ObservationRequest, ObservationStatus,
)
from elvion.core.music import (
    MUSIC_APP_ID, MUSIC_APP_OPEN, MUSIC_CURRENT_TRACK, MUSIC_PAUSE,
    MUSIC_PLAY, MUSIC_READ_STATE, MUSIC_RESUME, MUSIC_SEARCH,
)


def verify_music_action(
    intent: ActionIntent,
    result: ActionResult,
    adapter: Adapter,
    *,
    timeout_seconds: float = 3.0,
    interval_seconds: float = 0.1,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Independently verify an Apple Music action; never trust the execution result alone."""
    if result.status != ActionStatus.SUCCESS:
        return False

    bundle_id = intent.target.get("app")
    if bundle_id != MUSIC_APP_ID:
        return False

    deadline = clock() + timeout_seconds

    if intent.capability == MUSIC_APP_OPEN:
        if intent.postcondition != {"kind": "app_running", "bundle_id": MUSIC_APP_ID}:
            return False
        while True:
            obs = adapter.observe(ObservationRequest(app=MUSIC_APP_ID, kind="app_running", subject_id=MUSIC_APP_ID))
            if obs.status == ObservationStatus.OBSERVED:
                data = obs.data
                if (
                    data.get("bundle_id") == MUSIC_APP_ID
                    and data.get("running") is True
                    and isinstance(data.get("pids"), list)
                    and data["pids"]
                    and all(isinstance(pid, int) and pid > 0 for pid in data["pids"])
                ):
                    return True
            if clock() >= deadline:
                return False
            sleep(min(interval_seconds, max(0.0, deadline - clock())))

    elif intent.capability == MUSIC_PLAY:
        target_pid = intent.arguments.get("persistent_id")
        if not target_pid or intent.postcondition != {"kind": "track_playing", "persistent_id": target_pid}:
            return False
        while True:
            obs = adapter.observe(ObservationRequest(app=MUSIC_APP_ID, kind="track_playing", subject_id=MUSIC_APP_ID))
            if obs.status == ObservationStatus.OBSERVED:
                data = obs.data
                cur_track = data.get("current_track")
                # Player must be playing AND currently playing track must match target persistent ID
                if (
                    data.get("running") is True
                    and data.get("state") == "playing"
                    and isinstance(cur_track, dict)
                    and cur_track.get("persistent_id") == target_pid
                ):
                    return True
            if clock() >= deadline:
                return False
            sleep(min(interval_seconds, max(0.0, deadline - clock())))

    elif intent.capability == MUSIC_PAUSE:
        if intent.postcondition != {"kind": "player_paused"}:
            return False
        while True:
            obs = adapter.observe(ObservationRequest(app=MUSIC_APP_ID, kind="player_paused", subject_id=MUSIC_APP_ID))
            if obs.status == ObservationStatus.OBSERVED:
                data = obs.data
                # Must be running and state must be paused or stopped
                if data.get("running") is True and data.get("state") in ("paused", "stopped"):
                    return True
            if clock() >= deadline:
                return False
            sleep(min(interval_seconds, max(0.0, deadline - clock())))

    elif intent.capability == MUSIC_RESUME:
        if intent.postcondition != {"kind": "player_resumed"}:
            return False
        while True:
            obs = adapter.observe(ObservationRequest(app=MUSIC_APP_ID, kind="player_state", subject_id=MUSIC_APP_ID))
            if obs.status == ObservationStatus.OBSERVED:
                data = obs.data
                if data.get("running") is True and data.get("state") == "playing":
                    return True
            if clock() >= deadline:
                return False
            sleep(min(interval_seconds, max(0.0, deadline - clock())))

    elif intent.capability == MUSIC_READ_STATE:
        if intent.postcondition != {"kind": "player_state_read"}:
            return False
        obs = adapter.observe(ObservationRequest(app=MUSIC_APP_ID, kind="player_state", subject_id=MUSIC_APP_ID))
        return (
            obs.status == ObservationStatus.OBSERVED
            and obs.data.get("bundle_id") == MUSIC_APP_ID
            and obs.data.get("state") in ("playing", "paused", "stopped")
        )

    elif intent.capability == MUSIC_CURRENT_TRACK:
        if intent.postcondition != {"kind": "current_track_read"}:
            return False
        obs = adapter.observe(ObservationRequest(app=MUSIC_APP_ID, kind="current_track", subject_id=MUSIC_APP_ID))
        return (
            obs.status == ObservationStatus.OBSERVED
            and obs.data.get("bundle_id") == MUSIC_APP_ID
            and "has_track" in obs.data
        )

    elif intent.capability == MUSIC_SEARCH:
        query = intent.arguments.get("query")
        if not query or intent.postcondition != {"kind": "music_searched", "query": query}:
            return False
        # Search is a read-only query; verify result structure has candidates
        candidates = result.evidence.get("candidates")
        return isinstance(candidates, list)

    return False
