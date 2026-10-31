"""Explicitly confirmed single AXPress smoke; never launch or clear Calculator."""
import argparse
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from elvion.core.contracts import ConfirmationResponse,TaskRequest
from elvion.desktop_action.backend import CalculatorPressBackend
from elvion.desktop_action.contracts import CAPABILITY,READ_GRANT,make_intent
from elvion.desktop_action.discovery import discover_target
from elvion.desktop_action.journal import AttemptJournal
from elvion.desktop_action.runtime import build_runtime
from elvion.storage.traces import TraceStore
from elvion.verification.calculator import CalculatorResultReader

ROOT=Path(__file__).resolve().parents[1]


def main(argv=None, *, prompt=input):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grant-press7',action='store_true')
    parser.add_argument('--include-current-entry',action='store_true')
    parser.add_argument('--result-role')
    parser.add_argument('--result-identifier')
    parser.add_argument('--parent-role')
    parser.add_argument('--parent-identifier')
    args=parser.parse_args(argv)
    def stop(reason):
        print(json.dumps({'status':'blocked','reason':reason,'actions':0}))
        return 2
    # Both flags are independent of the per-action y/N confirmation.
    if not args.grant_press7 or not args.include_current_entry:
        return stop('EXPLICIT_ACTION_AND_RESULT_GRANTS_REQUIRED')
    supplied=(args.result_role,args.result_identifier,args.parent_role,args.parent_identifier)
    if any(v is not None for v in supplied) and any(v is None for v in supplied):
        return stop('VERIFIER_PROFILE_REQUIRED')
    try:
        from elvion.calculator_verification import ResultRegionProfile
        from elvion.calculator_verification.verifier import standard_entry_profile
        profile=(standard_entry_profile() if all(v is None for v in supplied) else
            ResultRegionProfile(*supplied,reviewed=True,surface='current_entry'))
        reader=CalculatorResultReader(profile)
        reader.prepare()  # Build/read support only; no result value collected here.
        backend=CalculatorPressBackend()
        backend.prepare()
        target=discover_target()
        request=TaskRequest(utterance='Nhấn nút 7 trong Calculator, kiểm tra 0 → 7')
        intent=make_intent(request,target)
        grants=frozenset((CAPABILITY,READ_GRANT))
        runtime,_=build_runtime(intent,backend=backend,reader=reader,
            journal=AttemptJournal(ROOT/'artifacts/desktop-action/attempts.sqlite3'),
            current_grants=lambda:grants,trace_store=TraceStore(ROOT/'artifacts/desktop-action'))
    except (ImportError,ValueError,OSError,TypeError,KeyError):
        return stop('CALCULATOR_ACTION_PREREQUISITES_UNAVAILABLE')
    def confirm(confirmation):
        print('Thao tác thật: nhấn nút 7 đúng một lần bằng AXPress trong Calculator.')
        print('Cậu tự đưa Calculator về 0 trước khi đồng ý. ELVION không tự xóa nội dung.')
        print('Đọc ô nhập số hiện tại trước/sau để kiểm tra 0 → 7. Không tự retry.')
        print('PID:',target['pid'])
        expiry=confirmation.expires_at.astimezone(ZoneInfo('Asia/Ho_Chi_Minh'))
        print('Hết hạn:',expiry.strftime('%H:%M:%S %d/%m/%Y'),'giờ VN')
        approved=prompt('Đồng ý? [y/N]: ').strip().lower()=='y'
        return ConfirmationResponse(confirmation_id=confirmation.confirmation_id,
            action_digest=confirmation.action_digest,approved=approved)
    report=runtime.run(request,grants,confirmation_handler=confirm)
    print(json.dumps({'status':report.status.value,'message':report.message,
        'error_code':report.error_code.value if report.error_code else None,
        'reason':report.evidence.get('reason'),
        'postcondition_verified':report.evidence.get('postcondition_verified',False),
        'task_id':str(report.task_id),'trace_id':str(report.trace_id),
        'trace_status':report.trace['status']},ensure_ascii=False))
    return 0 if report.status.value=='succeeded' else 1


if __name__=='__main__':
    raise SystemExit(main())
