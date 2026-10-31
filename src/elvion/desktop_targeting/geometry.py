"""Read-only AX/window/display consistency, never a permission or click verifier."""
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time

from elvion.models.structured import strict_json
from .contracts import DesktopTargetResult
from .locator import _snapshot_valid, _box_valid, SCOPES

DISPLAY_ERRORS=frozenset(('MACOS_REQUIRED','DISPLAY_BUILD_FAILED','DISPLAY_READ_FAILED',
    'DISPLAY_PROTOCOL_ERROR','DISPLAY_LAYOUT_UNAVAILABLE','DISPLAY_ID_UNAVAILABLE',
    'DISPLAY_COORDINATE_MISMATCH'))


@dataclass(frozen=True)
class Display:
    id: int
    bbox: tuple
    scale: float


def _displays_valid(displays):
    return (type(displays) is tuple and 1 <= len(displays) <= 16 and
        all(type(d) is Display and type(d.id) is int and d.id > 0 and _box_valid(d.bbox) and
            type(d.scale) in (int,float) and isfinite(d.scale) and d.scale > 0 for d in displays) and
        len({d.id for d in displays})==len(displays))


def _inside(child,parent):
    x,y,w,h=child;px,py,pw,ph=parent
    return px <= x and py <= y and x+w <= px+pw and y+h <= py+ph


def check_geometry(snapshot,target,displays,*,now_ns=None,max_age_ms=2000):
    base={'actions':0,'visibility_verified':False,'freshness_for_execution':False,
          'coordinate_space':'native_ax_screen_points'}
    def reject(reason):return dict(base,status='unavailable',reason=reason)
    if not _snapshot_valid(snapshot) or type(target) is not DesktopTargetResult:
        return reject('INVALID_GEOMETRY_INPUT')
    if (type(max_age_ms) is not int or not 1 <= max_age_ms <= 10000 or
            (now_ns is not None and (type(now_ns) is not int or now_ns <= 0))):
        return reject('INVALID_CLOCK_INPUT')
    if target.status!='found':return reject('TARGET_NOT_FOUND')
    if (target.snapshot_id!=snapshot.id or target.scope not in SCOPES or
            type(target.node_id) is not str):
        return reject('TARGET_SNAPSHOT_MISMATCH')
    now_ns=time.monotonic_ns() if now_ns is None else now_ns
    age=(now_ns-snapshot.captured_at_monotonic_ns)/1_000_000
    if age < 0 or age > max_age_ms:return reject('SNAPSHOT_STALE')
    if snapshot.truncated:return reject('SNAPSHOT_TRUNCATED')
    nodes={node.id:node for node in snapshot.elements};node=nodes.get(target.node_id)
    if (node is None or node.role!='AXButton' or node.enabled is not True or
            node.bbox is None or target.bbox!=node.bbox or target.role!=node.role or target.enabled is not True):
        return reject('TARGET_NODE_MISMATCH')
    parent=node.parent_id;window=None
    while parent is not None:
        ancestor=nodes[parent]
        if ancestor.role=='AXWindow':window=ancestor;break
        parent=ancestor.parent_id
    if window is None or window.bbox is None:return reject('WINDOW_BBOX_UNAVAILABLE')
    if not _inside(node.bbox,window.bbox):return reject('TARGET_OUTSIDE_WINDOW')
    if not _displays_valid(displays):return reject('INVALID_DISPLAY_LAYOUT')
    matches=[display for display in displays if _inside(node.bbox,display.bbox)]
    if len(matches)!=1:return reject('TARGET_NOT_ON_UNIQUE_DISPLAY')
    display=matches[0]
    return dict(base,status='geometry_consistent',reason='AX_WINDOW_AND_DISPLAY_CONTAIN_TARGET',
        snapshot_id=snapshot.id,node_id=node.id,target_scope=target.scope,bbox=node.bbox,
        window_bbox=window.bbox,display_id=display.id,display_bbox=display.bbox,
        display_scale=display.scale,age_ms=age)


class DisplayGeometryBackend:
    def __init__(self,*,runner=subprocess.run):
        self.runner=runner
        self.source=Path(__file__).resolve().parents[3]/'native/macos/DisplayGeometry.swift'
        self.binary=self.source.parents[2]/'artifacts/native'/('display-geometry-'+sha256(self.source.read_bytes()).hexdigest()[:16])

    def prepare(self):
        if sys.platform!='darwin':raise ValueError('MACOS_REQUIRED')
        if self.binary.is_file() and os.access(self.binary,os.X_OK):return
        self.binary.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.binary.parent,prefix='.display-build-') as folder:
            path=Path(folder);source=path/'main.swift';binary=path/'helper'
            source.write_bytes(self.source.read_bytes())
            result=self.runner(['/usr/bin/swiftc','-swift-version','5','-module-cache-path',
                str(path/'cache'),str(source),'-o',str(binary)],stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,timeout=60,check=False,shell=False)
            if result.returncode!=0 or not binary.is_file():raise ValueError('DISPLAY_BUILD_FAILED')
            binary.chmod(0o700);os.replace(binary,self.binary)

    def read(self):
        response=self.runner([str(self.binary)],capture_output=True,timeout=3,check=False,shell=False)
        if response.returncode!=0 or type(response.stdout) is not bytes or len(response.stdout)>65536:
            raise ValueError('DISPLAY_READ_FAILED')
        data=strict_json(response.stdout.decode('utf-8'))
        if (type(data) is not dict or set(data)!={'version','status','reason','displays'} or
                type(data['version']) is not int or data['version']!=1):
            raise ValueError('DISPLAY_PROTOCOL_ERROR')
        if data['status']!='observed' or data['reason'] is not None:
            if (data['status']=='unavailable' and type(data['reason']) is str and
                    data['reason'] in DISPLAY_ERRORS and data['displays']==[]):
                raise ValueError(data['reason'])
            raise ValueError('DISPLAY_PROTOCOL_ERROR')
        if type(data['displays']) is not list or len(data['displays'])>16:
            raise ValueError('DISPLAY_PROTOCOL_ERROR')
        displays=[]
        for row in data['displays']:
            if (type(row) is not dict or set(row)!={'id','bbox','scale'} or type(row['bbox']) is not list):
                raise ValueError('DISPLAY_PROTOCOL_ERROR')
            displays.append(Display(row['id'],tuple(row['bbox']),row['scale']))
        result=tuple(sorted(displays,key=lambda d:d.id))
        if not _displays_valid(result):raise ValueError('DISPLAY_PROTOCOL_ERROR')
        return result
