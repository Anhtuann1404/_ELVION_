import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from benchmarks.vision.runner import frame_for,load_cases
from benchmarks.vision_labels.cases import CASES
from benchmarks.vision_labels.diagnostics import RecordingGrounder
from benchmarks.vision_labels.runner import evaluate,Capture,write_report
from elvion.browser.contracts import GroundingResult
from elvion.vision.ocr import TextObservation


class LabelDiagnosticsTests(TestCase):
    def make(self):
        frame=frame_for(load_cases()[0])
        provider=SimpleNamespace(complete=Mock(return_value='{"version":7,"text":"Example"}'))
        ocr=SimpleNamespace(profile='upscale2x-v2',segments=False,label=None,
            recognize=Mock(return_value=[TextObservation('Example',(10.,20.,30.,20.),1)]))
        g=SimpleNamespace(provider=provider,ocr=ocr,last_diagnostics={},label_scale=2)
        def locate(frame,*,target,role):
            g.ocr.recognize(frame)
            provider.complete(image_png=frame.image_png,target='',role='transcribe_visible_label')
            return GroundingResult(frame.frame_id,'not_found',reason='TARGET_NOT_FOUND')
        g.locate=locate
        return frame,g

    def test_each_observation_keeps_its_own_frame_ocr_and_replies(self):
        frame,g=self.make();wrapped=RecordingGrounder(g)
        for _ in range(2):wrapped.locate(frame,target='Example',role='link')
        self.assertEqual(len(wrapped.records),2)
        self.assertEqual(len(wrapped.records[0]['ocr_calls']),1)
        self.assertEqual(len(wrapped.records[0]['model_calls']),1)
        self.assertEqual(wrapped.records[0]['frame_png'],frame.image_png)
        self.assertEqual(wrapped.records[0]['result']['status'],'not_found')
        self.assertNotIn('expected',wrapped.records[0]);self.assertNotIn('truth_boxes',wrapped.records[0])
        self.assertEqual(g.provider.complete.__name__,'record_model')

    def test_failed_provider_call_is_retained(self):
        frame,g=self.make();g.provider.complete.side_effect=RuntimeError('private details')
        wrapped=RecordingGrounder(g)
        with self.assertRaises(RuntimeError):wrapped.locate(frame,target='Example',role='link')
        row=wrapped.records[0]
        self.assertEqual(row['model_calls'][0]['error_type'],'RuntimeError')
        self.assertNotIn('private details',str(row))
        self.assertIsNone(wrapped.active)

    def test_opt_in_sidecar_preserves_pixels_and_default_report_stays_sanitized(self):
        frame,g=self.make();wrapped=RecordingGrounder(g)
        report=evaluate([CASES[0]],grounder=wrapped,capture=lambda c:Capture(frame,(),()))
        self.assertNotIn('Example',json.dumps(report))
        with TemporaryDirectory() as directory:
            root=Path(directory)
            plain,_=write_report(report,root)
            self.assertNotIn('diagnostics_file',json.loads(plain.read_text()))
            rich,_=write_report(report,root,diagnostic_records=wrapped.records)
            named=json.loads(rich.read_text())['diagnostics_file']
            raw=json.loads((root/named).read_text());record=raw['records'][0]
            self.assertEqual((root/record['frame_png']).read_bytes(),frame.image_png)
            self.assertEqual(raw['actions'],0)
            self.assertEqual((root/named).stat().st_mode & 0o077,0)
            self.assertNotIn('truth_boxes',record)
