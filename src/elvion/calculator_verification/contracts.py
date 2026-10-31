"""Typed immutable contracts; observations contain raw result only after opt-in."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResultRegionProfile:
    role: str
    identifier: str
    parent_role: str
    parent_identifier: str
    locale: str = 'en_US'
    reviewed: bool = False
    surface: str = 'result'


@dataclass(frozen=True)
class CalculatorExpectation:
    schema_version: int = 1
    policy_version: int = 1
    before_value: str = '0'
    after_value: str = '7'
    surface: str = 'result'


@dataclass(frozen=True)
class CalculatorObservation:
    schema_version: int = 1
    status: str = 'unknown'
    reason: str = 'NOT_CAPTURED'
    observation_id: str = ''
    session_id: str = ''
    bundle_id: str = 'com.apple.calculator'
    pid: int = 0
    process_marker: str | None = None
    same_host_session: bool = False
    provenance: bool = False
    capture_start_ns: int = 0
    capture_end_ns: int = 0
    permission_granted: bool | None = None
    profile: ResultRegionProfile | None = None
    region_unique: bool | None = None
    result_text: str | None = None
    result_included: bool = False
    native_identity_continuity_proven: bool = False


@dataclass(frozen=True)
class CalculatorVerificationResult:
    status: str
    reason: str
    observed_matches_expected: bool | None = None
    transition_observed: bool = False
    actions: int = 0
    authority_granted: bool = False
    action_causality_proven: bool = False
