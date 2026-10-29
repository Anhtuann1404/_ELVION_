"""Explicit CLI modes: fake note demo, or allowlisted real macOS app control."""
import argparse
from functools import partial
import json
import sys

from elvion import __version__
from elvion.core.contracts import (
    ConfirmationRequest, ConfirmationResponse, ContractError, TaskRequest, TaskStatus,
)
from elvion.core.orchestrator import DemoOrchestrator
from elvion.core.runtime import AppOrchestrator, NotesOrchestrator
from elvion.core.notes import NotesScope
from elvion.storage.traces import TraceStorageError, TraceStore


def confirm_in_cli(request: ConfirmationRequest, *, simulated: bool = True) -> ConfirmationResponse:
    # Keep stdout machine-readable; JSON escaping protects the terminal preview.
    label = "Confirm simulated action (no real app is affected):" if simulated else "Confirm real macOS action:"
    print(label, file=sys.stderr)
    print(json.dumps(request.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
    print("Approve? [y/N]: ", end="", file=sys.stderr, flush=True)
    reply = sys.stdin.readline()
    return ConfirmationResponse(confirmation_id=request.confirmation_id,
                                action_digest=request.action_digest,
                                approved=reply.strip().casefold() in {"y", "yes", "có"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="elvion", description="ELVION — local-first agent prototype")
    parser.add_argument("--version", action="version", version=f"ELVION {__version__}")
    commands = parser.add_subparsers(dest="command")
    demo = commands.add_parser("demo", help="Create a fake note in memory; no real apps or model calls")
    demo.add_argument("utterance", help='Example: "Tạo ghi chú Ôn AI"')
    demo.add_argument("--grant", action="append", choices=["note.create"], default=[],
                      help="Grant this demo capability for this invocation only")
    demo.add_argument("--disable-native", action="store_true", help="Simulate native unavailability")
    demo.add_argument("--confirm", action="store_true",
                      help="Require explicit approval after preview; capability grant is still required")
    live = commands.add_parser("run", help="Open allowlisted macOS app (real action, not simulation)")
    live.add_argument("utterance", help='Example: "Mở Máy tính"')
    live.add_argument("--grant", action="append", choices=["app.open"], default=[],
                      help="Grant app.open for this invocation only")
    live.add_argument("--confirm", action="store_true", help="Preview and confirm the real action")
    notes = commands.add_parser("notes", help="Create/find a real Apple Note in an explicit account / ELVION folder")
    notes.add_argument("utterance", help='Example: "Tạo ghi chú Ôn AI" or "Tìm ghi chú Ôn AI"')
    notes.add_argument("--account", required=True, help='Exact Notes account name, e.g. "On My Mac"; no default-account fallback')
    notes.add_argument("--grant", action="append", choices=["note.create", "note.find"], default=[])
    notes.add_argument("--confirm", action="store_true", help="Also confirm searches; creation always requires confirmation")
    for command in (demo, live, notes):
        command.add_argument("--data-dir", help="Local ELVION data directory (traces are stored under traces/)")
        command.add_argument("--no-trace", action="store_true", help="Disable persistent trace for this invocation")
    traces = commands.add_parser("traces", help="Read sanitized local task history")
    trace_commands = traces.add_subparsers(dest="trace_command", required=True)
    trace_list = trace_commands.add_parser("list", help="List recent tasks")
    trace_list.add_argument("--limit", type=int, default=10)
    trace_show = trace_commands.add_parser("show", help="Read one trace by UUID")
    trace_show.add_argument("trace_id")
    for command in (trace_list, trace_show):
        command.add_argument("--data-dir", help="Local ELVION data directory")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "traces":
        store = TraceStore(args.data_dir)
        try:
            result = ({"traces": store.recent(args.limit)} if args.trace_command == "list"
                      else store.show(args.trace_id))
        except TraceStorageError as error:
            print(json.dumps({"error_code": error.code}))
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    trace_store = None if args.no_trace else TraceStore(args.data_dir)
    try:
        request = TaskRequest(utterance=args.utterance)
    except ContractError as exc:
        parser.error(str(exc))
    simulated = args.command == "demo"
    if simulated:
        agent = DemoOrchestrator(native_available=not args.disable_native, require_confirmation=args.confirm,
                                 trace_store=trace_store)
    elif args.command == "run":
        agent = AppOrchestrator(require_confirmation=args.confirm, trace_store=trace_store)
    else:
        try:
            scope = NotesScope(account=args.account)
        except ContractError as exc:
            parser.error(str(exc))
        agent = NotesOrchestrator(scope, require_confirmation=args.confirm, trace_store=trace_store)
    report = agent.run(
        request, grants=frozenset(args.grant),
        confirmation_handler=partial(confirm_in_cli, simulated=simulated) if args.confirm or args.command == "notes" else None,
    )
    if report.trace["status"] in {"partial", "failed"}:
        print(f"Trace persistence warning: {report.trace['error_code']}; task outcome is unchanged. "
              "Do not repeat an action just to restore its log.", file=sys.stderr)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if report.status == TaskStatus.SUCCEEDED else 1
