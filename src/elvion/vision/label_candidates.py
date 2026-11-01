"""Experimental dual-profile OCR hypotheses with independent, exact visual reads."""
import unicodedata

from elvion.browser.contracts import GroundingResult
from elvion.models.structured import strict_json
from elvion.vision.image_crop import context_rectangle, crop_context
from elvion.vision.presentation import resize_crop,prepare_scaler
from elvion.vision.ocr import AppleVisionOCR, OCRCandidateGrounder, normalized_label
from elvion.vision.semantic import (OCRVerifiedGrounder, FULL_SYSTEM, FULL_SCHEMA, LOCAL_SCHEMA,
                                   LOCAL_SYSTEM, READ_SCHEMA, READ_SYSTEM, classification)

ROLE_MARKER_NOTE = (' A red outline locates the candidate label. It is an annotation, not original UI. '
                    'Classify ONLY the control at that outline, not a neighboring field or heading. ')
V4_LOCAL_SYSTEM = LOCAL_SYSTEM + ROLE_MARKER_NOTE + (
    ' The supplied bbox locates the candidate label in crop coordinates. '
    'Classify the control surrounding that label, not neighboring controls. '
    'Navigation links can be blue labels grouped in a navigation or help row without an underline. '
    'Do not require an underline for link classification; use the surrounding navigation context. '
    'Color alone does not make a heading or ordinary prose a link; unclear evidence stays unknown. '
    ' Availability describes visible UI appearance, not proof of navigation or network success. '
    'For a link, evaluate its normal active navigation styling versus an explicitly muted, '
    'greyed or disabled appearance; a link need not have a button border to look enabled. '
    'An ordinary clearly rendered blue underlined navigation link with no disabled appearance '
    'is visually enabled. If the visual evidence is insufficient, keep unknown. '
    'Never infer availability from the wording or requested action.'
)


def role_system(marked):
    if type(marked) is not bool:raise ValueError('Invalid role marker')
    return V4_LOCAL_SYSTEM if marked else V4_LOCAL_SYSTEM.replace(ROLE_MARKER_NOTE,'')


def hypothesis(text, target):
    """Proposal generation only; never an acceptance or destructive normalization."""
    def skeleton(value):
        return ''.join(c for c in unicodedata.normalize('NFD', normalized_label(value))
                       if not unicodedata.combining(c) and c not in '.,;:!?')
    if skeleton(text) == skeleton(target):
        return True
    # Adjacent pictograms can be OCR'd as one leading glyph (e.g. magnifier).
    # This is a proposal only: independent reading still sees the entire region.
    words = normalized_label(text).split()
    return (len(normalized_label(target).split()) >= 2 and len(words) >= 3 and
            len(words[0]) == 1 and skeleton(' '.join(words[1:])) == skeleton(target))


def needs_label_marker(text, target):
    """Deterministic input policy, not a retry based on the model's answer."""
    words=normalized_label(text).split()
    return (len(words)>=3 and len(words[0])==1 and
            normalized_label(text)!=normalized_label(target) and
            hypothesis(' '.join(words[1:]),target))


def embedded_label(text,target):
    """A whole label in a merged line, never a prefix of another word."""
    text,target=normalized_label(text),normalized_label(target)
    if not target:return False
    start=text.find(target)
    while start!=-1:
        end=start+len(target)
        before=start==0 or text[start-1].isspace() or text[start-1] in '•·|'
        after=end==len(text) or not (text[end]=='_' or unicodedata.category(text[end])[0] in 'LNM')
        if before and after:return True
        start=text.find(target,start+1)
    return False


def overlap(a, b):
    x = max(0, min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0]))
    y = max(0, min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    intersection = x*y
    return intersection / (a[2]*a[3]+b[2]*b[3]-intersection)


def same_region(a, b):
    """Cross-profile boxes can differ in height while enclosing the same text."""
    if overlap(a, b) >= .5:
        return True
    intersection = (max(0, min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0])) *
                    max(0, min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1])))
    def center_inside(first, second):
        x, y = first[0]+first[2]/2, first[1]+first[3]/2
        return second[0] <= x <= second[0]+second[2] and second[1] <= y <= second[1]+second[3]
    return (intersection / min(a[2]*a[3], b[2]*b[3]) >= .8 and
            center_inside(a, b) and center_inside(b, a))


class OCRLabelGrounder(OCRVerifiedGrounder):
    protocol = 'ocr-verified-v4'

    def _full_evidence_permits(self, full, role):
        # Independent full-frame evidence is a veto, never merely diagnostic.
        return full['observed_role'] == role and full['availability'] == 'enabled'

    full_system = FULL_SYSTEM + (
        ' Count only EXACT labels, including every punctuation mark and accent. '
        'Labels differing by punctuation are different labels, not duplicate matches. '
        'Never remove punctuation or accents when counting.'
    )

    def __init__(self, provider, ocr, *, secondary_ocr=None, span_ocr=None, cropper=crop_context,
                 label_scale=1, scaler=None,role_marker=True,full_scale=1,duplicate_text_check=False):
        if type(label_scale) is not int or label_scale not in (1,2,4):
            raise ValueError('Invalid label scale')
        if type(role_marker) is not bool:raise ValueError('Invalid role marker')
        if type(full_scale) is not int or full_scale not in (1,2):raise ValueError('Invalid full scale')
        if type(duplicate_text_check) is not bool:raise ValueError('Invalid duplicate text check')
        super().__init__(provider, ocr, cropper=cropper)
        self.label_scale,self.scaler=label_scale,scaler
        self.role_marker=role_marker
        self.full_scale=full_scale
        self.duplicate_text_check=duplicate_text_check
        profile = 'native-v1' if getattr(ocr, 'profile', None) != 'native-v1' else 'upscale2x-v2'
        self.secondary = secondary_ocr if secondary_ocr is not None else AppleVisionOCR(profile=profile)
        self.span_ocr = span_ocr

    def _full_presentation(self,frame,candidate):
        if self.full_scale==1:return super()._full_presentation(frame,candidate)
        if self.scaler is None:self.scaler=prepare_scaler()
        image=resize_crop(frame,frame.image_png,factor=self.full_scale,helper=self.scaler)
        self.last_diagnostics['full_scale']=self.full_scale
        return image,{'id':0,'text':candidate.text,
            'bbox_image_pixels':[value*self.full_scale for value in candidate.bbox],
            'viewport_image_pixels':[frame.width*self.full_scale,frame.height*self.full_scale]}

    def _matching_lines(self, lines, target):
        self._subline_boxes=set()
        self._unresolved_merged=False
        self.secondary.prepare()
        alternatives = self.secondary.recognize(self._current_frame)
        self.last_diagnostics['native_edge_adjustments'] = (
            getattr(self.ocr,'edge_adjustments',0) + getattr(self.secondary,'edge_adjustments',0))
        # Merge the same physical text region across profiles, not separate controls.
        self._hypotheses = []
        for line in list(lines) + list(alternatives):
            if hypothesis(line.text, target):
                if not any(same_region(line.bbox, old.bbox) for old in self._hypotheses):
                    self._hypotheses.append(line)
        # Inspect merged lines even when another complete candidate already exists.
        # Otherwise labels in navigation rows can escape duplicate checks.
        merged=[line for line in list(lines)+list(alternatives)
                if embedded_label(line.text,target) and
                not hypothesis(line.text,target)]
        if merged:
            if self.span_ocr is None:
                self.span_ocr=AppleVisionOCR(profile=getattr(self.ocr,'profile','upscale2x-v2'),segments=True)
            self.span_ocr.label=target
            self.span_ocr.prepare()
            spans=self.span_ocr.recognize(self._current_frame)
            resolved=[]
            for line in spans:
                if hypothesis(line.text,target):
                    resolved.append(line)
                    if not any(same_region(line.bbox,old.bbox) for old in self._hypotheses):
                        self._hypotheses.append(line)
                        self._subline_boxes.add(line.bbox)
            def within(child,parent):
                x,y,w,h=child.bbox;px,py,pw,ph=parent.bbox
                return px <= x+w/2 <= px+pw and py <= y+h/2 <= py+ph
            self._unresolved_merged=any(not any(within(child,parent) for child in resolved) for parent in merged)
            self.last_diagnostics['subline_ocr_passes'] = 1
            self.last_diagnostics['unresolved_merged_labels']=self._unresolved_merged
        self.last_diagnostics['candidate_count'] = len(self._hypotheses)
        return self._hypotheses

    def _candidate(self, frame, *, target, role):
        self._candidate_local = None
        self._unresolved_merged = False
        self._current_frame = frame
        initial = OCRCandidateGrounder._candidate(self, frame, target=target, role=role)
        if self._unresolved_merged:
            self.last_diagnostics['decision_stage']='unresolved_merged_label'
            return GroundingResult(frame.frame_id,'ambiguous',reason='AMBIGUOUS_TARGET')
        if isinstance(initial, GroundingResult) and initial.status in ('error', 'not_found'):
            return initial
        if len(self._hypotheses) > 4:
            return GroundingResult(frame.frame_id, 'ambiguous', reason='AMBIGUOUS_TARGET')
        self.last_diagnostics['decision_stage'] = 'independent_label_read'
        matches, times = [], []
        semantic_rejections = 0
        uncertain = False
        for line in self._hypotheses:
            marked=needs_label_marker(line.text,target) or line.bbox in self._subline_boxes
            crop = self.cropper(frame, line.bbox, helper=self.ocr.helper,
                                padding=96, mark_bbox=self.role_marker)
            # Preserve broad UI context for role/state, but let transcription inspect
            # the label at higher relative resolution. Padding retains edge marks.
            if self.cropper is crop_context:
                label_crop = crop_context(frame, line.bbox, helper=self.ocr.helper, padding=12, mark_bbox=marked)
                left, top, _, _ = context_rectangle(frame, line.bbox, padding=12)
            else:
                label_crop = crop
                left, top, _, _ = context_rectangle(frame, line.bbox,padding=96)
            x, y, width, height = line.bbox
            anchor=[x-left,y-top,width,height]
            anchor_key='bbox_css'
            if self.label_scale!=1:
                if self.scaler is None:self.scaler=prepare_scaler()
                label_crop=resize_crop(frame,label_crop,factor=self.label_scale,helper=self.scaler)
                anchor=[value*self.label_scale for value in anchor]
                anchor_key='bbox_image_pixels'
                self.last_diagnostics['label_scale']=self.label_scale
            raw = self.provider.complete(image_png=label_crop, target='', role='transcribe_visible_label',
                schema=READ_SCHEMA, system=READ_SYSTEM +
                (' A red outline marks the OCR candidate label. Read ONLY inside that outline, '
                 'not text elsewhere in this crop. The red outline is an annotation, not label content. '
                 if marked else '') +
                ' Distinguish adjacent pictographic UI icons from printed letters. '
                'Transcribe the label text, not a decorative icon. Preserve actual leading letters or initials.',
                candidates=[{anchor_key:anchor}])
            times.append(self.provider.last_inference_ms)
            if type(raw) is not str or len(raw.encode('utf-8')) > 8192:
                raise ValueError('Invalid label read')
            read = strict_json(raw)
            if (type(read) is not dict or set(read) != {'version', 'text'} or
                    type(read['version']) is not int or read['version'] != 7 or
                    type(read['text']) is not str or len(read['text']) > 256):
                raise ValueError('Invalid label read')
            if not read['text'].strip():
                uncertain = True
                self.last_diagnostics['uncertainty_stage'] = 'empty_label_read'
            elif normalized_label(read['text']) == normalized_label(target):
                context_left, context_top, _, _ = context_rectangle(frame,line.bbox,padding=96)
                raw = self.provider.complete(image_png=crop, target='', role='actual_element_type',
                    schema=LOCAL_SCHEMA, system=role_system(self.role_marker),
                    candidates=[{'bbox_css':[x-context_left,y-context_top,width,height]}])
                times.append(self.provider.last_inference_ms)
                local = classification(raw, full=False)
                self.last_diagnostics.update(observed_role=local['observed_role'],
                                             availability=local['availability'])
                # A known wrong role is conclusive regardless of availability.
                # Ordinary text has no meaningful enabled/disabled state.
                if local['observed_role'] != 'unknown' and local['observed_role'] != role:
                    semantic_rejections += 1
                    self.last_diagnostics['semantic_rejection'] = 'wrong_role'
                    continue
                if local['observed_role'] == role and local['availability'] == 'unknown':
                    # A second, full-frame observation may prove disability;
                    # it must never turn an unknown local state into permission to act.
                    full_image,full_anchor=self._full_presentation(frame,line)
                    raw = self.provider.complete(image_png=full_image, target=target,
                        role='classify_actual_type', schema=FULL_SCHEMA,
                        system=self.full_system,
                        candidates=[full_anchor])
                    times.append(self.provider.last_inference_ms)
                    full = classification(raw, full=True)
                    if (full['matching_labels'] == 'one' and full['observed_role'] == role and
                            full['availability'] == 'disabled'):
                        semantic_rejections += 1
                        self.last_diagnostics['semantic_rejection'] = 'full_image_disabled'
                        continue
                if local['observed_role'] == 'unknown' or local['availability'] == 'unknown':
                    uncertain = True
                    self.last_diagnostics.update(uncertainty_stage='local_semantic_unknown',
                                                 observed_role=local['observed_role'],
                                                 availability=local['availability'])
                elif local['observed_role'] == role and local['availability'] == 'enabled':
                    matches.append(line)
                    self._candidate_local = (line.bbox, local)
                elif local['availability'] == 'disabled':
                    semantic_rejections += 1
                    self.last_diagnostics['semantic_rejection'] = 'local_disabled'
        self.provider.last_inference_ms = (sum(times) if all(type(t) in (int,float) for t in times) else None)
        self.last_diagnostics['verified_candidate_count'] = len(matches)
        if uncertain or len(matches) > 1:
            # Optional refusal refinement only: never select among duplicates or
            # use full-frame evidence to grant a previously rejected action.
            if not uncertain and len(matches)>1 and self.duplicate_text_check:
                text_only=True
                checked=0
                for line in matches:
                    image,anchor=self._full_presentation(frame,line)
                    raw=self.provider.complete(image_png=image,target=target,
                        role='classify_actual_type',schema=FULL_SCHEMA,
                        system=self.full_system,candidates=[anchor])
                    times.append(self.provider.last_inference_ms)
                    full=classification(raw,full=True)
                    checked+=1
                    if full['observed_role']!='text' or full['matching_labels']!='multiple':
                        text_only=False
                        break
                self.provider.last_inference_ms=(sum(times) if all(type(t) in (int,float) for t in times) else None)
                self.last_diagnostics['duplicate_text_checks']=checked
                if text_only:
                    self.last_diagnostics['decision_stage']='duplicate_full_image_text_rejection'
                    return GroundingResult(frame.frame_id,'not_found',reason='TARGET_NOT_FOUND')
            return GroundingResult(frame.frame_id, 'ambiguous', reason='AMBIGUOUS_TARGET')
        if not matches:
            self.last_diagnostics['decision_stage'] = ('model_rejected_candidate'
                if semantic_rejections else 'label_read_rejected')
            return GroundingResult(frame.frame_id, 'not_found', reason='TARGET_NOT_FOUND')
        self.last_diagnostics['label_verification'] = 'independent_image_read'
        return matches[0]

    def _local_evidence(self, candidate):
        cached = self._candidate_local
        return cached[1] if cached is not None and cached[0] == candidate.bbox else None
