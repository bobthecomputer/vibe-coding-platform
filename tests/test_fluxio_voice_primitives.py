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
              parseVoiceCommand,
            } from './web/src/fluxio/voice/voiceCommandGrammar.js';

            const navigation = parseVoiceCommand('open settings', { confidence: 0.95 });
            const lowConfidence = parseVoiceCommand('send message', { confidence: 0.41 });
            const approval = parseVoiceCommand('approve request', { confidence: 0.96 });
            const unknown = parseVoiceCommand('open nebula', { confidence: 0.96 });
            const send = parseVoiceCommand('send message', { confidence: 0.96 });
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
            console.log(JSON.stringify({ navigation, lowConfidence, approval, unknown, guarded, confirmationGuard }));
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
        self.assertEqual(payload["guarded"]["status"], "review_required")
        self.assertEqual(payload["guarded"]["reason"], "transcript_quality")
        self.assertEqual(payload["confirmationGuard"]["status"], "confirmation_required")

    def test_transcript_corrections_and_ambiguity_are_visible_metadata(self) -> None:
        payload = run_node(
            """
            import {
              appendTranscriptSegment,
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
            state = replaceTranscriptSegment(state, 'phrase', {
              text: 'send message',
              reason: 'operator correction',
            });
            const after = buildTranscriptSnapshot(state);
            console.log(JSON.stringify({
              needsReviewBefore: transcriptNeedsReview({ ...state, interim: { text: 'send mess', confidence: 0.9 } }),
              ambiguousCount: before.ambiguousSegments.length,
              correctionCount: after.correctionCount,
              correctedFrom: after.segments[0].correctedFrom,
              checkIds: after.qualityChecks.map(check => check.id),
            }));
            """
        )

        self.assertTrue(payload["needsReviewBefore"])
        self.assertEqual(payload["ambiguousCount"], 1)
        self.assertEqual(payload["correctionCount"], 1)
        self.assertEqual(payload["correctedFrom"], "send massage")
        self.assertIn("ambiguity", payload["checkIds"])

    def test_accessibility_helpers_do_not_claim_live_voice_without_checked_support(self) -> None:
        payload = run_node(
            """
            import {
              buildKeyboardParityLabel,
              detectVoiceInputSupport,
              getVoiceMotionAffordance,
              getVoiceStatusCopy,
            } from './web/src/fluxio/voice/voiceAccessibility.js';

            const unsupported = detectVoiceInputSupport({ window: {} });
            const browser = detectVoiceInputSupport({ window: { SpeechRecognition: function SpeechRecognition() {} } });
            const bridge = detectVoiceInputSupport({
              window: { __FLUXIO_VOICE_BRIDGE__: { startDictation() {}, stopDictation() {} } }
            });
            console.log(JSON.stringify({
              unsupported,
              browser,
              bridge,
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
        self.assertIn("Keyboard: Ctrl+Enter", payload["label"])
        self.assertEqual(payload["reduced"]["data-motion"], "reduced")

    def test_image_studio_request_draft_reports_preview_and_annotation_proof(self) -> None:
        payload = run_node(
            """
            import { DEFAULT_IMAGE_PROJECT } from './web/src/fluxio/imagePlaygroundState.js';
            import {
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
        self.assertEqual(payload["openAiRouteStatus"]["model"], "gpt-image-2")
        self.assertEqual(payload["openAiRouteStatus"]["localStatus"], "connector_required")
        self.assertFalse(payload["openAiRouteStatus"]["runActionAvailable"])
        self.assertIn("api/docs/models/gpt-image-2", " ".join(payload["openAiRouteStatus"]["officialSources"]))


if __name__ == "__main__":
    unittest.main()
