"""Experimental bounded image presentation; no change to click-coordinate proposals."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import os
import struct
import subprocess
import sys
import tempfile

from elvion.vision.grounder import valid_png
from elvion.vision.image_crop import CropError


def prepare_scaler():
    if sys.platform!='darwin':raise CropError('SCALER_UNAVAILABLE')
    source=Path(__file__).resolve().parents[3]/'native/macos/ResizeImage.swift'
    binary=source.parents[2]/'artifacts/native'/('image-scaler-'+sha256(source.read_bytes()).hexdigest()[:16])
    if binary.is_file() and os.access(binary,os.X_OK):return binary
    binary.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=binary.parent,prefix='.scaler-build-') as directory:
        path=Path(directory);swift=path/'main.swift';output=path/'helper';swift.write_bytes(source.read_bytes())
        result=subprocess.run(['/usr/bin/swiftc','-swift-version','5','-module-cache-path',
            str(path/'cache'),str(swift),'-o',str(output)],stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,timeout=60,check=False,shell=False)
        if result.returncode!=0 or not output.is_file():raise CropError('SCALER_BUILD_FAILED')
        output.chmod(0o700);os.replace(output,binary)
    return binary


def resize_crop(frame,image_png,*,factor,helper,runner=subprocess.run):
    if type(factor) is not int or factor not in (1,2,4):raise CropError('INVALID_SCALE')
    try:
        if type(image_png) is not bytes or not 24 <= len(image_png) <= 5*1024*1024:
            raise CropError('INVALID_SCALE_IMAGE')
        width,height=struct.unpack('>II',image_png[16:24])
        crop=replace(frame,image_png=image_png,width=width,height=height)
        if not valid_png(crop) or width*factor>4096 or height*factor>4096:
            raise CropError('INVALID_SCALE_IMAGE')
        if factor==1:return image_png
        result=runner([str(helper),str(factor)],input=image_png,capture_output=True,
            timeout=5,check=False,shell=False)
        if result.returncode!=0 or type(result.stdout) is not bytes:
            raise CropError('SCALER_FAILED')
        output=replace(crop,image_png=result.stdout,width=width*factor,height=height*factor)
        if not valid_png(output):raise CropError('SCALER_INVALID_OUTPUT')
        return output.image_png
    except CropError:raise
    except (ValueError,TypeError,struct.error,OSError,subprocess.SubprocessError):
        raise CropError('SCALER_FAILED') from None
