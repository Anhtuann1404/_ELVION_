"""Opt-in, read-only Calculator button targeting demo."""

import argparse
import json

from elvion.desktop_observation import observe_app
from elvion.desktop_targeting import locate_control, evidence_summary


def main(argv=None, *, observer=observe_app, locator=locate_control):
    parser = argparse.ArgumentParser(description='Locate a labelled Calculator button in one AX snapshot.')
    parser.add_argument('--label', required=True, help='Exact visible AX button label to seek.')
    parser.add_argument('--include-labels', action='store_true',
                        help='Opt in to reading AX title/description; may contain private text.')
    parser.add_argument('--diagnose-evidence',action='store_true',
                        help='Explain incomplete evidence using counts and structural IDs; no label dump.')
    parser.add_argument('--scope',choices=['all-buttons','calculator-content'],default='all-buttons',
                        help='Content scope excludes only verified direct AXWindow management buttons.')
    args = parser.parse_args(argv)
    if not args.include_labels:
        print(json.dumps({'status': 'unavailable', 'reason': 'LABEL_OPT_IN_REQUIRED',
                          'hint': 'Pass --include-labels to read AX labels explicitly.'}))
        return 2
    observed = observer('com.apple.calculator', include_labels=True)
    if observed.status != 'observed' or observed.snapshot is None:
        print(json.dumps({'status': observed.status, 'reason': observed.reason,
                          'snapshot_id': None, 'candidate_count': 0}))
        return 2
    scope=args.scope.replace('-','_')
    result = (locator(observed.snapshot,label=args.label,scope=scope) if scope!='all_buttons'
              else locator(observed.snapshot,label=args.label))
    summary={'status': result.status, 'reason': result.reason,
                      'snapshot_id': result.snapshot_id, 'node_id': result.node_id,
                      'role': result.role, 'enabled': result.enabled, 'bbox': result.bbox,
                      'age_ms': result.age_ms, 'candidate_count': result.candidate_count,'target_scope':result.scope}
    if args.diagnose_evidence and result.reason not in ('INVALID_SNAPSHOT','UNSUPPORTED_REQUEST'):
        summary['evidence_diagnostic']=evidence_summary(observed.snapshot,label=args.label,scope=scope)
    print(json.dumps(summary))
    return 0 if result.status == 'found' else 1


if __name__ == '__main__':
    raise SystemExit(main())
