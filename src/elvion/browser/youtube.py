"""Small, opt-in YouTube search flow using the existing web policy and verifier."""
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from elvion.browser.runtime import web_runtime
from elvion.browser.session import BrowserSession
from elvion.core.contracts import TaskRequest, TaskStatus


class YouTubeError(ValueError):
    pass


@dataclass(frozen=True)
class VideoResult:
    handle: str
    title: str
    channel: str
    video_id: str
    url: str


def video_id(url: str) -> str | None:
    parts = urlsplit(url)
    if parts.hostname != "www.youtube.com" or parts.path != "/watch":
        return None
    values = parse_qs(parts.query).get("v", [])
    value = values[0] if len(values) == 1 else ""
    return value if len(value) == 11 and all(c.isalnum() or c in "_-" for c in value) else None


class YouTubeSession(BrowserSession):
    def navigate(self, url, *, authorized):
        super().navigate(url, authorized=authorized)
        if urlsplit(url).hostname == "www.youtube.com":
            try:
                self.page.wait_for_function("document.title.length > 0", timeout=10000)
            except Exception:
                raise YouTubeError("YT_PAGE_NOT_READY") from None


class YouTubeWorkflow:
    def __init__(self, session: YouTubeSession):
        self.session = session
        self.results: dict[str, VideoResult] = {}
        self.search_revision: int | None = None
        self.search_url: str | None = None

    def _open(self, url, grants, confirm):
        return web_runtime(self.session).run(
            TaskRequest(utterance=f"Mở web {url}"),
            frozenset(grants),
            confirmation_handler=confirm,
        )

    def search(self, query: str, *, grants, confirm) -> tuple[object, tuple[VideoResult, ...]]:
        if type(query) is not str or not 1 <= len(query.strip()) <= 512:
            raise YouTubeError("YT_INVALID_QUERY")
        self.results.clear()
        self.search_revision = self.search_url = None
        url = "https://www.youtube.com/results?" + urlencode({"search_query": query.strip()})
        report = self._open(url, grants, confirm)
        if report.status != TaskStatus.SUCCEEDED:
            return report, ()
        try:
            self.session.page.locator("ytd-video-renderer").first.wait_for(timeout=10000)
        except Exception:
            raise YouTubeError("YT_NO_CLEAR_RESULTS") from None
        revision, page_url = self.session.revision, self.session.page.url
        found: list[VideoResult] = []
        rows = self.session.page.locator("ytd-video-renderer").all()[:20]
        first_hrefs = []
        for row in rows:
            try:
                if not row.is_visible():
                    first_hrefs.append(None)
                    continue
                anchor = row.locator("a#video-title").first
                href = anchor.get_attribute("href") or ""
                first_hrefs.append(href)
                title = (anchor.get_attribute("title") or anchor.inner_text()).strip()
                vid = video_id("https://www.youtube.com" + href)
                channel = row.locator("ytd-channel-name a").first.inner_text().strip()
                if not title or not channel or not vid:
                    continue
                found.append(VideoResult(uuid4().hex, title[:160], channel[:100], vid,
                                         f"https://www.youtube.com/watch?v={vid}"))
            except Exception:
                raise YouTubeError("YT_RESULTS_CHANGED") from None
            if len(found) == 5:
                break
        current_rows = self.session.page.locator("ytd-video-renderer").all()[:len(first_hrefs)]
        try:
            current_hrefs = [
                (row.locator("a#video-title").first.get_attribute("href") or "") if row.is_visible() else None
                for row in current_rows
            ]
        except Exception:
            raise YouTubeError("YT_RESULTS_CHANGED") from None
        if (revision, page_url) != (self.session.revision, self.session.page.url):
            raise YouTubeError("YT_RESULTS_CHANGED")
        if first_hrefs != current_hrefs:
            raise YouTubeError("YT_RESULTS_CHANGED")
        if not found:
            raise YouTubeError("YT_NO_CLEAR_RESULTS")
        self.search_revision, self.search_url = revision, page_url
        self.results = {item.handle: item for item in found}
        return report, tuple(found)

    def open_video(self, handle: str, *, grants, confirm) -> tuple[object, bool]:
        item = self.results.get(handle)
        page = self.session.page
        if (item is None or page is None or page.is_closed() or
                self.search_revision != self.session.revision or
                self.search_url != getattr(self.session.page, "url", None)):
            raise YouTubeError("YT_RESULT_EXPIRED")
        self.results.clear()
        report = self._open(item.url, grants, confirm)
        return report, report.status == TaskStatus.SUCCEEDED and video_id(self.session.page.url) == item.video_id
