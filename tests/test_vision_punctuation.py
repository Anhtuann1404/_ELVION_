"""Punctuation recovery must independently read pixels and preserve ambiguity."""
import json
from elvion.vision.ocr import TextObservation
from elvion.vision.semantic import OCRPunctuationGrounder
from tests.test_vision_semantic import SemanticVisionTests, full, local


class PunctuationTests(SemanticVisionTests):
    def make_grounder(self, replies):
        old = super().make_grounder(replies)
        return OCRPunctuationGrounder(old.provider, old.ocr, cropper=old.cropper)

    def test_near_label_needs_blind_read_then_all_semantic_guards(self):
        g = self.make_grounder([json.dumps({'version':7,'text':'Save draft'}), full(), local()])
        box = (40.,60.,80.,20.)
        g.ocr.recognize.return_value = [TextObservation('Save draft.',box,.9)]
        self.assertEqual(g.locate(self.frame,target='Save draft',role='button').bbox,box)
        first = g.provider.complete.call_args_list[0].kwargs
        self.assertEqual(first['target'],'')
        self.assertNotIn('Save draft',json.dumps(first['candidates']))
        self.assertEqual(g.provider.complete.call_count,3)

    def test_real_punctuation_or_uncertainty_is_rejected(self):
        for text in ('Save draft.', '', 'Save drafts'):
            g=self.make_grounder([json.dumps({'version':7,'text':text})])
            g.ocr.recognize.return_value=[TextObservation('Save draft.',(40.,60.,80.,20.),.9)]
            self.assertEqual(g.locate(self.frame,target='Save draft',role='button').status,'not_found')
            self.assertEqual(g.provider.complete.call_count,1)

    def test_exact_and_near_duplicate_abstain_before_model(self):
        g=self.make_grounder([])
        g.ocr.recognize.return_value=[TextObservation(t,(40.,60.,80.,20.),.9)
                                    for t in ('Save draft','Save draft.')]
        self.assertEqual(g.locate(self.frame,target='Save draft',role='button').status,'ambiguous')
        g.provider.complete.assert_not_called()

    def test_internal_punctuation_spelling_and_multiple_marks_are_not_recovered(self):
        for text in ('Save. draft','Save drafts.','Save draft..','Save-draft'):
            g=self.make_grounder([])
            g.ocr.recognize.return_value=[TextObservation(text,(40.,60.,80.,20.),.9)]
            self.assertEqual(g.locate(self.frame,target='Save draft',role='button').status,'not_found')
            g.provider.complete.assert_not_called()

    def test_duplicate_plain_text_is_not_a_link_but_controls_stay_ambiguous(self):
        for roles, expected in ((('text','text'),'not_found'),
                                (('text','link'),'ambiguous'),
                                (('unknown',),'ambiguous'),
                                (('button',),'ambiguous')):
            g=self.make_grounder([local(role=role) for role in roles])
            g.ocr.recognize.return_value=[TextObservation('Open guide',box,.9) for box in
                                         ((40.,60.,80.,20.),(300.,350.,80.,20.))]
            result=g.locate(self.frame,target='Open guide',role='link')
            self.assertEqual(result.status,expected)
            self.assertIsNone(result.bbox)
            self.assertTrue(all(c.kwargs['role']=='actual_element_type'
                                for c in g.provider.complete.call_args_list))
