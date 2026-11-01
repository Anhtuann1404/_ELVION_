"""Versioned allowlist projection: raw requests, previews and evidence are never logged."""
from datetime import datetime, timezone
from math import isfinite
from uuid import UUID

from elvion.core.contracts import ErrorCode, Method, TaskStatus

SCHEMA_VERSION = 1
CAPABILITIES = frozenset({"app.open", "note.create", "note.find", "web.open", "web.search", "web.open_result"})
ADAPTERS = frozenset({"macos.app.native", "macos.notes.note.create", "macos.notes.note.find",
                     "fake_notes.native_api", "fake_notes.accessibility", "fake_notes.vision", "fake_notes.dom"}) | frozenset(
                         "browser.dom." + cap for cap in CAPABILITIES if cap.startswith("web.")
                     ) | {"browser.vision.web.open_result"}
POLICIES = frozenset({"demo-v2", "macos-app-v1", "macos-notes-v1", "base-v1", "browser-web-v1"})
REASONS = frozenset({
    "WEB_BROWSER_READY", "WEB_BROWSER_UNAVAILABLE", "WEB_BROWSER_CLOSED",
    "WEB_NAVIGATION_UNCERTAIN", "WEB_SEARCH_NOT_VERIFIED", "WEB_RESULT_EXPIRED",
    "WEB_ACTION_DENIED", "WEB_REDIRECT_OUTSIDE_SCOPE", "WEB_DRIVER_FAILURE",
    "POLICY_DENIED", "UNSUPPORTED", "ELIGIBLE", "SIMULATED_READY", "SIMULATED_UNAVAILABLE",
    "DESCRIPTOR_UNSUPPORTED", "ADAPTER_PERMISSION_DENIED", "VERIFICATION_UNAVAILABLE", "ADAPTER_PROBE_FAILED",
    "NATIVE_TOOLS_AND_BUNDLE_AVAILABLE", "NOTES_APP_AVAILABLE_AUTOMATION_NOT_YET_CHECKED",
    "ACCOUNT_NOT_FOUND", "FOLDER_NOT_FOUND", "NOTE_NOT_FOUND", "MULTIPLE_MATCHES", "MULTIPLE_FOLDERS",
    "SHARED_OR_LOCKED_NOTE", "SHARED_FOLDER", "NOTE_OUTSIDE_FOLDER", "AUTOMATION_DENIED", "AUTOMATION_FAILED",
    "AUTHORIZATION_EXPIRED", "INVALID_REQUEST", "INVALID_TITLE", "INVALID_NOTE_ID", "NOTES_APP_NOT_FOUND",
    "MACOS_AUTOMATION_UNAVAILABLE", "INVALID_OPERATION", "MISSING_AUTHORIZATION", "AUTOMATION_UNAVAILABLE",
    "AUTOMATION_TIMEOUT_OR_FAILURE", "AUTOMATION_PROCESS_FAILED", "INVALID_AUTOMATION_RESPONSE",
}) | frozenset(error.value for error in ErrorCode)
STATUSES = frozenset(item.value for item in TaskStatus)
METHODS = frozenset(item.value for item in Method)
ERRORS = frozenset(item.value for item in ErrorCode)


def uuid_text(value: object) -> str | None:
    if not isinstance(value, (str, UUID)):
        return None
    try:
        return str(UUID(str(value)))
    except ValueError:
        return None


def time_text(value: object) -> str | None:
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime) or value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError):
        return None


def _enum(value: object, allowed: frozenset[str]) -> str | None:
    return str(value) if isinstance(value, str) and value in allowed else None


def _duration(value: object) -> float | None:
    if type(value) not in (int, float) or value < 0 or value > 86_400_000 or not isfinite(value):
        return None
    return round(float(value), 3)


def _safe_diagnostics(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in ("postcondition_verified", "already_running", "launch_requested"):
        if type(value.get(key)) is bool:
            result[key] = value[key]
    for key in ("native_error", "native_exit_code", "os_status"):
        if type(value.get(key)) is int and -(2 ** 31) <= value[key] < 2 ** 31:
            result[key] = value[key]
    reason = _enum(value.get("reason"), REASONS)
    if reason is not None:
        result["reason"] = reason
    return result


def sanitize_record(raw: dict, *, kind: str) -> dict:
    """Create a new safe object; never stringify arbitrary values or preserve unknown keys."""
    if kind not in {"event", "task_result"}:
        raise ValueError("Unknown trace record kind")
    task_id, trace_id = uuid_text(raw.get("task_id")), uuid_text(raw.get("trace_id"))
    status = _enum(raw.get("status"), STATUSES)
    timestamp = time_text(raw.get("created_at"))
    if task_id is None or trace_id is None or status is None or timestamp is None:
        raise ValueError("Trace metadata is invalid")
    record = {"schema_version": SCHEMA_VERSION, "kind": kind, "task_id": task_id,
              "trace_id": trace_id, "created_at": timestamp, "status": status}
    for key in ("step_id", "confirmation_id"):
        value = uuid_text(raw.get(key))
        if value is not None:
            record[key] = value
    for key, allowed in (("capability", CAPABILITIES), ("selected_method", METHODS),
                         ("selected_adapter", ADAPTERS), ("policy_version", POLICIES), ("error_code", ERRORS)):
        value = _enum(raw.get(key), allowed)
        if value is not None:
            record[key] = value
    for key in ("elapsed_ms", "duration_ms"):
        value = _duration(raw.get(key))
        if value is not None:
            record[key] = value
    if type(raw.get("simulated")) is bool:
        record["simulated"] = raw["simulated"]
    if kind == "event" and isinstance(raw.get("candidates"), list):
        candidates = []
        for item in raw["candidates"][:16]:
            if not isinstance(item, dict):
                continue
            adapter = _enum(item.get("adapter_id"), ADAPTERS)
            method = _enum(item.get("method"), METHODS)
            reason = _enum(item.get("reason"), REASONS)
            if adapter is None or method is None or reason is None or type(item.get("eligible")) is not bool:
                continue
            candidate = {"adapter_id": adapter, "method": method, "reason": reason, "eligible": item["eligible"]}
            if type(item.get("priority")) is int and 0 <= item["priority"] <= 100:
                candidate["priority"] = item["priority"]
            candidates.append(candidate)
        record["candidates"] = candidates
    if kind == "task_result":
        # Reader reuses this projection on stored data; never accept the full evidence object.
        diagnostics = _safe_diagnostics(raw.get("evidence", raw.get("diagnostics")))
        if diagnostics:
            record["diagnostics"] = diagnostics
    return record
