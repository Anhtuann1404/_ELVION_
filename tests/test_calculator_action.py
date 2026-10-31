"""Fake private pipes + real policy/orchestrator + pure Task B verifier. No OS actions."""
from collections import deque
from dataclasses import replace
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import time
import unittest
from unittest.mock import patch

from elvion.core.contracts import (AuthorizationToken,ConfirmationResponse,TaskRequest,TaskStatus,utc_now)
from elvion.desktop_action.backend import CalculatorPressBackend
from elvion.desktop_action.contracts import CAPABILITY,READ_GRANT,make_intent
from elvion.desktop_action.journal import AttemptJournal
from elvion.desktop_action.runtime import build_runtime
from elvion.policy.calculator import CalculatorPressPolicy
from elvion.policy.confirmation import ConfirmationManager
from elvion.storage.traces import TraceStore
from elvion.verification.calculator import CalculatorResultReader
from elvion.calculator_verification.contracts import CalculatorObservation,ResultRegionProfile
from elvion.calculator_verification.observer import SESSION_ID

TARGET={'app':'com.apple.calculator','pid':123,'process_marker':'1700000000.000000',
    'target_bbox':[10,20,48,48],'window_bbox':[0,0,230,408],
    'displays':[{'id':1,'bbox':[0,0,1280,800],'scale':1}]}
GRANTS=frozenset((CAPABILITY,READ_GRANT))
PROFILE=ResultRegionProfile('AXStaticText','','AXScrollArea','StandardInputView',reviewed=True,surface='current_entry')


class Reader(CalculatorResultReader):
    def __init__(self):
        super().__init__(PROFILE)
        self.value='0';self.captures=0;self.mutate=lambda o:o

    def prepare(self):pass

    def capture(self):
        self.captures+=1
        start=time.monotonic_ns()
        obs=CalculatorObservation(status='observed',reason='RESULT_VALUE_READ',
            observation_id=str(self.captures),session_id=SESSION_ID,pid=123,
            process_marker=TARGET['process_marker'],same_host_session=True,provenance=True,
            capture_start_ns=start,capture_end_ns=time.monotonic_ns(),permission_granted=True,
            profile=PROFILE,region_unique=True,result_text=self.value,result_included=True)
        return self.mutate(obs)


class Pipe:
    def __init__(self, reader, *, final='dispatched', prepared_hook=lambda:None,
                 commit_error=False, malformed=False):
        self.reader=reader;self.final=final;self.prepared_hook=prepared_hook
        self.commit_error=commit_error;self.malformed=malformed
        self.sent=[];self.closed=False

    def send(self,payload):
        self.sent.append(payload)
        if payload.get('command')=='commit':
            self.reader.value='7'
            if self.commit_error:raise BrokenPipeError()

    def read(self,timeout):
        base={'version':1,'nonce':self.sent[0]['nonce']}
        if len(self.sent)==1:
            self.prepared_hook()
            return base | {'status':'prepared','reason':'PREPARED'}
        if self.final=='timeout':raise TimeoutError()
        if self.malformed:return base | {'status':'blocked','reason':'TARGET_CHANGED','native_error':-1}
        if self.final=='uncertain':return base | {'status':'uncertain','reason':'AXPRESS_ERROR','native_error':-25204}
        return base | {'status':'dispatched','reason':'AXPRESS_RETURNED','native_error':0}

    def close(self):self.closed=True


class Backend(CalculatorPressBackend):
    def prepare(self):pass


class CalculatorActionTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.request=TaskRequest(utterance='fixed calculator test')
        self.intent=make_intent(self.request,json.loads(json.dumps(TARGET)))
        self.reader=Reader();self.pipe=Pipe(self.reader);self.pipes=0
        def factory(binary):self.pipes+=1;return self.pipe
        self.backend=Backend(transport_factory=factory)
        self.grants=set(GRANTS)
        self.journal=AttemptJournal(self.root/'attempts.sqlite3')
        self.runtime,self.adapter=build_runtime(self.intent,backend=self.backend,reader=self.reader,
            journal=self.journal,current_grants=lambda:frozenset(self.grants),trace_store=TraceStore(self.root))

    @staticmethod
    def approve(c):return ConfirmationResponse(confirmation_id=c.confirmation_id,
        action_digest=c.action_digest,approved=True)

    def run_task(self,handler=None,grants=GRANTS):
        return self.runtime.run(self.request,grants,confirmation_handler=handler)

    def token(self):
        return AuthorizationToken(task_id=self.intent.task_id,step_id=self.intent.step_id,
            action_digest=self.intent.digest(),expires_at=utc_now()+timedelta(seconds=30))

    def test_exact_allowlist_and_mandatory_confirmation(self):
        policy=CalculatorPressPolicy();self.assertTrue(policy.allows(self.intent,GRANTS))
        self.assertFalse(policy.allows(self.intent,frozenset((CAPABILITY,'desktop.calculator.read_result'))))
        for change in ({'arguments':{'label':'8','ax_action':'AXPress'}},
                       {'target':{**self.intent.target,'pid':True}},
                       {'postcondition':{'kind':'app_running'}},{'preconditions':()},
                       {'risk':'high'},{'capability':'app.open'}):
            self.assertFalse(policy.allows(replace(self.intent,**change),GRANTS))
        policy.require_confirmation=False
        self.assertTrue(policy.requires_confirmation(self.intent))

    def test_missing_grant_decline_and_missing_handler_do_not_read_or_press(self):
        self.assertEqual(self.run_task(self.approve,frozenset()).status,TaskStatus.FAILED)
        self.assertEqual(self.run_task().status,TaskStatus.AWAITING_CONFIRMATION)
        def decline(c):return replace(self.approve(c),approved=False)
        self.assertEqual(self.run_task(decline).status,TaskStatus.CANCELLED)
        self.assertEqual((self.reader.captures,self.pipes),(0,0))

    def test_expired_confirmation_and_changed_preview_do_not_execute(self):
        now=[utc_now()]
        self.runtime.policy.confirmations=ConfirmationManager(clock=lambda:now[0],ttl_seconds=1)
        def expired(c):now[0]+=timedelta(seconds=2);return self.approve(c)
        self.assertEqual(self.run_task(expired).status,TaskStatus.FAILED)
        def mutate(c):self.intent.arguments['label']='8';return self.approve(c)
        self.assertEqual(self.run_task(mutate).status,TaskStatus.FAILED)
        self.assertEqual(self.pipes,0)

    def test_before_value_or_evidence_invalid_never_starts_helper(self):
        for mutation in (lambda o:replace(o,result_text='7'),lambda o:replace(o,result_text='17'),
                lambda o:replace(o,pid=124),lambda o:replace(o,region_unique=False),
                lambda o:replace(o,result_included=False),lambda o:replace(o,session_id='other'),
                lambda o:replace(o,capture_start_ns=o.capture_start_ns-3_000_000_000)):
            self.reader.mutate=mutation
            self.assertEqual(self.run_task(self.approve).status,TaskStatus.FAILED)
        self.assertEqual(self.pipes,0)

    def test_verified_transition_requires_independent_after_read(self):
        report=self.run_task(self.approve)
        self.assertEqual(report.status,TaskStatus.SUCCEEDED)
        self.assertTrue(report.evidence['postcondition_verified'])
        self.assertEqual(self.reader.captures,2)
        self.assertEqual(sum(p.get('command')=='commit' for p in self.pipe.sent),1)
        self.assertTrue(self.pipe.closed)

    def test_lrm_wrapped_entry_is_used_by_both_precondition_and_verifier(self):
        self.reader.mutate=lambda o:replace(o,result_text='\u200e'+o.result_text)
        report=self.run_task(self.approve)
        self.assertEqual(report.status,TaskStatus.SUCCEEDED)
        self.assertEqual(self.reader.captures,2)
        self.assertEqual(sum(p.get('command')=='commit' for p in self.pipe.sent),1)

    def test_lrm_does_not_turn_negative_or_expression_into_zero_authority(self):
        for text in ('\u200e-0','\u200e0.1','0\u200e0','\u200e0+0'):
            self.reader.mutate=lambda o,text=text:replace(o,result_text=text)
            self.assertEqual(self.run_task(self.approve).status,TaskStatus.FAILED)
        self.assertEqual(self.pipes,0)

    def test_native_success_without_display_change_is_uncertain_no_retry(self):
        original=self.pipe.send
        def send(payload):original(payload);self.reader.value='0'
        self.pipe.send=send
        report=self.run_task(self.approve)
        self.assertEqual(report.status,TaskStatus.UNCERTAIN)
        self.assertEqual(sum(p.get('command')=='commit' for p in self.pipe.sent),1)

    def test_timeout_error_and_malformed_after_commit_are_uncertain(self):
        for mode in ('timeout','uncertain','malformed','partial_write'):
            with self.subTest(mode=mode):
                self.setUp()
                self.pipe.final=mode
                self.pipe.malformed=mode=='malformed';self.pipe.commit_error=mode=='partial_write'
                report=self.run_task(self.approve)
                self.assertEqual(report.status,TaskStatus.UNCERTAIN)
                self.assertEqual(self.reader.captures,1)
                self.assertEqual(sum(p.get('command')=='commit' for p in self.pipe.sent),1)

    def test_revoke_or_expire_during_prepare_sends_no_commit(self):
        self.pipe.prepared_hook=self.grants.clear
        report=self.run_task(self.approve)
        self.assertEqual(report.status,TaskStatus.FAILED)
        self.assertEqual(len(self.pipe.sent),1)
        self.assertFalse((self.root/'attempts.sqlite3').exists())

    def test_expired_token_never_starts_transport(self):
        token=replace(self.token(),expires_at=utc_now()-timedelta(seconds=1))
        result=self.adapter.execute(self.intent,token)
        self.assertEqual(result.status.value,'failed')
        self.assertEqual(self.pipes,0)

    def test_token_expiry_after_prepare_prevents_commit(self):
        wall=[utc_now()]
        self.pipe.prepared_hook=lambda:wall.__setitem__(0,wall[0]+timedelta(minutes=2))
        with patch('elvion.core.contracts.utc_now',side_effect=lambda:wall[0]):
            self.assertEqual(self.run_task(self.approve).status,TaskStatus.FAILED)
        self.assertEqual(len(self.pipe.sent),1)

    def test_baseline_stales_while_helper_prepares_prevents_commit(self):
        current=[time.monotonic_ns()]
        self.adapter.clock=lambda:current[0]
        self.pipe.prepared_hook=lambda:current.__setitem__(0,current[0]+3_000_000_000)
        # Initial value must be sampled after the fake reader's actual timestamp.
        capture=self.reader.capture
        def observed():
            obs=capture();current[0]=obs.capture_end_ns;return obs
        self.reader.capture=observed
        self.assertEqual(self.run_task(self.approve).status,TaskStatus.FAILED)
        self.assertEqual(len(self.pipe.sent),1)

    def test_baseline_exception_is_known_no_execution_failure(self):
        def broken():raise ValueError('private result must not escape')
        self.reader.capture=broken
        report=self.run_task(self.approve)
        self.assertEqual(report.status,TaskStatus.FAILED)
        self.assertEqual(self.pipes,0)
        self.assertNotIn('private',json.dumps(report.to_dict()))

    def test_bad_prepared_nonce_or_bool_version_never_reserves_or_commits(self):
        for change in ({'nonce':'other'},{'version':True}):
            self.pipe=Pipe(self.reader)
            read=self.pipe.read
            self.pipe.read=lambda timeout,read=read,change=change:read(timeout)|change
            self.assertEqual(self.run_task(self.approve).status,TaskStatus.FAILED)
            self.assertEqual(len(self.pipe.sent),1)
        self.assertFalse(self.journal.path.exists())

    def test_durable_key_blocks_second_commit_after_new_adapter_or_journal(self):
        self.assertEqual(self.run_task(self.approve).status,TaskStatus.SUCCEEDED)
        self.reader.value='0'
        other_pipe=Pipe(self.reader)
        backend=Backend(transport_factory=lambda binary:other_pipe)
        runtime,_=build_runtime(self.intent,backend=backend,reader=self.reader,
            journal=AttemptJournal(self.journal.path),current_grants=lambda:GRANTS)
        self.assertEqual(runtime.run(self.request,GRANTS,confirmation_handler=self.approve).status,TaskStatus.FAILED)
        self.assertEqual(len(other_pipe.sent),1)
        self.assertEqual(self.journal.path.stat().st_mode & 0o777,0o600)

    def test_reservation_failure_never_commits(self):
        def fail(*args):raise OSError('storage unavailable')
        self.journal.reserve=fail
        self.assertEqual(self.run_task(self.approve).status,TaskStatus.FAILED)
        self.assertEqual(len(self.pipe.sent),1)

    def test_uncertain_dispatch_stays_reserved_across_new_journal(self):
        self.pipe.final='timeout'
        self.assertEqual(self.run_task(self.approve).status,TaskStatus.UNCERTAIN)
        self.assertFalse(AttemptJournal(self.journal.path).reserve(
            self.intent.idempotency_key,self.intent.digest()))

    def test_revocation_after_reservation_burns_key_without_commit(self):
        original=self.journal.reserve
        def reserve(*args):
            ok=original(*args);self.grants.clear();return ok
        self.journal.reserve=reserve
        self.assertEqual(self.run_task(self.approve).status,TaskStatus.FAILED)
        self.assertEqual(len(self.pipe.sent),1)
        self.assertFalse(original(self.intent.idempotency_key,self.intent.digest()))

    def test_trace_keeps_capability_and_codes_without_raw_state(self):
        report=self.run_task(self.approve)
        path=Path(report.trace['path'])
        raw=path.read_text()
        records=[json.loads(line) for line in raw.splitlines()]
        self.assertEqual(records[-1]['capability'],CAPABILITY)
        self.assertEqual(records[-1]['policy_version'],'macos-calculator-ax-v2')
        for text in ('target_bbox','window_bbox','process_marker','result_text','reviewed-result','ocr'):
            self.assertNotIn(text,raw)

    def test_script_no_opt_in_stops_before_discovery(self):
        from scripts.check_calculator_action import main
        with (patch('scripts.check_calculator_action.discover_target') as discover,
                patch('sys.stdout',new_callable=StringIO) as output):
            self.assertEqual(main([]),2)
        discover.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['actions'],0)

    def test_action_reader_accepts_reviewed_native_empty_id_profile(self):
        profile=PROFILE
        reader=CalculatorResultReader(profile)
        with patch('elvion.calculator_verification.observer.NativeResultBackend') as backend:
            reader.prepare()
        backend.return_value.prepare.assert_called_once()
        wrong=CalculatorResultReader(replace(profile,surface='result'))
        with self.assertRaises(ValueError):wrong.prepare()


if __name__=='__main__':unittest.main()
