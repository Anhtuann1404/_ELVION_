# Graph Report - ELVION  (2026-11-01)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 3336 nodes · 10542 edges · 165 communities (107 shown, 58 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 1452 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `defd32d9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 131
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 164

## God Nodes (most connected - your core abstractions)
1. `TaskRequest` - 160 edges
2. `ActionIntent` - 91 edges
3. `ContractError` - 62 edges
4. `GroundingResult` - 54 edges
5. `ReminderStore` - 54 edges
6. `ModelPlanner` - 52 edges
7. `ErrorCode` - 50 edges
8. `InteractiveSession` - 50 edges
9. `main()` - 48 edges
10. `DemoOrchestrator` - 46 edges

## Surprising Connections (you probably didn't know these)
- `listen_once()` --calls--> `Transcription`  [INFERRED]
  tests/test_gui_bridge.py → src/elvion/voice/input/types.py
- `listen()` --calls--> `Transcription`  [INFERRED]
  tests/test_spoken_review.py → src/elvion/voice/input/types.py
- `recognize()` --calls--> `OCRError`  [INFERRED]
  tests/test_web_observation.py → src/elvion/vision/ocr.py
- `approve_handler()` --calls--> `ConfirmationResponse`  [INFERRED]
  tests/test_reminders_product.py → src/elvion/core/contracts.py
- `poll()` --calls--> `ReminderStore`  [INFERRED]
  tests/test_reminders.py → src/elvion/reminders/store.py

## Import Cycles
- None detected.

## Communities (165 total, 58 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (6): present_confirmation(), present_report(), print_json(), vietnam_time(), configure_voice(), resolve_voice_options()

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (30): main(), main(), main(), _write(), generate(), main(), transcribe(), main() (+22 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (29): Case, check_cases(), e(), Element, manifest_sha256(), render(), RecordingGrounder, load_inputs() (+21 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (40): build_subjects(), role_system(), run(), save(), manifest_sha256(), compare(), recorded(), save() (+32 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (19): Case, score(), ScriptedProvider, main(), ConversationMemory, CapabilityContext, ConversationResult, Persona (+11 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (4): main(), private_directory(), NativePresentationTests, ReferenceBeamValidationTests

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (17): Carbon, AppDelegate, CapsuleView, .body, .confirmation, CoreModel, .compact, .detail (+9 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (23): analyze(), geometry(), main(), render_html(), render_markdown(), collect(), main(), save() (+15 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (10): main(), VisionFrame, VisionGrounder, compile_proposal(), compile_proposal_v2(), compile_proposal_v3(), valid_png(), FakeProvider (+2 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (8): TextObservation, OCRPunctuationGrounder, LabelCandidatesTests, read(), PunctuationTests, full(), local(), SemanticVisionTests

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (19): subjects(), GroundingResult, context_rectangle(), crop_context(), embedded_label(), hypothesis(), skeleton(), needs_label_marker() (+11 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (16): AppleNotesAdapter, Adapter, ActionResult, ActionStatus, CapabilityDescriptor, Contract, Observation, ObservationRequest (+8 more)

### Community 12 - "Community 12"
Cohesion: 0.12
Nodes (9): TaskRequest, ModelPlanner, PlannerTests, ModelPlannerTests, provider_for(), NoteReferenceTests, provider(), AppReferenceTests (+1 more)

### Community 13 - "Community 13"
Cohesion: 0.11
Nodes (9): RemindersAdapter, ActionIntent, AuthorizationToken, valid_reminder_content(), valid_reminder_id(), RemindersPolicy, CapabilityPolicy, RemindersAdapterAndVerifierTests (+1 more)

### Community 14 - "Community 14"
Cohesion: 0.11
Nodes (21): DatasetError, evaluate(), _expected_intent(), _fail(), _group(), load_dataset(), make_report(), markdown() (+13 more)

### Community 15 - "Community 15"
Cohesion: 0.07
Nodes (10): main(), VoicePreferences, VoicePreferencesStore, NotesCLITests, NativeCLITests, ModelCLITests, SessionCLITests, QwenVoiceCLITests (+2 more)

### Community 16 - "Community 16"
Cohesion: 0.08
Nodes (7): DemoOrchestrator, PipelineTests, PresentationTests, TraceTests, decline(), factory(), demo_factory()

### Community 17 - "Community 17"
Cohesion: 0.08
Nodes (8): AttemptJournal, Backend, CalculatorActionTests, observed(), expired(), mutate(), decline(), Pipe

### Community 18 - "Community 18"
Cohesion: 0.08
Nodes (12): listen(), VoiceInput, Transcription, VoiceInputError, VoicePurposeTests, listen(), transcribe(), transcribe() (+4 more)

### Community 19 - "Community 19"
Cohesion: 0.09
Nodes (13): CalculatorAXAdapter, authorized(), final_authorized(), outcome(), CalculatorPressBackend, box(), make_intent(), PressOutcome (+5 more)

### Community 21 - "Community 21"
Cohesion: 0.09
Nodes (12): record_model(), main(), backend(), wrapped(), CachedOCR, backend(), backend(), observed_ocr() (+4 more)

### Community 22 - "Community 22"
Cohesion: 0.10
Nodes (14): wrapped(), is_reminder_command(), _parse_datetime(), _parse_time_spec(), plan(), UnsupportedCommand, apply_control(), _clean() (+6 more)

### Community 23 - "Community 23"
Cohesion: 0.14
Nodes (22): Darwin, attr(), authorizedTime(), boolean(), box(), children(), emit(), fivePoints() (+14 more)

### Community 24 - "Community 24"
Cohesion: 0.12
Nodes (10): AppState, AppOrchestrator, ConversationBridge, BridgeTests, proposal(), Provider, report(), SessionConversationTests (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.14
Nodes (12): run_once(), handler(), ConfirmationRequest, ConfirmationResponse, ErrorCode, TaskOrchestrator, confirm_in_cli(), ConfirmationError (+4 more)

### Community 26 - "Community 26"
Cohesion: 0.09
Nodes (8): _clean_text(), _DOMBuilder, _DOMNode, _extract_from_container(), _find_candidate_containers(), _sanitize_link(), _scan_links_iterative(), _score_container()

### Community 27 - "Community 27"
Cohesion: 0.11
Nodes (8): valid_title(), plan_known_app(), MissingInformation, RequestRejected, inspect_note_reference(), NoteReference, check_request_constraints(), replace_note_title()

### Community 28 - "Community 28"
Cohesion: 0.12
Nodes (15): Case, score(), main(), run_once(), RevalidationEvidence, RevalidationResult, evaluate_revalidation(), result() (+7 more)

### Community 29 - "Community 29"
Cohesion: 0.13
Nodes (8): Case, check_cases(), render(), assess(), Clock, ObservedGrounder, summarize(), BrowserVisionQualificationTests

### Community 30 - "Community 30"
Cohesion: 0.09
Nodes (4): HelperTransport, strict_json(), _NoRedirect, Response

### Community 31 - "Community 31"
Cohesion: 0.13
Nodes (4): Preferences, PreferencesError, PreferencesStore, PreferencesTests

### Community 32 - "Community 32"
Cohesion: 0.14
Nodes (11): build_report(), _in_order(), main(), markdown(), run_once(), readline(), Scenario, summarize() (+3 more)

### Community 33 - "Community 33"
Cohesion: 0.22
Nodes (4): ObservedSession, terminal_text(), VoiceSession, transcript_text()

### Community 34 - "Community 34"
Cohesion: 0.11
Nodes (6): FakeNotesAdapter, FakeNoteStore, Method, DemoPolicy, RegistryTests, AdapterAuthorizationTests

### Community 35 - "Community 35"
Cohesion: 0.14
Nodes (12): case(), SelectionCase, evaluate(), main(), markdown(), write_report(), select(), AIMSEvaluationTests (+4 more)

### Community 36 - "Community 36"
Cohesion: 0.18
Nodes (7): main(), run_case(), main(), main(), BrowserError, BrowserSession, public_url()

### Community 37 - "Community 37"
Cohesion: 0.14
Nodes (5): default_macos_notifier(), ReminderNotificationConsumer, DueEvent, Occurrence, RemindersConsumerTests

### Community 38 - "Community 38"
Cohesion: 0.15
Nodes (7): main(), ResultRegionProfile, numeric_format_summary(), capture_calculator_result(), standard_entry_profile(), CalculatorVerificationTests, FakeBackend

### Community 40 - "Community 40"
Cohesion: 0.19
Nodes (4): InteractiveSession, run_session(), is_web_command(), factory()

### Community 41 - "Community 41"
Cohesion: 0.19
Nodes (8): comparison(), comparison_markdown(), main(), progress(), run_reports(), save_reports(), PlanningFailure, ModelBenchmarkTests

### Community 42 - "Community 42"
Cohesion: 0.17
Nodes (11): CalculatorExpectation, CalculatorObservation, CalculatorVerificationResult, parse_display_number(), _capture(), capture_calculator_entry(), _number(), _valid_observation() (+3 more)

### Community 43 - "Community 43"
Cohesion: 0.11
Nodes (3): create_corpus(), SpeechEvaluationTests, transcribe()

### Community 44 - "Community 44"
Cohesion: 0.20
Nodes (3): Reminder, ReminderError, ReminderStore

### Community 45 - "Community 45"
Cohesion: 0.12
Nodes (5): main(), decline(), BackendError, MacOSAppBackend, NativeBackendTests

### Community 46 - "Community 46"
Cohesion: 0.13
Nodes (10): TaskStatus, TaskReport, BridgeResult, trusted_outcome(), main(), speak_prompt(), speak_reply(), speak_report() (+2 more)

### Community 47 - "Community 47"
Cohesion: 0.17
Nodes (6): Bridge, main(), GUIBridgeTests, write(), listen_once(), ScriptBridge

### Community 48 - "Community 48"
Cohesion: 0.14
Nodes (13): sha256(), bounded_update_scan(), main(), run(), decode(), __init__(), loss_fn(), measure() (+5 more)

### Community 49 - "Community 49"
Cohesion: 0.19
Nodes (12): attr(), boolean(), box(), children(), finish(), marker(), output(), point() (+4 more)

### Community 50 - "Community 50"
Cohesion: 0.15
Nodes (11): convert(), fetch(), file_hash(), prepare(), revision(), run(), validate_model(), doctor() (+3 more)

### Community 51 - "Community 51"
Cohesion: 0.15
Nodes (7): discover_target(), NativeBackend, _object(), RevalidationBackend, DisplayGeometryBackend, test_protocol_rejects_duplicate_keys_and_bool_integer(), test_timeout_is_bounded_error()

### Community 52 - "Community 52"
Cohesion: 0.17
Nodes (8): DesktopElement, DesktopObservationResult, DesktopSnapshot, _error(), _parse(), _valid_string(), evaluate(), VisibilityTests

### Community 53 - "Community 53"
Cohesion: 0.17
Nodes (14): distance(), evaluate(), load_cases(), normalized(), term_counts(), term_scores(), text_scores(), combine_lora_output() (+6 more)

### Community 54 - "Community 54"
Cohesion: 0.22
Nodes (9): main(), VisibilityBackend, VisibilityEvidence, VisibilityResult, _box(), evaluate_visibility(), result(), _inside() (+1 more)

### Community 55 - "Community 55"
Cohesion: 0.18
Nodes (6): ContractError, json_value(), require_mapping(), require_text(), require_time(), require_uuid()

### Community 56 - "Community 56"
Cohesion: 0.21
Nodes (12): DesktopTargetResult, check_geometry(), _displays_valid(), _inside(), _box_valid(), evidence_summary(), _incomplete_reason(), locate_control() (+4 more)

### Community 57 - "Community 57"
Cohesion: 0.16
Nodes (3): QwenTranscriber, ReferenceQwenTranscriber, QwenAdapterTests

### Community 58 - "Community 58"
Cohesion: 0.14
Nodes (5): approve(), ConfirmationPipelineTests, handler(), handler(), ConfirmationTests

### Community 60 - "Community 60"
Cohesion: 0.14
Nodes (4): BufferedBackend, SpeechBufferingTests, popen(), FakeProcess

### Community 61 - "Community 61"
Cohesion: 0.15
Nodes (5): screen(), fetch_file(), main(), QwenResearchToolsTests, Response

### Community 62 - "Community 62"
Cohesion: 0.20
Nodes (5): web_runtime(), approval(), BrowserWorkflowTests, decline(), FakeBrowser

### Community 63 - "Community 63"
Cohesion: 0.18
Nodes (4): WhisperTranscriber, runner(), make_wav(), WhisperTests

### Community 65 - "Community 65"
Cohesion: 0.11
Nodes (9): AppKit, CoreGraphics, Foundation, ImageIO, hasVietnamese(), emit(), id(), Speech (+1 more)

### Community 66 - "Community 66"
Cohesion: 0.32
Nodes (4): node(), snapshot(), DesktopTargetingTests, find()

### Community 67 - "Community 67"
Cohesion: 0.14
Nodes (4): AdapterRegistry, event(), finish(), TraceSession

### Community 68 - "Community 68"
Cohesion: 0.19
Nodes (3): instant(), ReminderTests, poll()

### Community 69 - "Community 69"
Cohesion: 0.23
Nodes (6): AppleNotesBackend, decode(), NoteMetadata, NotesScope, make_backend(), MatchesBridgeTests

### Community 70 - "Community 70"
Cohesion: 0.18
Nodes (7): Case, check_cases(), main(), score_cases(), _write_new(), DesktopTargetingBenchmarkTests, always_wrong()

### Community 72 - "Community 72"
Cohesion: 0.20
Nodes (6): _NoRedirect, OllamaProvider, envelope(), LocalHTTPIntegrationTests, do_POST(), OllamaProviderTests

### Community 73 - "Community 73"
Cohesion: 0.19
Nodes (3): SpokenReviewTests, listen(), listen()

### Community 74 - "Community 74"
Cohesion: 0.25
Nodes (3): proposal(), Provider, VoiceConversationTests

### Community 75 - "Community 75"
Cohesion: 0.16
Nodes (5): Case, main(), score(), _summary(), CalculatorVerificationBenchmarkTests

### Community 77 - "Community 77"
Cohesion: 0.19
Nodes (4): NotesBackendError, approve(), NotesPipelineTests, handler()

### Community 78 - "Community 78"
Cohesion: 0.28
Nodes (8): _local_instant(), _next(), _next_after_gap(), _parse(), Schedule, _stamp(), _utc(), _zone()

### Community 79 - "Community 79"
Cohesion: 0.21
Nodes (7): build_report(), main(), markdown(), Scenario, summarize(), write_report(), BenchmarkTests

### Community 80 - "Community 80"
Cohesion: 0.15
Nodes (4): _datetime(), main(), _print(), _schedule()

### Community 81 - "Community 81"
Cohesion: 0.24
Nodes (8): attribute(), bbox(), boolean(), children(), point(), sameBox(), size(), text()

### Community 82 - "Community 82"
Cohesion: 0.17
Nodes (5): MacOSAppAdapter, AppPolicy, AppPlanningAndPolicyTests, backend_mock(), app_factory()

### Community 83 - "Community 83"
Cohesion: 0.25
Nodes (6): ModelOrchestrator, TraceStore, approve(), ModelPipelineTests, confirm(), GuardPipelineTests

### Community 84 - "Community 84"
Cohesion: 0.26
Nodes (4): NotesOrchestrator, ambiguous_backend(), DuplicateSelectionTests, notes_factory()

### Community 85 - "Community 85"
Cohesion: 0.21
Nodes (3): render_spoken_summary(), report(), VoiceOutputTests

### Community 86 - "Community 86"
Cohesion: 0.19
Nodes (7): c(), Case, check_cases(), score_cases(), VisibilityBenchmarkTests, always_visible(), wrong_binding()

### Community 87 - "Community 87"
Cohesion: 0.22
Nodes (4): diagnose(), DiagnosticProvider, main(), PlannerDiagnosticTests

### Community 88 - "Community 88"
Cohesion: 0.22
Nodes (4): BrowserDOMAdapter, plan_web(), valid_web_intent(), WebPolicy

### Community 89 - "Community 89"
Cohesion: 0.24
Nodes (3): plan_notes(), NotesPolicy, ScopePlannerPolicyTests

### Community 90 - "Community 90"
Cohesion: 0.22
Nodes (4): run_voice(), NativeRecorder, stop_owned_process(), RecorderTests

### Community 92 - "Community 92"
Cohesion: 0.17
Nodes (4): WebObservationTests, backend(), recognize(), locate()

### Community 93 - "Community 93"
Cohesion: 0.30
Nodes (4): observed(), OllamaVisionProvider, VisionProviderError, ProviderTests

### Community 94 - "Community 94"
Cohesion: 0.29
Nodes (8): attribute(), box(), children(), emit(), enabledAttribute(), point(), size(), stringAttribute()

### Community 95 - "Community 95"
Cohesion: 0.24
Nodes (7): inspect_audio(), context_text(), model_assets_available(), handle(), main(), handle(), main()

### Community 96 - "Community 96"
Cohesion: 0.23
Nodes (7): reject(), _duration(), _enum(), _safe_diagnostics(), sanitize_record(), time_text(), PrivacyProjectionTests

### Community 98 - "Community 98"
Cohesion: 0.22
Nodes (3): package(), runtime_files(), PreviewPackageTests

### Community 100 - "Community 100"
Cohesion: 0.18
Nodes (4): main(), confirm(), CalculatorResultReader, Reader

### Community 102 - "Community 102"
Cohesion: 0.35
Nodes (4): observe_app(), backend(), DesktopObservationTests, envelope()

### Community 104 - "Community 104"
Cohesion: 0.23
Nodes (4): ReplyTests, communicate(), start(), FakeBackend

### Community 105 - "Community 105"
Cohesion: 0.23
Nodes (6): ApplicationServices, attribute(), children(), emit(), text(), uniqueTopLevelKeys()

### Community 106 - "Community 106"
Cohesion: 0.21
Nodes (5): _candidate(), Case, check_cases(), _domain(), WebObservationCasesTests

### Community 107 - "Community 107"
Cohesion: 0.23
Nodes (6): read_segment(), write_joined(), prepare_reply(), SpeechPart, communicate(), pcm()

### Community 108 - "Community 108"
Cohesion: 0.23
Nodes (4): _candidate(), Clarification, clarification_for(), ClarificationAnalysisTests

### Community 109 - "Community 109"
Cohesion: 0.27
Nodes (4): CropError, resize_crop(), png(), PresentationTests

### Community 113 - "Community 113"
Cohesion: 0.31
Nodes (4): collect(), wait(), audio_quality(), AudioQualityTests

### Community 115 - "Community 115"
Cohesion: 0.33
Nodes (3): uuid_text(), _check_file(), TraceStorageError

### Community 116 - "Community 116"
Cohesion: 0.29
Nodes (3): ModelComparisonTests, grounder(), locate()

### Community 117 - "Community 117"
Cohesion: 0.31
Nodes (4): _case(), main(), score(), ReminderBenchmarkTests

### Community 124 - "Community 124"
Cohesion: 0.29
Nodes (3): RemindersOrchestrator, RemindersOrchestratorTests, approve_handler()

### Community 125 - "Community 125"
Cohesion: 0.38
Nodes (3): AVFoundation, emit(), fail()

### Community 131 - "Community 131"
Cohesion: 0.50
Nodes (3): cases, coordinate_unit, schema_version

### Community 137 - "Community 137"
Cohesion: 0.67
Nodes (3): factory(), wrapped(), planner()

## Knowledge Gaps
- **9 isolated node(s):** `AVFoundation`, `elvion`, `Darwin`, `Carbon`, `.compact` (+4 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 766 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **58 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskRequest` connect `Community 12` to `Community 0`, `Community 129`, `Community 11`, `Community 14`, `Community 15`, `Community 16`, `Community 17`, `Community 19`, `Community 22`, `Community 24`, `Community 25`, `Community 27`, `Community 34`, `Community 40`, `Community 45`, `Community 46`, `Community 55`, `Community 58`, `Community 62`, `Community 64`, `Community 67`, `Community 69`, `Community 71`, `Community 77`, `Community 82`, `Community 83`, `Community 84`, `Community 87`, `Community 89`, `Community 100`, `Community 101`, `Community 120`, `Community 124`, `Community 126`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 50 inferred relationships involving `TaskRequest` (e.g. with `evaluate()` and `run_once()`) actually correct?**
  _`TaskRequest` has 50 INFERRED edges - model-reasoned connections that need verification._
- **What connects `AVFoundation`, `elvion`, `Darwin` to the rest of the system?**
  _9 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.0646476412347117 - nodes in this community are weakly interconnected._
- **Why does `ActionIntent` connect `Community 13` to `Community 0`, `Community 89`, `Community 34`, `Community 67`, `Community 88`, `Community 11`, `Community 12`, `Community 14`, `Community 82`, `Community 19`, `Community 22`, `Community 55`, `Community 120`, `Community 25`, `Community 27`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `ActionIntent` (e.g. with `evaluate()` and `AppleNotesAdapter`) actually correct?**
  _`ActionIntent` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.050286058416139714 - nodes in this community are weakly interconnected._