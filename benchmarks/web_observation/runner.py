"""Capture -> annotate/lock -> offline proposal evaluation. No controller or input actions."""
import argparse
import base64
from datetime import datetime, timezone
from hashlib import sha256
import html
import json
from math import isfinite
from pathlib import Path
import time
import shutil
from uuid import uuid4

from elvion.browser.contracts import VisionFrame
from elvion.browser.session import BrowserSession, public_url


def digest(data): return sha256(data).hexdigest()


def write_json(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
    path.chmod(0o600)


def load_capture(directory):
    meta = json.loads((directory/'capture.json').read_text())
    png = (directory/'frame.png').read_bytes()
    if digest(png) != meta['image_sha256']:
        raise ValueError('CAPTURE_IMAGE_CHANGED')
    frame = VisionFrame(meta['capture_id'],meta['capture_id'],0,png,
                        meta['width'],meta['height'],time.monotonic())
    from elvion.vision.grounder import valid_png
    if not valid_png(frame): raise ValueError('INVALID_CAPTURE_IMAGE')
    if meta['role'] not in ('button','textbox','link') or not meta['target'].strip():
        raise ValueError('INVALID_CAPTURE_GOAL')
    return meta, frame


def boxes(raw, width, height):
    if type(raw) is not list or len(raw) > 32: raise ValueError('INVALID_BOXES')
    for box in raw:
        if (type(box) is not list or len(box) != 4 or
            any(type(v) not in (int,float) or not isfinite(v) for v in box) or
            min(box[:2]) < 0 or min(box[2:]) <= 0 or
            box[0]+box[2] > width or box[1]+box[3] > height):
            raise ValueError('INVALID_BOXES')
    return raw


def lock_annotation(directory, *, status, truth, distractors, annotator, rationale,
                    reviewer, evidence_source='vision_only'):
    meta, frame = load_capture(directory)
    # Annotation must precede ANY proposal artifacts in this capture directory.
    if list(directory.glob('proposal-*')): raise ValueError('PROPOSAL_ALREADY_VISIBLE')
    truth = boxes(truth, frame.width, frame.height)
    distractors = boxes(distractors, frame.width, frame.height)
    if (status not in ('found','not_found','ambiguous','undetermined') or
        (status == 'found' and len(truth) != 1) or
        (status == 'ambiguous' and len(truth) < 2) or
        (status in ('not_found','undetermined') and truth) or
        not annotator.strip() or not reviewer.strip() or not rationale.strip() or
        evidence_source not in ('vision_only','dom_assisted')):
        raise ValueError('INVALID_ANNOTATION')
    annotation = {'case_id':meta['case_id'],'capture_id':meta['capture_id'],
        'viewport':{'width':frame.width,'height':frame.height,'device_scale_factor':1},
        'capture_sha256':digest((directory/'capture.json').read_bytes()),
        'image_sha256':meta['image_sha256'],'expected_status':status,
        'truth_boxes':truth,'distractor_boxes':distractors,'annotator':annotator,
        'rationale':rationale,'locked_at':datetime.now(timezone.utc).isoformat(),
        'reviewer':reviewer,'evidence_source':evidence_source,
        'uncertain_reason':rationale if status=='undetermined' else None,
        'review_status':'locked'}
    write_json(directory/'annotation.lock.json', annotation)
    return annotation


def score(result, annotation, frame):
    expected = annotation['expected_status']
    if expected == 'undetermined': return 'unscorable'
    if result.frame_id != frame.frame_id or result.status == 'error': return 'grounder_error'
    if result.status != 'found':
        if expected == 'found': return 'false_abstention'
        return 'correct_rejection' if result.status == expected else 'wrong_abstention'
    if expected != 'found': return 'false_acceptance'
    x,y,w,h = result.bbox
    if x < 0 or y < 0 or x+w > frame.width or y+h > frame.height:
        return 'grounder_error'
    point = x+w/2,y+h/2
    def inside(b): return b[0] <= point[0] <= b[0]+b[2] and b[1] <= point[1] <= b[1]+b[3]
    return ('correct_target' if any(inside(b) for b in annotation['truth_boxes']) and
            not any(inside(b) for b in annotation['distractor_boxes']) else 'wrong_target')


def viewer(frame, *, target, result=None, annotation=None):
    # Local embedded image only. User-facing text is escaped; no remote resources.
    rectangles = ''
    if annotation:
        for b in annotation['truth_boxes']:
            rectangles += f'<rect x="{b[0]}" y="{b[1]}" width="{b[2]}" height="{b[3]}" fill="none" stroke="green" stroke-width="3"/>'
    if result is not None and result.status == 'found':
        x,y,w,h = result.bbox
        rectangles += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="red" stroke-width="3"/>'
    image = base64.b64encode(frame.image_png).decode()
    return f'''<!doctype html><meta charset="utf-8"><title>ELVION observation</title>
<h2>{html.escape(target)}</h2><p>Original CSS pixels: {frame.width} × {frame.height}.
Drag to measure a box; green = locked truth, red = model proposal. No browser actions.</p>
<pre id="box">[x,y,width,height]</pre>
<svg id="scene" width="{frame.width}" height="{frame.height}" viewBox="0 0 {frame.width} {frame.height}">
<image width="{frame.width}" height="{frame.height}" href="data:image/png;base64,{image}"/>{rectangles}</svg>
<script>
const scene=document.getElementById('scene');let start=null;
function point(e){{const p=scene.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(scene.getScreenCTM().inverse());}}
scene.onpointerdown=e=>{{start=point(e);scene.setPointerCapture(e.pointerId);}};
scene.onpointerup=e=>{{if(!start)return;const p=point(e);document.getElementById('box').textContent=JSON.stringify([Math.min(start.x,p.x),Math.min(start.y,p.y),Math.abs(p.x-start.x),Math.abs(p.y-start.y)].map(v=>Math.round(v*10)/10));start=null;}};
</script>'''


def capture(args):
    public_url(args.url)
    directory = args.output_dir / ('capture-'+uuid4().hex[:12])
    directory.mkdir(parents=True, mode=0o700)
    session = BrowserSession(headless=True)
    try:
        session.navigate(args.url, authorized=lambda:True)
        # Bounded settling only; do not dismiss overlays, scroll or manipulate the DOM.
        session.page.wait_for_timeout(1000)
        public_url(session.page.url)
        frame = session.snapshot()
        meta = {'capture_id':directory.name,'case_id':args.case_id,'requested_url':args.url,
            'split':getattr(args,'split','manual'),
            'manifest_sha256':getattr(args,'manifest_sha256',None),
            'browser_version':session.browser.version,'zoom':'default',
            'capture_status':'captured','overlay_review':'pending_human_annotation',
            'final_url':session.page.url,'captured_at':datetime.now(timezone.utc).isoformat(),
            'width':frame.width,'height':frame.height,'device_scale_factor':1,
            'target':args.target,'role':args.role,'image_sha256':digest(frame.image_png),
            'actions':0,'scope':'public page in isolated Chromium; no login/input/click'}
        (directory/'frame.png').write_bytes(frame.image_png)
        (directory/'frame.png').chmod(0o600)
        write_json(directory/'capture.json',meta)
        (directory/'original.html').write_text(viewer(frame,target=args.target))
        (directory/'original.html').chmod(0o600)
        if getattr(args,'record_dom',False):
            evidence={'capture_id':directory.name,'image_sha256':meta['image_sha256'],
                      'evidence_source':'dom_assisted','actions':0,'oracle_status':'undetermined',
                      'same_capture_session':True}
            try:
                candidates=read_dom_candidates(session.page,args.target)
                after=session.snapshot()
                if digest(after.image_png)==meta['image_sha256'] and session.page.url==meta['final_url']:
                    evidence.update(status='image_matched',candidates=candidates)
                else:
                    evidence['status']='capture_changed'
            except Exception as error:
                evidence.update(status='blocked',error_type=type(error).__name__)
            write_json(directory/'dom-at-capture.json',evidence)
        print(f'Capture: {directory}\nView original: {directory}/original.html')
        return directory
    except Exception as error:
        write_json(directory/'blocked.json',{'status':'blocked','phase':'capture',
            'error_type':type(error).__name__,'actions':0,'quality_score':None})
        raise ValueError(f'CAPTURE_BLOCKED; record: {directory}/blocked.json') from None
    finally:
        session.close()


def derive_capture(directory, *, case):
    """Same immutable screenshot, separate goal; never copy annotations/proposals."""
    meta,frame=load_capture(directory)
    if case.url!=meta['requested_url'] or case.split!=meta['split']:
        raise ValueError('DERIVED_GOAL_OUTSIDE_PAGE')
    child=directory.parent/('capture-'+uuid4().hex[:12]);child.mkdir(mode=0o700)
    meta.update(capture_id=child.name,case_id=case.id,target=case.target,role=case.role,
                shared_page_capture_id=meta.get('shared_page_capture_id',directory.name))
    shutil.copyfile(directory/'frame.png',child/'frame.png');(child/'frame.png').chmod(0o600)
    write_json(child/'capture.json',meta)
    (child/'original.html').write_text(viewer(frame,target=case.target))
    (child/'original.html').chmod(0o600)
    print(f'Capture: {child}\nView original: {child}/original.html')
    return child


def evaluate_capture(directory, *, grounder, model):
    meta, frame = load_capture(directory)
    annotation_bytes = (directory/'annotation.lock.json').read_bytes()
    annotation = json.loads(annotation_bytes)
    if (annotation['capture_sha256'] != digest((directory/'capture.json').read_bytes()) or
        annotation['image_sha256'] != meta['image_sha256']):
        raise ValueError('ANNOTATION_CAPTURE_CHANGED')
    boxes(annotation['truth_boxes'],frame.width,frame.height)
    boxes(annotation['distractor_boxes'],frame.width,frame.height)
    if annotation['expected_status'] == 'undetermined':
        raise ValueError('UNSCORABLE_CAPTURE; no model called')
    started = time.perf_counter()
    result = grounder.locate(frame,target=meta['target'],role=meta['role'])
    elapsed = (time.perf_counter()-started)*1000
    report = {'capture_id':meta['capture_id'],'case_id':meta['case_id'],
        'manifest_sha256':meta.get('manifest_sha256'),'split':meta.get('split','manual'),
        'image_sha256':meta['image_sha256'],'annotation_sha256':digest(annotation_bytes),
        'model':model,'grounder':'ocr-verified-v4','status':result.status,'reason':result.reason,
        'config':{'primary_ocr':'upscale2x-v2','secondary_ocr':'native-v1',
                  'label_crop_padding':12,'label_scale':getattr(grounder,'label_scale',1),
                  'label_marker':'leading_single_glyph_or_subline_hypotheses',
                  'role_crop_padding':96,'role_marker':getattr(grounder,'role_marker',True),
                  'full_scale':getattr(grounder,'full_scale',1),
                  'native_ocr_edge_tolerance_css':0.1,'subline_policy':'merged_label_native_query_even_with_existing_candidates',
                  'max_tokens':512,'device_scale_factor':1},
        'bbox':result.bbox,'outcome':score(result,annotation,frame),'locate_ms':elapsed,
        'actions':0,'offline_saved_image':True,'freshness_verified':False,
        'scope':'single proposal observation; not click or navigation verification'}
    root=Path(__file__).resolve().parents[2]
    from benchmarks.web_observation.plan import sources
    report['source_sha256']=sources()
    allowed={'candidate_count','verified_candidate_count','ocr_line_count','exact_match_count',
             'decision_stage','uncertainty_stage','label_verification','full_image_match_count',
             'full_observed_role','observed_role','availability','semantic_rejection','native_edge_adjustments','subline_ocr_passes','unresolved_merged_labels','label_scale','full_scale'}
    diagnostics=getattr(grounder,'last_diagnostics',{})
    report['diagnostics']={key:value for key,value in diagnostics.items()
        if key in allowed and type(value) in (str,int,bool)} if type(diagnostics) is dict else {}
    stem = 'proposal-'+uuid4().hex[:12]
    write_json(directory/(stem+'.json'),report)
    (directory/(stem+'.html')).write_text(viewer(frame,target=meta['target'],result=result,annotation=annotation))
    (directory/(stem+'.html')).chmod(0o600)
    return directory/(stem+'.json')


def diagnose_ocr(directory):
    """Explicit opt-in raw OCR of the already approved public-page capture, no model."""
    from dataclasses import asdict
    from elvion.vision.ocr import AppleVisionOCR, OCR_PROFILES, normalized_label
    meta,frame=load_capture(directory)
    rows=[]
    for profile in OCR_PROFILES:
        import subprocess
        native=[]
        def recording_run(*args,**kwargs):
            result=subprocess.run(*args,**kwargs)
            if 'input' in kwargs:
                item={'returncode':result.returncode}
                if type(result.stdout) is bytes and len(result.stdout)<=256*1024:
                    try: item['response']=json.loads(result.stdout.decode('utf-8'))
                    except (ValueError,UnicodeError): item['response_status']='invalid_json'
                native.append(item)
            return result
        ocr=AppleVisionOCR(profile=profile,runner=recording_run)
        try:
            ocr.prepare()
            lines=ocr.recognize(frame)
            row={'profile':profile,'status':'ok','exact_matches':sum(normalized_label(line.text)==
                normalized_label(meta['target']) for line in lines),'lines':[asdict(line) for line in lines],
                 'edge_adjustments':getattr(ocr,'edge_adjustments',0)}
        except Exception as error:
            row={'profile':profile,'status':'error','error_type':type(error).__name__,
                 'native':native}
        rows.append(row)
        print(f"{profile}: {row['status']}; exact_matches={row.get('exact_matches','unavailable')}")
    path=directory/('ocr-diagnostic-'+uuid4().hex[:12]+'.json')
    write_json(path,{'capture_id':meta['capture_id'],'image_sha256':meta['image_sha256'],
        'model_called':False,'actions':0,'target':meta['target'],'rows':rows})
    return path


def read_dom_candidates(page,target):
    return page.get_by_text(target,exact=True).evaluate_all('''els => els.slice(0,32).map(el => {
                const control=el.closest('button,a[href],input,textarea,select,summary,[role]') || el;
                const tag=control.tagName.toLowerCase();
                const declared=control.getAttribute('role');
                const inferred=tag==='summary'||tag==='button'?'button':tag==='a'&&control.hasAttribute('href')?'link':
                    tag==='textarea'||tag==='input'&&['text','search','email','url','tel','password',''].includes(control.type)?'textbox':'unknown';
                const b=control.getBoundingClientRect();
                return {tag,role:declared||inferred,disabled:control.matches(':disabled')||control.getAttribute('aria-disabled')==='true',
                    bbox:[b.x,b.y,b.width,b.height]};
            })''')


def review_dom(directory, *, session_factory=BrowserSession):
    """Supplemental oracle evidence only; never feed DOM to the grounder."""
    meta, frame = load_capture(directory)
    session = session_factory(headless=True)
    report = {'capture_id':meta['capture_id'],'image_sha256':meta['image_sha256'],
              'evidence_source':'dom_assisted','actions':0,'oracle_status':'undetermined'}
    try:
        session.navigate(meta['requested_url'],authorized=lambda:True)
        session.page.wait_for_timeout(1000)
        before = session.snapshot()
        if digest(before.image_png) != meta['image_sha256'] or session.page.url != meta['final_url']:
            report['status'] = 'capture_changed'
        else:
            candidates=read_dom_candidates(session.page,meta['target'])
            after = session.snapshot()
            if digest(after.image_png) != meta['image_sha256']:
                report['status'] = 'capture_changed'
            else:
                report.update(status='image_matched',candidates=candidates)
    except Exception as error:
        report.update(status='blocked',error_type=type(error).__name__)
    finally:
        session.close()
    path=directory/('dom-review-'+uuid4().hex[:12]+'.json')
    write_json(path,report)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    c=commands.add_parser('capture');c.add_argument('--url')
    c.add_argument('--target');c.add_argument('--role',choices=['button','textbox','link'])
    c.add_argument('--manifest-case',help='Case ID from Task B benchmarks.web_observation_cases.cases')
    c.add_argument('--page-cases',action='store_true',help='Bind all manifest goals on same URL/split to one saved screenshot')
    c.add_argument('--record-dom',action='store_true',help='Collect supplemental role evidence in this capture session; no model')
    c.add_argument('--case-id',default='manual');c.add_argument('--output-dir',type=Path,default=Path('artifacts/benchmarks/web-observation'))
    a=commands.add_parser('annotate');a.add_argument('directory',type=Path)
    a.add_argument('--status',choices=['found','not_found','ambiguous','undetermined'],required=True)
    a.add_argument('--truth',default='[]');a.add_argument('--distractors',default='[]')
    a.add_argument('--annotator',required=True);a.add_argument('--rationale',required=True)
    a.add_argument('--reviewer',required=True)
    a.add_argument('--evidence-source',choices=['vision_only','dom_assisted'],default='vision_only')
    e=commands.add_parser('evaluate');e.add_argument('directory',type=Path)
    e.add_argument('--model',default='qwen3.5:4b')
    e.add_argument('--repetitions',type=int,default=1)
    e.add_argument('--diagnose-model',action='store_true',help='Save raw model replies locally for this approved capture')
    r=commands.add_parser('review-dom');r.add_argument('directory',type=Path)
    o=commands.add_parser('diagnose-ocr');o.add_argument('directory',type=Path)
    p=commands.add_parser('evaluate-plan');p.add_argument('plan',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command=='capture':
            if args.page_cases and (not args.manifest_case or args.record_dom):
                raise ValueError('PAGE_CASES_REQUIRES_MANIFEST_AND_NO_DOM_RECORDING')
            if args.manifest_case:
                if args.url or args.target or args.role: raise ValueError('MANIFEST_GOAL_OVERRIDE_DENIED')
                from benchmarks.web_observation_cases.cases import CASES, check_cases, manifest_sha256
                check_cases()
                selected=[case for case in CASES if case.id==args.manifest_case]
                if len(selected)!=1: raise ValueError('UNKNOWN_MANIFEST_CASE')
                case=selected[0]
                args.url,args.target,args.role,args.case_id,args.split=case.url,case.target,case.role,case.id,case.split
                args.manifest_sha256=manifest_sha256()
            if not args.url or not args.target or not args.role: raise ValueError('URL_TARGET_ROLE_REQUIRED')
            directory=capture(args)
            if args.page_cases:
                for other in CASES:
                    if other.id!=case.id and other.url==case.url and other.split==case.split:
                        derive_capture(directory,case=other)
        elif args.command=='annotate':
            lock_annotation(args.directory,status=args.status,truth=json.loads(args.truth),
                distractors=json.loads(args.distractors),annotator=args.annotator,rationale=args.rationale,
                reviewer=args.reviewer,evidence_source=args.evidence_source)
            print('Annotation locked; grounder has not been called.')
        elif args.command=='review-dom':
            print(review_dom(args.directory))
        elif args.command=='diagnose-ocr':
            print(diagnose_ocr(args.directory))
        elif args.command=='evaluate-plan':
            from benchmarks.web_observation.plan import run_plan
            print(f'Plan report: {run_plan(args.plan)}')
        else:
            # Check locked input before preparing OCR or requesting inference.
            if not (args.directory/'annotation.lock.json').is_file(): raise ValueError('ANNOTATION_REQUIRED')
            from elvion.vision.ocr import AppleVisionOCR
            from elvion.vision.ollama import OllamaVisionProvider
            from elvion.vision.label_candidates import OCRLabelGrounder
            if not 1 <= args.repetitions <= 5: raise ValueError('REPETITIONS_MUST_BE_1_TO_5')
            if args.repetitions > 1 and not args.diagnose_model:
                raise ValueError('REPEATED_EVALUATION_REQUIRES_DIAGNOSE_MODEL')
            from dataclasses import asdict
            reports=[]
            for repetition in range(1,args.repetitions+1):
                calls=[]
                ocr_calls=[]
                def observed_ocr(profile, segments=False):
                    backend=AppleVisionOCR(profile=profile,segments=segments);backend.prepare()
                    recognize=backend.recognize
                    def recorded(frame):
                        lines=recognize(frame)
                        if args.diagnose_model:
                            ocr_calls.append({'profile':profile,'segments':segments,
                                              'label_query':getattr(backend,'label',None),
                                              'lines':[asdict(line) for line in lines]})
                        return lines
                    backend.recognize=recorded
                    return backend
                ocr=observed_ocr('upscale2x-v2')
                secondary=observed_ocr('native-v1')
                spans=observed_ocr('upscale2x-v2',segments=True)
                provider=OllamaVisionProvider(model=args.model,max_tokens=512)
                if args.diagnose_model:
                    complete=provider.complete
                    def traced(**kwargs):
                        raw=complete(**kwargs)
                        calls.append({'phase':kwargs['role'],'image_sha256':digest(kwargs['image_png']),
                                      'candidates':kwargs.get('candidates'),
                                      'response':json.loads(raw)})
                        return raw
                    provider.complete=traced
                proposal=evaluate_capture(args.directory,grounder=OCRLabelGrounder(
                    provider,ocr,secondary_ocr=secondary,span_ocr=spans),model=args.model)
                print(proposal)
                entry={'repetition':repetition,'proposal':proposal.name}
                if args.diagnose_model:
                    path=args.directory/('model-diagnostic-'+uuid4().hex[:12]+'.json')
                    write_json(path,{'actions':0,'scope':'local diagnostic on approved capture',
                                     'ocr_calls':ocr_calls,'model_calls':calls})
                    entry['diagnostic']=path.name
                    print(path)
                reports.append(entry)
            if args.repetitions>1:
                path=args.directory/('reproduction-'+uuid4().hex[:12]+'.json')
                write_json(path,{'actions':0,'same_saved_capture':True,'repetitions':reports,
                                 'scope':'all attempts retained; diagnostic repetitions, not independent scenes'})
                print(f'Reproduction: {path}')
    except Exception as error:
        parser.exit(2,f'Observation incomplete: {type(error).__name__}: {error}\n')
    return 0


if __name__=='__main__': raise SystemExit(main())
