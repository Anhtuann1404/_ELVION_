"""Apple Music adapter and backend implementations for macOS."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
from typing import Any, Protocol, runtime_checkable

from elvion.core.contracts import (
    ActionIntent, ActionResult, ActionStatus, AuthorizationToken, CapabilityDescriptor,
    ErrorCode, Method, Observation, ObservationRequest, ObservationStatus, ProbeResult,
)
from elvion.core.music import (
    MUSIC_APP_ID, MUSIC_CAPABILITIES, MUSIC_CURRENT_TRACK, MUSIC_PAUSE,
    MUSIC_PLAY, MUSIC_READ_STATE, MUSIC_RESUME, MUSIC_SEARCH, MUSIC_APP_OPEN,
    MusicPlayerState, MusicTrack, valid_persistent_id, valid_track_query,
)

_MUSIC_JXA_SCRIPT = r'''
ObjC.import("Foundation");
ObjC.import("AppKit");

function run() {
    function fail(code, reason) { throw {elvionCode: code, reason: reason}; }
    try {
        var bytes = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile;
        var input = ObjC.unwrap($.NSString.alloc.initWithDataEncoding(bytes, $.NSUTF8StringEncoding));
        var payload = JSON.parse(input);
        var op = payload.operation;

        if (op === "app_state") {
            var bundleID = "com.apple.Music";
            var apps = $.NSRunningApplication.runningApplicationsWithBundleIdentifier(bundleID);
            var pids = [];
            for (var i = 0; i < Number(apps.count); i++) {
                var app = apps.objectAtIndex(i);
                if (!app.terminated && ObjC.unwrap(app.bundleIdentifier) === bundleID) {
                    pids.push(Number(app.processIdentifier));
                }
            }
            return JSON.stringify({ok: true, running: pids.length > 0, pids: pids});
        }

        var music = Application("com.apple.Music");
        if (!music.running()) {
            fail("TARGET_NOT_FOUND", "MUSIC_APP_NOT_RUNNING");
        }

        if (op === "player_state") {
            var state = music.playerState();
            var vol = 100;
            try { vol = music.soundVolume(); } catch(e) {}
            var pos = 0;
            try { pos = music.playerPosition(); } catch(e) {}
            var cur = null;
            try {
                var tr = music.currentTrack();
                if (tr && tr.name()) {
                    cur = {
                        persistent_id: tr.persistentID(),
                        name: tr.name(),
                        artist: tr.artist() || "",
                        album: tr.album() || "",
                        duration: tr.duration() || 0
                    };
                }
            } catch(e) {}
            return JSON.stringify({ok: true, state: state, volume: vol, position: pos, current_track: cur});
        }

        if (op === "search") {
            var query = payload.query;
            var limit = payload.limit || 10;
            var playlist = music.playlists[0];
            var tracks = playlist.search({for: query}) || [];
            var results = [];
            for (var i = 0; i < tracks.length && results.length < limit; i++) {
                var t = tracks[i];
                try {
                    results.push({
                        persistent_id: t.persistentID(),
                        name: t.name(),
                        artist: t.artist() || "",
                        album: t.album() || "",
                        duration: t.duration() || 0
                    });
                } catch(err) {}
            }
            return JSON.stringify({ok: true, results: results});
        }

        if (op === "play") {
            var targetId = payload.persistent_id;
            var matched = music.tracks.whose({persistentID: targetId})();
            if (!matched || matched.length === 0) {
                fail("TARGET_NOT_FOUND", "TRACK_NOT_FOUND");
            }
            matched[0].play();
            return JSON.stringify({ok: true, persistent_id: targetId});
        }

        if (op === "pause") {
            music.pause();
            return JSON.stringify({ok: true});
        }

        if (op === "resume") {
            music.play();
            return JSON.stringify({ok: true});
        }

        if (op === "check_track") {
            var targetId = payload.persistent_id;
            var matched = music.tracks.whose({persistentID: targetId})();
            var exists = Boolean(matched && matched.length > 0);
            return JSON.stringify({ok: true, exists: exists});
        }

        fail("UNSUPPORTED", "UNKNOWN_OPERATION");
    } catch(e) {
        var nativeError = typeof e.number === "number" ? e.number : e.errorNumber;
        var code = e.elvionCode || (nativeError === -1743 ? "PERMISSION_DENIED" : "TRANSIENT_FAILURE");
        var reason = e.reason || (e.message || String(e));
        return JSON.stringify({ok: false, error_code: code, reason: reason});
    }
}
'''


class MusicBackendError(ValueError):
    def __init__(self, code: ErrorCode, message: str, *, external_effect_possible: bool = False,
                 native_exit_code: int | None = None, os_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.external_effect_possible = external_effect_possible
        self.native_exit_code = native_exit_code
        self.os_status = os_status


@runtime_checkable
class AppleMusicBackend(Protocol):
    def check_available(self) -> None: ...
    def app_state(self) -> dict[str, Any]: ...
    def launch(self) -> None: ...
    def player_state(self) -> MusicPlayerState: ...
    def search_library(self, query: str, limit: int = 10) -> list[MusicTrack]: ...
    def play_track(self, persistent_id: str) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def track_exists(self, persistent_id: str) -> bool: ...


class NativeAppleMusicBackend:
    command_timeout = 3.0
    app_path = Path("/System/Applications/Music.app")

    def __init__(self, *, runner=None):
        self.runner = runner if runner is not None else subprocess.run

    def check_available(self) -> None:
        if sys.platform != "darwin":
            raise MusicBackendError(ErrorCode.UNSUPPORTED, "macOS is required")
        if not all(os.access(path, os.X_OK) for path in ("/usr/bin/open", "/usr/bin/osascript")):
            raise MusicBackendError(ErrorCode.UNSUPPORTED, "Required macOS tools are unavailable")
        try:
            with (self.app_path / "Contents/Info.plist").open("rb") as stream:
                info = plistlib.load(stream)
            if not isinstance(info, dict) or info.get("CFBundleIdentifier") != MUSIC_APP_ID:
                raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, "Music app bundle does not match")
            executable = info.get("CFBundleExecutable")
            if not isinstance(executable, str) or not executable:
                raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, "Music app executable missing")
            executable_path = self.app_path / "Contents/MacOS" / executable
            if not executable_path.is_file() or not os.access(executable_path, os.X_OK):
                raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, "Music app executable is unavailable")
        except MusicBackendError:
            raise
        except Exception:
            raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, "Music app is unavailable") from None

    def _run_jxa(self, payload: dict[str, Any], *, mutating: bool = False) -> dict[str, Any]:
        self.check_available()
        try:
            result = self.runner(
                ["/usr/bin/osascript", "-l", "JavaScript", "-e", _MUSIC_JXA_SCRIPT],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=self.command_timeout,
                check=False,
            )
        except PermissionError:
            raise MusicBackendError(ErrorCode.PERMISSION_DENIED, "OS denied process execution") from None
        except FileNotFoundError:
            raise MusicBackendError(ErrorCode.UNSUPPORTED, "osascript tool is unavailable") from None
        except (subprocess.TimeoutExpired, OSError):
            raise MusicBackendError(
                ErrorCode.TRANSIENT_FAILURE,
                "Command failed or timed out",
                external_effect_possible=mutating,
            ) from None

        if result.returncode != 0:
            stderr = result.stderr or ""
            if "-1743" in stderr:
                raise MusicBackendError(ErrorCode.PERMISSION_DENIED, "Apple Events permission denied (-1743)")
            raise MusicBackendError(
                ErrorCode.TRANSIENT_FAILURE,
                f"osascript returned error: {stderr.strip()}",
                external_effect_possible=mutating,
                native_exit_code=result.returncode,
            )

        try:
            data = json.loads(result.stdout)
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object")
            if data.get("ok") is not True:
                if data.get("ok") is not False:
                    raise ValueError("INVALID_ENVELOPE")
                err_code_str = data.get("error_code", "TRANSIENT_FAILURE")
                try:
                    code = ErrorCode(err_code_str)
                except ValueError:
                    code = ErrorCode.TRANSIENT_FAILURE
                raise MusicBackendError(code, data.get("reason", "Operation failed"), external_effect_possible=mutating)
            return data
        except MusicBackendError:
            raise
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise MusicBackendError(ErrorCode.VERIFICATION_FAILED, "Invalid backend response",
                                    external_effect_possible=mutating) from None

    def app_state(self) -> dict[str, Any]:
        data = self._run_jxa({"operation": "app_state"})
        return {"running": bool(data.get("running")), "pids": list(data.get("pids", []))}

    def launch(self) -> None:
        self.check_available()
        try:
            res = self.runner(["/usr/bin/open", "-a", str(self.app_path)], capture_output=True, text=True,
                              timeout=self.command_timeout, check=False)
            if res.returncode != 0:
                raise MusicBackendError(ErrorCode.TRANSIENT_FAILURE, "Failed to launch Music.app",
                                        external_effect_possible=True, native_exit_code=res.returncode)
        except (subprocess.TimeoutExpired, OSError):
            raise MusicBackendError(ErrorCode.TRANSIENT_FAILURE, "Timed out launching Music.app",
                                    external_effect_possible=True) from None

    def player_state(self) -> MusicPlayerState:
        data = self._run_jxa({"operation": "player_state"})
        cur_dict = data.get("current_track")
        cur_track = None
        if isinstance(cur_dict, dict) and cur_dict.get("persistent_id") and cur_dict.get("name"):
            cur_track = MusicTrack(
                persistent_id=cur_dict["persistent_id"],
                name=cur_dict["name"],
                artist=cur_dict.get("artist", ""),
                album=cur_dict.get("album", ""),
                duration=float(cur_dict.get("duration", 0.0)),
            )
        raw_state = data.get("state")
        if raw_state not in ("playing", "paused", "stopped"):
            raise MusicBackendError(ErrorCode.VERIFICATION_FAILED, "Invalid player state")
        return MusicPlayerState(
            state=raw_state,
            running=True,
            volume=int(data.get("volume", 100)),
            position=float(data.get("position", 0.0)),
            current_track=cur_track,
        )

    def search_library(self, query: str, limit: int = 10) -> list[MusicTrack]:
        data = self._run_jxa({"operation": "search", "query": query, "limit": limit})
        tracks: list[MusicTrack] = []
        for raw in data.get("results", []):
            if isinstance(raw, dict) and raw.get("persistent_id") and raw.get("name"):
                tracks.append(MusicTrack(
                    persistent_id=raw["persistent_id"],
                    name=raw["name"],
                    artist=raw.get("artist", ""),
                    album=raw.get("album", ""),
                    duration=float(raw.get("duration", 0.0)),
                ))
        return tracks

    def play_track(self, persistent_id: str) -> None:
        self._run_jxa({"operation": "play", "persistent_id": persistent_id}, mutating=True)

    def pause(self) -> None:
        self._run_jxa({"operation": "pause"}, mutating=True)

    def resume(self) -> None:
        self._run_jxa({"operation": "resume"}, mutating=True)

    def track_exists(self, persistent_id: str) -> bool:
        data = self._run_jxa({"operation": "check_track", "persistent_id": persistent_id})
        return bool(data.get("exists", False))


class FakeAppleMusicBackend:
    """Hermetic in-memory mock for testing AM-01 through AM-29."""

    def __init__(
        self,
        *,
        running: bool = False,
        pids: list[int] | None = None,
        player_state_val: str = "stopped",
        current_track: MusicTrack | None = None,
        tracks: list[MusicTrack] | None = None,
        volume: int = 100,
        position: float = 0.0,
        simulate_permission_denied: bool = False,
        simulate_unsupported: bool = False,
        simulate_timeout: bool = False,
        simulate_bad_schema: bool = False,
        simulate_app_quit: bool = False,
    ):
        self.running = running
        self.pids = pids if pids is not None else ([1234] if running else [])
        self.state_val = player_state_val
        self.cur_track = current_track
        self.tracks = list(tracks) if tracks is not None else []
        self.volume = volume
        self.position = position
        self.simulate_permission_denied = simulate_permission_denied
        self.simulate_unsupported = simulate_unsupported
        self.simulate_timeout = simulate_timeout
        self.simulate_bad_schema = simulate_bad_schema
        self.simulate_app_quit = simulate_app_quit

    def check_available(self) -> None:
        if self.simulate_permission_denied:
            raise MusicBackendError(ErrorCode.PERMISSION_DENIED, "Automation permission denied")
        if self.simulate_unsupported:
            raise MusicBackendError(ErrorCode.UNSUPPORTED, "Platform unsupported or helper missing")

    def _check_faults(self, *, mutating: bool = False) -> None:
        self.check_available()
        if self.simulate_timeout:
            raise MusicBackendError(ErrorCode.TRANSIENT_FAILURE, "Operation timed out", external_effect_possible=mutating)
        if self.simulate_bad_schema:
            raise MusicBackendError(ErrorCode.VERIFICATION_FAILED, "Backend returned invalid schema")
        if self.simulate_app_quit:
            self.running = False
            self.pids = []
            raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, "Music.app terminated unexpectedly")

    def app_state(self) -> dict[str, Any]:
        self._check_faults()
        return {"running": self.running, "pids": list(self.pids)}

    def launch(self) -> None:
        self._check_faults(mutating=True)
        self.running = True
        if not self.pids:
            self.pids = [1234]

    def player_state(self) -> MusicPlayerState:
        self._check_faults()
        if not self.running:
            raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, "Music app not running")
        return MusicPlayerState(
            state=self.state_val,
            running=self.running,
            volume=self.volume,
            position=self.position,
            current_track=self.cur_track,
        )

    def search_library(self, query: str, limit: int = 10) -> list[MusicTrack]:
        self._check_faults()
        if not self.running:
            raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, "Music app not running")
        q = query.lower().strip()
        tokens = [tok for tok in q.split() if tok]
        matched = [
            t for t in self.tracks
            if all(tok in f"{t.name} {t.artist} {t.album}".lower() for tok in tokens)
        ]
        return matched[:limit]

    def play_track(self, persistent_id: str) -> None:
        self._check_faults(mutating=True)
        if not self.running:
            raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, "Music app not running")
        target = next((t for t in self.tracks if t.persistent_id == persistent_id), None)
        if not target:
            raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, f"Track {persistent_id} not found in library")
        self.cur_track = target
        self.state_val = "playing"

    def pause(self) -> None:
        self._check_faults(mutating=True)
        if not self.running:
            raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, "Music app not running")
        self.state_val = "paused"

    def resume(self) -> None:
        self._check_faults(mutating=True)
        if not self.running:
            raise MusicBackendError(ErrorCode.TARGET_NOT_FOUND, "Music app not running")
        self.state_val = "playing"

    def track_exists(self, persistent_id: str) -> bool:
        self._check_faults()
        return any(t.persistent_id == persistent_id for t in self.tracks)


class AppleMusicAdapter:
    """Native macOS Apple Music adapter implementing the ELVION Adapter protocol."""

    def __init__(self, capability: str, *, backend: AppleMusicBackend | None = None):
        if capability not in MUSIC_CAPABILITIES:
            raise ValueError(f"Unsupported Music capability: {capability}")
        self.capability = capability
        self.backend = backend if backend is not None else NativeAppleMusicBackend()

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name=f"macos.music.{self.capability}",
            platform="macos",
            app=MUSIC_APP_ID,
            method=Method.NATIVE_API,
            supported_actions=(self.capability,),
            required_permissions=(self.capability,),
            can_verify=True,
            estimated_latency_ms=10,
            simulated=False,
        )

    def probe(self, intent: ActionIntent) -> ProbeResult:
        if intent.capability != self.capability or intent.target.get("app") != MUSIC_APP_ID:
            return ProbeResult(
                adapter_id=self.descriptor.name,
                method=Method.NATIVE_API,
                supported=False,
                prerequisites_met=False,
                reason="DESCRIPTOR_UNSUPPORTED",
            )
        try:
            self.backend.check_available()
            return ProbeResult(
                adapter_id=self.descriptor.name,
                method=Method.NATIVE_API,
                supported=True,
                prerequisites_met=True,
                reason="APPLE_MUSIC_READY",
            )
        except MusicBackendError as exc:
            return ProbeResult(
                adapter_id=self.descriptor.name,
                method=Method.NATIVE_API,
                supported=True,
                prerequisites_met=False,
                reason=exc.code.value,
            )
        except Exception:
            return ProbeResult(
                adapter_id=self.descriptor.name,
                method=Method.NATIVE_API,
                supported=True,
                prerequisites_met=False,
                reason="ADAPTER_PROBE_FAILED",
            )

    def execute(self, intent: ActionIntent, token: AuthorizationToken) -> ActionResult:
        if intent.capability != self.capability or intent.target.get("app") != MUSIC_APP_ID:
            return ActionResult(
                status=ActionStatus.FAILED,
                method=Method.NATIVE_API,
                error_code=ErrorCode.UNSUPPORTED,
                evidence={"reason": "DESCRIPTOR_UNSUPPORTED"},
            )

        if not token.permits(intent):
            return ActionResult(
                status=ActionStatus.FAILED,
                method=Method.NATIVE_API,
                error_code=ErrorCode.PERMISSION_DENIED,
                evidence={"reason": "INVALID_OR_EXPIRED_TOKEN"},
            )

        args = intent.arguments
        try:
            if intent.capability == MUSIC_APP_OPEN:
                app_state = self.backend.app_state()
                if app_state["running"]:
                    return ActionResult(
                        status=ActionStatus.SUCCESS,
                        method=Method.NATIVE_API,
                        evidence={"bundle_id": MUSIC_APP_ID, "already_running": True, "pids": app_state["pids"]},
                    )
                self.backend.launch()
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    method=Method.NATIVE_API,
                    evidence={"bundle_id": MUSIC_APP_ID, "launch_requested": True},
                    external_effect_possible=True,
                )

            elif intent.capability == MUSIC_READ_STATE:
                state = self.backend.player_state()
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    method=Method.NATIVE_API,
                    evidence={
                        "player_state": state.state,
                        "volume": state.volume,
                        "position": state.position,
                        "has_track": state.current_track is not None,
                    },
                )

            elif intent.capability == MUSIC_CURRENT_TRACK:
                state = self.backend.player_state()
                cur = state.current_track
                evidence = {
                    "player_state": state.state,
                    "has_track": cur is not None,
                }
                if cur is not None:
                    evidence["track"] = {
                        "persistent_id": cur.persistent_id,
                        "name": cur.name,
                        "artist": cur.artist,
                        "album": cur.album,
                        "duration": cur.duration,
                    }
                return ActionResult(status=ActionStatus.SUCCESS, method=Method.NATIVE_API, evidence=evidence)

            elif intent.capability == MUSIC_SEARCH:
                query = args.get("query", "")
                limit = int(args.get("limit", 10))
                tracks = self.backend.search_library(query, limit=limit)
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    method=Method.NATIVE_API,
                    evidence={
                        "query": query,
                        "count": len(tracks),
                        "candidates": [
                            {
                                "persistent_id": t.persistent_id,
                                "name": t.name,
                                "artist": t.artist,
                                "album": t.album,
                                "duration": t.duration,
                            }
                            for t in tracks
                        ],
                    },
                )

            elif intent.capability == MUSIC_PLAY:
                persistent_id = args.get("persistent_id")
                if not persistent_id or not valid_persistent_id(persistent_id):
                    return ActionResult(
                        status=ActionStatus.FAILED,
                        method=Method.NATIVE_API,
                        error_code=ErrorCode.TARGET_NOT_FOUND,
                        evidence={"reason": "INVALID_PERSISTENT_ID"},
                    )
                self.backend.play_track(persistent_id)
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    method=Method.NATIVE_API,
                    evidence={"persistent_id": persistent_id, "action": "played"},
                    external_effect_possible=True,
                )

            elif intent.capability == MUSIC_PAUSE:
                self.backend.pause()
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    method=Method.NATIVE_API,
                    evidence={"action": "paused"},
                    external_effect_possible=True,
                )

            elif intent.capability == MUSIC_RESUME:
                self.backend.resume()
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    method=Method.NATIVE_API,
                    evidence={"action": "resumed"},
                    external_effect_possible=True,
                )

            return ActionResult(
                status=ActionStatus.FAILED,
                method=Method.NATIVE_API,
                error_code=ErrorCode.UNSUPPORTED,
                evidence={"reason": "CAPABILITY_NOT_HANDLED"},
            )

        except MusicBackendError as exc:
            return ActionResult(
                status=ActionStatus.UNCERTAIN if exc.external_effect_possible else ActionStatus.FAILED,
                method=Method.NATIVE_API,
                error_code=exc.code,
                evidence={"reason": str(exc)},
                external_effect_possible=exc.external_effect_possible,
                retryable=False,
            )

    def observe(self, request: ObservationRequest) -> Observation:
        if request.app != MUSIC_APP_ID:
            return Observation(status=ObservationStatus.UNAVAILABLE, error_code=ErrorCode.UNSUPPORTED)

        try:
            if request.kind == "app_running":
                state = self.backend.app_state()
                return Observation(
                    status=ObservationStatus.OBSERVED,
                    data={"bundle_id": MUSIC_APP_ID, "running": state["running"], "pids": state["pids"]},
                )

            elif request.kind in ("player_state", "track_playing", "player_paused"):
                state = self.backend.player_state()
                cur_dict = None
                if state.current_track is not None:
                    cur_dict = {
                        "persistent_id": state.current_track.persistent_id,
                        "name": state.current_track.name,
                        "artist": state.current_track.artist,
                        "album": state.current_track.album,
                        "duration": state.current_track.duration,
                    }
                return Observation(
                    status=ObservationStatus.OBSERVED,
                    data={
                        "bundle_id": MUSIC_APP_ID,
                        "running": state.running,
                        "state": state.state,
                        "volume": state.volume,
                        "position": state.position,
                        "current_track": cur_dict,
                    },
                )

            elif request.kind == "current_track":
                state = self.backend.player_state()
                cur = state.current_track
                cur_dict = None
                if cur is not None:
                    cur_dict = {
                        "persistent_id": cur.persistent_id,
                        "name": cur.name,
                        "artist": cur.artist,
                        "album": cur.album,
                        "duration": cur.duration,
                    }
                return Observation(
                    status=ObservationStatus.OBSERVED,
                    data={
                        "bundle_id": MUSIC_APP_ID,
                        "player_state": state.state,
                        "has_track": cur is not None,
                        "track": cur_dict,
                    },
                )

            elif request.kind == "track_library":
                exists = self.backend.track_exists(request.subject_id)
                if not exists:
                    return Observation(status=ObservationStatus.NOT_FOUND, data={"persistent_id": request.subject_id})
                return Observation(status=ObservationStatus.OBSERVED, data={"persistent_id": request.subject_id, "exists": True})

            return Observation(status=ObservationStatus.UNAVAILABLE, error_code=ErrorCode.UNSUPPORTED)

        except MusicBackendError as exc:
            return Observation(status=ObservationStatus.UNAVAILABLE, error_code=exc.code)


def create_music_adapters(backend: AppleMusicBackend | None = None) -> tuple[AppleMusicAdapter, ...]:
    """Helper to instantiate adapters for all supported Music capabilities sharing the same backend."""
    b = backend if backend is not None else NativeAppleMusicBackend()
    return tuple(AppleMusicAdapter(cap, backend=b) for cap in sorted(MUSIC_CAPABILITIES))
