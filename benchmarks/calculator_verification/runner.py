"""Run the fixed synthetic oracle; write unique redacted JSON and Markdown."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
from uuid import uuid4
from elvion.calculator_verification import CalculatorVerificationResult, verify_result_transition
from .cases import CASES, NOW

OUTPUT = Path('artifacts/benchmarks/calculator-verification')


def score(*, verifier=verify_result_transition, cases=CASES):
    counts = Counter()
    rows = []
    for case in cases:
        try:
            result = verifier(case.before, case.after, case.expectation, now_ns=case.now_ns)
            if type(result) is not CalculatorVerificationResult or result.status not in ('verified','not_verified','unknown','error'):
                raise ValueError
            actual = result.status
            actions = result.actions
            if (type(actions) is not int or actions != 0 or result.authority_granted is not False or
                    result.action_causality_proven is not False):
                actual, actions = 'error', 1
        except Exception:
            actual, actions = 'error', 0
        passed = actual == case.expected and actions == 0
        counts[actual] += 1
        counts['passed' if passed else 'failed'] += 1
        counts['actions'] += actions
        if actual == 'verified' and case.expected != 'verified': counts['false_verified'] += 1
        if actual == 'not_verified' and case.expected == 'verified': counts['false_not_verified'] += 1
        if actual == 'unknown' and case.expected == 'verified': counts['false_unknown'] += 1
        rows.append({'name':case.name,'expected':case.expected,'actual':actual,'passed':passed})
    return {'synthetic_only':True,'observations':len(cases),
            **{k:counts[k] for k in ('passed','failed','verified','not_verified','unknown','error',
                                     'false_verified','false_not_verified','false_unknown','actions')},
            'rows':rows}


def main():
    report=score()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    stem=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex[:8]
    json_path,md_path=OUTPUT/(stem+'.json'),OUTPUT/(stem+'.md')
    with json_path.open('x') as f: json.dump(report,f,indent=2);f.write('\n')
    lines=['# Calculator verification synthetic benchmark','','Synthetic only; actions: 0.','',
           f"Observations: {report['observations']}; passed: {report['passed']}; failed: {report['failed']}.",
           f"False verified: {report['false_verified']}; false not verified: {report['false_not_verified']}; false unknown: {report['false_unknown']}.",
           '', '| Case | Expected | Actual | Pass |','| --- | --- | --- | --- |']
    lines += [f"| {r['name']} | {r['expected']} | {r['actual']} | {r['passed']} |" for r in report['rows']]
    with md_path.open('x') as f: f.write('\n'.join(lines)+'\n')
    print(json.dumps({'json':str(json_path),'markdown':str(md_path),
                      'observations':report['observations'],'failed':report['failed']}))
    return 0 if report['failed']==0 else 1

if __name__=='__main__': raise SystemExit(main())
