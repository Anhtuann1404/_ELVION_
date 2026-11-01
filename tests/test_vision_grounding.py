"""Strict local viewport grounding with shared browser contract and no real model."""
from dataclasses import replace
import json
from math import nan
import unittest

from benchmarks.vision.runner import load_cases, frame_for, score
from elvion.browser.contracts import GroundingResult, VisionFrame
from elvion.vision.grounder import LocalVisionGrounder, compile_proposal, compile_proposal_v2, valid_png


class FakeProvider:
    def __init__(self, value='{"version":1,"status":"found","box":[100,200,200,100]}'):
        self.value, self.calls = value, []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        return self.value


class VisionGroundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = frame_for(load_cases()[0])

    def test_shared_contract_signature_and_conversion(self):
        provider = FakeProvider()
        result = LocalVisionGrounder(provider).locate(self.frame, target="Search", role="textbox")
        self.assertIsInstance(result, GroundingResult)
        self.assertEqual(result.frame_id, self.frame.frame_id)
        self.assertEqual(result.bbox, (80.0, 120.0, 160.0, 60.0))
        self.assertEqual(provider.calls[0]["image_png"], self.frame.image_png)
        self.assertNotIn("boxes", json.dumps(provider.calls[0]["schema"]))
        self.assertEqual(compile_proposal('{"version":1,"status":"found","box":[999,999,1,1]}', self.frame).bbox,
                         (799.2, 599.4, 0.8, 0.6))

    def test_v2_corners_are_explicit_and_default_v1_is_preserved(self):
        raw = '{"version":2,"boxes":[[750,800,1000,1000]]}'
        provider = FakeProvider(raw)
        result = LocalVisionGrounder(provider, protocol='xyxy-v2').locate(self.frame, target='Search', role='textbox')
        self.assertEqual(result.bbox, (600., 480., 200., 120.))
        self.assertEqual(provider.calls[0]['schema']['properties']['version']['const'], 2)
        self.assertEqual(provider.calls[0]['image_png'], self.frame.image_png)
        self.assertEqual(compile_proposal(raw, self.frame).status, 'error')
        self.assertEqual(LocalVisionGrounder(FakeProvider()).protocol, 'xywh-v1')
        with self.assertRaises(ValueError):
            LocalVisionGrounder(provider, protocol='auto-guess')

    def test_v2_multiple_matches_abstain_and_invalid_candidate_is_not_ignored(self):
        for boxes, status, reason in [([], 'not_found', 'TARGET_NOT_FOUND'),
                ([[10,20,30,40], [50,60,70,80]], 'ambiguous', 'AMBIGUOUS_TARGET'),
                ([[10,20,30,40], [999,0,1001,10]], 'error', 'INVALID_BOX')]:
            result = compile_proposal_v2(json.dumps({'version':2, 'boxes':boxes}), self.frame)
            self.assertEqual((result.status, result.reason, result.bbox), (status, reason, None))
        for box in ([-1,0,20,20], [0,0,1001,20], [1,2,1,20], [0,2,20,1]):
            self.assertEqual(compile_proposal_v2(json.dumps({'version':2,'boxes':[box]}), self.frame).reason, 'INVALID_BOX')

    def test_v2_rejects_actions_bad_types_and_protocol_confusion(self):
        proposals = [{'version': True, 'boxes': []}, {'version': 1, 'boxes': []},
            {'version': 2, 'boxes': [[0,0,True,10]]}, {'version': 2, 'boxes': [[0,0,10.,10]]},
            {'version': 2, 'boxes': None}, {'version': 2, 'boxes': [[0,0,10,10]] * 9},
            {'version': 2, 'boxes': [], 'click': [10,10]},
            {'version': 2, 'boxes': [], 'url': 'https://example.com'},
            {'version': 1, 'status':'found', 'box':[0,0,10,10]}]
        for proposal in proposals:
            with self.subTest(proposal=proposal):
                self.assertEqual(compile_proposal_v2(json.dumps(proposal), self.frame).status, 'error')
        for raw in ('{"version":2,"boxes":[],"boxes":[]}', '[]', '[' * 1200 + ']' * 1200):
            self.assertEqual(compile_proposal_v2(raw, self.frame).status, 'error')

    def test_invalid_frame_png_and_target_never_reach_provider(self):
        provider = FakeProvider()
        grounder = LocalVisionGrounder(provider)
        corrupt = bytearray(self.frame.image_png)
        corrupt[-8] ^= 1
        self.assertEqual(grounder.locate(replace(self.frame, image_png=bytes(corrupt)), target="Search", role="textbox").reason,
                         "INVALID_IMAGE")
        for role in ("", "image", 1, None):
            self.assertEqual(grounder.locate(self.frame, target="Search", role=role).reason, "UNSUPPORTED_ROLE")
        for target in ("", " ", "x" * 161, "A\nB", "A\u202eB", [], None):
            self.assertEqual(grounder.locate(self.frame, target=target, role="button").status, "error")
        self.assertEqual(provider.calls, [])
        with self.assertRaises(TypeError):
            grounder.locate(object(), target="Search", role="textbox")
        with self.assertRaises(Exception):
            replace(self.frame, width=self.frame.width + 1)
        with self.assertRaises(Exception):
            replace(self.frame, captured_at=nan)
        for changes in ({"frame_id": ""}, {"page_id": 4}, {"revision": True},
                        {"image_png": b"x" * (5 * 1024 * 1024 + 1)},
                        {"image_png": b"not a png"}, {"height": self.frame.height + 1}):
            with self.subTest(changes=list(changes)), self.assertRaises(Exception):
                replace(self.frame, **changes)

    def test_schema_rejects_extra_action_code_wrong_types_and_boxes(self):
        bad = [
            '{"version":1,"status":"found","box":[0,0,10,10],"javascript":"alert(1)"}',
            '{"version":1,"status":"found","box":[0,0,10,10],"type_text":"secret"}',
            '{"version":1,"status":"found","box":[0,0,10,10],"url":"https://bad.example"}',
            '{"version":1,"status":"found","box":[0,0,10,10],"status":"found"}',
            '{"version":true,"status":"found","box":[0,0,10,10]}',
            '{"version":1,"status":"found","box":[true,0,10,10]}',
            '{"version":1,"status":"found","box":[NaN,0,10,10]}',
            '{"version":1,"status":"found","box":[Infinity,0,10,10]}',
            '{"version":1,"status":"found","box":[0,0,10.5,10]}',
            '{"version":1,"status":"found","box":null}',
            '{"version":1,"status":"not_found","box":[0,0,10,10]}',
            '{"version":1,"status":"ambiguous","box":[0,0,10,10]}',
            '{"version":1,"status":"act","box":null}',
            '{"version":1,"status":"found"}',
            'not json',
        ]
        for raw in bad:
            with self.subTest(raw=raw):
                self.assertEqual(compile_proposal(raw, self.frame).status, "error")
        for box in ([-1, 0, 10, 10], [0, -1, 10, 10], [0, 0, 0, 10], [0, 0, 10, 0],
                    [999, 0, 2, 10], [0, 999, 10, 2]):
            raw = json.dumps({"version": 1, "status": "found", "box": box})
            self.assertEqual(compile_proposal(raw, self.frame).reason, "INVALID_BOX")

    def test_abstention_and_provider_failures_have_fixed_reasons(self):
        for status, reason in (("not_found", "TARGET_NOT_FOUND"), ("ambiguous", "AMBIGUOUS_TARGET")):
            raw = json.dumps({"version": 1, "status": status, "box": None})
            result = compile_proposal(raw, self.frame)
            self.assertEqual((result.status, result.reason, result.bbox), (status, reason, None))
        for code in ("MODEL_TIMEOUT", "MODEL_UNAVAILABLE", "PRIVATE_SECRET"):
            class Error(Exception):
                pass
            error = Error(code)
            error.code = code
            provider = FakeProvider()
            provider.complete = lambda **kwargs: (_ for _ in ()).throw(error)
            result = LocalVisionGrounder(provider).locate(self.frame, target="Search", role="textbox")
            self.assertEqual(result.reason, code if code != "PRIVATE_SECRET" else "PROVIDER_ERROR")

    def test_scoring_detects_wrong_target_and_abstention(self):
        case = load_cases()[0]
        hit = GroundingResult(self.frame.frame_id, "found", bbox=(30, 55, 290, 45))
        miss = GroundingResult(self.frame.frame_id, "found", bbox=(700, 500, 20, 20))
        self.assertEqual(score(case, hit), "target_hit")
        self.assertEqual(score(case, miss), "wrong_target")
        self.assertEqual(score(case, GroundingResult(self.frame.frame_id, "not_found")), "unexpected_abstain")


if __name__ == "__main__":
    unittest.main()
