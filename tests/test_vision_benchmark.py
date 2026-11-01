"""Fixture and scoring tests use fake proposals, never infer model quality."""
from contextlib import redirect_stderr
import io
from pathlib import Path
import tempfile
import unittest

from benchmarks.vision.runner import evaluate, load_cases, main, markdown, write_report, compare_protocols
from elvion.vision import LocalVisionGrounder


class TruthProvider:
    model = "fake_provider"
    last_inference_ms = None
    def __init__(self, cases):
        self.cases = {case["target"]: case for case in cases}
    def complete(self, *, image_png, target, role, schema, system):
        case = self.cases[target]
        if case["expected"] != "found":
            return '{"version":1,"status":"' + case["expected"] + '","box":null}'
        x, y, width, height = case["boxes"][0]
        return ('{"version":1,"status":"found","box":[' +
                ','.join(str(round(v * 1000 / dim)) for v, dim in zip((x, y, width, height), (800, 600, 800, 600))) + ']}')


class BenchmarkTests(unittest.TestCase):
    def test_paired_comparison_alternates_without_leaking_truth(self):
        class Provider:
            model, max_tokens, last_inference_ms = 'fake', 512, None
            def __init__(self): self.calls = []
            def complete(self, **kwargs):
                version = kwargs['schema']['properties']['version']['const']
                self.calls.append((kwargs['image_png'], kwargs['target'], version))
                return '{"version":1,"status":"not_found","box":null}' if version == 1 else '{"version":2,"boxes":[]}'
        cases = load_cases()[:2]
        provider, progress = Provider(), []
        reports = compare_protocols(cases, provider, repetitions=2, progress=lambda *args: progress.append(args))
        self.assertEqual([call[2] for call in provider.calls], [1,2,2,1,2,1,1,2])
        for index in range(0, len(provider.calls), 2):
            self.assertEqual(provider.calls[index][:2], provider.calls[index+1][:2])
        self.assertEqual(progress[-1][:2], (8,8))
        for name, report in reports.items():
            self.assertEqual(report['config']['protocol'], name)
            self.assertEqual(report['config']['max_tokens'], 512)
            self.assertEqual(report['summary']['observations'], 4)
            self.assertFalse(report['config']['live_vision_enabled'])
            self.assertEqual([row['repetition'] for row in report['results']], [1,2,1,2])
        for repetitions in (0, True, 11):
            with self.assertRaises(ValueError):
                compare_protocols(cases, provider, repetitions)
    def test_fixtures_are_distinct_split_and_valid(self):
        cases = load_cases()
        self.assertEqual(len(cases), 24)
        self.assertEqual({case["split"] for case in cases}, {"dev", "test"})
        self.assertTrue(any(case["canvas"] for case in cases))
        self.assertTrue(any(case["expected"] == "ambiguous" for case in cases))
        self.assertTrue(any(case["expected"] == "not_found" for case in cases))

    def test_fake_scores_include_abstain_wrong_and_provider_errors(self):
        cases = load_cases()
        grounder = LocalVisionGrounder(TruthProvider(cases))
        # Unique target strings avoid using truth boxes in the grounder. This subset has distinct targets.
        selected = [next(case for case in cases if case["id"] == key)
                    for key in ("textbox_right", "button_edge", "ambiguous_links", "absent_button")]
        report = evaluate(selected, grounder)
        self.assertEqual(report["summary"]["passed"], 4)
        self.assertEqual(report["summary"]["target_hit"], 2)
        self.assertEqual(report["summary"]["correct_abstain"], 2)
        grounder.provider.complete = lambda **kwargs: '{"version":1,"status":"found","box":[0,0,20,20]}'
        failed = evaluate(selected, grounder)
        self.assertGreater(failed["summary"]["wrong_target"], 0)
        self.assertEqual(failed["summary"]["observations"], 4)
        grounder.provider.complete = lambda **kwargs: "PRIVATE RAW MODEL RESPONSE"
        malformed = evaluate(selected[:1], grounder)
        self.assertEqual(malformed["summary"]["provider_error"], 1)
        self.assertEqual(malformed["summary"]["failed"], 1)
        self.assertNotIn("PRIVATE RAW MODEL RESPONSE", markdown(malformed))

    def test_reports_are_unique_and_contain_no_png_or_raw_response(self):
        case = next(case for case in load_cases() if case["id"] == "absent_button")
        grounder = LocalVisionGrounder(TruthProvider([case]))
        report = evaluate([case], grounder)
        with tempfile.TemporaryDirectory() as directory:
            first = write_report(report, Path(directory))
            second = write_report(report, Path(directory))
            self.assertTrue(set(first).isdisjoint(second))
            text = first[0].read_text() + first[1].read_text() + markdown(report)
            self.assertNotIn("iVBOR", text)
            self.assertNotIn("images", text)
            self.assertNotIn("raw_response", text)
            self.assertTrue(all(path.stat().st_mode & 0o077 == 0 for path in (*first, *second)))

    def test_cli_rejects_bad_selection_and_repetitions_without_model(self):
        for argv in (["--case", "unknown"], ["--case", "textbox_top", "--case", "textbox_top"],
                     ["--repetitions", "0"], ["--split", "test", "--case", "textbox_top"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(["--model", "qwen3.5:4b", *argv])
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
