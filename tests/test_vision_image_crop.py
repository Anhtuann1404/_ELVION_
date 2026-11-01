"""Context crop protocol guards: stdlib PNG fixtures, no native OCR or model."""
from dataclasses import replace
import struct
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zlib

from benchmarks.vision.runner import frame_for, load_cases
from elvion.vision.image_crop import ImageCropError, context_rectangle, crop_context


def png(width, height):
    def chunk(kind, payload):
        return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload))
    raw=(b'\0'+b'\x20\x40\x60'*width)*height
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+
            chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))


class ImageCropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame=replace(frame_for(load_cases()[0]),captured_at=123.25)

    def test_context_padding_floor_ceil_and_viewport_clipping(self):
        self.assertEqual(context_rectangle(self.frame,(200,200,20,10)),(72,72,276,266))
        self.assertEqual(context_rectangle(self.frame,(0,0,20,20)),(0,0,148,148))
        self.assertEqual(context_rectangle(self.frame,(200.25,200.75,20.5,10.5)),(72,72,277,268))
        self.assertEqual(context_rectangle(self.frame,(200,200,200,100)),(0,0,784,600))

    def test_transcription_padding_preserves_label_and_clips_only_context(self):
        self.assertEqual(context_rectangle(self.frame,(200,200,100,20),padding=24),
                         (176,176,148,68))
        self.assertEqual(context_rectangle(self.frame,(0,0,100,20),padding=24),
                         (0,0,124,44))
        for padding in (True,0,7,385,24.5):
            with self.assertRaises(ImageCropError):
                context_rectangle(self.frame,(200,200,100,20),padding=padding)

    def test_invalid_box_is_rejected_instead_of_clamped(self):
        for box in ((-1,0,10,10),(0,-1,10,10),(799,0,2,10),(0,599,10,2),
                    (0,0,0,10),(True,0,10,10),(0,0,float('nan'),10),[1,2,3],None):
            with self.subTest(box=box), self.assertRaises(ImageCropError):
                context_rectangle(self.frame,box)

    def test_stdin_no_shell_bounded_timeout_and_original_timestamp(self):
        output=png(276,266)
        runner=Mock(return_value=SimpleNamespace(returncode=0,stdout=output))
        from elvion.vision.grounder import valid_png
        captures=[]
        def inspect_frame(frame):
            captures.append(frame)
            return valid_png(frame)
        with patch('elvion.vision.image_crop.valid_png',side_effect=inspect_frame):
            self.assertEqual(crop_context(self.frame,(200,200,20,10),helper='/fixture/helper',runner=runner),output)
        args,kwargs=runner.call_args
        self.assertEqual(args[0],['/fixture/helper','--crop','72','72','276','266'])
        self.assertEqual(kwargs['input'],self.frame.image_png)
        self.assertFalse(kwargs['shell'])
        self.assertLessEqual(kwargs['timeout'],5)
        self.assertEqual(captures[-1].captured_at,123.25)
        self.assertEqual(captures[-1].frame_id,self.frame.frame_id)
        self.assertEqual(self.frame.image_png,kwargs['input'])

    def test_wrong_dimensions_crc_and_not_png_outputs_are_errors(self):
        corrupt=bytearray(png(276,266));corrupt[-5]^=1
        for output in (png(277,266),bytes(corrupt),b'not png',b'x'*(5*1024*1024+1)):
            runner=Mock(return_value=SimpleNamespace(returncode=0,stdout=output))
            with self.subTest(size=len(output)), self.assertRaises(ImageCropError):
                crop_context(self.frame,(200,200,20,10),helper='/fixture/helper',runner=runner)

    def test_invalid_input_never_runs_helper_and_helper_failures_are_fixed(self):
        corrupt=bytearray(self.frame.image_png);corrupt[-5]^=1
        runner=Mock()
        with self.assertRaises(ImageCropError):
            crop_context(replace(self.frame,image_png=bytes(corrupt)),(200,200,20,10),helper='/fixture/helper',runner=runner)
        runner.assert_not_called()
        for failure in (subprocess.TimeoutExpired('helper',5),OSError('PRIVATE_DETAIL')):
            runner=Mock(side_effect=failure)
            with self.assertRaisesRegex(ImageCropError,'^CROP_FAILED$'):
                crop_context(self.frame,(200,200,20,10),helper='/fixture/helper',runner=runner)


class MarkedCropTests(unittest.TestCase):
    def test_marker_is_explicit_and_uses_crop_coordinates_without_changing_dimensions(self):
        frame=frame_for(load_cases()[0])
        runner=Mock(return_value=SimpleNamespace(returncode=0,stdout=png(148,68)))
        output=crop_context(frame,(200,200,100,20),helper='/fake/helper',runner=runner,
                            padding=24,mark_bbox=True)
        self.assertEqual(output,png(148,68))
        self.assertEqual(runner.call_args.args[0],['/fake/helper','--crop-mark','176','176','148','68','24','24','100','20'])
        runner.reset_mock()
        with self.assertRaises(ImageCropError):
            crop_context(frame,(200,200,100,20),helper='/fake/helper',runner=runner,mark_bbox=1)
        runner.assert_not_called()


if __name__=='__main__':
    unittest.main()
