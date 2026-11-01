from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from benchmarks.vision.runner import frame_for,load_cases
from tests.test_vision_image_crop import png
from elvion.vision.presentation import resize_crop
from elvion.vision.image_crop import CropError
from benchmarks.web_observation.label_presentation import PROFILES,read_system


class PresentationTests(TestCase):
    @classmethod
    def setUpClass(cls):cls.frame=frame_for(load_cases()[0])

    def test_scaling_changes_input_pixels_only_and_keeps_original_frame(self):
        image=png(60,40);runner=Mock(return_value=SimpleNamespace(returncode=0,stdout=png(120,80)))
        original=self.frame.image_png
        self.assertEqual(resize_crop(self.frame,image,factor=2,helper='/fake/helper',runner=runner),png(120,80))
        self.assertEqual(runner.call_args.args[0],['/fake/helper','2'])
        self.assertEqual(runner.call_args.kwargs['input'],image)
        self.assertFalse(runner.call_args.kwargs['shell'])
        self.assertEqual(self.frame.image_png,original)

    def test_invalid_scale_and_oversized_inputs_do_not_call_helper(self):
        runner=Mock()
        for factor in (True,0,3,8):
            with self.assertRaises(CropError):resize_crop(self.frame,png(60,40),factor=factor,helper='/fake',runner=runner)
        with self.assertRaises(CropError):resize_crop(self.frame,png(1100,20),factor=4,helper='/fake',runner=runner)
        runner.assert_not_called()

    def test_bad_native_outputs_and_wrong_scaled_dimensions_are_rejected(self):
        for output in (b'bad',png(121,80),png(60,40)):
            with self.assertRaises(CropError):
                resize_crop(self.frame,png(60,40),factor=2,helper='/fake',
                    runner=Mock(return_value=SimpleNamespace(returncode=0,stdout=output)))

    def test_identity_is_exact_and_profiles_do_not_expose_expected_label(self):
        image=png(60,40);runner=Mock()
        self.assertIs(resize_crop(self.frame,image,factor=1,helper='/fake',runner=runner),image)
        runner.assert_not_called()
        self.assertEqual(len(PROFILES),len({p[0] for p in PROFILES}))
        self.assertNotIn('red outline',read_system(False))
        self.assertIn('red outline',read_system(True))
