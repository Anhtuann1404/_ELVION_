import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from elvion.browser.youtube import YouTubeError, YouTubeWorkflow, video_id
from elvion.core.contracts import TaskStatus


class Row:
    def __init__(self, title, channel, href, *, visible=True):
        self.title, self.channel, self.href, self.visible = title, channel, href, visible

    def is_visible(self):
        return self.visible

    def locator(self, selector):
        if selector == "a#video-title":
            return SimpleNamespace(first=SimpleNamespace(
                get_attribute=lambda name: self.title if name == "title" else self.href,
                inner_text=lambda: self.title))
        return SimpleNamespace(first=SimpleNamespace(inner_text=lambda: self.channel))


class Page:
    def __init__(self, rows):
        self.url = "https://www.youtube.com/results?search_query=python"
        self.rows = rows
        self.closed = False

    def is_closed(self):
        return self.closed

    def locator(self, selector):
        return SimpleNamespace(first=SimpleNamespace(wait_for=lambda **kw: None),
                               all=lambda: self.rows)


class YouTubeWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.page = Page([Row("Same", "Channel A", "/watch?v=abcdefghijk"),
                          Row("Same", "Channel B", "/watch?v=12345678901")])
        self.session = SimpleNamespace(page=self.page, revision=1)
        self.workflow = YouTubeWorkflow(self.session)
        self.report = SimpleNamespace(status=TaskStatus.SUCCEEDED)
        self.runtime = patch("elvion.browser.youtube.web_runtime")
        self.agent = self.runtime.start().return_value
        self.agent.run.return_value = self.report
        self.addCleanup(self.runtime.stop)

    def search(self, query="python"):
        return self.workflow.search(query, grants={"web.open"}, confirm=Mock())

    def test_video_id_accepts_only_single_canonical_watch_id(self):
        self.assertEqual(video_id("https://www.youtube.com/watch?v=abcdefghijk"), "abcdefghijk")
        for url in ("https://youtube.com/watch?v=abcdefghijk",
                    "https://www.youtube.com/shorts/abcdefghijk",
                    "https://www.youtube.com/playlist?list=abcdefghijk",
                    "https://www.youtube.com/watch?v=bad",
                    "https://www.youtube.com/watch?v=abcdefghijk&v=12345678901"):
            self.assertIsNone(video_id(url))

    def test_search_encodes_query_and_keeps_duplicate_titles_distinct(self):
        _, videos = self.search('tiếng Việt "A & B"')
        self.assertEqual([v.channel for v in videos], ["Channel A", "Channel B"])
        self.assertNotEqual(videos[0].video_id, videos[1].video_id)
        utterance = self.agent.run.call_args.args[0].utterance
        self.assertIn("search_query=", utterance)
        self.assertIn("%26", utterance)
        self.assertIn("%22", utterance)

    def test_excludes_ads_shorts_playlists_and_hidden_results(self):
        self.page.rows = [Row("Ad", "Promoter", "/ad?x=1"),
                          Row("Short", "C", "/shorts/abcdefghijk"),
                          Row("Playlist", "C", "/playlist?list=PL123"),
                          Row("Hidden", "C", "/watch?v=abcdefghijk", visible=False),
                          Row("Video", "C", "/watch?v=12345678901")]
        _, videos = self.search()
        self.assertEqual([v.title for v in videos], ["Video"])

    def test_empty_or_unclear_results_stop_without_selection(self):
        self.page.rows = []
        with self.assertRaisesRegex(YouTubeError, "YT_NO_CLEAR_RESULTS"):
            self.search()
        self.assertEqual(self.workflow.results, {})

    def test_result_list_change_during_read_is_rejected(self):
        original = self.page.locator
        calls = 0
        def changing(selector):
            nonlocal calls
            calls += 1
            value = original(selector)
            if calls == 3:
                return SimpleNamespace(first=value.first, all=lambda: [Row("Other", "C", "/watch?v=zzzzzzzzzzz")])
            return value
        self.page.locator = changing
        with self.assertRaisesRegex(YouTubeError, "YT_RESULTS_CHANGED"):
            self.search()

    def test_failed_or_declined_web_open_does_not_read_dom(self):
        self.agent.run.return_value = SimpleNamespace(status=TaskStatus.CANCELLED)
        report, videos = self.search()
        self.assertEqual(report.status, TaskStatus.CANCELLED)
        self.assertEqual(videos, ())
        self.assertEqual(self.workflow.results, {})

    def test_open_requires_current_search_and_verifies_video_id(self):
        _, videos = self.search()
        def opened(*args, **kwargs):
            self.page.url = videos[0].url
            return self.report
        self.agent.run.side_effect = opened
        report, verified = self.workflow.open_video(videos[0].handle, grants={"web.open"}, confirm=Mock())
        self.assertIs(report, self.report)
        self.assertTrue(verified)
        self.assertEqual(self.workflow.results, {})

    def test_wrong_video_id_never_counts_as_opened(self):
        _, videos = self.search()
        def wrong_redirect(*args, **kwargs):
            self.page.url = "https://www.youtube.com/watch?v=12345678901"
            return self.report
        self.agent.run.side_effect = wrong_redirect
        _, verified = self.workflow.open_video(videos[0].handle, grants={"web.open"}, confirm=Mock())
        self.assertFalse(verified)

    def test_stale_or_closed_page_blocks_action_before_dispatch(self):
        _, videos = self.search()
        self.agent.run.reset_mock()
        self.session.revision += 1
        with self.assertRaisesRegex(YouTubeError, "YT_RESULT_EXPIRED"):
            self.workflow.open_video(videos[0].handle, grants={"web.open"}, confirm=Mock())
        self.agent.run.assert_not_called()
        self.session.revision -= 1
        self.page.closed = True
        with self.assertRaisesRegex(YouTubeError, "YT_RESULT_EXPIRED"):
            self.workflow.open_video(videos[0].handle, grants={"web.open"}, confirm=Mock())
        self.agent.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
