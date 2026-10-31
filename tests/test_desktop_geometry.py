from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch

from benchmarks.desktop_targeting.cases import snapshot,node,NOW
from elvion.desktop_observation import DesktopObservationResult
from elvion.desktop_targeting import locate_control
from elvion.desktop_targeting.geometry import Display,DisplayGeometryBackend,check_geometry
from scripts.check_desktop_geometry import main


class DesktopGeometryTests(TestCase):
    def setUp(self):
        self.snapshot=snapshot(node('window',role='AXWindow',bbox=(1000.,-600.,300.,500.)),
            node('seven','7',parent='window',bbox=(1103.,-519.,48.,48.)))
        self.target=locate_control(self.snapshot,label='7',now_ns=NOW,scope='calculator_content')
        self.displays=(Display(1,(0.,0.,1512.,982.),2.),Display(2,(0.,-900.,1600.,900.),1.))

    def check(self,**kwargs):
        return check_geometry(kwargs.pop('snapshot',self.snapshot),kwargs.pop('target',self.target),
                              kwargs.pop('displays',self.displays),now_ns=kwargs.pop('now_ns',NOW),**kwargs)

    def test_negative_origin_and_scale_preserve_native_points(self):
        result=self.check()
        self.assertEqual(result['status'],'geometry_consistent')
        self.assertEqual(result['display_id'],2)
        self.assertEqual(result['bbox'],(1103.,-519.,48.,48.))
        self.assertFalse(result['visibility_verified']);self.assertFalse(result['freshness_for_execution'])
        self.assertEqual(result['actions'],0)

    def test_target_must_match_snapshot_and_window(self):
        self.assertEqual(self.check(target=replace(self.target,snapshot_id='other'))['reason'],'TARGET_SNAPSHOT_MISMATCH')
        self.assertEqual(self.check(target=replace(self.target,bbox=(0.,0.,10.,10.)))['reason'],'TARGET_NODE_MISMATCH')
        ax=replace(self.snapshot,elements=(self.snapshot.elements[0],
            replace(self.snapshot.elements[1],bbox=(1000.,0.,300.,500.)),self.snapshot.elements[2]))
        self.assertEqual(self.check(snapshot=ax)['reason'],'TARGET_OUTSIDE_WINDOW')
        ax=replace(self.snapshot,elements=(self.snapshot.elements[0],self.snapshot.elements[1],
                                         replace(self.snapshot.elements[2],parent_id='root')))
        self.assertEqual(self.check(snapshot=ax)['reason'],'WINDOW_BBOX_UNAVAILABLE')

    def test_single_display_containment_and_display_protocol(self):
        self.assertEqual(self.check(displays=(self.displays[0],))['reason'],'TARGET_NOT_ON_UNIQUE_DISPLAY')
        self.assertEqual(self.check(displays=self.displays+(Display(3,self.displays[1].bbox,1.),))['reason'],'TARGET_NOT_ON_UNIQUE_DISPLAY')
        self.assertEqual(self.check(displays=(Display(True,self.displays[1].bbox,1.),))['reason'],'INVALID_DISPLAY_LAYOUT')
        self.assertEqual(self.check(displays=(Display(2,self.displays[1].bbox,float('nan')),))['reason'],'INVALID_DISPLAY_LAYOUT')

    def test_stale_future_truncated_and_unselected_targets_refuse(self):
        self.assertEqual(self.check(now_ns=4_000_000_001)['reason'],'SNAPSHOT_STALE')
        self.assertEqual(self.check(now_ns=999_999_999)['reason'],'SNAPSHOT_STALE')
        self.assertEqual(self.check(snapshot=replace(self.snapshot,truncated=True,truncation_reason='NODE_LIMIT'))['reason'],'SNAPSHOT_TRUNCATED')
        self.assertEqual(self.check(target=replace(self.target,status='unavailable'))['reason'],'TARGET_NOT_FOUND')

    def test_native_protocol_and_no_shell(self):
        payload={'version':1,'status':'observed','reason':None,'displays':[{'id':2,'bbox':[0,-900,1600,900],'scale':1}]}
        runner=Mock(return_value=SimpleNamespace(returncode=0,stdout=json.dumps(payload).encode()))
        backend=DisplayGeometryBackend(runner=runner);backend.binary=Path('/usr/bin/true')
        self.assertEqual(backend.read(),(self.displays[1],))
        self.assertFalse(runner.call_args.kwargs['shell'])
        payload['version']=True;runner.return_value.stdout=json.dumps(payload).encode()
        with self.assertRaises(ValueError):backend.read()
        runner.return_value.stdout=b'{"version":1,"version":1}'
        with self.assertRaises(ValueError):backend.read()

    def test_demo_compiles_before_capture_observes_once_and_detects_layout_change(self):
        events=[]
        backend=SimpleNamespace(prepare=lambda:events.append('prepare'),
            read=Mock(side_effect=[self.displays,(self.displays[0],)]))
        observer=Mock(side_effect=lambda *a,**k:(events.append('observe') or DesktopObservationResult('observed',self.snapshot)))
        with patch('sys.stdout',new_callable=StringIO) as output:
            status=main(['--include-labels'],observer=observer,backend=backend)
        self.assertEqual(status,2);self.assertEqual(events,['prepare','observe'])
        self.assertEqual(json.loads(output.getvalue())['reason'],'DISPLAY_LAYOUT_CHANGED')
        observer.assert_called_once()

    def test_demo_requires_opt_in_before_any_backend(self):
        observer=Mock();backend=Mock()
        with patch('sys.stdout',new_callable=StringIO):self.assertEqual(main([],observer=observer,backend=backend),2)
        observer.assert_not_called();backend.prepare.assert_not_called()
