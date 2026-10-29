"""Run the remaining app.open checks in the user's desktop session; never quit apps."""
import json

from elvion.adapters.macos_apps import BackendError, MacOSAppBackend
from elvion.core.app_catalog import CALCULATOR_BUNDLE_ID
from elvion.core.contracts import ConfirmationResponse, ErrorCode, TaskRequest, TaskStatus
from elvion.core.runtime import AppOrchestrator


def main() -> int:
    checks = []
    request = TaskRequest(utterance="Mở Máy tính")
    denied = AppOrchestrator().run(request)
    denied_ok = (denied.error_code == ErrorCode.PERMISSION_DENIED
                 and not any(event["status"] == "executing" for event in denied.events))
    checks.append({"name": "missing_grant", "status": "pass" if denied_ok else "fail"})

    def decline(confirmation):
        return ConfirmationResponse(confirmation_id=confirmation.confirmation_id,
                                    action_digest=confirmation.action_digest, approved=False)

    declined = AppOrchestrator(require_confirmation=True).run(
        TaskRequest(utterance="Mở Máy tính"), frozenset({"app.open"}), confirmation_handler=decline)
    unavailable = declined.error_code in {ErrorCode.UNSUPPORTED, ErrorCode.TARGET_NOT_FOUND}
    checks.append({"name": "declined_confirmation", "status": "skip" if unavailable else
                   "pass" if declined.status == TaskStatus.CANCELLED and not any(
                       event["status"] == "executing" for event in declined.events) else "fail"})

    try:
        state = MacOSAppBackend().state(CALCULATOR_BUNDLE_ID)
    except BackendError as error:
        checks.append({"name": "already_running", "status": "skip", "reason": error.code.value})
    else:
        if not state.running:
            checks.append({"name": "already_running", "status": "skip",
                           "reason": "Calculator is not visible as running to this process; open it and rerun in desktop Terminal"})
        else:
            report = AppOrchestrator().run(TaskRequest(utterance="Mở Máy tính"), frozenset({"app.open"}))
            checks.append({"name": "already_running", "status": "pass" if (
                report.status == TaskStatus.SUCCEEDED and report.evidence.get("already_running") is True
                and report.evidence.get("postcondition_verified") is True) else "fail",
                "task_id": str(report.task_id), "trace_id": str(report.trace_id)})
    result = "fail" if any(item["status"] == "fail" for item in checks) else (
        "incomplete" if any(item["status"] == "skip" for item in checks) else "pass")
    print(json.dumps({"result": result, "checks": checks}, ensure_ascii=False, indent=2))
    return {"pass": 0, "fail": 1, "incomplete": 2}[result]


if __name__ == "__main__":
    raise SystemExit(main())
