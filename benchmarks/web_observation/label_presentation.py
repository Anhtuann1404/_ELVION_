"""Controlled blind-label presentation experiment on five known public-web regions."""
import json
from pathlib import Path
import struct
from types import SimpleNamespace
from uuid import uuid4

from benchmarks.web_observation.compare_models import inputs,CachedOCR,model_metadata,unload
from benchmarks.web_observation.plan import sources
from benchmarks.web_observation.runner import load_capture,digest,write_json
from elvion.vision.ocr import AppleVisionOCR,OCRCandidateGrounder,normalized_label
from elvion.vision.label_candidates import OCRLabelGrounder,needs_label_marker
from elvion.vision.semantic import READ_SCHEMA,READ_SYSTEM
from elvion.vision.image_crop import crop_context,context_rectangle
from elvion.vision.presentation import prepare_scaler,resize_crop
from elvion.vision.ollama import OllamaVisionProvider

# Prespecified before inference; every profile runs on every region exactly once.
PROFILES=(('current',12,1,True,'bbox_css'),('image_coords',12,1,True,'bbox_image_pixels'),
          ('unmarked',12,1,False,'bbox_image_pixels'),('upscale2',12,2,True,'bbox_image_pixels'),
          ('upscale4',12,4,True,'bbox_image_pixels'),('context96',96,1,True,'bbox_image_pixels'))


def read_system(marked):
    return READ_SYSTEM + (
        ' A red outline marks the OCR candidate label. Read ONLY inside that outline, '
        'not text elsewhere in this crop. The red outline is an annotation, not label content. '
        if marked else '') + (
        ' Distinguish adjacent pictographic UI icons from printed letters. '
        'Transcribe the label text, not a decorative icon. Preserve actual leading letters or initials.')


def subjects(base,entries,helper):
    output=[]
    for entry in entries:
        directory=base/entry['capture_id'];meta,frame=load_capture(directory)
        saved=json.loads((directory/entry['diagnostic']).read_text())
        def backend(profile,segments=False):
            return CachedOCR(saved,profile=profile,segments=segments,helper=helper,
                             image_sha256=entry['image_sha256'],target=meta['target'])
        g=OCRLabelGrounder(SimpleNamespace(last_inference_ms=None),backend('upscale2x-v2'),
            secondary_ocr=backend('native-v1'),span_ocr=backend('upscale2x-v2',True))
        g._current_frame=frame
        OCRCandidateGrounder._candidate(g,frame,target=meta['target'],role=meta['role'])
        if g._unresolved_merged:raise ValueError('UNRESOLVED_EXPERIMENT_REGION')
        oracle=json.loads((directory/'annotation.lock.json').read_text())
        for index,line in enumerate(g._hypotheses):
            x,y,w,h=line.bbox
            if not any(bx <= x+w/2 <= bx+bw and by <= y+h/2 <= by+bh
                       for bx,by,bw,bh in oracle['truth_boxes']):
                raise ValueError('EXPERIMENT_REGION_NOT_ANNOTATED')
            output.append({'id':entry['case_id']+f'-{index}','capture_id':entry['capture_id'],
                'bbox':list(line.bbox),'expected_text':meta['target'],
                'selective_marker':needs_label_marker(line.text,meta['target']) or line.bbox in g._subline_boxes})
    return output


def run(base=Path('artifacts/benchmarks/web-observation'),model='qwen3.5:9b'):
    entries=inputs(base);source=sources();ocr=AppleVisionOCR();ocr.prepare();scaler=prepare_scaler()
    region_plan=subjects(base,entries,ocr.helper)
    provider=OllamaVisionProvider(model=model,max_tokens=512,timeout=120);provider.check_local()
    metadata=model_metadata(provider,model)
    output=base/('label-presentation-'+uuid4().hex[:12]);output.mkdir(mode=0o700)
    report={'scope':'Five previously seen label regions; cached OCR + native presentation + live model; no role/grounding quality claim',
        'actions':0,'model':model,'model_metadata':metadata,'source_sha256':source,
        'inputs':entries,'regions':region_plan,'profiles':PROFILES,'rows':[],
        'schedule':'profiles rotated by region index; one attempt each; retain all outcomes',
        'complete':False,'generalization_gate_passed':False}
    def save():
        temp=output/'report.pending';write_json(temp,report);temp.replace(output/'report.json')
    # Lock all regions, profiles and expected transcription BEFORE inference.
    write_json(output/'plan.json',{k:v for k,v in report.items() if k not in ('rows','complete')})
    save()
    try:
        for i,region in enumerate(region_plan):
            _,frame=load_capture(base/region['capture_id']);box=region['bbox']
            order=PROFILES[i%len(PROFILES):]+PROFILES[:i%len(PROFILES)]
            for profile,padding,factor,use_marker,key in order:
                if inputs(base)!=entries or sources()!=source:raise ValueError('EXPERIMENT_INPUT_CHANGED')
                marked=use_marker and region['selective_marker']
                png=crop_context(frame,box,helper=ocr.helper,padding=padding,mark_bbox=marked)
                png=resize_crop(frame,png,factor=factor,helper=scaler)
                left,top,_,_=context_rectangle(frame,box,padding=padding)
                x,y,w,h=box;anchor=[(x-left)*factor,(y-top)*factor,w*factor,h*factor]
                image_path=output/(region['id']+'-'+profile+'.png');image_path.write_bytes(png);image_path.chmod(0o600)
                row={'region':region['id'],'profile':profile,'image':image_path.name,'image_sha256':digest(png),
                    'dimensions':list(struct.unpack('>II',png[16:24])),'marked':marked,
                    'anchor':{key:anchor},'expected_text':region['expected_text']}
                try:
                    raw=provider.complete(image_png=png,target='',role='transcribe_visible_label',
                        schema=READ_SCHEMA,system=read_system(marked),candidates=[{key:anchor}])
                    data=json.loads(raw)
                    if (type(data) is not dict or set(data)!={'version','text'} or
                            type(data['version']) is not int or data['version']!=7 or
                            type(data['text']) is not str or len(data['text'])>256):raise ValueError('INVALID_LABEL_READ')
                    row.update(response=data,match=normalized_label(data['text'])==normalized_label(region['expected_text']),
                               empty=not data['text'].strip(),error=False)
                except Exception as error:row.update(match=False,empty=False,error=True,error_type=type(error).__name__)
                row['inference_ms']=provider.last_inference_ms
                report['rows'].append(row);save()
                print(region['id'],profile,row.get('response',row.get('error_type')),flush=True)
        if model_metadata(provider,model)!=metadata:raise ValueError('MODEL_CHANGED')
        report['summary']={p[0]:{'matched':sum(r['match'] for r in report['rows'] if r['profile']==p[0]),
            'attempts':sum(r['profile']==p[0] for r in report['rows']),
            'empty':sum(r['empty'] for r in report['rows'] if r['profile']==p[0]),
            'errors':sum(r['error'] for r in report['rows'] if r['profile']==p[0])} for p in PROFILES}
        report['complete']=True
    except Exception as error:report['incomplete_reason']=type(error).__name__
    finally:
        save();unload(provider,model)
    print(f'Presentation report: {output}/report.json',flush=True)
    return output/'report.json'


if __name__=='__main__':run()
