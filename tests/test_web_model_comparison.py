import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch

from benchmarks.vision.runner import frame_for,load_cases
from benchmarks.web_observation.runner import digest,lock_annotation,write_json
from benchmarks.web_observation.compare_models import compare,CachedOCR
from elvion.browser.contracts import GroundingResult
from elvion.vision.ocr import OCRError


class ModelComparisonTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        self.frame=frame_for(load_cases()[0]);self.ids=(('one','a'),('two','b'))
        for capture,diagnostic in self.ids:
            directory=self.base/f'capture-{capture}';directory.mkdir()
            (directory/'frame.png').write_bytes(self.frame.image_png)
            write_json(directory/'capture.json',{'capture_id':directory.name,'case_id':capture,
                'width':self.frame.width,'height':self.frame.height,'target':'Example','role':'link',
                'image_sha256':digest(self.frame.image_png),'final_url':'https://example.com/',
                'split':'held_out'})
            lock_annotation(directory,status='found',truth=[[10,20,40,20]],distractors=[],
                annotator='fake',reviewer='fake',rationale='synthetic protocol test')
            write_json(directory/f'model-diagnostic-{diagnostic}.json',{'ocr_calls':[]})
        self.factory=Mock(side_effect=lambda **kw:SimpleNamespace(check_local=Mock(),complete=Mock()))
        self.unload=Mock();self.metadata=lambda p,m:{'digest':m,'size_bytes':1}

    def run_compare(self):
        return json.loads(compare(self.base,['first','second'],provider_factory=self.factory,
            helper=Path('/usr/bin/true'),metadata=self.metadata,unloader=self.unload).read_text())

    def grounder(self):
        return SimpleNamespace(last_diagnostics={},locate=lambda frame,**k:
            GroundingResult(frame.frame_id,'not_found',reason='TARGET_NOT_FOUND'))

    def test_same_inputs_all_attempts_and_cold_group_schedule_are_recorded(self):
        with patch('benchmarks.web_observation.compare_models.INPUTS',self.ids),patch(
                'benchmarks.web_observation.compare_models.OCRLabelGrounder',side_effect=lambda *a,**k:self.grounder()):
            report=self.run_compare()
        self.assertTrue(report['complete']);self.assertEqual(len(report['results']),4)
        self.assertEqual([r['model'] for r in report['results']],['first','first','second','second'])
        self.assertEqual(report['summaries']['first']['false_abstention']['denominator'],2)
        self.assertFalse(report['generalization_gate_passed']);self.assertEqual(self.unload.call_count,2)

    def test_missing_model_is_reported_before_any_inference(self):
        self.factory.side_effect=[SimpleNamespace(check_local=Mock(),complete=Mock()),RuntimeError('missing')]
        with patch('benchmarks.web_observation.compare_models.INPUTS',self.ids),patch(
                'benchmarks.web_observation.compare_models.OCRLabelGrounder') as grounder:
            report=self.run_compare()
        self.assertFalse(report['complete']);self.assertEqual(report['results'],[])
        grounder.assert_not_called()

    def test_model_digest_change_blocks_before_inference(self):
        calls=[]
        def metadata(p,m):
            calls.append(m)
            return {'digest':m if len(calls)<3 else 'changed'}
        self.metadata=metadata
        with patch('benchmarks.web_observation.compare_models.INPUTS',self.ids):report=self.run_compare()
        self.assertFalse(report['complete']);self.assertEqual(report['results'],[])

    def test_changed_input_retains_completed_observation_and_stops(self):
        def grounder(*a,**k):
            def locate(frame,**kw):
                path=self.base/'capture-two/model-diagnostic-b.json'
                path.write_text('{"ocr_calls":[],"changed":true}')
                return GroundingResult(frame.frame_id,'not_found',reason='TARGET_NOT_FOUND')
            return SimpleNamespace(last_diagnostics={},locate=locate)
        with patch('benchmarks.web_observation.compare_models.INPUTS',self.ids),patch(
                'benchmarks.web_observation.compare_models.OCRLabelGrounder',side_effect=grounder):report=self.run_compare()
        self.assertFalse(report['complete']);self.assertEqual(len(report['results']),1)

    def test_cached_query_and_image_are_bound_and_native_decoder_rejects_bad_boxes(self):
        rows=[{'profile':'upscale2x-v2','segments':True,'label_query':'Example',
               'lines':[{'text':'Example','confidence':1,'bbox':[10,20,40,20]}]}]
        cache=CachedOCR({'ocr_calls':rows},profile='upscale2x-v2',segments=True,
            helper=Path('/usr/bin/true'),image_sha256=digest(self.frame.image_png),target='Example')
        with self.assertRaises(OCRError):cache.recognize(self.frame)
        cache.label='Example';self.assertEqual(cache.recognize(self.frame)[0].text,'Example')
        rows[0]['lines'][0]['bbox']=[-100,20,40,20]
        with self.assertRaises(OCRError):cache.recognize(self.frame)
