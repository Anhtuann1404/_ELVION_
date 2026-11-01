"""Strict research gate: repeated dev first, then existing regression; never enable live clicks."""
import argparse
import json
from pathlib import Path

from benchmarks.vision.runner import evaluate, frame_for, load_cases, write_report
from elvion.vision.ocr import AppleVisionOCR, OCRCandidateGrounder, OCRError, OCR_PROFILES
from elvion.vision.ollama import OllamaVisionProvider, VisionProviderError


def validate(cases, grounder, *, repetitions=3, progress=None):
    if type(repetitions) is not int or not 2 <= repetitions <= 10:
        raise ValueError('Use 2..10 repetitions for the stability gate')
    reports = []
    for split in ('dev', 'test'):
        selected = [case for case in cases if case['split'] == split]
        if not selected:
            raise ValueError('Missing evaluation split')
        report = evaluate(selected, grounder, repetitions, progress=progress)
        report['config']['research_gate'] = 'all_observations_correct_v1'
        report['config']['ocr_language'] = 'en-US'
        reports.append(report)
        if report['summary']['failed']:
            break
    return {'research_gate_passed': len(reports) == 2 and all(r['summary']['failed'] == 0 for r in reports),
            'live_vision_enabled': False, 'reports': reports,
            'scope': 'English labeled synthetic controls; existing test split is regression, not new blind evaluation'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--grounder', choices=['ocr-candidates-v1','ocr-verified-v2','ocr-verified-v3'], default='ocr-candidates-v1')
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--ocr-profile', choices=OCR_PROFILES, default='native-v1')
    parser.add_argument('--diagnose-ocr', action='store_true', help='Explicit raw OCR export of synthetic dev fixtures only')
    parser.add_argument('--output-dir', type=Path, default=Path('artifacts/benchmarks/vision/ocr-validation'))
    args = parser.parse_args(argv)
    if not 2 <= args.repetitions <= 10:
        parser.error('--repetitions must be 2..10')
    cases = load_cases()
    try:
        ocr = AppleVisionOCR(profile=args.ocr_profile)
        ocr.prepare()
        ocr.recognize(frame_for(next(case for case in cases if case['split'] == 'dev')))
        if args.diagnose_ocr:
            from benchmarks.vision.ocr_diagnose import collect, save
            diagnostic = collect([case for case in cases if case['split'] == 'dev'],
                progress=lambda row:print(f"OCR {row['case_id']} · {row['profile']} · {row['exact_matches']} exact matches",flush=True))
            path = save(diagnostic, args.output_dir / 'ocr-diagnostics')
            print(f'OCR diagnostic JSON: {path}',flush=True)
        provider = OllamaVisionProvider(model=args.model, max_tokens=512)
        provider.check_local()
    except OCRError as error:
        reason = str(error) if str(error) in {'OCR_FAILED', 'OCR_UNAVAILABLE', 'OCR_BUILD_FAILED'} else 'OCR_FAILED'
        parser.exit(2, f'OCR prerequisite failed: {reason}; no quality score claimed. Try macOS desktop Terminal.\n')
    except (VisionProviderError, ValueError):
        parser.exit(2, 'Model prerequisite failed; no quality score claimed.\n')
    if args.grounder in {'ocr-verified-v2','ocr-verified-v3'}:
        from elvion.vision.semantic import OCRVerifiedGrounder, OCRPunctuationGrounder
        grounder = (OCRPunctuationGrounder if args.grounder == 'ocr-verified-v3' else OCRVerifiedGrounder)(provider, ocr)
    else:
        grounder = OCRCandidateGrounder(provider, ocr)
    result = validate(cases, grounder, repetitions=args.repetitions,
        progress=lambda done, total, case, protocol, outcome: print(f'[{done}/{total}] {case} · {protocol} · {outcome}', flush=True))
    for report in result['reports']:
        paths = write_report(report, args.output_dir)
        print(f"{report['config']['split'][0]}: {report['summary']['passed']}/{report['summary']['observations']}; "
              f"wrong targets: {report['summary']['wrong_target']}; errors: {report['summary']['provider_error'] + report['summary']['timeout']}")
        print(f'JSON: {paths[0]}\nMarkdown: {paths[1]}')
    print(json.dumps({key:value for key,value in result.items() if key != 'reports'}, ensure_ascii=False))
    return 0 if result['research_gate_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
