"""Independent label oracle; fake grounders never see DOM or expected labels."""
from dataclasses import replace
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
from uuid import uuid4

from benchmarks.vision_labels.cases import CASES, WIDTH, HEIGHT, check_cases, manifest_sha256, render
from benchmarks.vision_labels.runner import Capture, assess, evaluate, write_report
from elvion.browser.contracts import GroundingResult, VisionFrame


def blank_png():
    def chunk(kind,payload):
        return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload))
    rows=(b'\0'+b'\xff'*(WIDTH*3))*HEIGHT
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',WIDTH,HEIGHT,8,2,0,0,0))+
            chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))


class SequenceGrounder:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def locate(self, frame, *, target, role):
        self.calls.append((frame, target, role))
        status, box = next(self.outputs)
        return GroundingResult(frame.frame_id, status, bbox=box)


class LabelBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image_frame = VisionFrame('fake','fake',0,blank_png(),WIDTH,HEIGHT,0.0)

    def capture(self, case):
        # Fake capture is only a scorer fixture. CLI --check-cases uses actual Chromium DOM boxes.
        frame = replace(self.image_frame, frame_id=uuid4().hex)
        truth = tuple((float(e.x),float(e.y),float(e.width),float(e.height))
                      for e in case.elements if e.id in case.truth_ids)
        other = tuple((float(e.x),float(e.y),float(e.width),float(e.height))
                      for e in case.elements if e.id not in case.truth_ids)
        return Capture(frame, truth, other)

    def test_fixed_manifest_is_balanced_distinct_and_semantically_labelled(self):
        self.assertEqual(check_cases(), CASES)
        self.assertEqual(len(CASES), 30)
        self.assertEqual([sum(c.split == split for c in CASES) for split in ('dev','held_out')], [15,15])
        self.assertEqual({c.expected for c in CASES}, {'found','not_found','ambiguous'})
        self.assertTrue(all(c.rationale for c in CASES))
        self.assertEqual(len(manifest_sha256()), 64)
        from benchmarks.browser_vision.cases import CASES as old
        from benchmarks.browser_vision.challenge import CASES as challenge
        self.assertFalse({c.target for c in CASES} & {c.target for c in (*old,*challenge)})
        self.assertNotIn('https://', render(CASES[0]))

    def test_correct_proposal_hits_positive_and_wrong_box_fails(self):
        case = CASES[0]
        capture = self.capture(case)
        good = GroundingResult(capture.frame.frame_id,'found',(215.,158.,190.,54.))
        wrong = GroundingResult(capture.frame.frame_id,'found',(600.,400.,40.,40.))
        outside = GroundingResult(capture.frame.frame_id,'found',(1250.,100.,80.,50.))
        self.assertEqual(assess(case,good,capture),'correct_target')
        self.assertEqual(assess(case,wrong,capture),'wrong_target')
        self.assertEqual(assess(case,outside,capture),'grounder_error')
        self.assertEqual(assess(case,GroundingResult('stale','found',(215.,158.,190.,54.)),capture),'grounder_error')

    def test_abstain_all_fails_positives_and_ambiguity_status_is_exact(self):
        positive = CASES[0]
        ambiguous = next(c for c in CASES if c.expected == 'ambiguous')
        missing = next(c for c in CASES if c.expected == 'not_found')
        p, a, m = self.capture(positive), self.capture(ambiguous), self.capture(missing)
        self.assertEqual(assess(positive,GroundingResult(p.frame.frame_id,'not_found'),p),'false_abstention')
        self.assertEqual(assess(ambiguous,GroundingResult(a.frame.frame_id,'not_found'),a),'wrong_abstention')
        self.assertEqual(assess(missing,GroundingResult(m.frame.frame_id,'ambiguous'),m),'wrong_abstention')
        self.assertEqual(assess(ambiguous,GroundingResult(a.frame.frame_id,'ambiguous'),a),'correct_ambiguity')

    def test_always_found_fails_negatives_and_near_distractor(self):
        near = next(c for c in CASES if c.id == 'vl_h11_plain_and_period')
        capture = self.capture(near)
        punct_only = next(c for c in CASES if c.id == 'vl_d11_missing_period')
        c = self.capture(punct_only)
        found = GroundingResult(c.frame.frame_id,'found',(180.,365.,190.,54.))
        self.assertEqual(assess(punct_only,found,c),'false_acceptance')
        self.assertEqual(assess(near,GroundingResult(capture.frame.frame_id,'not_found'),capture),'false_abstention')
        self.assertEqual(assess(near,GroundingResult(capture.frame.frame_id,'found',(925.,590.,180.,54.)),capture),
                         'wrong_target')

    def test_provider_error_never_counts_as_rejection(self):
        missing = next(c for c in CASES if c.expected == 'not_found')
        capture = self.capture(missing)
        self.assertEqual(assess(missing,GroundingResult(capture.frame.frame_id,'error',reason='MODEL_TIMEOUT'),capture),
                         'grounder_error')

    def test_evaluate_metrics_and_grounder_input_boundary(self):
        positive = CASES[0]
        missing = next(c for c in CASES if c.expected == 'not_found')
        ambiguous = next(c for c in CASES if c.expected == 'ambiguous')
        grounder = SequenceGrounder([('found',(215.,158.,190.,54.)),('not_found',None),('ambiguous',None)])
        report = evaluate([positive,missing,ambiguous],grounder=grounder,capture=self.capture)
        summary = report['summary']
        self.assertEqual((summary['observations'],summary['passed'],summary['correct_target_proposals']), (3,3,1))
        self.assertEqual(summary['positive_success_rate']['denominator'],1)
        self.assertEqual(summary['correct_ambiguity']['numerator'],1)
        self.assertEqual(len(grounder.calls),3)
        self.assertEqual(grounder.calls[0][1:],(positive.target,positive.role))
        self.assertFalse(any(hasattr(frame,'expected') or hasattr(frame,'truth_boxes') for frame,_,_ in grounder.calls))
        self.assertFalse(any(any(case.id in frame.frame_id for case in (positive,missing,ambiguous))
                             for frame,_,_ in grounder.calls))
        self.assertNotIn('<html',json.dumps(report['results']))
        self.assertNotIn(positive.target,json.dumps(report['results']))
        self.assertTrue(report['config']['synthetic_only'])
        self.assertEqual(report['config']['manifest_sha256'],manifest_sha256())
        abstainer = SequenceGrounder([('not_found',None),('not_found',None),('not_found',None)])
        failed = evaluate([positive,missing,ambiguous],grounder=abstainer,capture=self.capture)
        self.assertEqual(failed['summary']['false_abstentions'],1)
        self.assertEqual(failed['summary']['wrong_abstentions'],1)
        self.assertEqual(failed['summary']['passed'],1)

    def test_unique_private_reports_and_no_overwrite(self):
        case = CASES[0]
        report = evaluate([case],grounder=SequenceGrounder([('not_found',None)]),capture=self.capture)
        with tempfile.TemporaryDirectory() as directory:
            first = write_report(report,Path(directory))
            second = write_report(report,Path(directory))
            self.assertTrue(set(first).isdisjoint(second))
            self.assertTrue(all(path.stat().st_mode & 0o077 == 0 for path in (*first,*second)))
            self.assertEqual(json.loads(first[0].read_text())['summary']['false_abstentions'],1)


if __name__=='__main__': unittest.main()
