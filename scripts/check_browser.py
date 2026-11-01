"""Opt-in real Chromium fixture: no public network, no user browser profile."""
import argparse
from elvion.browser.controller import BrowserController
from elvion.browser.session import BrowserSession


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['dom', 'vision', 'auto'], default='dom')
    parser.add_argument('--vision-model')
    parser.add_argument('--grounder', choices=['model-v1', 'ocr-candidates-v1','ocr-verified-v2','ocr-verified-v3'], default='model-v1')
    args = parser.parse_args(argv)
    if args.mode == 'dom' and args.grounder != 'model-v1':
        parser.error('--grounder requires --mode vision or auto')
    grounder = None
    if args.mode != 'dom':
        if not args.vision_model: parser.error('Chọn --vision-model đã cài; không tự tải model')
        from elvion.vision import LocalVisionGrounder, OllamaVisionProvider
        provider = OllamaVisionProvider(model=args.vision_model, timeout=30)
        provider.check_local()
        if args.grounder in {'ocr-candidates-v1','ocr-verified-v2','ocr-verified-v3'}:
            from elvion.vision.ocr import AppleVisionOCR, OCRCandidateGrounder
            ocr = AppleVisionOCR(profile='upscale2x-v2')
            ocr.prepare()
            if args.grounder in {'ocr-verified-v2','ocr-verified-v3'}:
                from elvion.vision.semantic import OCRVerifiedGrounder, OCRPunctuationGrounder
                grounder = (OCRPunctuationGrounder if args.grounder == 'ocr-verified-v3' else OCRVerifiedGrounder)(provider, ocr)
            else:
                grounder = OCRCandidateGrounder(provider, ocr)
        else:
            grounder = LocalVisionGrounder(provider)
    session = BrowserSession()
    try:
        session.start()
        if args.mode == 'dom':
            html = '''<html><head><title>ELVION browser fixture</title></head>
            <body><button onclick="document.body.dataset.done='yes'">Fixture search</button></body></html>'''
        else:
            html = '''<html><head><title>ELVION canvas fixture</title></head><body style="margin:0">
            <canvas width="1280" height="800" id="surface"></canvas><script>
            const canvas=document.getElementById('surface'), c=canvas.getContext('2d');
            c.fillStyle='white';c.fillRect(0,0,1280,800);
            c.fillStyle='#1263a0';c.fillRect(480,350,280,70);
            c.fillStyle='white';c.font='24px Arial';c.fillText('Fixture search',530,393);
            canvas.onclick=e=>{if(e.offsetX>=480&&e.offsetX<760&&e.offsetY>=350&&e.offsetY<420)
              document.body.dataset.done='yes'};</script></body></html>'''
        session.page.set_content(html)
        controller = BrowserController(session, grounder=grounder)
        controller.click(target='Fixture search', role='button',
                         locator=session.page.get_by_role('button', name='Fixture search'), authorized=lambda:True, mode=args.mode)
        if session.page.get_attribute('body', 'data-done') != 'yes':
            raise RuntimeError('Fixture postcondition was not verified')
        frame = session.snapshot()
        print(f"PASS: {controller.decisions[-1]['chosen']} click + independent state read; PNG {frame.width}x{frame.height}.")
    finally:
        session.close()


if __name__ == '__main__':
    main()
