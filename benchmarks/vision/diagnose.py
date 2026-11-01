"""Offline dev-only box diagnostics. No inference, browser actions or score changes."""
import argparse
import base64
from html import escape
import json
from pathlib import Path

from benchmarks.vision.runner import FIXTURES, load_cases, score
from elvion.browser.contracts import GroundingResult


def geometry(prediction, truth):
    if prediction is None or len(truth) != 1:
        return {}
    x, y, w, h = prediction
    left, top, width, height = truth[0]
    cx, cy = x + w / 2, y + h / 2
    overlap = max(0, min(x+w, left+width)-max(x, left)) * max(0, min(y+h, top+height)-max(y, top))
    return {
        'center': [round(cx, 3), round(cy, 3)],
        'delta_from_truth_center': [round(cx-left-width/2, 3), round(cy-top-height/2, 3)],
        'horizontal_inside': left <= cx <= left+width,
        'vertical_inside': top <= cy <= top+height,
        'iou': round(overlap / (w*h + width*height - overlap), 4),
    }


def analyze(paths):
    cases = {case['id']: case for case in load_cases() if case['split'] == 'dev'}
    rows, sources = [], []
    for path in paths:
        report = json.loads(Path(path).read_text(encoding='utf-8'))
        if report['config'].get('synthetic_fixtures') is not True:
            raise ValueError('Only synthetic fixture reports are supported')
        if report['config']['split'] != ['dev']:
            raise ValueError('Only dev reports are supported; do not inspect test while tuning')
        sources.append(str(path))
        for row in report['results']:
            case = cases[row['case_id']]
            if row['split'] != 'dev' or row['expected'] != case['expected']:
                raise ValueError('Report does not match dev manifest')
            result = GroundingResult('offline-diagnostic', row['observed'],
                bbox=tuple(row['bbox']) if row['bbox'] is not None else None, reason=row['reason'])
            if score(case, result) != row['outcome']:
                raise ValueError('Saved outcome disagrees with unchanged scorer')
            rows.append({
                'case_id': case['id'], 'protocol': report['config']['protocol'],
                'source': str(path), 'repetition': row['repetition'],
                'model': report['model'], 'max_tokens': report['config'].get('max_tokens'),
                'expected': row['expected'], 'observed': row['observed'],
                'outcome': row['outcome'], 'reason': row['reason'],
                'predicted_bbox': row['bbox'], 'truth_boxes': case['boxes'],
                'geometry': geometry(row['bbox'], case['boxes']),
            })
    return {'sources': sources, 'split': 'dev', 'model_called': False,
            'scores_changed': False, 'rows': rows}


def render_html(diagnostic):
    cases = {case['id']: case for case in load_cases() if case['split'] == 'dev'}
    cards = []
    rows = sorted(diagnostic['rows'], key=lambda row: (row['case_id'], row['protocol'], row['repetition']))
    for row in rows:
        case = cases[row['case_id']]
        encoded = base64.b64encode((FIXTURES / case['png']).read_bytes()).decode('ascii')
        elements = []
        for x, y, w, h in row['truth_boxes']:
            elements.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="#00945e" stroke-width="3"/>')
        if row['predicted_bbox'] is not None:
            x, y, w, h = row['predicted_bbox']
            elements += [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="#df2935" stroke-width="3" stroke-dasharray="7 4"/>',
                         f'<circle cx="{x+w/2}" cy="{y+h/2}" r="5" fill="#df2935"/>']
        label = f"{row['case_id']} · {row['protocol']} · run {row['repetition']}"
        details = json.dumps({'predicted': row['predicted_bbox'], **row['geometry']}, ensure_ascii=False)
        cards.append(f'''<section><h2>{escape(label)}</h2>
<p>Target: {escape(case['target'])} · Role: {escape(case['role'])}<br>
Expected: {escape(row['expected'])} · Observed: {escape(row['observed'])} · {escape(row['outcome'])}</p>
<svg viewBox="0 0 {case['width']} {case['height']}" role="img" aria-label="{escape(label, quote=True)}">
<image href="data:image/png;base64,{encoded}" width="{case['width']}" height="{case['height']}"/>
{''.join(elements)}</svg><pre>{escape(details)}</pre></section>''')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><title>ELVION Vision dev diagnostics</title>
<style>body{font:16px system-ui;margin:24px;background:#f3f6fa;color:#172536}
main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
section{background:white;padding:16px;border:1px solid #c6d3df;border-radius:12px}
h2{font-size:17px}svg{width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}
@media(max-width:850px){main{grid-template-columns:1fr}}</style>
<h1>Vision dev: saved predictions versus truth</h1>
<p>Green solid: truth. Red dashed + dot: prediction and its click center.</p>
<p>Offline analysis only. No model called, no click, no score changed. Truth is used only here, never sent to the model.</p>
<main>''' + ''.join(cards) + '</main></html>\n'


def render_markdown(diagnostic):
    lines = ['# Vision dev box diagnostics', '',
        'Offline saved-report analysis; no model inference, clicks or scoring changes.', '',
        '| Case | Protocol | Outcome | Center dx | Center dy | IoU |',
        '| --- | --- | --- | ---: | ---: | ---: |']
    for row in diagnostic['rows']:
        stats = row['geometry']
        delta = stats.get('delta_from_truth_center', ['—', '—'])
        lines.append(f"| {row['case_id']} | {row['protocol']} | {row['outcome']} | {delta[0]} | {delta[1]} | {stats.get('iou', '—')} |")
    lines += ['', 'dx/dy are signed CSS-pixel offsets from truth center. IoU is diagnostic only; it does not replace the original center-hit metric.', '', 'Sources:']
    lines.extend(f'- {path}' for path in diagnostic['sources'])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', nargs='+', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('artifacts/benchmarks/vision/dev-diagnostics'))
    args = parser.parse_args(argv)
    diagnostic = analyze(args.reports)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {'comparison.html': render_html(diagnostic), 'comparison.md': render_markdown(diagnostic),
               'comparison.json': json.dumps(diagnostic, ensure_ascii=False, indent=2) + '\n'}
    for name, content in outputs.items():
        path = args.output_dir / name
        path.write_text(content, encoding='utf-8')
        print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
