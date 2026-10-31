"""Read-only sampled AX visibility evidence for Calculator."""

from .contracts import VisibilityEvidence, VisibilityResult
from .evaluator import evaluate_visibility

__all__ = ('VisibilityEvidence', 'VisibilityResult', 'evaluate_visibility')
