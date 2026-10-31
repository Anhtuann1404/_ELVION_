"""Synthetic-only AX targeting scorer. No Calculator, AX backend or model."""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from elvion.desktop_targeting import locate_control

from .cases import CASES, check_cases


def score_cases(cases=CASES, *, locator=locate_control):
    check_cases(cases)
    rows = []
    for case in cases:
        try:
            result = locator(case.ax_snapshot, label=case.label,
                             now_ns=case.now_ns, max_age_ms=case.max_age_ms)
            actual, node_id = result.status, result.node_id
        except Exception:
            actual, node_id = 'error', None
        if actual == 'found' and case.expected_status == 'found':
            verdict = 'correct_found' if node_id == case.expected_node_id else 'wrong_target'
        elif actual == 'found':
            verdict = 'false_acceptance'
        elif case.expected_status == 'found':
            verdict = 'false_rejection' if actual != 'error' else 'error'
        elif actual == case.expected_status:
            verdict = 'correct_rejection'
        elif actual == 'error':
            verdict = 'error'
        else:
            verdict = 'wrong_rejection'
        rows.append({'case_id': case.id, 'group': case.group, 'expected_status': case.expected_status,
                     'expected_node_id': case.expected_node_id, 'actual_status': actual,
                     'actual_node_id': node_id if actual == 'found' else None, 'verdict': verdict})
    counts = Counter(row['verdict'] for row in rows)
    per_status = defaultdict(lambda: {'passed': 0, 'total': 0})
    for row in rows:
        entry = per_status[row['expected_status']]
        entry['total'] += 1
        entry['passed'] += row['verdict'].startswith('correct_')
    return {'synthetic_only': True, 'actions': 0, 'observations': len(rows),
            'correct': counts['correct_found'] + counts['correct_rejection'],
            'positive_hits': counts['correct_found'],
            'correct_rejections': counts['correct_rejection'],
            'false_acceptances': counts['false_acceptance'],
            'wrong_targets': counts['wrong_target'],
            'false_rejections': counts['false_rejection'],
            'errors': counts['error'],
            'accuracy_by_expected_status': dict(sorted(per_status.items())),
            'verdicts': dict(sorted(counts.items())), 'rows': rows}


def _write_new(path: Path, content: str):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(content)


def main():
    report = score_cases()
    directory = Path(__file__).resolve().parents[2] / 'artifacts/benchmarks/desktop-targeting'
    directory.mkdir(parents=True, exist_ok=True)
    stem = 'desktop-targeting-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
    json_path, md_path = directory / f'{stem}.json', directory / f'{stem}.md'
    _write_new(json_path, json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = ['# Desktop targeting synthetic benchmark', '',
             f"- Observations: {report['observations']}",
             f"- Correct: {report['correct']}/{report['observations']}",
             f"- Positive target hits: {report['positive_hits']}",
             f"- Correct refusals/errors on authored negative cases: {report['correct_rejections']}",
             f"- False acceptances: {report['false_acceptances']}",
             f"- Wrong targets: {report['wrong_targets']}",
             f"- False rejections: {report['false_rejections']}",
             f"- Unexpected errors: {report['errors']}",
             '- Synthetic only; actions: 0', '', '## By expected status', '']
    for status, count in report['accuracy_by_expected_status'].items():
        lines.append(f"- {status}: {count['passed']}/{count['total']}")
    _write_new(md_path, '\n'.join(lines) + '\n')
    print(json.dumps({'json': str(json_path), 'markdown': str(md_path),
                      'observations': report['observations'],
                      'correct': report['correct'],
                      'false_acceptances': report['false_acceptances']}))
    return 0 if report['correct'] == report['observations'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
