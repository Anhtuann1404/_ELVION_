"""Score screenshot-only label proposals on synthetic Chromium fixtures; never click."""
import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from statistics import median
import time
from uuid import uuid4

from benchmarks.vision_labels.cases import CASES, WIDTH, HEIGHT, Case, check_cases, manifest_sha256, render
from elvion.browser.contracts import GroundingResult, VisionFrame
from elvion.browser.session import BrowserSession, BrowserError
from elvion.core.contracts import utc_now
from elvion.vision.ocr import AppleVisionOCR, OCRError
from elvion.vision.ollama import OllamaVisionProvider, VisionProviderError
from elvion.vision.semantic import OCRVerifiedGrounder, OCRPunctuationGrounder

from elvion.vision.label_candidates import OCRLabelGrounder

GROUNDERS = {'ocr-verified-v2': OCRVerifiedGrounder, 'ocr-verified-v3': OCRPunctuationGrounder,
             'ocr-verified-v4': OCRLabelGrounder}
OCR_PROFILE = 'upscale2x-v2'
TOKEN_BUDGET = 512


@dataclass(frozen=True)
class Capture:
    frame: VisionFrame
    truth_boxes: tuple[tuple[float, float, float, float], ...]
    distractor_boxes: tuple[tuple[float, float, float, float], ...]


def capture_case(session: BrowserSession, case: Case, revision: int) -> Capture:
    """DOM is used only by the oracle; the grounder receives frame pixels alone."""
    html = render(case)
    session.page.set_content(html, wait_until='load')
    boxes = {}
    for element in case.elements:
        rect = session.page.locator(f'[data-fixture-id="{element.id}"]').bounding_box()
        if rect is None:
            raise ValueError('FIXTURE_CONTROL_NOT_VISIBLE')
        if any(abs(rect[key] - expected) > 0.5 for key, expected in
               (('x',element.x),('y',element.y),('width',element.width),('height',element.height))):
            raise ValueError('FIXTURE_CONTROL_GEOMETRY_CHANGED')
        boxes[element.id] = (rect['x'], rect['y'], rect['width'], rect['height'])
    png = session.page.screenshot(type='png', full_page=False, caret='hide')
    frame = VisionFrame(uuid4().hex, uuid4().hex, revision, png, WIDTH, HEIGHT, time.monotonic())
    return Capture(frame, tuple(boxes[key] for key in case.truth_ids),
                   tuple(boxes[key] for key in boxes if key not in case.truth_ids))


def _inside(point, box):
    x, y, width, height = box
    return x <= point[0] <= x + width and y <= point[1] <= y + height


def assess(case: Case, result: GroundingResult, capture: Capture) -> str:
    """One result per observation; errors and unexpected abstentions always fail."""
    if type(result) is not GroundingResult or result.frame_id != capture.frame.frame_id:
        return 'grounder_error'
    if result.status == 'error':
        return 'grounder_error'
    if result.status == 'found':
        box = result.bbox
        if (type(box) is not tuple or len(box) != 4 or
                any(type(v) not in (int, float) or not isfinite(v) for v in box) or
                box[0] < 0 or box[1] < 0 or box[2] <= 0 or box[3] <= 0 or
                box[0] + box[2] > capture.frame.width or box[1] + box[3] > capture.frame.height):
            return 'grounder_error'
        center = box[0] + box[2] / 2, box[1] + box[3] / 2
        if case.expected != 'found':
            return 'false_acceptance'
        return ('correct_target' if any(_inside(center, truth) for truth in capture.truth_boxes) and
                not any(_inside(center, other) for other in capture.distractor_boxes) else 'wrong_target')
    if case.expected == 'found':
        return 'false_abstention'
    if result.status == case.expected:
        return 'correct_ambiguity' if result.status == 'ambiguous' else 'correct_rejection'
    return 'wrong_abstention'


def evaluate(cases, *, grounder, capture, repetitions=1, model='fake', grounder_version='fake',
             ocr_profile='none', token_budget=0, headless=True):
    """Inject capture and grounder independently; never pass answer/DOM to locate()."""
    cases = tuple(cases)
    if not cases or type(repetitions) is not int or not 1 <= repetitions <= 5:
        raise ValueError('Invalid selection or repetition count')
    rows = []
    for repetition in range(1, repetitions + 1):
        for case in cases:
            observation = capture(case)
            started = time.perf_counter_ns()
            try:
                result = grounder.locate(observation.frame, target=case.target, role=case.role)
            except Exception:
                result = GroundingResult(observation.frame.frame_id, 'error', reason='PROVIDER_ERROR')
            elapsed_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
            outcome = assess(case, result, observation)
            # Fixed, non-content diagnostics only: never store OCR/model text.
            diagnostic_keys = {'decision_stage', 'ocr_line_count', 'exact_match_count',
                               'label_verification', 'full_image_match_count',
                               'full_observed_role', 'observed_role', 'availability',
                               'candidate_count', 'verified_candidate_count', 'uncertainty_stage',
                               'label_scale','full_scale','duplicate_text_checks','subline_ocr_passes','unresolved_merged_labels','native_edge_adjustments'}
            diagnostics = getattr(grounder, 'last_diagnostics', {})
            if type(diagnostics) is not dict:
                diagnostics = {}
            rows.append({'case_id':case.id, 'split':case.split, 'group':case.group,
                         'repetition':repetition, 'expected':case.expected,
                         'observed':result.status if type(result) is GroundingResult else 'error',
                         'reason':result.reason if type(result) is GroundingResult else 'PROVIDER_ERROR',
                         'outcome':outcome, 'pass':outcome in {'correct_target','correct_rejection','correct_ambiguity'},
                         'locate_ms':elapsed_ms, 'html_sha256':sha256(render(case).encode()).hexdigest(),
                         'diagnostics': {key: value for key, value in diagnostics.items()
                                         if key in diagnostic_keys and type(value) in (str, int, bool)}})
    positive = [row for row in rows if row['expected'] == 'found']
    negative = [row for row in rows if row['expected'] != 'found']
    ambiguity = [row for row in rows if row['expected'] == 'ambiguous']
    count = lambda outcome: sum(row['outcome'] == outcome for row in rows)
    rate = lambda numerator, denominator: {'numerator':numerator, 'denominator':denominator,
                                            'value':round(numerator/denominator,4) if denominator else None}
    summary = {'observations':len(rows), 'passed':sum(row['pass'] for row in rows),
               'failed':sum(not row['pass'] for row in rows),
               'positive_observations':len(positive), 'correct_target_proposals':count('correct_target'),
               'positive_success_rate':rate(count('correct_target'),len(positive)),
               'false_abstentions':count('false_abstention'),
               'false_abstention_rate':rate(count('false_abstention'),len(positive)),
               'wrong_target_proposals':count('wrong_target'),
               'negative_observations':len(negative), 'negative_false_acceptances':count('false_acceptance'),
               'correct_rejections':count('correct_rejection'),
               'correct_ambiguity':rate(count('correct_ambiguity'),len(ambiguity)),
               'wrong_abstentions':count('wrong_abstention'), 'provider_grounder_errors':count('grounder_error'),
               'median_locate_ms':median(row['locate_ms'] for row in rows)}
    return {'schema_version':1, 'created_at':utc_now().isoformat(),
            'config':{'model':model, 'grounder':grounder_version, 'ocr_profile':ocr_profile,
                      'label_scale':getattr(grounder,'label_scale',1),
                      'role_marker':getattr(grounder,'role_marker',None),
                      'full_scale':getattr(grounder,'full_scale',1),
                      'duplicate_text_check':getattr(grounder,'duplicate_text_check',False),
                      'role_profile':getattr(grounder,'role_profile','current'),
                      'role_profile_source_sha256':sha256(Path(__file__).with_name('role_profiles.py').read_bytes()).hexdigest(),
                      'token_budget':token_budget,
                      'label_marker':'leading_single_glyph_or_subline_hypotheses' if grounder_version=='ocr-verified-v4' else None, 'viewport':{'width':WIDTH,'height':HEIGHT,'device_scale_factor':1},
                      'repetitions':repetitions, 'splits':sorted({case.split for case in cases}),
                      'held_out_use':'regression_after_first_view' if any(case.split=='held_out' for case in cases) else None,
                      'synthetic_only':True, 'headless':headless, 'manifest_sha256':manifest_sha256()},
            'summary':summary, 'results':rows}


def markdown(report):
    summary = report['summary']
    coverage, abstain = summary['positive_success_rate'], summary['false_abstention_rate']
    lines = ['# ELVION Vision label benchmark', '',
             f"Observations: {summary['observations']}; pass: {summary['passed']}/{summary['observations']}; "
             f"positive target hit: {coverage['numerator']}/{coverage['denominator']}; "
             f"false abstention: {abstain['numerator']}/{abstain['denominator']}.",
             f"Wrong target: {summary['wrong_target_proposals']}; negative false acceptances: "
             f"{summary['negative_false_acceptances']}/{summary['negative_observations']}; "
             f"correct ambiguity: {summary['correct_ambiguity']['numerator']}/{summary['correct_ambiguity']['denominator']}; "
             f"errors: {summary['provider_grounder_errors']}.",
             f"Median full locate: {summary['median_locate_ms']} ms. Manifest SHA256: {report['config']['manifest_sha256']}", '',
             '| Case | Split | Run | Expected | Observed | Outcome | Locate ms |',
             '| --- | --- | ---: | --- | --- | --- | ---: |']
    lines += [f"| {row['case_id']} | {row['split']} | {row['repetition']} | {row['expected']} | "
              f"{row['observed']} | {row['outcome']} | {row['locate_ms']} |" for row in report['results']]
    lines += ['', 'Synthetic screenshots only. No click, action, or post-action verifier was used.', '']
    return '\n'.join(lines)


def write_report(report, directory, *, diagnostic_records=None):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stem = f"vision-labels-{utc_now():%Y%m%dT%H%M%S}-{uuid4().hex[:8]}"
    paths = directory / f'{stem}.json', directory / f'{stem}.md'
    if diagnostic_records is not None:
        from benchmarks.web_observation.plan import sources
        frames=directory/f'{stem}.frames';frames.mkdir(mode=0o700)
        rows=[]
        for index,record in enumerate(diagnostic_records):
            row={k:v for k,v in record.items() if k!='frame_png'}
            image=frames/f'frame-{index:03}.png'
            with image.open('xb') as stream:stream.write(record['frame_png'])
            image.chmod(0o600);row['frame_png']=str(image.relative_to(directory));rows.append(row)
        diagnostic=directory/f'{stem}.diagnostics.json'
        data={'synthetic_only':True,'actions':0,'config':report['config'],
              'source_sha256':sources(),'records':rows}
        with diagnostic.open('x') as stream:json.dump(data,stream,ensure_ascii=False,indent=2)
        diagnostic.chmod(0o600)
        report=dict(report,diagnostics_file=diagnostic.name)
    for path, content in ((paths[0],json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
                          (paths[1],markdown(report))):
        with path.open('x',encoding='utf-8') as stream: stream.write(content)
        path.chmod(0o600)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-cases',action='store_true',help='Render and validate synthetic fixtures; no model')
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--model')
    parser.add_argument('--grounder',choices=tuple(GROUNDERS),default='ocr-verified-v3')
    parser.add_argument('--label-scale',type=int,choices=[1,2,4],default=1)
    parser.add_argument('--role-marker',choices=['on','off'],default='on')
    parser.add_argument('--full-scale',type=int,choices=[1,2],default=1)
    parser.add_argument('--duplicate-text-check',action='store_true')
    parser.add_argument('--role-profile',choices=['current','visual-evidence-v1'],default='current')
    parser.add_argument('--diagnose-model',action='store_true',help='Opt in to saving synthetic frames, OCR and model replies for offline diagnosis')
    parser.add_argument('--split',choices=('dev','held_out','all'),default='dev')
    parser.add_argument('--case',action='append')
    parser.add_argument('--headless',action='store_true')
    parser.add_argument('--repetitions',type=int,default=1)
    parser.add_argument('--output-dir',type=Path,default=Path('artifacts/benchmarks/vision-labels'))
    args = parser.parse_args(argv)
    if args.label_scale!=1 and args.grounder!='ocr-verified-v4':
        parser.error('--label-scale requires ocr-verified-v4')
    if args.role_marker!='on' and args.grounder!='ocr-verified-v4':
        parser.error('--role-marker requires ocr-verified-v4')
    if args.full_scale!=1 and args.grounder!='ocr-verified-v4':
        parser.error('--full-scale requires ocr-verified-v4')
    if args.duplicate_text_check and args.grounder!='ocr-verified-v4':
        parser.error('--duplicate-text-check requires ocr-verified-v4')
    if args.role_profile!='current' and args.grounder!='ocr-verified-v4':
        parser.error('--role-profile requires ocr-verified-v4')
    try: check_cases()
    except ValueError: parser.exit(2,'Invalid fixture manifest.\n')
    if args.list:
        for case in CASES: print(f'{case.id} [{case.split}] {case.group}: {case.expected}')
        return 0
    if not 1 <= args.repetitions <= 5: parser.error('--repetitions must be 1..5')
    ids = args.case or [case.id for case in CASES if args.split=='all' or case.split==args.split]
    if len(ids)!=len(set(ids)) or any(item not in {case.id for case in CASES} for item in ids):
        parser.error('Select unique known case IDs')
    selected = [case for case in CASES if case.id in ids and (args.split=='all' or case.split==args.split)]
    if len(selected)!=len(ids): parser.error('A selected case is outside --split')
    session = BrowserSession(headless=True if args.check_cases else args.headless)
    try:
        session.start()
        session.context.route('**/*',lambda route:route.abort())
        revision=[0]
        def capture(case):
            revision[0]+=1
            return capture_case(session,case,revision[0])
        if args.check_cases:
            for case in CASES: capture(case)
            print(f'{len(CASES)} cases rendered; manifest SHA256={manifest_sha256()}; no model/click')
            return 0
        if not args.model: parser.error('--model is required for inference')
        provider=OllamaVisionProvider(model=args.model,max_tokens=TOKEN_BUDGET)
        provider.check_local()
        from benchmarks.vision_labels.role_profiles import with_role_profile
        provider.complete=with_role_profile(provider.complete,args.role_profile)
        ocr=AppleVisionOCR(profile=OCR_PROFILE)
        ocr.prepare()
        ocr.recognize(capture(selected[0]).frame)
        if args.grounder=='ocr-verified-v4':
            from elvion.vision.presentation import prepare_scaler
            grounder=OCRLabelGrounder(provider,ocr,label_scale=args.label_scale,role_marker=args.role_marker=='on',
                full_scale=args.full_scale,duplicate_text_check=args.duplicate_text_check,
                scaler=prepare_scaler() if args.label_scale!=1 or args.full_scale!=1 else None)
        else:grounder=GROUNDERS[args.grounder](provider,ocr)
        grounder.role_profile=args.role_profile
        if args.diagnose_model:
            from benchmarks.vision_labels.diagnostics import RecordingGrounder
            grounder=RecordingGrounder(grounder)
        report=evaluate(selected,grounder=grounder,capture=capture,repetitions=args.repetitions,
                        model=args.model,grounder_version=args.grounder,ocr_profile=OCR_PROFILE,
                        token_budget=TOKEN_BUDGET,headless=args.headless)
    except (BrowserError, OCRError, VisionProviderError, ValueError):
        parser.exit(2,'Browser/OCR/model fixture prerequisite failed; no quality score claimed.\n')
    finally:
        session.close()
    paths=write_report(report,args.output_dir,
        diagnostic_records=grounder.records if args.diagnose_model else None)
    print(f"Pass: {report['summary']['passed']}/{report['summary']['observations']}; "
          f"positive target hit: {report['summary']['correct_target_proposals']}/{report['summary']['positive_observations']}; "
          f"false acceptances: {report['summary']['negative_false_acceptances']}")
    print(f'JSON: {paths[0]}\nMarkdown: {paths[1]}')
    if args.diagnose_model:print(f'Diagnostics: {paths[0].with_suffix(".diagnostics.json")}')
    return 0 if report['summary']['failed']==0 else 1


if __name__=='__main__':
    raise SystemExit(main())
