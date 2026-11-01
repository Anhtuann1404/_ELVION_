"""Read-only OCR diagnostics for saved synthetic browser challenge failures."""
import argparse
import json
from pathlib import Path
import struct
from time import monotonic

from benchmarks.browser_vision.challenge import CASES as CHALLENGE_CASES
from benchmarks.vision.ocr_diagnose import save
from elvion.browser.contracts import VisionFrame
from elvion.vision.ocr import AppleVisionOCR, OCR_PROFILES, normalized_label


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text())
    if (report['config'].get('synthetic_only') is not True or
            report['config'].get('suite') != 'challenge'):
        parser.error('Choose a synthetic challenge report')
    cases = {case.id: case for case in CHALLENGE_CASES}
    rows = []
    backends = {profile: AppleVisionOCR(profile=profile) for profile in OCR_PROFILES}
    try:
        for backend in backends.values():
            backend.prepare()
        seen = set()
        for result in report['results']:
            if result['pass'] or result['case_id'] in seen:
                continue
            case = cases[result['case_id']]
            name = result['synthetic_failure_frame']
            if Path(name).name != name or not name.endswith('.png'):
                raise ValueError('Invalid synthetic frame filename')
            png = (args.report.parent / name).read_bytes()
            width, height = struct.unpack('>II', png[16:24])
            frame = VisionFrame('diagnostic', 'synthetic-challenge', 0, png,
                                width, height, monotonic())
            seen.add(case.id)
            for profile, backend in backends.items():
                lines = backend.recognize(frame)
                texts = [line.text for line in lines]
                row = {'case_id': case.id, 'profile': profile, 'target': case.target,
                       'texts': texts, 'exact_matches': sum(
                           normalized_label(text) == normalized_label(case.target) for text in texts)}
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    except Exception as error:
        parser.exit(2, f'OCR diagnostic unavailable: {type(error).__name__}; no quality result.\n')
    output = save({'synthetic_only': True, 'actions': 0, 'model_called': False,
                   'source_report': args.report.name, 'rows': rows},
                  args.report.parent / 'ocr-diagnostics')
    print(f'JSON: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
