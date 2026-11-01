from unittest import TestCase
from unittest.mock import Mock

from benchmarks.vision_labels.role_profiles import ROLE_EVIDENCE_NOTE, with_role_profile
from benchmarks.vision_labels.replay import ROLE_EVIDENCE_NOTE as REPLAY_NOTE


class RoleProfileTests(TestCase):
    def test_research_profile_keeps_images_anchors_schemas_and_label_reads(self):
        self.assertEqual(REPLAY_NOTE, ROLE_EVIDENCE_NOTE)
        complete=Mock(return_value='reply')
        wrapped=with_role_profile(complete,'visual-evidence-v1')
        for phase in ('transcribe_visible_label','actual_element_type','classify_actual_type'):
            request={'role':phase,'target':'','system':'baseline','image_png':b'original',
                     'schema':{'version':1},'candidates':[{'bbox_css':[1,2,3,4]}]}
            self.assertEqual(wrapped(**request),'reply')
            actual=complete.call_args.kwargs
            self.assertEqual(actual,request | {'system':'baseline'+(
                ROLE_EVIDENCE_NOTE if phase!='transcribe_visible_label' else '')})
            self.assertEqual(request['system'],'baseline')

    def test_default_is_exact_passthrough_and_invalid_profile_fails(self):
        complete=Mock(return_value='reply')
        request={'role':'actual_element_type','system':'baseline'}
        with_role_profile(complete,'current')(**request)
        self.assertEqual(complete.call_args.kwargs,request)
        with self.assertRaises(ValueError):with_role_profile(complete,'missing')
