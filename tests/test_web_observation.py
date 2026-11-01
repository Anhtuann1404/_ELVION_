import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from benchmarks.vision.runner import frame_for,load_cases
from benchmarks.web_observation.runner import (write_json,digest,lock_annotation,
    evaluate_capture,load_capture,viewer,score,capture)
from elvion.browser.contracts import GroundingResult


class WebObservationTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.frame=frame_for(load_cases()[0])
        (self.directory/'frame.png').write_bytes(self.frame.image_png)
        write_json(self.directory/'capture.json',{'capture_id':'test','case_id':'manual',
            'width':self.frame.width,'height':self.frame.height,'target':'Example',
            'role':'link','image_sha256':digest(self.frame.image_png)})

    def lock(self,**kwargs):
        return lock_annotation(self.directory,status=kwargs.get('status','found'),
            truth=kwargs.get('truth',[[10,20,100,30]]),distractors=[],
            annotator='test human',reviewer='test reviewer',rationale='reviewed original screenshot')

    def test_annotation_required_and_never_overwritten(self):
        g=Mock()
        with self.assertRaises(FileNotFoundError):evaluate_capture(self.directory,grounder=g,model='fake')
        g.locate.assert_not_called()
        self.lock()
        with self.assertRaises(FileExistsError):self.lock()

    def test_invalid_annotation_and_modified_image_fail(self):
        for truth in ([],[[10,20,0,5]],[[True,20,10,5]],[[790,20,100,30]]):
            with self.assertRaises(ValueError):self.lock(truth=truth)
        (self.directory/'frame.png').write_bytes(b'changed')
        with self.assertRaises(ValueError):load_capture(self.directory)

    def test_modified_metadata_cannot_use_locked_annotation(self):
        self.lock()
        p=self.directory/'capture.json';m=json.loads(p.read_text());m['target']='different';p.write_text(json.dumps(m))
        g=Mock()
        with self.assertRaises(ValueError):evaluate_capture(self.directory,grounder=g,model='fake')
        g.locate.assert_not_called()

    def test_pipeline_scores_wrong_proposal_and_withholds_oracle(self):
        self.lock()
        def locate(frame,**kwargs):
            self.assertEqual(kwargs,{'target':'Example','role':'link'})
            return GroundingResult(frame.frame_id,'found',bbox=(300,300,20,20))
        path=evaluate_capture(self.directory,grounder=SimpleNamespace(locate=locate),model='fake')
        report=json.loads(path.read_text());self.assertEqual(report['outcome'],'wrong_target')
        self.assertEqual(report['actions'],0);self.assertFalse(report['freshness_verified'])
        with self.assertRaises(ValueError):self.lock()

    def test_unscorable_does_not_invoke_grounder(self):
        self.lock(status='undetermined',truth=[]);g=Mock()
        with self.assertRaises(ValueError):evaluate_capture(self.directory,grounder=g,model='fake')
        g.locate.assert_not_called()

    def test_viewer_escapes_target_and_scores_errors_as_errors(self):
        self.assertIn('&lt;script&gt;',viewer(self.frame,target='<script>'))
        a={'expected_status':'not_found','truth_boxes':[],'distractor_boxes':[]}
        self.assertEqual(score(GroundingResult(self.frame.frame_id,'error',reason='PROVIDER_ERROR'),a,self.frame),'grounder_error')
        self.assertEqual(score(GroundingResult(self.frame.frame_id,'found',bbox=(10,10,10,10)),a,self.frame),'false_acceptance')

    def test_blocked_capture_has_no_quality_score(self):
        from unittest.mock import patch
        args=SimpleNamespace(url='https://example.com/',output_dir=self.directory,
            target='Example',role='link',case_id='manual')
        session=Mock();session.navigate.side_effect=ValueError('blocked')
        with patch('benchmarks.web_observation.runner.BrowserSession',return_value=session):
            with self.assertRaises(ValueError):capture(args)
        blocked=list(self.directory.glob('capture-*/blocked.json'))
        self.assertEqual(len(blocked),1)
        self.assertIsNone(json.loads(blocked[0].read_text())['quality_score'])
        session.snapshot.assert_not_called();session.close.assert_called_once()

    def test_dom_review_evidence_requires_identical_pixels_before_and_after(self):
        from benchmarks.web_observation.runner import review_dom
        meta=json.loads((self.directory/'capture.json').read_text())
        meta.update(requested_url='https://example.com/',final_url='https://example.com/')
        (self.directory/'capture.json').write_text(json.dumps(meta))
        for after_changed in (False,True):
            session=Mock();session.page.url='https://example.com/'
            session.snapshot.side_effect=[self.frame,SimpleNamespace(image_png=b'changed') if after_changed else self.frame]
            session.page.get_by_text.return_value.evaluate_all.return_value=[{'tag':'summary','role':'button','disabled':False,'bbox':[1,2,30,10]}]
            path=review_dom(self.directory,session_factory=Mock(return_value=session))
            report=json.loads(path.read_text())
            self.assertEqual(report['status'],'capture_changed' if after_changed else 'image_matched')
            self.assertEqual('candidates' in report,not after_changed)
            self.assertEqual(report['oracle_status'],'undetermined')
            session.close.assert_called_once()

    def test_ocr_diagnostic_retains_native_reply_on_protocol_error(self):
        from unittest.mock import patch
        from elvion.vision.ocr import OCRError
        from benchmarks.web_observation.runner import diagnose_ocr
        raw={'version':1,'lines':[{'text':'Example','confidence':1,'bbox':[1,2,900,10]}]}
        def backend(*,profile,runner):
            def recognize(frame):
                runner(['/fake/helper',profile],input=frame.image_png,capture_output=True)
                raise OCRError('OCR_FAILED')
            return SimpleNamespace(prepare=Mock(),recognize=recognize)
        with patch('elvion.vision.ocr.AppleVisionOCR',side_effect=backend),patch(
                'subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(raw).encode())):
            path=diagnose_ocr(self.directory)
        report=json.loads(path.read_text())
        self.assertFalse(report['model_called'])
        self.assertTrue(all(r['status']=='error' and r['native'][0]['response']==raw for r in report['rows']))

    def test_same_session_dom_capture_does_not_reopen_or_accept_changed_pixels(self):
        from unittest.mock import patch
        for changed in (False,True):
            session=Mock();session.page.url='https://example.com/';session.browser.version='test'
            session.snapshot.side_effect=[self.frame,SimpleNamespace(image_png=b'changed') if changed else self.frame]
            session.page.get_by_text.return_value.evaluate_all.return_value=[{'role':'link','bbox':[1,2,30,10]}]
            args=SimpleNamespace(url='https://example.com/',target='Example',role='link',
                                 case_id='manual',output_dir=self.directory,record_dom=True)
            before=set(self.directory.glob('capture-*'))
            with patch('benchmarks.web_observation.runner.BrowserSession',return_value=session):capture(args)
            directory=(set(self.directory.glob('capture-*'))-before).pop()
            evidence=json.loads((directory/'dom-at-capture.json').read_text())
            self.assertEqual(evidence['status'],'capture_changed' if changed else 'image_matched')
            self.assertEqual('candidates' in evidence,not changed)
            session.navigate.assert_called_once()
            session.close.assert_called_once()

    def test_shared_capture_binds_new_goal_without_reusing_oracle_or_scene(self):
        from benchmarks.web_observation.runner import derive_capture
        meta=json.loads((self.directory/'capture.json').read_text())
        meta.update(requested_url='https://example.com/',split='held_out',captured_at='fixed')
        (self.directory/'capture.json').write_text(json.dumps(meta))
        self.lock()
        case=SimpleNamespace(url='https://example.com/',split='held_out',id='second',target='Other',role='button')
        child=derive_capture(self.directory,case=case)
        self.addCleanup(__import__('shutil').rmtree,child)
        derived,_=load_capture(child)
        self.assertEqual(derived['image_sha256'],meta['image_sha256'])
        self.assertEqual(derived['captured_at'],'fixed')
        self.assertEqual(derived['target'],'Other')
        self.assertFalse((child/'annotation.lock.json').exists())
        self.assertFalse(list(child.glob('proposal-*')))
        case.url='https://different.example/'
        with self.assertRaises(ValueError):derive_capture(self.directory,case=case)
