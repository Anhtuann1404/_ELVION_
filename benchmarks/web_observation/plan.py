"""Frozen observational run plans. All attempts retained; no best-of aggregation."""
import json
from math import ceil
from pathlib import Path
from statistics import median
import time
from urllib.parse import urlsplit
from uuid import uuid4

from benchmarks.web_observation.runner import digest, load_capture, write_json, evaluate_capture

SOURCES=tuple('src/elvion/vision/'+name for name in
              ('label_candidates.py','semantic.py','ocr.py','image_crop.py','recognize.swift','ollama.py','presentation.py')) + ('native/macos/ResizeImage.swift',)


def sources():
    root=Path(__file__).resolve().parents[2]
    return {name:digest((root/name).read_bytes()) for name in SOURCES}


def held_out_freeze():
    root=Path(__file__).resolve().parents[2]
    path=root/'configs/vision-web-heldout-freeze-v1.json'
    raw=path.read_bytes();freeze=json.loads(raw)
    if freeze['source_sha256']!=sources():raise ValueError('HELD_OUT_SOURCE_CHANGED')
    manifest=root/'benchmarks/web_observation_cases/cases.py'
    if freeze['manifest_sha256_file']!=digest(manifest.read_bytes()):
        raise ValueError('HELD_OUT_MANIFEST_CHANGED')
    return freeze,digest(raw)


def make_plan(directories, *, model='qwen3.5:4b', split='dev'):
    if split not in ('dev','held_out'):raise ValueError('INVALID_PLAN_SPLIT')
    freeze,freeze_hash=held_out_freeze() if split=='held_out' else (None,None)
    if freeze is not None and model!=freeze['model']:raise ValueError('HELD_OUT_MODEL_CHANGED')
    entries=[]
    for directory in directories:
        meta,frame=load_capture(directory)
        raw=(directory/'annotation.lock.json').read_bytes();annotation=json.loads(raw)
        if meta['split']!=split:raise ValueError('PLAN_SPLIT_MISMATCH')
        if split=='held_out':
            from benchmarks.web_observation_cases.cases import CASES,manifest_sha256
            case=next((c for c in CASES if c.id==meta['case_id']),None)
            if (case is None or case.split!=split or case.url!=meta['requested_url'] or
                case.target!=meta['target'] or case.role!=meta['role'] or
                meta['manifest_sha256']!=manifest_sha256()):
                raise ValueError('HELD_OUT_CASE_CHANGED')
            if list(directory.glob('proposal-*')):raise ValueError('HELD_OUT_PROPOSAL_ALREADY_VISIBLE')
        if (annotation['capture_sha256']!=digest((directory/'capture.json').read_bytes()) or
            annotation['image_sha256']!=meta['image_sha256']): raise ValueError('ANNOTATION_CHANGED')
        entries.append({'capture_id':directory.name,'case_id':meta['case_id'],'split':meta['split'],
            'domain':urlsplit(meta['final_url']).hostname,'image_sha256':meta['image_sha256'],
            'capture_sha256':digest((directory/'capture.json').read_bytes()),
            'annotation_sha256':digest(raw),'expected':annotation['expected_status'],
            'evidence_source':annotation['evidence_source'],'reviewer':annotation['reviewer']})
    if len({e['case_id'] for e in entries})!=len(entries): raise ValueError('DUPLICATE_PLAN_CASE')
    if split=='held_out' and {e['case_id'] for e in entries}!={c.id for c in CASES if c.split==split}:
        raise ValueError('HELD_OUT_CASES_INCOMPLETE')
    return {'schema_version':1,'model':model,'source_sha256':sources(),'entries':entries,
        'split':split,'freeze_sha256':freeze_hash,
        'actions':0,'scope':('frozen observational development plan; previously seen scenes, no blind claim'
            if split=='dev' else 'held-out observational pilot; user annotations plus assistant review/self-review; no actions'),
        'limitations':([] if split=='dev' else [
            'Chrome scene visibly degraded/unstyled; no claim about fully rendered website',
            'Three unique screenshots, twelve goals; not twelve independent scenes',
            'Annotations are not two independent human reviews; model weight digest not pinned'])}


def verify(plan,base):
    if plan['source_sha256']!=sources(): raise ValueError('GROUNDING_SOURCE_CHANGED')
    if plan.get('split')=='held_out':
        freeze,freeze_hash=held_out_freeze()
        if plan.get('freeze_sha256')!=freeze_hash or plan['model']!=freeze['model']:
            raise ValueError('HELD_OUT_FREEZE_CHANGED')
    for entry in plan['entries']:
        name=entry['capture_id']
        if Path(name).name!=name or not name.startswith('capture-'): raise ValueError('INVALID_CAPTURE_ID')
        directory=base/name
        meta,_=load_capture(directory)
        annotation=json.loads((directory/'annotation.lock.json').read_text())
        if (meta['case_id']!=entry['case_id'] or meta['image_sha256']!=entry['image_sha256'] or
            annotation['expected_status']!=entry['expected'] or meta['split']!=entry['split'] or
            digest((directory/'capture.json').read_bytes())!=entry['capture_sha256'] or
            digest((directory/'annotation.lock.json').read_bytes())!=entry['annotation_sha256']):
            raise ValueError('PLAN_INPUT_CHANGED')


def summarize(rows, entries):
    scorable=[e for e in entries if e['expected']!='undetermined']
    positive=[r for r in rows if r['expected']=='found']
    negative=[r for r in rows if r['expected']=='not_found']
    ambiguous=[r for r in rows if r['expected']=='ambiguous']
    def ratio(n,d):return {'numerator':n,'denominator':d,'value':n/d if d else None}
    def count(items,outcome):return sum(r['outcome']==outcome for r in items)
    times=sorted(r['locate_ms'] for r in rows)
    scenes={e['image_sha256'] for e in scorable}
    scene_results=[]
    for image_hash in sorted(scenes):
        selected=[e for e in scorable if e['image_sha256']==image_hash]
        observed=[r for r in rows if r['capture_id'] in {e['capture_id'] for e in selected}]
        complete=len(observed)==len(selected)
        scene_results.append({'image_sha256':image_hash,'planned_cases':len(selected),
            'observations':len(observed),'complete':complete,
            'all_observations_passed':complete and all(r['outcome'] in
                ('correct_target','correct_rejection') for r in observed)})
    return {'planned_cases':len(entries),'scorable_cases':len(scorable),
        'unscorable_cases':sum(e['expected']=='undetermined' for e in entries),
        'evaluated_observations':len(rows),'passed_observations':sum(r['outcome'] in
            ('correct_target','correct_rejection') for r in rows),
        'positive_hit':ratio(count(positive,'correct_target'),len(positive)),
        'false_abstention':ratio(count(positive,'false_abstention'),len(positive)),
        'wrong_target':ratio(count(positive,'wrong_target'),len(positive)),
        'negative_false_acceptance':ratio(count(negative,'false_acceptance'),len(negative)),
        'correct_ambiguity':ratio(count(ambiguous,'correct_rejection'),len(ambiguous)),
        'ambiguous_false_acceptances':count(ambiguous,'false_acceptance'),
        'grounder_errors':sum(r['outcome']=='grounder_error' for r in rows),
        'unique_scorable_image_hashes':len(scenes),
        'scene_results':scene_results,
        'scorable_domains':sorted({e['domain'] for e in scorable}),
        'median_locate_ms':median(times) if times else None,
        'p95_locate_ms_nearest_rank':times[ceil(.95*len(times))-1] if times else None,
        'all_scorable_evaluated':len(rows)==len(scorable),
        'generalization_gate_passed':False,
        'gate_reason':('Held-out pilot requires separate coverage and annotation assessment; this score never enables live actions'
            if entries and all(e['split']=='held_out' for e in entries) else
            'Development observations; held_out not evaluated; coverage and annotation review need separate assessment')}


def run_plan(path, *, evaluator=None):
    raw=path.read_bytes();plan=json.loads(raw);base=path.parent
    verify(plan,base)  # Validate ALL inputs before any inference.
    rows=[];failure=None
    output=base/('plan-run-'+uuid4().hex[:12]+'.json')
    def save():
        write={'plan_sha256':digest(raw),'plan_file':path.name,'source_sha256':plan['source_sha256'],
            'split':plan.get('split','dev'),'freeze_sha256':plan.get('freeze_sha256'),
            'limitations':plan.get('limitations',[]),
            'scope':plan['scope'],'actions':0,'entries':plan['entries'],'results':rows,
            'incomplete_reason':failure,'quality_valid':failure is None and
                len(rows)==sum(e['expected']!='undetermined' for e in plan['entries']),
            'summary':summarize(rows,plan['entries'])}
        # Each run owns a unique output; persist progress without touching old runs.
        temp=output.with_suffix('.pending')
        write_json(temp,write);temp.replace(output)
    save()
    try:
        if evaluator is None:
            from elvion.vision.ocr import AppleVisionOCR
            from elvion.vision.ollama import OllamaVisionProvider
            from elvion.vision.label_candidates import OCRLabelGrounder
            ocr=AppleVisionOCR(profile='upscale2x-v2');ocr.prepare()
            provider=OllamaVisionProvider(model=plan['model'],max_tokens=512);provider.check_local()
            grounder=OCRLabelGrounder(provider,ocr)
            evaluator=lambda directory:evaluate_capture(directory,grounder=grounder,model=plan['model'])
        for entry in plan['entries']:
            if entry['expected']=='undetermined':continue
            verify(plan,base)
            started=time.perf_counter()
            try:
                proposal=evaluator(base/entry['capture_id'])
            except Exception as error:
                rows.append({'case_id':entry['case_id'],'capture_id':entry['capture_id'],
                    'expected':entry['expected'],'outcome':'grounder_error',
                    'locate_ms':(time.perf_counter()-started)*1000,'proposal':None,
                    'error_type':type(error).__name__,'phase':'evaluation_exception',
                    'timing_scope':'whole failed evaluation, not isolated locate'})
                raise
            result=json.loads(proposal.read_text())
            if (result['source_sha256']!=plan['source_sha256'] or
                result['image_sha256']!=entry['image_sha256'] or
                result['annotation_sha256']!=entry['annotation_sha256']):
                rows.append({'case_id':entry['case_id'],'capture_id':entry['capture_id'],
                    'expected':entry['expected'],'outcome':'grounder_error',
                    'locate_ms':result['locate_ms'],'proposal':str(proposal.relative_to(base)),
                    'phase':'proposal_plan_mismatch'})
                raise ValueError('PROPOSAL_PLAN_MISMATCH')
            rows.append({'case_id':entry['case_id'],'capture_id':entry['capture_id'],
                'expected':entry['expected'],'outcome':result['outcome'],
                'locate_ms':result['locate_ms'],'proposal':str(proposal.relative_to(base))})
            save()
            print(f"{entry['case_id']}: {result['outcome']}",flush=True)
        verify(plan,base)
    except Exception as error:
        failure=type(error).__name__
        save()
        print(f'Incomplete run: {type(error).__name__}; all completed attempts retained.',flush=True)
    return output
