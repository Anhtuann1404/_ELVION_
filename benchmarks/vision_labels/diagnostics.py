"""Explicit synthetic-only recording for offline diagnosis; never pass oracle to models."""
from dataclasses import asdict
from hashlib import sha256
import json

from elvion.vision.ocr import AppleVisionOCR


class RecordingGrounder:
    def __init__(self,grounder):
        self.grounder=grounder;self.records=[];self.active=None
        if hasattr(grounder,'span_ocr') and grounder.span_ocr is None:
            grounder.span_ocr=AppleVisionOCR(profile='upscale2x-v2',segments=True)
        seen=set()
        for name in ('ocr','secondary','span_ocr'):
            backend=getattr(grounder,name,None)
            if backend is None or id(backend) in seen:continue
            seen.add(id(backend));recognize=backend.recognize
            def recorded(frame,*,backend=backend,recognize=recognize):
                try:lines=recognize(frame)
                except Exception as error:
                    if self.active is not None:self.active['ocr_calls'].append({
                        'profile':getattr(backend,'profile','unknown'),'error_type':type(error).__name__})
                    raise
                if self.active is not None:self.active['ocr_calls'].append({
                    'profile':getattr(backend,'profile','unknown'),'segments':getattr(backend,'segments',False),
                    'label_query':getattr(backend,'label',None),'lines':[asdict(line) for line in lines]})
                return lines
            backend.recognize=recorded
        complete=grounder.provider.complete
        def record_model(**kwargs):
            try:raw=complete(**kwargs)
            except Exception as error:
                if self.active is not None:self.active['model_calls'].append({
                    'phase':kwargs['role'],'error_type':type(error).__name__})
                raise
            try:response=json.loads(raw)
            except (ValueError,TypeError):response={'invalid_json':True}
            if self.active is not None:self.active['model_calls'].append({
                'phase':kwargs['role'],'image_sha256':sha256(kwargs['image_png']).hexdigest(),
                'candidates':kwargs.get('candidates'),'response':response})
            return raw
        grounder.provider.complete=record_model

    def __getattr__(self,name):return getattr(self.grounder,name)

    def locate(self,frame,*,target,role):
        record={'frame_id':frame.frame_id,'width':frame.width,'height':frame.height,
            'image_sha256':sha256(frame.image_png).hexdigest(),'frame_png':frame.image_png,
            'target':target,'role':role,'ocr_calls':[],'model_calls':[]}
        self.active=record
        try:
            result=self.grounder.locate(frame,target=target,role=role)
            record['result']={'status':result.status,'reason':result.reason,'bbox':result.bbox}
            return result
        except Exception as error:
            record['error_type']=type(error).__name__;raise
        finally:
            self.records.append(record);self.active=None
