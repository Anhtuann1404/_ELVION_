"""Read-only targeting of an existing Calculator AX snapshot."""

from .contracts import DesktopTargetResult
from .locator import locate_control, evidence_summary

__all__ = ('DesktopTargetResult', 'locate_control', 'evidence_summary')
