"""Narrow allowlist shared by policy, adapter and native transport."""
from dataclasses import dataclass
from math import isfinite
import re

from elvion.core.contracts import ActionIntent, TaskRequest

CAPABILITY = 'desktop.calculator.press7'
READ_GRANT = 'desktop.calculator.read_entry'
BUNDLE = 'com.apple.calculator'
POLICY_VERSION = 'macos-calculator-ax-v2'
ADAPTER_ID = 'macos.calculator.ax.press7'


def box(value):
    return (type(value) in (list, tuple) and len(value) == 4 and
            all(type(v) in (int, float) and isfinite(v) for v in value) and
            value[2] > 0 and value[3] > 0)


def valid_target(target):
    if type(target) is not dict or set(target) != {
            'app', 'pid', 'process_marker', 'target_bbox', 'window_bbox', 'displays'}:
        return False
    if (target['app'] != BUNDLE or type(target['pid']) is not int or
            not 0 < target['pid'] <= 2_147_483_647 or
            type(target['process_marker']) is not str or
            not re.fullmatch(r'[0-9]{1,12}\.[0-9]{6}', target['process_marker']) or
            not box(target['target_bbox']) or not box(target['window_bbox'])):
        return False
    displays = target['displays']
    return (type(displays) is list and 1 <= len(displays) <= 16 and
            all(type(d) is dict and set(d) == {'id', 'bbox', 'scale'} and
                type(d['id']) is int and d['id'] > 0 and box(d['bbox']) and
                type(d['scale']) in (int, float) and isfinite(d['scale']) and d['scale'] > 0
                for d in displays) and len({d['id'] for d in displays}) == len(displays))


def supports(intent):
    return (type(intent) is ActionIntent and intent.capability == CAPABILITY and
            valid_target(intent.target) and
            intent.arguments == {'label': '7', 'ax_action': 'AXPress'} and
            intent.preconditions == ('calculator_entry_zero',) and intent.risk == 'low' and
            intent.postcondition == {'kind': 'calculator_entry_transition', 'before': '0', 'after': '7'})


def make_intent(request: TaskRequest, target: dict):
    if not valid_target(target):
        raise ValueError('INVALID_CALCULATOR_TARGET')
    return ActionIntent(task_id=request.task_id, capability=CAPABILITY, target=target,
                        arguments={'label': '7', 'ax_action': 'AXPress'},
                        preconditions=('calculator_entry_zero',),
                        postcondition={'kind': 'calculator_entry_transition', 'before': '0', 'after': '7'})


@dataclass(frozen=True)
class PressOutcome:
    status: str  # dispatched, blocked, uncertain; never "task succeeded"
    reason: str
    external_effect_possible: bool = False
    native_error: int | None = None
