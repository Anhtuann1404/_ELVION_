"""Read-only Calculator desktop evidence revalidation."""

from .contracts import RevalidationEvidence, RevalidationResult
from .evaluator import evaluate_revalidation

__all__ = ('RevalidationEvidence', 'RevalidationResult', 'evaluate_revalidation')
