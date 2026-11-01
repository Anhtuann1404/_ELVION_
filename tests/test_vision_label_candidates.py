import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from benchmarks.vision.runner import frame_for, load_cases
from elvion.vision.ocr import TextObservation
from elvion.vision.label_candidates import OCRLabelGrounder, hypothesis
from tests.test_vision_semantic import full, local


def read(text): return json.dumps({'version':7,'text':text})


class LabelCandidatesTests(TestCase):
    @classmethod
    def setUpClass(cls): cls.frame=frame_for(load_cases()[0])

    def make(self, labels, replies, secondary=()):
        provider=SimpleNamespace(complete=Mock(side_effect=replies),last_inference_ms=None)
        lines=[TextObservation(text,(40.+i*220,60.,100.,20.),.9) for i,text in enumerate(labels)]
        ocr=SimpleNamespace(profile='upscale2x-v2',helper='fake',recognize=Mock(return_value=lines))
        second=SimpleNamespace(prepare=Mock(),recognize=Mock(return_value=list(secondary)))
        return OCRLabelGrounder(provider,ocr,secondary_ocr=second,cropper=Mock(return_value=b'crop'))

    def test_punctuation_distractor_is_read_and_not_selected(self):
        g=self.make(['Publish','Publish.'],[read('Publish'),local(),read('Publish.'),full(),local()])
        r=g.locate(self.frame,target='Publish',role='button')
        self.assertEqual(r.bbox,(40.,60.,100.,20.))
        for call in g.provider.complete.call_args_list:
            if call.kwargs['role']=='transcribe_visible_label':
                self.assertEqual(call.kwargs['target'],'')
                self.assertNotIn('text',call.kwargs['candidates'][0])

    def test_real_punctuation_is_not_removed_to_accept(self):
        g=self.make(['Publish.'],[read('Publish.')])
        self.assertEqual(g.locate(self.frame,target='Publish',role='button').status,'not_found')

    def test_true_duplicates_and_unknown_are_ambiguous(self):
        for replies in ([read('Publish'),local(),read('Publish'),local()],
                        [read('Publish'),local(),read('')]):
            g=self.make(['Publish','Publish.'],replies)
            self.assertEqual(g.locate(self.frame,target='Publish',role='button').status,'ambiguous')

    def test_duplicate_text_refinement_requires_every_full_region_to_be_text(self):
        prefix=[read('Open guide'),local(role='link'),read('Open guide'),local(role='link')]
        for checks,status in (([full(role='text',count='multiple')]*2,'not_found'),
                ([full(role='text',count='multiple'),full(role='link',count='multiple')],'ambiguous'),
                ([full(role='unknown',count='multiple')],'ambiguous'),
                ([full(role='text',count='one')],'ambiguous'),
                ([full(role='link',count='multiple')],'ambiguous')):
            g=self.make(['Open guide','Open guide'],prefix+checks);g.duplicate_text_check=True
            result=g.locate(self.frame,target='Open guide',role='link')
            self.assertEqual(result.status,status)
            self.assertIsNone(result.bbox)
            for call in g.provider.complete.call_args_list[4:]:
                self.assertEqual(call.kwargs['image_png'],self.frame.image_png)
                self.assertNotIn('link',call.kwargs['candidates'][0])

    def test_duplicate_refinement_never_resolves_uncertain_reads_or_bad_protocol(self):
        prefix=[read('Open guide'),local(role='link'),read('Open guide'),local(role='link')]
        g=self.make(['Open guide','Open guide'],prefix+['{"version":true}'])
        g.duplicate_text_check=True
        self.assertEqual(g.locate(self.frame,target='Open guide',role='link').status,'error')
        g=self.make(['Open guide','Open guide'],[read('Open guide'),local(role='link'),read('')])
        g.duplicate_text_check=True
        self.assertEqual(g.locate(self.frame,target='Open guide',role='link').status,'ambiguous')
        self.assertEqual(g.provider.complete.call_count,3)

    def test_native_and_upscale_same_region_are_merged(self):
        second=[TextObservation('Xem chi tiết?',(42.,60.,100.,20.),1)]
        g=self.make(['Xem chi tiêt?'],[read('Xem chi tiết?'),local(role='link'),
                                     full(role='link'),local(role='link')],second)
        self.assertEqual(g.locate(self.frame,target='Xem chi tiết?',role='link').status,'found')
        self.assertEqual(g.last_diagnostics['candidate_count'],1)

    def test_hypothesis_is_not_spelling_correction_and_bad_read_errors(self):
        self.assertTrue(hypothesis('Wait..!','Wait...!'))
        self.assertFalse(hypothesis('Wat...','Wait...!'))
        g=self.make(['Publish'],['{"version":7,"text":"Publish","click":true}'])
        self.assertEqual(g.locate(self.frame,target='Publish',role='button').status,'error')

    def test_exact_text_with_wrong_role_is_rejected(self):
        g=self.make(['Publish'],[read('Publish'),local(role='text')])
        self.assertEqual(g.locate(self.frame,target='Publish',role='button').status,'not_found')

    def test_contained_cross_profile_box_merges_but_separate_labels_do_not(self):
        from elvion.vision.label_candidates import same_region
        self.assertTrue(same_region((40.,50.,100.,50.),(50.,65.,80.,20.)))
        self.assertFalse(same_region((40.,50.,100.,50.),(150.,50.,100.,50.)))
        self.assertFalse(same_region((40.,50.,100.,50.),(90.,50.,100.,50.)))

    def test_known_wrong_role_does_not_require_enabled_state(self):
        g=self.make(['Open guide','Open guide'],
                    [read('Open guide'),local(role='text',state='unknown'),
                     read('Open guide'),local(role='text',state='unknown')])
        result=g.locate(self.frame,target='Open guide',role='link')
        self.assertEqual(result.status,'not_found')
        self.assertIsNone(result.bbox)

    def test_matching_role_with_unknown_availability_still_abstains(self):
        g=self.make(['Open guide'],[read('Open guide'),local(role='link',state='unknown'),
                                     full(role='link',state='unknown')])
        self.assertEqual(g.locate(self.frame,target='Open guide',role='link').status,'ambiguous')

    def test_local_evidence_reused_only_within_current_locate(self):
        g=self.make(['Publish'],[read('Publish'),local(),full()])
        self.assertEqual(g.locate(self.frame,target='Publish',role='button').status,'found')
        self.assertEqual(g.provider.complete.call_count,3)
        g.provider.complete.side_effect=[read('Publish'),local(role='text')]
        self.assertEqual(g.locate(self.frame,target='Publish',role='button').status,'not_found')
        self.assertEqual(g.last_diagnostics['decision_stage'],'model_rejected_candidate')

    def test_unknown_state_only_full_disabled_can_refine_refusal(self):
        for state, expected in [('disabled','not_found'),('enabled','ambiguous'),('unknown','ambiguous')]:
            g=self.make(['Publish'],[read('Publish'),local(state='unknown'),full(state=state)])
            self.assertEqual(g.locate(self.frame,target='Publish',role='button').status,expected)

    def test_leading_icon_hypothesis_does_not_strip_actual_letter(self):
        self.assertTrue(hypothesis('Q Tìm kiếm trên Wikipedia','Tìm kiếm trên Wikipedia'))
        self.assertFalse(hypothesis('Q Search','Search'))
        self.assertFalse(hypothesis('Extra Tìm kiếm trên Wikipedia','Tìm kiếm trên Wikipedia'))
        g=self.make(['A Save draft'],[read('A Save draft')])
        self.assertEqual(g.locate(self.frame,target='Save draft',role='button').status,'not_found')

    def test_role_classifier_is_anchored_to_candidate_not_neighbor(self):
        g=self.make(['Publish'],[read('Publish'),local(),full()])
        self.assertEqual(g.locate(self.frame,target='Publish',role='button').status,'found')
        call=g.provider.complete.call_args_list[1].kwargs
        self.assertEqual(call['role'],'actual_element_type')
        self.assertEqual(call['target'],'')
        self.assertEqual(len(call['candidates'][0]['bbox_css']),4)
        self.assertNotIn('button',json.dumps(call['candidates']))

    def test_full_frame_role_or_state_disagreement_vetoes_local_acceptance(self):
        for actual_role, state in [('text','enabled'),('button','enabled'),
                                   ('unknown','enabled'),('link','unknown'),('link','disabled')]:
            g=self.make(['Open guide'],[read('Open guide'),local(role='link'),
                                       full(role=actual_role,state=state)])
            r=g.locate(self.frame,target='Open guide',role='link')
            self.assertEqual(r.status,'not_found')
            self.assertIsNone(r.bbox)
            self.assertEqual(g.last_diagnostics['decision_stage'],'model_rejected_candidate')

    def test_full_frame_and_crop_both_agree_before_acceptance(self):
        g=self.make(['Open guide'],[read('Open guide'),local(role='link'),full(role='link')])
        self.assertEqual(g.locate(self.frame,target='Open guide',role='link').status,'found')

    def test_marker_policy_is_based_on_ocr_input_not_site_or_expected_answer(self):
        from elvion.vision.label_candidates import needs_label_marker
        self.assertTrue(needs_label_marker('Q Tìm kiếm trên Wikipedia','Tìm kiếm trên Wikipedia'))
        self.assertTrue(needs_label_marker('A Save draft','Save draft'))
        self.assertFalse(needs_label_marker('Tag;','Tag;'))
        self.assertFalse(needs_label_marker('Read policy.','Read policy'))
        self.assertFalse(needs_label_marker('Xem chi tiêt?','Xem chi tiết?'))
        g=self.make(['Tag;'],[read('Tag;'),local(role='textbox'),full(role='textbox')])
        self.assertEqual(g.locate(self.frame,target='Tag;',role='textbox').status,'found')
        self.assertNotIn('red outline',g.provider.complete.call_args_list[0].kwargs['system'])

    def test_merged_delimiter_line_uses_native_subline_box_not_whole_line(self):
        g=self.make(['Intro • Guide • Other'],[read('Guide'),local(role='link'),full(role='link')])
        box=(100.,60.,40.,20.)
        g.span_ocr=SimpleNamespace(prepare=Mock(),recognize=Mock(return_value=[TextObservation('Guide',box,.9)]))
        result=g.locate(self.frame,target='Guide',role='link')
        self.assertEqual(result.bbox,box)
        self.assertEqual(g.last_diagnostics['subline_ocr_passes'],1)
        self.assertIn('red outline',g.provider.complete.call_args_list[0].kwargs['system'])
        g.span_ocr.recognize.assert_called_once_with(self.frame)

    def test_subline_spelling_match_is_not_automatic_acceptance(self):
        g=self.make(['Intro • Guide • Other'],[read('Other')])
        g.span_ocr=SimpleNamespace(prepare=Mock(),recognize=Mock(return_value=[TextObservation('Guide',(100.,60.,40.,20.),.9)]))
        self.assertEqual(g.locate(self.frame,target='Guide',role='link').status,'not_found')

    def test_merged_duplicate_is_examined_even_with_existing_exact_candidate(self):
        g=self.make(['Docs','Docs Case studies Blog'],
                    [read('Docs'),local(role='link'),read('Docs'),local(role='link')])
        g.span_ocr=SimpleNamespace(prepare=Mock(),recognize=Mock(return_value=[
            TextObservation('Docs',(260.,60.,40.,20.),.9)]))
        self.assertEqual(g.locate(self.frame,target='Docs',role='link').status,'ambiguous')
        self.assertEqual(g.last_diagnostics['candidate_count'],2)
        self.assertEqual(g.span_ocr.label,'Docs')
        g.span_ocr.recognize.assert_called_once()

    def test_unresolved_merged_duplicate_cannot_be_overridden_by_model_one(self):
        g=self.make(['Docs','Docs Case studies Blog'],[read('Docs'),local(role='link'),full(role='link')])
        g.span_ocr=SimpleNamespace(prepare=Mock(),recognize=Mock(return_value=[]))
        self.assertEqual(g.locate(self.frame,target='Docs',role='link').status,'ambiguous')
        g.provider.complete.assert_not_called()
        self.assertEqual(g.last_diagnostics['decision_stage'],'unresolved_merged_label')

    def test_merged_line_without_delimiters_uses_native_geometry(self):
        g=self.make(['First Get started Other'],[read('Get started'),local(role='link'),full(role='link')])
        box=(90.,60.,40.,20.)
        g.span_ocr=SimpleNamespace(prepare=Mock(),recognize=Mock(return_value=[TextObservation('Get started',box,.9)]))
        self.assertEqual(g.locate(self.frame,target='Get started',role='link').bbox,box)

    def test_label_focus_and_role_anchor_use_separate_padding_and_original_full_frame(self):
        g=self.make(['Example label'],[read('Example label'),local(role='link'),full(role='link')])
        with patch('elvion.vision.label_candidates.crop_context',return_value=b'focused') as crop:
            g.cropper=crop
            self.assertEqual(g.locate(self.frame,target='Example label',role='link').status,'found')
        self.assertEqual(crop.call_args_list[0].kwargs['padding'],96)
        self.assertTrue(crop.call_args_list[0].kwargs['mark_bbox'])
        self.assertEqual(crop.call_args_list[1].kwargs['padding'],12)
        self.assertFalse(crop.call_args_list[1].kwargs['mark_bbox'])
        calls=g.provider.complete.call_args_list
        self.assertEqual(calls[0].kwargs['candidates'],[{'bbox_css':[12.,12.,100.,20.]}])
        self.assertEqual(calls[1].kwargs['candidates'],[{'bbox_css':[40.,60.,100.,20.]}])
        self.assertEqual(calls[2].kwargs['image_png'],self.frame.image_png)

    def test_scaled_label_coordinates_never_replace_original_target_box(self):
        g=self.make(['Publish'],[read('Publish'),local(),full()]);g.label_scale=2;g.scaler='/fake/scaler'
        with patch('elvion.vision.label_candidates.crop_context',return_value=b'small') as crop,patch(
                'elvion.vision.label_candidates.resize_crop',return_value=b'large') as resize:
            g.cropper=crop
            result=g.locate(self.frame,target='Publish',role='button')
        self.assertEqual(result.bbox,(40.,60.,100.,20.))
        calls=g.provider.complete.call_args_list
        self.assertEqual(calls[0].kwargs['image_png'],b'large')
        self.assertEqual(calls[0].kwargs['candidates'],[{'bbox_image_pixels':[24.,24.,200.,40.]}])
        self.assertEqual(calls[1].kwargs['candidates'],[{'bbox_css':[40.,60.,100.,20.]}])
        self.assertEqual(calls[2].kwargs['image_png'],self.frame.image_png)
        self.assertEqual(resize.call_args.kwargs['factor'],2)

    def test_near_word_is_not_treated_as_unresolved_merged_label(self):
        g=self.make(['Save files'],[])
        g.span_ocr=SimpleNamespace(prepare=Mock(),recognize=Mock(return_value=[]))
        self.assertEqual(g.locate(self.frame,target='Save file',role='button').status,'not_found')
        g.span_ocr.recognize.assert_not_called()
        g.provider.complete.assert_not_called()

    def test_merged_label_boundaries_keep_real_navigation_and_punctuation(self):
        from elvion.vision.label_candidates import embedded_label
        for text,target in [('Docs Case studies','Docs'),('Intro • Guide • Other','Guide'),
                            ('W3C Recommendation 12 December','W3C Recommendation'),
                            ('Publish. Next','Publish')]:
            self.assertTrue(embedded_label(text,target))
        for text,target in [('Save files','Save file'),('Search_box','Search'),
                            ('Guidebook','Guide'),('2027','7')]:
            self.assertFalse(embedded_label(text,target))

    def test_unmarked_role_profile_retains_label_and_full_frame_verification(self):
        g=self.make(['Publish'],[read('Publish'),local(),full()]);g.role_marker=False
        result=g.locate(self.frame,target='Publish',role='button')
        self.assertEqual(result.status,'found')
        self.assertFalse(g.cropper.call_args_list[0].kwargs['mark_bbox'])
        calls=g.provider.complete.call_args_list
        self.assertEqual([c.kwargs['role'] for c in calls],['transcribe_visible_label','actual_element_type','classify_actual_type'])
        self.assertNotIn('red outline',calls[1].kwargs['system'])
        self.assertEqual(calls[1].kwargs['target'],'')
        self.assertEqual(calls[2].kwargs['image_png'],self.frame.image_png)

    def test_scaled_full_frame_keeps_original_target_geometry_and_role_veto(self):
        for full_role,expected in [('button','found'),('text','not_found')]:
            g=self.make(['Publish'],[read('Publish'),local(),full(role=full_role)])
            g.full_scale=2;g.scaler='/fake/scaler'
            with patch('elvion.vision.label_candidates.resize_crop',return_value=b'large-full') as resize:
                result=g.locate(self.frame,target='Publish',role='button')
            self.assertEqual(result.status,expected)
            if expected=='found':self.assertEqual(result.bbox,(40.,60.,100.,20.))
            call=g.provider.complete.call_args_list[-1].kwargs
            self.assertEqual(call['image_png'],b'large-full')
            self.assertEqual(call['candidates'][0]['bbox_image_pixels'],[80.,120.,200.,40.])
            self.assertEqual(call['candidates'][0]['viewport_image_pixels'],[self.frame.width*2,self.frame.height*2])
            self.assertEqual(resize.call_args.args[1],self.frame.image_png)
