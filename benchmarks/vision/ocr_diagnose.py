"""Opt-in raw OCR diagnostics on known synthetic dev images only. No model or actions."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from benchmarks.vision.runner import frame_for, load_cases
from elvion.vision.ocr import AppleVisionOCR, OCRError, OCR_PROFILES, normalized_label


def collect(cases, *, ocr_factory=AppleVisionOCR, progress=None):
    if any(case['split'] != 'dev' for case in cases):
        raise ValueError('Only synthetic dev cases may be diagnosed')
    rows = []
    backends = {profile: ocr_factory(profile=profile) for profile in OCR_PROFILES}
    for backend in backends.values():
        backend.prepare()
    for case in cases:
        frame = frame_for(case)
        for profile, backend in backends.items():
            lines = backend.recognize(frame)
            row = {'case_id':case['id'], 'profile':profile,
                   'image_sha256':sha256(frame.image_png).hexdigest(), 'target':case['target'],
                   'viewport':[frame.width,frame.height], 'lines':[asdict(line) for line in lines],
                   'exact_matches':sum(normalized_label(line.text) == normalized_label(case['target']) for line in lines)}
            rows.append(row)
            if progress: progress(row)
    return {'version':1, 'synthetic_dev_only':True, 'model_called':False, 'rows':rows}


def save(report, directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/f'ocr-diagnostic-{uuid4().hex[:12]}.json'
    with path.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    path.chmod(0o600)
    return path


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',action='append')
    parser.add_argument('--output-dir',type=Path,default=Path('artifacts/benchmarks/vision/ocr-diagnostics'))
    args=parser.parse_args(argv)
    cases=[case for case in load_cases() if case['split']=='dev']
    if args.case:
        if any(name not in {case['id'] for case in cases} for name in args.case):
            parser.error('Choose known dev IDs only')
        cases=[case for case in cases if case['id'] in args.case]
    try:
        report=collect(cases,progress=lambda row:print(
            f"{row['case_id']} · {row['profile']} · {row['exact_matches']} exact matches · "
            f"OCR={json.dumps([line['text'] for line in row['lines']],ensure_ascii=False)}",flush=True))
    except OCRError:
        parser.exit(2,'Native OCR failed; no quality result claimed.\n')
    print(f'JSON: {save(report,args.output_dir)}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
