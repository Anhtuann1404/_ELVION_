"""Native macOS launch via LaunchServices; observation via read-only AppKit/JXA.

No shell, user-supplied executable, Apple Events to another app or GUI scripting.
The initial app path and bundle ID are pinned to Calculator.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys

from elvion.core.app_catalog import CALCULATOR_BUNDLE_ID
from elvion.core.contracts import (
    ActionIntent, ActionResult, ActionStatus, AuthorizationToken, CapabilityDescriptor,
    ErrorCode, Method, Observation, ObservationRequest, ObservationStatus, ProbeResult,
)

# Fixed script; the allowlisted ID is passed as an argument, never interpolated into code.
_STATE_SCRIPT = r'''
ObjC.import("AppKit");
function run(argv) {
    var bundleID = argv[0];
    var apps = $.NSRunningApplication.runningApplicationsWithBundleIdentifier(bundleID);
    var pids = [];
    for (var i = 0; i < Number(apps.count); i++) {
        var app = apps.objectAtIndex(i);
        if (!app.terminated && ObjC.unwrap(app.bundleIdentifier) === bundleID) {
            pids.push(Number(app.processIdentifier));
        }
    }
    return JSON.stringify({bundle_id: bundleID, pids: pids});
}
'''


class BackendError(ValueError):
    def __init__(self, code: ErrorCode, message: str, *, external_effect_possible: bool = False,
                 native_exit_code: int | None = None, os_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.external_effect_possible = external_effect_possible
        self.native_exit_code = native_exit_code
        self.os_status = os_status


@dataclass(frozen=True)
class AppState:
    bundle_id: str
    pids: tuple[int, ...]

    @property
    def running(self) -> bool:
        return bool(self.pids)


class MacOSAppBackend:
    command_timeout = 3.0
    app_path = Path("/System/Applications/Calculator.app")

    def __init__(self, *, runner=None):
        self.runner = runner if runner is not None else subprocess.run

    def check_available(self, bundle_id: str) -> None:
        if bundle_id != CALCULATOR_BUNDLE_ID:
            raise BackendError(ErrorCode.UNSUPPORTED, "App is not allowlisted")
        if sys.platform != "darwin":
            raise BackendError(ErrorCode.UNSUPPORTED, "macOS is required")
        if not all(os.access(path, os.X_OK) for path in ("/usr/bin/open", "/usr/bin/osascript")):
            raise BackendError(ErrorCode.UNSUPPORTED, "Required macOS tools are unavailable")
        try:
            with (self.app_path / "Contents/Info.plist").open("rb") as stream:
                info = plistlib.load(stream)
            if not isinstance(info, dict):
                raise BackendError(ErrorCode.TARGET_NOT_FOUND, "Invalid app bundle metadata")
            executable = info.get("CFBundleExecutable")
            if (info.get("CFBundleIdentifier") != bundle_id or not isinstance(executable, str)
                    or not executable or executable in {".", ".."} or Path(executable).name != executable):
                raise BackendError(ErrorCode.TARGET_NOT_FOUND, "App bundle does not match allowlist")
            executable_path = self.app_path / "Contents/MacOS" / executable
            if not executable_path.is_file() or not os.access(executable_path, os.X_OK):
                raise BackendError(ErrorCode.TARGET_NOT_FOUND, "App executable is unavailable")
        except BackendError:
            raise
        except (OSError, ValueError, plistlib.InvalidFileException):
            raise BackendError(ErrorCode.TARGET_NOT_FOUND, "App bundle is unavailable") from None

    def _run(self, argv: list[str], *, launching: bool = False):
        try:
            result = self.runner(argv, capture_output=True, text=True,
                                 timeout=self.command_timeout, check=False, shell=False)
        except PermissionError:
            raise BackendError(ErrorCode.PERMISSION_DENIED, "OS denied process execution") from None
        except FileNotFoundError:
            raise BackendError(ErrorCode.UNSUPPORTED, "Native tool is unavailable") from None
        except (subprocess.TimeoutExpired, OSError):
            raise BackendError(ErrorCode.TRANSIENT_FAILURE, "Native command failed or timed out",
                               external_effect_possible=launching) from None
        if result.returncode != 0:
            # An error after requesting launch can still have produced an effect. Never retry it.
            status = re.search(r"(?:Code|code)=(-?\d+)", result.stderr or "")
            raise BackendError(ErrorCode.TRANSIENT_FAILURE, "Native command returned an error",
                               external_effect_possible=launching, native_exit_code=result.returncode,
                               os_status=int(status.group(1)) if status else None)
        return result

    def state(self, bundle_id: str) -> AppState:
        self.check_available(bundle_id)
        result = self._run(["/usr/bin/osascript", "-l", "JavaScript", "-e", _STATE_SCRIPT, bundle_id])
        try:
            payload = json.loads(result.stdout)
            if (not isinstance(payload, dict) or payload.get("bundle_id") != bundle_id
                    or not isinstance(payload.get("pids"), list)
                    or any(type(pid) is not int or pid <= 0 for pid in payload["pids"])):
                raise ValueError("Invalid observation")
            return AppState(bundle_id=bundle_id, pids=tuple(payload["pids"]))
        except (ValueError, TypeError):
            raise BackendError(ErrorCode.VERIFICATION_FAILED, "Invalid AppKit observation") from None

    def launch(self, bundle_id: str) -> None:
        self.check_available(bundle_id)
        # Fixed absolute app path avoids reliance on a registered display name or untrusted input.
        self._run(["/usr/bin/open", "-a", str(self.app_path)], launching=True)


class MacOSAppAdapter:
    def __init__(self, *, backend: MacOSAppBackend | None = None):
        self.backend = backend if backend is not None else MacOSAppBackend()

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(name="macos.app.native", platform="macos", app=CALCULATOR_BUNDLE_ID,
                                    method=Method.NATIVE_API, required_permissions=("app.open",),
                                    supported_actions=("app.open",), can_verify=True,
                                    estimated_latency_ms=0, simulated=False)

    def supports(self, intent: ActionIntent) -> bool:
        return (intent.capability == "app.open" and intent.target == {"app": CALCULATOR_BUNDLE_ID}
                and intent.arguments == {} and intent.preconditions == () and intent.risk == "low"
                and intent.postcondition == {"kind": "app_running", "bundle_id": CALCULATOR_BUNDLE_ID})

    def probe(self, intent: ActionIntent) -> ProbeResult:
        supported = self.supports(intent)
        ready = False
        reason = "UNSUPPORTED"
        if supported:
            try:
                self.backend.check_available(CALCULATOR_BUNDLE_ID)
            except BackendError as exc:
                reason = exc.code.value
            else:
                ready, reason = True, "NATIVE_TOOLS_AND_BUNDLE_AVAILABLE"
        return ProbeResult(adapter_id=self.descriptor.name, method=Method.NATIVE_API,
                           supported=supported, prerequisites_met=ready, reason=reason)

    def execute(self, intent: ActionIntent, token: AuthorizationToken) -> ActionResult:
        if not token.permits(intent):
            return ActionResult(status=ActionStatus.FAILED, method=Method.NATIVE_API,
                                error_code=ErrorCode.PERMISSION_DENIED)
        if not self.supports(intent):
            return ActionResult(status=ActionStatus.FAILED, method=Method.NATIVE_API,
                                error_code=ErrorCode.UNSUPPORTED)
        try:
            state = self.backend.state(CALCULATOR_BUNDLE_ID)
            if state.running:
                return ActionResult(status=ActionStatus.SUCCESS, method=Method.NATIVE_API,
                                    evidence={"bundle_id": CALCULATOR_BUNDLE_ID, "already_running": True})
            # The read-only state query can take time; revalidate immediately before OS mutation.
            if not token.permits(intent) or not self.supports(intent):
                return ActionResult(status=ActionStatus.FAILED, method=Method.NATIVE_API,
                                    error_code=ErrorCode.PERMISSION_DENIED)
            self.backend.launch(CALCULATOR_BUNDLE_ID)
        except BackendError as exc:
            evidence = {"bundle_id": CALCULATOR_BUNDLE_ID}
            if exc.native_exit_code is not None:
                evidence["native_exit_code"] = exc.native_exit_code
            if exc.os_status is not None:
                evidence["os_status"] = exc.os_status
            return ActionResult(status=ActionStatus.UNCERTAIN if exc.external_effect_possible else ActionStatus.FAILED,
                                method=Method.NATIVE_API, error_code=exc.code, evidence=evidence,
                                external_effect_possible=exc.external_effect_possible)
        return ActionResult(status=ActionStatus.SUCCESS, method=Method.NATIVE_API,
                            evidence={"bundle_id": CALCULATOR_BUNDLE_ID, "launch_requested": True},
                            external_effect_possible=True)

    def observe(self, request: ObservationRequest) -> Observation:
        if (request.app != CALCULATOR_BUNDLE_ID or request.kind != "app_running"
                or request.subject_id != CALCULATOR_BUNDLE_ID):
            return Observation(status=ObservationStatus.UNAVAILABLE, error_code=ErrorCode.UNSUPPORTED)
        try:
            state = self.backend.state(CALCULATOR_BUNDLE_ID)
        except BackendError as exc:
            return Observation(status=ObservationStatus.UNAVAILABLE, error_code=exc.code)
        return Observation(status=ObservationStatus.OBSERVED,
                           data={"bundle_id": state.bundle_id, "running": state.running,
                                 "pids": list(state.pids)})
