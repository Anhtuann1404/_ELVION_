"""Hand-authored oracle for the read-only 0 → 7 verifier."""
from dataclasses import dataclass, replace
from elvion.calculator_verification import CalculatorExpectation, CalculatorObservation, ResultRegionProfile

NOW = 10_000_000_000
PROFILE = ResultRegionProfile('AXTextField', 'reviewed-result', 'AXGroup', 'reviewed-display', reviewed=True)
BEFORE = CalculatorObservation(status='observed', reason='RESULT_VALUE_READ',
    observation_id='before-1', session_id='session-1', pid=321, process_marker='launch-1', same_host_session=True,
    provenance=True, capture_start_ns=8_000_000_000, capture_end_ns=8_100_000_000,
    permission_granted=True, profile=PROFILE, region_unique=True,
    result_text='0', result_included=True)
AFTER = replace(BEFORE, observation_id='after-1', capture_start_ns=9_000_000_000,
                capture_end_ns=9_100_000_000, result_text='7')

@dataclass(frozen=True)
class Case:
    name: str
    before: CalculatorObservation
    after: CalculatorObservation
    expected: str
    expectation: CalculatorExpectation = CalculatorExpectation()
    now_ns: int = NOW

CASES = (
    Case('zero_to_seven', BEFORE, AFTER, 'verified'),
    Case('zero_to_seven_spaces', replace(BEFORE,result_text=' 0 '), replace(AFTER,result_text=' 7 '), 'verified'),
    Case('zero_to_zero', BEFORE, replace(AFTER,result_text='0'), 'not_verified'),
    Case('seven_to_seven', replace(BEFORE,result_text='7'), AFTER, 'not_verified'),
    Case('one_to_seven', replace(BEFORE,result_text='1'), AFTER, 'not_verified'),
    Case('negative_before', replace(BEFORE,result_text='-7'), AFTER, 'not_verified'),
    Case('seventeen_after', BEFORE, replace(AFTER,result_text='17'), 'not_verified'),
    Case('negative_seven_after', BEFORE, replace(AFTER,result_text='-7'), 'not_verified'),
    Case('decimal_seven_after', BEFORE, replace(AFTER,result_text='7.1'), 'not_verified'),
    Case('expression_only_seven', BEFORE, replace(AFTER,result_text='0'), 'not_verified'),
    Case('history_only_seven', BEFORE, replace(AFTER,result_text='0'), 'not_verified'),
    Case('button_seven_misbound', BEFORE, replace(AFTER,region_unique=False), 'unknown'),
    Case('no_result_region', BEFORE, replace(AFTER,status='unknown',reason='RESULT_REGION_NOT_FOUND',result_text=None,region_unique=False), 'unknown'),
    Case('multiple_result_regions', BEFORE, replace(AFTER,region_unique=False), 'unknown'),
    Case('unsupported_role', BEFORE, replace(AFTER,profile=replace(PROFILE,role='AXButton')), 'unknown'),
    Case('unreviewed_profile', BEFORE, replace(AFTER,profile=replace(PROFILE,reviewed=False)), 'unknown'),
    Case('missing_identifier', BEFORE, replace(AFTER,profile=replace(PROFILE,identifier='')), 'unknown'),
    Case('different_parent', BEFORE, replace(AFTER,profile=replace(PROFILE,parent_identifier='other')), 'unknown'),
    Case('missing_value', BEFORE, replace(AFTER,result_text=None), 'unknown'),
    Case('wrong_value_type', BEFORE, replace(AFTER,result_text=7), 'error'),
    Case('missing_opt_in', BEFORE, replace(AFTER,result_included=False,result_text=None), 'unknown'),
    Case('pid_changed', BEFORE, replace(AFTER,pid=322), 'unknown'),
    Case('instance_changed', BEFORE, replace(AFTER,process_marker='launch-2'), 'unknown'),
    Case('process_marker_missing', BEFORE, replace(AFTER,process_marker=None), 'unknown'),
    Case('same_observation_id', BEFORE, replace(AFTER,observation_id='before-1'), 'unknown'),
    Case('different_session', BEFORE, replace(AFTER,same_host_session=False), 'unknown'),
    Case('different_session_id', BEFORE, replace(AFTER,session_id='session-2'), 'unknown'),
    Case('imported_observation', replace(BEFORE,provenance=False), AFTER, 'unknown'),
    Case('future_timestamp', BEFORE, replace(AFTER,capture_end_ns=NOW+1), 'error'),
    Case('clock_out_of_order', BEFORE, replace(AFTER,capture_start_ns=8_000_000_000), 'error'),
    Case('capture_too_long', replace(BEFORE,capture_start_ns=2_000_000_000), AFTER, 'unknown'),
    Case('evidence_stale', replace(BEFORE,capture_start_ns=1_000_000_000,
                                   capture_end_ns=1_100_000_000), AFTER, 'unknown', now_ns=40_000_000_000),
    Case('permission_lost_after', BEFORE, replace(AFTER,permission_granted=False), 'unknown'),
    Case('timeout', BEFORE, replace(AFTER,status='error',reason='OBSERVATION_TIMEOUT',result_text=None), 'error'),
    Case('malformed_protocol', BEFORE, replace(AFTER,status='error',reason='PROTOCOL_ERROR',result_text=None), 'error'),
    Case('locale_unknown', BEFORE, replace(AFTER,profile=replace(PROFILE,locale='unknown')), 'unknown'),
    Case('grouped_number', BEFORE, replace(AFTER,result_text='1,007'), 'unknown'),
    Case('expression_format', BEFORE, replace(AFTER,result_text='0+7'), 'unknown'),
    Case('distinct_ids_no_native_continuity', BEFORE, AFTER, 'verified'),
    Case('wrong_policy', BEFORE, AFTER, 'error', CalculatorExpectation(policy_version=2)),
    Case('wrong_expectation', BEFORE, AFTER, 'error', CalculatorExpectation(after_value='8')),
)
