"""Seen-case comparison: cached desktop OCR, original pixels, unchanged live models/guards."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import time
from uuid import uuid4
from urllib.request import Request

from benchmarks.web_observation.plan import sources, summarize
from benchmarks.web_observation.runner import digest, load_capture, score, write_json
from elvion.vision.label_candidates import OCRLabelGrounder
from elvion.vision.ocr import AppleVisionOCR, OCRError
from elvion.vision.ollama import OllamaVisionProvider
from elvion.vision.presentation import prepare_scaler

INPUTS=(('23c487694c59','cc5602511322'),('a885e567e9a8','f7fdaa6836a5'),
        ('462805ae0235','b6be5ccdadfc'),('b4e60c379808','9ec3d499bacd'))


def inputs(base):
    entries=[]
    for capture, diagnostic in INPUTS:
        directory=base/f'capture-{capture}';meta,frame=load_capture(directory)
        annotation=directory/'annotation.lock.json'
        raw=annotation.read_bytes();oracle=json.loads(raw)
        if (oracle['capture_sha256']!=digest((directory/'capture.json').read_bytes()) or
                oracle['image_sha256']!=digest(frame.image_png)):
            raise ValueError('ANNOTATION_CHANGED')
        path=directory/f'model-diagnostic-{diagnostic}.json'
        entries.append({'capture_id':directory.name,'case_id':meta['case_id'],
            'expected':oracle['expected_status'],'split':'seen_case_regression',
            'domain':meta['final_url'].split('/')[2],'image_sha256':meta['image_sha256'],
            'capture_sha256':digest((directory/'capture.json').read_bytes()),
            'annotation_sha256':digest(raw),'diagnostic':path.name,
            'diagnostic_sha256':digest(path.read_bytes())})
    return entries


class CachedOCR:
    """Validate saved rows with the native decoder; never execute native OCR."""
    def __init__(self,saved,*,profile,segments,helper,image_sha256,target):
        self.profile,self.segments,self.helper=profile,segments,helper
        self.image_sha256,self.target,self.label=image_sha256,target,None
        self.rows=[r for r in saved['ocr_calls'] if r['profile']==profile and r['segments']==segments]

    def prepare(self):pass

    def recognize(self,frame):
        if digest(frame.image_png)!=self.image_sha256 or len(self.rows)!=1:
            raise OCRError('CACHED_OCR_INPUT_MISMATCH')
        row=self.rows[0]
        if self.segments and (row.get('label_query')!=self.target or self.label!=self.target):
            raise OCRError('CACHED_OCR_QUERY_MISMATCH')
        raw=json.dumps({'version':1,'lines':row['lines']}).encode()
        backend=AppleVisionOCR(profile=self.profile,runner=lambda *a,**k:
            SimpleNamespace(returncode=0,stdout=raw))
        backend.helper=self.helper
        lines=backend.recognize(frame)
        self.edge_adjustments=backend.edge_adjustments
        return lines


def unload(provider,model):
    provider._request('/api/generate',{'model':model,'keep_alive':0,'stream':False})


def model_metadata(provider,model):
    with provider._opener.open(Request(provider.base_url+'/api/tags',method='GET'),timeout=10) as response:
        raw=response.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('MODEL_METADATA_LIMIT')
    tags=json.loads(raw)
    matches=[m for m in tags.get('models',[]) if m.get('name')==model]
    if len(matches)!=1 or not matches[0].get('digest'):raise ValueError('MODEL_DIGEST_REQUIRED')
    return {'digest':matches[0]['digest'],'size_bytes':matches[0].get('size')}


def compare(base,models,*,provider_factory=OllamaVisionProvider,helper=None,unloader=unload,metadata=model_metadata,label_scale=1,role_marker=True,full_scale=1):
    if type(label_scale) is not int or label_scale not in (1,2,4):raise ValueError('INVALID_LABEL_SCALE')
    if type(role_marker) is not bool:raise ValueError('INVALID_ROLE_MARKER')
    if type(full_scale) is not int or full_scale not in (1,2):raise ValueError('INVALID_FULL_SCALE')
    if len(models)!=len(set(models)) or len(models)<2:raise ValueError('TWO_DISTINCT_MODELS_REQUIRED')
    entries=inputs(base);source=sources()
    report={'scope':'Four previously seen failure cases; cached desktop OCR + native crops + live model, not native end-to-end or blind evaluation',
        'actions':0,'source_sha256':source,'inputs':entries,'models':{},'results':[],
        'schedule':'blocked model order, one attempt per case; cold-start included; not statistically balanced',
        'config':{'max_tokens':512,'num_ctx':4096,'temperature':0,'timeout_seconds':120,'label_scale':label_scale,'role_marker':role_marker,'full_scale':full_scale},
        'limitations':['3 positive, 1 ambiguous; no absent-target negatives',
            'Model replacement requires wider negative/regression validation',
            'Cached OCR provenance relies on supplied diagnostic/capture association; hashes pinned at comparison preparation'],
        'complete':False,'generalization_gate_passed':False}
    path=base/f'model-comparison-{uuid4().hex[:12]}.json'
    def save():
        temporary=path.with_suffix('.pending');write_json(temporary,report);temporary.replace(path)
    save()
    try:
        providers={}
        # Model availability and digest checked before any comparison inference.
        for model in models:
            report['phase']='preflight';report['active_model']=model
            provider=provider_factory(model=model,max_tokens=512,timeout=120);provider.check_local()
            report['models'][model]=metadata(provider,model)
            providers[model]=provider
        if helper is None:
            native=AppleVisionOCR();native.prepare();helper=native.helper
        scaler=prepare_scaler() if label_scale!=1 or full_scale!=1 else None
        for model in models:
            report['phase']='inference';report['active_model']=model
            provider=providers[model]
            if metadata(provider,model)!=report['models'][model]:raise ValueError('MODEL_CHANGED')
            for entry in entries:
                if inputs(base)!=entries or sources()!=source:raise ValueError('COMPARISON_INPUT_CHANGED')
                directory=base/entry['capture_id'];meta,frame=load_capture(directory)
                saved=json.loads((directory/entry['diagnostic']).read_text())
                def backend(profile,segments=False):
                    return CachedOCR(saved,profile=profile,segments=segments,helper=helper,
                        image_sha256=entry['image_sha256'],target=meta['target'])
                calls=[];complete=provider.complete
                def recorded(**kwargs):
                    raw=complete(**kwargs)
                    calls.append({'phase':kwargs['role'],'image_sha256':digest(kwargs['image_png']),
                                  'response':json.loads(raw)})
                    return raw
                provider.complete=recorded
                start=time.perf_counter()
                try:
                    grounder=OCRLabelGrounder(provider,backend('upscale2x-v2'),
                        secondary_ocr=backend('native-v1'),span_ocr=backend('upscale2x-v2',True),
                        label_scale=label_scale,scaler=scaler,role_marker=role_marker,full_scale=full_scale)
                    result=grounder.locate(frame,target=meta['target'],role=meta['role'])
                    oracle=json.loads((directory/'annotation.lock.json').read_text())
                    row={'model':model,'capture_id':entry['capture_id'],'case_id':entry['case_id'],
                        'expected':entry['expected'],'outcome':score(result,oracle,frame),
                        'status':result.status,'reason':result.reason,'bbox':result.bbox,'calls':calls,
                        'diagnostics':grounder.last_diagnostics,'locate_ms':(time.perf_counter()-start)*1000}
                    report['results'].append(row);save()
                    print(f"{model} / {entry['case_id']}: {row['outcome']}",flush=True)
                finally:provider.complete=complete
            # Free the first model before loading the next on the 16GB machine.
            unloader(provider,model)
            if metadata(provider,model)!=report['models'][model]:raise ValueError('MODEL_CHANGED')
        if inputs(base)!=entries or sources()!=source:raise ValueError('COMPARISON_INPUT_CHANGED')
        report['summaries']={m:summarize([r for r in report['results'] if r['model']==m],entries) for m in models}
        for summary in report['summaries'].values():
            summary['gate_reason']='Four previously seen diagnostic cases; no absent-target negative coverage; not a generalization claim'
        report['phase']='completed'
        report['complete']=True
    except Exception as error:
        report['incomplete_reason']=type(error).__name__
    save();return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',nargs='+',default=['qwen3.5:4b','qwen3.5:9b'])
    parser.add_argument('--label-scale',type=int,choices=[1,2,4],default=1)
    parser.add_argument('--role-marker',choices=['on','off'],default='on')
    parser.add_argument('--full-scale',type=int,choices=[1,2],default=1)
    parser.add_argument('--base',type=Path,default=Path('artifacts/benchmarks/web-observation'))
    args=parser.parse_args();path=compare(args.base,args.models,label_scale=args.label_scale,role_marker=args.role_marker=='on',full_scale=args.full_scale)
    print(f'Comparison report: {path}')
    return 0 if json.loads(path.read_text())['complete'] else 2


if __name__=='__main__':raise SystemExit(main())
