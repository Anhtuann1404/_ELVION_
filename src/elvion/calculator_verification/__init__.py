"""Read-only Calculator result observation and pure transition verification."""

from .contracts import CalculatorExpectation, CalculatorObservation, CalculatorVerificationResult, ResultRegionProfile
from .observer import capture_calculator_result, capture_calculator_entry, diagnose_calculator_region
from .verifier import verify_result_transition

__all__ = ('CalculatorExpectation', 'CalculatorObservation', 'CalculatorVerificationResult',
           'ResultRegionProfile', 'capture_calculator_result', 'diagnose_calculator_region',
           'verify_result_transition','capture_calculator_entry')
