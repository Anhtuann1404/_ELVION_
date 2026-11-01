"""Clean text DOM reader and article extractor for local-first web understanding.

Extracts structured, boilerplate-free article content from raw HTML or an active
BrowserSession without relying on heavy vision models or remote cloud APIs.
"""
from dataclasses import dataclass
import html
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

from elvion.browser.session import BrowserError, BrowserSession

# Resource safety limits
MAX_HTML_CHARS = 5 * 1024 * 1024  # 5 MB character limit
MAX_EXTRACTED_CHARS = 50_000
MAX_PARAGRAPHS = 500
MAX_DOM_DEPTH = 256
MAX_OVERFLOW_DEPTH = 256
MAX_DOM_NODES = 20_000

# Field budget limits
MAX_TITLE_CHARS = 300
MAX_DESCRIPTION_CHARS = 500
MAX_BYLINE_CHARS = 200
MAX_DATE_CHARS = 100
MAX_HEADING_CHARS = 200
MAX_HEADINGS = 100
MAX_LINKS = 200
MAX_EXCERPT_CHARS = 450
WORDS_PER_MINUTE = 200

# Tags to discard entirely during parse time (including children and text)
PARSE_DISCARD_TAGS = frozenset({
    "script", "style", "noscript", "svg", "canvas", "video", "audio",
    "iframe", "template", "object", "embed", "applet",
})

# Structural non-content container tags
NON_CONTENT_TAGS = frozenset({
    "nav", "header", "footer", "aside", "form", "dialog", "menu",
})

# HTML void tags that do not have closing tags
VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
LEAF_BLOCK_TAGS = frozenset({"p", "pre"})
CONTAINER_BLOCK_TAGS = frozenset({"blockquote", "li", "dd", "dt"})
NON_LEAF_BLOCK_TAGS = frozenset({
    "document", "html", "body", "div", "section", "article", "main", "ul", "ol", "figure",
    "figcaption", "table", "tbody", "tr", "td", "th",
})

ALLOWED_LINK_SCHEMES = frozenset({"http", "https"})

BOILERPLATE_CLASS_OR_ID = re.compile(
    r"(?:^|[-_ ])(ad|ads|advertisement|banner|byline|cookie|consent|sidebar|"
    r"social-share|share-bar|share-buttons|disqus|comments|popup|modal|"
    r"newsletter|subscribe|widget|promo|sponsor|related-posts|breadcrumb|hatnote|infobox)(?:$|[-_ ])",
    re.IGNORECASE,
)

HIDDEN_CLASS_PATTERN = re.compile(
    r"(?:^|\s)(?:hidden|is-hidden|d-none|hide|invisible|sr-only|visually-hidden)(?:\s|$)",
    re.IGNORECASE,
)

BOILERPLATE_TEXT_PREFIXES = (
    "copyright", "all rights reserved", "bản quyền", "chia sẻ bài viết",
    "đăng ký nhận tin", "theo dõi chúng tôi", "quảng cáo", "chính sách bảo mật",
    "điều khoản sử dụng", "from wikipedia, the free encyclopedia",
)


@dataclass(frozen=True)
class ExtractedArticle:
    """Structured article representation extracted from web DOM."""
    url: str
    domain: str
    title: str
    byline: str | None
    published_date: str | None
    description: str | None
    lead_paragraph: str
    paragraphs: tuple[str, ...]
    headings: tuple[tuple[str, str], ...]
    full_text: str
    word_count: int
    reading_time_minutes: int
    links: tuple[tuple[str, str], ...]
    excerpt: str
    is_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert extracted article to a JSON-serializable dictionary."""
        return {
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "byline": self.byline,
            "published_date": self.published_date,
            "description": self.description,
            "lead_paragraph": self.lead_paragraph,
            "paragraphs": list(self.paragraphs),
            "headings": [{"level": h[0], "text": h[1]} for h in self.headings],
            "full_text": self.full_text,
            "word_count": self.word_count,
            "reading_time_minutes": self.reading_time_minutes,
            "links": [{"text": l[0], "url": l[1]} for l in self.links],
            "excerpt": self.excerpt,
            "is_truncated": self.is_truncated,
        }


class _DOMNode:
    """Lightweight in-memory DOM element tree node for text content scoring."""

    def __init__(self, tag: str, attrs: dict[str, str], parent: "_DOMNode | None" = None):
        self.tag = tag.lower()
        self.attrs = attrs
        self.children: list[_DOMNode | str] = []
        self.parent = parent

    def is_boilerplate(self) -> bool:
        if self.tag in PARSE_DISCARD_TAGS or self.tag in NON_CONTENT_TAGS:
            return True

        # Check for hidden content (WEB-READER-005)
        if "hidden" in self.attrs:
            return True
        if self.attrs.get("aria-hidden", "").strip().lower() == "true":
            return True

        style = self.attrs.get("style", "").lower()
        if style:
            if re.search(r"display\s*:\s*none", style):
                return True
            if re.search(r"visibility\s*:\s*hidden", style):
                return True
            if re.search(r"(?:^|;)\s*opacity\s*:\s*(?:0+(?:\.0+)?|\.0+)\s*(?:%|\s*!important)?\s*(?:;|$)", style):
                return True

        class_name = self.attrs.get("class", "")
        if HIDDEN_CLASS_PATTERN.search(class_name):
            return True

        role = self.attrs.get("role", "").lower()
        if role in ("navigation", "banner", "contentinfo", "complementary"):
            return True

        element_id = self.attrs.get("id", "")
        identifier = f"{class_name} {element_id}"
        return bool(BOILERPLATE_CLASS_OR_ID.search(identifier))

    def text_content(self) -> str:
        """Iterative (non-recursive) text extraction to prevent RecursionError."""
        parts: list[str] = []
        stack: list[_DOMNode | str] = list(reversed(self.children))
        while stack:
            item = stack.pop()
            if isinstance(item, str):
                parts.append(item)
            elif not item.is_boilerplate():
                stack.extend(reversed(item.children))
        return " ".join(parts)


class _DOMBuilder(HTMLParser):
    """HTML parser building a lightweight tree with depth, overflow, and node guards."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _DOMNode("document", {})
        self.current = self.root
        self.stack: list[_DOMNode] = [self.root]
        self.metadata: dict[str, str] = {}
        self.title_tag_text: list[str] = []
        self.time_tags: list[str] = []
        self._in_title = False
        self._ignore_tag: str | None = None
        self._ignore_depth = 0
        self._overflow_stack: list[str] = []
        self.overflowed = False
        self._exhausted = False
        self._node_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if self._exhausted:
            return

        tag_lower = tag.lower()

        # If inside an ignored subtree (script, style, etc.)
        if self._ignore_tag is not None:
            if tag_lower == self._ignore_tag:
                self._ignore_depth += 1
            return

        # Check if starting an ignored subtree (void tags like embed never have a subtree)
        if tag_lower in PARSE_DISCARD_TAGS:
            if tag_lower not in VOID_TAGS:
                self._ignore_tag = tag_lower
                self._ignore_depth = 1
            return

        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        # Collect meta tags
        if tag_lower == "meta":
            prop = attr_dict.get("property", "").lower() or attr_dict.get("name", "").lower()
            content = attr_dict.get("content", "").strip()
            if prop and content and prop not in self.metadata:
                self.metadata[prop] = content
            return

        # Collect time tags
        if tag_lower == "time":
            dt = attr_dict.get("datetime", "").strip()
            if dt and dt not in self.time_tags:
                self.time_tags.append(dt)

        if tag_lower == "title":
            self._in_title = True

        # Overflow tracking to prevent leaking data at DOM depth limit (WEB-READER-001/005)
        if self._overflow_stack:
            if tag_lower not in VOID_TAGS:
                if len(self._overflow_stack) >= MAX_OVERFLOW_DEPTH:
                    self.overflowed = True
                    self._exhausted = True
                    return
                self._overflow_stack.append(tag_lower)
            return

        # Resource safety bounds
        if self._node_count >= MAX_DOM_NODES or len(self.stack) >= MAX_DOM_DEPTH:
            self.overflowed = True
            if tag_lower not in VOID_TAGS:
                self._overflow_stack.append(tag_lower)
            return

        self._node_count += 1
        node = _DOMNode(tag_lower, attr_dict, parent=self.current)
        self.current.children.append(node)

        if tag_lower not in VOID_TAGS:
            self.current = node
            self.stack.append(node)

    def handle_endtag(self, tag: str):
        if self._exhausted:
            return

        tag_lower = tag.lower()

        if self._ignore_tag is not None:
            if tag_lower == self._ignore_tag:
                self._ignore_depth -= 1
                if self._ignore_depth == 0:
                    self._ignore_tag = None
            return

        if tag_lower == "title":
            self._in_title = False

        # In HTML, void tags never have valid closing tags; ignore closing void tags
        if tag_lower in VOID_TAGS:
            return

        # If currently in overflow
        if self._overflow_stack:
            # Check if tag matches an element in _overflow_stack (unwind up to it)
            if tag_lower in self._overflow_stack:
                for i in range(len(self._overflow_stack) - 1, -1, -1):
                    if self._overflow_stack[i] == tag_lower:
                        self._overflow_stack = self._overflow_stack[:i]
                        return
            # If not in _overflow_stack, check if it closes an ancestor in self.stack
            for i in range(len(self.stack) - 1, 0, -1):
                if self.stack[i].tag == tag_lower:
                    self._overflow_stack.clear()
                    self.stack = self.stack[:i]
                    self.current = self.stack[-1]
                    return
            # Tag was neither in _overflow_stack nor in self.stack (e.g. </unexpected>)
            # Malformed tag: ignore without popping valid overflow tags
            return

        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag_lower:
                self.stack = self.stack[:i]
                self.current = self.stack[-1]
                break

    def handle_data(self, data: str):
        if self._ignore_depth > 0 or not data:
            return
        if self._exhausted or self._overflow_stack:
            self.overflowed = True
            return
        if self._in_title:
            self.title_tag_text.append(data)
        if self.current is not self.root:
            self.current.children.append(data)


def _clean_text(raw: str) -> str:
    """Normalize whitespace and decode HTML entities."""
    if not raw:
        return ""
    text = html.unescape(raw)
    text = text.replace("\xa0", " ")
    return " ".join(text.split())


def _sanitize_link(href: str, base_url: str) -> str | None:
    """Sanitize and validate link against allowed schemes (WEB-READER-004)."""
    href = href.strip()
    if not href or any(ord(c) < 32 or ord(c) == 127 for c in href):
        return None
    # Reject dangerous raw scheme prefixes case-insensitively
    if re.match(r"^\s*(?:javascript|data|vbscript|file|blob)\s*:", href, re.IGNORECASE):
        return None
    if href.startswith("#"):
        return None
    try:
        resolved = urljoin(base_url, href) if base_url else href
        parsed = urlsplit(resolved)
        scheme = parsed.scheme.lower()
        if scheme:
            if scheme not in ALLOWED_LINK_SCHEMES:
                return None
            if not parsed.netloc:
                return None
        else:
            # Relative path without base_url: reject disguised schemes
            if ":" in parsed.path.split("/")[0]:
                return None
        if len(resolved) > 2048:
            return None
        return resolved
    except Exception:
        return None


def _scan_links_iterative(
    root: _DOMNode,
    base_url: str,
    seen_links: set[str],
    links: list[tuple[str, str]],
):
    """Scan node and its descendants for valid links without recursion."""
    stack: list[_DOMNode] = [root]
    while stack:
        curr = stack.pop()
        if curr.is_boilerplate():
            continue
        if curr.tag == "a":
            href = curr.attrs.get("href", "")
            atext = _clean_text(curr.text_content())
            sanitized = _sanitize_link(href, base_url)
            if sanitized and atext and len(atext) >= 3:
                if sanitized not in seen_links and len(links) < MAX_LINKS:
                    seen_links.add(sanitized)
                    links.append((atext[:200], sanitized))
        for child in reversed(curr.children):
            if isinstance(child, _DOMNode):
                stack.append(child)


def _find_candidate_containers(node: _DOMNode) -> list[_DOMNode]:
    """Iterative traversal to find candidate content containers."""
    candidates: list[_DOMNode] = []
    stack: list[_DOMNode] = [node]
    while stack:
        curr = stack.pop()
        if curr.is_boilerplate():
            continue
        tag = curr.tag
        role = curr.attrs.get("role", "").lower()
        class_id = f"{curr.attrs.get('class', '')} {curr.attrs.get('id', '')}".lower()

        if tag in ("article", "main") or role == "main":
            candidates.append(curr)
        elif tag in ("div", "section") and any(k in class_id for k in ("article", "content", "post", "story", "entry", "body")):
            candidates.append(curr)

        for child in reversed(curr.children):
            if isinstance(child, _DOMNode):
                stack.append(child)
    return candidates


def _score_container(node: _DOMNode) -> int:
    """Iterative scoring based on paragraph density and link ratio."""
    score = 0
    p_count = 0
    text_len = 0
    link_text_len = 0
    stack: list[_DOMNode | str] = [node]

    while stack:
        curr = stack.pop()
        if isinstance(curr, str):
            text_len += len(_clean_text(curr))
            continue
        if curr.is_boilerplate():
            continue

        if curr.tag == "p":
            txt = _clean_text(curr.text_content())
            if len(txt) >= 25:
                p_count += 1
                score += 25
        elif curr.tag in HEADING_TAGS:
            txt = _clean_text(curr.text_content())
            if len(txt) >= 5:
                score += 15
        elif curr.tag == "a":
            link_text_len += len(_clean_text(curr.text_content()))

        for child in reversed(curr.children):
            stack.append(child)

    score += text_len // 80
    if text_len > 0 and (link_text_len / text_len) > 0.45:
        score -= 50
    return score


def _extract_from_container(
    container: _DOMNode,
    base_url: str,
) -> tuple[list[str], list[tuple[str, str]], list[tuple[str, str]], bool]:
    """Iterative extraction of paragraphs, headings, and safe links from flow.

    Handles mixed text runs before and after block elements without losing text
    or duplicating content (WEB-READER-003).
    """
    paragraphs: list[str] = []
    headings: list[tuple[str, str]] = []
    links: list[tuple[str, str]] = []
    seen_links: set[str] = set()

    # Stack frame: [container_node, child_index, inline_text_buffer]
    stack: list[list[Any]] = [[container, 0, []]]

    while stack:
        frame = stack[-1]
        parent: _DOMNode = frame[0]
        idx: int = frame[1]
        buf: list[str] = frame[2]

        if idx >= len(parent.children):
            # End of this container: flush any remaining inline text
            if buf:
                txt = _clean_text(" ".join(buf))
                if len(txt) >= 15 and not any(txt.lower().startswith(p) for p in BOILERPLATE_TEXT_PREFIXES):
                    paragraphs.append(txt)
            stack.pop()
            continue

        child = parent.children[idx]
        frame[1] += 1  # advance child index for next iteration

        if isinstance(child, str):
            if child.strip():
                buf.append(child.strip())
            continue

        if not isinstance(child, _DOMNode) or child.is_boilerplate():
            continue

        if child.tag in HEADING_TAGS:
            if buf:
                txt = _clean_text(" ".join(buf))
                if len(txt) >= 15 and not any(txt.lower().startswith(p) for p in BOILERPLATE_TEXT_PREFIXES):
                    paragraphs.append(txt)
                frame[2] = []
            htext = _clean_text(child.text_content())
            if htext and len(htext) <= MAX_HEADING_CHARS:
                if len(headings) < MAX_HEADINGS:
                    headings.append((child.tag, htext))
            _scan_links_iterative(child, base_url, seen_links, links)

        elif child.tag in LEAF_BLOCK_TAGS:
            if buf:
                txt = _clean_text(" ".join(buf))
                if len(txt) >= 15 and not any(txt.lower().startswith(p) for p in BOILERPLATE_TEXT_PREFIXES):
                    paragraphs.append(txt)
                frame[2] = []
            ptxt = _clean_text(child.text_content())
            if len(ptxt) >= 15 and not any(ptxt.lower().startswith(p) for p in BOILERPLATE_TEXT_PREFIXES):
                paragraphs.append(ptxt)
            _scan_links_iterative(child, base_url, seen_links, links)

        elif child.tag in (CONTAINER_BLOCK_TAGS | NON_LEAF_BLOCK_TAGS):
            # Block container: flush preceding inline buffer and traverse deeper
            if buf:
                txt = _clean_text(" ".join(buf))
                if len(txt) >= 15 and not any(txt.lower().startswith(p) for p in BOILERPLATE_TEXT_PREFIXES):
                    paragraphs.append(txt)
                frame[2] = []
            stack.append([child, 0, []])

        else:
            # Inline tag (span, em, strong, a, code, etc.)
            _scan_links_iterative(child, base_url, seen_links, links)
            itxt = _clean_text(child.text_content())
            if itxt:
                buf.append(itxt)

    # Fallback if no paragraphs were collected
    if not paragraphs:
        raw_text = _clean_text(container.text_content())
        chunks = [c.strip() for c in raw_text.split("  ") if len(c.strip()) >= 20]
        paragraphs.extend(chunks)

    is_truncated = len(paragraphs) > MAX_PARAGRAPHS
    return paragraphs[:MAX_PARAGRAPHS], headings, links, is_truncated


def extract_article(
    html_content: str,
    *,
    base_url: str = "",
    max_chars: int = MAX_EXTRACTED_CHARS,
) -> ExtractedArticle:
    """Extract clean, readable article content from raw HTML string.

    Args:
        html_content: Raw HTML text of the page.
        base_url: Origin URL used to resolve relative links and extract domain.
        max_chars: Strict maximum character budget for full_text.

    Returns:
        ExtractedArticle dataclass with clean paragraphs, metadata, headings, links,
        and is_truncated status.
    """
    domain = urlsplit(base_url).hostname or "" if base_url else ""
    budget = max(0, max_chars)

    if not html_content or not isinstance(html_content, str):
        return ExtractedArticle(
            url=base_url,
            domain=domain,
            title="",
            byline=None,
            published_date=None,
            description=None,
            lead_paragraph="",
            paragraphs=(),
            headings=(),
            full_text="",
            word_count=0,
            reading_time_minutes=0,
            links=(),
            excerpt="",
            is_truncated=False,
        )

    if len(html_content) > MAX_HTML_CHARS:
        raise ValueError(f"HTML content length ({len(html_content)} chars) exceeds maximum safety limit ({MAX_HTML_CHARS})")

    builder = _DOMBuilder()
    try:
        builder.feed(html_content)
        builder.close()
    except Exception:
        pass

    meta = builder.metadata

    # 1. Title Resolution (og:title -> twitter:title -> <title> -> heading h1)
    raw_title = (
        meta.get("og:title")
        or meta.get("twitter:title")
        or _clean_text("".join(builder.title_tag_text))
    )
    title = raw_title[:MAX_TITLE_CHARS] if raw_title else ""

    # 2. Metadata: Author / Byline
    raw_byline = (
        meta.get("author")
        or meta.get("article:author")
        or meta.get("byl")
        or meta.get("twitter:creator")
    )
    byline = raw_byline[:MAX_BYLINE_CHARS] if raw_byline else None

    # 3. Metadata: Published Date (with <time> fallback)
    raw_date = (
        meta.get("article:published_time")
        or meta.get("published_time")
        or meta.get("date")
        or meta.get("pubdate")
        or (builder.time_tags[0] if builder.time_tags else None)
    )
    published_date = raw_date[:MAX_DATE_CHARS] if raw_date else None

    # 4. Description
    raw_desc = meta.get("description") or meta.get("og:description")
    description = _clean_text(raw_desc)[:MAX_DESCRIPTION_CHARS] if raw_desc else None

    # 5. Select Best Content Container
    candidates = _find_candidate_containers(builder.root)
    chosen_container = builder.root

    if candidates:
        article_candidates = [c for c in candidates if c.tag == "article"]
        main_candidates = [c for c in candidates if c.tag == "main" or c.attrs.get("role", "").lower() == "main"]

        if article_candidates:
            chosen_container = max(article_candidates, key=_score_container)
        elif main_candidates:
            chosen_container = max(main_candidates, key=_score_container)
        else:
            scored = [(c, _score_container(c)) for c in candidates]
            scored.sort(key=lambda x: x[1], reverse=True)
            if scored and scored[0][1] > 0:
                chosen_container = scored[0][0]

    # 6. Extract Raw Paragraphs and Headings
    raw_paragraphs, headings_list, links_list, raw_truncated = _extract_from_container(chosen_container, base_url)

    if not title and headings_list:
        title = headings_list[0][1][:MAX_TITLE_CHARS]

    # 7. Apply Strict Hard Budget and Retain Long Paragraph Prefix (WEB-READER-002)
    collected_paragraphs: list[str] = []
    current_chars = 0
    is_truncated = raw_truncated or builder.overflowed

    if budget == 0:
        if raw_paragraphs:
            is_truncated = True
    else:
        for p in raw_paragraphs:
            sep_len = 2 if collected_paragraphs else 0
            available = budget - current_chars - sep_len
            if available <= 0:
                is_truncated = True
                break

            if len(p) <= available:
                collected_paragraphs.append(p)
                current_chars += len(p) + sep_len
            else:
                prefix = p[:available]
                last_space = prefix.rfind(" ")
                if last_space > available // 2:
                    prefix = prefix[:last_space]
                prefix = prefix.rstrip()
                if prefix:
                    collected_paragraphs.append(prefix)
                    current_chars += len(prefix) + sep_len
                is_truncated = True
                break

    if not is_truncated and len(collected_paragraphs) < len(raw_paragraphs):
        is_truncated = True

    paragraphs = tuple(collected_paragraphs)
    full_text = "\n\n".join(paragraphs)

    assert len(full_text) <= budget

    lead_paragraph = paragraphs[0] if paragraphs else ""
    word_count = len(full_text.split())
    reading_time = max(1, (word_count + (WORDS_PER_MINUTE - 1)) // WORDS_PER_MINUTE) if word_count > 0 else 0

    # 8. Excerpt (strictly bounded by min(budget, MAX_EXCERPT_CHARS))
    excerpt_budget = min(budget, MAX_EXCERPT_CHARS)
    excerpt = ""
    source_text = lead_paragraph or description or ""
    if excerpt_budget > 0 and source_text:
        if len(source_text) <= excerpt_budget:
            excerpt = source_text
        else:
            if excerpt_budget > 3:
                cut_len = excerpt_budget - 3
                prefix = source_text[:cut_len]
                last_space = prefix.rfind(" ")
                if last_space > cut_len // 2:
                    prefix = prefix[:last_space]
                excerpt = prefix.rstrip() + "..."
            else:
                excerpt = source_text[:excerpt_budget]

    return ExtractedArticle(
        url=base_url,
        domain=domain,
        title=title,
        byline=byline,
        published_date=published_date,
        description=description,
        lead_paragraph=lead_paragraph,
        paragraphs=paragraphs,
        headings=tuple(headings_list),
        full_text=full_text,
        word_count=word_count,
        reading_time_minutes=reading_time,
        links=tuple(links_list),
        excerpt=excerpt,
        is_truncated=is_truncated,
    )


def read_page(session: BrowserSession, *, max_chars: int = MAX_EXTRACTED_CHARS) -> ExtractedArticle:
    """Read and extract clean article from the current page in an active BrowserSession.

    Args:
        session: An initialized BrowserSession.
        max_chars: Maximum characters to extract.

    Returns:
        ExtractedArticle from the loaded web page.

    Raises:
        BrowserError: If browser or page is unavailable.
    """
    if session.page is None or session.page.is_closed():
        raise BrowserError("WEB_BROWSER_CLOSED")
    try:
        url = session.page.url
        content = session.page.content()
        return extract_article(content, base_url=url, max_chars=max_chars)
    except Exception as err:
        if isinstance(err, BrowserError):
            raise
        raise BrowserError("WEB_NAVIGATION_UNCERTAIN") from err
