"""Fixed role-presentation experiment: saved synthetic frames plus two public controls."""
import json
from pathlib import Path
import struct
import time
from uuid import uuid4

from elvion.browser.contracts import VisionFrame
from elvion.vision.ocr import AppleVisionOCR,normalized_label
from elvion.vision.image_crop import crop_context,context_rectangle
from elvion.vision.presentation import prepare_scaler,resize_crop
from elvion.vision.label_candidates import V4_LOCAL_SYSTEM
from elvion.vision.semantic import LOCAL_SCHEMA,classification
from elvion.vision.ollama import OllamaVisionProvider
from benchmarks.web_observation.compare_models import model_metadata,unload
from benchmarks.web_observation.runner import load_capture,digest,write_json
from benchmarks.web_observation.plan import sources

MARKER_NOTE=(' A red outline locates the candidate label. It is an annotation, not original UI. '
             'Classify ONLY the control at that outline, not a neighboring field or heading. ')
PROFILES=(('current',True,1),('unmarked',False,1),('marked2x',True,2),('unmarked2x',False,2))


def role_system(marked):
    if V4_LOCAL_SYSTEM.count(MARKER_NOTE)!=1:raise ValueError('ROLE_TEMPLATE_CHANGED')
    return V4_LOCAL_SYSTEM if marked else V4_LOCAL_SYSTEM.replace(MARKER_NOTE,'')


def build_subjects(root):
    b=root/'artifacts/benchmarks/vision-labels'
    path=b/'vision-labels-20261031T033137-e4158aca.diagnostics.json'
    data=json.loads(path.read_text());output=[]
    for i,(name,role) in enumerate((('Proceed','link'),('Save files','button'),('Methods','link'),('Status','link'))):
        record=data['records'][i];png=(b/record['frame_png']).read_bytes()
        if digest(png)!=record['image_sha256']:raise ValueError('FRAME_CHANGED')
        frame=VisionFrame(record['frame_id'],'role-diagnostic',0,png,record['width'],record['height'],time.monotonic())
        lines=record['ocr_calls'][0]['lines'];line=lines[1]
        output.append({'id':name,'frame':frame,'bbox':line['bbox'],'expected_role':role,
                       'input_sha256':digest(path.read_bytes())})
    web=root/'artifacts/benchmarks/web-observation'
    for capture,diagnostic,label,name in (
            ('capture-a885e567e9a8','f7fdaa6836a5','Latest published version:','metadata-control'),
            ('capture-23c487694c59','cc5602511322','GitHub Docs','heading-control')):
        _,frame=load_capture(web/capture);path=web/capture/f'model-diagnostic-{diagnostic}.json'
        data=json.loads(path.read_text())
        lines=data['ocr_calls'][0]['lines'];matches=[r for r in lines if normalized_label(r['text'])==normalized_label(label)]
        if len(matches)!=1:raise ValueError('CONTROL_CANDIDATE_NOT_UNIQUE')
        output.append({'id':name,'frame':frame,'bbox':matches[0]['bbox'],'expected_role':'text',
                       'input_sha256':digest(path.read_bytes())})
    return output


def run():
    root=Path(__file__).resolve().parents[2];subjects=build_subjects(root)
    helper=AppleVisionOCR();helper.prepare();scaler=prepare_scaler()
    provider=OllamaVisionProvider(model='qwen3.5:9b',max_tokens=512,timeout=120);provider.check_local()
    metadata=model_metadata(provider,provider.model)
    directory=root/'artifacts/benchmarks/vision-labels'/('role-presentation-'+uuid4().hex[:12]);directory.mkdir(mode=0o700)
    report={'scope':'Six seen diagnostic regions; four fixed local role presentations; not whole-pipeline or blind evaluation',
        'actions':0,'model':provider.model,'model_metadata':metadata,'source_sha256':sources(),
        'driver_sha256':digest(Path(__file__).read_bytes()),'profiles':PROFILES,'rows':[],'complete':False,
        'subjects':[{k:v for k,v in s.items() if k!='frame'} | {'image_sha256':digest(s['frame'].image_png)} for s in subjects]}
    write_json(directory/'plan.json',{k:v for k,v in report.items() if k!='rows'})
    def save():
        temp=directory/'report.pending';write_json(temp,report);temp.replace(directory/'report.json')
    save()
    try:
        for i,subject in enumerate(subjects):
            frame=subject['frame'];box=subject['bbox'];left,top,_,_=context_rectangle(frame,box,padding=96)
            for name,marked,factor in PROFILES[i%4:]+PROFILES[:i%4]:
                image=crop_context(frame,box,helper=helper.helper,padding=96,mark_bbox=marked)
                image=resize_crop(frame,image,factor=factor,helper=scaler)
                x,y,w,h=box;anchor=[(x-left)*factor,(y-top)*factor,w*factor,h*factor]
                key='bbox_css' if factor==1 else 'bbox_image_pixels'
                path=directory/(subject['id']+'-'+name+'.png');path.write_bytes(image);path.chmod(0o600)
                row={'subject':subject['id'],'profile':name,'expected_role':subject['expected_role'],
                     'image_sha256':digest(image),'dimensions':list(struct.unpack('>II',image[16:24]))}
                try:
                    raw=provider.complete(image_png=image,target='',role='actual_element_type',
                        schema=LOCAL_SCHEMA,system=role_system(marked),candidates=[{key:anchor}])
                    parsed=classification(raw,full=False)
                    row.update(response=parsed,match=parsed['observed_role']==subject['expected_role'],error=False)
                except Exception as error:row.update(match=False,error=True,error_type=type(error).__name__)
                report['rows'].append(row);save();print(subject['id'],name,row.get('response',row.get('error_type')),flush=True)
        if model_metadata(provider,provider.model)!=metadata:raise ValueError('MODEL_CHANGED')
        report['summary']={p[0]:{'matches':sum(r['match'] for r in report['rows'] if r['profile']==p[0]),
                               'attempts':sum(r['profile']==p[0] for r in report['rows'])} for p in PROFILES}
        report['complete']=True
    except Exception as error:report['incomplete_reason']=type(error).__name__
    finally:save();unload(provider,provider.model)
    print(f'Role presentation report: {directory}/report.json',flush=True)
    return directory/'report.json'


if __name__=='__main__':run()
