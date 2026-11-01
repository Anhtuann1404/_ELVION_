"""Replay saved synthetic fixture pixels and OCR; no browser/native OCR or actions."""
import argparse
import json
from pathlib import Path
import time
from uuid import uuid4

from benchmarks.vision_labels.cases import CASES,manifest_sha256,render,WIDTH,HEIGHT
from benchmarks.vision_labels.runner import assess,Capture
from benchmarks.web_observation.runner import digest,write_json
from benchmarks.web_observation.plan import sources
from benchmarks.web_observation.compare_models import CachedOCR,model_metadata,unload
from elvion.browser.contracts import VisionFrame,GroundingResult
from elvion.vision.ocr import AppleVisionOCR
from elvion.vision.presentation import prepare_scaler
from elvion.vision.label_candidates import OCRLabelGrounder
from elvion.vision.ollama import OllamaVisionProvider
from benchmarks.vision_labels.role_profiles import ROLE_EVIDENCE_NOTE,with_role_profile


def load_inputs(path):
    data=json.loads(path.read_text());base=path.parent
    name=path.name.removesuffix('.diagnostics.json')+'.json'
    report_path=base/name;report=json.loads(report_path.read_text())
    if (data.get('synthetic_only') is not True or data['config']['manifest_sha256']!=manifest_sha256() or
            report['config']['manifest_sha256']!=manifest_sha256() or len(data['records'])!=len(report['results'])):
        raise ValueError('REPLAY_MANIFEST_MISMATCH')
    cases={case.id:case for case in CASES};entries=[]
    for result,record in zip(report['results'],data['records']):
        case=cases[result['case_id']];image=(base/record['frame_png']).resolve()
        if not image.is_relative_to(base.resolve()):raise ValueError('INVALID_FRAME_PATH')
        png=image.read_bytes()
        if (digest(png)!=record['image_sha256'] or record['target']!=case.target or record['role']!=case.role):
            raise ValueError('REPLAY_INPUT_CHANGED')
        if (record['width']!=WIDTH or record['height']!=HEIGHT or
                result['html_sha256']!=digest(render(case).encode())):
            raise ValueError('REPLAY_FIXTURE_CHANGED')
        frame=VisionFrame(record['frame_id'],'offline-fixture',0,png,record['width'],record['height'],time.monotonic())
        truth=tuple((e.x,e.y,e.width,e.height) for e in case.elements if e.id in case.truth_ids)
        distractors=tuple((e.x,e.y,e.width,e.height) for e in case.elements if e.id not in case.truth_ids)
        entries.append((case,record,Capture(frame,truth,distractors)))
    return entries,{'diagnostic_sha256':digest(path.read_bytes()),'report_sha256':digest(report_path.read_bytes())}


def select_entries(entries, case_ids=None):
    if case_ids is None:return entries
    if not case_ids or len(set(case_ids))!=len(case_ids):raise ValueError('INVALID_CASE_SELECTION')
    if set(case_ids)-{entry[0].id for entry in entries}:raise ValueError('UNKNOWN_REPLAY_CASE')
    return [entry for entry in entries if entry[0].id in case_ids]


def run(path,*,model='qwen3.5:9b',label_scale=2,role_marker=True,full_scale=1,
        case_ids=None,repetitions=1,role_profile='current',duplicate_text_check=False):
    if type(repetitions) is not int or not 1<=repetitions<=5:raise ValueError('INVALID_REPETITIONS')
    if role_profile not in ('current','visual-evidence-v1'):raise ValueError('INVALID_ROLE_PROFILE')
    entries,binding=load_inputs(path);source=sources()
    entries=select_entries(entries,case_ids)
    ocr=AppleVisionOCR();ocr.prepare();scaler=prepare_scaler() if label_scale!=1 or full_scale!=1 else None
    provider=OllamaVisionProvider(model=model,max_tokens=512,timeout=120);provider.check_local()
    metadata=model_metadata(provider,model)
    output=path.parent/('fixture-replay-'+uuid4().hex[:12]+'.json')
    report={'scope':'Previously seen synthetic fixtures; cached native OCR + original saved pixels + live model; not native OCR end-to-end or blind evaluation',
        'actions':0,'diagnostic_file':path.name,'binding':binding,'source_sha256':source,
        'model':model,'metadata':metadata,'label_scale':label_scale,'role_marker':role_marker,'full_scale':full_scale,
        'case_ids':[entry[0].id for entry in entries], 'repetitions':repetitions,
        'role_profile':role_profile,'role_evidence_note':ROLE_EVIDENCE_NOTE if role_profile!='current' else None,
        'duplicate_text_check':duplicate_text_check,
        'driver_sha256':digest(Path(__file__).read_bytes()),
        'planned_observations':len(entries)*repetitions,'rows':[],'complete':False}
    write_json(output.with_suffix('.plan.json'),{k:v for k,v in report.items() if k!='rows'})
    def save():
        temp=output.with_suffix('.pending');write_json(temp,report);temp.replace(output)
    save()
    try:
        for repetition,(case,record,capture) in ((n,e) for n in range(1,repetitions+1) for e in entries):
            _,current=load_inputs(path)
            if binding!=current or source!=sources():raise ValueError('REPLAY_INPUT_CHANGED')
            def backend(profile,segments=False):
                return CachedOCR(record,profile=profile,segments=segments,helper=ocr.helper,
                    image_sha256=record['image_sha256'],target=case.target)
            calls=[];complete=provider.complete
            profiled=with_role_profile(complete,role_profile)
            def traced(**kwargs):
                raw=profiled(**kwargs);calls.append({'phase':kwargs['role'],
                    'image_sha256':digest(kwargs['image_png']),'response':json.loads(raw)})
                return raw
            provider.complete=traced;start=time.perf_counter()
            try:
                grounder=OCRLabelGrounder(provider,backend('upscale2x-v2'),secondary_ocr=backend('native-v1'),
                    span_ocr=backend('upscale2x-v2',True),label_scale=label_scale,scaler=scaler,role_marker=role_marker,full_scale=full_scale,
                    duplicate_text_check=duplicate_text_check)
                result=grounder.locate(capture.frame,target=case.target,role=case.role)
                row={'case_id':case.id,'repetition':repetition,'expected':case.expected,'status':result.status,'reason':result.reason,
                    'bbox':result.bbox,'outcome':assess(case,result,capture),'diagnostics':grounder.last_diagnostics,
                    'calls':calls,'locate_ms':(time.perf_counter()-start)*1000}
                report['rows'].append(row);save();print(case.id,row['outcome'],flush=True)
            finally:provider.complete=complete
        if model_metadata(provider,model)!=metadata:raise ValueError('MODEL_CHANGED')
        report['passed']=sum(r['outcome'] in ('correct_target','correct_rejection','correct_ambiguity') for r in report['rows'])
        report['complete']=True
    except Exception as error:report['incomplete_reason']=type(error).__name__
    finally:save();unload(provider,model)
    print(f'Replay report: {output}',flush=True);return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('diagnostic',type=Path)
    parser.add_argument('--model',default='qwen3.5:9b')
    parser.add_argument('--label-scale',type=int,choices=[1,2,4],default=2)
    parser.add_argument('--role-marker',choices=['on','off'],default='on')
    parser.add_argument('--full-scale',type=int,choices=[1,2],default=1)
    parser.add_argument('--case',action='append',dest='case_ids')
    parser.add_argument('--repetitions',type=int,choices=range(1,6),default=1)
    parser.add_argument('--role-profile',choices=['current','visual-evidence-v1'],default='current')
    parser.add_argument('--duplicate-text-check',action='store_true')
    args=parser.parse_args();run(args.diagnostic,model=args.model,label_scale=args.label_scale,role_marker=args.role_marker=='on',full_scale=args.full_scale,
        case_ids=args.case_ids,repetitions=args.repetitions,role_profile=args.role_profile,duplicate_text_check=args.duplicate_text_check)


if __name__=='__main__':main()
