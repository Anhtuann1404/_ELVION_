import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from benchmarks.vision.runner import frame_for,load_cases
from benchmarks.web_observation.runner import digest,write_json,lock_annotation
from benchmarks.web_observation.plan import make_plan,run_plan,summarize,held_out_freeze


class ObservationPlanTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        frame=frame_for(load_cases()[0]);self.directories=[]
        for i,status in enumerate(('found','not_found','undetermined')):
            directory=self.base/f'capture-{i}';directory.mkdir();self.directories.append(directory)
            (directory/'frame.png').write_bytes(frame.image_png)
            write_json(directory/'capture.json',{'case_id':f'case{i}','capture_id':directory.name,
                'width':frame.width,'height':frame.height,'image_sha256':digest(frame.image_png),
                'target':'Example','role':'link','final_url':'https://example.com/','split':'dev'})
            lock_annotation(directory,status=status,truth=[[10,20,40,20]] if status=='found' else [],
                distractors=[],annotator='test',reviewer='reviewer',rationale='before inference')
        self.plan=make_plan(self.directories);self.path=self.base/'dev-plan.json';write_json(self.path,self.plan)

    def evaluator(self,directory):
        entry=next(e for e in self.plan['entries'] if e['capture_id']==directory.name)
        path=directory/'proposal-test.json'
        write_json(path,{'source_sha256':self.plan['source_sha256'],
            'image_sha256':entry['image_sha256'],'annotation_sha256':entry['annotation_sha256'],
            'outcome':'false_abstention' if entry['expected']=='found' else 'correct_rejection',
            'locate_ms':100})
        return path

    def test_all_attempts_retained_unscorable_skipped_and_no_best_of(self):
        evaluator=Mock(side_effect=self.evaluator)
        report=json.loads(run_plan(self.path,evaluator=evaluator).read_text())
        self.assertEqual(evaluator.call_count,2)
        self.assertEqual(report['summary']['unscorable_cases'],1)
        self.assertEqual(report['summary']['passed_observations'],1)
        self.assertEqual(report['summary']['positive_hit']['value'],0)
        self.assertFalse(report['summary']['generalization_gate_passed'])

    def test_changed_annotation_or_source_stops_before_inference(self):
        evaluator=Mock();p=self.directories[0]/'annotation.lock.json';p.write_text('{}')
        with self.assertRaises((KeyError,ValueError)):run_plan(self.path,evaluator=evaluator)
        evaluator.assert_not_called()

    def test_partial_run_retains_completed_observations(self):
        calls=[]
        def evaluate(directory):
            calls.append(directory)
            if len(calls)==2:raise RuntimeError('blocked')
            return self.evaluator(directory)
        report=json.loads(run_plan(self.path,evaluator=evaluate).read_text())
        self.assertEqual(len(report['results']),2)
        self.assertEqual(report['results'][1]['outcome'],'grounder_error')
        self.assertIsNotNone(report['incomplete_reason'])
        self.assertFalse(report['quality_valid'])

    def test_zero_denominators_are_not_perfect_scores(self):
        summary=summarize([],self.plan['entries'])
        self.assertIsNone(summary['positive_hit']['value'])
        self.assertIsNone(summary['median_locate_ms'])
        self.assertEqual(summary['unique_scorable_image_hashes'],1)

    def test_source_change_stops_before_any_evaluation(self):
        altered=json.loads(self.path.read_text())
        altered['source_sha256']={}
        self.path.write_text(json.dumps(altered))
        evaluator=Mock()
        with self.assertRaises(ValueError):run_plan(self.path,evaluator=evaluator)
        evaluator.assert_not_called()

    def test_mismatched_source_proposal_is_retained_as_invalid_not_accepted(self):
        def invalid(directory):
            path=self.evaluator(directory)
            result=json.loads(path.read_text());result['source_sha256']={}
            path.write_text(json.dumps(result))
            return path
        report=json.loads(run_plan(self.path,evaluator=invalid).read_text())
        self.assertFalse(report['quality_valid'])
        self.assertEqual(len(report['results']),1)
        self.assertEqual(report['results'][0]['phase'],'proposal_plan_mismatch')

    def held_out_directories(self):
        from benchmarks.web_observation_cases.cases import CASES,manifest_sha256
        png=(self.directories[0]/'frame.png').read_bytes();directories=[]
        original=json.loads((self.directories[0]/'capture.json').read_text())
        for case in CASES:
            if case.split!='held_out':continue
            directory=self.base/f'capture-{case.id}';directory.mkdir();directories.append(directory)
            (directory/'frame.png').write_bytes(png)
            write_json(directory/'capture.json',{'case_id':case.id,'capture_id':directory.name,
                'width':original['width'],'height':original['height'],'image_sha256':digest(png),
                'target':case.target,'role':case.role,'requested_url':case.url,
                'final_url':case.url,'split':case.split,'manifest_sha256':manifest_sha256()})
            lock_annotation(directory,status='not_found',truth=[],distractors=[],
                annotator='test',reviewer='reviewer',rationale='synthetic test only')
        return directories

    def test_held_out_plan_requires_complete_manifest_and_frozen_model(self):
        directories=self.held_out_directories()
        with patch('benchmarks.web_observation.plan.held_out_freeze',return_value=({'model':'qwen3.5:4b'},'freeze')):
            with self.assertRaisesRegex(ValueError,'CASES_INCOMPLETE'):
                make_plan(directories[:-1],split='held_out')
            with self.assertRaisesRegex(ValueError,'MODEL_CHANGED'):
                make_plan(directories,split='held_out',model='different')
            self.plan=make_plan(directories,split='held_out')
            self.path=self.base/'held-out.json';write_json(self.path,self.plan)
            report=json.loads(run_plan(self.path,evaluator=self.evaluator).read_text())
            self.assertTrue(report['quality_valid'])
            self.assertEqual(report['split'],'held_out')
            self.assertEqual(report['summary']['passed_observations'],12)
            self.assertFalse(report['summary']['generalization_gate_passed'])
            # A second plan must not silently reinterpret already seen cases as unseen.
            with self.assertRaisesRegex(ValueError,'PROPOSAL_ALREADY_VISIBLE'):
                make_plan(directories,split='held_out')
            evaluator=Mock()
            self.plan['freeze_sha256']='changed';self.path.write_text(json.dumps(self.plan))
            with self.assertRaisesRegex(ValueError,'FREEZE_CHANGED'):
                run_plan(self.path,evaluator=evaluator)
            evaluator.assert_not_called()

    def test_held_out_freeze_rejects_changed_source_before_inference(self):
        with patch('benchmarks.web_observation.plan.sources',return_value={}):
            with self.assertRaisesRegex(ValueError,'HELD_OUT_SOURCE_CHANGED'):
                held_out_freeze()

    def test_default_dev_plan_rejects_held_out_inputs(self):
        with self.assertRaisesRegex(ValueError,'PLAN_SPLIT_MISMATCH'):
            make_plan(self.held_out_directories())
