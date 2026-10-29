"""Apple Notes scripting bridge, confined to one explicit account and ELVION folder."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

from elvion.core.contracts import (
    ActionIntent, ActionResult, ActionStatus, AuthorizationToken, CapabilityDescriptor,
    ErrorCode, Method, Observation, ObservationRequest, ObservationStatus, ProbeResult,
)
from elvion.core.notes import NOTES_APP_ID, NOTES_FOLDER, NotesScope, valid_title

# User data arrives through stdin as JSON, never through code interpolation or shell argv.
_NOTES_SCRIPT = r'''
ObjC.import("Foundation");
function run() {
    var mutationStarted = false;
    function fail(code, reason) { throw {elvionCode: code, reason: reason}; }
    function assertUnexpired(payload) {
        if (typeof payload.expires_ms !== "number" || Date.now() >= payload.expires_ms) {
            fail("CONFIRMATION_EXPIRED", "AUTHORIZATION_EXPIRED");
        }
    }
    function onlyOne(objects, missingReason) {
        if (objects.length === 0) fail("TARGET_NOT_FOUND", missingReason);
        if (objects.length !== 1) fail("AMBIGUOUS_TARGET", "MULTIPLE_MATCHES");
        return objects[0];
    }
    function htmlEscape(text) {
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                   .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }
    function readMetadata(note, account, folder) {
        if (note.shared() || note.passwordProtected()) fail("PERMISSION_DENIED", "SHARED_OR_LOCKED_NOTE");
        if (note.container().id() !== folder.id()) fail("PERMISSION_DENIED", "NOTE_OUTSIDE_FOLDER");
        return {note_id: note.id(), title: note.name(), account: account.name(), folder: folder.name(),
                shared: false, locked: false};
    }
    try {
        var bytes = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile;
        var input = ObjC.unwrap($.NSString.alloc.initWithDataEncoding(bytes, $.NSUTF8StringEncoding));
        var payload = JSON.parse(input);
        if (["create", "find", "get"].indexOf(payload.operation) === -1 || payload.folder !== "ELVION"
                || typeof payload.account !== "string" || payload.account.length === 0) {
            fail("UNSUPPORTED", "INVALID_REQUEST");
        }
        if ((payload.operation === "create" || payload.operation === "find")
                && (typeof payload.title !== "string" || payload.title.trim().length === 0
                    || payload.title.length > 512 || /[\x00-\x1f\x7f]/.test(payload.title))) {
            fail("UNSUPPORTED", "INVALID_TITLE");
        }
        if (payload.operation === "get" && (typeof payload.note_id !== "string" || !payload.note_id)) {
            fail("UNSUPPORTED", "INVALID_NOTE_ID");
        }
        var app = Application("com.apple.Notes");
        var account = onlyOne(app.accounts.whose({name: payload.account})(), "ACCOUNT_NOT_FOUND");
        var folders = account.folders.whose({name: payload.folder})();
        if (folders.length > 1) fail("AMBIGUOUS_TARGET", "MULTIPLE_FOLDERS");
        var folder;
        if (folders.length === 0) {
            if (payload.operation !== "create") fail("TARGET_NOT_FOUND", "FOLDER_NOT_FOUND");
            assertUnexpired(payload);
            mutationStarted = true;
            folder = app.make({new: "folder", at: account, withProperties: {name: payload.folder}});
        } else {
            folder = folders[0];
        }
        if (folder.shared()) fail("PERMISSION_DENIED", "SHARED_FOLDER");
        var note;
        if (payload.operation === "create") {
            assertUnexpired(payload);
            mutationStarted = true;
            note = app.make({new: "note", at: folder,
                             withProperties: {body: "<div>" + htmlEscape(payload.title) + "</div>"}});
        } else if (payload.operation === "find") {
            note = onlyOne(folder.notes.whose({name: payload.title})(), "NOTE_NOT_FOUND");
        } else {
            note = onlyOne(folder.notes.whose({id: payload.note_id})(), "NOTE_NOT_FOUND");
        }
        return JSON.stringify({ok: true, data: readMetadata(note, account, folder)});
    } catch (error) {
        var nativeError = typeof error.number === "number" ? error.number : error.errorNumber;
        var code = error.elvionCode || (nativeError === -1743 ? "PERMISSION_DENIED" : "TRANSIENT_FAILURE");
        return JSON.stringify({ok: false, error_code: code,
                               reason: error.reason || (nativeError === -1743 ? "AUTOMATION_DENIED" : "AUTOMATION_FAILED"),
                               native_error: typeof nativeError === "number" ? nativeError : null,
                               external_effect_possible: mutationStarted});
    }
}
'''


class NotesBackendError(ValueError):
    def __init__(self, code: ErrorCode, reason: str, *, external_effect_possible: bool = False,
                 native_error: int | None = None):
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.native_error = native_error
        self.external_effect_possible = external_effect_possible


@dataclass(frozen=True)
class NoteMetadata:
    note_id: str
    title: str
    account: str
    folder: str
    shared: bool = False
    locked: bool = False

    def to_dict(self) -> dict:
        return {"note_id": self.note_id, "title": self.title, "account": self.account,
                "folder": self.folder, "shared": self.shared, "locked": self.locked}


class AppleNotesBackend:
    command_timeout = 15.0
    app_path = Path("/System/Applications/Notes.app")

    def __init__(self, *, runner=None):
        self.runner = runner if runner is not None else subprocess.run

    def check_available(self) -> None:
        # Pure filesystem probe: never launch Notes or request Automation permission here.
        if sys.platform != "darwin" or not os.access("/usr/bin/osascript", os.X_OK):
            raise NotesBackendError(ErrorCode.UNSUPPORTED, "MACOS_AUTOMATION_UNAVAILABLE")
        try:
            with (self.app_path / "Contents/Info.plist").open("rb") as stream:
                info = plistlib.load(stream)
            if not isinstance(info, dict) or info.get("CFBundleIdentifier") != NOTES_APP_ID:
                raise ValueError("Wrong bundle")
        except (OSError, ValueError, plistlib.InvalidFileException):
            raise NotesBackendError(ErrorCode.TARGET_NOT_FOUND, "NOTES_APP_NOT_FOUND") from None

    def _call(self, operation: str, scope: NotesScope, *, title: str | None = None,
              note_id: str | None = None, token: AuthorizationToken | None = None) -> NoteMetadata:
        self.check_available()
        if operation not in {"create", "find", "get"}:
            raise NotesBackendError(ErrorCode.UNSUPPORTED, "INVALID_OPERATION")
        if operation in {"create", "find"} and not valid_title(title):
            raise NotesBackendError(ErrorCode.UNSUPPORTED, "INVALID_TITLE")
        if operation == "get" and (not isinstance(note_id, str) or not note_id):
            raise NotesBackendError(ErrorCode.UNSUPPORTED, "INVALID_NOTE_ID")
        payload = {"operation": operation, "account": scope.account, "folder": NOTES_FOLDER}
        if title is not None:
            payload["title"] = title
        if note_id is not None:
            payload["note_id"] = note_id
        if operation == "create":
            if token is None:
                raise NotesBackendError(ErrorCode.PERMISSION_DENIED, "MISSING_AUTHORIZATION")
            payload["expires_ms"] = int(token.expires_at.timestamp() * 1000)
        writing = operation == "create"
        try:
            result = self.runner(["/usr/bin/osascript", "-l", "JavaScript", "-e", _NOTES_SCRIPT],
                                 input=json.dumps(payload, ensure_ascii=False), capture_output=True,
                                 text=True, timeout=self.command_timeout, check=False, shell=False)
        except PermissionError:
            raise NotesBackendError(ErrorCode.PERMISSION_DENIED, "AUTOMATION_DENIED") from None
        except FileNotFoundError:
            raise NotesBackendError(ErrorCode.UNSUPPORTED, "AUTOMATION_UNAVAILABLE") from None
        except (OSError, subprocess.TimeoutExpired):
            raise NotesBackendError(ErrorCode.TRANSIENT_FAILURE, "AUTOMATION_TIMEOUT_OR_FAILURE",
                                    external_effect_possible=writing) from None
        if result.returncode != 0:
            # Raw stderr is neither printed nor logged; it can contain private data.
            raise NotesBackendError(ErrorCode.TRANSIENT_FAILURE, "AUTOMATION_PROCESS_FAILED",
                                    external_effect_possible=writing)
        try:
            envelope = json.loads(result.stdout)
            if not isinstance(envelope, dict) or type(envelope.get("ok")) is not bool:
                raise ValueError("Invalid envelope")
            if not envelope["ok"]:
                code = ErrorCode(envelope.get("error_code"))
                possible = envelope.get("external_effect_possible")
                if type(possible) is not bool:
                    raise ValueError("Invalid effect flag")
                native_error = envelope.get("native_error")
                if native_error is not None and type(native_error) is not int:
                    raise ValueError("Invalid native error number")
                # Only accept fixed diagnostic labels from the embedded script.
                reason = envelope.get("reason")
                allowed = {"ACCOUNT_NOT_FOUND", "FOLDER_NOT_FOUND", "NOTE_NOT_FOUND", "MULTIPLE_MATCHES",
                           "MULTIPLE_FOLDERS", "SHARED_OR_LOCKED_NOTE", "SHARED_FOLDER", "NOTE_OUTSIDE_FOLDER",
                           "AUTOMATION_DENIED", "AUTOMATION_FAILED", "AUTHORIZATION_EXPIRED", "INVALID_REQUEST",
                           "INVALID_TITLE", "INVALID_NOTE_ID"}
                raise NotesBackendError(code, reason if reason in allowed else "AUTOMATION_FAILED",
                                        external_effect_possible=possible, native_error=native_error)
            data = envelope["data"]
            if (not isinstance(data, dict) or not isinstance(data.get("note_id"), str) or not data["note_id"]
                    or not valid_title(data.get("title")) or data.get("account") != scope.account
                    or data.get("folder") != NOTES_FOLDER or data.get("shared") is not False
                    or data.get("locked") is not False):
                raise ValueError("Invalid scoped metadata")
            return NoteMetadata(note_id=data["note_id"], title=data["title"], account=scope.account,
                                folder=NOTES_FOLDER)
        except NotesBackendError:
            raise
        except (ValueError, TypeError, KeyError):
            raise NotesBackendError(ErrorCode.VERIFICATION_FAILED, "INVALID_AUTOMATION_RESPONSE",
                                    external_effect_possible=writing) from None

    def create(self, scope: NotesScope, title: str, token: AuthorizationToken) -> NoteMetadata:
        return self._call("create", scope, title=title, token=token)

    def find(self, scope: NotesScope, title: str) -> NoteMetadata:
        return self._call("find", scope, title=title)

    def get(self, scope: NotesScope, note_id: str) -> NoteMetadata:
        return self._call("get", scope, note_id=note_id)


class AppleNotesAdapter:
    def __init__(self, scope: NotesScope, *, capability: str, backend: AppleNotesBackend | None = None):
        if capability not in {"note.create", "note.find"}:
            raise ValueError("Unsupported Notes capability")
        self.scope = scope
        self.capability = capability
        self.backend = backend if backend is not None else AppleNotesBackend()
        self._attempts: dict[str, tuple[str, ActionResult]] = {}

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(name=f"macos.notes.{self.capability}", platform="macos", app=NOTES_APP_ID,
                                    method=Method.NATIVE_API, required_permissions=(self.capability,),
                                    supported_actions=(self.capability,), can_verify=True,
                                    estimated_latency_ms=0, simulated=False)

    def supports(self, intent: ActionIntent) -> bool:
        kind = "note_exists" if self.capability == "note.create" else "note_found"
        return (intent.capability == self.capability and intent.target == self.scope.target
                and intent.arguments.keys() == {"title"} and valid_title(intent.arguments.get("title"))
                and intent.preconditions == () and intent.risk == "low"
                and intent.postcondition == {"kind": kind, "title": intent.arguments["title"]})

    def probe(self, intent: ActionIntent) -> ProbeResult:
        ready, supported, reason = False, self.supports(intent), "UNSUPPORTED"
        if supported:
            try:
                self.backend.check_available()
            except NotesBackendError as exc:
                reason = exc.code.value
            else:
                ready, reason = True, "NOTES_APP_AVAILABLE_AUTOMATION_NOT_YET_CHECKED"
        return ProbeResult(adapter_id=self.descriptor.name, method=Method.NATIVE_API,
                           supported=supported, prerequisites_met=ready, reason=reason)

    def execute(self, intent: ActionIntent, token: AuthorizationToken) -> ActionResult:
        if not token.permits(intent):
            return ActionResult(status=ActionStatus.FAILED, method=Method.NATIVE_API,
                                error_code=ErrorCode.PERMISSION_DENIED)
        if not self.supports(intent):
            return ActionResult(status=ActionStatus.FAILED, method=Method.NATIVE_API,
                                error_code=ErrorCode.UNSUPPORTED)
        creating = self.capability == "note.create"
        key = str(intent.idempotency_key)
        digest = intent.digest()
        if creating and key in self._attempts:
            previous_digest, previous = self._attempts[key]
            if digest != previous_digest:
                return ActionResult(status=ActionStatus.FAILED, method=Method.NATIVE_API,
                                    error_code=ErrorCode.PERMISSION_DENIED)
            return previous
        if creating:
            # Cache uncertain before the write: unexpected exceptions must not allow duplicate attempts.
            self._attempts[key] = (digest, ActionResult(status=ActionStatus.UNCERTAIN, method=Method.NATIVE_API,
                                  error_code=ErrorCode.UNCERTAIN_EXTERNAL_EFFECT, external_effect_possible=True))
        try:
            metadata = (self.backend.create(self.scope, intent.arguments["title"], token) if creating
                        else self.backend.find(self.scope, intent.arguments["title"]))
        except NotesBackendError as exc:
            evidence = {"reason": exc.reason}
            if exc.native_error is not None:
                evidence["native_error"] = exc.native_error
            result = ActionResult(status=ActionStatus.UNCERTAIN if exc.external_effect_possible else ActionStatus.FAILED,
                                  method=Method.NATIVE_API, error_code=exc.code,
                                  evidence=evidence, external_effect_possible=exc.external_effect_possible)
        else:
            result = ActionResult(status=ActionStatus.SUCCESS, method=Method.NATIVE_API,
                                  evidence={"note_id": metadata.note_id}, external_effect_possible=creating)
        if creating:
            self._attempts[key] = (digest, result)
        return result

    def observe(self, request: ObservationRequest) -> Observation:
        if request.app != NOTES_APP_ID or request.kind != "note":
            return Observation(status=ObservationStatus.UNAVAILABLE, error_code=ErrorCode.UNSUPPORTED)
        try:
            metadata = self.backend.get(self.scope, request.subject_id)
        except NotesBackendError as exc:
            return Observation(status=ObservationStatus.NOT_FOUND if exc.code == ErrorCode.TARGET_NOT_FOUND
                               else ObservationStatus.UNAVAILABLE, error_code=exc.code)
        return Observation(status=ObservationStatus.OBSERVED, data=metadata.to_dict())
