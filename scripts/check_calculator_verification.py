"""Read-only two-capture Calculator result smoke; user changes Calculator manually."""

import argparse
import json

from elvion.calculator_verification import (ResultRegionProfile, capture_calculator_result,
    capture_calculator_entry,CalculatorExpectation,diagnose_calculator_region, verify_result_transition)
from elvion.calculator_verification.verifier import _number,standard_entry_profile
from elvion.calculator_verification.formatting import numeric_format_summary
import time


def _summary(result):
    return {'status': result.status, 'reason': result.reason,
            'observed_matches_expected': result.observed_matches_expected,
            'transition_observed': result.transition_observed,
            'actions': result.actions, 'authority_granted': result.authority_granted,
            'action_causality_proven': result.action_causality_proven}


def main(argv=None, *, capture=capture_calculator_result, diagnose=diagnose_calculator_region,
         entry_capture=capture_calculator_entry,prompt=input, clock=time.monotonic_ns):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-result', action='store_true')
    parser.add_argument('--include-current-entry', action='store_true')
    parser.add_argument('--diagnose-region', action='store_true')
    parser.add_argument('--diagnose-format',action='store_true')
    parser.add_argument('--result-role')
    parser.add_argument('--result-identifier')
    parser.add_argument('--parent-role')
    parser.add_argument('--parent-identifier')
    args = parser.parse_args(argv)
    if args.diagnose_region:
        print(json.dumps(diagnose(), ensure_ascii=False))
        return 0
    if args.include_result and args.include_current_entry:
        print(json.dumps({'status':'error','reason':'AMBIGUOUS_SURFACE_OPT_IN','actions':0}))
        return 2
    if not args.include_result and not args.include_current_entry:
        print(json.dumps({'status':'unknown','reason':'RESULT_OPT_IN_REQUIRED','actions':0,
                          'authority_granted':False,'action_causality_proven':False}))
        return 2
    entry=args.include_current_entry
    if entry and any(v is not None for v in (args.result_role,args.result_identifier,args.parent_role,args.parent_identifier)):
        print(json.dumps({'status':'error','reason':'ENTRY_PROFILE_FIXED','actions':0}))
        return 2
    if not entry and any(v is None for v in (args.result_role,args.result_identifier,args.parent_role,args.parent_identifier)):
        print(json.dumps({'status':'unknown','reason':'REGION_PROFILE_REQUIRED','actions':0,
                          'authority_granted':False,'action_causality_proven':False}))
        return 2
    profile = standard_entry_profile() if entry else ResultRegionProfile(args.result_role,args.result_identifier,args.parent_role,
                                  args.parent_identifier, reviewed=True)
    def observe():
        return entry_capture(include_current_entry=True) if entry else capture(include_result=True,profile=profile)
    if args.diagnose_format:
        observation=observe()
        info={'status':'diagnostic' if observation.status=='observed' else observation.status,
              'reason':'FORMAT_ONLY' if observation.status=='observed' else observation.reason,
              'surface':profile.surface,'actions':0,'authority_granted':False,'action_causality_proven':False}
        if observation.status=='observed':info['format']=numeric_format_summary(observation.result_text)
        print(json.dumps(info))
        return 0 if observation.status=='observed' else 1
    if entry:
        print('Chỉ đọc ô nhập số hiện tại; không đọc history hoặc coi đây là kết quả phép tính.')
    print('Read-only demo. Set Calculator to 0 manually; this script will not change it.')
    prompt('Press Enter to capture the before result...')
    before = observe()
    if before.status != 'observed':
        print(json.dumps({'status':before.status,'reason':before.reason,'actions':0,
                          'authority_granted':False,'action_causality_proven':False}))
        return 1
    if _number(before.result_text) != '0':
        reason = 'BEFORE_VALUE_NOT_ZERO' if _number(before.result_text) is not None else 'UNSUPPORTED_RESULT_FORMAT'
        status = 'not_verified' if reason == 'BEFORE_VALUE_NOT_ZERO' else 'unknown'
        print(json.dumps({'status':status,'reason':reason,'actions':0,
                          'authority_granted':False,'action_causality_proven':False,
                          'stage':'before_capture',
                          **({'format':numeric_format_summary(before.result_text)}
                             if reason=='UNSUPPORTED_RESULT_FORMAT' else {})}))
        return 1
    print('Now press 7 manually in Calculator. This script will only observe the result.')
    prompt('Press Enter to capture the after result...')
    after = observe()
    result = verify_result_transition(before, after,CalculatorExpectation(surface=profile.surface),now_ns=clock())
    info=_summary(result)|{'surface':profile.surface}
    if result.reason=='UNSUPPORTED_RESULT_FORMAT':
        info.update(stage='transition',format_before=numeric_format_summary(before.result_text),
                    format_after=numeric_format_summary(after.result_text))
    print(json.dumps(info))
    return 0 if result.status == 'verified' else 1


if __name__ == '__main__':
    raise SystemExit(main())
