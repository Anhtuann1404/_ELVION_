import io
import struct
import time
import unittest
from unittest.mock import Mock, patch
from tempfile import TemporaryDirectory
from uuid import uuid4

from elvion.browser.contracts import VisionFrame, GroundingResult
from elvion.browser.controller import BrowserController
from elvion.browser.runtime import web_runtime
from elvion.browser.session import BrowserError, BrowserSession, public_url
from elvion.core.contracts import TaskRequest, TaskStatus, ConfirmationResponse, ContractError


class FakeBrowser:
    def __init__(self):
        self.results = {}
        self.calls = []
        self.current = None
    def available(self): return True
    def navigate(self, url, *, authorized):
        assert authorized()
        self.calls.append(url)
        self.current = {'url':url, 'title':'Fixture title', 'ready':True, 'visible_results':0}
    def search(self, query, *, authorized):
        from urllib.parse import urlencode
        self.navigate('https://duckduckgo.com/?'+urlencode({'q':query}), authorized=authorized)
        self.current['visible_results'] = 1
        self.results = {'fixture-handle': {'url':'https://example.com/', 'title':'Fixture result'}}
    def state(self): return self.current
    def result_locator(self, handle):
        locator = Mock()
        locator.count.return_value = 1
        locator.is_visible.return_value = True
        return locator
    def open_result(self, handle, *, authorized, mode, grounder=None):
        self.navigate(self.results[handle]['url'], authorized=authorized)


def approval(request):
    return ConfirmationResponse(confirmation_id=request.confirmation_id, action_digest=request.action_digest, approved=True)


class BrowserWorkflowTests(unittest.TestCase):
    def test_queued_close_event_is_processed_before_reusing_page(self):
        session = BrowserSession()
        old_page, old_browser, old_context, old_driver = Mock(), Mock(), Mock(), Mock()
        old_page.is_closed.return_value = False
        old_browser.is_connected.return_value = True
        def deliver_close():
            old_page.is_closed.return_value = True
            raise RuntimeError('closed during read-only liveness check')
        old_page.title.side_effect = deliver_close
        session.page, session.browser, session.context, session.playwright = old_page, old_browser, old_context, old_driver
        driver, factory = Mock(), Mock()
        driver.chromium.launch.return_value.new_context.return_value.new_page.return_value.url = 'https://example.com'
        factory.return_value.start.return_value = driver
        with patch.dict('sys.modules', {'playwright': Mock(), 'playwright.sync_api': Mock(sync_playwright=factory)}):
            session.navigate('https://example.com', authorized=lambda: True)
        old_page.title.assert_called_once()
        old_page.goto.assert_not_called()
        old_context.close.assert_called_once()
        session.page.goto.assert_called_once()

    def test_live_page_is_reused_and_failed_probe_is_not_restarted_blindly(self):
        session = BrowserSession()
        session.page, session.browser = Mock(), Mock()
        session.page.is_closed.return_value = False
        session.browser.is_connected.return_value = True
        page = session.page
        session.start()
        self.assertIs(session.page, page)
        page.title.assert_called_once()
        page.title.side_effect = RuntimeError('PRIVATE_ERROR')
        with self.assertRaisesRegex(BrowserError, '^WEB_BROWSER_UNAVAILABLE$'):
            session.start()
        self.assertIs(session.page, page)
        session.browser.close.assert_not_called()

    def test_closed_browser_is_recreated_before_new_navigation(self):
        session = BrowserSession()
        old_page, old_browser, old_context, old_driver = Mock(), Mock(), Mock(), Mock()
        old_page.is_closed.return_value = True
        session.page, session.browser, session.context, session.playwright = old_page, old_browser, old_context, old_driver
        driver = Mock()
        driver.chromium.launch.return_value.new_context.return_value.new_page.return_value.url = 'https://example.com'
        factory = Mock()
        factory.return_value.start.return_value = driver
        module = Mock(sync_playwright=factory)
        with patch.dict('sys.modules', {'playwright': Mock(), 'playwright.sync_api': module}):
            session.navigate('https://example.com', authorized=lambda: True)
        old_context.close.assert_called_once()
        old_browser.close.assert_called_once()
        old_driver.stop.assert_called_once()
        old_page.goto.assert_not_called()
        session.page.goto.assert_called_once_with('https://example.com', wait_until='domcontentloaded', timeout=20000)

    def test_navigation_errors_keep_fixed_reason_and_never_retry(self):
        for error, reason in [(BrowserError('WEB_BROWSER_CLOSED'), 'WEB_BROWSER_CLOSED'),
                              (RuntimeError('PRIVATE_URL_SECRET'), 'WEB_DRIVER_FAILURE')]:
            session = FakeBrowser()
            session.navigate = Mock(side_effect=error)
            report = web_runtime(session).run(TaskRequest(utterance='Mở web https://example.com'),
                frozenset({'web.open'}), confirmation_handler=approval)
            self.assertEqual(report.status, TaskStatus.UNCERTAIN)
            self.assertEqual(report.evidence, {'reason': reason})
            session.navigate.assert_called_once()

    @unittest.skip("CLI integration is owned by the active main working tree")
    def test_interactive_web_does_not_enable_unqualified_vision_model(self):
        from elvion.interface.session import InteractiveSession
        with TemporaryDirectory() as root:
            session = InteractiveSession(data_dir=root, no_trace=True,
                                         model_provider=Mock(model='qwen3.5:4b'))
            with patch('elvion.browser.runtime.web_runtime') as factory:
                agent = session._agent('Tìm trên web thuật toán')
                factory.assert_called_once_with(session._browser_session, None)
                self.assertIs(agent, factory.return_value)

    def test_registry_aims_selects_vision_when_dom_target_is_unavailable(self):
        session = FakeBrowser()
        session.results = {'handle': {'url':'https://example.com/', 'title':'Search result'}}
        locator = Mock()
        locator.count.return_value = 0
        session.result_locator = lambda handle: locator
        session.open_result = Mock(side_effect=lambda handle, **kw: session.navigate(session.results[handle]['url'], authorized=kw['authorized']))
        report = web_runtime(session, grounder=Mock()).run(TaskRequest(utterance='Mở kết quả 1'),
            frozenset({'web.open_result'}), confirmation_handler=approval)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        self.assertEqual(report.selected_method.value, 'vision')
        self.assertEqual(session.open_result.call_args.kwargs['mode'], 'vision')

    def test_aims_dom_priority_and_no_fallback_after_uncertain_click(self):
        session, grounder = Mock(), Mock()
        locator = Mock()
        locator.count.return_value = 1
        locator.is_visible.return_value = True
        locator.click.side_effect = RuntimeError('uncertain')
        controller = BrowserController(session, grounder=grounder)
        with self.assertRaises(BrowserError):
            controller.click(target='Search', role='button', locator=locator, authorized=lambda:True)
        self.assertEqual(controller.decisions[0]['chosen'], 'browser.ui.dom')
        grounder.locate.assert_not_called()
        locator.click.assert_called_once()

    def test_vision_only_does_not_inspect_dom_and_missing_model_abstains(self):
        locator = Mock()
        controller = BrowserController(Mock())
        with self.assertRaises(BrowserError):
            controller.click(target='Search', role='button', locator=locator, authorized=lambda:True, mode='vision')
        locator.count.assert_not_called()
        locator.click.assert_not_called()

    def test_trace_omits_query_and_url(self):
        import tempfile
        from pathlib import Path
        from elvion.storage.traces import TraceStore
        with tempfile.TemporaryDirectory() as root:
            web_runtime(FakeBrowser(), TraceStore(root)).run(TaskRequest(utterance='Tìm trên web PRIVATE_QUERY_SENTINEL'),
                frozenset({'web.search'}), confirmation_handler=approval)
            text = '\n'.join(p.read_text() for p in Path(root).rglob('*.jsonl'))
            self.assertNotIn('PRIVATE_QUERY_SENTINEL', text)
            self.assertNotIn('https://duckduckgo.com', text)
            self.assertIn('web.search', text)

    def test_search_open_result_and_independent_verification(self):
        session = FakeBrowser()
        agent = web_runtime(session)
        report = agent.run(TaskRequest(utterance='Tìm trên web thuật toán A*'), frozenset({'web.search'}), confirmation_handler=approval)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        report = agent.run(TaskRequest(utterance='Mở kết quả 1'), frozenset({'web.open_result'}), confirmation_handler=approval)
        self.assertEqual(report.status, TaskStatus.SUCCEEDED)
        self.assertEqual(len(session.calls), 2)

    def test_missing_grant_and_declined_confirmation_do_not_navigate(self):
        for grants in (frozenset(), frozenset({'web.open'})):
            session = FakeBrowser()
            def decline(req):
                return ConfirmationResponse(confirmation_id=req.confirmation_id, action_digest=req.action_digest, approved=False)
            report = web_runtime(session).run(TaskRequest(utterance='Mở web https://example.com'), grants, confirmation_handler=decline)
            self.assertNotEqual(report.status, TaskStatus.SUCCEEDED)
            self.assertEqual(session.calls, [])

    def test_wrong_postcondition_is_not_success_and_no_retry(self):
        session = FakeBrowser()
        session.state = lambda: {'url':'https://different.example/', 'title':'Wrong', 'ready':True}
        report = web_runtime(session).run(TaskRequest(utterance='Mở web https://example.com'), frozenset({'web.open'}), confirmation_handler=approval)
        self.assertNotEqual(report.status, TaskStatus.SUCCEEDED)
        self.assertEqual(len(session.calls), 1)

    def test_navigation_error_is_uncertain_and_not_retried(self):
        session = FakeBrowser()
        session.navigate = Mock(side_effect=BrowserError('WEB_NAVIGATION_UNCERTAIN'))
        report = web_runtime(session).run(TaskRequest(utterance='Mở web https://example.com'), frozenset({'web.open'}), confirmation_handler=approval)
        self.assertEqual(report.status, TaskStatus.UNCERTAIN)
        session.navigate.assert_called_once()

    def test_rejects_non_public_schemes_and_credentials(self):
        for url in ('file:///tmp/a', 'javascript:alert(1)', 'https://127.0.0.1', 'https://10.0.0.1',
                    'https://localhost', 'https://user:pass@example.com', 'https://example.com:8443', 'https://2130706433'):
            with self.assertRaises(BrowserError): public_url(url)
        self.assertEqual(public_url('https://example.com/a?q=b'), 'https://example.com/a?q=b')

    def test_current_results_only(self):
        report = web_runtime(FakeBrowser()).run(TaskRequest(utterance='Mở kết quả 1'), frozenset({'web.open_result'}), confirmation_handler=approval)
        self.assertNotEqual(report.status, TaskStatus.SUCCEEDED)

    def test_vision_freshness_box_and_authorization(self):
        # Contract header fixture only; B owns full image decode validation.
        png = b'\x89PNG\r\n\x1a\n'+struct.pack('>I', 13)+b'IHDR'+struct.pack('>II', 100, 100)+b'\x08\x02\x00\x00\x00'+b'\0'*4
        for change in ('none', 'click-error', 'stale', 'outside', 'wrong-frame', 'denied', 'abstain', 'changed-pixels'):
            session = Mock(page_id='page', revision=1, frame_id='frame')
            session.frame_is_current.return_value = change != 'changed-pixels'
            # Reject unsupported keywords instead of allowing arbitrary Mock calls.
            session.page.mouse.click = Mock(side_effect=lambda x, y: None)
            if change == 'click-error':
                def failed_click(x, y):
                    raise RuntimeError('Transport failure after dispatch')
                session.page.mouse.click.side_effect = failed_click
            session.snapshot.return_value = VisionFrame('frame', 'page', 1, png, 100, 100, 0)
            grounder = Mock()
            grounder.locate.return_value = GroundingResult('wrong' if change == 'wrong-frame' else 'frame',
                'not_found' if change == 'abstain' else 'found', None if change == 'abstain' else
                (90, 90, 20, 20) if change == 'outside' else (10, 10, 20, 20))
            controller = BrowserController(session, grounder=grounder, clock=lambda: 20 if change == 'stale' else 1)
            if change == 'none':
                controller.click_vision(target='Search', role='button', authorized=lambda:True)
                session.page.mouse.click.assert_called_once_with(20, 20)
            elif change == 'click-error':
                with self.assertRaisesRegex(BrowserError, '^WEB_CLICK_UNCERTAIN$'):
                    controller.click_vision(target='Search', role='button', authorized=lambda:True)
                session.page.mouse.click.assert_called_once_with(20, 20)
                grounder.locate.assert_called_once()
            else:
                with self.assertRaises(BrowserError):
                    controller.click_vision(target='Search', role='button', authorized=lambda:change != 'denied')
                session.page.mouse.click.assert_not_called()

    def test_contract_rejects_invalid_boxes_and_images(self):
        for box in ((True, 0, 1, 1), (0, 0, float('nan'), 1), (0, 0, 0, 1), (-1, 0, 1, 1)):
            with self.assertRaises(ContractError): GroundingResult('frame', 'found', box)
        with self.assertRaises(ContractError): VisionFrame('f', 'p', 1, b'not PNG', 100, 100, 0)
