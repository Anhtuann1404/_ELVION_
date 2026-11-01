"""Opt-in real Chromium vision qualification on synthetic, network-blocked fixtures."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import time
from unittest.mock import patch
from uuid import uuid4

from benchmarks.browser_vision.cases import CASES, check_cases, render
from elvion.browser.controller import BrowserController
from elvion.browser.session import BrowserSession, BrowserError
from elvion.core.contracts import utc_now
from elvion.vision.ocr import AppleVisionOCR, OCRCandidateGrounder, OCRError
from elvion.vision.ollama import OllamaVisionProvider, VisionProviderError


class Clock:
    def __init__(self): self.expired = False
    def __call__(self): return time.monotonic() + (11 if self.expired else 0)


class ObservedGrounder:
    """Fixture-owned mutation happens AFTER real grounding, without changing its inputs."""
    def __init__(self, base, case, session, authority, clock):
        self.base, self.case, self.session = base, case, session
        self.authority, self.clock = authority, clock
        self.result = self.frame = None
        self.grounding_ms = self.frame_age_ms = None

    def locate(self, frame, *, target, role):
        self.frame = frame
        started = time.monotonic()
        self.result = self.base.locate(frame, target=target, role=role)
        self.grounding_ms = round((time.monotonic()-started)*1000,3)
        self.frame_age_ms = round((time.monotonic()-frame.captured_at)*1000,3)
        if self.result.status == 'found':
            if self.case.mutation == 'move':
                # No session.invalidate(): exercise a pixel change within the same page/revision.
                self.session.page.evaluate("document.getElementById('target').style.left='890px'")
            elif self.case.mutation == 'revoke':
                self.authority[0] = False
            elif self.case.mutation == 'expire':
                self.clock.expired = True
        return self.result


def assess(case, result, reason, attempts, state, diagnostics=None):
    """Independent postcondition oracle; failed inference cannot count as a guard pass."""
    if (type(attempts) is not int or attempts < 0 or type(state) is not dict or
            set(state) != {'clicks','target_clicks'} or
            any(type(value) is not int or value < 0 for value in state.values())):
        return False
    if case.expected == 'click':
        return (result is not None and result.status == 'found' and reason is None and
                attempts == 1 and state == {'clicks':1, 'target_clicks':1})
    if attempts != 0 or state != {'clicks':0, 'target_clicks':0} or result is None:
        return False
    if case.expected == 'abstain':
        expected_status = 'ambiguous' if case.kind == 'duplicate' else 'not_found'
        if result.status != expected_status or reason != 'WEB_VISION_ABSTAINED':
            return False
        if case.kind in {'heading','disabled','prose'} or (case.kind == 'input' and case.role != 'textbox'):
            # An OCR miss must not masquerade as successful semantic role verification.
            return (diagnostics or {}).get('decision_stage') == 'model_rejected_candidate'
        return True
    return result.status == 'found' and reason == 'WEB_STALE_OR_UNAUTHORIZED'


def run_case(case, base, *, headless=False):
    base.last_diagnostics = {}
    session = BrowserSession(headless=headless)
    authority, clock = [True], Clock()
    grounder = ObservedGrounder(base, case, session, authority, clock)
    attempts, reason, state = 0, None, None
    started = time.perf_counter()
    try:
        session.start()
        session.context.route('**/*', lambda route: route.abort())
        session.page.set_content(render(case))
        mouse = session.page.mouse
        original_click = mouse.click
        def counted_click(x, y):
            nonlocal attempts
            attempts += 1
            return original_click(x, y)
        controller = BrowserController(session, grounder=grounder, clock=clock)
        try:
            with patch.object(mouse, 'click', side_effect=counted_click):
                controller.click(target=case.target, role=case.role, locator=None,
                                 authorized=lambda:authority[0], mode='vision')
        except BrowserError as error:
            known = {'WEB_VISION_ABSTAINED','WEB_STALE_OR_UNAUTHORIZED','WEB_BOX_OUTSIDE_VIEWPORT',
                     'WEB_ACTION_DENIED','WEB_CLICK_UNCERTAIN','WEB_BUDGET_EXHAUSTED'}
            reason = str(error) if str(error) in known else 'DRIVER_ERROR'
        state = session.page.evaluate("({clicks:Number(document.body.dataset.clicks),target_clicks:Number(document.body.dataset.targetClicks)})")
    except Exception:
        reason = 'SETUP_OR_DRIVER_ERROR'
    finally:
        session.close()
    result = grounder.result
    row = {'case_id':case.id, 'expected':case.expected, 'observed':result.status if result else None,
           'grounding_reason':result.reason if result else None, 'controller_reason':reason,
           'bbox':list(result.bbox) if result and result.bbox else None,
           'mouse_attempts':attempts, 'page_state':state,
           'diagnostics':dict(base.last_diagnostics),
           'pass':assess(case,result,reason,attempts,state,base.last_diagnostics),
           'duration_ms':round((time.perf_counter()-started)*1000,3),
           'grounding_ms':grounder.grounding_ms, 'frame_age_after_grounding_ms':grounder.frame_age_ms,
           'clock_fault_injected':case.mutation == 'expire',
           'html_sha256':sha256(render(case).encode()).hexdigest()}
    return row, grounder.frame


def summarize(rows):
    positives=[row for row in rows if row['expected']=='click']
    verified=sum(row['pass'] for row in positives)
    refusals=sum(row['observed'] in {'not_found','ambiguous'} and row['mouse_attempts']==0 for row in positives)
    return {'observations':len(rows), 'passed':sum(row['pass'] for row in rows),
            'positive_observations':len(positives), 'false_abstentions':refusals,
            'positive_success_rate':verified/len(positives) if positives else None,
            'false_abstention_rate':refusals/len(positives) if positives else None,
            'failed':sum(not row['pass'] for row in rows),
            'unexpected_mouse_attempts':sum(row['mouse_attempts'] for row in rows if row['expected'] != 'click'),
            'wrong_click_observations':sum(row['mouse_attempts'] > 0 and
                (row['expected'] != 'click' or row['page_state'] != {'clicks':1,'target_clicks':1}) for row in rows),
            'verified_target_clicks':sum(row['pass'] and row['expected']=='click' for row in rows),
            'guard_passes':sum(row['pass'] and row['expected'] in {'stale','revoked','expired'} for row in rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model')
    parser.add_argument('--suite', choices=['regression','challenge'], default='regression')
    parser.add_argument('--grounder', choices=['ocr-candidates-v1','ocr-verified-v2','ocr-verified-v3','ocr-verified-v4'], default='ocr-candidates-v1')
    parser.add_argument('--check-cases', action='store_true')
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=Path('artifacts/benchmarks/browser-vision'))
    args = parser.parse_args(argv)
    cases=CASES
    if args.suite=='challenge':
        from benchmarks.browser_vision.challenge import CASES as challenge_cases
        cases=challenge_cases
    check_cases(cases)
    if args.check_cases:
        print(f'{len(cases)} {args.suite} fixture specs valid; no browser/model/click executed')
        return 0
    if not args.model: parser.error('--model is required for real fixture evaluation')
    if not 1 <= args.repetitions <= 5: parser.error('--repetitions must be 1..5')
    probe = BrowserSession(headless=args.headless)
    try:
        provider = OllamaVisionProvider(model=args.model, max_tokens=512)
        provider.check_local()
        ocr = AppleVisionOCR(profile='upscale2x-v2')
        ocr.prepare()
        probe.start()
        probe.context.route('**/*', lambda route: route.abort())
        probe.page.set_content(render(cases[0]))
        ocr.recognize(probe.snapshot())
    except (BrowserError, OCRError, VisionProviderError):
        parser.exit(2,'Browser/OCR/model prerequisite failed; no quality score claimed. Try desktop Terminal.\n')
    finally:
        probe.close()
    if args.grounder == 'ocr-verified-v4':
        from elvion.vision.label_candidates import OCRLabelGrounder
        base = OCRLabelGrounder(provider, ocr)
    elif args.grounder in {'ocr-verified-v2','ocr-verified-v3'}:
        from elvion.vision.semantic import OCRVerifiedGrounder, OCRPunctuationGrounder
        base = (OCRPunctuationGrounder if args.grounder == 'ocr-verified-v3' else OCRVerifiedGrounder)(provider, ocr)
    else:
        base = OCRCandidateGrounder(provider, ocr)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_id = f'{utc_now():%Y%m%dT%H%M%S}-{uuid4().hex[:8]}'
    rows = []
    for repetition in range(1,args.repetitions+1):
        for case in cases:
            row, frame = run_case(case,base,headless=args.headless)
            row['repetition'] = repetition
            if not row['pass'] and frame is not None:
                path = args.output_dir/f'{run_id}-{case.id}-r{repetition}.png'
                path.write_bytes(frame.image_png)
                path.chmod(0o600)
                row['synthetic_failure_frame'] = path.name
            rows.append(row)
            print(f"[{len(rows)}/{len(cases)*args.repetitions}] {case.id} · {'PASS' if row['pass'] else 'FAIL'} · "
                  f"mouse={row['mouse_attempts']} · {row['controller_reason'] or 'verified'}",flush=True)
    report = {'schema_version':1,'created_at':utc_now().isoformat(),'model':args.model,
              'config':{'grounder':args.grounder,'ocr_profile':'upscale2x-v2','max_tokens':512,
                        'suite':args.suite,'fixture_count':len(cases),
                        'repetitions':args.repetitions,'headless':args.headless,'synthetic_only':True,
                        'live_vision_enabled':False,'scope':'controlled fixture browser, no public websites'},
              'summary':summarize(rows),'results':rows}
    json_path=args.output_dir/f'browser-vision-{run_id}.json'
    json_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    json_path.chmod(0o600)
    md_path=json_path.with_suffix('.md')
    lines=['# Browser vision qualification','',json.dumps(report['summary']),'',
           '| Case | Run | Expected | Observed | Mouse attempts | Pass |',
           '| --- | ---: | --- | --- | ---: | --- |']
    lines += [f"| {r['case_id']} | {r['repetition']} | {r['expected']} | {r['observed']} | {r['mouse_attempts']} | {r['pass']} |" for r in rows]
    md_path.write_text('\n'.join(lines)+'\n');md_path.chmod(0o600)
    print(json.dumps(report['summary']))
    print(f'JSON: {json_path}\nMarkdown: {md_path}')
    return 0 if report['summary']['failed']==0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
