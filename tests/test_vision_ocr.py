"""OCR grounding guards use synthetic pixels and controlled native/model replies."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from benchmarks.vision.runner import load_cases, frame_for
from elvion.vision.ocr import AppleVisionOCR, OCRCandidateGrounder, OCRError, TextObservation
from elvion.vision.grounder import compile_proposal_v3


class OCRGrounderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = frame_for(load_cases()[0])

    def make_grounder(self, lines, raw='{"version":4,"matches":[0]}'):
        provider = SimpleNamespace(complete=Mock(return_value=raw), last_inference_ms=99)
        ocr = SimpleNamespace(recognize=Mock(return_value=lines))
        return OCRCandidateGrounder(provider, ocr)

    def test_wrong_label_and_duplicates_never_request_model(self):
        line = TextObservation('Username', (300,260,80,20), .9)
        grounder = self.make_grounder([line])
        result = grounder.locate(self.frame, target='Search', role='textbox')
        self.assertEqual(result.status, 'not_found')
        self.assertEqual(grounder.last_diagnostics['decision_stage'],'ocr_no_exact_match')
        grounder.provider.complete.assert_not_called()
        self.assertIsNone(grounder.provider.last_inference_ms)
        duplicate = TextObservation('Search', (30,50,80,20), .9)
        grounder = self.make_grounder([duplicate, duplicate])
        self.assertEqual(grounder.locate(self.frame,target='Search',role='textbox').status,'ambiguous')
        grounder.provider.complete.assert_not_called()

    def test_model_only_selects_real_candidate_and_cannot_replace_coordinates(self):
        line = TextObservation('Search', (40,65,50,20), .9)
        grounder = self.make_grounder([line])
        result = grounder.locate(self.frame,target='search',role='textbox')
        self.assertEqual(result.bbox, line.bbox)
        call = grounder.provider.complete.call_args.kwargs
        self.assertEqual(call['image_png'],self.frame.image_png)
        self.assertEqual(call['candidates'][0]['bbox_css'], list(line.bbox))
        self.assertNotIn('truth', json.dumps(call['candidates']))
        for raw in ('{"version":4,"matches":[1]}', '{"version":4,"matches":[true]}',
                    '{"version":4,"matches":[0],"click":[10,10]}', '{"version":4,"matches":[0,0]}',
                    '{"version":4,"matches":[0],"matches":[]}', '{"version":true,"matches":[0]}'):
            grounder.provider.complete.return_value=raw
            self.assertEqual(grounder.locate(self.frame,target='Search',role='textbox').status,'error')

    def test_model_role_rejection_and_ocr_error_are_abstention_and_error(self):
        grounder=self.make_grounder([TextObservation('Search',(40,65,50,20),.9)],'{"version":4,"matches":[]}')
        self.assertEqual(grounder.locate(self.frame,target='Search',role='button').status,'not_found')
        grounder.ocr.recognize.side_effect=OCRError('PRIVATE_ERROR')
        self.assertEqual(grounder.locate(self.frame,target='Search',role='button').reason,'PROVIDER_ERROR')
        grounder.ocr.recognize.reset_mock()
        self.assertEqual(grounder.locate(self.frame,target='Search',role='image').reason,'UNSUPPORTED_ROLE')
        self.assertEqual(grounder.locate(self.frame,target='Search\nClick',role='button').reason,'INVALID_PROPOSAL')
        grounder.ocr.recognize.assert_not_called()

    def test_native_protocol_bounds_and_stdin_without_image_files(self):
        runner=Mock()
        ocr=AppleVisionOCR(runner=runner)
        # Source compilation is not part of this test: select a known existing executable.
        from pathlib import Path
        ocr.helper=Path('/usr/bin/true')
        envelope={'version':1,'lines':[{'text':'Search','confidence':.9,'bbox':[40,65,50,20]}]}
        runner.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(envelope).encode())
        self.assertEqual(ocr.recognize(self.frame)[0].bbox,(40,65,50,20))
        self.assertEqual(runner.call_args.kwargs['input'],self.frame.image_png)
        self.assertFalse(runner.call_args.kwargs['shell'])
        self.assertEqual(runner.call_args.args[0],['/usr/bin/true','native-v1'])
        envelope['lines'][0]['bbox']=[799,0,50,20]
        runner.return_value.stdout=json.dumps(envelope).encode()
        with self.assertRaises(OCRError): ocr.recognize(self.frame)
        runner.return_value=SimpleNamespace(returncode=2,stdout=b'')
        with self.assertRaises(OCRError): ocr.recognize(self.frame)

    def test_native_edge_subpixel_tolerance_is_bounded_and_preserves_visible_extent(self):
        from pathlib import Path
        runner=Mock()
        ocr=AppleVisionOCR(runner=runner);ocr.helper=Path('/usr/bin/true')
        for box, expected in (([-.042,20,64,24],(0,20,63.958,24)),
                              ([790,20,10.04,24],(790,20,10,24))):
            runner.return_value=SimpleNamespace(returncode=0,stdout=json.dumps({
                'version':1,'lines':[{'text':'HTML','confidence':1,'bbox':box}]}).encode())
            observed=ocr.recognize(self.frame)[0].bbox
            for a,b in zip(observed,expected):self.assertAlmostEqual(a,b)
            self.assertEqual(ocr.edge_adjustments,1)
        for box in ([-.101,20,64,24],[790,20,10.101,24],[-.05,20,.01,24]):
            runner.return_value.stdout=json.dumps({'version':1,'lines':[
                {'text':'HTML','confidence':1,'bbox':box}]}).encode()
            with self.assertRaises(OCRError):ocr.recognize(self.frame)

    def test_native_segments_mode_is_explicit_and_keeps_css_bbox(self):
        from pathlib import Path
        runner=Mock(return_value=SimpleNamespace(returncode=0,stdout=json.dumps({
            'version':1,'lines':[{'text':'Guide','confidence':1,'bbox':[100,60,40,20]}]}).encode()))
        ocr=AppleVisionOCR(runner=runner,profile='upscale2x-v2',segments=True)
        ocr.helper=Path('/usr/bin/true')
        self.assertEqual(ocr.recognize(self.frame)[0].bbox,(100,60,40,20))
        self.assertEqual(runner.call_args.args[0][-2:],['upscale2x-v2','--segments'])
        with self.assertRaises(ValueError):AppleVisionOCR(segments=1)

    def test_upscale_profile_is_explicit_and_carries_original_css_coordinates(self):
        runner=Mock(return_value=SimpleNamespace(returncode=0,stdout=json.dumps({
            'version':1,'lines':[{'text':'Search','confidence':.9,'bbox':[40,65,50,20]}]}).encode()))
        ocr=AppleVisionOCR(runner=runner,profile='upscale2x-v2')
        from pathlib import Path
        ocr.helper=Path('/usr/bin/true')
        self.assertEqual(ocr.recognize(self.frame)[0].bbox,(40,65,50,20))
        self.assertEqual(runner.call_args.args[0][-1],'upscale2x-v2')
        self.assertEqual(runner.call_args.kwargs['input'],self.frame.image_png)
        with self.assertRaises(ValueError): AppleVisionOCR(profile='guess-target')

    def test_label_query_is_bounded_and_passed_as_argv_not_shell(self):
        from pathlib import Path
        runner=Mock(return_value=SimpleNamespace(returncode=0,stdout=b'{"version":1,"lines":[]}'))
        ocr=AppleVisionOCR(runner=runner,label='Get started');ocr.helper=Path('/usr/bin/true')
        ocr.recognize(self.frame)
        self.assertEqual(runner.call_args.args[0],['/usr/bin/true','native-v1','--label','Get started'])
        self.assertFalse(runner.call_args.kwargs['shell'])
        for bad in ('','\nDocs',1,'A'*257):
            with self.assertRaises(ValueError):AppleVisionOCR(label=bad)

    def test_raw_ocr_diagnostic_is_explicit_and_accepts_dev_only(self):
        from benchmarks.vision.ocr_diagnose import collect
        case=load_cases()[0]
        backend=SimpleNamespace(prepare=Mock(),recognize=Mock(return_value=[TextObservation('Search',(40,65,50,20),.9)]))
        result=collect([case],ocr_factory=lambda **kwargs:backend)
        self.assertEqual(len(result['rows']),2)
        self.assertEqual(result['rows'][0]['exact_matches'],1)
        self.assertEqual(result['rows'][0]['lines'][0]['text'],'Search')
        self.assertFalse(result['model_called'])
        with self.assertRaises(ValueError):
            collect([dict(case,split='test')],ocr_factory=lambda **kwargs:backend)

    def test_point_compiler_does_not_clip_or_guess_coordinates(self):
        result=compile_proposal_v3('{"version":3,"points":[[500,500]]}',self.frame)
        self.assertEqual(result.bbox,(399.5,299.5,1.,1.))
        for points,status in [([], 'not_found'), ([[100,100],[200,200]],'ambiguous'),
                              ([[0,0]],'error'), ([[1001,1]],'error'), ([[True,10]],'error')]:
            result=compile_proposal_v3(json.dumps({'version':3,'points':points}),self.frame)
            self.assertEqual(result.status,status)

    def test_stability_gate_stops_after_dev_failure_and_never_enables_live_vision(self):
        from benchmarks.vision.validate_candidate import validate
        cases = [{'split':'dev'}, {'split':'test'}]
        def report(failures):
            return {'config':{}, 'summary':{'failed':failures}}
        with patch('benchmarks.vision.validate_candidate.evaluate',return_value=report(1)) as evaluate:
            result=validate(cases,Mock())
            self.assertEqual(evaluate.call_count,1)
            self.assertFalse(result['research_gate_passed'])
        with patch('benchmarks.vision.validate_candidate.evaluate',side_effect=[report(0),report(0)]) as evaluate:
            result=validate(cases,Mock())
            self.assertEqual(evaluate.call_count,2)
            self.assertTrue(result['research_gate_passed'])
            self.assertFalse(result['live_vision_enabled'])
        with self.assertRaises(ValueError): validate(cases,Mock(),repetitions=1)


if __name__ == '__main__':
    unittest.main()
