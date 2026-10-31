"""Explicit single-action composition; never installed in general CLI/voice/GUI."""
from elvion.adapters.calculator_ax import CalculatorAXAdapter
from elvion.adapters.registry import AdapterRegistry
from elvion.core.orchestrator import TaskOrchestrator
from elvion.planning.rules import UnsupportedCommand
from elvion.policy.calculator import CalculatorPressPolicy
from elvion.verification.calculator import verify_calculator_transition


def build_runtime(intent, *, backend, reader, journal, current_grants, trace_store=None):
    adapter = CalculatorAXAdapter(backend=backend,reader=reader,journal=journal,current_grants=current_grants)
    adapter.prepare()
    def planner(request):
        if request.task_id != intent.task_id:
            raise UnsupportedCommand('CALCULATOR_TASK_MISMATCH')
        return intent
    runtime = TaskOrchestrator(registry=AdapterRegistry((adapter,)),policy=CalculatorPressPolicy(),
        verifier=verify_calculator_transition,simulated=False,planner=planner,trace_store=trace_store,
        success_message='Đã quan sát ô nhập số Calculator chuyển từ 0 sang 7 sau một yêu cầu AXPress.')
    return runtime,adapter
