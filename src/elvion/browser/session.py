"""One owned Chromium context; public HTTPS navigation and read-only observations."""
import importlib.util
import ipaddress
import json
import socket
import re
import time
from urllib.parse import urlsplit, urlencode, urljoin, parse_qs, unquote
from uuid import uuid4

from elvion.browser.contracts import VisionFrame


class BrowserError(ValueError):
    pass


def public_url(value):
    if type(value) is not str or not value or len(value) > 2048 or '\\' in value or any(c.isspace() or ord(c) < 32 for c in value):
        raise BrowserError('WEB_INVALID_URL')
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password or
                url.port not in (None, 443) or url.hostname.endswith(('.localhost', '.local', '.internal')) or
                url.hostname == 'localhost' or '.' not in url.hostname):
            raise ValueError
        try: address = ipaddress.ip_address(url.hostname)
        except ValueError: address = None
        if address is not None and not address.is_global:
            raise ValueError
        if address is None and re.fullmatch(r'(?:0x[0-9a-f]+|[0-9.]+)', url.hostname, re.I):
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise BrowserError('WEB_INVALID_URL') from None


class BrowserSession:
    def __init__(self, *, headless=False):
        if type(headless) is not bool:
            raise ValueError('headless must be boolean')
        self.headless = headless
        self.playwright = self.browser = self.context = self.page = None
        self.page_id = uuid4().hex
        self.revision = 0
        self.frame_id = None
        self.results = {}
        self.allowed_hosts = set()

    def available(self):
        return importlib.util.find_spec('playwright') is not None

    def _route(self, route):
        try:
            address = route.request.url
            if address == 'about:blank':
                route.continue_(); return
            public_url(address)
            host = urlsplit(address).hostname
            if host not in self.allowed_hosts:
                raise BrowserError('WEB_OUTSIDE_SCOPE')
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
                raise BrowserError('WEB_PRIVATE_ADDRESS')
            if route.request.method not in {'GET', 'HEAD'}:
                raise BrowserError('WEB_WRITE_BLOCKED')
            route.continue_()
        except Exception:
            route.abort()

    def start(self):
        if self.page is not None:
            if not self.page.is_closed() and self.browser is not None and self.browser.is_connected():
                # These two flags are cached. While the CLI waits for keyboard
                # input, Playwright's sync event loop is suspended and a close
                # event can still be queued. A read-only round trip flushes it
                # before deciding whether the previous page is reusable.
                try:
                    self.page.title()
                except Exception:
                    if not self.page.is_closed() and self.browser.is_connected():
                        raise BrowserError('WEB_BROWSER_UNAVAILABLE') from None
                if not self.page.is_closed() and self.browser.is_connected():
                    return
            # A user can close the owned window between requests. Recreate it
            # before a new navigation, never retry a dispatched action.
            self.close()
        try:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.context = self.browser.new_context(viewport={'width':1280, 'height':800},
                device_scale_factor=1, accept_downloads=False, service_workers='block')
            self.context.route('**/*', self._route)
            self.context.route_web_socket('**/*', lambda ws: ws.close())
            self.page = self.context.new_page()
            self.context.on('page', lambda p: p.close() if p != self.page else None)
            self.page.on('framenavigated', lambda _: self.invalidate())
            self.page.set_default_timeout(8000)
        except Exception:
            self.close()
            raise BrowserError('WEB_BROWSER_UNAVAILABLE') from None

    def invalidate(self):
        self.revision += 1
        self.frame_id = None

    def navigate(self, url, *, authorized):
        if not authorized(): raise BrowserError('WEB_ACTION_DENIED')
        public_url(url)
        self.results = {}
        self.allowed_hosts = {urlsplit(url).hostname}
        self.start()
        if not authorized(): raise BrowserError('WEB_ACTION_DENIED')
        self.invalidate()
        try:
            self.page.goto(url, wait_until='domcontentloaded', timeout=20000)
            if urlsplit(self.page.url).hostname not in self.allowed_hosts:
                raise BrowserError('WEB_REDIRECT_OUTSIDE_SCOPE')
        except Exception:
            if self.page.is_closed() or not self.browser.is_connected():
                raise BrowserError('WEB_BROWSER_CLOSED') from None
            raise BrowserError('WEB_NAVIGATION_UNCERTAIN') from None

    def search(self, query, *, authorized):
        self.results = {}
        self.navigate('https://duckduckgo.com/?'+urlencode({'q':query}), authorized=authorized)
        try:
            self.page.locator('a[data-testid="result-title-a"]').first.wait_for(timeout=10000)
            links = self.page.locator('a[data-testid="result-title-a"]').all()[:10]
            for link in links:
                title, source_href = link.inner_text().strip(), link.get_attribute('href')
                if not title or len(title) > 160 or not source_href or len(source_href) > 2048:
                    continue
                href = urljoin(self.page.url, source_href)
                if urlsplit(href).hostname == 'duckduckgo.com':
                    href = parse_qs(urlsplit(href).query).get('uddg', [href])[0]
                try:
                    public_url(href)
                except BrowserError:
                    continue
                self.results[uuid4().hex] = {'title':title[:256], 'url':href,
                                             'source_href':source_href}
            if not self.results:
                raise ValueError
        except Exception:
            raise BrowserError('WEB_SEARCH_NOT_VERIFIED') from None

    def snapshot(self):
        if self.page is None:
            raise BrowserError('WEB_NO_PAGE')
        self.frame_id = uuid4().hex
        captured = time.monotonic()
        return VisionFrame(self.frame_id, self.page_id, self.revision,
                           self.page.screenshot(type='png', full_page=False, caret='hide'), 1280, 800, captured)

    def frame_is_current(self, frame):
        """Conservative visual recheck. Never refresh the model frame's timestamp/identity."""
        if (type(frame) is not VisionFrame or self.page is None or
                (self.frame_id, self.page_id, self.revision) != (frame.frame_id, frame.page_id, frame.revision)):
            return False
        try:
            current = self.page.screenshot(type='png', full_page=False, caret='hide')
            return (current == frame.image_png and
                    (self.frame_id, self.page_id, self.revision) == (frame.frame_id, frame.page_id, frame.revision))
        except Exception:
            return False

    def result_locator(self, handle):
        item = self.results.get(handle)
        if self.page is None or item is None or not item.get('source_href'):
            raise BrowserError('WEB_RESULT_EXPIRED')
        href = json.dumps(item['source_href'], ensure_ascii=False)
        return self.page.get_by_role('link', name=item['title'], exact=True).and_(
            self.page.locator(f'a[data-testid="result-title-a"][href={href}]'))

    def open_result(self, handle, *, authorized, mode, grounder=None):
        from elvion.browser.controller import BrowserController
        item = self.results.get(handle)
        if item is None or not authorized(): raise BrowserError('WEB_RESULT_EXPIRED')
        locator = None if mode == 'vision' else self.result_locator(handle)
        self.allowed_hosts.add(urlsplit(public_url(item['url'])).hostname)
        controller = BrowserController(self, grounder=grounder)
        try:
            controller.click(target=item['title'], role='link', locator=locator, authorized=authorized, mode=mode)
            self.page.wait_for_load_state('domcontentloaded', timeout=8000)
        finally:
            self.results = {}

    def read_article(self, *, max_chars=50_000):
        from elvion.browser.reader import read_page
        return read_page(self, max_chars=max_chars)

    def state(self):
        if self.page is None:
            return None
        return {'url': self.page.url, 'title': self.page.title(),
                'ready': self.page.evaluate('document.readyState') in {'interactive', 'complete'},
                'visible_results': self.page.locator('a[data-testid="result-title-a"]:visible').count()}

    def close(self):
        for value in (self.context, self.browser):
            if value is not None:
                try: value.close()
                except Exception: pass
        if self.playwright is not None:
            try: self.playwright.stop()
            except Exception: pass
        self.page = self.context = self.browser = self.playwright = None
