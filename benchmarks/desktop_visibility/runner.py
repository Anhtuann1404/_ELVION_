"""Synthetic-only scorer; no desktop probe, action or model."""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from elvion.desktop_visibility import evaluate_visibility

from .cases import CASES, check_cases


def score_cases(cases=CASES, *, evaluator=evaluate_visibility):
    check_cases(cases)
    rows = []
    for case in cases:
        try:
            result = evaluator(case.evidence, now_ns=case.now_ns, max_age_ms=case.max_age_ms)
            actual = result.status
            # A forged visible result with the wrong binding is not a hit.
            binding_ok = (result.snapshot_id == case.evidence.snapshot_id and
                          result.reference_id == case.evidence.reference_id and
                          result.target_node_id == case.evidence.target_node_id and
                          result.sampled_visibility_verified is True and
                          result.whole_target_visibility_verified is False and
                          result.freshness_for_execution is False)
        except Exception:
            actual, binding_ok = 'error', False
        if actual == 'visible':
            verdict = ('positive_hit' if case.expected_status == 'visible' and binding_ok else
                       'false_visible' if case.expected_status != 'visible' else 'wrong_binding')
        elif actual == 'blocked' and case.expected_status != 'blocked':
            verdict = 'false_blocked'
        elif actual == case.expected_status:
            verdict = 'correct_' + actual
        elif actual == 'unknown':
            verdict = 'wrong_unknown'
        elif actual == 'error':
            verdict = 'error'
        else:
            verdict = 'wrong_status'
        rows.append({'case_id': case.id, 'group': case.group,
                     'expected_status': case.expected_status, 'actual_status': actual,
                     'verdict': verdict})
    counts = Counter(row['verdict'] for row in rows)
    accuracy = defaultdict(lambda: {'passed': 0, 'total': 0})
    for row in rows:
        entry = accuracy[row['expected_status']]
        entry['total'] += 1
        entry['passed'] += row['verdict'] in {'positive_hit', 'correct_blocked',
                                             'correct_unknown', 'correct_error'}
    correct = sum(counts[k] for k in ('positive_hit', 'correct_blocked',
                                      'correct_unknown', 'correct_error'))
    return {'synthetic_only': True, 'actions': 0, 'observations': len(rows),
            'correct': correct, 'positive_hits': counts['positive_hit'],
            'false_visible': counts['false_visible'] + counts['wrong_binding'],
            'false_blocked': counts['false_blocked'],
            'unknown_results': sum(row['actual_status'] == 'unknown' for row in rows),
            'unexpected_errors': counts['error'],
            'accuracy_by_expected_status': dict(sorted(accuracy.items())),
            'verdicts': dict(sorted(counts.items())), 'rows': rows}


def _write(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(text)


def main():
    report = score_cases()
    directory = Path(__file__).resolve().parents[2] / 'artifacts/benchmarks/desktop-visibility'
    directory.mkdir(parents=True, exist_ok=True)
    stem = 'desktop-visibility-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
    json_path, md_path = directory / f'{stem}.json', directory / f'{stem}.md'
    _write(json_path, json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = ['# Desktop visibility synthetic benchmark', '',
             f"- Correct: {report['correct']}/{report['observations']}",
             f"- Positive sampled hits: {report['positive_hits']}",
             f"- False visible: {report['false_visible']}",
             f"- False blocked: {report['false_blocked']}",
             f"- Unknown results: {report['unknown_results']}",
             f"- Unexpected errors: {report['unexpected_errors']}",
             '- Synthetic only; actions: 0', '', '## Accuracy by expected status', '']
    for status, entry in report['accuracy_by_expected_status'].items():
        lines.append(f"- {status}: {entry['passed']}/{entry['total']}")
    _write(md_path, '\n'.join(lines) + '\n')
    print(json.dumps({'json': str(json_path), 'markdown': str(md_path),
                      'observations': report['observations'], 'correct': report['correct'],
                      'false_visible': report['false_visible']}))
    return 0 if report['correct'] == report['observations'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
