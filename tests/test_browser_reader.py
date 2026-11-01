"""Unit tests for clean DOM reader and article extractor."""
import unittest
from unittest.mock import Mock

from elvion.browser.reader import (
    ExtractedArticle,
    extract_article,
    read_page,
    MAX_HTML_CHARS,
)
from elvion.browser.session import BrowserError, BrowserSession


SAMPLE_VIETNAMESE_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <title>Công nghệ Local AI trên macOS - Báo Công Nghệ</title>
    <meta property="og:title" content="Khám phá Local-first AI trên MacBook Pro">
    <meta name="author" content="Lê Văn Bảo">
    <meta property="article:published_time" content="2026-11-01T08:00:00Z">
    <meta name="description" content="Đánh giá chi tiết khả năng xử lý AI cục bộ trên macOS Sonoma và kiến trúc Apple Silicon.">
</head>
<body>
    <header>
        <nav>
            <ul>
                <li><a href="/">Trang chủ</a></li>
                <li><a href="/tin-tuc">Tin tức</a></li>
            </ul>
        </nav>
    </header>

    <div class="sidebar ad-banner">
        <p>Quảng cáo giảm giá máy tính tại đây</p>
    </div>

    <main>
        <article class="post-content">
            <h1>Khám phá Local-first AI trên MacBook Pro</h1>
            <div class="byline">Tác giả: Lê Văn Bảo - 01/11/2026</div>

            <p>Trí tuệ nhân tạo cục bộ (Local-first AI) đang mở ra hướng tiếp cận mới cho các nhà phát triển phần mềm trên máy tính cá nhân.</p>

            <h2>Ưu điểm về quyền riêng tư</h2>
            <p>Khi các mô hình được thực thi trực tiếp trên Neural Engine và GPU của máy, dữ liệu người dùng không bao giờ rời khỏi thiết bị.</p>

            <h2>Hiệu năng và độ trễ</h2>
            <p>Với bộ nhớ thống nhất (Unified Memory) băng thông cao, việc nạp và suy luận các mô hình 7B hoặc 9B diễn ra với độ trễ thấp và độ tin cậy vượt trội.</p>
            <p>Để biết thêm về phương pháp đánh giá, hãy tham khảo <a href="/docs/benchmarks">tài liệu benchmark</a> chi tiết của chúng tôi.</p>
        </article>
    </main>

    <aside class="cookie-consent">
        <p>Chúng tôi sử dụng cookie để nâng cao trải nghiệm.</p>
    </aside>

    <footer>
        <p>Bản quyền 2026 thuộc về Báo Công Nghệ. Tất cả quyền được bảo lưu.</p>
    </footer>
</body>
</html>
"""


class BrowserReaderTests(unittest.TestCase):
    def test_wikipedia_source_line_is_not_the_article_excerpt(self):
        article = extract_article('''<html><body><main>
            <div>From Wikipedia, the free encyclopedia</div>
            <div class="hatnote">For another topic, see a different article.</div>
            <table class="infobox"><tr><td>Alan Mathison Turing</td></tr></table>
            <p>Alan Turing was a mathematician whose work shaped computer science.</p>
            </main></body></html>''', base_url="https://en.wikipedia.org/wiki/Alan_Turing")
        self.assertTrue(article.lead_paragraph.startswith("Alan Turing was"))
        self.assertEqual(article.excerpt, article.lead_paragraph)

    def test_basic_article_extraction(self):
        article = extract_article(SAMPLE_VIETNAMESE_HTML, base_url="https://tech.example.vn/ai/local-mac")

        self.assertIsInstance(article, ExtractedArticle)
        self.assertEqual(article.url, "https://tech.example.vn/ai/local-mac")
        self.assertEqual(article.domain, "tech.example.vn")
        self.assertEqual(article.title, "Khám phá Local-first AI trên MacBook Pro")
        self.assertEqual(article.byline, "Lê Văn Bảo")
        self.assertEqual(article.published_date, "2026-11-01T08:00:00Z")
        self.assertIn("Đánh giá chi tiết", article.description or "")

        self.assertEqual(len(article.paragraphs), 4)
        self.assertTrue(article.lead_paragraph.startswith("Trí tuệ nhân tạo cục bộ"))
        self.assertIn("Unified Memory", article.full_text)

        # Headings
        self.assertEqual(len(article.headings), 3)
        self.assertEqual(article.headings[0], ("h1", "Khám phá Local-first AI trên MacBook Pro"))
        self.assertEqual(article.headings[1], ("h2", "Ưu điểm về quyền riêng tư"))
        self.assertEqual(article.headings[2], ("h2", "Hiệu năng và độ trễ"))

        # Links
        self.assertEqual(len(article.links), 1)
        self.assertEqual(article.links[0], ("tài liệu benchmark", "https://tech.example.vn/docs/benchmarks"))

        # Metrics
        self.assertGreater(article.word_count, 50)
        self.assertEqual(article.reading_time_minutes, 1)
        self.assertTrue(article.excerpt.startswith("Trí tuệ nhân tạo cục bộ"))

    def test_boilerplate_and_noise_removal(self):
        html_with_noise = """
        <html>
        <body>
            <script>console.log("tracking");</script>
            <style>body { color: red; }</style>
            <div id="social-share" class="share-buttons">Chia sẻ Facebook Twitter</div>
            <div class="advertisement">Quảng cáo độc quyền chỉ 99k</div>
            <article>
                <h1>Nội dung chính</h1>
                <p>Đây là đoạn văn bản nội dung thực sự quan trọng của bài viết khoa học.</p>
                <p>Đoạn văn thứ hai làm rõ thêm chi tiết về phương pháp nghiên cứu.</p>
            </article>
            <div class="footer-widget">Liên kết chân trang không liên quan</div>
        </body>
        </html>
        """
        article = extract_article(html_with_noise, base_url="https://example.org/test")
        full = article.full_text

        self.assertNotIn("tracking", full)
        self.assertNotIn("color: red", full)
        self.assertNotIn("Quảng cáo độc quyền", full)
        self.assertNotIn("Chia sẻ Facebook", full)
        self.assertNotIn("Liên kết chân trang", full)

        self.assertEqual(len(article.paragraphs), 2)
        self.assertIn("nội dung thực sự quan trọng", article.paragraphs[0])
        self.assertIn("phương pháp nghiên cứu", article.paragraphs[1])

    def test_metadata_fallback_hierarchy(self):
        # Case 1: og:title takes precedence over <title>
        h1 = """<html><head><title>Title Tag</title><meta property="og:title" content="OG Title"></head><body><p>Nội dung thử nghiệm dài đủ điều kiện.</p></body></html>"""
        a1 = extract_article(h1)
        self.assertEqual(a1.title, "OG Title")

        # Case 2: twitter:title if no og:title
        h2 = """<html><head><title>Title Tag</title><meta name="twitter:title" content="Twitter Title"></head><body><p>Nội dung thử nghiệm dài đủ điều kiện.</p></body></html>"""
        a2 = extract_article(h2)
        self.assertEqual(a2.title, "Twitter Title")

        # Case 3: <title> tag if no meta title
        h3 = """<html><head><title>Native Title</title></head><body><p>Nội dung thử nghiệm dài đủ điều kiện.</p></body></html>"""
        a3 = extract_article(h3)
        self.assertEqual(a3.title, "Native Title")

        # Case 4: First heading if no title tag or meta
        h4 = """<html><body><h2>Fallback Heading Title</h2><p>Nội dung thử nghiệm dài đủ điều kiện.</p></body></html>"""
        a4 = extract_article(h4)
        self.assertEqual(a4.title, "Fallback Heading Title")

    def test_container_selection_without_article_tag(self):
        # Layout using div with content classes
        html_divs = """
        <html>
        <body>
            <div class="nav-links">
                <a href="/1">Menu 1</a> <a href="/2">Menu 2</a> <a href="/3">Menu 3</a>
            </div>
            <div class="main-entry-body">
                <h2>Tiêu đề bài viết</h2>
                <p>Đoạn mở đầu giải thích bối cảnh của vấn đề được thảo luận.</p>
                <p>Đoạn thứ hai trình bày giải pháp kỹ thuật đã được kiểm nghiệm.</p>
                <p>Đoạn kết luận tóm tắt các điểm cốt lõi cần nhớ.</p>
            </div>
            <div class="sidebar">
                <p>Danh mục phụ</p>
            </div>
        </body>
        </html>
        """
        article = extract_article(html_divs)
        self.assertEqual(len(article.paragraphs), 3)
        self.assertIn("Đoạn mở đầu", article.paragraphs[0])
        self.assertIn("Đoạn thứ hai", article.paragraphs[1])
        self.assertIn("Đoạn kết luận", article.paragraphs[2])

    def test_link_relative_resolution(self):
        html_links = """
        <html><body><article>
            <p>Tham khảo <a href="guide/start.html">hướng dẫn bắt đầu</a> và <a href="/api/v1">tài liệu API</a>.</p>
            <p>Bỏ qua link rác <a href="#top">Về đầu trang</a> và <a href="javascript:void(0)">Click</a>.</p>
        </article></body></html>
        """
        article = extract_article(html_links, base_url="https://example.com/docs/intro")
        links_dict = dict(article.links)

        self.assertEqual(links_dict.get("hướng dẫn bắt đầu"), "https://example.com/docs/guide/start.html")
        self.assertEqual(links_dict.get("tài liệu API"), "https://example.com/api/v1")
        self.assertNotIn("Về đầu trang", links_dict)
        self.assertNotIn("Click", links_dict)

    def test_malformed_html_robustness(self):
        # Broken tags, missing closing tags, unescaped characters
        broken = """
        <div>
            <h1>Tiêu đề dở dang
            <p>Đoạn văn không có thẻ đóng
            <div><span>Lồng ghép phức tạp
            <p>Nội dung vẫn được trích xuất an toàn không bị crash.
        """
        article = extract_article(broken)
        self.assertTrue(len(article.paragraphs) >= 1)
        self.assertIn("Nội dung vẫn được trích xuất", article.full_text)

    def test_empty_and_whitespace_inputs(self):
        empty_article = extract_article("")
        self.assertEqual(empty_article.full_text, "")
        self.assertEqual(empty_article.word_count, 0)
        self.assertEqual(empty_article.paragraphs, ())

        none_article = extract_article(None)  # type: ignore
        self.assertEqual(none_article.full_text, "")

        space_article = extract_article("   \n\t  ")
        self.assertEqual(space_article.full_text, "")

    def test_oversized_html_raises_value_error(self):
        oversized = "A" * (MAX_HTML_CHARS + 10)
        with self.assertRaises(ValueError):
            extract_article(oversized)

    def test_character_truncation_bound(self):
        huge_paragraph = "Đoạn văn kiểm tra giới hạn độ dài nội dung. " * 50
        html_huge = f"<html><body><article>{'<p>' + huge_paragraph + '</p>' * 30}</article></body></html>"
        article = extract_article(html_huge, max_chars=1000)

        self.assertLessEqual(len(article.full_text), 1000)
        self.assertTrue(article.is_truncated)
        self.assertGreater(len(article.paragraphs), 0)
        self.assertLessEqual(len(article.excerpt), 1000)

    def test_web_reader_001_deep_dom_recursion_guard(self):
        # 1200 nested divs does not trigger RecursionError and fails closed at MAX_DOM_DEPTH
        deep_html = (
            "<article><p>Shallow content within safe depth.</p>"
            + "<div>" * 1200
            + "<p>Synthetic content beyond safe DOM depth.</p>"
            + "</div>" * 1200
            + "</article>"
        )
        article = extract_article(deep_html)
        self.assertIn("Shallow content within safe depth.", article.full_text)
        self.assertTrue(article.is_truncated)

    def test_web_reader_001_embed_void_tag_does_not_swallow_trailing_content(self):
        # Repro 1: Bare <embed> void tag without closing tag does not swallow subsequent content
        html_bare = '<embed src="media.bin"><article><p>Visible article text after media embed.</p></article>'
        art_bare = extract_article(html_bare)
        self.assertEqual(len(art_bare.paragraphs), 1)
        self.assertEqual(art_bare.paragraphs[0], "Visible article text after media embed.")

        # Self-closing <embed/> also preserves trailing content
        html_slash = '<embed src="media.bin"/><article><p>Visible article text after media embed.</p></article>'
        art_slash = extract_article(html_slash)
        self.assertEqual(len(art_slash.paragraphs), 1)
        self.assertEqual(art_slash.paragraphs[0], "Visible article text after media embed.")

    def test_web_reader_001_005_depth_overflow_does_not_leak_hidden_content(self):
        # Repro 2: At depth limit, overflow subtree discards data and excludes hidden text fail-closed
        from elvion.browser.reader import MAX_DOM_DEPTH
        repro_html = (
            "<article>"
            + "<div>" * (MAX_DOM_DEPTH - 2)
            + "<p hidden>Hidden text at depth limit must remain excluded.</p>"
            + "</div>" * (MAX_DOM_DEPTH - 2)
            + "</article>"
        )
        art = extract_article(repro_html)
        self.assertNotIn("Hidden text", art.full_text)
        self.assertTrue(art.is_truncated)

        # Malformed closing tags in overflow subtree (</unexpected>, </br>) must not prematurely reset overflow
        prefix = "<article>" + "<div>" * (MAX_DOM_DEPTH - 2)
        suffix = "</div>" * (MAX_DOM_DEPTH - 2) + "</article>"

        art_unexpected = extract_article(
            prefix + "<section hidden></unexpected>Hidden direct text must remain excluded.</section>" + suffix
        )
        self.assertNotIn("Hidden direct text", art_unexpected.full_text)
        self.assertTrue(art_unexpected.is_truncated)

        art_void_close = extract_article(
            prefix + "<section hidden><br></br>Hidden direct text after void closing.</section>" + suffix
        )
        self.assertNotIn("Hidden direct text", art_void_close.full_text)
        self.assertTrue(art_void_close.is_truncated)

    def test_web_reader_001_depth_boundary_text_preservation_and_truncation(self):
        from elvion.browser.reader import MAX_DOM_DEPTH

        # 1. Inside depth limit (depth 255)
        html_inside = (
            "<article>"
            + "<div>" * (MAX_DOM_DEPTH - 3)
            + "<p>Text inside safe depth limit.</p>"
            + "</div>" * (MAX_DOM_DEPTH - 3)
            + "</article>"
        )
        art_inside = extract_article(html_inside)
        self.assertEqual(art_inside.full_text, "Text inside safe depth limit.")
        self.assertFalse(art_inside.is_truncated)

        # 2. At exact allowed depth limit (depth 256)
        html_exact = (
            "<article>"
            + "<div>" * (MAX_DOM_DEPTH - 2)
            + "Visible text at the exact allowed depth."
            + "</div>" * (MAX_DOM_DEPTH - 2)
            + "</article>"
        )
        art_exact = extract_article(html_exact)
        self.assertEqual(art_exact.full_text, "Visible text at the exact allowed depth.")
        self.assertFalse(art_exact.is_truncated)

        # 3. Beyond allowed depth limit (depth 257)
        html_beyond = (
            "<article>"
            + "<div>" * (MAX_DOM_DEPTH - 2)
            + "<p>Text beyond allowed depth.</p>"
            + "</div>" * (MAX_DOM_DEPTH - 2)
            + "</article>"
        )
        art_beyond = extract_article(html_beyond)
        self.assertEqual(art_beyond.full_text, "")
        self.assertTrue(art_beyond.is_truncated)

        # 4. Text at exact depth AND text beyond: boundary text kept, beyond discarded, is_truncated=True
        html_both = (
            "<article>"
            + "<div>" * (MAX_DOM_DEPTH - 2)
            + "Allowed text at boundary."
            + "<p>Dropped text beyond boundary.</p>"
            + "</div>" * (MAX_DOM_DEPTH - 2)
            + "</article>"
        )
        art_both = extract_article(html_both)
        self.assertIn("Allowed text at boundary.", art_both.full_text)
        self.assertNotIn("Dropped text beyond boundary.", art_both.full_text)
        self.assertTrue(art_both.is_truncated)

    def test_web_reader_001_overflow_stack_bounded_resource_limit(self):
        from elvion.browser.reader import MAX_DOM_DEPTH, MAX_OVERFLOW_DEPTH, _DOMBuilder

        # 10,000 opening divs must be bounded to MAX_DOM_DEPTH and MAX_OVERFLOW_DEPTH
        b = _DOMBuilder()
        b.feed("<div>" * 10000)
        self.assertLessEqual(len(b.stack), MAX_DOM_DEPTH)
        self.assertLessEqual(len(b._overflow_stack), MAX_OVERFLOW_DEPTH)
        self.assertTrue(b.overflowed)
        self.assertTrue(b._exhausted)

    def test_web_reader_003_mixed_container_preserves_loose_text_and_blocks(self):
        # Repro 3: Mixed container with loose text runs before and after child block
        html_mixed = (
            "<article><blockquote>Opening context is essential."
            "<p>Detailed explanation is here.</p>"
            "Closing context is essential.</blockquote></article>"
        )
        art = extract_article(html_mixed)
        self.assertEqual(len(art.paragraphs), 3)
        self.assertEqual(art.paragraphs[0], "Opening context is essential.")
        self.assertEqual(art.paragraphs[1], "Detailed explanation is here.")
        self.assertEqual(art.paragraphs[2], "Closing context is essential.")

    def test_web_reader_002_max_paragraphs_truncation_sets_flag(self):
        # Repro 4: 501 paragraphs truncated to 500 sets is_truncated=True even with budget remaining
        html_501 = (
            "<article>"
            + "".join(f"<p>Paragraph number {i} has substantive content.</p>" for i in range(501))
            + "</article>"
        )
        art = extract_article(html_501)
        self.assertEqual(len(art.paragraphs), 500)
        self.assertTrue(art.is_truncated)

    def test_web_reader_002_budget_preserves_prefix_and_hard_bounds(self):
        # 1200 chars in a single paragraph with budget 1000 preserves content prefix
        single_long = "B" * 1200
        html_input = f"<article><p>{single_long}</p></article>"
        art = extract_article(html_input, max_chars=1000)
        self.assertEqual(len(art.paragraphs), 1)
        self.assertEqual(len(art.full_text), 1000)
        self.assertTrue(art.full_text.startswith("BBBB"))
        self.assertTrue(art.is_truncated)

        # Budget of 10 chars strictly bounds full_text and excerpt
        art_tiny = extract_article(html_input, max_chars=10)
        self.assertLessEqual(len(art_tiny.full_text), 10)
        self.assertLessEqual(len(art_tiny.excerpt), 10)
        self.assertTrue(art_tiny.is_truncated)

        # Bounded metadata fields
        oversized_meta = """
        <html><head>
            <title>""" + ("T" * 1000) + """</title>
            <meta name="description" content='""" + ("D" * 1000) + """'>
            <meta name="author" content='""" + ("A" * 1000) + """'>
        </head><body><article><p>Valid paragraph content.</p></article></body></html>
        """
        art_meta = extract_article(oversized_meta)
        self.assertLessEqual(len(art_meta.title), 300)
        self.assertLessEqual(len(art_meta.description or ""), 500)
        self.assertLessEqual(len(art_meta.byline or ""), 200)

    def test_web_reader_003_no_duplicate_content_in_nested_blocks(self):
        # blockquote containing p does not duplicate the paragraph
        html_quote = "<article><blockquote><p>Synthetic quoted paragraph with sufficient length.</p></blockquote></article>"
        art_quote = extract_article(html_quote)
        self.assertEqual(len(art_quote.paragraphs), 1)
        self.assertEqual(art_quote.paragraphs[0], "Synthetic quoted paragraph with sufficient length.")

        # li with and without p
        html_list = "<ul><li>Simple list item with sufficient length.</li><li><p>Nested list item in p tag with sufficient length.</p></li></ul>"
        art_list = extract_article(html_list)
        self.assertEqual(len(art_list.paragraphs), 2)
        self.assertEqual(art_list.paragraphs[0], "Simple list item with sufficient length.")
        self.assertEqual(art_list.paragraphs[1], "Nested list item in p tag with sufficient length.")

    def test_web_reader_004_link_scheme_allowlist(self):
        html_links = """
        <article><p>
            An <a href="JaVaScRiPt:alert(1)">unsafe js link</a>,
            a <a href="data:text/html,bad">data link</a>,
            a <a href="file:///etc/passwd">file link</a>,
            a <a href="https://example.com/safe">safe link</a>,
            and a <a href="/docs/guide">relative link</a>.
        </p></article>
        """
        art = extract_article(html_links, base_url="https://example.com/start")
        links_dict = dict(art.links)

        self.assertNotIn("unsafe js link", links_dict)
        self.assertNotIn("data link", links_dict)
        self.assertNotIn("file link", links_dict)
        self.assertEqual(links_dict.get("safe link"), "https://example.com/safe")
        self.assertEqual(links_dict.get("relative link"), "https://example.com/docs/guide")

    def test_web_reader_005_hidden_content_exclusion(self):
        html_hidden = """
        <article>
            <p>Visible content paragraph.</p>
            <p hidden>Secret hidden content with enough length.</p>
            <p aria-hidden="true">Aria hidden content with enough length.</p>
            <p style="display:none">Inline hidden display none.</p>
            <p style="visibility: hidden">Inline visibility hidden content.</p>
            <p style="opacity: 0">Inline opacity zero content.</p>
            <p style="opacity: 0.0">Inline opacity decimal zero content.</p>
            <p style="opacity: 0.00; color: red">Inline opacity multi-decimal zero content.</p>
            <p style="opacity: 0.5">Semi-transparent visible content of sufficient length.</p>
            <p class="is-hidden">Class hidden content with enough length.</p>
        </article>
        """
        art = extract_article(html_hidden)
        self.assertEqual(len(art.paragraphs), 2)
        self.assertEqual(art.paragraphs[0], "Visible content paragraph.")
        self.assertEqual(art.paragraphs[1], "Semi-transparent visible content of sufficient length.")
        self.assertNotIn("Secret hidden", art.full_text)
        self.assertNotIn("Aria hidden", art.full_text)
        self.assertNotIn("display none", art.full_text)
        self.assertNotIn("visibility hidden", art.full_text)
        self.assertNotIn("opacity zero", art.full_text)
        self.assertNotIn("decimal zero", art.full_text)
        self.assertNotIn("Class hidden", art.full_text)

    def test_web_reader_006_anchor_in_inline_wrapper_extracted(self):
        # Anchor inside inline wrapper span or em must be extracted into article.links
        html_links = (
            "<article>"
            "<span>Visible intro <a href=\"https://example.com/docs\">useful documentation</a> ends here.</span>"
            "<p>Main paragraph sufficient length with <em>nested <a href=\"/relative/path\">inline link</a></em>.</p>"
            "</article>"
        )
        art = extract_article(html_links, base_url="https://example.com/base/")
        links_dict = dict(art.links)
        self.assertIn("useful documentation", links_dict)
        self.assertEqual(links_dict["useful documentation"], "https://example.com/docs")
        self.assertIn("inline link", links_dict)
        self.assertEqual(links_dict["inline link"], "https://example.com/relative/path")

    def test_time_tag_published_date_fallback(self):
        html_time = """
        <html><body><article>
            <h1>Title of the Article</h1>
            <time datetime="2026-11-01T10:00:00Z">01/11/2026</time>
            <p>Paragraph content of sufficient length for test.</p>
        </article></body></html>
        """
        art = extract_article(html_time)
        self.assertEqual(art.published_date, "2026-11-01T10:00:00Z")

    def test_html_entity_unescaping(self):
        html_entities = """
        <html><body><article>
            <p>&ldquo;Tr&iacute; tuệ nh&acirc;n tạo&rdquo; &amp; Machine Learning tr&ecirc;n macOS.</p>
        </article></body></html>
        """
        article = extract_article(html_entities)
        self.assertEqual(len(article.paragraphs), 1)
        self.assertEqual(article.paragraphs[0], "“Trí tuệ nhân tạo” & Machine Learning trên macOS.")

    def test_to_dict_serialization(self):
        article = extract_article(SAMPLE_VIETNAMESE_HTML, base_url="https://tech.example.vn/post")
        d = article.to_dict()

        self.assertIsInstance(d, dict)
        self.assertEqual(d["title"], "Khám phá Local-first AI trên MacBook Pro")
        self.assertEqual(d["domain"], "tech.example.vn")
        self.assertIsInstance(d["paragraphs"], list)
        self.assertIsInstance(d["headings"], list)
        self.assertIsInstance(d["links"], list)
        self.assertEqual(d["headings"][0]["level"], "h1")
        self.assertEqual(d["headings"][1]["level"], "h2")
        self.assertEqual(d["links"][0]["text"], "tài liệu benchmark")

    def test_read_page_with_active_session(self):
        session = Mock(spec=BrowserSession)
        session.page = Mock()
        session.page.is_closed.return_value = False
        session.page.url = "https://example.com/article"
        session.page.content.return_value = SAMPLE_VIETNAMESE_HTML

        article = read_page(session)
        self.assertEqual(article.url, "https://example.com/article")
        self.assertEqual(article.title, "Khám phá Local-first AI trên MacBook Pro")

    def test_read_page_with_closed_or_none_page(self):
        session_none = Mock(spec=BrowserSession)
        session_none.page = None
        with self.assertRaisesRegex(BrowserError, "^WEB_BROWSER_CLOSED$"):
            read_page(session_none)

        session_closed = Mock(spec=BrowserSession)
        session_closed.page = Mock()
        session_closed.page.is_closed.return_value = True
        with self.assertRaisesRegex(BrowserError, "^WEB_BROWSER_CLOSED$"):
            read_page(session_closed)

    def test_session_read_article_delegates(self):
        session = BrowserSession()
        session.page = Mock()
        session.page.is_closed.return_value = False
        session.page.url = "https://example.com/test"
        session.page.content.return_value = "<html><head><title>Test Title</title></head><body><article><p>Nội dung kiểm tra gọi qua session.</p></article></body></html>"

        article = session.read_article()
        self.assertEqual(article.title, "Test Title")
        self.assertIn("Nội dung kiểm tra gọi qua session", article.full_text)

    def test_read_page_handles_unexpected_exception(self):
        session = Mock(spec=BrowserSession)
        session.page = Mock()
        session.page.is_closed.return_value = False
        session.page.content.side_effect = RuntimeError("Driver failure")

        with self.assertRaisesRegex(BrowserError, "^WEB_NAVIGATION_UNCERTAIN$"):
            read_page(session)


if __name__ == "__main__":
    unittest.main()
