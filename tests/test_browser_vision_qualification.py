"""Qualification oracle and visual freshness guards; no real model or browser."""
import unittest
from unittest.mock import Mock

from benchmarks.browser_vision.cases import CASES, check_cases
from benchmarks.browser_vision.runner import assess, ObservedGrounder, Clock
from benchmarks.browser_vision.runner import summarize
from benchmarks.vision.runner import frame_for, load_cases
from elvion.browser.contracts import GroundingResult
from elvion.browser.controller import BrowserController
from elvion.browser.session import BrowserSession, BrowserError


class BrowserVisionQualificationTests(unittest.TestCase):
    def test_challenge_is_disjoint_and_wrong_role_still_requires_model_rejection(self):
        from benchmarks.browser_vision.challenge import CASES as challenge
        self.assertEqual(len(check_cases(challenge)),18)
        self.assertFalse({c.id for c in challenge} & {c.id for c in CASES})
        self.assertFalse({c.target for c in challenge} & {c.target for c in CASES})
        case=next(c for c in challenge if c.kind=='heading')
        result=GroundingResult('frame','not_found',reason='TARGET_NOT_FOUND')
        self.assertFalse(assess(case,result,'WEB_VISION_ABSTAINED',0,{'clicks':0,'target_clicks':0},
                               {'decision_stage':'ocr_no_exact_match'}))

    def test_refusing_all_positives_does_not_count_as_coverage(self):
        row={'expected':'click','pass':False,'observed':'not_found','mouse_attempts':0,'page_state':{'clicks':0,'target_clicks':0}}
        result=summarize([row,row])
        self.assertEqual(result['positive_success_rate'],0)
        self.assertEqual(result['false_abstention_rate'],1)
        self.assertEqual(result['false_abstentions'],2)

    @classmethod
    def setUpClass(cls):
        cls.frame = frame_for(load_cases()[0])

    def test_specs_are_new_and_cover_positive_negative_and_fault_cases(self):
        self.assertEqual(len(check_cases()),15)
        old_targets={case['target'] for case in load_cases()}
        self.assertTrue(all(case.target not in old_targets for case in CASES))
        self.assertEqual({case.expected for case in CASES},{'click','abstain','stale','revoked','expired'})

    def test_oracle_rejects_wrong_click_duplicates_and_error_as_abstention(self):
        found=GroundingResult('frame','found',(10.,10.,20.,20.))
        case=CASES[0]
        self.assertTrue(assess(case,found,None,1,{'clicks':1,'target_clicks':1}))
        self.assertFalse(assess(case,found,None,1,{'clicks':1,'target_clicks':0}))
        self.assertFalse(assess(case,found,None,2,{'clicks':2,'target_clicks':2}))
        self.assertFalse(assess(case,found,None,1,{'clicks':True,'target_clicks':True}))
        for case in CASES:
            if case.expected!='click':
                self.assertFalse(assess(case,found,'WEB_STALE_OR_UNAUTHORIZED',1,{'clicks':0,'target_clicks':0}))
        error=GroundingResult('frame','error',reason='MODEL_UNAVAILABLE')
        self.assertFalse(assess(CASES[-1],error,'WEB_STALE_OR_UNAUTHORIZED',0,{'clicks':0,'target_clicks':0}))

    def test_role_negatives_require_semantic_rejection_not_an_ocr_miss(self):
        case=next(case for case in CASES if case.id=='heading_wrong_role')
        absent=GroundingResult('frame','not_found',reason='TARGET_NOT_FOUND')
        state={'clicks':0,'target_clicks':0}
        self.assertFalse(assess(case,absent,'WEB_VISION_ABSTAINED',0,state,{'decision_stage':'ocr_no_exact_match'}))
        self.assertTrue(assess(case,absent,'WEB_VISION_ABSTAINED',0,state,{'decision_stage':'model_rejected_candidate'}))
        duplicate=next(case for case in CASES if case.kind=='duplicate')
        self.assertFalse(assess(duplicate,absent,'WEB_VISION_ABSTAINED',0,state))

    def test_visual_recheck_keeps_original_identity_and_detects_pixels_and_events(self):
        frame=self.frame
        session=BrowserSession()
        session.page=Mock()
        session.frame_id,session.page_id,session.revision=frame.frame_id,frame.page_id,frame.revision
        session.page.screenshot.return_value=frame.image_png
        self.assertTrue(session.frame_is_current(frame))
        self.assertEqual(session.frame_id,frame.frame_id)
        self.assertEqual(frame.captured_at,0.)
        session.page.screenshot.return_value=frame.image_png+b'different'
        self.assertFalse(session.frame_is_current(frame))
        def navigation_during_capture(**kwargs):
            session.invalidate()
            return frame.image_png
        session.page.screenshot.side_effect=navigation_during_capture
        self.assertFalse(session.frame_is_current(frame))

    def test_expiry_or_revocation_during_final_screenshot_prevents_click(self):
        frame=self.frame
        for fault in ('expire','revoke'):
            now,authority=[1.],[True]
            session=Mock(page_id=frame.page_id,revision=frame.revision,frame_id=frame.frame_id)
            session.snapshot.return_value=frame
            def visual_check(_):
                if fault=='expire':now[0]=20.
                else:authority[0]=False
                return True
            session.frame_is_current.side_effect=visual_check
            grounder=Mock()
            grounder.locate.return_value=GroundingResult(frame.frame_id,'found',(40.,60.,20.,20.))
            controller=BrowserController(session,grounder=grounder,clock=lambda:now[0])
            with self.assertRaisesRegex(BrowserError,'WEB_STALE_OR_UNAUTHORIZED'):
                controller.click_vision(target='Search',role='textbox',authorized=lambda:authority[0])
            session.page.mouse.click.assert_not_called()

    def test_fixture_mutation_does_not_leak_oracle_to_grounder(self):
        case=next(case for case in CASES if case.mutation=='move')
        base,session=Mock(),Mock()
        base.locate.return_value=GroundingResult(self.frame.frame_id,'found',(40.,60.,20.,20.))
        grounder=ObservedGrounder(base,case,session,[True],Clock())
        grounder.locate(self.frame,target=case.target,role=case.role)
        base.locate.assert_called_once_with(self.frame,target=case.target,role=case.role)
        session.page.evaluate.assert_called_once()
        session.invalidate.assert_not_called()


if __name__=='__main__':
    unittest.main()
