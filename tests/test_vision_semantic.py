"""Independent semantic guards with strict fake model responses, no browser or inference."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from benchmarks.vision.runner import load_cases, frame_for
from elvion.vision.ocr import TextObservation
from elvion.vision.image_crop import CropError
from elvion.vision.semantic import OCRVerifiedGrounder, classification


def full(*, count='one', role='button', state='enabled'):
    return json.dumps({'version':5,'observed_role':role,'availability':state,'matching_labels':count})


def local(*, role='button', state='enabled'):
    return json.dumps({'version':6,'observed_role':role,'availability':state})


class SemanticVisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.frame=frame_for(load_cases()[0])

    def make_grounder(self, replies):
        provider=SimpleNamespace(complete=Mock(side_effect=replies),last_inference_ms=None)
        ocr=SimpleNamespace(helper='/synthetic/helper',recognize=Mock(return_value=[TextObservation('Save draft',(40.,60.,80.,20.),.9)]))
        return OCRVerifiedGrounder(provider,ocr,cropper=Mock(return_value=b'validated crop PNG'))

    def test_crop_role_must_match_and_requested_role_is_not_supplied_to_model(self):
        grounder=self.make_grounder([full(role='button'),local(role='textbox')])
        result=grounder.locate(self.frame,target='Save draft',role='button')
        self.assertEqual(result.status,'not_found')
        self.assertEqual(grounder.last_diagnostics['observed_role'],'textbox')
        calls=grounder.provider.complete.call_args_list
        self.assertEqual(calls[0].kwargs['role'],'classify_actual_type')
        self.assertEqual(calls[1].kwargs['role'],'actual_element_type')
        self.assertEqual(calls[0].kwargs['image_png'],self.frame.image_png)
        self.assertEqual(calls[1].kwargs['image_png'],b'validated crop PNG')
        grounder.cropper.assert_called_once_with(self.frame,(40.,60.,80.,20.),helper='/synthetic/helper')

    def test_matching_role_and_enabled_return_original_ocr_box(self):
        grounder=self.make_grounder([full(),local()])
        result=grounder.locate(self.frame,target='Save draft',role='button')
        self.assertEqual(result.bbox,(40.,60.,80.,20.))
        self.assertEqual(result.frame_id,self.frame.frame_id)

    def test_full_page_duplicates_abstain_even_when_ocr_only_found_one(self):
        grounder=self.make_grounder([full(count='multiple')])
        result=grounder.locate(self.frame,target='Save draft',role='button')
        self.assertEqual(result.status,'ambiguous')
        self.assertEqual(grounder.provider.complete.call_count,1)
        grounder.cropper.assert_not_called()

    def test_disabled_or_unknown_is_never_approved(self):
        for replies in ([full(state='disabled')],[full(count='unknown')],
                        [full(),local(state='disabled')],[full(),local(state='unknown')],
                        [full(),local(role='unknown')]):
            grounder=self.make_grounder(replies)
            result=grounder.locate(self.frame,target='Save draft',role='button')
            self.assertEqual(result.status,'not_found')

    def test_extra_action_fields_bad_versions_and_crop_failure_are_errors(self):
        for raw in ('{"version":true,"observed_role":"button","availability":"enabled","matching_labels":"one"}',
                    '{"version":5,"observed_role":"button","availability":"enabled","matching_labels":"one","click":[1,2]}',
                    '{"version":5,"observed_role":"button","availability":"enabled","matching_labels":"one","matching_labels":"multiple"}'):
            grounder=self.make_grounder([raw])
            self.assertEqual(grounder.locate(self.frame,target='Save draft',role='button').status,'error')
        grounder=self.make_grounder([full()]);grounder.cropper.side_effect=CropError('CROP_FAILED')
        self.assertEqual(grounder.locate(self.frame,target='Save draft',role='button').reason,'PROVIDER_ERROR')
        with self.assertRaises(ValueError): classification(local(),full=True)


if __name__=='__main__': unittest.main()
