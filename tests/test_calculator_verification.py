import json
import subprocess
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock
from dataclasses import replace
from types import SimpleNamespace

from elvion.calculator_verification import (CalculatorObservation, ResultRegionProfile,
    capture_calculator_result,capture_calculator_entry,CalculatorExpectation,verify_result_transition)
from elvion.calculator_verification.verifier import standard_entry_profile
from elvion.calculator_verification.formatting import numeric_format_summary,parse_display_number
from elvion.calculator_verification.observer import NativeResultBackend,diagnose_calculator_region
from benchmarks.calculator_verification.cases import BEFORE, AFTER, NOW, PROFILE


class FakeBackend:
    def __init__(self, value='0'):
        self.calls=[]
        self.value=value
    def prepare(self): self.calls.append('prepare')
    def run(self, descriptor):
        self.calls.append(descriptor)
        return {'status':'observed','reason':'ENTRY_VALUE_READ' if descriptor['mode']=='capture_entry' else 'RESULT_VALUE_READ','pid':321,
                'process_marker':'launch-1','permission':True,'region_unique':True,
                'value':self.value,'diagnostic':[]}


class CalculatorVerificationTests(unittest.TestCase):
    def test_observed_edge_lrm_preserves_digits_signs_and_decimal(self):
        for text,value in (('\u200e0','0'),('7\u200e','7'),(' \u200e-7\u200e ','-7'),
                           ('\u200e7.1','7.1'),('\u200e17','17')):
            self.assertEqual(parse_display_number(text),value)
        for text in ('1\u200e7','-\u200e7','7\u200e.1','\u200f0','\u202e0',
                     '\u20660\u2069','\ufeff0','0\n','0\u00a0','1+6','7,1'):
            self.assertIsNone(parse_display_number(text),repr(text))

    def test_read_only_entry_cli_verifies_lrm_wrapped_values_without_mutating_them(self):
        from scripts.check_calculator_verification import main
        before=replace(BEFORE,profile=standard_entry_profile(),result_text='\u200e0')
        after=replace(AFTER,profile=standard_entry_profile(),result_text='\u200e7')
        capture=Mock(side_effect=[before,after])
        with redirect_stdout(StringIO()) as output:
            code=main(['--include-current-entry'],entry_capture=capture,prompt=lambda _: '',clock=lambda:NOW)
        self.assertEqual(code,0)
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1])['reason'],'ENTRY_TRANSITION_OBSERVED')
        self.assertEqual(before.result_text,'\u200e0')
        for value in ('\u200e17','\u200e-7','\u200e7.1'):
            self.assertEqual(verify_result_transition(before,replace(after,result_text=value),
                CalculatorExpectation(surface='current_entry'),now_ns=NOW).status,'not_verified')

    def test_format_diagnostic_discloses_wrappers_and_counts_without_digits(self):
        text='\u200e987654\n'
        info=numeric_format_summary(text)
        self.assertEqual(info['ascii_digit_count'],6)
        self.assertEqual(info['presentation_codepoints'],{'U+200E':1,'U+000A':1})
        self.assertNotIn('987654',json.dumps(info))
        self.assertFalse(numeric_format_summary(None)['text_available'])

    def test_format_only_cli_captures_once_without_prompt_or_raw_value(self):
        from scripts.check_calculator_verification import main
        observation=replace(BEFORE,profile=standard_entry_profile(),result_text='\u200e987654')
        capture=Mock(return_value=observation);prompt=Mock(side_effect=AssertionError('unexpected prompt'))
        with redirect_stdout(StringIO()) as output:
            code=main(['--include-current-entry','--diagnose-format'],entry_capture=capture,prompt=prompt)
        self.assertEqual(code,0)
        capture.assert_called_once_with(include_current_entry=True)
        self.assertNotIn('987654',output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['reason'],'FORMAT_ONLY')
        prompt.assert_not_called()

    def test_initial_format_failure_has_stage_and_does_not_request_digit_seven(self):
        from scripts.check_calculator_verification import main
        obs=replace(BEFORE,profile=standard_entry_profile(),result_text='\u200f0')
        capture=Mock(return_value=obs);prompt=Mock(return_value='')
        with redirect_stdout(StringIO()) as output:
            code=main(['--include-current-entry'],entry_capture=capture,prompt=prompt)
        self.assertEqual(code,1)
        self.assertEqual(prompt.call_count,1)
        capture.assert_called_once()
        summary=json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(summary['stage'],'before_capture')
        self.assertEqual(summary['format']['presentation_codepoints'],{'U+200F':1})
        self.assertNotIn('Now press 7',output.getvalue())

    def test_entry_opt_in_is_distinct_from_result_and_selection_is_fixed(self):
        backend=FakeBackend()
        self.assertEqual(capture_calculator_entry(backend=backend).reason,'ENTRY_OPT_IN_REQUIRED')
        self.assertEqual(backend.calls,[])
        self.assertEqual(capture_calculator_result(include_result=True,profile=standard_entry_profile(),
            backend=backend).reason,'REGION_PROFILE_REQUIRED')
        self.assertEqual(backend.calls,[])
        ticks=iter((8_000_000_000,8_100_000_000))
        obs=capture_calculator_entry(include_current_entry=True,backend=backend,clock=lambda:next(ticks))
        self.assertEqual(obs.profile.surface,'current_entry')
        self.assertEqual(obs.result_text,'0')
        descriptor=backend.calls[1]
        self.assertEqual(descriptor['mode'],'capture_entry')
        self.assertTrue(descriptor['include_current_entry'])
        self.assertEqual(descriptor['parent_identifier'],'StandardInputView')
        self.assertNotIn('include_result',descriptor)
        self.assertNotIn('expected',descriptor)

    def test_entry_transition_is_not_a_computed_result_or_expression(self):
        profile=standard_entry_profile()
        before=replace(BEFORE,profile=profile);after=replace(AFTER,profile=profile)
        expectation=CalculatorExpectation(surface='current_entry')
        self.assertEqual(verify_result_transition(before,after,now_ns=NOW).reason,'OBSERVATION_SURFACE_MISMATCH')
        result=verify_result_transition(before,after,expectation,now_ns=NOW)
        self.assertEqual((result.status,result.reason),('verified','ENTRY_TRANSITION_OBSERVED'))
        for value in ('1+6','17','-7','7.1'):
            self.assertNotEqual(verify_result_transition(before,replace(after,result_text=value),expectation,now_ns=NOW).status,'verified')
        self.assertEqual(verify_result_transition(before,replace(after,region_unique=False),expectation,now_ns=NOW).status,'unknown')

    def test_entry_cli_needs_only_explicit_entry_opt_in_and_keeps_actions_zero(self):
        from scripts.check_calculator_verification import main
        profile=standard_entry_profile()
        capture=Mock(side_effect=[replace(BEFORE,profile=profile),replace(AFTER,profile=profile)])
        result_reader=Mock()
        with redirect_stdout(StringIO()) as output:
            code=main(['--include-current-entry'],entry_capture=capture,capture=result_reader,
                prompt=lambda _: '',clock=lambda:NOW)
        self.assertEqual(code,0)
        result_reader.assert_not_called()
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1])['surface'],'current_entry')
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1])['actions'],0)
        capture.reset_mock()
        with redirect_stdout(StringIO()):
            self.assertEqual(main(['--include-current-entry','--include-result'],entry_capture=capture),2)
            self.assertEqual(main(['--include-current-entry','--parent-identifier','StandardResultView'],entry_capture=capture),2)
        capture.assert_not_called()

    def test_diagnostic_reports_window_binding_without_reading_values(self):
        row={'role':'AXStaticText','identifier':'','parent_role':'AXScrollArea',
             'parent_identifier':'StandardResultView','window_role':''}
        payload={'version':1,'status':'diagnostic','reason':'STRUCTURE_ONLY','pid':321,
                 'process_marker':'launch-1','permission':True,'region_unique':None,
                 'value':None,'diagnostic':[row]}
        def runner(*args,**kwargs):
            self.assertEqual(json.loads(kwargs['input']),{'version':1,'mode':'diagnose'})
            return SimpleNamespace(returncode=0,stdout=json.dumps(payload).encode())
        backend=NativeResultBackend(runner=runner);backend.prepare=lambda:None
        result=diagnose_calculator_region(backend=backend)
        self.assertEqual(result['candidates'][0]['window_role'],'')
        self.assertEqual(result['helper_source_sha256'],backend.source_sha256)
        self.assertNotIn('value',result)
        self.assertEqual(result['actions'],0)
        payload['diagnostic'][0]['window_role']='AXButton'
        with self.assertRaises(ValueError):backend.run({'version':1,'mode':'diagnose'})

    def test_empty_identifier_allowed_only_for_reviewed_standard_result_structure(self):
        profile=ResultRegionProfile('AXStaticText','','AXScrollArea','StandardResultView',reviewed=True)
        for invalid in (replace(profile,parent_identifier='StandardInputView'),
                        replace(profile,identifier='nonempty',parent_identifier='StandardInputView'),
                        replace(profile,parent_identifier='HistoryView'),
                        replace(profile,parent_role='AXGroup'),replace(profile,role='AXButton'),
                        replace(profile,reviewed=False)):
            backend=FakeBackend()
            result=capture_calculator_result(include_result=True,profile=invalid,backend=backend)
            self.assertEqual(result.reason,'REGION_PROFILE_REQUIRED')
            self.assertEqual(backend.calls,[])
        backend=FakeBackend()
        ticks=iter((8_000_000_000,8_100_000_000))
        result=capture_calculator_result(include_result=True,profile=profile,backend=backend,clock=lambda:next(ticks))
        self.assertEqual(result.status,'observed')
        self.assertEqual(backend.calls[1]['identifier'],'')
        self.assertEqual(backend.calls[1]['parent_identifier'],'StandardResultView')

    def test_standard_result_profile_still_requires_unique_region_and_correct_transition(self):
        profile=ResultRegionProfile('AXStaticText','','AXScrollArea','StandardResultView',reviewed=True)
        before=replace(BEFORE,profile=profile);after=replace(AFTER,profile=profile)
        self.assertEqual(verify_result_transition(before,after,now_ns=NOW).status,'verified')
        self.assertEqual(verify_result_transition(before,replace(after,region_unique=False),now_ns=NOW).status,'unknown')
        self.assertEqual(verify_result_transition(before,replace(after,result_text='0'),now_ns=NOW).status,'not_verified')

    def test_read_only_cli_accepts_explicit_empty_identifier(self):
        from scripts.check_calculator_verification import main
        profile=ResultRegionProfile('AXStaticText','','AXScrollArea','StandardResultView',reviewed=True)
        capture=Mock(side_effect=[replace(BEFORE,profile=profile),replace(AFTER,profile=profile)])
        with redirect_stdout(StringIO()) as output:
            code=main(['--include-result','--result-role','AXStaticText','--result-identifier','',
                '--parent-role','AXScrollArea','--parent-identifier','StandardResultView'],
                capture=capture,prompt=lambda _: '',clock=lambda:NOW)
        self.assertEqual(code,0)
        self.assertEqual(capture.call_args.kwargs['profile'],profile)
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1])['status'],'verified')

    def test_positive_transition_and_flags(self):
        result=verify_result_transition(BEFORE,AFTER,now_ns=NOW)
        self.assertEqual(result.status,'verified')
        self.assertTrue(result.transition_observed)
        self.assertFalse(result.action_causality_proven)
        self.assertFalse(result.authority_granted)
        self.assertEqual(result.actions,0)

    def test_no_value_read_without_opt_in(self):
        backend=FakeBackend()
        result=capture_calculator_result(backend=backend)
        self.assertEqual(result.reason,'RESULT_OPT_IN_REQUIRED')
        self.assertEqual(backend.calls,[])

    def test_unreviewed_profile_stops_before_native(self):
        backend=FakeBackend()
        result=capture_calculator_result(include_result=True,profile=replace(PROFILE,reviewed=False),backend=backend)
        self.assertEqual(result.reason,'REGION_PROFILE_REQUIRED')
        self.assertEqual(backend.calls,[])

    def test_expected_value_never_becomes_observed_value(self):
        backend=FakeBackend('0')
        times=iter((8_000_000_000,8_100_000_000))
        observation=capture_calculator_result(include_result=True,profile=PROFILE,
                                              backend=backend,clock=lambda:next(times))
        self.assertEqual(observation.result_text,'0')
        self.assertNotIn('expected',backend.calls[1])
        after=replace(observation,observation_id='after',capture_start_ns=9_000_000_000,
                      capture_end_ns=9_100_000_000)
        self.assertEqual(verify_result_transition(observation,after,now_ns=NOW).status,'not_verified')

    def test_button_and_history_evidence_cannot_verify(self):
        self.assertEqual(verify_result_transition(BEFORE,replace(AFTER,region_unique=False),now_ns=NOW).status,'unknown')
        self.assertEqual(verify_result_transition(BEFORE,replace(AFTER,result_text='0'),now_ns=NOW).status,'not_verified')

    def test_strict_protocol_rejects_duplicate_bool_and_nan(self):
        for raw in (b'{"version":1,"version":1}',
                    b'{"version":true,"status":"unknown"}',
                    b'{"version":1,"value":NaN}',
                    b'{"version":1,"status":"unknown","reason":[]}' ):
            backend=NativeResultBackend(runner=lambda *a,raw=raw,**k: SimpleNamespace(returncode=0,stdout=raw))
            with self.assertRaises(ValueError):
                backend.run({'version':1,'mode':'diagnose'})

    def test_timeout_is_error(self):
        def timeout(*a,**k): raise subprocess.TimeoutExpired('helper',5)
        backend=NativeResultBackend(runner=timeout)
        with self.assertRaisesRegex(ValueError,'OBSERVATION_TIMEOUT'):
            backend.run({'version':1,'mode':'diagnose'})

    def test_clock_and_process_guards(self):
        self.assertEqual(verify_result_transition(BEFORE,replace(AFTER,pid=322),now_ns=NOW).status,'unknown')
        self.assertEqual(verify_result_transition(BEFORE,replace(AFTER,capture_end_ns=NOW+1),now_ns=NOW).status,'error')
        self.assertEqual(verify_result_transition(BEFORE,replace(AFTER,process_marker=None),now_ns=NOW).status,'unknown')


if __name__=='__main__': unittest.main()
