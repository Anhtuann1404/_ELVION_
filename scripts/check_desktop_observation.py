"""Read-only Calculator AX smoke. Output is summary unless explicitly saved."""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path

from elvion.desktop_observation import observe_app


def main(argv=None):
    parser = argparse.ArgumentParser(description='Observe an already-running Calculator via AX; no actions.')
    parser.add_argument('--include-labels', action='store_true',
                        help='Read visible AX title/description strings; may contain private text.')
    parser.add_argument('--write-snapshot', type=Path, metavar='PATH',
                        help='Explicitly save the snapshot (AX metadata and optional labels) to a new 0600 file.')
    args = parser.parse_args(argv)
    result = observe_app('com.apple.calculator', include_labels=args.include_labels)
    print(json.dumps({'status': result.status, 'reason': result.reason,
                      'nodes': len(result.snapshot.elements) if result.snapshot else 0,
                      'truncated': result.snapshot.truncated if result.snapshot else False}))
    if args.write_snapshot and result.snapshot:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(args.write_snapshot, flags, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(asdict(result.snapshot), out, ensure_ascii=False, indent=2)
            out.write('\n')
    return 0 if result.status == 'observed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
