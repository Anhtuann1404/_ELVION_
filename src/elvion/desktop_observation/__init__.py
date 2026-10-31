"""Read-only macOS Accessibility observation spike."""

from .contracts import DesktopElement, DesktopObservationResult, DesktopSnapshot
from .observer import observe_app

__all__ = ('DesktopElement', 'DesktopObservationResult', 'DesktopSnapshot', 'observe_app')
