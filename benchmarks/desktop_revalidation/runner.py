"""Run fixed synthetic oracle; write one unique JSON and Markdown report."""
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import json
from uuid import uuid4

from elvion.desktop_revalidation import RevalidationResult, evaluate_revalidation
from .cases import CASES, NOW

OUTPUT = Path('artifacts/benchmarks/desktop-revalidation')


def score(*, evaluator=evaluate_revalidation, cases=CASES):
    counts = Counter()
    rows = []
    for case in cases:
        try:
            result = evaluator(case.evidence, now_ns=NOW)
            if type(result) is not RevalidationResult or result.status not in ('ready','blocked','unknown','error'):
                raise ValueError('INVALID_RESULT')
            actual = result.status
            actions = result.actions
            if (type(actions) is not int or actions != 0 or result.authority_granted is not False or
                    result.whole_target_visibility_verified is not False or
                    result.freshness_for_execution is not False):
                actual = 'error'
                actions = 1
        except Exception:
            actual, actions = 'error', 0
        passed = actual == case.expected and actions == 0
        counts[actual] += 1
        counts['passed' if passed else 'failed'] += 1
        if actual == 'ready' and case.expected != 'ready': counts['false_ready'] += 1
        if actual == 'blocked' and case.expected != 'blocked': counts['false_blocked'] += 1
        if actual == 'unknown' and case.expected == 'ready': counts['false_unknown'] += 1
        counts['actions'] += actions
        rows.append({'name': case.name, 'expected': case.expected, 'actual': actual, 'passed': passed})
    return {'synthetic_only': True, 'observations': len(cases),
            **{key: counts[key] for key in ('passed','failed','ready','blocked','unknown','error',
                                              'false_ready','false_blocked','false_unknown','actions')},
            'rows': rows}


def main():
    report = score()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stem = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid4().hex[:8]
    json_path, md_path = OUTPUT / (stem + '.json'), OUTPUT / (stem + '.md')
    json_path.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Desktop revalidation synthetic benchmark', '',
             'Synthetic only. Actions: 0.', '',
             f"Observations: {report['observations']}; passed: {report['passed']}; failed: {report['failed']}.",
             f"False ready: {report['false_ready']}; false blocked: {report['false_blocked']}; false unknown: {report['false_unknown']}.",
             '', '| Case | Expected | Actual | Pass |', '| --- | --- | --- | --- |']
    lines += [f"| {r['name']} | {r['expected']} | {r['actual']} | {r['passed']} |" for r in report['rows']]
    md_path.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'json': str(json_path), 'markdown': str(md_path),
                      'observations': report['observations'], 'failed': report['failed']}))
    return 0 if report['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
