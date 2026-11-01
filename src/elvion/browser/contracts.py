"""Shared immutable grounding boundary. Only the browser controller executes actions."""
from dataclasses import dataclass
from math import isfinite
import struct
from typing import Protocol, Literal

from elvion.core.contracts import ContractError

MAX_PNG_BYTES = 5 * 1024 * 1024
ROLES = frozenset({'textbox', 'button', 'link'})
GROUNDING_REASONS = frozenset({'TARGET_NOT_FOUND', 'AMBIGUOUS_TARGET', 'INVALID_PROPOSAL',
    'MODEL_UNAVAILABLE', 'MODEL_TIMEOUT', 'MODEL_INVALID_RESPONSE', 'INVALID_IMAGE',
    'UNSUPPORTED_ROLE', 'PROVIDER_ERROR', 'INVALID_BOX'})


@dataclass(frozen=True)
class VisionFrame:
    frame_id: str
    page_id: str
    revision: int
    image_png: bytes
    width: int
    height: int
    captured_at: float

    def __post_init__(self):
        if any(type(v) is not str or not v or len(v) > 128 for v in (self.frame_id, self.page_id)):
            raise ContractError('Invalid frame identity')
        if type(self.revision) is not int or self.revision < 0:
            raise ContractError('Invalid page revision')
        if any(type(v) is not int or not 1 <= v <= 4096 for v in (self.width, self.height)):
            raise ContractError('Invalid viewport size')
        if type(self.captured_at) not in (int, float) or not isfinite(self.captured_at) or self.captured_at < 0:
            raise ContractError('Invalid frame timestamp')
        png = self.image_png
        if (type(png) is not bytes or not 33 <= len(png) <= MAX_PNG_BYTES or
                png[:8] != b'\x89PNG\r\n\x1a\n' or png[12:16] != b'IHDR' or
                struct.unpack('>II', png[16:24]) != (self.width, self.height)):
            raise ContractError('Invalid PNG header/size')


@dataclass(frozen=True)
class GroundingResult:
    frame_id: str
    status: Literal['found', 'not_found', 'ambiguous', 'error']
    bbox: tuple[float, float, float, float] | None = None
    reason: str | None = None

    def __post_init__(self):
        if type(self.frame_id) is not str or not self.frame_id or len(self.frame_id) > 128:
            raise ContractError('Invalid result frame')
        if type(self.status) is not str or self.status not in ('found', 'not_found', 'ambiguous', 'error'):
            raise ContractError('Invalid grounding status')
        if self.reason is not None and (type(self.reason) is not str or self.reason not in GROUNDING_REASONS):
            raise ContractError('Unknown grounding reason')
        if self.status == 'found':
            if (type(self.bbox) is not tuple or len(self.bbox) != 4 or
                    any(type(v) not in (int, float) or not isfinite(v) for v in self.bbox) or
                    min(self.bbox[:2]) < 0 or min(self.bbox[2:]) <= 0):
                raise ContractError('Invalid grounding box')
        elif self.bbox is not None:
            raise ContractError('Abstention cannot contain a box')


class VisionGrounder(Protocol):
    def locate(self, frame: VisionFrame, *, target: str, role: str) -> GroundingResult: ...
