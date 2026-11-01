"""Comprehensive test suite for Apple Music subsystem (AM-01 to AM-29).

Hermetic, deterministic verification of app lifecycle, permissions, search,
selection, playback control, independent verification, and data boundaries.
"""
from datetime import datetime, timezone
import time
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from elvion.adapters.apple_music import (
    AppleMusicAdapter, AppleMusicBackend, FakeAppleMusicBackend,
    MusicBackendError, NativeAppleMusicBackend, create_music_adapters,
)
from elvion.adapters.registry import AdapterRegistry
from elvion.core.contracts import (
    ActionIntent, ActionStatus, AuthorizationToken, ConfirmationRequest,
    ConfirmationResponse, ContractError, ErrorCode, Method,
    ObservationRequest, ObservationStatus, TaskRequest, TaskStatus, utc_now,
)
from elvion.core.music import (
    MUSIC_APP_ID, MUSIC_APP_OPEN, MUSIC_CAPABILITIES, MUSIC_CURRENT_TRACK,
    MUSIC_PAUSE, MUSIC_PLAY, MUSIC_READ_STATE, MUSIC_RESUME, MUSIC_SEARCH,
    MUSIC_TARGET, MusicOrchestrator, MusicPlayerState, MusicTrack,
)
from elvion.planning.music import MusicSelectionState, is_music_command, plan_music
from elvion.planning.rules import UnsupportedCommand
from elvion.policy.music import MusicPolicy
from elvion.policy.rules import PermissionDenied
from elvion.storage.traces import TraceStore
from elvion.verification.music import verify_music_action

ALL_MUSIC_GRANTS = frozenset(MUSIC_CAPABILITIES)

TRACK_1 = MusicTrack(
    persistent_id="1111222233334444",
    name="Tình Yêu Của Tôi Không Thay Đổi",
    artist="CHANG CUT",
    album="Single",
    duration=201.5,
)
TRACK_2 = MusicTrack(
    persistent_id="5555666677778888",
    name="Giá Như (feat. Dangrangto)",
    artist="COOLKID",
    album="Single",
    duration=220.0,
)
TRACK_HELLO_ADELE = MusicTrack(
    persistent_id="AAAAAAAAAAAAAAAA",
    name="Hello",
    artist="Adele",
    album="25",
    duration=295.0,
)
TRACK_HELLO_LIONEL = MusicTrack(
    persistent_id="BBBBBBBBBBBBBBBB",
    name="Hello",
    artist="Lionel Richie",
    album="Can't Slow Down",
    duration=250.0,
)
TRACK_HOTEL_STUDIO = MusicTrack(
    persistent_id="CCCCCCCCCCCCCCCC",
    name="Hotel California",
    artist="Eagles",
    album="Hotel California",
    duration=391.0,
)
TRACK_HOTEL_LIVE = MusicTrack(
    persistent_id="DDDDDDDDDDDDDDDD",
    name="Hotel California (Live)",
    artist="Eagles",
    album="Hell Freezes Over",
    duration=432.0,
)
TRACK_HOTEL_REMASTER = MusicTrack(
    persistent_id="EEEEEEEEEEEEEEEE",
    name="Hotel California (2013 Remaster)",
    artist="Eagles",
    album="Hotel California (40th Anniversary)",
    duration=391.0,
)
TRACK_SPECIAL_CHARS = MusicTrack(
    persistent_id="FFFFFFFFFFFFFFFF",
    name="Don't Stop Believin' \"Rock & Roll\"",
    artist="Journey & Friends",
    album="Greatest Hits",
    duration=251.0,
)

STANDARD_LIBRARY = [
    TRACK_1,
    TRACK_2,
    TRACK_HELLO_ADELE,
    TRACK_HELLO_LIONEL,
    TRACK_HOTEL_STUDIO,
    TRACK_HOTEL_LIVE,
    TRACK_HOTEL_REMASTER,
    TRACK_SPECIAL_CHARS,
]


def make_token(intent: ActionIntent) -> AuthorizationToken:
    from datetime import timedelta
    return AuthorizationToken(
        task_id=intent.task_id,
        step_id=intent.step_id,
        action_digest=intent.digest(),
        expires_at=utc_now() + timedelta(minutes=5),
    )


class AppleMusicTests(unittest.TestCase):

    # =========================================================================
    # Group A: App và quyền hệ thống (AM-01 to AM-06)
    # =========================================================================

    def test_am_01_app_not_running_launches_and_verifies_running(self):
        """AM-01: Music chưa chạy → mở app và xác nhận app đang chạy."""
        backend = FakeAppleMusicBackend(running=False)
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance="Mở Apple Music")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.SUCCEEDED)
        self.assertTrue(backend.running)
        self.assertTrue(len(backend.pids) > 0)

    def test_am_02_app_already_running_reuses_app(self):
        """AM-02: Music đã chạy → dùng lại app."""
        backend = FakeAppleMusicBackend(running=True, pids=[9999])
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance="Mở Apple Music")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.SUCCEEDED)
        self.assertEqual(backend.pids, [9999])

    def test_am_03_permission_denied_handled_gracefully(self):
        """AM-03: Automation/Accessibility bị từ chối (-1743 / PERMISSION_DENIED)."""
        backend = FakeAppleMusicBackend(simulate_permission_denied=True)
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance="Mở Apple Music")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.FAILED)
        self.assertEqual(record.error_code, ErrorCode.PERMISSION_DENIED)

    def test_am_04_helper_or_system_api_unavailable(self):
        """AM-04: Helper hoặc API hệ thống không khả dụng (UNSUPPORTED)."""
        backend = FakeAppleMusicBackend(simulate_unsupported=True)
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance="Mở Apple Music")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.FAILED)
        self.assertEqual(record.error_code, ErrorCode.UNSUPPORTED)

    def test_am_05_app_quits_mid_operation(self):
        """AM-05: Ứng dụng đóng giữa thao tác."""
        backend = FakeAppleMusicBackend(running=True, simulate_app_quit=True, tracks=STANDARD_LIBRARY)
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance="Tìm bài Tình Yêu")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.FAILED)
        self.assertEqual(record.error_code, ErrorCode.TARGET_NOT_FOUND)

    def test_am_06_missing_grant_or_user_cancelled_no_dispatch(self):
        """AM-06: Thiếu grant hoặc người dùng hủy → không dispatch."""
        backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
        orchestrator = MusicOrchestrator(backend=backend, require_confirmation=True)

        # 1. Missing grant -> Fails at policy, no execute
        req = TaskRequest(utterance="Tạm dừng nhạc")
        record = orchestrator.run(req, grants=frozenset({MUSIC_APP_OPEN}))  # Missing MUSIC_PAUSE
        self.assertEqual(record.status, TaskStatus.FAILED)

        # 2. User rejects confirmation -> Fails, no dispatch
        intent = plan_music(req)
        policy = MusicPolicy(require_confirmation=True)
        conf_req = policy.request_confirmation(intent, ALL_MUSIC_GRANTS)
        user_rejection = ConfirmationResponse(
            confirmation_id=conf_req.confirmation_id,
            action_digest=conf_req.action_digest,
            approved=False,
        )
        from elvion.policy.confirmation import ConfirmationRejected
        with self.assertRaises(ConfirmationRejected):
            policy.authorize(intent, ALL_MUSIC_GRANTS, response=user_rejection)

    # =========================================================================
    # Group B: Tìm và chọn bài (AM-07 to AM-16)
    # =========================================================================

    def test_am_07_unique_track_and_artist_match(self):
        """AM-07: Tên bài và nghệ sĩ khớp duy nhất."""
        backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
        tracks = backend.search_library("Giá Như COOLKID")
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].persistent_id, TRACK_2.persistent_id)

    def test_am_08_same_title_different_artist_disambiguation(self):
        """AM-08: Hai bài cùng tên, khác nghệ sĩ → phân biệt rõ, không đoán mò."""
        backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
        tracks = backend.search_library("Hello")
        self.assertEqual(len(tracks), 2)
        artists = {t.artist for t in tracks}
        self.assertEqual(artists, {"Adele", "Lionel Richie"})

        # Multi-candidate selection state requires explicit user choice
        state = MusicSelectionState(candidates=[t.to_dict() for t in tracks])
        self.assertEqual(len(state.candidates), 2)

        # User chooses #2 -> Lionel Richie
        intent = plan_music(TaskRequest(utterance="Phát kết quả số 2"), selection_state=state)
        self.assertEqual(intent.arguments["persistent_id"], TRACK_HELLO_LIONEL.persistent_id)

    def test_am_09_distinguishes_live_remaster_and_cover(self):
        """AM-09: Cùng bài có bản live/remaster/cover."""
        backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
        tracks = backend.search_library("Hotel California")
        self.assertEqual(len(tracks), 3)

        # Ensure all 3 persistent IDs are distinct
        pids = {t.persistent_id for t in tracks}
        self.assertEqual(len(pids), 3)
        self.assertIn(TRACK_HOTEL_STUDIO.persistent_id, pids)
        self.assertIn(TRACK_HOTEL_LIVE.persistent_id, pids)
        self.assertIn(TRACK_HOTEL_REMASTER.persistent_id, pids)

    def test_am_10_vietnamese_diacritics_preserved(self):
        """AM-10: Tên tiếng Việt có dấu được xử lý chính xác không hỏng chuỗi."""
        backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
        req = TaskRequest(utterance="Tìm bài Tình Yêu Của Tôi Không Thay Đổi")
        intent = plan_music(req)
        self.assertEqual(intent.arguments["query"], "Tình Yêu Của Tôi Không Thay Đổi")

        results = backend.search_library(intent.arguments["query"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Tình Yêu Của Tôi Không Thay Đổi")

    def test_am_11_quotes_apostrophe_and_special_characters(self):
        """AM-11: Tên có dấu ngoặc kép, apostrophe hoặc ký tự đặc biệt."""
        backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
        req = TaskRequest(utterance='Tìm bài Don\'t Stop Believin\' "Rock & Roll"')
        intent = plan_music(req)
        self.assertEqual(intent.arguments["query"], 'Don\'t Stop Believin\' "Rock & Roll"')

        results = backend.search_library("Don't Stop Believin'")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].persistent_id, TRACK_SPECIAL_CHARS.persistent_id)

    def test_am_12_no_results_handled_safely(self):
        """AM-12: Không có kết quả → trả về rỗng không văng lỗi."""
        backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance="Tìm bài Bài Hát Chưa Từng Có 123456789")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.SUCCEEDED)
        # Search is read-only; observation succeeded with 0 candidates
        results = backend.search_library("Bài Hát Chưa Từng Có 123456789")
        self.assertEqual(len(results), 0)

    def test_am_13_multiple_results_prompts_selection(self):
        """AM-13: Nhiều kết quả → tạo selection state để người dùng chọn."""
        backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
        tracks = backend.search_library("Hotel California")
        state = MusicSelectionState(candidates=[t.to_dict() for t in tracks])
        self.assertTrue(state.is_valid())
        self.assertEqual(len(state.candidates), 3)

    def test_am_14_invalid_or_expired_choice_rejected(self):
        """AM-14: Lựa chọn không hợp lệ hoặc đã hết hiệu lực."""
        state = MusicSelectionState(
            candidates=[TRACK_1.to_dict(), TRACK_2.to_dict()],
            created_at=time.monotonic() - 400.0,  # Expired (> 300s)
        )
        # Expired selection state
        with self.assertRaises(UnsupportedCommand):
            plan_music(TaskRequest(utterance="Phát kết quả số 1"), selection_state=state)

        # Valid time, but index out of bounds
        fresh_state = MusicSelectionState(candidates=[TRACK_1.to_dict()])
        with self.assertRaises(UnsupportedCommand):
            plan_music(TaskRequest(utterance="Phát kết quả số 5"), selection_state=fresh_state)

    def test_am_15_results_change_after_browsing(self):
        """AM-15: Kết quả thay đổi sau khi duyệt (track bị xóa khỏi library)."""
        backend = FakeAppleMusicBackend(running=True, tracks=[TRACK_1])
        adapter = AppleMusicAdapter(MUSIC_PLAY, backend=backend)

        # Track 2 is NOT in the library
        intent = ActionIntent(
            task_id=uuid4(),
            capability=MUSIC_PLAY,
            target=MUSIC_TARGET,
            arguments={"persistent_id": TRACK_2.persistent_id},
            postcondition={"kind": "track_playing", "persistent_id": TRACK_2.persistent_id},
        )
        token = make_token(intent)
        result = adapter.execute(intent, token)
        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertEqual(result.error_code, ErrorCode.TARGET_NOT_FOUND)

    def test_am_16_catalog_blocker_documented_not_faked(self):
        """AM-16: Catalog search không có scripting API → báo blocker, không giả lập."""
        # Non-library track search returns 0 candidates from library
        backend = FakeAppleMusicBackend(running=True, tracks=[TRACK_1])
        results = backend.search_library("Streaming Exclusive Non Library Song")
        self.assertEqual(len(results), 0)

    # =========================================================================
    # Group C: Player và verifier (AM-17 to AM-25)
    # =========================================================================

    def test_am_17_plays_correct_track_and_verifies(self):
        """AM-17: Phát đúng track đã chọn."""
        backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance=f"Phát {TRACK_1.persistent_id}")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.SUCCEEDED)
        self.assertEqual(backend.state_val, "playing")
        self.assertEqual(backend.cur_track.persistent_id, TRACK_1.persistent_id)

    def test_am_18_playing_different_track_fails_verification(self):
        """AM-18: Player đang phát track khác → không báo đúng bài."""
        backend = FakeAppleMusicBackend(
            running=True,
            player_state_val="playing",
            current_track=TRACK_2,  # Playing Track 2 instead of Track 1
            tracks=STANDARD_LIBRARY,
        )
        adapter = AppleMusicAdapter(MUSIC_PLAY, backend=backend)
        intent = ActionIntent(
            task_id=uuid4(),
            capability=MUSIC_PLAY,
            target=MUSIC_TARGET,
            arguments={"persistent_id": TRACK_1.persistent_id},
            postcondition={"kind": "track_playing", "persistent_id": TRACK_1.persistent_id},
        )
        fake_result = Mock(status=ActionStatus.SUCCESS, evidence={"persistent_id": TRACK_1.persistent_id})
        verified = verify_music_action(intent, fake_result, adapter, timeout_seconds=0.1)
        self.assertFalse(verified)

    def test_am_19_app_open_but_player_not_playing_fails_play_verification(self):
        """AM-19: App mở nhưng player chưa phát → không báo đang phát."""
        backend = FakeAppleMusicBackend(
            running=True,
            player_state_val="paused",  # Still paused
            current_track=TRACK_1,
            tracks=STANDARD_LIBRARY,
        )
        adapter = AppleMusicAdapter(MUSIC_PLAY, backend=backend)
        intent = ActionIntent(
            task_id=uuid4(),
            capability=MUSIC_PLAY,
            target=MUSIC_TARGET,
            arguments={"persistent_id": TRACK_1.persistent_id},
            postcondition={"kind": "track_playing", "persistent_id": TRACK_1.persistent_id},
        )
        fake_result = Mock(status=ActionStatus.SUCCESS, evidence={"persistent_id": TRACK_1.persistent_id})
        verified = verify_music_action(intent, fake_result, adapter, timeout_seconds=0.1)
        self.assertFalse(verified)

    def test_am_20_pause_and_verify_paused(self):
        """AM-20: Pause và kiểm chứng paused."""
        backend = FakeAppleMusicBackend(
            running=True,
            player_state_val="playing",
            current_track=TRACK_1,
            tracks=STANDARD_LIBRARY,
        )
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance="Tạm dừng nhạc")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.SUCCEEDED)
        self.assertEqual(backend.state_val, "paused")

    def test_am_21_resume_and_verify_playing(self):
        """AM-21: Resume và kiểm chứng playing."""
        backend = FakeAppleMusicBackend(
            running=True,
            player_state_val="paused",
            current_track=TRACK_1,
            tracks=STANDARD_LIBRARY,
        )
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance="Tiếp tục phát")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.SUCCEEDED)
        self.assertEqual(backend.state_val, "playing")

    def test_am_22_no_current_track_returns_safely(self):
        """AM-22: Không có current track."""
        backend = FakeAppleMusicBackend(running=True, player_state_val="stopped", current_track=None)
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance="Đang phát bài gì?")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.SUCCEEDED)

    def test_am_23_query_current_track_while_paused(self):
        """AM-23: Đọc 'đang phát gì' khi đang paused."""
        backend = FakeAppleMusicBackend(
            running=True,
            player_state_val="paused",
            current_track=TRACK_1,
            tracks=STANDARD_LIBRARY,
        )
        orchestrator = MusicOrchestrator(backend=backend)
        req = TaskRequest(utterance="Đang phát bài gì?")
        record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)

        self.assertEqual(record.status, TaskStatus.SUCCEEDED)
        # Direct check on adapter observe
        adapter = AppleMusicAdapter(MUSIC_CURRENT_TRACK, backend=backend)
        obs = adapter.observe(ObservationRequest(app=MUSIC_APP_ID, kind="current_track", subject_id=MUSIC_APP_ID))
        self.assertEqual(obs.status, ObservationStatus.OBSERVED)
        self.assertEqual(obs.data["player_state"], "paused")
        self.assertTrue(obs.data["has_track"])

    def test_am_24_timeout_after_dispatch_uncertain_no_automatic_retry(self):
        """AM-24: Timeout sau dispatch → uncertain, không phát lại tự động."""
        backend = FakeAppleMusicBackend(running=True, simulate_timeout=True, tracks=STANDARD_LIBRARY)
        adapter = AppleMusicAdapter(MUSIC_PLAY, backend=backend)
        intent = ActionIntent(
            task_id=uuid4(),
            capability=MUSIC_PLAY,
            target=MUSIC_TARGET,
            arguments={"persistent_id": TRACK_1.persistent_id},
            postcondition={"kind": "track_playing", "persistent_id": TRACK_1.persistent_id},
        )
        token = make_token(intent)
        result = adapter.execute(intent, token)

        self.assertEqual(result.status, ActionStatus.UNCERTAIN)
        self.assertTrue(result.external_effect_possible)
        self.assertFalse(result.retryable)

    def test_am_25_backend_bad_schema_detected(self):
        """AM-25: Câu trả lời của backend sai schema hoặc thiếu track identity."""
        backend = FakeAppleMusicBackend(running=True, simulate_bad_schema=True)
        adapter = AppleMusicAdapter(MUSIC_READ_STATE, backend=backend)
        intent = ActionIntent(
            task_id=uuid4(),
            capability=MUSIC_READ_STATE,
            target=MUSIC_TARGET,
            arguments={},
            postcondition={"kind": "player_state_read"},
        )
        token = make_token(intent)
        result = adapter.execute(intent, token)
        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertEqual(result.error_code, ErrorCode.VERIFICATION_FAILED)

    # =========================================================================
    # Group D: Ranh giới dữ liệu và injection (AM-26 to AM-29)
    # =========================================================================

    def test_am_26_command_like_title_treated_as_pure_data(self):
        """AM-26: Tên bài chứa nội dung giống câu lệnh không thực thi shell/code."""
        evil_title = 'rm -rf /; tell application "Music" to quit'
        evil_track = MusicTrack(
            persistent_id="1234567890ABCDEF",
            name=evil_title,
            artist="Hacker",
            album="Payload",
            duration=120.0,
        )
        backend = FakeAppleMusicBackend(running=True, tracks=[evil_track])
        req = TaskRequest(utterance=f"Tìm bài {evil_title}")
        intent = plan_music(req)

        self.assertEqual(intent.arguments["query"], evil_title)
        results = backend.search_library(intent.arguments["query"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].persistent_id, "1234567890ABCDEF")

    def test_am_27_escape_characters_handled_safely(self):
        """AM-27: Tên bài có ký tự escape AppleScript/shell."""
        weird_title = 'Song with \\ and " and \' and $HOME and `date`'
        weird_track = MusicTrack(
            persistent_id="FEDCBA0987654321",
            name=weird_title,
            artist="Artist",
            album="Album",
            duration=180.0,
        )
        backend = FakeAppleMusicBackend(running=True, tracks=[weird_track])
        results = backend.search_library('Song with \\ and " and \'')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].persistent_id, "FEDCBA0987654321")

    def test_am_28_traces_never_leak_private_tracks_or_history(self):
        """AM-28: Log/trace không chứa thông tin thư viện hoặc track riêng tư."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp_dir:
            trace_store = TraceStore(data_dir=Path(tmp_dir))
            backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
            orchestrator = MusicOrchestrator(backend=backend, trace_store=trace_store)

            req = TaskRequest(utterance=f"Phát {TRACK_1.persistent_id}")
            record = orchestrator.run(req, grants=ALL_MUSIC_GRANTS)
            self.assertEqual(record.status, TaskStatus.SUCCEEDED)

            # Inspect trace files on disk
            trace_files = list(trace_store.directory.glob("*.jsonl"))
            self.assertTrue(len(trace_files) > 0)
            for tf in trace_files:
                content = tf.read_text(encoding="utf-8")
                # Private song title and artist must NEVER appear in persistent traces
                self.assertNotIn("Tình Yêu Của Tôi Không Thay Đổi", content)
                self.assertNotIn("CHANG CUT", content)

    def test_am_29_model_or_planner_does_not_hallucinate_substitution(self):
        """AM-29: Không tự thay nghệ sĩ hoặc chọn bản khác khi tên gần giống."""
        backend = FakeAppleMusicBackend(running=True, tracks=STANDARD_LIBRARY)
        # Search specifically for Adele's Hello
        req = TaskRequest(utterance="Tìm bài Hello Adele")
        intent = plan_music(req)
        results = backend.search_library(intent.arguments["query"])

        self.assertEqual(len(results), 1)
        # Must not substitute with Lionel Richie
        self.assertEqual(results[0].artist, "Adele")
        self.assertNotEqual(results[0].artist, "Lionel Richie")


if __name__ == "__main__":
    unittest.main()
