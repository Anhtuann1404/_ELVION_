"""Score local vision grounding on synthetic viewport screenshots; never execute an action."""
import argparse
import json
from pathlib import Path
from time import perf_counter_ns
from uuid import uuid4

from elvion.browser.contracts import VisionFrame
from elvion.core.contracts import utc_now
from elvion.vision import LocalVisionGrounder, OllamaVisionProvider
from elvion.vision.grounder import valid_png
from elvion.vision.grounder import PROTOCOLS, POINT_PROTOCOL

EXPERIMENTAL_PROTOCOLS = (*PROTOCOLS, POINT_PROTOCOL, 'ocr-candidates-v1')
from elvion.vision.ollama import VisionProviderError

FIXTURES = Path(__file__).parent / "fixtures"


def load_cases():
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or type(manifest.get("cases")) is not list:
        raise ValueError("INVALID_MANIFEST")
    cases = manifest["cases"]
    if len(cases) != 24 or len({case.get("id") for case in cases}) != len(cases):
        raise ValueError("INVALID_MANIFEST")
    for case in cases:
        if (case.get("split") not in {"dev", "test"} or case.get("role") not in {"textbox", "button", "link"} or
                case.get("expected") not in {"found", "not_found", "ambiguous"} or
                type(case.get("target")) is not str or not case["target"] or
                type(case.get("boxes")) is not list or
                (case["expected"] == "found" and len(case["boxes"]) != 1) or
                (case["expected"] == "ambiguous" and len(case["boxes"]) < 2) or
                (case["expected"] == "not_found" and case["boxes"])):
            raise ValueError("INVALID_MANIFEST")
        if case["png"] != case["id"] + ".png" or case["html"] != case["id"] + ".html":
            raise ValueError("INVALID_MANIFEST")
        frame = frame_for(case)
        if not valid_png(frame):
            raise ValueError("INVALID_FIXTURE_PNG")
        html = (FIXTURES / case["html"]).read_text(encoding="utf-8")
        if case["target"] not in html and case["expected"] != "not_found":
            raise ValueError("INVALID_FIXTURE_HTML")
        for box in case["boxes"]:
            if (type(box) is not list or len(box) != 4 or any(type(v) is not int for v in box) or
                    min(box[:2]) < 0 or min(box[2:]) <= 0 or
                    box[0] + box[2] > frame.width or box[1] + box[3] > frame.height):
                raise ValueError("INVALID_MANIFEST")
            x, y, width, height = box
            if case["canvas"]:
                if f"fillRect({x},{y},{width},{height})" not in html:
                    raise ValueError("INVALID_FIXTURE_HTML")
            elif not all(text in html for text in (f"left:{x}px", f"top:{y}px", f"width:{width}px", f"height:{height}px")):
                raise ValueError("INVALID_FIXTURE_HTML")
    return cases


def frame_for(case):
    return VisionFrame(frame_id="synthetic-" + case["id"], page_id="fixture-page",
                       revision=0, image_png=(FIXTURES / case["png"]).read_bytes(),
                       width=case["width"], height=case["height"], captured_at=0.0)


def score(case, result):
    if result.status == "error":
        return "timeout" if result.reason == "MODEL_TIMEOUT" else "provider_error"
    expected = case["expected"]
    if expected != "found":
        return "correct_abstain" if result.status == expected else "wrong_target" if result.status == "found" else "wrong_abstain"
    if result.status != "found":
        return "unexpected_abstain"
    x, y, width, height = result.bbox
    center = x + width / 2, y + height / 2
    return "target_hit" if any(left <= center[0] <= left + w and top <= center[1] <= top + h
                               for left, top, w, h in case["boxes"]) else "wrong_target"


def evaluate(cases, grounder, repetitions=1, *, progress=None):
    if type(repetitions) is not int or not 1 <= repetitions <= 10:
        raise ValueError("INVALID_REPETITIONS")
    rows = []
    for case in cases:
        for repetition in range(1, repetitions + 1):
            frame = frame_for(case)
            started = perf_counter_ns()
            result = grounder.locate(frame, target=case["target"], role=case["role"])
            duration_ms = round((perf_counter_ns() - started) / 1_000_000, 3)
            outcome = score(case, result)
            rows.append({"case_id": case["id"], "split": case["split"], "repetition": repetition,
                         "expected": case["expected"], "observed": result.status,
                         "reason": result.reason, "bbox": list(result.bbox) if result.bbox else None,
                         "outcome": outcome, "pass": outcome in {"target_hit", "correct_abstain"},
                         "grounding_ms": duration_ms,
                         "inference_ms": getattr(grounder.provider, "last_inference_ms", None)})
            diagnostics = getattr(grounder, 'last_diagnostics', None)
            if type(diagnostics) is dict:
                rows[-1]['diagnostics'] = dict(diagnostics)
            if progress:
                progress(len(rows), len(cases)*repetitions, case['id'], grounder.protocol, outcome)
    return report_for(cases, grounder, repetitions, rows)


def report_for(cases, grounder, repetitions, rows):
    counts = {name: sum(row["outcome"] == name for row in rows) for name in
              ("target_hit", "wrong_target", "correct_abstain", "wrong_abstain", "unexpected_abstain",
               "provider_error", "timeout")}
    counts.update({"cases": len(cases), "observations": len(rows), "passed": sum(row["pass"] for row in rows),
                   "failed": sum(not row["pass"] for row in rows)})
    counts['reason_counts'] = {reason: sum(row['reason'] == reason for row in rows)
                               for reason in sorted({row['reason'] for row in rows if row['reason']})}
    report = {"schema_version": 1, "created_at": utc_now().isoformat().replace("+00:00", "Z"),
            "model": getattr(grounder.provider, "model", "fake_provider"),
            "config": {"split": sorted({case["split"] for case in cases}), "repetitions": repetitions,
                       "synthetic_fixtures": True, "protocol": getattr(grounder, 'protocol', 'xywh-v1'),
                       "max_tokens": getattr(grounder.provider, 'max_tokens', None),
                       "live_vision_enabled": False}, "results": rows, "summary": counts}
    if getattr(grounder, 'protocol', None) in {'ocr-candidates-v1','ocr-verified-v2'}:
        report['config'].update(ocr_language='en-US', label_match='NFC_casefold_full_line',
                                model_role_verification=True, coordinates_source='native_ocr_text_box',
                                ocr_profile=getattr(grounder.ocr, 'profile', 'fake'))
        report['config']['semantic_verification'] = ('full_image_count_and_independent_crop_role'
            if grounder.protocol == 'ocr-verified-v2' else 'goal_conditioned_single_verification')
    return report


def compare_protocols(cases, provider, repetitions=1, *, progress=None):
    """Paired, alternating protocol order; identical pixels, model, budget and scoring."""
    if type(repetitions) is not int or not 1 <= repetitions <= 10:
        raise ValueError('INVALID_REPETITIONS')
    grounders = {name: LocalVisionGrounder(provider, protocol=name) for name in PROTOCOLS}
    rows = {name: [] for name in PROTOCOLS}
    done, total = 0, len(cases) * repetitions * len(PROTOCOLS)
    for index, case in enumerate(cases):
        for repetition in range(1, repetitions + 1):
            order = PROTOCOLS if (index + repetition) % 2 else PROTOCOLS[::-1]
            for name in order:
                row = evaluate([case], grounders[name])['results'][0]
                row['repetition'] = repetition
                rows[name].append(row)
                done += 1
                if progress:
                    progress(done, total, case['id'], name, row['outcome'])
    reports = {name: report_for(cases, grounders[name], repetitions, rows[name]) for name in PROTOCOLS}
    for report in reports.values():
        report['config']['paired_protocols'] = list(PROTOCOLS)
        report['config']['alternating_order'] = True
    return reports


def markdown(report):
    summary = report["summary"]
    lines = ["# ELVION synthetic vision grounding", "",
             f"Model: {report['model']}; protocol: {report['config'].get('protocol', 'xywh-v1')}; "
             f"max tokens: {report['config'].get('max_tokens')}; cases: {summary['cases']}; observations: {summary['observations']}",
             f"Pass: {summary['passed']}/{summary['observations']}; target hits: {summary['target_hit']}; "
             f"wrong targets: {summary['wrong_target']}; correct abstentions: {summary['correct_abstain']}; "
             f"unexpected abstentions: {summary['unexpected_abstain']}; provider errors: {summary['provider_error']}; "
             f"timeouts: {summary['timeout']}", "",
             "| Case | Split | Run | Expected | Observed | Outcome | Grounding ms | Inference ms |",
             "| --- | --- | ---: | --- | --- | --- | ---: | ---: |"]
    for row in report["results"]:
        lines.append(f"| {row['case_id']} | {row['split']} | {row['repetition']} | {row['expected']} | "
                     f"{row['observed']} | {row['outcome']} | {row['grounding_ms']} | {row['inference_ms'] or '—'} |")
    lines += ["", "Hit means the predicted box center lies inside the synthetic truth box. No click or task verification occurred.", ""]
    return "\n".join(lines)


def write_report(report, directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stem = f"vision-{utc_now():%Y%m%dT%H%M%S}-{uuid4().hex[:8]}"
    paths = directory / f"{stem}.json", directory / f"{stem}.md"
    for path, content in ((paths[0], json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
                          (paths[1], markdown(report))):
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
        path.chmod(0o600)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="Explicit installed local Ollama vision model")
    parser.add_argument('--protocol', choices=EXPERIMENTAL_PROTOCOLS, default='xywh-v1')
    parser.add_argument('--compare-protocols', action='store_true', help='Paired alternating v1/v2 evaluation; no clicks')
    parser.add_argument('--max-tokens', type=int, default=128, help='Identical generation budget for both profiles (64..1024)')
    parser.add_argument("--split", choices=("dev", "test", "all"), default="all")
    parser.add_argument("--case", action="append", help="Repeat to select case IDs")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--check-fixtures", action="store_true", help="Validate manifest, PNG and HTML without model")
    parser.add_argument("--list", action="store_true", help="List synthetic case IDs")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/benchmarks/vision"))
    args = parser.parse_args(argv)
    try:
        cases = load_cases()
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"Fixture setup failed: {str(error) if type(error) is ValueError else 'INVALID_FIXTURE'}\n")
    if args.list:
        for case in cases:
            print(f"{case['id']} ({case['split']}): {case['role']} / {case['expected']}")
        return 0
    if args.check_fixtures:
        print(f"Fixture check passed: {len(cases)} cases; no model called")
        return 0
    if not args.model:
        parser.error("--model is required for inference")
    if not 1 <= args.repetitions <= 10:
        parser.error("--repetitions must be between 1 and 10")
    if not 64 <= args.max_tokens <= 1024:
        parser.error('--max-tokens must be between 64 and 1024')
    if args.compare_protocols and args.protocol != 'xywh-v1':
        parser.error('Use either --protocol or --compare-protocols')
    ids = args.case or [case["id"] for case in cases if args.split == "all" or case["split"] == args.split]
    if not ids or len(ids) != len(set(ids)) or any(item not in {case["id"] for case in cases} for item in ids):
        parser.error("Choose unique known case IDs")
    selected = [case for case in cases if case["id"] in ids and (args.split == "all" or case["split"] == args.split)]
    if len(selected) != len(ids):
        parser.error("A selected case is outside --split")
    try:
        provider = OllamaVisionProvider(model=args.model, max_tokens=args.max_tokens)
        provider.check_local()
    except (VisionProviderError, ValueError) as error:
        parser.exit(2, f"Model setup failed: {getattr(error, 'code', 'MODEL_UNAVAILABLE')}\n")
    if args.compare_protocols:
        reports = compare_protocols(selected, provider, args.repetitions,
            progress=lambda done, total, case, name, outcome: print(f'[{done}/{total}] {case} · {name} · {outcome}', flush=True))
    else:
        if args.protocol == 'ocr-candidates-v1':
            from elvion.vision.ocr import AppleVisionOCR, OCRCandidateGrounder, OCRError
            ocr = AppleVisionOCR()
            try:
                ocr.prepare()
                ocr.recognize(frame_for(selected[0]))
            except OCRError:
                parser.exit(2, 'OCR setup failed: native recognition unavailable in this process; no model evaluation started\n')
            grounder = OCRCandidateGrounder(provider, ocr)
        else:
            grounder = LocalVisionGrounder(provider, protocol=args.protocol)
        reports = {args.protocol: evaluate(selected, grounder, args.repetitions,
            progress=lambda done, total, case, name, outcome: print(f'[{done}/{total}] {case} · {name} · {outcome}', flush=True))}
    for name, report in reports.items():
        paths = write_report(report, args.output_dir)
        print(f"{name}: {report['summary']['passed']}/{report['summary']['observations']}; "
              f"hits: {report['summary']['target_hit']}; wrong: {report['summary']['wrong_target']}; "
              f"errors: {report['summary']['provider_error'] + report['summary']['timeout']}; "
              f"reasons: {json.dumps(report['summary']['reason_counts'])}")
        print(f"JSON: {paths[0]}\nMarkdown: {paths[1]}")
    return 0 if all(report['summary']['failed'] == 0 for report in reports.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
