"""Deterministic OCR-label context crops; never adjust a proposed click box."""
from dataclasses import replace
from math import ceil, floor, isfinite
import subprocess

from elvion.browser.contracts import VisionFrame
from elvion.vision.grounder import valid_png


class CropError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


# Descriptive alias retained for callers/tests that prefer the module-specific name.
ImageCropError = CropError


def context_rectangle(frame, bbox, *, padding=None):
    """Return integer top-left (x,y,width,height), clipping context only, never bbox."""
    if type(frame) is not VisionFrame:
        raise ImageCropError('INVALID_IMAGE')
    if (type(bbox) not in (tuple, list) or len(bbox) != 4 or
            any(type(value) not in (int, float) or not isfinite(value) for value in bbox)):
        raise ImageCropError('INVALID_BOX')
    x, y, width, height = bbox
    if not (x >= 0 and y >= 0 and width > 0 and height > 0 and
            x+width <= frame.width and y+height <= frame.height):
        raise ImageCropError('INVALID_BOX')
    if padding is not None and (type(padding) is not int or not 8 <= padding <= 384):
        raise ImageCropError('INVALID_BOX')
    pad = max(128, min(384, 3*max(width, height))) if padding is None else padding
    left, top = max(0, floor(x-pad)), max(0, floor(y-pad))
    right, bottom = min(frame.width, ceil(x+width+pad)), min(frame.height, ceil(y+height+pad))
    return left, top, right-left, bottom-top


def crop_context(frame, bbox, *, helper, runner=None, padding=None, mark_bbox=False):
    """PNG stdin/stdout only. The helper exits before any OCR/model work in crop mode."""
    if not valid_png(frame):
        raise ImageCropError('INVALID_IMAGE')
    left, top, width, height = context_rectangle(frame, bbox, padding=padding)
    if type(mark_bbox) is not bool:
        raise ImageCropError('INVALID_BOX')
    run = runner if runner is not None else subprocess.run
    try:
        command = [str(helper), '--crop-mark' if mark_bbox else '--crop', str(left), str(top), str(width), str(height)]
        if mark_bbox:
            command += [str(bbox[0]-left),str(bbox[1]-top),str(bbox[2]),str(bbox[3])]
        result = run(command,
                     input=frame.image_png, capture_output=True, timeout=5, check=False, shell=False)
        if result.returncode != 0 or type(result.stdout) is not bytes:
            raise ImageCropError('CROP_FAILED')
        # replace preserves frame/page identity, revision and original monotonic capture time.
        cropped = replace(frame, image_png=result.stdout, width=width, height=height)
        if not valid_png(cropped):
            raise ImageCropError('CROP_INVALID_OUTPUT')
        return cropped.image_png
    except ImageCropError:
        raise
    except (OSError, subprocess.SubprocessError):
        raise ImageCropError('CROP_FAILED') from None
    except (ValueError, TypeError, OverflowError):
        raise ImageCropError('CROP_INVALID_OUTPUT') from None
