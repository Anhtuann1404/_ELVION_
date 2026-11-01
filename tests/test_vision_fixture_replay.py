import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from tests.test_vision_image_crop import png
from benchmarks.vision_labels.cases import CASES,manifest_sha256,render,WIDTH,HEIGHT
from benchmarks.web_observation.runner import digest
from benchmarks.vision_labels.replay import load_inputs,select_entries,run


class FixtureReplayTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        self.case=CASES[0];self.image=png(WIDTH,HEIGHT);(self.base/'frame.png').write_bytes(self.image)
        self.record={'frame_png':'frame.png','image_sha256':digest(self.image),'width':WIDTH,'height':HEIGHT,
            'frame_id':'fixture','target':self.case.target,'role':self.case.role,'ocr_calls':[]}
        self.diagnostic={'synthetic_only':True,'config':{'manifest_sha256':manifest_sha256()},'records':[self.record]}
        self.report={'config':{'manifest_sha256':manifest_sha256()},'results':[
            {'case_id':self.case.id,'html_sha256':digest(render(self.case).encode())}]}
        self.path=self.base/'fixture.diagnostics.json';self.save()

    def save(self):
        self.path.write_text(json.dumps(self.diagnostic))
        (self.base/'fixture.json').write_text(json.dumps(self.report))

    def test_saved_pixels_and_authored_geometry_are_separate_from_model_frame(self):
        rows,binding=load_inputs(self.path)
        case,record,capture=rows[0]
        self.assertEqual(capture.frame.image_png,self.image)
        self.assertEqual(case.id,self.case.id)
        self.assertFalse(hasattr(capture.frame,'truth_boxes'))
        self.assertEqual(len(capture.truth_boxes),1)
        self.assertEqual(binding['diagnostic_sha256'],digest(self.path.read_bytes()))

    def test_changed_image_goal_or_fixture_metadata_is_rejected(self):
        for update in ({'image_sha256':'changed'},{'target':'wrong'},{'width':WIDTH-1}):
            original=dict(self.record);self.record.update(update);self.save()
            with self.assertRaises(ValueError):load_inputs(self.path)
            self.record.clear();self.record.update(original)
        self.record['frame_png']='../outside.png';self.save()
        with self.assertRaisesRegex(ValueError,'INVALID_FRAME_PATH'):load_inputs(self.path)

    def test_selection_preserves_source_order_and_rejects_silent_omissions(self):
        rows,_=load_inputs(self.path)
        self.assertEqual(select_entries(rows,[self.case.id]),rows)
        for ids in ([],[self.case.id,self.case.id],['missing']):
            with self.subTest(ids=ids),self.assertRaises(ValueError):select_entries(rows,ids)

    def test_invalid_experiment_configuration_fails_before_backend(self):
        for config in ({'repetitions':True},{'repetitions':0},{'role_profile':'unknown'}):
            with self.subTest(config=config),self.assertRaises(ValueError):run(self.path,**config)
