from __future__ import annotations

import json
import pathlib
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def run_node(script: str) -> dict:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", textwrap.dedent(script)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


class FluxioVoicePrimitiveTests(unittest.TestCase):
    def test_transcript_buffer_tracks_interim_final_and_low_confidence_segments(self) -> None:
        payload = run_node(
            """
            import {
              appendTranscriptSegment,
              buildTranscriptSnapshot,
              createVoiceTranscriptState,
              finalizeInterimTranscript,
              transcriptNeedsReview,
            } from './web/src/fluxio/voice/voiceTranscriptBuffer.js';

            let state = createVoiceTranscriptState({ maxSegments: 2, lowConfidenceThreshold: 0.75 });
            state = appendTranscriptSegment(state, { id: 'one', text: 'open settings', confidence: 0.93 });
            state = appendTranscriptSegment(state, { id: 'two', text: 'send massage', confidence: 0.52 });
            state = appendTranscriptSegment(state, { id: 'three', text: 'show proof', confidence: 0.88 });
            state = appendTranscriptSegment(state, { id: 'draft', text: 'approve request', confidence: 0.64, isFinal: false });
            const interimSnapshot = buildTranscriptSnapshot(state);
            state = finalizeInterimTranscript(state, { confidence: 0.91 });
            const finalSnapshot = buildTranscriptSnapshot(state);
            console.log(JSON.stringify({
              interimText: interimSnapshot.interimText,
              finalText: finalSnapshot.finalText,
              segmentIds: finalSnapshot.segments.map(segment => segment.id),
              needsReviewBeforeFinal: transcriptNeedsReview({
                ...state,
                interim: { text: 'still changing', confidence: 0.9 }
              }),
              warnings: interimSnapshot.warnings,
            }));
            """
        )

        self.assertEqual(payload["interimText"], "approve request")
        self.assertEqual(payload["segmentIds"], ["three", "draft"])
        self.assertEqual(payload["finalText"], "show proof approve request")
        self.assertTrue(payload["needsReviewBeforeFinal"])
        self.assertIn("Listening result is still changing", " ".join(payload["warnings"]))

    def test_command_grammar_requires_recovery_for_unclear_or_risky_commands(self) -> None:
        payload = run_node(
            """
            import {
              buildAccidentalSendGuard,
              buildVoiceModeCheckpoint,
              buildVoiceCommandPacket,
              buildVoiceCommandReviewTarget,
              fingerprintVoiceText,
              parseVoiceCommand,
            } from './web/src/fluxio/voice/voiceCommandGrammar.js';

            const navigation = parseVoiceCommand('open settings', { confidence: 0.95 });
            const lowConfidence = parseVoiceCommand('send message', { confidence: 0.41 });
            const approval = parseVoiceCommand('approve request', { confidence: 0.96 });
            const unknown = parseVoiceCommand('open nebula', { confidence: 0.96 });
            const send = parseVoiceCommand('send message', { confidence: 0.96 });
            const clear = parseVoiceCommand('clear transcript', { confidence: 0.96 });
            const guarded = buildAccidentalSendGuard({
              command: send,
              transcript: {
                reviewRequired: true,
                lowConfidenceSegments: [{ id: 'unclear' }],
                ambiguousSegments: [],
              },
            });
            const confirmationGuard = buildAccidentalSendGuard({
              command: send,
              transcript: { reviewRequired: false, lowConfidenceSegments: [], ambiguousSegments: [] },
            });
            const readyTarget = buildVoiceCommandReviewTarget({
              command: send,
              context: {
                composerText: 'Please continue the PR stack and include proof.',
                missionId: 'mission-42',
                missionTitle: 'Autonomous platform proof',
                attachmentCount: 2,
              },
            });
            const emptyTarget = buildVoiceCommandReviewTarget({
              command: send,
              context: { composerText: '', workspaceName: 'Syntelos Workspace' },
            });
            const workspaceChatTarget = buildVoiceCommandReviewTarget({
              command: send,
              context: {
                composerText: 'Continue the stack',
                workspaceName: 'Syntelos Workspace',
                idleSendMode: 'chat',
              },
            });
            const confirmationPacket = buildVoiceCommandPacket({
              command: send,
              guard: confirmationGuard,
              transcript: { reviewRequired: false, lowConfidenceSegments: [], ambiguousSegments: [], combinedText: 'send message' },
              reviewTarget: readyTarget,
            });
            const dictationModeCheckpoint = buildVoiceModeCheckpoint({
              text: 'send message',
              activeMode: 'dictation',
              command: send,
            });
            const dictationModeGuard = buildAccidentalSendGuard({
              command: send,
              activeMode: 'dictation',
              transcript: { reviewRequired: false, lowConfidenceSegments: [], ambiguousSegments: [], combinedText: 'send message' },
            });
            const packet = buildVoiceCommandPacket({
              command: send,
              guard: dictationModeGuard,
              transcript: {
                finalText: 'send message',
                combinedText: 'send message',
                inputMode: 'dictation',
                reviewRequired: true,
                averageConfidence: 0.81,
                segments: [{ id: 'unclear', text: 'send massage', confidence: 0.52 }],
                lowConfidenceSegments: [{ id: 'unclear', text: 'send massage', confidence: 0.52 }],
                ambiguousSegments: [{ id: 'unclear', text: 'send massage', confidence: 0.52 }],
                correctionLog: [{ id: 'fix', from: 'massage', to: 'message' }],
                repairQueue: { status: 'review', nextSegmentId: 'unclear', nextSegmentText: 'send massage' },
                warnings: ['review before send'],
              },
            });
            console.log(JSON.stringify({
              navigation,
              lowConfidence,
              approval,
              unknown,
              send,
              clear,
              guarded,
              confirmationGuard,
              confirmationPacket,
              readyTarget,
              emptyTarget,
              workspaceChatTarget,
              sameFingerprint: readyTarget.textFingerprint === fingerprintVoiceText('Please continue the PR stack and include proof.'),
              changedFingerprint: readyTarget.textFingerprint === fingerprintVoiceText('Changed text'),
              dictationModeCheckpoint,
              dictationModeGuard,
              packet
            }));
            """
        )

        self.assertTrue(payload["navigation"]["matched"])
        self.assertEqual(payload["navigation"]["action"], "surface.open")
        self.assertEqual(payload["navigation"]["parameters"]["surface"], "settings")
        self.assertFalse(payload["lowConfidence"]["matched"])
        self.assertEqual(payload["lowConfidence"]["blockedReason"], "low_confidence")
        self.assertTrue(payload["approval"]["requiresConfirmation"])
        self.assertEqual(payload["approval"]["parameters"]["decision"], "approved")
        self.assertEqual(payload["unknown"]["blockedReason"], "unknown_surface")
        self.assertEqual(payload["clear"]["action"], "voice.clearTranscript")
        self.assertTrue(payload["clear"]["requiresConfirmation"])
        self.assertEqual(payload["guarded"]["status"], "review_required")
        self.assertEqual(payload["guarded"]["reason"], "transcript_quality")
        self.assertEqual(payload["confirmationGuard"]["status"], "confirmation_required")
        self.assertTrue(payload["confirmationPacket"]["review"]["confirmationRequired"])
        self.assertFalse(payload["confirmationPacket"]["review"]["sendable"])
        self.assertEqual(payload["confirmationPacket"]["review"]["target"]["label"], "Mission follow-up")
        self.assertEqual(payload["confirmationPacket"]["review"]["target"]["attachmentCount"], 2)
        self.assertFalse(payload["readyTarget"]["blocked"])
        self.assertEqual(payload["readyTarget"]["destination"], "Autonomous platform proof")
        self.assertTrue(payload["sameFingerprint"])
        self.assertFalse(payload["changedFingerprint"])
        self.assertTrue(payload["emptyTarget"]["blocked"])
        self.assertEqual(payload["emptyTarget"]["blockedReason"], "empty_composer")
        self.assertEqual(payload["workspaceChatTarget"]["label"], "Workspace chat message")
        self.assertTrue(payload["dictationModeCheckpoint"]["modeConflict"])
        self.assertEqual(payload["dictationModeCheckpoint"]["route"], "hold_for_mode_review")
        self.assertEqual(payload["dictationModeGuard"]["reason"], "dictation_contains_command")
        self.assertEqual(payload["packet"]["schemaVersion"], "fluxio.voice-command-packet.v1")
        self.assertEqual(payload["packet"]["command"]["action"], "composer.send")
        self.assertEqual(payload["packet"]["transcript"]["inputMode"], "dictation")
        self.assertEqual(payload["packet"]["transcript"]["lowConfidenceCount"], 1)
        self.assertEqual(payload["packet"]["transcript"]["ambiguousCount"], 1)
        self.assertEqual(payload["packet"]["transcript"]["correctionCount"], 1)
        self.assertIn("dictation_contains_command", payload["packet"]["review"]["blockedBy"])
        self.assertEqual(payload["packet"]["review"]["modeCheckpoint"]["activeMode"], "dictation")
        self.assertFalse(payload["packet"]["review"]["sendable"])

    def test_transcript_corrections_and_ambiguity_are_visible_metadata(self) -> None:
        payload = run_node(
            """
            import {
              appendTranscriptSegment,
              buildVoiceRepairQueue,
              buildTranscriptSnapshot,
              createVoiceTranscriptState,
              replaceTranscriptSegment,
              transcriptNeedsReview,
            } from './web/src/fluxio/voice/voiceTranscriptBuffer.js';

            let state = createVoiceTranscriptState({
              lowConfidenceThreshold: 0.7,
              ambiguityConfidenceThreshold: 0.86,
            });
            state = appendTranscriptSegment(state, {
              id: 'phrase',
              text: 'send massage',
              confidence: 0.81,
              alternatives: [{ text: 'send message', confidence: 0.8 }],
              ambiguityReasons: ['message and massage sound similar'],
            });
            const before = buildTranscriptSnapshot(state);
            const repairQueue = buildVoiceRepairQueue(before);
            state = replaceTranscriptSegment(state, 'phrase', {
              text: 'send message',
              reason: 'operator correction',
            });
            const after = buildTranscriptSnapshot(state);
            console.log(JSON.stringify({
              needsReviewBefore: transcriptNeedsReview({ ...state, interim: { text: 'send mess', confidence: 0.9 } }),
              ambiguousCount: before.ambiguousSegments.length,
              repairLabel: repairQueue.label,
              nextRepair: repairQueue.nextSegmentText,
              correctionCount: after.correctionCount,
              correctedFrom: after.segments[0].correctedFrom,
              checkIds: after.qualityChecks.map(check => check.id),
            }));
            """
        )

        self.assertTrue(payload["needsReviewBefore"])
        self.assertEqual(payload["ambiguousCount"], 1)
        self.assertEqual(payload["repairLabel"], "Repair before send")
        self.assertEqual(payload["nextRepair"], "send massage")
        self.assertEqual(payload["correctionCount"], 1)
        self.assertEqual(payload["correctedFrom"], "send massage")
        self.assertIn("ambiguity", payload["checkIds"])

    def test_unknown_confidence_requires_review_without_faking_stt_confidence(self) -> None:
        payload = run_node(
            """
            import {
              appendTranscriptSegment,
              buildTranscriptSnapshot,
              createVoiceTranscriptState,
              replaceTranscriptSegment,
            } from './web/src/fluxio/voice/voiceTranscriptBuffer.js';

            let state = createVoiceTranscriptState();
            state = appendTranscriptSegment(state, {
              id: 'local-stt',
              text: 'send message',
              source: 'tauri-local-stt',
            });
            const before = buildTranscriptSnapshot(state);
            state = replaceTranscriptSegment(state, 'local-stt', {
              text: 'send message',
              reason: 'operator reviewed local STT',
              reviewedAt: '2026-06-21T06:00:00.000Z',
              reviewedBy: 'operator',
            });
            const after = buildTranscriptSnapshot(state);
            console.log(JSON.stringify({
              beforeUnknown: before.unknownConfidenceSegments.length,
              beforeReviewRequired: before.reviewRequired,
              beforeQueueKind: before.repairQueue.nextRepairKind,
              afterUnknown: after.unknownConfidenceSegments.length,
              afterReviewRequired: after.reviewRequired,
              rawConfidence: after.segments[0].confidence,
              reviewedBy: after.segments[0].reviewedBy,
              checkIds: before.qualityChecks.map(check => check.id),
            }));
            """
        )

        self.assertEqual(payload["beforeUnknown"], 1)
        self.assertTrue(payload["beforeReviewRequired"])
        self.assertEqual(payload["beforeQueueKind"], "unknown_confidence")
        self.assertEqual(payload["afterUnknown"], 0)
        self.assertFalse(payload["afterReviewRequired"])
        self.assertIsNone(payload["rawConfidence"])
        self.assertEqual(payload["reviewedBy"], "operator")
        self.assertIn("unknown-confidence", payload["checkIds"])

    def test_accessibility_helpers_do_not_claim_live_voice_without_checked_support(self) -> None:
        payload = run_node(
            """
            import {
              buildKeyboardParityLabel,
              describeVoiceCaptureStatus,
              detectVoiceInputSupport,
              getVoiceMotionAffordance,
              getVoiceStatusCopy,
            } from './web/src/fluxio/voice/voiceAccessibility.js';

            const unsupported = detectVoiceInputSupport({ window: {} });
            const browser = detectVoiceInputSupport({ window: { SpeechRecognition: function SpeechRecognition() {} } });
            const bridge = detectVoiceInputSupport({
              window: { __FLUXIO_VOICE_BRIDGE__: { startDictation() {}, stopDictation() {} } }
            });
            const browserWithoutAdapter = describeVoiceCaptureStatus({ support: browser });
            const browserWithAdapter = describeVoiceCaptureStatus({
              support: browser,
              speechAdapter: { label: 'Browser speech adapter', start() {}, stop() {} }
            });
            console.log(JSON.stringify({
              unsupported,
              browser,
              bridge,
              browserWithoutAdapter,
              browserWithAdapter,
              unwiredStatus: getVoiceStatusCopy({ support: browser, capture: browserWithoutAdapter }),
              unsupportedStatus: getVoiceStatusCopy({ support: unsupported }),
              label: buildKeyboardParityLabel({
                label: 'Send message',
                shortcut: 'Ctrl+Enter',
                voice: 'send message'
              }),
              reduced: getVoiceMotionAffordance(true),
            }));
            """
        )

        self.assertFalse(payload["unsupported"]["supported"])
        self.assertEqual(payload["unsupported"]["mode"], "none")
        self.assertIn("not available", payload["unsupportedStatus"])
        self.assertTrue(payload["browser"]["supported"])
        self.assertEqual(payload["browser"]["mode"], "browser-speech-api")
        self.assertTrue(payload["bridge"]["supported"])
        self.assertEqual(payload["bridge"]["mode"], "bridge")
        self.assertFalse(payload["browserWithoutAdapter"]["canStartLiveCapture"])
        self.assertEqual(payload["browserWithoutAdapter"]["label"], "Adapter not wired")
        self.assertTrue(payload["browserWithAdapter"]["canStartLiveCapture"])
        self.assertIn("no active capture adapter", payload["unwiredStatus"])
        self.assertIn("Keyboard: Ctrl+Enter", payload["label"])
        self.assertEqual(payload["reduced"]["data-motion"], "reduced")

    def test_voice_capture_adapters_normalize_browser_and_bridge_results(self) -> None:
        payload = run_node(
            """
            import {
              createBridgeSpeechAdapter,
              createBrowserSpeechAdapter,
              createVoiceCaptureAdapter,
              normalizeSpeechRecognitionResult,
            } from './web/src/fluxio/voice/voiceCaptureAdapters.js';

            const browserSegments = [];
            const browserStops = [];
            const browserLifecycle = [];
            class FakeSpeechRecognition {
              constructor() {
                FakeSpeechRecognition.instance = this;
                FakeSpeechRecognition.instances.push(this);
              }
              start() {
                const interim = [
                  { transcript: 'open set', confidence: 0.62 },
                  { transcript: 'open settings', confidence: 0.58 },
                ];
                interim.isFinal = false;
                const finalResult = [
                  { transcript: 'open settings', confidence: 0.94 },
                  { transcript: 'open setting', confidence: 0.72 },
                ];
                finalResult.isFinal = true;
                this.onresult({ resultIndex: 0, results: [interim, finalResult] });
              }
              stop() {
                this.stopped = true;
              }
            }
            FakeSpeechRecognition.instances = [];
            const browserAdapter = createBrowserSpeechAdapter({ window: { SpeechRecognition: FakeSpeechRecognition } });
            await browserAdapter.start({
              onInterim: segment => browserSegments.push({ kind: 'interim', ...segment }),
              onFinal: segment => browserSegments.push({ kind: 'final', ...segment }),
              onStop: event => browserStops.push(event),
              onLifecycle: event => browserLifecycle.push(event),
            });
            FakeSpeechRecognition.instance.onend();
            await browserAdapter.stop();

            const bridgeSegments = [];
            const bridgeAdapter = createBridgeSpeechAdapter({
              window: {
                __FLUXIO_VOICE_BRIDGE__: {
                  startDictation(callbacks) {
                    callbacks.onInterim({ text: 'show pro', confidence: 0.51 });
                    callbacks.onFinal({ text: 'show proof', confidence: 0.92, alternatives: ['show proofs'] });
                    return () => { this.unsubscribed = true; };
                  },
                  stopDictation() { this.stopped = true; },
                },
              },
            });
            await bridgeAdapter.start({
              onInterim: segment => bridgeSegments.push({ kind: 'interim', ...segment }),
              onFinal: segment => bridgeSegments.push({ kind: 'final', ...segment }),
            });
            await bridgeAdapter.stop();

            const preferred = createVoiceCaptureAdapter({
              window: {
                SpeechRecognition: FakeSpeechRecognition,
                __FLUXIO_VOICE_BRIDGE__: { start() {}, stop() {} },
              },
            });
            const normalized = normalizeSpeechRecognitionResult(
              Object.assign(
                [
                  { transcript: 'send message', confidence: 0.91 },
                  { transcript: 'send massage', confidence: 0.68 },
                ],
                { isFinal: true },
              ),
              { source: 'test' },
            );

            console.log(JSON.stringify({
              browserKinds: browserSegments.map(item => item.kind),
              browserFinal: browserSegments.find(item => item.kind === 'final'),
              browserStops,
              browserLifecycle,
              browserStopped: FakeSpeechRecognition.instance.stopped,
              browserInstanceCount: FakeSpeechRecognition.instances.length,
              bridgeKinds: bridgeSegments.map(item => item.kind),
              bridgeFinal: bridgeSegments.find(item => item.kind === 'final'),
              preferredName: preferred.name,
              normalized,
            }));
            """
        )

        self.assertEqual(payload["browserKinds"][:2], ["interim", "final"])
        self.assertEqual(payload["browserFinal"]["text"], "open settings")
        self.assertEqual(payload["browserFinal"]["alternatives"][0]["text"], "open setting")
        self.assertEqual(payload["browserStops"], [])
        self.assertIn("reconnecting", [item["status"] for item in payload["browserLifecycle"]])
        self.assertIn("restarted", [item["status"] for item in payload["browserLifecycle"]])
        self.assertGreaterEqual(payload["browserInstanceCount"], 2)
        self.assertTrue(payload["browserStopped"])
        self.assertEqual(payload["bridgeKinds"], ["interim", "final"])
        self.assertEqual(payload["bridgeFinal"]["text"], "show proof")
        self.assertEqual(payload["bridgeFinal"]["alternatives"][0]["text"], "show proofs")
        self.assertEqual(payload["preferredName"], "fluxio-voice-bridge")
        self.assertEqual(payload["normalized"]["text"], "send message")
        self.assertEqual(payload["normalized"]["alternatives"][0]["text"], "send massage")

    def test_voice_capture_adapter_errors_are_visible(self) -> None:
        payload = run_node(
            """
            import { createBrowserSpeechAdapter } from './web/src/fluxio/voice/voiceCaptureAdapters.js';

            class FakeSpeechRecognition {
              constructor() {
                FakeSpeechRecognition.instance = this;
                FakeSpeechRecognition.instances.push(this);
              }
              start() {
                this.onerror({ error: 'not-allowed', message: 'permission denied by test' });
              }
              stop() {}
            }
            FakeSpeechRecognition.instances = [];
            const errors = [];
            const lifecycle = [];
            const stops = [];
            const adapter = createBrowserSpeechAdapter({ window: { webkitSpeechRecognition: FakeSpeechRecognition } });
            await adapter.start({
              onError: error => errors.push(error),
              onLifecycle: event => lifecycle.push(event),
              onStop: event => stops.push(event),
            });
            FakeSpeechRecognition.instance.onend();
            console.log(JSON.stringify({
              label: adapter.label,
              errors,
              lifecycle,
              stops,
              instanceCount: FakeSpeechRecognition.instances.length,
            }));
            """
        )

        self.assertEqual(payload["label"], "Browser speech adapter")
        self.assertEqual(payload["errors"][0]["code"], "permission_denied")
        self.assertIn("permission denied", payload["errors"][0]["message"])
        self.assertEqual(payload["instanceCount"], 1)
        self.assertIn("blocked", [item["status"] for item in payload["lifecycle"]])
        self.assertNotIn("restarted", [item["status"] for item in payload["lifecycle"]])
        self.assertEqual(payload["stops"][0]["errorCode"], "permission_denied")

    def test_tauri_voice_bridge_records_audio_before_local_stt(self) -> None:
        payload = run_node(
            """
            import { installTauriVoiceBridge } from './web/src/fluxio/voice/tauriVoiceBridge.js';

            class FakeBlob {
              constructor(parts, options = {}) {
                this.parts = parts;
                this.type = options.type || '';
                this.size = parts.reduce((total, part) => total + Number(part?.size || String(part || '').length), 0);
              }
            }
            class FakeFileReader {
              readAsDataURL() {
                this.result = 'data:audio/webm;base64,ZmFrZS1hdWRpbw==';
                this.onloadend();
              }
            }
            class FakeMediaRecorder {
              static isTypeSupported() { return true; }
              constructor(stream, options = {}) {
                this.stream = stream;
                this.mimeType = options.mimeType || 'audio/webm';
                this.state = 'inactive';
              }
              start() {
                this.state = 'recording';
                this.ondataavailable({ data: { size: 10 } });
              }
              stop() {
                this.state = 'inactive';
                this.onstop();
              }
            }
            const calls = [];
            const lifecycle = [];
            const finals = [];
            const stops = [];
            const root = {
              __TAURI_INTERNALS__: {},
              Blob: FakeBlob,
              FileReader: FakeFileReader,
              MediaRecorder: FakeMediaRecorder,
              navigator: {
                mediaDevices: {
                  async getUserMedia() {
                    return { getTracks: () => [{ stop() { this.stopped = true; } }] };
                  },
                },
              },
            };
            globalThis.Blob = FakeBlob;
            const bridge = installTauriVoiceBridge(root, {
              FileReader: FakeFileReader,
              MediaRecorder: FakeMediaRecorder,
              navigator: root.navigator,
              async invoke(command, args) {
                calls.push({ command, args });
                if (command === 'start_dictation') return { sessionId: 'dict-test' };
                if (command === 'save_dictation_audio_blob') {
                  return { audioPath: 'C:/tmp/dict-test.webm', byteCount: 10 };
                }
                if (command === 'stop_dictation') {
                  return { status: 'transcribed', transcript: 'open settings', message: '' };
                }
                throw new Error(command);
              },
            });
            await bridge.startDictation({
              onLifecycle: event => lifecycle.push(event.status),
              onFinal: segment => finals.push(segment),
              onStop: event => stops.push(event),
            });
            await bridge.stopDictation();
            console.log(JSON.stringify({ calls, lifecycle, finals, stops, installed: Boolean(root.__FLUXIO_VOICE_BRIDGE__) }));
            """
        )

        self.assertTrue(payload["installed"])
        self.assertEqual([item["command"] for item in payload["calls"]], [
            "start_dictation",
            "save_dictation_audio_blob",
            "stop_dictation",
        ])
        self.assertIn("started", payload["lifecycle"])
        self.assertIn("saving", payload["lifecycle"])
        self.assertIn("transcribing", payload["lifecycle"])
        self.assertEqual(payload["calls"][1]["args"]["payload"]["sessionId"], "dict-test")
        self.assertEqual(payload["calls"][2]["args"]["payload"]["audioPath"], "C:/tmp/dict-test.webm")
        self.assertEqual(payload["finals"][0]["text"], "open settings")
        self.assertEqual(payload["finals"][0]["source"], "tauri-local-stt")
        self.assertEqual(payload["stops"][0]["source"], "tauri-local-dictation")

    def test_tauri_voice_bridge_surfaces_local_stt_fallback_without_fake_transcript(self) -> None:
        payload = run_node(
            """
            import { installTauriVoiceBridge } from './web/src/fluxio/voice/tauriVoiceBridge.js';

            class FakeBlob {
              constructor(parts, options = {}) {
                this.parts = parts;
                this.type = options.type || '';
                this.size = 8;
              }
            }
            class FakeFileReader {
              readAsDataURL() {
                this.result = 'data:audio/webm;base64,ZmFrZQ==';
                this.onloadend();
              }
            }
            class FakeMediaRecorder {
              static isTypeSupported() { return true; }
              constructor() { this.mimeType = 'audio/webm'; this.state = 'inactive'; }
              start() { this.state = 'recording'; this.ondataavailable({ data: { size: 8 } }); }
              stop() { this.state = 'inactive'; this.onstop(); }
            }
            globalThis.Blob = FakeBlob;
            const errors = [];
            const finals = [];
            const root = {
              __TAURI_INTERNALS__: {},
              FileReader: FakeFileReader,
              MediaRecorder: FakeMediaRecorder,
              navigator: {
                mediaDevices: {
                  async getUserMedia() {
                    return { getTracks: () => [{ stop() {} }] };
                  },
                },
              },
            };
            const bridge = installTauriVoiceBridge(root, {
              FileReader: FakeFileReader,
              MediaRecorder: FakeMediaRecorder,
              navigator: root.navigator,
              async invoke(command) {
                if (command === 'start_dictation') return { sessionId: 'dict-fallback' };
                if (command === 'save_dictation_audio_blob') return { audioPath: 'C:/tmp/fallback.webm' };
                if (command === 'stop_dictation') {
                  return { status: 'needs_os_fallback', message: 'Local STT is not configured.' };
                }
                throw new Error(command);
              },
            });
            await bridge.startDictation({
              onError: error => errors.push(error),
              onFinal: segment => finals.push(segment),
            });
            await bridge.stopDictation();
            console.log(JSON.stringify({ errors, finals }));
            """
        )

        self.assertEqual(payload["finals"], [])
        self.assertEqual(payload["errors"][0]["code"], "local_stt_fallback")
        self.assertIn("not configured", payload["errors"][0]["message"])

    def test_image_studio_request_draft_reports_preview_and_annotation_proof(self) -> None:
        payload = run_node(
            """
            import { DEFAULT_IMAGE_PROJECT } from './web/src/fluxio/imagePlaygroundState.js';
            import {
              buildImageBreakdownWorkflow,
              buildImageStudioOperationPayload,
              buildImageStudioProofReview,
              buildImageStudioRequestDraft,
              getImageGenerationRouteStatus,
              getProviderRoute,
            } from './web/src/fluxio/image-studio/imageStudioModel.js';

            const project = {
              ...DEFAULT_IMAGE_PROJECT,
              annotationReadiness: {
                pins: [{ id: 'pin-a', x: 100, y: 120 }],
                rectangles: [{ id: 'rect-a', x: 20, y: 30, width: 200, height: 140 }],
                layers: [],
                comments: [{ id: 'comment-a', text: 'tighten crop' }],
              },
            };
            const draft = buildImageStudioRequestDraft(project, {
              routeId: 'local-request-draft',
              referenceAssets: [{ id: 'ref-a', name: 'reference.png', mime: 'image/png', size: 2000 }],
            });
            const review = buildImageStudioProofReview(project, draft, {
              referenceAssets: draft.references,
              routeId: 'local-request-draft',
            });
            const workflow = buildImageBreakdownWorkflow(project, draft, {
              referenceAssets: draft.references,
              routeId: 'local-request-draft',
            });
            const operationPayload = buildImageStudioOperationPayload(draft);
            const openAiRouteStatus = getImageGenerationRouteStatus(
              getProviderRoute('openai-gpt-image-2'),
              { openAIReady: false },
            );
            console.log(JSON.stringify({
              draftHasReview: Boolean(draft.proofReview),
              annotationTotal: review.annotations.total,
              referenceCount: review.references.count,
              hasRealArtifact: review.preview.hasRealArtifact,
              readyForProviderHandoff: review.readyForProviderHandoff,
              claim: review.noGenerationClaim,
              chromaKey: draft.chromaKey,
              payloadChromaKey: draft.payload.chromaKey,
              reviewChromaKey: review.chromaKey,
              matteChecklist: review.chromaKey.qaChecklist.map(item => [item.id, item.status]),
              matteStrength: review.chromaKey.matteStrength,
              edgeRisk: review.chromaKey.edgeRisk,
              exportStatus: review.chromaKey.exportStatus,
              workflow,
              draftWorkflow: draft.breakdownWorkflow,
              operationPayload,
              artifactIds: draft.proofArtifacts.map(item => item.id),
              openAiRouteStatus,
            }));
            """
        )

        self.assertTrue(payload["draftHasReview"])
        self.assertEqual(payload["annotationTotal"], 3)
        self.assertEqual(payload["referenceCount"], 1)
        self.assertTrue(payload["hasRealArtifact"])
        self.assertTrue(payload["readyForProviderHandoff"])
        self.assertIn("not a provider completion receipt", payload["claim"])
        self.assertIn("annotation-review", payload["artifactIds"])
        self.assertIn("chroma-key-matte", payload["artifactIds"])
        self.assertTrue(payload["chromaKey"]["ready"])
        self.assertEqual(payload["chromaKey"]["keyColor"], "#00ff66")
        self.assertEqual(payload["payloadChromaKey"]["tolerance"], 28)
        self.assertIn("spill cleanup", payload["reviewChromaKey"]["providerInstruction"])
        self.assertGreater(payload["matteStrength"], 0)
        self.assertEqual(payload["edgeRisk"], "controlled")
        self.assertIn("Transparent export plan ready", payload["exportStatus"])
        self.assertEqual(payload["workflow"]["stageCount"], 6)
        self.assertEqual(payload["draftWorkflow"]["stageCount"], 6)
        self.assertGreaterEqual(payload["workflow"]["readyCount"], 5)
        self.assertEqual(payload["workflow"]["handoffState"], "draft_handoff_ready")
        self.assertIn("Provider route", payload["workflow"]["nextAction"])
        self.assertTrue(payload["operationPayload"]["requestId"].startswith("image-request"))
        self.assertEqual(payload["operationPayload"]["providerId"], "local-request-draft")
        self.assertEqual(payload["operationPayload"]["provider"]["model"], "manual-handoff")
        self.assertEqual(payload["operationPayload"]["chromaKey"]["keyColor"], "#00ff66")
        self.assertEqual(payload["operationPayload"]["breakdownWorkflow"]["stageCount"], 6)
        self.assertIn("chroma-key-matte", [item["id"] for item in payload["operationPayload"]["proofArtifacts"]])
        self.assertEqual(
            [stage["id"] for stage in payload["workflow"]["stages"]],
            [
                "source-intake",
                "region-plan",
                "matte-quality",
                "prompt-intent",
                "review-markup",
                "provider-route",
            ],
        )
        self.assertIn("not a provider completion receipt", payload["claim"])
        self.assertIn(["comparison-artifact", "planned"], payload["matteChecklist"])
        self.assertIn(["spill-cleanup", "ready"], payload["matteChecklist"])
        self.assertEqual(payload["openAiRouteStatus"]["model"], "gpt-image-2")
        self.assertEqual(payload["openAiRouteStatus"]["localStatus"], "connector_required")
        self.assertFalse(payload["openAiRouteStatus"]["runActionAvailable"])
        self.assertIn("api/docs/models/gpt-image-2", " ".join(payload["openAiRouteStatus"]["officialSources"]))


if __name__ == "__main__":
    unittest.main()
