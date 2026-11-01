"""Opt-in raw OCR of four known synthetic label fixtures; no model or actions."""
import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from benchmarks.vision_labels.cases import CASES, manifest_sha256
from benchmarks.vision_labels.runner import capture_case
from elvion.browser.session import BrowserSession
from elvion.vision.ocr import AppleVisionOCR, OCR_PROFILES


def main():
    ids = {'vl_h09_multiple_terminal','vl_h10_vietnamese',
           'vl_h11_plain_and_period','vl_h12_period_and_plain'}
    session = BrowserSession(headless=True)
    rows = []
    try:
        session.start()
        session.context.route('**/*', lambda route: route.abort())
        backends = {profile: AppleVisionOCR(profile=profile) for profile in OCR_PROFILES}
        for backend in backends.values():
            backend.prepare()
        for revision, case in enumerate((c for c in CASES if c.id in ids), 1):
            frame = capture_case(session, case, revision).frame
            for profile, backend in backends.items():
                row = {'case_id':case.id, 'profile':profile, 'target':case.target,
                       'lines':[asdict(line) for line in backend.recognize(frame)]}
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    except Exception as error:
        print(f'Diagnostic blocked: {type(error).__name__}; no quality score.')
        return 2
    finally:
        session.close()
    directory = Path('artifacts/benchmarks/vision-labels/ocr-diagnostics')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'ocr-labels-{uuid4().hex[:12]}.json'
    with path.open('x') as stream:
        json.dump({'synthetic_only':True, 'model_called':False, 'actions':0,
                   'manifest_sha256':manifest_sha256(), 'rows':rows}, stream,
                  ensure_ascii=False, indent=2)
    path.chmod(0o600)
    print(f'JSON: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
