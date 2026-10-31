"""Opt-in read-only Calculator target/window/display consistency probe."""
import argparse
import json
import subprocess

from elvion.desktop_observation import observe_app
from elvion.desktop_targeting import locate_control
from elvion.desktop_targeting.geometry import DisplayGeometryBackend,check_geometry,DISPLAY_ERRORS


def main(argv=None,*,observer=observe_app,backend=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',default='7')
    parser.add_argument('--include-labels',action='store_true')
    args=parser.parse_args(argv)
    if not args.include_labels:
        print(json.dumps({'status':'unavailable','reason':'LABEL_OPT_IN_REQUIRED','actions':0}));return 2
    try:
        backend=DisplayGeometryBackend() if backend is None else backend
        backend.prepare()  # Compile before capturing the short-lived snapshot.
        before=backend.read()
        observed=observer('com.apple.calculator',include_labels=True)
        if observed.status!='observed' or observed.snapshot is None:
            print(json.dumps({'status':observed.status,'reason':observed.reason,'actions':0}));return 2
        target=locate_control(observed.snapshot,label=args.label,scope='calculator_content')
        after=backend.read()
        if before!=after:
            print(json.dumps({'status':'unavailable','reason':'DISPLAY_LAYOUT_CHANGED','actions':0}));return 2
        result=check_geometry(observed.snapshot,target,after)
        result['target_status']=target.status;result['target_reason']=target.reason
        result['layout_samples_match']=True
        print(json.dumps(result));return 0 if result['status']=='geometry_consistent' else 1
    except (ValueError,OSError,subprocess.SubprocessError,TypeError,KeyError,RecursionError) as error:
        reason=str(error) if type(error) is ValueError and str(error) in DISPLAY_ERRORS else 'GEOMETRY_BACKEND_UNAVAILABLE'
        print(json.dumps({'status':'unavailable','reason':reason,'actions':0}));return 2


if __name__=='__main__':raise SystemExit(main())
