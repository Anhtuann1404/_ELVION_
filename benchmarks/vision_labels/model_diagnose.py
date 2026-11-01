"""Opt-in model/OCR diagnostics for one authored synthetic fixture, without actions."""
import argparse
from pathlib import Path
from uuid import uuid4
import json
from time import monotonic

from benchmarks.vision_labels.cases import CASES
from benchmarks.vision_labels.runner import capture_case
from elvion.browser.session import BrowserSession
from elvion.vision.label_candidates import OCRLabelGrounder
from elvion.vision.ocr import AppleVisionOCR
from elvion.vision.ollama import OllamaVisionProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    from benchmarks.browser_vision.challenge import CASES as BROWSER_CASES
    select = parser.add_mutually_exclusive_group(required=True)
    select.add_argument('--case', choices=[case.id for case in CASES])
    select.add_argument('--browser-case', choices=[case.id for case in BROWSER_CASES])
    args = parser.parse_args()
    case = next(case for case in (BROWSER_CASES if args.browser_case else CASES)
                if case.id == (args.browser_case or args.case))
    rows = []
    provider = OllamaVisionProvider(model='qwen3.5:4b', max_tokens=512)
    complete = provider.complete
    def observed(**kwargs):
        raw = complete(**kwargs)
        # Raw responses are permitted here ONLY for the fixed synthetic fixture.
        row = {'phase':kwargs['role'], 'response':json.loads(raw)}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        return raw
    provider.complete = observed
    session = BrowserSession(headless=True)
    try:
        session.start()
        session.context.route('**/*', lambda route: route.abort())
        if args.browser_case:
            from benchmarks.browser_vision.cases import render
            from elvion.browser.contracts import VisionFrame
            session.page.set_content(render(case), wait_until='load')
            png = session.page.screenshot(type='png', full_page=False, caret='hide')
            frame = VisionFrame(uuid4().hex, uuid4().hex, 1, png, 1280, 800, monotonic())
        else:
            frame = capture_case(session, case, 1).frame
        primary = AppleVisionOCR(profile='upscale2x-v2')
        primary.prepare()
        grounder = OCRLabelGrounder(provider, primary)
        result = grounder.locate(frame, target=case.target, role=case.role)
        report = {'case_id':case.id, 'synthetic_only':True, 'actions':0,
                  'status':result.status, 'reason':result.reason,
                  'diagnostics':grounder.last_diagnostics, 'model_calls':rows}
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except Exception as error:
        print(f'Diagnostic blocked: {type(error).__name__}; no quality score.')
        return 2
    finally:
        session.close()
    directory = Path('artifacts/benchmarks/vision-labels/model-diagnostics')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'label-model-{uuid4().hex[:12]}.json'
    with path.open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    path.chmod(0o600)
    print(f'JSON: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
