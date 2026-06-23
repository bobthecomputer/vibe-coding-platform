from __future__ import annotations

import pathlib
import io
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent import web_backend
from grant_agent.web_backend import (
    FluxioWebBackend,
    MISSION_ACTION_TIMEOUT_SECONDS,
    MISSION_START_TIMEOUT_SECONDS,
    OpenAICodexOAuthSession,
    MiniMaxOAuthSession,
    _platform_path_for_windows_drive,
    add_or_reset_admin_user,
    make_handler,
)


class FluxioWebBackendTests(unittest.TestCase):
    def test_web_handler_uses_http_11_keep_alive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            handler = make_handler(FluxioWebBackend(root, root))

            self.assertEqual(handler.protocol_version, "HTTP/1.1")

    def test_dictation_config_command_exposes_repair_and_accessibility_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch("get_dictation_config", {})

            self.assertEqual(result["schema"], "fluxio.dictation_config.v1")
            self.assertEqual(result["primaryRuntimeLane"], "hermes")
            self.assertEqual(result["fallbackRuntimeLane"], "openclaw")
            self.assertTrue(result["reviewBeforeSend"])
            self.assertTrue(result["ambiguityGuard"])
            self.assertTrue(result["correctionBuffer"])
            self.assertTrue(result["accessibility"]["ariaLiveStatus"])
            self.assertTrue(result["accessibility"]["accidentalSendProtection"])
            self.assertIn("review the correction buffer", result["osFallbackHint"])

    def test_voice_accessibility_readiness_command_writes_mission9_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "get_voice_accessibility_readiness_command",
                {"payload": {"requestId": "mission9-proof", "surface": "agent"}},
            )

            self.assertEqual(result["schema"], "fluxio.voice_accessibility_readiness.v1")
            self.assertEqual(result["status"], "ready")
            self.assertTrue(result["voiceInput"]["accidentalSendProtection"])
            self.assertTrue(result["accessibility"]["keyboardRepairPath"])
            self.assertTrue(result["accessibility"]["reducedMotionControl"])
            self.assertEqual(result["missionGate"]["mission"], "mission9-dictation-voice-accessibility")
            self.assertEqual(result["missionGate"]["status"], "complete")
            check_ids = {item["id"] for item in result["checks"]}
            self.assertIn("review-before-send", check_ids)
            self.assertIn("keyboard-repair-path", check_ids)
            artifact_path = pathlib.Path(result["proof"]["artifactPath"])
            self.assertTrue(artifact_path.exists())
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["requestId"], "mission9-proof")
            self.assertEqual(artifact["proof"]["purpose"], "dictation_voice_accessibility_readiness")

    def test_subagent_monitoring_readiness_command_writes_mission10_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "get_subagent_monitoring_readiness_command",
                {"payload": {"requestId": "mission10-proof", "surface": "settings-team"}},
            )

            self.assertEqual(result["schema"], "fluxio.subagent_monitoring_readiness.v1")
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", result["fallbackRuntimeLanes"])
            self.assertIn("opencode", result["fallbackRuntimeLanes"])
            self.assertTrue(result["monitoringPolicy"]["nonNoisyByDefault"])
            self.assertTrue(result["mergePolicy"]["requiresProofArtifact"])
            role_ids = {item["id"] for item in result["roles"]}
            self.assertIn("researcher", role_ids)
            self.assertIn("executor", role_ids)
            self.assertIn("verifier", role_ids)
            self.assertIn("ui-reviewer", role_ids)
            control_ids = {item["id"] for item in result["controls"]}
            self.assertIn("spawn-role", control_ids)
            self.assertIn("cancel-subagent", control_ids)
            self.assertIn("merge-proof", control_ids)
            check_ids = {item["id"] for item in result["checks"]}
            self.assertIn("role-assignment", check_ids)
            self.assertIn("monitor-activation", check_ids)
            self.assertIn("cancel-path", check_ids)
            self.assertIn("proof-merge", check_ids)
            self.assertIn("drift-intervention", check_ids)
            self.assertEqual(result["missionGate"]["mission"], "mission10-subagents-monitoring-ux")
            self.assertEqual(result["missionGate"]["status"], "complete")
            artifact_path = pathlib.Path(result["proof"]["artifactPath"])
            self.assertTrue(artifact_path.exists())
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["requestId"], "mission10-proof")
            self.assertEqual(artifact["proof"]["purpose"], "subagents_monitoring_ux_readiness")

    def test_image_playground_operation_writes_served_artifact_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            png_bytes = (
                b"\x89PNG\r\n\x1a\n"
                b"\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
                b"\x1f\x15\xc4\x89"
                b"\x00\x00\x00\x0cIDATx\x9cc``\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\xd9\x8b\x8d"
                b"\x00\x00\x00\x00IEND\xaeB`\x82"
            )

            def fake_run_process_capture(args, *, cwd, timeout=180, extra_env=None):
                self.assertIn("openclaw", args[0])
                self.assertIn("image", args)
                self.assertIn("generate", args)
                self.assertIn("openai/gpt-image-2", args)
                output_path = pathlib.Path(args[args.index("--output") + 1])
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(png_bytes)
                payload = {
                    "ok": True,
                    "provider": "openai-codex",
                    "model": "gpt-image-2",
                    "attempts": [{"provider": "openai-codex", "model": "gpt-image-2"}],
                    "outputs": [{"path": str(output_path), "mimeType": "image/png", "size": len(png_bytes)}],
                }
                return payload, json.dumps(payload), "", 120

            with mock.patch(
                "grant_agent.web_backend._openai_codex_oauth_status",
                return_value={"authenticated": True, "source": "openclaw-auth-profile"},
            ):
                with mock.patch("grant_agent.web_backend.shutil.which", return_value="openclaw"):
                    with mock.patch("grant_agent.web_backend._run_process_capture", side_effect=fake_run_process_capture):
                        result = backend.dispatch(
                            "image_playground_operation_command",
                            {
                                "requestId": "imgreq-test",
                                "operation": "generate",
                                "providerId": "codex_subscription_gpt_image2",
                                "canvas": {"width": 320, "height": 240},
                                "prompt": {"text": "served artifact"},
                            },
                        )

            image_path = pathlib.Path(result["outputArtifactPath"])
            manifest_path = pathlib.Path(result["manifestPath"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(image_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertIn("/api/artifact?id=", result["previewUrl"])
            self.assertEqual(result["layer"]["src"], result["previewUrl"])
            self.assertEqual(result["provider"], "openai-codex")
            self.assertEqual(result["model"], "gpt-image-2")
            self.assertEqual(result["billingNote"], "codex subscription")
            self.assertEqual(manifest["provider"], "openai-codex")
            self.assertEqual(manifest["model"], "gpt-image-2")
            self.assertEqual(manifest["billingNote"], "codex subscription")
            self.assertEqual(manifest["route"], "codex_subscription")
            artifact_id = result["previewUrl"].split("id=", 1)[1]
            self.assertEqual(backend._resolve_artifact_id(artifact_id), image_path)
            self.assertEqual(backend._resolve_artifact_path(str(image_path)), image_path)

    def test_backend_serves_mission_artifacts_from_sibling_project_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            projects = pathlib.Path(temp_dir) / "projects"
            active_release = projects / "syntelos" / "releases" / "current"
            mission_artifacts = projects / "overnight-discovery-lab" / ".agent_control" / "mission_artifacts"
            active_release.mkdir(parents=True)
            mission_artifacts.mkdir(parents=True)
            report = mission_artifacts / "f1-telemetry-report.md"
            report.write_text("# F1 telemetry report\n\nRuntime output body.\n", encoding="utf-8")
            backend = FluxioWebBackend(active_release, active_release)

            self.assertEqual(backend._resolve_artifact_path(str(report)), report.resolve())
            artifact_id = backend._artifact_id(report)
            self.assertEqual(backend._resolve_artifact_id(artifact_id), report.resolve())

    def test_backend_serves_html_mission_dashboard_from_active_release_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            active_release = pathlib.Path(temp_dir) / "syntelos" / "releases" / "current"
            mission_artifacts = active_release / ".agent_control" / "mission_artifacts" / "mission_f1"
            mission_artifacts.mkdir(parents=True)
            dashboard = mission_artifacts / "index.html"
            dashboard.write_text(
                "<!doctype html><main>F1 telemetry analytics dashboard</main>\n",
                encoding="utf-8",
            )
            backend = FluxioWebBackend(active_release, active_release)

            self.assertEqual(backend._resolve_artifact_path(str(dashboard)), dashboard.resolve())
            artifact_id = backend._artifact_id(dashboard)
            self.assertEqual(backend._resolve_artifact_id(artifact_id), dashboard.resolve())
            self.assertIn(".html", web_backend.ARTIFACT_CONTENT_TYPES)

    def test_image_playground_accepts_openai_json_when_stderr_proves_codex_oauth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            png_bytes = (
                b"\x89PNG\r\n\x1a\n"
                b"\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
                b"\x1f\x15\xc4\x89"
                b"\x00\x00\x00\x0cIDATx\x9cc``\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\xd9\x8b\x8d"
                b"\x00\x00\x00\x00IEND\xaeB`\x82"
            )

            def fake_run_process_capture(args, *, cwd, timeout=180, extra_env=None):
                output_path = pathlib.Path(args[args.index("--output") + 1])
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(png_bytes)
                payload = {
                    "ok": True,
                    "provider": "openai",
                    "model": "gpt-image-2",
                    "outputs": [{"path": str(output_path), "mimeType": "image/png", "size": len(png_bytes)}],
                }
                stderr = (
                    "[image-generation/openai] image auth selected: "
                    "provider=openai-codex mode=oauth transport=codex-responses "
                    "requestedModel=gpt-image-2 responsesModel=gpt-5.5 timeoutMs=300000"
                )
                return payload, json.dumps(payload), stderr, 120

            with mock.patch(
                "grant_agent.web_backend._openai_codex_oauth_status",
                return_value={"authenticated": True, "source": "openclaw-auth-profile"},
            ):
                with mock.patch("grant_agent.web_backend.shutil.which", return_value="openclaw"):
                    with mock.patch("grant_agent.web_backend._run_process_capture", side_effect=fake_run_process_capture):
                        result = backend.dispatch(
                            "image_playground_operation_command",
                            {
                                "requestId": "imgreq-openai-json-codex-oauth",
                                "operation": "generate",
                                "providerId": "codex_subscription_gpt_image2",
                                "canvas": {"width": 320, "height": 240},
                                "prompt": {"text": "served artifact"},
                            },
                        )

            manifest = json.loads(pathlib.Path(result["manifestPath"]).read_text(encoding="utf-8"))
            self.assertEqual(result["providerStatus"], "available")
            self.assertEqual(result["provider"], "openai-codex")
            self.assertEqual(manifest["provenance"]["routeEvidence"]["rawProvider"], "openai")
            self.assertEqual(manifest["provenance"]["routeEvidence"]["authProvider"], "openai-codex")
            self.assertEqual(manifest["provenance"]["routeEvidence"]["authMode"], "oauth")
            self.assertEqual(manifest["provenance"]["routeEvidence"]["transport"], "codex-responses")

    def test_image_playground_codex_subscription_reports_blocked_when_openclaw_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch(
                "grant_agent.web_backend._openai_codex_oauth_status",
                return_value={"authenticated": True, "source": "openclaw-auth-profile"},
            ):
                with mock.patch("grant_agent.web_backend.shutil.which", return_value=None):
                    result = backend.dispatch(
                        "image_playground_operation_command",
                        {
                            "requestId": "imgreq-blocked",
                            "providerId": "codex_subscription_gpt_image2",
                            "operation": "generate",
                            "canvas": {"width": 640, "height": 512},
                            "prompt": {"text": "coastal retreat at sunset, cinematic architecture"},
                        },
                    )

            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(result["providerStatus"], "blocked")
            self.assertEqual(result["blockedReason"], "openclaw_missing")
            self.assertEqual(result["billingNote"], "codex subscription")

    def test_chat_route_preserves_openrouter_glm_nested_model_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            route = backend._chat_route({"route": {"provider": "openrouter", "model": "z-ai/glm-5.2"}})

            self.assertEqual(route["provider"], "openrouter")
            self.assertEqual(route["model"], "z-ai/glm-5.2")
            self.assertEqual(route["model_id"], "openrouter/z-ai/glm-5.2")

    def test_image_self_repair_loop_writes_skill_artifacts_and_prefers_hermes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            def fake_which(command, path=None):
                if command in {"opencode", "hermes", "openclaw"}:
                    return command
                return None

            def fake_run_process_capture(args, *, cwd, timeout=180, extra_env=None):
                executable = pathlib.Path(str(args[0])).name.lower()
                if executable == "opencode":
                    return {}, "openrouter/z-ai/glm-5.2\nopenrouter/z-ai/glm-4.6\n", "", 80
                if executable == "hermes":
                    raise RuntimeError("Hermes route timed out during proof capture.")
                if executable == "openclaw":
                    payload = {"reply": "{\"findings\":[\"legacy Images surface\"]}"}
                    return payload, json.dumps(payload), "", 120
                raise AssertionError(f"Unexpected command: {args}")

            with mock.patch("grant_agent.web_backend.shutil.which", side_effect=fake_which):
                with mock.patch("grant_agent.web_backend._run_process_capture", side_effect=fake_run_process_capture):
                    result = backend.dispatch(
                        "image_self_repair_loop_command",
                        {
                            "requestId": "mission1-proof",
                            "galleryCount": 2,
                            "layerCount": 3,
                            "annotationCount": 1,
                            "timeoutSeconds": 5,
                            "probeExternalRoutes": True,
                            "probeProviderModels": True,
                            "allowProviderCliProbe": True,
                            "allowOpenClawInferProbe": True,
                        },
                    )

            self.assertEqual(result["route"]["runtime"], "hermes")
            self.assertEqual(result["route"]["fallbackRuntime"], "openclaw")
            self.assertEqual(result["route"]["modelId"], "openrouter/z-ai/glm-5.2")
            self.assertEqual(result["routeStatus"], "ok")
            skill_ids = [item["id"] for item in result["skillsUsed"]]
            self.assertIn("image_vision_breakdown", skill_ids)
            self.assertIn("ui_self_repair_planner", skill_ids)
            self.assertIn("self_repair_verifier", skill_ids)

            route_proof = json.loads(pathlib.Path(result["artifacts"]["routeProofPath"]).read_text(encoding="utf-8"))
            self.assertTrue(route_proof["opencode"]["modelsContainGlm52"])
            self.assertEqual(route_proof["hermes"]["call"]["status"], "failed")
            self.assertEqual(route_proof["openclaw"]["call"]["status"], "ok")
            self.assertEqual(route_proof["selectedRuntime"], "openclaw")
            self.assertEqual(route_proof["missionGate"]["schema"], "fluxio.mission_completion_gate.v1")
            self.assertEqual(result["missionGate"]["status"], "incomplete")
            self.assertEqual(result["missionGate"]["nextMissing"]["id"], "preview-state-attached")
            mission_gate = json.loads(pathlib.Path(result["artifacts"]["missionGatePath"]).read_text(encoding="utf-8"))
            self.assertEqual(mission_gate["mission"], "mission1-image-playground")
            self.assertIn("Mission 1 still has open acceptance items", result["message"])
            for artifact_path in result["artifacts"].values():
                self.assertTrue(pathlib.Path(artifact_path).exists(), artifact_path)

    def test_image_playground_handoff_receipt_updates_mission_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            handoff = backend.dispatch(
                "image_playground_handoff_command",
                {
                    "requestId": "handoff-proof",
                    "target": "agent",
                    "artifactTitle": "ImageGen cyberpunk gallery artifact",
                    "artifactUrl": "/api/artifact/image.png",
                    "manifestUrl": "/api/artifact/image.manifest.json",
                },
            )
            self.assertEqual(handoff["status"], "recorded")
            self.assertTrue(pathlib.Path(handoff["receiptPath"]).exists())
            self.assertEqual(handoff["receipt"]["schema"], "fluxio.image_playground_handoff_receipt.v1")

            with mock.patch("grant_agent.web_backend.shutil.which", return_value=None):
                result = backend.dispatch(
                    "image_self_repair_loop_command",
                    {
                        "requestId": "mission1-gate-handoff-proof",
                        "screenshotPath": "artifacts/images-desktop.png",
                        "domFacts": {"surface": "images"},
                    },
                )

            gate_items = {item["id"]: item for item in result["missionGate"]["items"]}
            self.assertEqual(gate_items["handoff-proof"]["status"], "done")
            self.assertEqual(gate_items["handoff-proof"]["proof"], handoff["receiptPath"])
            self.assertEqual(result["missionGate"]["status"], "incomplete")

    def test_image_self_repair_loop_uses_opencode_glm_when_openclaw_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            backend.dispatch(
                "image_playground_handoff_command",
                {
                    "requestId": "handoff-proof",
                    "target": "agent",
                    "artifactTitle": "ImageGen cyberpunk gallery artifact",
                    "artifactUrl": "/api/artifact/image.png",
                },
            )

            def fake_which(command, path=None):
                if command in {"opencode", "openclaw"}:
                    return command
                return None

            def fake_run_process_capture(args, *, cwd, timeout=180, extra_env=None):
                executable = pathlib.Path(str(args[0])).name.lower()
                if executable == "opencode" and "models" in args:
                    return {}, "openrouter/z-ai/glm-5.2\n", "", 80
                if executable == "openclaw":
                    raise RuntimeError("OpenClaw route timed out during proof capture.")
                if executable == "opencode" and "run" in args:
                    payload = {"type": "text", "part": {"text": "{\"ok\":true,\"route\":\"opencode-glm\"}"}}
                    return payload, json.dumps(payload), "", 140
                raise AssertionError(f"Unexpected command: {args}")

            with mock.patch("grant_agent.web_backend.shutil.which", side_effect=fake_which):
                with mock.patch("grant_agent.web_backend._run_process_capture", side_effect=fake_run_process_capture):
                    result = backend.dispatch(
                        "image_self_repair_loop_command",
                        {
                            "requestId": "mission1-opencode-proof",
                            "screenshotPath": "artifacts/images-desktop.png",
                            "domFacts": {"surface": "images"},
                            "probeExternalRoutes": True,
                            "probeProviderModels": True,
                            "allowProviderCliProbe": True,
                            "timeoutSeconds": 5,
                        },
                    )

            self.assertEqual(result["routeStatus"], "ok")
            self.assertEqual(result["missionGate"]["status"], "complete")
            self.assertTrue(result["usedModelReply"])
            route_proof = json.loads(pathlib.Path(result["artifacts"]["routeProofPath"]).read_text(encoding="utf-8"))
            self.assertEqual(route_proof["selectedRuntime"], "opencode")
            self.assertEqual(route_proof["opencode"]["call"]["status"], "ok")
            self.assertEqual(route_proof["openclaw"]["call"]["status"], "not_attempted")
            self.assertIn("OpenClaw inference probe was skipped", route_proof["openclaw"]["call"]["error"])
            self.assertIn("opencode run", route_proof["opencode"]["call"]["command"])

    def test_ui_self_repair_loop_writes_builder_skill_artifacts_and_prefers_hermes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            def fake_which(command, path=None):
                if command in {"opencode", "hermes", "openclaw"}:
                    return command
                return None

            def fake_run_process_capture(args, *, cwd, timeout=180, extra_env=None):
                executable = pathlib.Path(str(args[0])).name.lower()
                if executable == "opencode":
                    return {}, "openrouter/z-ai/glm-5.2\nopenrouter/z-ai/glm-4.6\n", "", 80
                if executable == "hermes":
                    payload = {"reply": "{\"findings\":[\"builder proof clutter\"]}"}
                    return payload, json.dumps(payload), "", 110
                raise AssertionError(f"Unexpected command: {args}")

            with mock.patch("grant_agent.web_backend.shutil.which", side_effect=fake_which):
                with mock.patch("grant_agent.web_backend._run_process_capture", side_effect=fake_run_process_capture):
                    result = backend.dispatch(
                        "ui_self_repair_loop_command",
                        {
                            "requestId": "mission8-broader-ui-proof",
                            "surface": "core-surfaces",
                            "surfaces": ["builder", "agent", "runtime", "skills", "images", "preview"],
                            "clarityMode": "focus",
                            "missionCount": 3,
                            "timeoutSeconds": 5,
                            "probeExternalRoutes": True,
                        },
                    )

            self.assertEqual(result["route"]["runtime"], "hermes")
            self.assertEqual(result["route"]["fallbackRuntime"], "openclaw")
            self.assertEqual(result["route"]["modelId"], "openrouter/z-ai/glm-5.2")
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["routeStatus"], "ok")
            self.assertEqual(result["missionGate"]["schema"], "fluxio.broader_ui_self_repair_gate.v1")
            self.assertEqual(result["missionGate"]["missionId"], "mission8-broader-ui-self-repair")
            self.assertEqual(result["missionGate"]["status"], "complete")
            self.assertEqual(result["surfaceAudit"]["schema"], "fluxio.broader_ui_surface_audit.v1")
            self.assertEqual(result["surfaceAudit"]["targetSurfaces"], ["builder", "agent", "runtime", "skills", "images", "preview"])
            skill_ids = [item["id"] for item in result["skillsUsed"]]
            self.assertIn("broader_ui_surface_audit", skill_ids)
            self.assertIn("operator_ui_breakdown", skill_ids)
            self.assertIn("operator_ui_repair_planner", skill_ids)
            self.assertIn("implementation_surface_contract", skill_ids)
            self.assertIn("self_repair_verifier", skill_ids)

            route_proof = json.loads(pathlib.Path(result["artifacts"]["routeProofPath"]).read_text(encoding="utf-8"))
            self.assertTrue(route_proof["opencode"]["modelsContainGlm52"])
            self.assertEqual(route_proof["hermes"]["call"]["status"], "ok")
            self.assertEqual(route_proof["selectedRuntime"], "hermes")
            contract = json.loads(pathlib.Path(result["artifacts"]["implementationContractPath"]).read_text(encoding="utf-8"))
            self.assertIn('data-builder-current-mission="true"', contract["surfaceMarkers"])
            self.assertIn('data-ui-self-repair-canvas="mission8"', contract["surfaceMarkers"])
            self.assertIn('data-broader-ui-self-repair-receipt="true"', contract["surfaceMarkers"])
            for artifact_path in result["artifacts"].values():
                self.assertTrue(pathlib.Path(artifact_path).exists(), artifact_path)

    def test_artifact_resolver_maps_nas_absolute_path_to_local_volume_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            mirrored = root / ".agent_control" / "design_references" / "codex_image_artifacts"
            mirrored.mkdir(parents=True)
            artifact = mirrored / "nas-reference.png"
            artifact.write_bytes(b"png")
            backend = FluxioWebBackend(root, root)

            resolved = backend._resolve_artifact_path(
                "/volume1/Saclay/projects/vibe-coding-platform/.agent_control/design_references/codex_image_artifacts/nas-reference.png"
            )

            self.assertEqual(resolved, artifact)

    def test_artifact_resolver_rejects_general_workspace_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            readme = root / "README.md"
            readme.write_text("# private workspace note\n", encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            with self.assertRaises(RuntimeError):
                backend._resolve_artifact_path(str(readme))

    def test_artifact_resolver_serves_runtime_evidence_files_only_from_control_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            events_dir = root / ".agent_control" / "runtime_sessions"
            events_dir.mkdir(parents=True)
            events = events_dir / "delegate.events.jsonl"
            events.write_text('{"kind":"runtime.output"}\n', encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            self.assertEqual(backend._resolve_artifact_path(str(events)), events)
            self.assertEqual(backend._resolve_artifact_id(backend._artifact_id(events)), events)

    def test_artifact_resolver_recovers_embedded_windows_runtime_evidence_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            events_dir = root / ".agent_control" / "runtime_sessions"
            events_dir.mkdir(parents=True)
            events = events_dir / "delegate.events.jsonl"
            events.write_text('{"kind":"runtime.output"}\n', encoding="utf-8")
            backend = FluxioWebBackend(root, root)
            if not events.drive:
                self.skipTest("Embedded Windows-path recovery is Windows-specific.")
            malformed_path = f"/mnt/c/Users/paul/Projects/demo/{events}"

            self.assertEqual(backend._resolve_artifact_path(malformed_path), events)

    def test_windows_drive_path_translates_for_wsl_artifact_serving(self) -> None:
        with mock.patch("grant_agent.web_backend.os.name", "posix"):
            self.assertEqual(
                str(_platform_path_for_windows_drive(r"C:\volume1\Saclay\artifact.jsonl")),
                "/mnt/c/volume1/Saclay/artifact.jsonl",
            )

    def test_chat_compartment_records_messages_and_runtime_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            backend = FluxioWebBackend(root, root)

            compartment = backend._save_chat_compartment(
                {
                    "sessionId": "chat-live",
                    "message": "What changed?",
                    "runtime": "codex",
                    "missionId": "mission_live",
                    "workspacePath": str(workspace),
                    "route": {
                        "role": "executor",
                        "provider": "openai-codex",
                        "model": "gpt-5.5",
                        "effort": "medium",
                    },
                },
                {
                    "sessionId": "chat-live",
                    "reply": "The runtime wrote a proof receipt.",
                    "runtime": "codex",
                    "elapsedMs": 842,
                    "filesChanged": ["web/src/fluxio/FluxioShell.jsx"],
                    "toolTimeline": [
                        {
                            "kind": "command.execution",
                            "at": "2026-05-13T10:00:00Z",
                            "summary": "npm run frontend:build",
                            "status": "completed",
                        }
                    ],
                    "route": {
                        "role": "executor",
                        "provider": "openai-codex",
                        "model": "gpt-5.5",
                        "effort": "medium",
                    },
                },
            )

            self.assertEqual(compartment["cwd"], str(workspace))
            self.assertEqual(compartment["missionId"], "mission_live")
            self.assertGreaterEqual(len(compartment["messages"]), 2)
            self.assertEqual(compartment["messages"][-2]["source"], "operator-submitted")
            self.assertEqual(compartment["messages"][-1]["source"], "backend-model-message")
            self.assertEqual([lane["role"] for lane in compartment["lanes"]], ["planner", "executor", "verifier"])
            self.assertTrue(next(lane for lane in compartment["lanes"] if lane["role"] == "executor")["active"])
            self.assertIn("resume-chat", compartment["actions"])
            self.assertEqual(compartment["lastRoundtripMs"], 842)
            self.assertIn("web/src/fluxio/FluxioShell.jsx", compartment["filesChanged"])
            self.assertEqual(compartment["turnReceipt"]["schema"], "fluxio.turn_receipt.v1")
            self.assertEqual(compartment["turnReceipt"]["runtime"], "codex")
            self.assertEqual(compartment["turnReceipt"]["provider"], "openai-codex")
            self.assertEqual(compartment["turnReceipt"]["model"], "gpt-5.5")
            self.assertEqual(compartment["turnReceipt"]["effort"], "medium")
            self.assertEqual(compartment["turnReceipt"]["assistantMessage"], "The runtime wrote a proof receipt.")
            self.assertEqual(compartment["turnReceipt"]["finalMessage"], "The runtime wrote a proof receipt.")
            self.assertIn("web/src/fluxio/FluxioShell.jsx", compartment["turnReceipt"]["changedFiles"])
            self.assertIn("turnReceipts", compartment)
            timeline_kinds = [event.get("kind") for event in compartment["toolTimeline"] if isinstance(event, dict)]
            self.assertIn("runtime.roundtrip", timeline_kinds)
            self.assertIn("runtime.model_message", timeline_kinds)

    def test_chat_compartment_records_executable_comment_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            compartment = backend._save_chat_compartment(
                {
                    "sessionId": "comment-run",
                    "message": "Please apply this fix.",
                    "runtime": "hermes",
                    "sourceType": "comment",
                    "sourceMessageId": "turn-123",
                    "sourceZone": "thread",
                    "commentText": "Please apply this fix.",
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
                {
                    "sessionId": "comment-run",
                    "reply": "Done.",
                    "runtime": "hermes",
                    "command": "hermes chat -q <prompt> -Q --model MiniMax-M3",
                    "filesChanged": [],
                    "toolTimeline": [],
                    "elapsedMs": 120,
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
            )

            receipt = compartment["turnReceipt"]
            self.assertEqual(receipt["sourceType"], "comment")
            self.assertEqual(receipt["sourceMessageId"], "turn-123")
            self.assertEqual(receipt["sourceZone"], "thread")
            self.assertEqual(receipt["commentText"], "Please apply this fix.")
            self.assertEqual(receipt["command"], "hermes chat -q <prompt> -Q --model MiniMax-M3")
            self.assertEqual(receipt["changedFiles"], [])
            self.assertEqual(receipt["assistantMessage"], "Done.")

    def test_chat_turn_receipt_does_not_treat_command_message_as_agent_reply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            compartment = backend._save_chat_compartment(
                {
                    "sessionId": "command-only",
                    "message": "Run this.",
                    "runtime": "hermes",
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
                {
                    "sessionId": "command-only",
                    "message": "/volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    "runtime": "hermes",
                    "command": "/volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    "result_summary": "Delegated runtime lane launched.",
                    "filesChanged": [],
                    "toolTimeline": [],
                    "elapsedMs": 80,
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
            )

            receipt = compartment["turnReceipt"]
            self.assertEqual(receipt["assistantMessage"], "")
            self.assertEqual(receipt["finalMessage"], "")
            self.assertEqual(receipt["runSummary"], "Delegated runtime lane launched.")
            self.assertIn("ms-one-shot", receipt["command"])
            self.assertEqual([item["role"] for item in compartment["messages"]], ["operator"])
            timeline_kinds = [event.get("kind") for event in compartment["toolTimeline"] if isinstance(event, dict)]
            self.assertIn("runtime.trace_only_reply", timeline_kinds)

    def test_chat_turn_receipt_does_not_treat_command_prefixed_reply_as_agent_reply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            compartment = backend._save_chat_compartment(
                {
                    "sessionId": "command-prefix-only",
                    "message": "Run this.",
                    "runtime": "hermes",
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
                {
                    "sessionId": "command-prefix-only",
                    "reply": "Command: /volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    "runtime": "hermes",
                    "command": "/volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    "result_summary": "Delegated runtime lane launched.",
                    "filesChanged": [],
                    "toolTimeline": [],
                    "elapsedMs": 80,
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
            )

            receipt = compartment["turnReceipt"]
            self.assertEqual(receipt["assistantMessage"], "")
            self.assertEqual(receipt["finalMessage"], "")
            self.assertEqual(receipt["runSummary"], "Delegated runtime lane launched.")
            self.assertEqual([item["role"] for item in compartment["messages"]], ["operator"])
            timeline_kinds = [event.get("kind") for event in compartment["toolTimeline"] if isinstance(event, dict)]
            self.assertIn("runtime.trace_only_reply", timeline_kinds)

    def test_chat_turn_receipt_does_not_treat_command_word_without_colon_as_agent_reply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            compartment = backend._save_chat_compartment(
                {
                    "sessionId": "command-word-only",
                    "message": "Run this.",
                    "runtime": "hermes",
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
                {
                    "sessionId": "command-word-only",
                    "reply": "Command /volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    "runtime": "hermes",
                    "command": "/volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    "result_summary": "Delegated runtime lane launched.",
                    "filesChanged": [],
                    "toolTimeline": [],
                    "elapsedMs": 80,
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
            )

            receipt = compartment["turnReceipt"]
            self.assertEqual(receipt["assistantMessage"], "")
            self.assertEqual(receipt["finalMessage"], "")
            self.assertEqual([item["role"] for item in compartment["messages"]], ["operator"])
            timeline_kinds = [event.get("kind") for event in compartment["toolTimeline"] if isinstance(event, dict)]
            self.assertIn("runtime.trace_only_reply", timeline_kinds)

    def test_chat_turn_receipt_prefers_open_runtime_model_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            compartment = backend._save_chat_compartment(
                {
                    "sessionId": "open-runtime-message",
                    "message": "Show the real runtime answer.",
                    "runtime": "hermes",
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
                {
                    "sessionId": "open-runtime-message",
                    "openRuntimeMessage": "I changed the receipt so the model answer is visible first.",
                    "reply": "/volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    "runtime": "hermes",
                    "command": "/volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    "modelMessageSource": "runtime_transcript",
                    "modelMessageSourceLabel": "Runtime output artifact",
                    "modelMessageSourceTitle": "What changed in this resume",
                    "transcriptSessionId": "runtime_artifact",
                    "filesChanged": [],
                    "toolTimeline": [],
                    "elapsedMs": 80,
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
            )

            receipt = compartment["turnReceipt"]
            self.assertEqual(receipt["assistantMessage"], "I changed the receipt so the model answer is visible first.")
            self.assertEqual(receipt["finalMessage"], "I changed the receipt so the model answer is visible first.")
            self.assertEqual(compartment["messages"][-1]["source"], "backend-model-message")
            self.assertEqual(compartment["messages"][-1]["text"], "I changed the receipt so the model answer is visible first.")
            self.assertEqual(receipt["modelMessageSource"], "runtime_transcript")
            self.assertEqual(receipt["modelMessageSourceLabel"], "Runtime output artifact")
            self.assertEqual(receipt["modelMessageSourceTitle"], "What changed in this resume")
            self.assertEqual(receipt["transcriptSessionId"], "runtime_artifact")

    def test_chat_turn_receipt_humanizes_runtime_artifact_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            compartment = backend._save_chat_compartment(
                {
                    "sessionId": "artifact-shaped-message",
                    "message": "Show the real runtime answer.",
                    "runtime": "hermes",
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
                {
                    "sessionId": "artifact-shaped-message",
                    "openRuntimeMessage": (
                        "Ringway F1 compact telemetry board - mission_123\n"
                        "Artifact: /volume1/Saclay/projects/syntelos/current/.agent_control/artifacts/index.html\n"
                        "Preview URL: /api/artifact?path=/volume1/Saclay/projects/syntelos/current/.agent_control/artifacts/index.html\n"
                        "Route: Hermes harness; executor route preserved as minimax/MiniMax-M3.\n"
                        "Fastest lap: ARO L3 83.140s.\n"
                        "Sector comparison: S1 ARO 28.36s; S2 ARO 32.88s; S3 ARO 21.90s."
                    ),
                    "runtime": "hermes",
                    "command": "/volume1/Saclay/projects/syntelos/runtime/bin/hermes chat -q <prompt>",
                    "filesChanged": [],
                    "toolTimeline": [],
                    "elapsedMs": 80,
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
            )

            receipt = compartment["turnReceipt"]
            self.assertIn("OpenRuntime returned a real result", receipt["assistantMessage"])
            self.assertIn("Fastest lap", receipt["assistantMessage"])
            self.assertNotIn("/volume1/Saclay", receipt["assistantMessage"])
            self.assertNotIn("/api/artifact", receipt["assistantMessage"])
            self.assertEqual(compartment["messages"][-1]["text"], receipt["assistantMessage"])

    def test_chat_turn_receipt_skips_command_before_open_runtime_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            compartment = backend._save_chat_compartment(
                {
                    "sessionId": "command-then-open-runtime",
                    "message": "Show the real runtime answer.",
                    "runtime": "hermes",
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
                {
                    "sessionId": "command-then-open-runtime",
                    "turnReceipt": {
                        "assistantMessage": "/volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    },
                    "openRuntimeMessage": "Implemented and verified the receipt fix. The model answer is now first.",
                    "reply": "/volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    "runtime": "hermes",
                    "command": "/volume1/Saclay/projects/system-loss/bin/ms-one-shot execute model mission",
                    "filesChanged": [],
                    "toolTimeline": [],
                    "elapsedMs": 80,
                    "route": {"provider": "minimax-oauth", "model": "MiniMax-M3", "effort": "high"},
                },
            )

            receipt = compartment["turnReceipt"]
            self.assertEqual(
                receipt["assistantMessage"],
                "Implemented and verified the receipt fix. The model answer is now first.",
            )
            self.assertEqual(
                receipt["finalMessage"],
                "Implemented and verified the receipt fix. The model answer is now first.",
            )
            self.assertEqual(compartment["messages"][-1]["source"], "backend-model-message")
            self.assertEqual(
                compartment["messages"][-1]["text"],
                "Implemented and verified the receipt fix. The model answer is now first.",
            )

    def test_nas_deploy_readiness_command_returns_offline_safe_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            readiness = backend.dispatch("get_nas_deploy_readiness_command", {})

            self.assertIn("ready", readiness)
            self.assertIn("checks", readiness)
            check_ids = {item["checkId"] for item in readiness["checks"]}
            self.assertIn("web_backend_script", check_ids)
            self.assertIn("nas_setup_script", check_ids)
            self.assertIn("doctor_script", check_ids)
            self.assertIn("setupHealth", readiness)
            self.assertIn("source", readiness)

    def test_integration_readiness_command_returns_evidence_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            readiness = backend.dispatch("get_integration_readiness_command", {})

            self.assertEqual(readiness["schema"], "fluxio.integration_readiness.v1")
            self.assertIn("score", readiness)
            self.assertIn("maxScore", readiness)
            self.assertIn("percent", readiness)
            self.assertIn("categories", readiness)
            self.assertIn("blockers", readiness)
            self.assertLess(readiness["percent"], 100)
            category_ids = {item["id"] for item in readiness["categories"]}
            self.assertIn("provider_routes", category_ids)
            self.assertIn("authenticated_phone_agent", category_ids)

    def test_provider_secret_presence_uses_session_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "",
                    "ANTHROPIC_API_KEY": "",
                    "OPENROUTER_API_KEY": "",
                    "MINIMAX_API_KEY": "",
                    "MINIMAX_OAUTH_TOKEN": "",
                    "OPENCODE_API_KEY": "",
                    "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT": "",
                    "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT": "",
                    "HOME": str(root / "home"),
                    "OPENCLAW_STATE_DIR": str(root / "home" / ".openclaw"),
                },
            ):
                before = backend.dispatch(
                    "get_provider_secret_presence_command",
                    {"providerIds": ["openai", "openai-codex", "minimax"]},
                )
                self.assertFalse(before["openai"])

                self.assertTrue(
                    backend.dispatch(
                        "save_provider_secret_command",
                        {"providerId": "openai", "secret": "test-key"},
                    )
                )
                after = backend.dispatch(
                    "get_provider_secret_presence_command",
                    {"providerIds": ["openai", "openai-codex", "minimax", "opencode-go"]},
                )
                self.assertTrue(after["openai"])
                self.assertTrue(after["openai-codex"])
                self.assertFalse(after["minimax"])
                self.assertFalse(after["opencode-go"])

                self.assertTrue(
                    backend.dispatch(
                        "save_provider_secret_command",
                        {"providerId": "minimax", "secret": "test-minimax-key"},
                    )
                )
                runtime_env = root / "home" / ".fluxio_provider_env"
                self.assertTrue(runtime_env.is_file())
                self.assertIn("MINIMAX_API_KEY=", runtime_env.read_text(encoding="utf-8"))

                self.assertTrue(
                    backend.dispatch(
                        "save_provider_secret_command",
                        {"providerId": "opencode-go", "secret": "test-opencodego-key"},
                    )
                )
                runtime_text = runtime_env.read_text(encoding="utf-8")
                self.assertIn("OPENCODE_API_KEY=", runtime_text)

                restarted_backend = FluxioWebBackend(root, root)
                persisted = restarted_backend.dispatch(
                    "get_provider_secret_presence_command",
                    {"providerIds": ["openai", "openai-codex", "minimax", "opencode-go"]},
                )
                self.assertTrue(persisted["openai"])
                self.assertTrue(persisted["openai-codex"])
                self.assertTrue(persisted["minimax"])
                self.assertTrue(persisted["opencode-go"])

                self.assertTrue(
                    backend.dispatch("clear_provider_secret_command", {"providerId": "openai"})
                )
                cleared = backend.dispatch(
                    "get_provider_secret_presence_command",
                    {"providerIds": ["openai"]},
                )
                self.assertFalse(cleared["openai"])

    def test_provider_orchestration_command_writes_model_switching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            def fake_which(command, path=None):  # noqa: ANN001
                if command in {"hermes", "openclaw", "opencode"}:
                    return command
                return None

            with mock.patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "",
                    "ANTHROPIC_API_KEY": "",
                    "OPENROUTER_API_KEY": "",
                    "MINIMAX_API_KEY": "",
                    "MINIMAX_OAUTH_TOKEN": "",
                    "OPENCODE_API_KEY": "",
                    "HOME": str(root / "home"),
                    "OPENCLAW_STATE_DIR": str(root / "home" / ".openclaw"),
                },
            ), mock.patch("shutil.which", side_effect=fake_which):
                self.assertTrue(
                    backend.dispatch(
                        "save_provider_secret_command",
                        {"providerId": "openrouter", "secret": "test-openrouter-key"},
                    )
                )
                contract = backend.dispatch(
                    "get_provider_orchestration_command",
                    {
                        "root": str(root),
                        "requestId": "mission6-provider-route",
                        "taskBrief": "Use GLM-5.2 vision route for screenshot UI review and annotation.",
                        "activeProvider": "openai-codex",
                        "activeModel": "gpt-5.5",
                    },
                )

            self.assertEqual(contract["schema"], "fluxio.provider_orchestration_contract.v1")
            self.assertEqual(contract["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", contract["fallbackRuntimeLanes"])
            self.assertIn("opencode", contract["fallbackRuntimeLanes"])
            self.assertIn("vision", contract["requiredCapabilities"])
            self.assertEqual(contract["selectionMode"], "ready_best_fit")
            self.assertTrue(contract["shouldSwitch"])
            self.assertEqual(contract["runtimeAvailability"]["hermes"], True)
            self.assertEqual(contract["runtimeAvailability"]["openclaw"], True)
            self.assertEqual(contract["runtimeAvailability"]["opencode"], True)
            self.assertEqual(contract["taskProfile"]["schema"], "fluxio.provider_task_profile.v1")
            self.assertEqual(contract["routePolicy"]["schema"], "fluxio.provider_route_policy.v1")
            self.assertIn("https://opencode.ai/docs/providers/", contract["sourceDocs"])
            self.assertIn("https://ai-sdk.dev/docs/foundations/providers-and-models", contract["sourceDocs"])
            self.assertEqual(contract["missionGate"]["status"], "complete")
            selected = contract["selectedRoute"]
            self.assertEqual(selected["role"], "reviewer")
            self.assertEqual(selected["provider"], "openrouter")
            self.assertEqual(selected["model"], "openrouter/z-ai/glm-5.2")
            self.assertEqual(selected["health"], "ready")
            self.assertEqual(selected["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", selected["fallbackRuntimeLanes"])
            self.assertEqual(selected["scorecard"]["schema"], "fluxio.provider_scorecard.v1")
            self.assertEqual(selected["routeHealth"]["schema"], "fluxio.provider_route_health.v1")
            self.assertGreaterEqual(selected["scorecard"]["capabilityScore"], 75)
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "provider_orchestration_model_switching_contract")
            self.assertEqual(proof["selectedRoute"]["model"], "openrouter/z-ai/glm-5.2")
            self.assertEqual(proof["missionGate"]["status"], "complete")

    def test_provider_orchestration_uses_opencode_fallback_when_hermes_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            def fake_which(command, path=None):  # noqa: ANN001
                if command == "opencode":
                    return command
                return None

            with mock.patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "",
                    "ANTHROPIC_API_KEY": "",
                    "OPENROUTER_API_KEY": "",
                    "MINIMAX_API_KEY": "",
                    "MINIMAX_OAUTH_TOKEN": "",
                    "OPENCODE_API_KEY": "",
                    "HOME": str(root / "home"),
                    "OPENCLAW_STATE_DIR": str(root / "home" / ".openclaw"),
                },
            ), mock.patch("shutil.which", side_effect=fake_which):
                self.assertTrue(
                    backend.dispatch(
                        "save_provider_secret_command",
                        {"providerId": "opencode-go", "secret": "test-opencode-key"},
                    )
                )
                contract = backend.dispatch(
                    "get_provider_orchestration_command",
                    {
                        "root": str(root),
                        "requestId": "mission6-opencode-fallback",
                        "taskBrief": "Audit provider routes and choose a model switch fallback through OpenCode.",
                        "activeProvider": "openai-codex",
                        "activeModel": "gpt-5.5",
                    },
                )

            self.assertEqual(contract["schema"], "fluxio.provider_orchestration_contract.v1")
            self.assertEqual(contract["runtimeAvailability"]["hermes"], False)
            self.assertEqual(contract["runtimeAvailability"]["openclaw"], False)
            self.assertEqual(contract["runtimeAvailability"]["opencode"], True)
            self.assertEqual(contract["selectionMode"], "ready_best_fit")
            selected = contract["selectedRoute"]
            self.assertEqual(selected["provider"], "opencode-go")
            self.assertEqual(selected["health"], "fallback_ready")
            self.assertFalse(selected["routeHealth"]["hermesReady"])
            self.assertTrue(selected["routeHealth"]["fallbackReady"])
            self.assertIn("opencode", selected["fallbackRuntimeLanes"])
            self.assertIn("hermes_unavailable", selected["routeHealth"]["blockers"])
            self.assertTrue(contract["shouldSwitch"])
            self.assertEqual(contract["missionGate"]["status"], "complete")
            self.assertIn("fallback", contract["nextAction"].lower())

    def test_provider_chat_reliability_runs_ten_runtime_chat_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            def fake_which(command, path=None):  # noqa: ANN001
                if command in {"hermes", "opencode", "openclaw"}:
                    return command
                return None

            def fake_chat(payload):  # noqa: ANN001
                runtime = payload["runtime"]
                return {
                    "reply": "FLUXIO_ROUTE_OK",
                    "runtime": runtime,
                    "route": payload["route"],
                    "elapsedMs": 12,
                    "command": f"{runtime} <prompt>",
                    "compartment": {"id": payload["sessionId"]},
                }

            with mock.patch.dict(
                "os.environ",
                {
                    "OPENROUTER_API_KEY": "",
                    "OPENCODE_API_KEY": "",
                    "HOME": str(root / "home"),
                },
            ), mock.patch("shutil.which", side_effect=fake_which), mock.patch.object(
                backend,
                "_run_agent_chat",
                side_effect=fake_chat,
            ) as run_chat:
                contract = backend.dispatch(
                    "get_provider_chat_reliability_command",
                    {
                        "root": str(root),
                        "requestId": "provider-chat-reliability",
                        "provider": "openrouter",
                        "model": "z-ai/glm-5.2",
                        "attemptCount": 10,
                        "allowProviderChatProbe": True,
                    },
                )

            self.assertEqual(contract["schema"], "fluxio.provider_chat_reliability.v1")
            self.assertEqual(contract["status"], "complete")
            self.assertEqual(contract["attemptCount"], 10)
            self.assertEqual(contract["okCount"], 10)
            self.assertEqual(run_chat.call_count, 10)
            self.assertEqual(contract["runtimeSummary"]["hermes"]["attempted"], 5)
            self.assertEqual(contract["runtimeSummary"]["opencode"]["attempted"], 5)
            self.assertEqual(contract["runtimeSummary"]["hermes"]["ok"], 5)
            self.assertEqual(contract["runtimeSummary"]["opencode"]["ok"], 5)
            self.assertEqual(contract["missionGate"]["status"], "complete")
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "provider_runtime_chat_reliability")
            self.assertEqual(len(proof["attempts"]), 10)

    def test_provider_orchestration_task_profile_does_not_treat_fluxio_as_ux(self) -> None:
        profile = web_backend._provider_orchestration_task_profile(
            "Audit provider routes and choose a model switch fallback through OpenCode for Fluxio Mission 6."
        )

        self.assertEqual(profile["selectedRole"], "router")
        self.assertIn("provider_exploration", profile["requiredCapabilities"])
        self.assertNotIn("frontend_ui", profile["requiredCapabilities"])

    def test_runtime_route_unification_prefers_opencode_glm_when_hermes_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            def fake_which(command, path=None):  # noqa: ANN001
                if command in {"hermes", "opencode", "openclaw"}:
                    return command
                return None

            def fake_run(args, **kwargs):  # noqa: ANN001
                return mock.Mock(returncode=0, stdout=f"{args[0]} version 1\n", stderr="")

            def fake_run_process_capture(args, *, cwd, timeout=180, extra_env=None):  # noqa: ANN001
                executable = pathlib.Path(str(args[0])).name.lower()
                if executable == "opencode" and "models" in args:
                    return {}, "openrouter/z-ai/glm-5.2\n", "", 75
                if executable == "hermes":
                    raise RuntimeError("Hermes provider resolver returned an empty API key.")
                if executable == "opencode" and "run" in args:
                    payload = {"type": "text", "part": {"text": "{\"ok\":true,\"route\":\"opencode-glm\"}"}}
                    return payload, json.dumps(payload), "", 130
                if executable == "openclaw":
                    raise AssertionError("OpenClaw inference must stay controlled unless explicitly allowed.")
                raise AssertionError(f"Unexpected command: {args}")

            with mock.patch("grant_agent.web_backend.shutil.which", side_effect=fake_which):
                with mock.patch("grant_agent.web_backend.subprocess.run", side_effect=fake_run):
                    with mock.patch("grant_agent.web_backend._run_process_capture", side_effect=fake_run_process_capture):
                        contract = backend.dispatch(
                            "get_runtime_route_unification_command",
                            {
                                "root": str(root),
                                "requestId": "mission2-route-test",
                                "probeProviderModels": True,
                                "probeRuntime": True,
                                "allowProviderCliProbe": True,
                                "timeoutSeconds": 5,
                            },
                        )

            self.assertEqual(contract["schema"], "fluxio.runtime_route_unification.v1")
            self.assertEqual(contract["status"], "complete")
            self.assertEqual(contract["selectedRuntime"], "opencode")
            self.assertEqual(contract["missionGate"]["status"], "complete")
            self.assertIsNone(contract["missionGate"]["nextMissing"])
            self.assertEqual(contract["health"]["calls"]["hermes"]["status"], "failed")
            self.assertEqual(contract["health"]["calls"]["opencode"]["status"], "ok")
            self.assertFalse(contract["health"]["calls"]["openclaw"]["attempted"])
            self.assertIn("controlled", contract["health"]["calls"]["openclaw"]["error"])
            proof_path = pathlib.Path(contract["artifacts"]["routeHealthPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["selectedRuntime"], "opencode")
            self.assertTrue(proof["opencode"]["modelsContainGlm52"])

    def test_agent_chat_supports_opencode_runtime_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            backend = FluxioWebBackend(root, root)

            def fake_which(command, path=None):  # noqa: ANN001
                if command == "opencode":
                    return command
                return None

            def fake_run_process_capture(args, *, cwd, timeout=180, extra_env=None):  # noqa: ANN001
                executable = pathlib.Path(str(args[0])).name.lower()
                if executable == "opencode" and "run" in args:
                    payload = {"type": "text", "part": {"text": "OpenCode lane ready."}}
                    return payload, json.dumps(payload), "", 140
                raise AssertionError(f"Unexpected command: {args}")

            with mock.patch("grant_agent.web_backend.shutil.which", side_effect=fake_which):
                with mock.patch("grant_agent.web_backend._run_process_capture", side_effect=fake_run_process_capture):
                    result = backend.dispatch(
                        "send_agent_chat_command",
                        {
                            "payload": {
                                "runtime": "opencode",
                                "message": "prove the lane",
                                "workspaceId": "workspace_primary",
                                "workspacePath": str(workspace),
                                "route": {
                                    "role": "executor",
                                    "provider": "openrouter",
                                    "model": "z-ai/glm-5.2",
                                    "effort": "high",
                                },
                            }
                        },
                    )

            self.assertEqual(result["runtime"], "opencode")
            self.assertEqual(result["route"]["model_id"], "openrouter/z-ai/glm-5.2")
            self.assertEqual(result["reply"], "OpenCode lane ready.")
            self.assertEqual(result["compartment"]["runtime"], "opencode")

    def test_fusion_readiness_command_writes_detected_project_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = pathlib.Path(temp_dir) / "user"
            projects = user_root / "Projects"
            root = projects / "vibe-coding-platform"
            mind_tower = projects / "mind-tower"
            solantir = projects / "Solantír"
            fusion_workspace = user_root / "SynologyDrive" / "solantir-mindtower-fusion"
            root.mkdir(parents=True)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "connected_apps.json").write_text(
                json.dumps(
                    [
                        {
                            "app_id": "solantir-terminal",
                            "bridge": {"endpoint": "pipe://custom-solantir"},
                            "context_surfaces": [{"label": "Terminal watchlist"}],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (mind_tower / "skills" / "mindtower-ui-craft").mkdir(parents=True)
            (mind_tower / "services" / "bridge").mkdir(parents=True)
            (mind_tower / "services" / "monitor-worker" / "src" / "mindtower_worker").mkdir(parents=True)
            (mind_tower / "services" / "hermes-runtime").mkdir(parents=True)
            (mind_tower / "apps" / "tower").mkdir(parents=True)
            (mind_tower / "apps" / "admin").mkdir(parents=True)
            (mind_tower / "packages" / "shared" / "src").mkdir(parents=True)
            (mind_tower / "data").mkdir(parents=True)
            (mind_tower / "package.json").write_text(
                json.dumps({"name": "mind-tower", "version": "1.2.3", "packageManager": "pnpm@10.26.2"}),
                encoding="utf-8",
            )
            (mind_tower / "skills" / "mindtower-ui-craft" / "SKILL.md").write_text(
                "# Mind Tower UI Craft\n",
                encoding="utf-8",
            )
            (mind_tower / "README.md").write_text("# Mind Tower\n\nSynology-first monitoring stack.\n", encoding="utf-8")
            (mind_tower / "packages" / "shared" / "src" / "models.ts").write_text(
                "export type SourceHealth = { id: string }\n",
                encoding="utf-8",
            )
            (mind_tower / "data" / "mindtower.sqlite").write_text("", encoding="utf-8")
            (solantir / "apps" / "terminal").mkdir(parents=True)
            (solantir / "packages" / "contracts" / "src").mkdir(parents=True)
            (solantir / "services" / "ingestion").mkdir(parents=True)
            (solantir / "services" / "prediction").mkdir(parents=True)
            (solantir / "services" / "research").mkdir(parents=True)
            (solantir / "storage" / "warehouse").mkdir(parents=True)
            (solantir / "legacy" / "osint-platform").mkdir(parents=True)
            (solantir / "package.json").write_text(
                json.dumps({"name": "solantir-terminal", "version": "1.0.0"}),
                encoding="utf-8",
            )
            (solantir / "README.md").write_text("# Solantir Terminal\n\nUnified terminal shell.\n", encoding="utf-8")
            (solantir / "ARCHITECTURE_UNIFICATION_BRIEF.md").write_text(
                "# Brief\n\nUse one terminal and canonical contracts.\n",
                encoding="utf-8",
            )
            (solantir / "packages" / "contracts" / "src" / "solantir.ts").write_text(
                "export type Observation = { id: string }\n",
                encoding="utf-8",
            )
            fusion_workspace.mkdir(parents=True)
            (fusion_workspace / "README.md").write_text("fusion evidence\n", encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {
                    "HOME": str(user_root),
                    "USERPROFILE": str(user_root),
                    "FLUXIO_FUSION_HOME": str(user_root),
                },
            ):
                contract = backend.dispatch(
                    "get_fusion_readiness_command",
                    {"root": str(root), "requestId": "mission7-fusion-test"},
                )

            self.assertEqual(contract["schema"], "fluxio.fusion_readiness.v1")
            self.assertEqual(contract["mission"], "mission13-solantir-mind-tower-fusion")
            self.assertEqual(contract["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", contract["fallbackRuntimeLanes"])
            self.assertEqual(contract["status"], "ready_for_fusion_plan")
            projects_by_id = {item["id"]: item for item in contract["projects"]}
            self.assertEqual(projects_by_id["mind-tower"]["status"], "detected")
            self.assertEqual(projects_by_id["mind-tower"]["packageVersion"], "1.2.3")
            self.assertIn("mindtower-ui-craft", projects_by_id["mind-tower"]["skills"])
            self.assertEqual(projects_by_id["solantir-terminal"]["status"], "app_detected")
            self.assertEqual(projects_by_id["solantir-terminal"]["selectedRoot"], str(solantir.resolve()))
            self.assertIn(str(fusion_workspace), projects_by_id["solantir-terminal"]["candidateRoots"])
            self.assertEqual(projects_by_id["solantir-terminal"]["bridgeEndpoint"], "pipe://custom-solantir")
            self.assertEqual(projects_by_id["solantir-terminal"]["surface"], "Terminal watchlist")
            self.assertIn("Shared signal contract", contract["firstMergeTarget"]["title"])
            self.assertFalse(contract["blockers"])
            self.assertEqual(contract["missionGate"]["status"], "complete")
            self.assertGreaterEqual(len(contract["overlapMap"]), 4)
            self.assertEqual(contract["fusionDecisions"][0]["decision"], "solantir_terminal_is_primary_shell")
            self.assertIn("mindtower_monitor_worker_survives_as_ingestion_service", {item["decision"] for item in contract["fusionDecisions"]})
            self.assertEqual(contract["migrationPlan"][0]["id"], "read-only-inventory")
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "solantir_mind_tower_fusion_readiness")
            self.assertEqual(proof["missionGate"]["items"][-1]["proof"], str(proof_path))

    def test_jbh_eaven_redteam_readiness_command_writes_safe_lab_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = pathlib.Path(temp_dir) / "user"
            projects = user_root / "Projects"
            root = projects / "vibe-coding-platform"
            jbheaven = projects / "Jbheaven"
            skill_root = jbheaven / "skills" / "red-teaming" / "jbheaven-technique-scorer"
            root.mkdir(parents=True)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "connected_apps.json").write_text(
                json.dumps(
                    [
                        {
                            "app_id": "jbheaven",
                            "name": "JBheaven",
                            "bridge": {"endpoint": "http://127.0.0.1:1/api", "healthcheck": "/health"},
                            "permissions": ["task.run", "context.read", "skill.inspect"],
                            "auth": {"mode": "local_session"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text("# Technique scorer\n", encoding="utf-8")
            (jbheaven / "package.json").write_text(
                json.dumps({"name": "jbheaven", "version": "8.0.0"}),
                encoding="utf-8",
            )
            (jbheaven / "ETHICAL_LOOP_CONTEXT.md").write_text("synthetic lab only\n", encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {
                    "HOME": str(user_root),
                    "USERPROFILE": str(user_root),
                    "FLUXIO_JBH_EAVEN_HOME": str(user_root),
                },
            ):
                contract = backend.dispatch(
                    "get_jbh_eaven_redteam_readiness_command",
                    {"root": str(root), "requestId": "mission14-jbh-test"},
                )

            self.assertEqual(contract["schema"], "fluxio.jbh_eaven_redteam_readiness.v1")
            self.assertEqual(contract["mission"], "mission14-jbh-eaven-redteam-simulation")
            self.assertEqual(contract["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", contract["fallbackRuntimeLanes"])
            self.assertEqual(contract["status"], "ready_for_safe_synthetic_lab")
            self.assertEqual(contract["project"]["status"], "detected")
            self.assertEqual(contract["project"]["packageVersion"], "8.0.0")
            self.assertIn("jbheaven-technique-scorer", contract["project"]["redTeamSkills"])
            self.assertEqual(contract["api"]["status"], "offline")
            self.assertFalse(contract["scenarioGate"]["rawPayloadExport"])
            self.assertTrue(contract["scenarioGate"]["requiresFakeTargetBoundary"])
            self.assertIn("credential theft", contract["scenarioGate"]["blockedRealWorldActions"])
            self.assertEqual(contract["fakeTargetBoundary"]["authorizationLabel"], "synthetic_lab_authorized")
            self.assertEqual(contract["fakeTargetBoundary"]["networkPolicy"], "no_real_target_probe")
            self.assertGreaterEqual(len(contract["safeScenarioTemplates"]), 3)
            self.assertEqual(contract["safeScenarioTemplates"][0]["export"], "aggregate_only")
            self.assertGreaterEqual(len(contract["scoringRubric"]), 5)
            self.assertIn("blocked_real_world_abuse", contract["refusalAnalysis"]["expectedCategories"])
            self.assertEqual(contract["agentRun"]["schema"], "fluxio.jbh_eaven_safe_lab_agent_run.v1")
            self.assertEqual(contract["agentRun"]["executedBy"], "fluxio_internal_safe_lab_agent")
            self.assertEqual(contract["agentRun"]["status"], "complete")
            self.assertEqual(contract["agentRun"]["scenarioCount"], 3)
            self.assertFalse(contract["agentRun"]["rawPayloadExport"])
            self.assertIn(contract["agentRun"]["selectedRuntime"], {"hermes", "openclaw", "opencode", "local-safety-evaluator"})
            self.assertEqual(contract["missionGate"]["status"], "complete")
            self.assertIn("App internal agent run", [item["label"] for item in contract["missionGate"]["items"]])
            self.assertIn("JBheaven local API is offline", contract["warnings"][0])
            self.assertIn("Safe synthetic scenario gate", contract["firstRunTarget"]["title"])
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "jbh_eaven_safe_synthetic_redteam_readiness")
            self.assertEqual(proof["missionGate"]["items"][-1]["proof"], str(proof_path))

    def test_preview_annotation_readiness_command_writes_capture_contract_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "control_route_visual_smoke.py").write_text("# visual smoke fixture\n", encoding="utf-8")
            proof_dir = root / "artifacts" / "mission9-preview-annotation"
            proof_dir.mkdir(parents=True)
            screenshot = proof_dir / "before.png"
            dom = proof_dir / "before.dom.html"
            check = proof_dir / "before.check.json"
            screenshot.write_bytes(b"\x89PNG\r\n\x1a\n")
            dom.write_text("<main data-preview='true'>Preview fixture</main>", encoding="utf-8")
            check.write_text(json.dumps({"ok": True}), encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            contract = backend.dispatch(
                "get_preview_annotation_readiness_command",
                {
                    "root": str(root),
                    "requestId": "mission9-preview-test",
                    "surface": "builder-live-review",
                    "targetUrl": "http://127.0.0.1:5185/control?surface=builder",
                    "selectedEventId": "event-preview",
                    "selectedAnnotationId": "annotation-preview",
                    "screenshotPath": str(screenshot),
                    "domPath": str(dom),
                    "checkPath": str(check),
                    "visualFinding": {
                        "id": "annotation-preview",
                        "severity": "high",
                        "finding": "Preview capture shows proof cards crowding the browser work surface.",
                        "nextImplementationStep": "Fold raw proof behind the browser annotation lane before the next UI edit.",
                    },
                },
            )

            self.assertEqual(contract["schema"], "fluxio.preview_annotation_readiness.v1")
            self.assertEqual(contract["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", contract["fallbackRuntimeLanes"])
            self.assertIn("browser-cdp", contract["fallbackRuntimeLanes"])
            self.assertEqual(contract["status"], "ready_for_preview_annotation_loop")
            self.assertEqual(contract["previewTarget"]["selectedEventId"], "event-preview")
            self.assertIn("capture screenshot artifact", contract["captureCapabilities"])
            self.assertEqual(contract["selectedFinding"]["id"], "annotation-preview")
            self.assertIn("Fold raw proof", contract["nextAction"])
            self.assertEqual(contract["executionProof"]["schema"], "fluxio.preview_execution_proof.v1")
            self.assertTrue(contract["executionProof"]["screenshotCaptured"])
            self.assertTrue(contract["executionProof"]["domCaptured"])
            self.assertTrue(contract["executionProof"]["annotationFeedsRuntime"])
            self.assertEqual(contract["runtimeHandoff"]["schema"], "fluxio.preview_annotation_handoff.v1")
            self.assertIn("Fold raw proof", contract["runtimeHandoff"]["nextImplementationStep"])
            self.assertEqual(contract["annotationMap"]["schema"], "fluxio.preview_annotation_map.v1")
            self.assertEqual(contract["missionGate"]["schema"], "fluxio.preview_browser_annotation_gate.v1")
            self.assertEqual(contract["missionGate"]["missionId"], "mission7-preview-browser-annotation")
            self.assertEqual(contract["missionGate"]["status"], "complete")
            self.assertIn("preview_screenshot_breakdown", {item["id"] for item in contract["skillsUsed"]})
            self.assertEqual({item["step"] for item in contract["annotationLoop"]}, {"capture", "breakdown", "annotate", "repair"})
            self.assertTrue(all(item["status"] != "blocked" for item in contract["readinessChecks"]))
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "preview_browser_annotation_readiness")
            self.assertEqual(proof["proofArtifacts"]["screenshotPath"], str(screenshot.resolve()))
            annotation_map_path = pathlib.Path(contract["proofArtifacts"]["annotationMapPath"])
            runtime_handoff_path = pathlib.Path(contract["proofArtifacts"]["runtimeHandoffPath"])
            self.assertTrue(annotation_map_path.is_file())
            self.assertTrue(runtime_handoff_path.is_file())
            annotation_map = json.loads(annotation_map_path.read_text(encoding="utf-8"))
            runtime_handoff = json.loads(runtime_handoff_path.read_text(encoding="utf-8"))
            self.assertEqual(annotation_map["annotation"]["id"], "annotation-preview")
            self.assertEqual(runtime_handoff["source"], "preview_browser_annotation")

    def test_preview_annotation_readiness_blocks_without_capture_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "control_route_visual_smoke.py").write_text("# visual smoke fixture\n", encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            contract = backend.dispatch(
                "get_preview_annotation_readiness_command",
                {
                    "root": str(root),
                    "requestId": "mission7-preview-missing-capture",
                    "targetUrl": "http://127.0.0.1:5185/control?surface=builder",
                    "visualFinding": {
                        "id": "missing-capture",
                        "finding": "The preview cannot prove the browser saw the target yet.",
                        "nextImplementationStep": "Capture screenshot and DOM artifacts before implementation.",
                    },
                },
            )

            self.assertEqual(contract["status"], "blocked_missing_preview_capture")
            self.assertEqual(contract["missionGate"]["status"], "needs_capture")
            self.assertFalse(contract["executionProof"]["screenshotCaptured"])
            self.assertFalse(contract["executionProof"]["domCaptured"])
            self.assertIn("No screenshot path supplied yet.", contract["blockers"])
            self.assertIn("No DOM path supplied yet.", contract["blockers"])
            self.assertTrue(pathlib.Path(contract["proofArtifacts"]["annotationMapPath"]).is_file())
            self.assertTrue(pathlib.Path(contract["proofArtifacts"]["runtimeHandoffPath"]).is_file())

    def test_harness_benchmark_board_command_writes_hermes_first_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            agent_control = root / ".agent_control"
            for relative in (
                "image_playground_self_repair/mission1/route_proof.json",
                "ui_self_repair/mission2/ui_breakdown.json",
                "mission_anti_drift_guard/mission4-local-proof.json",
                "skill_runtime_contracts/mission5-local-proof.json",
                "provider_orchestration/mission6-local-proof.json",
                "preview_annotation_readiness/mission9-preview-actual.json",
            ):
                artifact = agent_control / relative
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text(json.dumps({"ok": True}), encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            def fake_which(command: str, **_kwargs: object) -> str | None:
                if command in {"hermes", "openclaw", "opencode"}:
                    return f"C:/tools/{command}.exe"
                return None

            with mock.patch("shutil.which", side_effect=fake_which):
                contract = backend.dispatch(
                    "get_harness_benchmark_board_command",
                    {
                        "root": str(root),
                        "requestId": "mission10-harness-test",
                        "primaryModel": "openrouter/z-ai/glm-5.2",
                    },
                )

            self.assertEqual(contract["schema"], "fluxio.harness_benchmark_board.v1")
            self.assertEqual(contract["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", contract["fallbackRuntimeLanes"])
            self.assertIn("opencode", contract["fallbackRuntimeLanes"])
            self.assertEqual(contract["status"], "ready_for_decision_board")
            self.assertEqual(contract["decision"]["production"], "hermes-fluxio-hybrid")
            self.assertEqual(contract["decision"]["specialist"], "opencode-glm52-coding-vision")
            self.assertEqual(contract["missionGate"]["mission"], "mission11-harness-benchmark-board")
            self.assertEqual(contract["missionGate"]["status"], "complete")
            labels = {item["label"] for item in contract["matrix"]}
            self.assertIn("Hermes + Syntelos Hybrid", labels)
            self.assertIn("OpenClaw + Syntelos Hybrid", labels)
            self.assertIn("OpenCode / GLM-5.2 route", labels)
            hermes_row = next(item for item in contract["matrix"] if item["id"] == "hermes-fluxio-hybrid")
            self.assertIn("dimensionScores", hermes_row)
            self.assertIn("proofCapture", hermes_row["dimensionScores"])
            recommendations = {item["id"]: item for item in contract["taskClassRecommendations"]}
            self.assertEqual(recommendations["completion-mission"]["use"], "hermes-fluxio-hybrid")
            self.assertEqual(recommendations["vision-coding-specialist"]["use"], "opencode-glm52-coding-vision")
            self.assertIn("Hermes + Syntelos Hybrid is the production policy lane", contract["routingRules"][0])
            self.assertTrue(contract["routeProof"]["hermes"]["available"])
            self.assertEqual(contract["routeProof"]["selectedOperationalLane"], "hermes")
            self.assertIn("harness_benchmark_reader", {item["id"] for item in contract["skillsUsed"]})
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "hermes_first_harness_benchmark_board")

    def test_harness_quality_gate_blocks_claimed_feature_without_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            contract = backend.dispatch(
                "get_harness_quality_gate_command",
                {
                    "root": str(root),
                    "requestId": "mission3-blocked-test",
                    "completionRequested": True,
                    "features": [
                        {
                            "id": "pre_completion_gate",
                            "title": "Pre-completion gate",
                            "status": "passed",
                            "passes": True,
                            "proofArtifacts": ["missing-proof.json"],
                        }
                    ],
                    "verificationResults": [
                        {
                            "command": "python -m pytest tests/test_web_backend.py::gate",
                            "status": "passed",
                            "returnCode": 0,
                        }
                    ],
                    "events": [
                        {"kind": "harness.plan", "message": "Plan the gate."},
                        {"kind": "harness.verify", "message": "Verify proof."},
                    ],
                    "progress": {
                        "currentFeatureId": "pre_completion_gate",
                        "nextAction": "Attach proof before claiming completion.",
                    },
                },
            )

            self.assertEqual(contract["schema"], "fluxio.harness_quality_gate.v1")
            self.assertEqual(contract["status"], "blocked")
            self.assertEqual(contract["missionGate"]["status"], "blocked")
            self.assertEqual(contract["missionGate"]["nextMissing"]["id"], "pre-completion-verification")
            feature = contract["featureLedger"]["features"][0]
            self.assertFalse(feature["passes"])
            self.assertEqual(feature["status"], "blocked")
            self.assertIn("missing-proof.json", feature["missingProofArtifacts"][0])
            artifacts = contract["artifacts"]
            self.assertTrue(pathlib.Path(artifacts["featureLedgerPath"]).is_file())
            self.assertTrue(pathlib.Path(artifacts["progressPath"]).is_file())
            self.assertTrue(pathlib.Path(artifacts["eventTracePath"]).is_file())
            self.assertTrue(pathlib.Path(artifacts["missionGatePath"]).is_file())
            self.assertTrue(pathlib.Path(artifacts["contractPath"]).is_file())

    def test_harness_quality_gate_completes_with_feature_proof_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            proof_dir = root / "artifacts" / "mission3"
            proof_dir.mkdir(parents=True)
            proof_file = proof_dir / "proof.json"
            proof_file.write_text(json.dumps({"ok": True}), encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            contract = backend.dispatch(
                "get_harness_quality_gate_command",
                {
                    "root": str(root),
                    "requestId": "mission3-complete-test",
                    "completionRequested": True,
                    "features": [
                        {
                            "id": "pre_completion_gate",
                            "title": "Pre-completion gate",
                            "status": "passed",
                            "passes": True,
                            "proofArtifacts": [str(proof_file)],
                            "verificationCommands": ["python -m pytest tests/test_web_backend.py::gate"],
                        }
                    ],
                    "verificationResults": [
                        {
                            "command": "python -m pytest tests/test_web_backend.py::gate",
                            "status": "passed",
                            "returnCode": 0,
                            "durationMs": 123,
                        }
                    ],
                    "events": [
                        {"kind": "harness.plan", "message": "Plan the gate."},
                        {"kind": "harness.verify", "message": "Verify proof."},
                    ],
                    "progress": {
                        "currentFeatureId": "pre_completion_gate",
                        "nextAction": "Open the focused Mission 3 PR.",
                    },
                },
            )

            self.assertEqual(contract["status"], "complete")
            self.assertEqual(contract["missionGate"]["status"], "complete")
            self.assertIsNone(contract["missionGate"]["nextMissing"])
            self.assertEqual(contract["featureLedger"]["rules"]["passesRequiresProof"], True)
            self.assertTrue(contract["featureLedger"]["features"][0]["passes"])
            self.assertEqual(contract["progress"]["completedFeatureCount"], 1)
            self.assertEqual({item["kind"] for item in contract["eventTrace"]}, {"harness.plan", "harness.verify"})
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "mission3_harness_quality_pre_completion_gate")
            self.assertEqual(proof["missionGate"]["status"], "complete")

    def test_update_management_readiness_command_writes_safe_update_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / "web" / "public").mkdir(parents=True)
            (root / "src-tauri").mkdir(parents=True)
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "version": "9.8.7",
                        "scripts": {
                            "frontend:build": "vite build --config vite.config.mjs",
                            "verify:long-history": "python scripts/control_route_responsive_smoke.py",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            (root / "uv.lock").write_text("", encoding="utf-8")
            (root / "src-tauri" / "Cargo.lock").write_text("", encoding="utf-8")
            (root / ".github" / "workflows" / "release-proof.yml").write_text(
                "steps:\n  - run: npm run frontend:build\n  - run: npm run verify:long-history\n",
                encoding="utf-8",
            )
            (root / "web" / "public" / "service-worker.js").write_text(
                'const CACHE_VERSION = "fluxio-test-cache";\n',
                encoding="utf-8",
            )
            (root / "web" / "public" / "manifest.webmanifest").write_text(
                json.dumps({"start_url": "/control"}),
                encoding="utf-8",
            )
            for relative in (
                "provider_orchestration/mission6-local-proof.json",
                "skill_runtime_contracts/mission5-local-proof.json",
                "harness_benchmark_board/mission10-local-proof.json",
                "preview_annotation_readiness/mission9-preview-actual.json",
            ):
                artifact = root / ".agent_control" / relative
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text(json.dumps({"ok": True}), encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            def fake_which(command: str, **_kwargs: object) -> str | None:
                if command in {"node", "npm", "python", "hermes", "openclaw", "opencode"}:
                    return f"C:/tools/{command}.exe"
                return None

            with mock.patch("shutil.which", side_effect=fake_which):
                contract = backend.dispatch(
                    "get_update_management_readiness_command",
                    {
                        "root": str(root),
                        "requestId": "mission12-update-test",
                    },
                )

            self.assertEqual(contract["schema"], "fluxio.update_management_readiness.v1")
            self.assertEqual(contract["mission"], "mission12-update-dependency-management")
            self.assertEqual(contract["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", contract["fallbackRuntimeLanes"])
            self.assertIn("opencode", contract["fallbackRuntimeLanes"])
            self.assertIn(contract["status"], {"ready_for_safe_update_window", "ready_with_manual_review"})
            self.assertEqual(contract["missionGate"]["mission"], "mission12-update-dependency-management")
            self.assertEqual(contract["missionGate"]["status"], "complete")
            self.assertEqual(contract["appVersion"], "9.8.7")
            self.assertEqual(contract["packageManager"], "npm")
            self.assertIn("package-lock.json", contract["lockfiles"])
            labels = {item["label"] for item in contract["components"]}
            self.assertIn("App dependencies", labels)
            self.assertIn("Provider and model definitions", labels)
            self.assertIn("Hermes / OpenClaw / OpenCode adapters", labels)
            self.assertIn("Web and app shell", labels)
            self.assertIn("Release proof workflow", labels)
            self.assertEqual({item["step"] for item in contract["safeUpgradeWorkflow"]}, {"snapshot", "isolate", "preview", "verify", "rollback"})
            self.assertEqual(contract["priorProofContractCount"], 4)
            self.assertGreaterEqual(len(contract["dependencyRows"]), 0)
            self.assertIn("compatibilityWarnings", contract)
            self.assertEqual({item["id"] for item in contract["updateFamilyPlan"]}, {"dependencies", "providers", "runtimes", "app-shell"})
            self.assertEqual(contract["outdatedCheck"]["status"], "not_requested")
            self.assertEqual(contract["auditCheck"]["status"], "not_requested")
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "safe_dependency_runtime_provider_update_readiness")
            self.assertEqual(proof["components"][0]["status"], "ready")
            self.assertEqual(proof["missionGate"]["items"][-1]["proof"], str(proof_path))

    def test_automation_overlap_status_command_defers_when_thread_goal_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            memory_path = root / "automation-memory.md"
            memory_path.write_text(
                "\n".join(
                    [
                        "## 2026-06-22T03:47:00+02:00",
                        "- Current state: Mission 11 has a focused PR.",
                        "## 2026-06-22T04:10:00+02:00",
                        "- PR130 opened and green: https://github.com/bobthecomputer/vibe-coding-platform/pull/130",
                        "- Current state: Mission 12 has a focused PR, real DOM/screenshot proof, and green release-proof.",
                    ]
                ),
                encoding="utf-8",
            )
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            (control_dir / "mission_watchdog_supervisor.json").write_text(
                json.dumps({"schema": "fluxio.mission_watchdog_supervisor.v1", "loopActive": True, "loopStatus": "active"}),
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)
            contract = backend.dispatch(
                "get_automation_overlap_status_command",
                {
                    "root": str(root),
                    "requestId": "mission13-overlap-test",
                    "automationId": "fluxio-night-school-real-agent-transcript-proof",
                    "automationMemoryPath": str(memory_path),
                    "threadGoalStatus": "active",
                    "threadGoalObjective": "Mission 13 test goal",
                    "currentMissionNumber": 13,
                },
            )

            self.assertEqual(contract["schema"], "fluxio.automation_overlap_status.v1")
            self.assertEqual(contract["status"], "defer_new_goal")
            self.assertEqual(contract["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", contract["fallbackRuntimeLanes"])
            self.assertEqual(contract["highestCompletedMission"], 12)
            self.assertEqual(contract["threadGoal"]["source"], "runtime_payload")
            self.assertTrue(contract["liveMissionState"]["supervisorActive"])
            self.assertIn("Do not create or override", contract["decision"])
            self.assertIn("https://github.com/bobthecomputer/vibe-coding-platform/pull/130", contract["proofLinks"])
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "automation_overlap_goal_guard")

    def test_pr_stack_landing_readiness_command_blocks_at_oldest_failed_pr(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            rows = [
                {
                    "number": 131,
                    "title": "Mission 13: Add automation overlap guard",
                    "headRefName": "codex/131-automation-overlap-status",
                    "baseRefName": "codex/130-in-app-update-cue",
                    "isDraft": False,
                    "url": "https://example.test/pull/131",
                    "mergeStateStatus": "CLEAN",
                    "reviewDecision": "",
                    "statusCheckRollup": [
                        {
                            "name": "release-proof",
                            "workflowName": "Fluxio Release Proof",
                            "status": "COMPLETED",
                            "conclusion": "SUCCESS",
                        }
                    ],
                },
                {
                    "number": 130,
                    "title": "Mission 12: Add in-app update cue",
                    "headRefName": "codex/130-in-app-update-cue",
                    "baseRefName": "codex/119-image-playground-mission1",
                    "isDraft": False,
                    "url": "https://example.test/pull/130",
                    "mergeStateStatus": "CLEAN",
                    "reviewDecision": "",
                    "statusCheckRollup": [
                        {
                            "name": "release-proof",
                            "workflowName": "Fluxio Release Proof",
                            "status": "COMPLETED",
                            "conclusion": "SUCCESS",
                        }
                    ],
                },
                {
                    "number": 119,
                    "title": "Mission 1: Image Playground self-repair loop",
                    "headRefName": "codex/119-image-playground-mission1",
                    "baseRefName": "master",
                    "isDraft": False,
                    "url": "https://example.test/pull/119",
                    "mergeStateStatus": "UNSTABLE",
                    "reviewDecision": "",
                    "statusCheckRollup": [
                        {
                            "name": "release-proof",
                            "workflowName": "Fluxio Release Proof",
                            "status": "COMPLETED",
                            "conclusion": "FAILURE",
                        }
                    ],
                },
            ]

            contract = backend.dispatch(
                "get_pr_stack_landing_readiness_command",
                {
                    "root": str(root),
                    "requestId": "mission14-landing-test",
                    "maxChain": 20,
                    "prRows": rows,
                },
            )

            self.assertEqual(contract["schema"], "fluxio.pr_stack_landing_readiness.v1")
            self.assertFalse(contract["ok"])
            self.assertEqual(contract["status"], "blocked_at_landing_frontier")
            self.assertEqual(contract["landingFrontier"]["number"], 119)
            self.assertEqual(contract["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", contract["fallbackRuntimeLanes"])
            self.assertIn("opencode", contract["fallbackRuntimeLanes"])
            self.assertIn("Fix PR119", contract["nextAction"])
            self.assertEqual(contract["performanceBudget"]["schema"], "fluxio.performance_budget.v1")
            self.assertEqual(contract["releasePackage"]["schema"], "fluxio.release_package_readiness.v1")
            self.assertEqual(contract["releaseAgentRun"]["schema"], "fluxio.release_landing_agent_run.v1")
            self.assertEqual(contract["releaseAgentRun"]["executedBy"], "fluxio_internal_release_landing_agent")
            self.assertEqual(contract["missionGate"]["mission"], "mission15-release-performance-pr-stack-landing")
            self.assertEqual(contract["landingDecision"]["status"], "hold_for_review")
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "pr_stack_landing_order_readiness")
            self.assertEqual(proof["landingSequence"][0]["number"], 119)
            self.assertIn("performanceBudget", proof)
            self.assertIn("releaseAgentRun", proof)

    def test_pr_stack_landing_readiness_command_accepts_empty_runtime_rows_as_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            contract = backend.dispatch(
                "get_pr_stack_landing_readiness_command",
                {
                    "root": str(root),
                    "requestId": "mission31-empty-stack-complete",
                    "maxChain": 5,
                    "prRows": [],
                },
            )

            self.assertEqual(contract["schema"], "fluxio.pr_stack_landing_readiness.v1")
            self.assertTrue(contract["ok"])
            self.assertEqual(contract["status"], "no_open_prs")
            self.assertEqual(contract["source"], "runtime_payload")
            self.assertEqual(contract["stack"]["openPrCount"], 0)
            self.assertEqual(contract["continuationPolicy"]["state"], "completed")
            self.assertFalse(contract["continuationPolicy"]["shouldContinueStackWork"])
            self.assertEqual(contract["continuationPolicy"]["automationDecision"], "skip_completed_pr_stack")
            self.assertEqual(contract["releaseAgentRun"]["executedBy"], "fluxio_internal_release_landing_agent")
            self.assertEqual(contract["landingDecision"]["status"], "hold_for_review")
            proof_path = pathlib.Path(contract["proof"]["artifactPath"])
            self.assertTrue(proof_path.is_file())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["source"], "runtime_payload")
            self.assertEqual(proof["continuationPolicy"]["state"], "completed")

    def test_provider_presence_reads_native_opencode_go_auth_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            home = root / "home"
            auth_store = home / ".local" / "share" / "opencode" / "auth.json"
            auth_store.parent.mkdir(parents=True)
            auth_store.write_text(
                json.dumps({"opencode-go": {"type": "api"}}),
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)
            with mock.patch.dict(
                "os.environ",
                {
                    "HOME": str(home),
                    "OPENCODE_API_KEY": "",
                    "OPENCLAW_STATE_DIR": str(home / ".openclaw"),
                },
                clear=False,
            ):
                presence = backend.dispatch(
                    "get_provider_secret_presence_command",
                    {"providerIds": ["opencode-go"]},
                )

            self.assertTrue(presence["opencode-go"])

    def test_web_backend_prepends_packaged_runtime_bin_to_cli_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            runtime_bin = root / ".agent_control" / "runtime" / "bin"
            runtime_bin.mkdir(parents=True)
            backend = FluxioWebBackend(root, root)

            env = backend._provider_env()

            self.assertIn("PATH", env)
            self.assertEqual(env["PATH"].split(__import__("os").pathsep)[0], str(runtime_bin))

    def test_web_backend_reports_minimax_openclaw_manual_auth_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {"HOME": str(root / "home"), "OPENCLAW_STATE_DIR": str(root / "home" / ".openclaw")},
            ):
                status = backend.dispatch("get_minimax_openclaw_auth_status_command", {})
            self.assertFalse(status["authenticated"])
            self.assertIn("credentialsPath", status)

            with mock.patch.dict(
                "os.environ",
                {"HOME": str(root / "home"), "OPENCLAW_STATE_DIR": str(root / "home" / ".openclaw")},
            ):
                with mock.patch(
                    "grant_agent.web_backend._request_minimax_oauth_code",
                    side_effect=RuntimeError("network unavailable"),
                ):
                    start = backend.dispatch(
                        "start_minimax_openclaw_auth_command",
                        {"payload": {"region": "global"}},
                    )
            self.assertTrue(start["manualRequired"])
            self.assertIn("openclaw models auth login", start["command"])
            self.assertEqual(start["method"], "oauth")

    def test_web_backend_starts_minimax_oauth_user_code_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {"HOME": str(root / "home"), "OPENCLAW_STATE_DIR": str(root / "home" / ".openclaw")},
            ):
                with mock.patch(
                    "grant_agent.web_backend._minimax_openclaw_auth_status",
                    return_value={"authenticated": False},
                ):
                    with mock.patch(
                        "grant_agent.web_backend._request_minimax_oauth_code",
                        return_value={
                            "user_code": "MM-1234",
                            "verification_uri": "https://api.minimax.io/oauth/verify",
                            "state": "",
                            "interval": 2000,
                            "expired_in": 1990000000000,
                        },
                    ):
                        result = backend.dispatch(
                            "start_minimax_openclaw_auth_command",
                            {"payload": {"region": "global"}},
                        )

            self.assertTrue(result["manualRequired"])
            self.assertEqual(result["providerId"], "minimax-portal")
            self.assertEqual(result["userCode"], "MM-1234")
            self.assertEqual(result["verificationUrl"], "https://api.minimax.io/oauth/verify")
            self.assertTrue(result["sessionId"])

    def test_web_backend_completes_minimax_oauth_user_code_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            session = MiniMaxOAuthSession(
                verifier="verifier",
                state="state",
                region="global",
                user_code="MM-1234",
                verification_url="https://api.minimax.io/oauth/verify",
                interval_ms=2000,
                expires_at_ms=1990000000000,
            )

            with mock.patch.dict(
                "os.environ",
                {"HOME": str(root), "OPENCLAW_STATE_DIR": str(root / ".openclaw")},
            ):
                with mock.patch.dict(
                    "grant_agent.web_backend._MINIMAX_OAUTH_SESSIONS",
                    {"minimax": session},
                    clear=True,
                ):
                    with mock.patch(
                        "grant_agent.web_backend._poll_minimax_oauth_token",
                        return_value={
                            "pending": False,
                            "access": "access",
                            "refresh": "refresh",
                            "expires": 1990000000000,
                        },
                    ):
                        with mock.patch(
                            "grant_agent.web_backend._minimax_openclaw_auth_status",
                            return_value={"authenticated": True},
                        ):
                            result = backend.dispatch(
                                "complete_minimax_openclaw_auth_command",
                                {"payload": {"sessionId": "minimax"}},
                            )

            self.assertTrue(result["authenticated"])
            auth_store = root / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
            payload = json.loads(auth_store.read_text(encoding="utf-8"))
            credential = payload["profiles"]["minimax-portal:default"]
            self.assertEqual(credential["provider"], "minimax-portal")
            self.assertEqual(credential["access"], "access")

    def test_minimax_status_does_not_claim_auth_store_source_without_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            home = root / "home"
            auth_store = home / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
            auth_store.parent.mkdir(parents=True)
            auth_store.write_text(
                json.dumps({"version": 1, "profiles": {"openai-codex:test": {"provider": "openai-codex"}}}),
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {"HOME": str(home), "OPENCLAW_STATE_DIR": str(home / ".openclaw")},
            ):
                status = backend.dispatch("get_minimax_openclaw_auth_status_command", {})

            self.assertFalse(status["authenticated"])
            self.assertIsNone(status["source"])

    def test_web_backend_reports_openai_codex_env_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                status = backend.dispatch("get_openai_codex_oauth_status_command", {})

            self.assertTrue(status["authenticated"])

    def test_web_backend_reports_openai_codex_openclaw_auth_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            home = root / "home"
            auth_store = home / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
            auth_store.parent.mkdir(parents=True)
            auth_store.write_text(
                '{"profiles":{"openai-codex:test@example.com":{"provider":"openai-codex","access":"token","refresh":"refresh"}}}',
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict("os.environ", {"HOME": str(home), "OPENCLAW_STATE_DIR": str(home / ".openclaw")}):
                status = backend.dispatch("get_openai_codex_oauth_status_command", {})

            self.assertTrue(status["authenticated"])
            self.assertEqual(status["source"], "openclaw-auth-profile")

    def test_web_backend_reports_openai_codex_hermes_auth_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            home = root / "home"
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {
                    "HOME": str(home),
                    "OPENCLAW_STATE_DIR": str(home / ".openclaw"),
                    "OPENAI_API_KEY": "",
                    "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT": "",
                },
            ):
                with mock.patch("grant_agent.web_backend.shutil.which", return_value="wsl"):
                    with mock.patch(
                        "grant_agent.web_backend.subprocess.run",
                        return_value=mock.Mock(
                            returncode=0,
                            stdout="openai-codex: logged in\n",
                            stderr="",
                        ),
                    ):
                        status = backend.dispatch("get_openai_codex_oauth_status_command", {})

            self.assertTrue(status["authenticated"])
            self.assertEqual(status["source"], "hermes-auth-store")

    def test_agent_chat_command_runs_openclaw_with_selected_non_codex_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            backend = FluxioWebBackend(root, root)
            calls: list[list[str]] = []

            def fake_run(args, **kwargs):
                calls.append(list(args))
                return mock.Mock(
                    returncode=0,
                    stdout='{"reply":"Hello from the selected model."}',
                    stderr="",
                )

            with mock.patch("grant_agent.web_backend.shutil.which", return_value="openclaw"):
                with mock.patch("grant_agent.web_backend.subprocess.run", side_effect=fake_run):
                    result = backend.dispatch(
                        "send_agent_chat_command",
                        {
                            "payload": {
                                "runtime": "openclaw",
                                "message": "hello",
                                "workspaceId": "workspace_primary",
                                "workspacePath": str(workspace),
                                "route": {
                                    "role": "executor",
                                    "provider": "openrouter",
                                    "model": "openai/gpt-5.3-codex",
                                    "effort": "medium",
                                },
                            }
                        },
                    )

            self.assertEqual(result["reply"], "Hello from the selected model.")
            self.assertEqual(calls[-1][1:4], ["infer", "model", "run"])
            self.assertIn("--prompt", calls[-1])
            self.assertIn("openai/gpt-5.3-codex", calls[-1])

    def test_agent_chat_command_uses_codex_cli_for_openai_codex_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            backend = FluxioWebBackend(root, root)
            calls: list[list[str]] = []

            def fake_run(args, **kwargs):
                calls.append(list(args))
                output_path = pathlib.Path(args[args.index("--output-last-message") + 1])
                output_path.write_text("pong", encoding="utf-8")
                return mock.Mock(returncode=0, stdout='{"type":"turn.completed"}', stderr="")

            with mock.patch("grant_agent.web_backend.shutil.which", return_value="codex"):
                with mock.patch("grant_agent.web_backend.subprocess.run", side_effect=fake_run):
                    result = backend.dispatch(
                        "send_agent_chat_command",
                        {
                            "payload": {
                                "runtime": "openclaw",
                                "message": "hello",
                                "workspaceId": "workspace_primary",
                                "workspacePath": str(workspace),
                                "route": {
                                    "role": "executor",
                                    "provider": "openai",
                                    "model": "gpt-5.3-codex",
                                    "effort": "medium",
                                },
                            }
                        },
                    )

            self.assertEqual(result["reply"], "pong")
            self.assertEqual(calls[-1][1], "exec")
            self.assertIn("gpt-5.3-codex", calls[-1])

    def test_agent_chat_prefers_minimax_portal_when_oauth_profile_is_connected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            home = root / "home"
            auth_store = home / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
            auth_store.parent.mkdir(parents=True)
            auth_store.write_text(
                '{"profiles":{"minimax-portal:default":{"provider":"minimax-portal","access":"token","refresh":"refresh"}}}',
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {
                    "HOME": str(home),
                    "OPENCLAW_STATE_DIR": str(home / ".openclaw"),
                    "MINIMAX_API_KEY": "",
                    "MINIMAX_OAUTH_TOKEN": "",
                },
            ):
                route = backend._chat_route(
                    {"route": {"provider": "minimax", "model": "MiniMax-M2.7", "effort": "low"}}
                )

            self.assertEqual(route["provider"], "minimax-portal")
            self.assertEqual(route["model_id"], "minimax-portal/MiniMax-M3")

    def test_hermes_chat_sends_normalized_minimax_m3_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            home = root / "home"
            workspace = root / "workspace"
            workspace.mkdir()
            auth_store = home / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
            auth_store.parent.mkdir(parents=True)
            auth_store.write_text(
                '{"profiles":{"minimax-portal:default":{"provider":"minimax-portal","access":"token","refresh":"refresh"}}}',
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)
            calls: list[list[str]] = []

            def fake_run(args, **kwargs):
                calls.append(list(args))
                return mock.Mock(
                    returncode=0,
                    stdout='{"reply":"M3 frontend route ready."}',
                    stderr="",
                )

            with mock.patch.dict(
                "os.environ",
                {
                    "HOME": str(home),
                    "OPENCLAW_STATE_DIR": str(home / ".openclaw"),
                    "MINIMAX_API_KEY": "",
                    "MINIMAX_OAUTH_TOKEN": "",
                },
            ):
                with mock.patch("grant_agent.web_backend.shutil.which", return_value="hermes"):
                    with mock.patch("grant_agent.web_backend.subprocess.run", side_effect=fake_run):
                        result = backend.dispatch(
                            "send_agent_chat_command",
                            {
                                "payload": {
                                    "runtime": "hermes",
                                    "message": "tighten the frontend",
                                    "workspaceId": "workspace_primary",
                                    "workspacePath": str(workspace),
                                    "route": {
                                        "role": "executor",
                                        "provider": "minimax",
                                        "model": "MiniMax-M2.7",
                                        "effort": "high",
                                    },
                                }
                            },
                        )

            self.assertEqual(result["runtime"], "hermes")
            self.assertEqual(result["route"]["provider"], "minimax-oauth")
            self.assertEqual(result["route"]["model"], "MiniMax-M3")
            self.assertIn("--model", calls[-1])
            self.assertEqual(calls[-1][calls[-1].index("--model") + 1], "MiniMax-M3")
            self.assertIn("--provider", calls[-1])
            self.assertEqual(calls[-1][calls[-1].index("--provider") + 1], "minimax-oauth")
            proof = json.loads((root / ".agent_control" / "runtime_route_proof.json").read_text(encoding="utf-8"))
            self.assertEqual(proof["runtime"], "hermes")
            self.assertEqual(proof["provider"], "minimax-oauth")
            self.assertEqual(proof["model"], "MiniMax-M3")

    def test_agent_chat_extracts_runtime_model_message_from_json_string_reply(self) -> None:
        from grant_agent.web_backend import _extract_model_reply

        reply = _extract_model_reply(
            {
                "reply": json.dumps(
                    {
                        "sessionId": "mission-chat-example",
                        "runtime": "hermes",
                        "toolTimeline": [
                            {
                                "kind": "operator.message",
                                "summary": "Can you answer this mission?",
                            },
                            {
                                "kind": "runtime.model_message",
                                "summary": "This is the visible Hermes answer.",
                            },
                        ],
                    }
                )
            }
        )

        self.assertEqual(reply, "This is the visible Hermes answer.")

    def test_agent_chat_uses_wsl_hermes_when_native_cli_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            backend = FluxioWebBackend(root, root)
            calls: list[list[str]] = []

            def fake_which(name, *args, **kwargs):  # noqa: ANN001
                if name == "wsl":
                    return "wsl"
                return None

            def fake_run(args, **kwargs):
                calls.append(list(args))
                return mock.Mock(
                    returncode=0,
                    stdout='{"reply":"Hermes via WSL."}',
                    stderr="",
                )

            with mock.patch("grant_agent.web_backend.shutil.which", side_effect=fake_which):
                with mock.patch("grant_agent.web_backend._wsl_has_command", return_value=True):
                    with mock.patch("grant_agent.web_backend.subprocess.run", side_effect=fake_run):
                        result = backend.dispatch(
                            "send_agent_chat_command",
                            {
                                "payload": {
                                    "runtime": "hermes",
                                    "message": "hello",
                                    "workspaceId": "workspace_primary",
                                    "workspacePath": str(workspace),
                                    "route": {
                                        "role": "executor",
                                        "provider": "anthropic",
                                        "model": "claude-sonnet-4.5",
                                        "effort": "medium",
                                    },
                                }
                            },
                        )

            self.assertEqual(result["runtime"], "hermes")
            self.assertEqual(result["reply"], "Hermes via WSL.")
            self.assertEqual(calls[-1][0], "wsl")
            self.assertEqual(calls[-1][1:3], ["bash", "-lc"])
            self.assertIn("hermes chat -q", calls[-1][3])

    def test_runtime_route_proof_reports_wsl_hermes_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            proof_path = root / ".agent_control" / "runtime_route_proof.json"
            proof_path.parent.mkdir(parents=True, exist_ok=True)
            proof_path.write_text(
                json.dumps(
                    {
                        "runtime": "hermes",
                        "provider": "minimax-oauth",
                        "model": "MiniMax-M3",
                        "replyPreview": "MiniMax-M3 answered through Hermes.",
                    }
                ),
                encoding="utf-8",
            )

            def fake_which(name, *args, **kwargs):  # noqa: ANN001
                if name == "wsl":
                    return "wsl"
                return None

            def fake_run(args, **kwargs):  # noqa: ANN001
                script = str(args[-1])
                if "command -v hermes" in script:
                    return mock.Mock(
                        returncode=0,
                        stdout="/home/kali/.local/bin/hermes\n",
                        stderr="",
                    )
                if "hermes --version" in script:
                    return mock.Mock(
                        returncode=0,
                        stdout="Hermes Agent v0.14.0\n",
                        stderr="",
                    )
                return mock.Mock(returncode=1, stdout="", stderr="")

            with mock.patch("grant_agent.web_backend.os.name", "nt"):
                with mock.patch("grant_agent.web_backend.shutil.which", side_effect=fake_which):
                    with mock.patch("grant_agent.web_backend.subprocess.run", side_effect=fake_run):
                        status = backend._runtime_route_proof_status(root)

            self.assertTrue(status["hermesCommandVisible"])
            self.assertEqual(status["hermesCommand"], "wsl:/home/kali/.local/bin/hermes")
            self.assertEqual(status["hermesCommandSource"], "wsl")
            self.assertEqual(status["hermesVersion"], "Hermes Agent v0.14.0")
            self.assertTrue(status["minimaxM3Verified"])

    def test_web_backend_starts_direct_openai_codex_oauth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch(
                "grant_agent.web_backend._openai_codex_oauth_status",
                return_value={"authenticated": False},
            ):
                result = backend.dispatch("start_openai_codex_oauth_command", {})

            self.assertEqual(result["status"], "manual_required")
            self.assertEqual(result["method"], "oauth")
            self.assertIn("https://auth.openai.com/oauth/authorize", result["authUrl"])
            self.assertIn("code_challenge=", result["authUrl"])
            self.assertNotIn("codex/device", result["authUrl"])
            self.assertEqual(result["callbackPort"], 1455)
            self.assertIn("/api/codex/login/browser-relay/complete/", result["relayUrl"])
            self.assertIn("--relay-token", result["helperCommand"])

    def test_openai_codex_oauth_completion_uses_only_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            session = OpenAICodexOAuthSession(
                verifier="verifier",
                state="state",
                auth_url="https://auth.openai.com/oauth/authorize",
            )

            with mock.patch.dict(
                "grant_agent.web_backend._OPENAI_CODEX_OAUTH_SESSIONS",
                {"only": session},
                clear=True,
            ):
                with mock.patch(
                    "grant_agent.web_backend._exchange_openai_codex_authorization_code",
                    return_value={"access": "token", "refresh": "refresh", "expires": 1770000000000},
                ) as exchange_mock:
                    with mock.patch(
                        "grant_agent.web_backend._write_openai_codex_auth_profile",
                        return_value={"profileId": "openai-codex:default"},
                    ) as write_profile_mock:
                        with mock.patch(
                            "grant_agent.web_backend._openai_codex_oauth_status",
                            return_value={"authenticated": True},
                        ):
                            result = backend.dispatch(
                                "complete_openai_codex_oauth_command",
                                {"callback": "http://localhost:1455/auth/callback?code=abc&state=state"},
                            )

            self.assertTrue(result["authenticated"])
            exchange_mock.assert_called_once_with(
                "abc",
                "verifier",
                redirect_uri=web_backend.OPENAI_CODEX_REDIRECT_URI,
            )
            write_profile_mock.assert_called_once()

    def test_openai_codex_oauth_relay_completes_relative_callback_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            session = OpenAICodexOAuthSession(
                verifier="verifier",
                state="state",
                auth_url="https://auth.openai.com/oauth/authorize",
                relay_token_hash=web_backend._sha256_hex("relay-token"),
            )

            with mock.patch.dict(
                "grant_agent.web_backend._OPENAI_CODEX_OAUTH_SESSIONS",
                {"only": session},
                clear=True,
            ):
                with mock.patch(
                    "grant_agent.web_backend._exchange_openai_codex_authorization_code",
                    return_value={"access": "token", "refresh": "refresh", "expires": 1770000000000},
                ) as exchange_mock:
                    with mock.patch(
                        "grant_agent.web_backend._write_openai_codex_auth_profile",
                        return_value={"profileId": "openai-codex:default"},
                    ):
                        with mock.patch(
                            "grant_agent.web_backend._openai_codex_oauth_status",
                            return_value={"authenticated": True},
                        ):
                            result = backend.complete_openai_codex_oauth_relay(
                                session_id="only",
                                payload={"callbackPath": "/auth/callback?code=abc&state=state"},
                                authorization="Bearer relay-token",
                            )

            self.assertTrue(result["authenticated"])
            exchange_mock.assert_called_once_with(
                "abc",
                "verifier",
                redirect_uri=web_backend.OPENAI_CODEX_REDIRECT_URI,
            )

    def test_openai_codex_oauth_session_status_reports_single_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            session = OpenAICodexOAuthSession(
                verifier="verifier",
                state="state",
                auth_url="https://auth.openai.com/oauth/authorize",
            )

            with mock.patch.dict(
                "grant_agent.web_backend._OPENAI_CODEX_OAUTH_SESSIONS",
                {"active": session},
                clear=True,
            ):
                result = backend.dispatch("get_openai_codex_oauth_session_command", {})

            self.assertTrue(result["active"])
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["sessionId"], "active")

    def test_account_config_is_local_and_password_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            self.assertEqual(backend.username, "admin")
            self.assertTrue((root / ".agent_control" / "grand_agent_web_admin.json").exists())
            self.assertTrue((root / ".agent_control" / "grand_agent_admin_password.txt").exists())
            self.assertIsNone(backend.login({"username": "admin", "password": "wrong"}))
            password_text = (root / ".agent_control" / "grand_agent_admin_password.txt").read_text(
                encoding="utf-8"
            )
            password_line = next(line for line in password_text.splitlines() if line.startswith("Password: "))
            token = backend.login(
                {
                    "username": " Admin ",
                    "password": password_line.replace("Password: ", "", 1),
                }
            )
            self.assertIsInstance(token, str)
            self.assertEqual(backend.sessions[str(token)]["role"], "account")

    def test_additional_local_user_can_login(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            _, password, password_path = add_or_reset_admin_user(
                root,
                username="paul",
                display_name="Paul",
            )
            backend = FluxioWebBackend(root, root)

            self.assertTrue(password_path.exists())
            self.assertIsNone(backend.login({"username": "paul", "password": "wrong"}))
            token = backend.login({"username": "paul", "password": password})
            self.assertIsInstance(token, str)
            self.assertEqual(backend.sessions[str(token)]["displayName"], "Paul")

    def test_auth_status_exposes_local_account_hints_without_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            add_or_reset_admin_user(root, username="theo", display_name="Theo")
            backend = FluxioWebBackend(root, root)

            class DummyHeaders:
                def get(self, _key: str) -> str:
                    return ""

            class DummyHandler:
                def __init__(self) -> None:
                    self.headers = DummyHeaders()

            status = backend.session_status(DummyHandler())
            self.assertFalse(status["authenticated"])
            self.assertIsNone(status["user"])
            hints = status.get("accountHints")
            self.assertIsInstance(hints, list)
            usernames = [item.get("username") for item in hints if isinstance(item, dict)]
            self.assertIn("admin", usernames)
            self.assertIn("theo", usernames)

    def test_environment_account_aliases_can_login_without_writing_password_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            with mock.patch.dict(
                "os.environ",
                {
                    "SYNTELOS_ACCOUNT_USER": "theo",
                    "SYNTELOS_ACCOUNT_DISPLAY_NAME": "Theo",
                    "SYNTELOS_ACCOUNT_PASSWORD": "local-password",
                },
            ):
                backend = FluxioWebBackend(root, root)

            self.assertFalse((root / ".agent_control" / "grand_agent_admin_password.txt").exists())
            token = backend.login({"username": "theo", "password": "local-password"})
            self.assertIsInstance(token, str)
            self.assertEqual(backend.sessions[str(token)]["displayName"], "Theo")

    def test_public_https_url_is_written_to_password_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            FluxioWebBackend(root, root, public_url="https://syntelos.example.test")

            password_text = (root / ".agent_control" / "grand_agent_admin_password.txt").read_text(
                encoding="utf-8"
            )
            self.assertIn("URL: https://syntelos.example.test", password_text)

    def test_list_workspace_directory_command_returns_directory_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            workspace = root / "workspace"
            docs = workspace / "docs"
            workspace.mkdir()
            docs.mkdir()
            (workspace / "README.md").write_text("# test\n", encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "list_workspace_directory_command",
                {"path": str(workspace)},
            )

            self.assertEqual(result["currentPath"], str(workspace.resolve()))
            self.assertEqual(result["parentPath"], str(workspace.parent.resolve()))
            names = {(entry["name"], entry["isDirectory"]) for entry in result["entries"]}
            self.assertIn(("docs", True), names)
            self.assertIn(("README.md", False), names)
            self.assertIn(str(root.resolve()), result["roots"])

    def test_run_cli_sets_pythonpath_to_workspace_src(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "src").mkdir(parents=True)

            completed = mock.Mock()
            completed.returncode = 0
            completed.stdout = "{}"
            completed.stderr = ""
            with mock.patch("grant_agent.web_backend.subprocess.run", return_value=completed) as run_mock:
                from grant_agent import web_backend

                web_backend._run_cli(root, "control-room", [], timeout=1)

            called_env = run_mock.call_args.kwargs["env"]
            self.assertIn("PYTHONPATH", called_env)
            self.assertTrue(str(root / "src") in called_env["PYTHONPATH"])

    def test_control_room_summary_command_uses_in_process_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_build_control_room_summary",
                return_value={"schema": "fluxio.control_room.summary.v1"},
            ) as build_summary:
                result = backend.dispatch(
                    "get_control_room_summary_command",
                    {"root": str(root)},
                )

            self.assertEqual(result["schema"], "fluxio.control_room.summary.v1")
            self.assertEqual(result["webBackend"]["commandSurface"], "http")
            self.assertEqual(result["summaryCache"]["mode"], "full")
            self.assertEqual(result["summaryCache"]["status"], "miss")
            self.assertEqual(build_summary.call_args.args[0], root.resolve())

    def test_control_room_summary_command_caches_full_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_build_control_room_summary",
                return_value={
                    "schema": "fluxio.control_room.summary.v1",
                    "missions": [{"mission_id": "mission_live", "status": "running"}],
                },
            ) as build_summary:
                with mock.patch.object(backend, "_start_mission_detail_prewarm_timer"):
                    result = backend.dispatch(
                        "get_control_room_summary_command",
                        {"root": str(root)},
                    )
                    cached_result = backend.dispatch(
                        "get_control_room_summary_command",
                        {"root": str(root)},
                    )

            self.assertEqual(result["summaryCache"]["status"], "miss")
            self.assertEqual(cached_result["summaryCache"]["status"], "hit")
            self.assertEqual(cached_result["summaryCache"]["mode"], "full")
            self.assertEqual(build_summary.call_count, 1)

    def test_control_room_summary_command_loads_matching_persisted_full_snapshot_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_build_control_room_summary",
                return_value={
                    "schema": "fluxio.control_room.summary.v1",
                    "missions": [{"mission_id": "mission_live", "status": "running"}],
                },
            ):
                first = backend.dispatch(
                    "get_control_room_summary_command",
                    {"root": str(root)},
                )

            restarted_backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                restarted_backend,
                "_build_control_room_summary",
                side_effect=AssertionError("persisted matching summary should avoid rebuild"),
            ):
                persisted = restarted_backend.dispatch(
                    "get_control_room_summary_command",
                    {"root": str(root)},
                )

            self.assertEqual(first["summaryCache"]["status"], "miss")
            self.assertEqual(persisted["summaryCache"]["status"], "disk-hit")
            self.assertEqual(persisted["summaryCache"]["freshness"], "control-files-matched")
            self.assertEqual(persisted["missions"][0]["mission_id"], "mission_live")

    def test_control_room_summary_cache_signature_includes_watchdog_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            backend = FluxioWebBackend(root, root)
            before = backend._control_room_freshness_signature(root)
            (control_dir / "mission_watchdog.json").write_text(
                '{"schema":"fluxio.mission_watchdog.v1"}',
                encoding="utf-8",
            )
            after = backend._control_room_freshness_signature(root)

            self.assertNotEqual(before, after)
            self.assertTrue(any("mission_watchdog.json" in row[0] and row[2] > 0 for row in after))

    def test_control_room_summary_cache_signature_includes_runtime_compartments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            compartment_dir = root / ".agent_control" / "runtime_compartments"
            compartment_dir.mkdir(parents=True)
            backend = FluxioWebBackend(root, root)
            before = backend._control_room_freshness_signature(root)
            (compartment_dir / "mission-chat-mission_live.json").write_text(
                json.dumps(
                    {
                        "sessionId": "mission-chat-mission_live",
                        "runtime": "hermes",
                        "messages": [{"role": "operator", "text": "Continue the mission."}],
                    }
                ),
                encoding="utf-8",
            )
            after = backend._control_room_freshness_signature(root)

            self.assertNotEqual(before, after)
            self.assertTrue(any("mission-chat-mission_live.json" in row[0] and row[2] > 0 for row in after))

    def test_control_room_summary_cache_signature_includes_connected_app_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True)
            backend = FluxioWebBackend(root, root)
            before = backend._control_room_freshness_signature(root)
            (config_dir / "connected_apps.json").write_text(
                json.dumps(
                    [
                        {
                            "manifest_id": "manifest_mind_tower",
                            "schema_version": "fluxio.app-capability/v0-draft",
                            "app_id": "mind-tower",
                            "name": "Mind Tower",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            after = backend._control_room_freshness_signature(root)

            self.assertNotEqual(before, after)
            self.assertTrue(any("connected_apps.json" in row[0] and row[2] > 0 for row in after))

    def test_bootstrap_summary_cache_uses_live_signature_instead_of_short_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            backend = FluxioWebBackend(root, root)
            build_count = 0

            def build_summary(active: int = 1) -> dict[str, object]:
                nonlocal build_count
                build_count += 1
                return {
                    "schema": "fluxio.control_room.summary.v1",
                    "summaryMode": "bootstrap",
                    "counts": {"activeMissions": active},
                    "missions": [{"mission_id": f"mission_{build_count}", "status": "running"}],
                    "performance": {
                        "durationMs": 300,
                        "payloadBytes": 64,
                        "budget": {"itemLimits": {"missions": active}},
                    },
                }

            with (
                mock.patch("grant_agent.web_backend.BOOTSTRAP_SUMMARY_CACHE_TTL_SECONDS", 0.0),
                mock.patch.object(backend, "_build_control_room_bootstrap_summary", side_effect=build_summary),
            ):
                first = backend.dispatch(
                    "get_control_room_summary_command",
                    {"root": str(root), "summaryMode": "bootstrap"},
                )
                second = backend.dispatch(
                    "get_control_room_summary_command",
                    {"root": str(root), "summaryMode": "bootstrap"},
                )
                (control_dir / "mission_events.jsonl").write_text(
                    '{"kind":"mission.updated"}\n',
                    encoding="utf-8",
                )
                third = backend.dispatch(
                    "get_control_room_summary_command",
                    {"root": str(root), "summaryMode": "bootstrap"},
                )

            self.assertEqual(first["summaryCache"]["status"], "miss")
            self.assertEqual(second["summaryCache"]["status"], "hit")
            self.assertEqual(second["summaryCache"]["freshness"], "control-files-matched")
            self.assertEqual(second["missions"][0]["mission_id"], "mission_1")
            self.assertEqual(third["summaryCache"]["status"], "miss")
            self.assertEqual(third["missions"][0]["mission_id"], "mission_2")
            self.assertEqual(build_count, 2)

    def test_bootstrap_summary_cache_persists_across_backend_restart_when_signature_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / ".agent_control").mkdir(parents=True)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_build_control_room_bootstrap_summary",
                return_value={
                    "schema": "fluxio.control_room.summary.v1",
                    "summaryMode": "bootstrap",
                    "missions": [{"mission_id": "mission_live", "status": "running"}],
                    "performance": {
                        "durationMs": 300,
                        "payloadBytes": 64,
                        "budget": {"itemLimits": {"missions": 1}},
                    },
                },
            ):
                first = backend.dispatch(
                    "get_control_room_summary_command",
                    {"root": str(root), "summaryMode": "bootstrap"},
                )

            restarted_backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                restarted_backend,
                "_build_control_room_bootstrap_summary",
                side_effect=AssertionError("matching persisted bootstrap summary should avoid rebuild"),
            ):
                persisted = restarted_backend.dispatch(
                    "get_control_room_summary_command",
                    {"root": str(root), "summaryMode": "bootstrap"},
                )

            self.assertEqual(first["summaryCache"]["status"], "miss")
            self.assertEqual(persisted["summaryCache"]["status"], "disk-hit")
            self.assertEqual(persisted["summaryCache"]["freshness"], "control-files-matched")
            self.assertEqual(persisted["missions"][0]["mission_id"], "mission_live")
            self.assertLess(float(persisted["performance"]["durationMs"]), 50)

    def test_control_room_summary_command_serves_stale_full_snapshot_while_revalidating(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_build_control_room_summary",
                return_value={"schema": "fluxio.control_room.summary.v1", "missions": []},
            ):
                result = backend.dispatch(
                    "get_control_room_summary_command",
                    {"root": str(root)},
                )
            with (
                mock.patch("grant_agent.web_backend.FULL_SUMMARY_CACHE_TTL_SECONDS", 0.0),
                mock.patch("grant_agent.web_backend.FULL_SUMMARY_STALE_WHILE_REVALIDATE_SECONDS", 30.0),
                mock.patch.object(backend, "_start_control_room_summary_revalidate") as start_revalidate,
            ):
                stale_result = backend.dispatch(
                    "get_control_room_summary_command",
                    {"root": str(root)},
                )

            self.assertEqual(result["summaryCache"]["status"], "miss")
            self.assertEqual(stale_result["summaryCache"]["status"], "stale-while-revalidate")
            self.assertEqual(stale_result["summaryCache"]["mode"], "full")
            self.assertIn(stale_result["summaryCache"]["freshness"], {"control-files-matched", "control-files-changed"})
            start_revalidate.assert_called_once()

    def test_control_room_summary_command_supports_bootstrap_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_build_control_room_bootstrap_summary",
                return_value={
                    "schema": "fluxio.control_room.summary.v1",
                    "summaryMode": "bootstrap",
                    "missions": [{"mission_id": "mission_live", "title": "Live mission", "status": "running"}],
                    "notifications": [{"kind": "mission_slice_completed", "title": "Slice completed"}],
                },
            ) as build_bootstrap:
                with (
                    mock.patch("grant_agent.web_backend.MISSION_DETAIL_PREWARM_ENABLED", True),
                    mock.patch.object(backend, "_start_mission_detail_prewarm_timer") as start_prewarm,
                ):
                    result = backend.dispatch(
                        "get_control_room_summary_command",
                        {"root": str(root), "summaryMode": "bootstrap"},
                    )
                    cached_result = backend.dispatch(
                        "get_control_room_summary_command",
                        {"root": str(root), "summaryMode": "bootstrap"},
                    )

            self.assertEqual(result["schema"], "fluxio.control_room.summary.v1")
            self.assertEqual(result["summaryMode"], "bootstrap")
            self.assertEqual(result["missions"][0]["title"], "Live mission")
            self.assertEqual(result["summaryCache"]["status"], "miss")
            self.assertEqual(cached_result["summaryCache"]["status"], "hit")
            self.assertEqual(cached_result["missions"][0]["title"], "Live mission")
            self.assertEqual(result["webBackend"]["commandSurface"], "http")
            self.assertEqual(build_bootstrap.call_args.args[0], root.resolve())
            self.assertEqual(build_bootstrap.call_count, 1)
            self.assertEqual(start_prewarm.call_count, 1)
            self.assertEqual(start_prewarm.call_args.args[1], "mission_live")

    def test_control_room_summary_prewarm_is_delayed_not_inline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(backend, "_cached_control_room_mission_detail") as build_detail:
                with mock.patch("grant_agent.web_backend.threading.Timer") as timer:
                    with mock.patch("grant_agent.web_backend.MISSION_DETAIL_PREWARM_ENABLED", True):
                        timer.return_value = mock.Mock()
                        backend._prewarm_control_room_mission_details(
                            root,
                            {
                                "missions": [
                                    {"mission_id": "mission_a", "status": "running"},
                                    {"mission_id": "mission_b", "status": "completed"},
                                ]
                            },
                        )

            build_detail.assert_not_called()
            timer.assert_called_once()
            self.assertGreater(timer.call_args.args[0], 0)
            self.assertEqual(timer.call_args.kwargs["args"][1], "mission_a")
            timer.return_value.start.assert_called_once()

    def test_control_room_summary_prewarm_is_enabled_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(backend, "_cached_control_room_mission_detail") as build_detail:
                with mock.patch("grant_agent.web_backend.threading.Timer") as timer:
                    timer.return_value = mock.Mock()
                    backend._prewarm_control_room_mission_details(
                        root,
                        {"missions": [{"mission_id": "mission_a", "status": "running"}]},
                    )

            build_detail.assert_not_called()
            timer.assert_called_once()
            timer.return_value.start.assert_called_once()

    def test_control_room_summary_prewarm_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(backend, "_cached_control_room_mission_detail") as build_detail:
                with mock.patch("grant_agent.web_backend.threading.Timer") as timer:
                    with mock.patch("grant_agent.web_backend.MISSION_DETAIL_PREWARM_ENABLED", False):
                        backend._prewarm_control_room_mission_details(
                            root,
                            {"missions": [{"mission_id": "mission_a", "status": "running"}]},
                        )

            build_detail.assert_not_called()
            timer.assert_not_called()

    def test_control_room_snapshot_command_uses_full_live_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_run_cli",
                return_value={"schema": "fluxio.control_room.snapshot.v1", "skillLibrary": {"items": ["live"]}},
            ) as run_cli:
                result = backend.dispatch(
                    "get_control_room_snapshot_command",
                    {"root": str(root)},
                )

            self.assertEqual(result["skillLibrary"]["items"], ["live"])
            self.assertEqual(result["webBackend"]["commandSurface"], "http")
            self.assertEqual(run_cli.call_args.args[1], "control-room")
            self.assertEqual(run_cli.call_args.kwargs["timeout"], 180)
            self.assertFalse(run_cli.call_args.kwargs["fast_control_room"])

    def test_control_room_mission_detail_command_uses_in_process_live_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_cached_control_room_mission_detail",
                return_value={"schema": "fluxio.control_room.mission_detail.v1"},
            ) as build_detail:
                with mock.patch.object(backend, "_run_cli") as run_cli:
                    result = backend.dispatch(
                        "get_control_room_mission_detail_command",
                        {"root": str(root), "missionId": "mission_123", "eventLimit": 12},
                    )

            self.assertEqual(result["schema"], "fluxio.control_room.mission_detail.v1")
            self.assertEqual(result["webBackend"]["commandSurface"], "http")
            self.assertEqual(build_detail.call_args.args[0], root.resolve())
            self.assertEqual(build_detail.call_args.kwargs["mission_id"], "mission_123")
            self.assertEqual(build_detail.call_args.kwargs["event_limit"], 12)
            run_cli.assert_not_called()

    def test_control_room_mission_detail_command_rejects_missing_mission_id_before_store_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(backend, "_cached_control_room_mission_detail") as build_detail:
                with self.assertRaises(RuntimeError):
                    backend.dispatch(
                        "get_control_room_mission_detail_command",
                        {"root": str(root), "eventLimit": 12},
                    )

            build_detail.assert_not_called()

    def test_control_room_mission_detail_command_normalizes_event_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_cached_control_room_mission_detail",
                return_value={"schema": "fluxio.control_room.mission_detail.v1"},
            ) as build_detail:
                result = backend.dispatch(
                    "get_control_room_mission_detail_command",
                    {"root": str(root), "missionId": "mission_123", "eventLimit": 0},
                )

            self.assertEqual(result["schema"], "fluxio.control_room.mission_detail.v1")
            self.assertEqual(build_detail.call_args.kwargs["event_limit"], 80)

    def test_control_room_mission_detail_cache_reuses_matching_live_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            payload = {
                "schema": "fluxio.control_room.mission_detail.v1",
                "performance": {
                    "source": "control_room_mission_detail",
                    "durationMs": 310.0,
                    "payloadBytes": 64,
                },
            }
            with mock.patch.object(
                backend,
                "_control_room_freshness_signature",
                return_value=(("missions.json", 1, 10),),
            ):
                with mock.patch.object(
                    backend,
                    "_build_control_room_mission_detail",
                    return_value=payload,
                ) as build_detail:
                    first = backend._cached_control_room_mission_detail(
                        root,
                        mission_id="mission_123",
                        event_limit=12,
                    )
                    second = backend._cached_control_room_mission_detail(
                        root,
                        mission_id="mission_123",
                        event_limit=12,
                    )

            self.assertEqual(build_detail.call_count, 1)
            self.assertEqual(first["performance"]["missionDetailCache"]["status"], "miss")
            self.assertEqual(second["performance"]["missionDetailCache"]["status"], "hit")
            self.assertEqual(second["performance"]["budget"]["status"], "pass")
            self.assertEqual(second["performance"]["budget"]["itemLimits"]["events"], 12)

    def test_control_room_mission_detail_cache_invalidates_when_live_signature_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            signatures = [
                (("missions.json", 1, 10),),
                (("missions.json", 2, 10),),
            ]
            with mock.patch.object(
                backend,
                "_control_room_freshness_signature",
                side_effect=signatures,
            ):
                with mock.patch("grant_agent.web_backend.MISSION_DETAIL_STALE_WHILE_REVALIDATE_SECONDS", 0):
                    with mock.patch.object(
                        backend,
                        "_build_control_room_mission_detail",
                        return_value={"schema": "fluxio.control_room.mission_detail.v1"},
                    ) as build_detail:
                        backend._cached_control_room_mission_detail(
                            root,
                            mission_id="mission_123",
                            event_limit=12,
                        )
                        backend._cached_control_room_mission_detail(
                            root,
                            mission_id="mission_123",
                            event_limit=12,
                        )

            self.assertEqual(build_detail.call_count, 2)

    def test_control_room_mission_detail_cache_serves_short_stale_hit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            signatures = [
                (("events.jsonl", 1, 10),),
                (("events.jsonl", 2, 11),),
            ]
            with mock.patch.object(
                backend,
                "_control_room_freshness_signature",
                side_effect=signatures,
            ):
                with mock.patch.object(
                    backend,
                    "_build_control_room_mission_detail",
                    return_value={"schema": "fluxio.control_room.mission_detail.v1"},
                ) as build_detail:
                    first = backend._cached_control_room_mission_detail(
                        root,
                        mission_id="mission_123",
                        event_limit=12,
                    )
                    with mock.patch.object(
                        backend,
                        "_queue_mission_detail_cache_refresh",
                    ) as refresh_detail:
                        second = backend._cached_control_room_mission_detail(
                            root,
                            mission_id="mission_123",
                            event_limit=12,
                        )

            self.assertEqual(build_detail.call_count, 1)
            self.assertEqual(first["performance"]["missionDetailCache"]["status"], "miss")
            self.assertEqual(second["performance"]["missionDetailCache"]["status"], "hit")
            self.assertEqual(
                second["performance"]["missionDetailCache"]["freshness"],
                "stale-while-revalidate",
            )
            refresh_detail.assert_called_once()

    def test_control_room_mission_detail_waits_for_active_prewarm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            signature = (("missions.json", 1, 10),)
            prewarm_key = backend._mission_detail_cache_key(root, "mission_123", 80)
            payload = {
                "schema": "fluxio.control_room.mission_detail.v1",
                "missionId": "mission_123",
                "performance": {
                    "source": "control_room_mission_detail",
                    "durationMs": 42.0,
                    "payloadBytes": 64,
                },
            }
            backend._mission_detail_prewarm_keys.add(prewarm_key)

            def store_prewarmed_payload() -> None:
                backend._store_mission_detail_cache(prewarm_key, signature, payload)
                with backend._mission_detail_cache_lock:
                    backend._mission_detail_prewarm_keys.discard(prewarm_key)

            timer = threading.Timer(0.03, store_prewarmed_payload)
            timer.daemon = True
            timer.start()
            try:
                with mock.patch.object(
                    backend,
                    "_control_room_freshness_signature",
                    return_value=signature,
                ):
                    with mock.patch.object(
                        backend,
                        "_build_control_room_mission_detail",
                    ) as build_detail:
                        with mock.patch("grant_agent.web_backend.MISSION_DETAIL_PREWARM_WAIT_SECONDS", 0.2):
                            detail = backend._cached_control_room_mission_detail(
                                root,
                                mission_id="mission_123",
                                event_limit=80,
                            )
            finally:
                timer.join(0.2)

            build_detail.assert_not_called()
            self.assertEqual(detail["missionId"], "mission_123")
            self.assertEqual(detail["performance"]["missionDetailCache"]["status"], "hit")

    def test_control_room_mission_detail_request_cancels_pending_prewarm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            prewarm_key = backend._mission_detail_cache_key(root, "mission_123", 80)
            backend._mission_detail_prewarm_keys.add(prewarm_key)
            with mock.patch.object(
                backend,
                "_control_room_freshness_signature",
                return_value=(("missions.json", 1, 10),),
            ):
                with mock.patch.object(
                    backend,
                    "_build_control_room_mission_detail",
                    return_value={"schema": "fluxio.control_room.mission_detail.v1"},
                ) as build_detail:
                    with mock.patch("grant_agent.web_backend.MISSION_DETAIL_PREWARM_WAIT_SECONDS", 0):
                        backend._cached_control_room_mission_detail(
                            root,
                            mission_id="mission_123",
                            event_limit=80,
                        )
                        backend._run_mission_detail_prewarm(root, "mission_123", prewarm_key)

            self.assertEqual(build_detail.call_count, 1)
            self.assertNotIn(prewarm_key, backend._mission_detail_prewarm_keys)

    def test_export_mission_proof_digest_command_writes_reviewable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_run_cli",
                return_value={"ok": True, "missionId": "mission_123", "reportPath": "digest.md"},
            ) as run_cli:
                result = backend.dispatch(
                    "export_mission_proof_digest_command",
                    {"root": str(root), "missionId": "mission_123"},
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result["reportPath"], "digest.md")
            self.assertEqual(run_cli.call_args.args[1], "mission-proof-digest")
            self.assertEqual(run_cli.call_args.args[2], ["--mission-id", "mission_123"])
            self.assertEqual(run_cli.call_args.kwargs["timeout"], 120)

    def test_export_control_room_data_command_is_available_on_web_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_run_cli",
                return_value={"ok": True, "exportPath": "control-room.json"},
            ) as run_cli:
                result = backend.dispatch("export_control_room_data_command", {"root": str(root)})

            self.assertTrue(result["ok"])
            self.assertEqual(result["exportPath"], "control-room.json")
            self.assertEqual(run_cli.call_args.args[1], "control-room-export")
            self.assertEqual(run_cli.call_args.kwargs["timeout"], 180)

    def test_apply_skill_repair_command_is_available_on_web_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            with mock.patch.object(
                backend,
                "_run_cli",
                return_value={"ok": True, "receipt": {"status": "applied"}},
            ) as run_cli:
                result = backend.dispatch(
                    "apply_skill_repair_command",
                    {
                        "proposalId": "skill_repair:learned_risky_runner",
                        "skillId": "learned_risky_runner",
                        "reviewer": "operator",
                    },
                )

            self.assertTrue(result["ok"])
            self.assertEqual(run_cli.call_args.args[1], "skill-repair-apply")
            self.assertIn("--proposal-id", run_cli.call_args.args[2])
            self.assertIn("--skill-id", run_cli.call_args.args[2])
            self.assertEqual(run_cli.call_args.kwargs["timeout"], 120)

    def test_mission_anti_drift_guard_command_writes_watchdog_proof_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            (control_dir / "mission_watchdog.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.mission_watchdog.v1",
                        "summary": {
                            "issueCount": 3,
                            "bad": 1,
                            "warn": 2,
                            "artifactMissing": 1,
                            "artifactPartial": 0,
                            "queuePressure": 1,
                        },
                        "issues": [
                            {
                                "kind": "mission_blocked_or_failed",
                                "severity": "bad",
                                "title": "Mission is blocked or failed",
                                "detail": "The mission cannot continue without repair.",
                                "firstStep": "Resume the Hermes lane after inspecting logs.",
                            },
                            {
                                "kind": "route_contract_incomplete",
                                "severity": "info",
                                "title": "Mission route contract is incomplete",
                                "firstStep": "Apply the task-aware route contract.",
                            },
                            {
                                "kind": "planned_scope_artifacts_not_ready",
                                "severity": "warn",
                                "title": "Completed mission artifact scope is not ready",
                            },
                        ],
                        "nextAction": "Repair the first watchdog issue.",
                    }
                ),
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "get_mission_anti_drift_guard_command",
                {"root": str(root), "requestId": "mission4-test"},
            )

            self.assertEqual(result["schema"], "fluxio.mission_anti_drift_guard.v1")
            self.assertEqual(result["primaryRuntimeLane"], "hermes")
            self.assertEqual(result["fallbackRuntimeLane"], "openclaw")
            self.assertEqual(result["status"], "intervention_required")
            self.assertEqual(result["summary"]["blockedLoopCount"], 1)
            self.assertEqual(result["summary"]["routeMismatchCount"], 1)
            self.assertGreaterEqual(result["summary"]["proofGapCount"], 2)
            self.assertTrue(result["routeProof"]["sourceReportPresent"])
            proof_path = pathlib.Path(result["proof"]["artifactPath"])
            self.assertTrue(proof_path.exists())
            self.assertIn("mission_anti_drift_guard", proof_path.read_text(encoding="utf-8"))

    def test_mission_anti_drift_guard_waits_when_no_monitoring_state_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "get_mission_anti_drift_guard_command",
                {"root": str(root), "requestId": "mission4-no-state"},
            )

            self.assertEqual(result["schema"], "fluxio.mission_anti_drift_guard.v1")
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "waiting_for_watchdog_evidence")
            self.assertEqual(result["missionGate"]["status"], "incomplete")
            self.assertEqual(result["missionGate"]["items"][0]["id"], "live-state-inspection")
            self.assertEqual(result["missionGate"]["items"][0]["status"], "blocked")

    def test_mission_anti_drift_guard_detects_local_state_intervention_without_watchdog_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            control_dir = root / ".agent_control"
            control_dir.mkdir(parents=True)
            stale_updated_at = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
            (control_dir / "missions.json").write_text(
                json.dumps(
                    [
                        {
                            "mission_id": "mission_stale",
                            "runtime_id": "hermes",
                            "objective": "Finish the current mission without drifting.",
                            "updated_at": stale_updated_at,
                            "state": {"status": "running"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            gate_dir = control_dir / "harness_quality_gate" / "latest"
            gate_dir.mkdir(parents=True)
            (gate_dir / "mission_completion_gate.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.mission_completion_gate.v1",
                        "mission": "mission3-harness-quality",
                        "status": "blocked",
                        "nextMissing": {
                            "id": "pre-completion-verification",
                            "label": "Pre-completion verifier has passing evidence",
                            "proof": "Attach a real proof artifact.",
                        },
                    }
                ),
                encoding="utf-8",
            )
            route_dir = control_dir / "runtime_route_unification" / "latest"
            route_dir.mkdir(parents=True)
            (route_dir / "contract.json").write_text(
                json.dumps(
                    {
                        "schema": "fluxio.runtime_route_unification.v1",
                        "status": "complete",
                        "selectedRuntime": "opencode",
                        "health": {
                            "calls": {
                                "hermes": {"status": "failed"},
                                "opencode": {"status": "ok"},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "get_mission_anti_drift_guard_command",
                {
                    "root": str(root),
                    "requestId": "mission4-local-state",
                    "staleMinutes": 30,
                },
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "intervention_required")
            self.assertEqual(result["monitoringLoop"]["liveMissionCount"], 1)
            self.assertEqual(result["monitoringLoop"]["staleActiveMissionCount"], 1)
            self.assertEqual(result["summary"]["driftRiskCount"], 2)
            self.assertEqual(result["summary"]["routeMismatchCount"], 1)
            self.assertGreaterEqual(result["summary"]["proofGapCount"], 1)
            self.assertEqual(result["gateState"]["latestHarnessGateStatus"], "blocked")
            self.assertEqual(result["routeProof"]["selectedRuntime"], "opencode")
            self.assertTrue(result["intervention"]["required"])
            self.assertTrue(result["intervention"]["pauseNewMissions"])
            self.assertTrue(result["intervention"]["shouldSwitchRoute"])
            self.assertEqual(result["intervention"]["recommendedRuntime"], "opencode")
            self.assertEqual(result["missionGate"]["status"], "complete")
            proof_path = pathlib.Path(result["proof"]["artifactPath"])
            self.assertTrue(proof_path.exists())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "monitoring_anti_drift_runtime_guard")
            self.assertEqual(proof["missionGate"]["status"], "complete")

    def test_skill_runtime_contract_command_writes_runtime_proof_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "skills.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "repo_scan",
                            "description": "Ground the task in repo evidence.",
                            "schema": {
                                "type": "object",
                                "properties": {"taskBrief": {"type": "string"}},
                                "required": ["taskBrief"],
                            },
                            "permissions": ["file_read"],
                            "action_kinds": ["workspace_search"],
                            "execution_capable": True,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "get_skill_runtime_contract_command",
                {
                    "root": str(root),
                    "requestId": "mission5-test",
                    "taskBrief": "scan the repo before editing",
                    "skillId": "repo_scan",
                },
            )

            self.assertEqual(result["schema"], "fluxio.skill_runtime_contract.v1")
            self.assertEqual(result["primaryRuntimeLane"], "hermes")
            self.assertIn("openclaw", result["fallbackRuntimeLanes"])
            self.assertIn("opencode", result["fallbackRuntimeLanes"])
            self.assertEqual(result["skills"][0]["skillId"], "repo_scan")
            self.assertEqual(result["skills"][0]["route"]["runtimeLane"], "hermes")
            self.assertEqual(result["skills"][0]["output"]["schema"], "fluxio.skill_runtime_result.v1")
            proof_path = pathlib.Path(result["proof"]["artifactPath"])
            self.assertTrue(proof_path.exists())
            self.assertIn("skills_runtime_centralization_contract", proof_path.read_text(encoding="utf-8"))

    def test_run_skill_runtime_command_executes_workspace_search_and_writes_result_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "skills.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "workspace_search",
                            "description": "Search code and docs quickly to ground planning in project evidence.",
                            "schema": {
                                "type": "object",
                                "properties": {"query": {"type": "string"}},
                                "required": ["query"],
                            },
                            "permissions": ["file_read"],
                            "action_kinds": ["workspace_search"],
                            "execution_capable": True,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            src_dir = root / "src"
            src_dir.mkdir()
            (src_dir / "runtime_notes.py").write_text(
                "def route_skill():\n    return 'Hermes skill runtime centralization proof'\n",
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "run_skill_runtime_command",
                {
                    "root": str(root),
                    "requestId": "mission5-runtime-search",
                    "missionId": "mission5",
                    "skillId": "workspace_search",
                    "taskBrief": "Find Hermes skill runtime code",
                    "input": {"query": "Hermes skill runtime"},
                },
            )

            self.assertEqual(result["schema"], "fluxio.skill_runtime_result.v1")
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["skill"]["skillId"], "workspace_search")
            self.assertEqual(result["execution"]["mode"], "local_workspace_search")
            self.assertGreaterEqual(result["execution"]["matchCount"], 1)
            self.assertEqual(result["missionGate"]["status"], "complete")
            proof_path = pathlib.Path(result["proof"]["artifactPath"])
            self.assertTrue(proof_path.exists())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof"]["purpose"], "skill_runtime_execution_result")
            self.assertEqual(proof["missionGate"]["status"], "complete")
            usage_path = root / ".agent_control" / "skill_usage.json"
            self.assertTrue(usage_path.exists())
            self.assertIn("workspace_search", usage_path.read_text(encoding="utf-8"))

    def test_run_skill_runtime_command_blocks_missing_required_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "skills.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "workspace_search",
                            "description": "Search code and docs quickly to ground planning in project evidence.",
                            "schema": {
                                "type": "object",
                                "properties": {"query": {"type": "string"}},
                                "required": ["query"],
                            },
                            "permissions": ["file_read"],
                            "action_kinds": ["workspace_search"],
                            "execution_capable": True,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "run_skill_runtime_command",
                {
                    "root": str(root),
                    "requestId": "mission5-missing-input",
                    "missionId": "mission5",
                    "skillId": "workspace_search",
                    "input": {},
                },
            )

            self.assertEqual(result["schema"], "fluxio.skill_runtime_result.v1")
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "blocked")
            self.assertIn("query", result["input"]["missing"])
            self.assertEqual(result["missionGate"]["status"], "blocked")
            proof_path = pathlib.Path(result["proof"]["artifactPath"])
            self.assertTrue(proof_path.exists())
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["missionGate"]["status"], "blocked")

    def test_record_delivery_receipt_command_persists_browser_notification_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "record_delivery_receipt_command",
                {
                    "missionId": "mission_123",
                    "channel": "browser_notification",
                    "destination": "current_browser",
                    "eventKind": "overnight_progress_digest",
                    "eventMessage": "One mission can continue hands-free.",
                    "status": "delivered",
                },
            )

            self.assertEqual(result["mission_id"], "mission_123")
            self.assertEqual(result["channel"], "browser_notification")
            self.assertEqual(result["status"], "delivered")
            receipt_path = root / ".agent_control" / "delivery_receipts.jsonl"
            self.assertTrue(receipt_path.exists())
            self.assertIn("overnight_progress_digest", receipt_path.read_text(encoding="utf-8"))

    def test_record_delivery_receipt_command_persists_runtime_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "record_delivery_receipt_command",
                {
                    "missionId": "mission_hermes",
                    "channel": "telegram",
                    "destination": "operator",
                    "eventKind": "watchdog.problem_report",
                    "eventMessage": "No problem found.",
                    "status": "delivered",
                    "originRuntime": "hermes",
                    "originProvider": "minimax",
                    "originModel": "MiniMax-M3",
                    "transportProvider": "telegram_via_openclaw_token",
                    "producer": "watchdog",
                    "sourceSessionId": "session_123",
                },
            )

            self.assertEqual(result["origin_runtime"], "hermes")
            self.assertEqual(result["origin_provider"], "minimax")
            self.assertEqual(result["origin_model"], "MiniMax-M3")
            self.assertEqual(result["transport_provider"], "telegram_via_openclaw_token")
            self.assertEqual(result["producer"], "watchdog")
            receipt_text = (root / ".agent_control" / "delivery_receipts.jsonl").read_text(encoding="utf-8")
            self.assertIn("telegram_via_openclaw_token", receipt_text)

    def test_web_push_status_and_subscription_are_exposed_for_browser_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            subscription = {
                "endpoint": "https://push.example.test/subscription/123",
                "keys": {"p256dh": "client-public-key", "auth": "client-auth-secret"},
            }

            with mock.patch.dict(
                "os.environ",
                {"FLUXIO_WEB_PUSH_PUBLIC_KEY": "BFluxioPublicKey"},
                clear=False,
            ):
                status = backend.dispatch("get_web_push_status_command", {})

            self.assertTrue(status["configured"])
            self.assertFalse(status["senderConfigured"])
            self.assertEqual(status["publicKey"], "BFluxioPublicKey")

            receipt = backend.dispatch(
                "record_web_push_subscription_command",
                {
                    "subscription": subscription,
                    "userAgent": "Fluxio test browser",
                },
            )

            self.assertEqual(receipt["schema"], "fluxio.web_push_subscription.v1")
            self.assertEqual(receipt["endpoint"], subscription["endpoint"])
            self.assertTrue(receipt["subscription"]["keysPresent"])
            subscription_path = root / ".agent_control" / "web_push_subscriptions.jsonl"
            self.assertTrue(subscription_path.exists())
            self.assertIn("Fluxio test browser", subscription_path.read_text(encoding="utf-8"))

    def test_generate_web_push_vapid_config_command_provisions_local_sender_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "generate_web_push_vapid_config_command",
                {"subject": "mailto:operator@example.test"},
            )
            status = backend.dispatch("get_web_push_status_command", {})

            self.assertEqual(result["schema"], "fluxio.web_push_vapid_provisioning.v1")
            self.assertTrue(result["ok"])
            self.assertTrue(result["privateKeyConfigured"])
            self.assertTrue(status["configured"])
            self.assertTrue(status["privateKeyConfigured"])
            self.assertTrue(status["localKeyConfigured"])
            self.assertEqual(status["configuredSource"], "local_agent_control")
            self.assertEqual(status["publicKey"], result["publicKey"])
            self.assertIn("web_push_vapid.json", status["setupPath"])
            vapid_path = root / ".agent_control" / "web_push_vapid.json"
            self.assertTrue(vapid_path.exists())
            self.assertIn("BEGIN PRIVATE KEY", vapid_path.read_text(encoding="utf-8"))

    def test_send_web_push_notification_command_records_real_sender_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            backend.dispatch(
                "record_web_push_subscription_command",
                {
                    "subscription": {
                        "endpoint": "https://push.example.test/subscription/123",
                        "keys": {"p256dh": "client-public-key", "auth": "client-auth-secret"},
                    },
                    "userAgent": "Fluxio test browser",
                },
            )

            result = backend.dispatch(
                "send_web_push_notification_command",
                {
                    "missionId": "mission_123",
                    "title": "Slice complete",
                    "body": "Mission slice completed.",
                    "eventKind": "mission_slice_completed",
                },
            )

            self.assertEqual(result["schema"], "fluxio.web_push_delivery.v1")
            self.assertFalse(result["ok"])
            self.assertEqual(result["skippedCount"], 1)
            self.assertEqual(result["receipts"][0]["channel"], "web_push")
            self.assertIn(
                result["receipts"][0]["error_message"],
                {"web_push_vapid_keys_not_configured", "web_push_sender_dependency_missing"},
            )

    def test_ntfy_status_and_send_command_expose_open_source_phone_channel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            status = backend.dispatch("get_ntfy_status_command", {})
            self.assertEqual(status["schema"], "fluxio.ntfy_status.v1")
            self.assertFalse(status["configured"])
            self.assertEqual(status["channel"], "ntfy")

            skipped = backend.dispatch(
                "send_ntfy_notification_command",
                {
                    "missionId": "mission_123",
                    "title": "Slice complete",
                    "body": "Mission slice completed.",
                    "eventKind": "mission.slice.completed",
                    "dryRun": True,
                },
            )
            self.assertEqual(skipped["schema"], "fluxio.ntfy_delivery.v1")
            self.assertFalse(skipped["ok"])
            self.assertEqual(skipped["receipt"]["status"], "skipped")
            self.assertEqual(skipped["receipt"]["error_message"], "ntfy_topic_not_configured")

    def test_ntfy_send_command_records_dry_run_receipt_when_topic_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / ".agent_control").mkdir()
            (root / ".agent_control" / "ntfy_settings.json").write_text(
                json.dumps(
                    {
                        "serverUrl": "https://ntfy.example.test",
                        "topic": "fluxio-test",
                        "token": "secret-token",
                    }
                ),
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            status = backend.dispatch("get_ntfy_status_command", {})
            self.assertTrue(status["configured"])
            self.assertTrue(status["senderConfigured"])
            self.assertTrue(status["tokenConfigured"])
            self.assertEqual(status["topic"], "fluxio-test")

            result = backend.dispatch(
                "send_ntfy_notification_command",
                {
                    "missionId": "mission_123",
                    "title": "Slice complete",
                    "body": "Mission slice completed.",
                    "eventKind": "mission.slice.completed",
                    "targetUrl": "/control?mode=agent&surface=agent&missionId=mission_123",
                    "dryRun": True,
                },
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["receipt"]["channel"], "ntfy")
            self.assertEqual(result["receipt"]["status"], "delivered")
            self.assertEqual(result["receipt"]["delivery_url"], "dry_run://ntfy/fluxio-test")
            receipts_path = root / ".agent_control" / "delivery_receipts.jsonl"
            self.assertIn("mission.slice.completed", receipts_path.read_text(encoding="utf-8"))

    def test_send_web_push_notification_command_supports_dry_run_delivery_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            backend.dispatch(
                "record_web_push_subscription_command",
                {
                    "subscription": {
                        "endpoint": "https://push.example.test/subscription/123",
                        "keys": {"p256dh": "client-public-key", "auth": "client-auth-secret"},
                    },
                    "userAgent": "Fluxio test browser",
                },
            )

            with mock.patch.dict(
                "os.environ",
                {
                    "FLUXIO_WEB_PUSH_PUBLIC_KEY": "BFluxioPublicKey",
                    "FLUXIO_WEB_PUSH_PRIVATE_KEY": "FluxioPrivateKey",
                },
                clear=False,
            ):
                with mock.patch("grant_agent.delivery_receipt._web_push_dependency_available", return_value=True):
                    result = backend.dispatch(
                        "send_web_push_notification_command",
                        {
                            "missionId": "mission_123",
                            "title": "Slice complete",
                            "body": "Mission slice completed.",
                            "eventKind": "mission_slice_completed",
                            "dryRun": True,
                        },
                    )

            self.assertTrue(result["ok"])
            self.assertEqual(result["deliveredCount"], 1)
            self.assertEqual(result["receipts"][0]["status"], "delivered")
            self.assertEqual(result["receipts"][0]["delivery_url"].split("/", 1)[0], "dry_run:")

    def test_start_control_room_mission_command_uses_async_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.object(backend, "_run_cli", return_value={"ok": True}) as run_cli:
                result = backend.dispatch(
                    "start_control_room_mission_command",
                    {
                        "workspaceId": "workspace_123",
                        "runtime": "hermes",
                        "objective": "Run Golf 40 for 2 days.",
                        "mode": "Autopilot",
                        "budgetHours": 48,
                    },
                )

            self.assertEqual(result, {"ok": True})
            self.assertEqual(run_cli.call_args.args[1], "mission-start")
            command_args = run_cli.call_args.args[2]
            self.assertIn("--launch-async", command_args)
            self.assertEqual(
                run_cli.call_args.kwargs["timeout"],
                MISSION_START_TIMEOUT_SECONDS,
            )

    def test_apply_control_room_mission_action_resume_uses_async_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.object(backend, "_run_cli", return_value={"ok": True}) as run_cli:
                result = backend.dispatch(
                    "apply_control_room_mission_action_command",
                    {
                        "missionId": "mission_abc",
                        "action": "resume",
                    },
                )

            self.assertEqual(result, {"ok": True})
            self.assertEqual(run_cli.call_args.args[1], "mission-action")
            command_args = run_cli.call_args.args[2]
            self.assertIn("--launch-async", command_args)
            self.assertEqual(
                run_cli.call_args.kwargs["timeout"],
                MISSION_ACTION_TIMEOUT_SECONDS,
            )

    def test_apply_control_room_mission_action_extend_budget_can_resume_async(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.object(backend, "_run_cli", return_value={"ok": True}) as run_cli:
                result = backend.dispatch(
                    "apply_control_room_mission_action_command",
                    {
                        "missionId": "mission_budget",
                        "action": "extend-budget",
                        "budgetHours": 18,
                        "launchAsync": True,
                    },
                )

            self.assertEqual(result, {"ok": True})
            self.assertEqual(run_cli.call_args.args[1], "mission-action")
            command_args = run_cli.call_args.args[2]
            self.assertIn("extend-budget", command_args)
            self.assertIn("--budget-hours", command_args)
            self.assertIn("18", command_args)
            self.assertIn("--launch-async", command_args)
            self.assertEqual(
                run_cli.call_args.kwargs["timeout"],
                MISSION_ACTION_TIMEOUT_SECONDS,
            )

    def test_apply_control_room_mission_action_parallelize_worktree_can_launch_async(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.object(backend, "_run_cli", return_value={"ok": True}) as run_cli:
                result = backend.dispatch(
                    "apply_control_room_mission_action_command",
                    {
                        "missionId": "mission_queue",
                        "action": "parallelize-worktree",
                        "launchAsync": True,
                    },
                )

            self.assertEqual(result, {"ok": True})
            self.assertEqual(run_cli.call_args.args[1], "mission-action")
            command_args = run_cli.call_args.args[2]
            self.assertIn("parallelize-worktree", command_args)
            self.assertIn("--launch-async", command_args)
            self.assertEqual(
                run_cli.call_args.kwargs["timeout"],
                MISSION_ACTION_TIMEOUT_SECONDS,
            )

    def test_apply_control_room_mission_action_complete_forwards_operator_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.object(backend, "_run_cli", return_value={"ok": True}) as run_cli:
                result = backend.dispatch(
                    "apply_control_room_mission_action_command",
                    {
                        "missionId": "mission_done",
                        "action": "complete",
                        "operatorValueScore": 91,
                        "operatorOutcome": "useful",
                        "operatorCloseoutNote": "The artifact is ready to reuse.",
                    },
                )

            self.assertEqual(result, {"ok": True})
            self.assertEqual(run_cli.call_args.args[1], "mission-action")
            command_args = run_cli.call_args.args[2]
            self.assertIn("--operator-value-score", command_args)
            self.assertIn("91", command_args)
            self.assertIn("--operator-outcome", command_args)
            self.assertIn("useful", command_args)
            self.assertIn("--operator-closeout-note", command_args)
            self.assertIn("The artifact is ready to reuse.", command_args)

    def test_record_control_room_lane_control_uses_cli_receipt_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.object(backend, "_run_cli", return_value={"ok": True}) as run_cli:
                result = backend.dispatch(
                    "record_control_room_lane_control_command",
                    {
                        "missionId": "mission_lane",
                        "role": "executor",
                        "action": "open-proof",
                        "reason": "Operator opened proof.",
                    },
                )

            self.assertEqual(result, {"ok": True})
            self.assertEqual(run_cli.call_args.args[1], "mission-lane-control")
            command_args = run_cli.call_args.args[2]
            self.assertIn("--mission-id", command_args)
            self.assertIn("mission_lane", command_args)
            self.assertIn("--role", command_args)
            self.assertIn("executor", command_args)
            self.assertIn("--action", command_args)
            self.assertIn("open-proof", command_args)
            self.assertIn("--reason", command_args)
            self.assertIn("Operator opened proof.", command_args)

    def test_health_response_includes_security_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            FluxioWebBackend(root, root)

            class DummyHeaders:
                def get(self, key: str) -> str:
                    return ""

            class DummyHandler:
                def __init__(self) -> None:
                    self.headers = DummyHeaders()
                    self.headers_out: dict[str, str] = {}
                    self.wfile = io.BytesIO()

                def send_response(self, _status: int) -> None:
                    return

                def send_header(self, key: str, value: str) -> None:
                    self.headers_out[key] = value

                def end_headers(self) -> None:
                    return

            from grant_agent.web_backend import _json_response

            handler = DummyHandler()
            _json_response(handler, 200, {"ok": True})
            self.assertEqual(handler.headers_out.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(handler.headers_out.get("X-Frame-Options"), "DENY")
            self.assertEqual(handler.headers_out.get("Referrer-Policy"), "no-referrer")
            self.assertEqual(handler.headers_out.get("Cache-Control"), "no-store")

    def test_static_manifest_uses_installable_pwa_content_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "manifest.webmanifest").write_text(
                '{"display":"standalone"}',
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            class DummyHandler:
                path = "/manifest.webmanifest"

                def __init__(self) -> None:
                    self.headers_out: dict[str, str] = {}
                    self.wfile = io.BytesIO()

                def send_response(self, status: int) -> None:
                    self.headers_out["Status"] = str(status)

                def send_header(self, key: str, value: str) -> None:
                    self.headers_out[key] = value

                def end_headers(self) -> None:
                    return

            handler = DummyHandler()
            self.assertTrue(backend.serve_file(handler))
            self.assertEqual(handler.headers_out.get("Status"), "200")
            self.assertEqual(
                handler.headers_out.get("Content-Type"),
                "application/manifest+json; charset=utf-8",
            )
            self.assertIn(b"standalone", handler.wfile.getvalue())

    def test_static_shell_and_service_worker_are_not_browser_cached(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "index.html").write_text("<html></html>", encoding="utf-8")
            (root / "service-worker.js").write_text("self.skipWaiting();", encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets" / "app.js").write_text("console.log('ok');", encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            class DummyHandler:
                def __init__(self, path: str) -> None:
                    self.path = path
                    self.headers_out: dict[str, str] = {}
                    self.wfile = io.BytesIO()

                def send_response(self, status: int) -> None:
                    self.headers_out["Status"] = str(status)

                def send_header(self, key: str, value: str) -> None:
                    self.headers_out[key] = value

                def end_headers(self) -> None:
                    return

            index_handler = DummyHandler("/control")
            self.assertTrue(backend.serve_file(index_handler))
            self.assertEqual(index_handler.headers_out.get("Cache-Control"), "no-store")

            worker_handler = DummyHandler("/service-worker.js")
            self.assertTrue(backend.serve_file(worker_handler))
            self.assertEqual(worker_handler.headers_out.get("Cache-Control"), "no-store")

            asset_handler = DummyHandler("/assets/app.js")
            self.assertTrue(backend.serve_file(asset_handler))
            self.assertEqual(asset_handler.headers_out.get("Cache-Control"), "no-store")

            nested_asset_handler = DummyHandler("/control/assets/app.js")
            self.assertTrue(backend.serve_file(nested_asset_handler))
            self.assertEqual(nested_asset_handler.headers_out.get("Content-Type"), "text/javascript; charset=utf-8")
            self.assertNotIn(b"<html", nested_asset_handler.wfile.getvalue().lower())
            self.assertIn(b"console.log('ok');", nested_asset_handler.wfile.getvalue())

    def test_main_refuses_duplicate_backend_port(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            with mock.patch(
                "grant_agent.web_backend.tcp_port_accepts_connection",
                return_value=True,
            ):
                result = web_backend.main(
                    [
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "47880",
                        "--root",
                        str(root),
                        "--static-root",
                        str(root),
                    ]
                )

            self.assertEqual(result, 98)


if __name__ == "__main__":
    unittest.main()
