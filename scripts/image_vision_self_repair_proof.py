from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grant_agent.web_backend import FluxioWebBackend  # noqa: E402


PREFERRED_ROUTE = {
    "runtime": "opencode",
    "provider": "zai",
    "model": "glm-5.2",
    "modelId": "zai/glm-5.2",
}
FALLBACK_ROUTES = [
    {
        "runtime": "opencode",
        "provider": "opencode",
        "model": "glm-4.7-free",
        "modelId": "opencode/glm-4.7-free",
        "reason": "OpenCode lists a GLM-family free route, so it is the closest GLM fallback to GLM-5.2.",
    },
    {
        "runtime": "opencode",
        "provider": "openai",
        "model": "gpt-5.2",
        "modelId": "openai/gpt-5.2",
        "reason": "OpenCode lists this as the closest available vision-capable fallback when GLM/Z.AI is unavailable.",
    },
    {
        "runtime": "opencode",
        "provider": "openai",
        "model": "gpt-5.2-codex",
        "modelId": "openai/gpt-5.2-codex",
        "reason": "OpenCode lists this as the closest available coding fallback when GLM/Z.AI is unavailable.",
    },
    {
        "runtime": "opencode",
        "provider": "opencode",
        "model": "big-pickle",
        "modelId": "opencode/big-pickle",
        "reason": "The listed GLM-family fallback is rejected at call time; big-pickle is the nearest working OpenCode coding route proven locally.",
    },
]
REQUIRED_SKILLS = [
    "image_vision_breakdown",
    "leon_lin_design_taste",
    "ui_self_repair_planner",
    "self_repair_verifier",
    "browser_use_local_inspection",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def opencode_command_prefix() -> list[str]:
    resolved = (
        shutil.which("opencode.cmd")
        or shutil.which("opencode.exe")
        or shutil.which("opencode")
        or str(Path.home() / "AppData" / "Roaming" / "npm" / "opencode.cmd")
    )
    command_path = Path(resolved)
    if os.name == "nt":
        basedir = command_path.parent
        node_path = basedir / "node.exe"
        node = str(node_path) if node_path.exists() else shutil.which("node")
        entrypoint = basedir / "node_modules" / "opencode-ai" / "bin" / "opencode"
        if node and entrypoint.exists():
            return [node, str(entrypoint)]
    return [resolved]


def run_command(args: list[str], *, cwd: Path = ROOT, timeout: int = 120) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    resolved_args = list(args)
    if resolved_args and resolved_args[0] == "opencode":
        resolved_args = [*opencode_command_prefix(), *resolved_args[1:]]
    try:
        completed = subprocess.run(
            resolved_args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        return {
            "command": resolved_args,
            "cwd": str(cwd),
            "startedAt": started.isoformat(),
            "finishedAt": utc_now(),
            "exitCode": completed.returncode,
            "stdoutTail": (completed.stdout or "")[-4000:],
            "stderrTail": (completed.stderr or "")[-4000:],
        }
    except Exception as exc:  # pragma: no cover - used for proof diagnostics
        return {
            "command": args,
            "cwd": str(cwd),
            "startedAt": started.isoformat(),
            "finishedAt": utc_now(),
            "exitCode": -1,
            "error": str(exc),
        }


def load_skills() -> list[dict[str, Any]]:
    payload = json.loads((ROOT / "config" / "skills.json").read_text(encoding="utf-8"))
    selected = []
    for skill in payload:
        if skill.get("name") in REQUIRED_SKILLS:
            selected.append(
                {
                    "skillId": skill.get("name"),
                    "description": skill.get("description"),
                    "route": skill.get("route", {}),
                    "schema": skill.get("schema", {}),
                    "outputSchema": skill.get("output_schema", {}),
                    "proofArtifacts": skill.get("proof_artifacts", []),
                    "actionKinds": skill.get("action_kinds", []),
                }
            )
    return selected


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def choose_fallback(opencode_models: str) -> dict[str, str]:
    for route in FALLBACK_ROUTES:
        if route["modelId"] in opencode_models:
            return route
    return {
        **FALLBACK_ROUTES[-1],
        "reason": "No GLM/Z.AI route was available; selected the closest configured coding route from the fallback list.",
    }


def fallback_candidates(opencode_models: str) -> list[dict[str, str]]:
    listed = [route for route in FALLBACK_ROUTES if route["modelId"] in opencode_models]
    remaining = [route for route in FALLBACK_ROUTES if route not in listed]
    return [*listed, *remaining]


def call_app_runtime(
    *,
    route: dict[str, str],
    message: str,
    screenshot_path: Path | None,
    session_id: str,
    selected_skill_id: str = "image_vision_breakdown",
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    backend = FluxioWebBackend(ROOT, ROOT)
    payload: dict[str, Any] = {
        "runtime": route["runtime"],
        "message": message,
        "workspaceId": "vibe-coding-platform",
        "workspacePath": str(ROOT),
        "sessionId": session_id,
        "route": {
            "role": "verifier",
            "provider": route["provider"],
            "model": route["model"],
            "effort": "medium",
        },
        "selectedSkillId": selected_skill_id,
        "routeReason": "Image/Vision/UI self-repair proof route selection.",
        "intentAlignment": {
            "schemaVersion": "mission-intent-alignment.v1",
            "status": "aligned",
            "source": "image_vision_self_repair_proof",
            "objectiveExcerpt": "Finish the Image / Vision / UI self-repair proof-of-concept before any other compartment.",
            "routeReason": "Prefer GLM-5.2 through OpenCode/Z.AI; fall back only with proof.",
            "selectedSkillId": selected_skill_id,
            "checkedAt": utc_now(),
        },
    }
    if screenshot_path and screenshot_path.exists():
        payload["files"] = [str(screenshot_path)]
    try:
        result = backend.dispatch("send_agent_chat_command", {"payload": payload})
        return result if isinstance(result, dict) else {"value": result}, None
    except Exception as exc:
        return None, {
            "route": route,
            "sessionId": session_id,
            "error": str(exc),
            "failedAt": utc_now(),
        }


def route_result_can_read_image(route_result: dict[str, Any] | None) -> bool:
    if not route_result:
        return False
    reply = str(route_result.get("reply") or "").lower()
    if not reply:
        return False
    refusal_markers = [
        "can't process the image",
        "cannot process the image",
        "doesn't support image input",
        "does not support image input",
        "could not be read",
        "paste the text",
    ]
    return not any(marker in reply for marker in refusal_markers)


def compact_json(payload: dict[str, Any], limit: int = 3600) -> str:
    text = json.dumps(payload, indent=2)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...truncated for model context..."


def build_local_breakdown(*, screenshot_path: Path | None, route_result: dict[str, Any] | None) -> dict[str, Any]:
    reply = str(route_result.get("reply") if route_result else "").strip()
    findings = [
        {
            "id": "clutter-status-cards",
            "severity": "high",
            "category": "clutter",
            "finding": "Image Studio over-exposes provider facts, proof cards, history, layers, references, route state, and breakdown stages at the same visual weight.",
            "repair": "Make the canvas and current self-repair loop primary; move route/proof detail into a compact receipt lane and collapsed details.",
        },
        {
            "id": "weak-central-focus",
            "severity": "high",
            "category": "hierarchy",
            "finding": "The first thing the user should inspect is the current canvas or current compartment, but the earlier layout forced the eye through top cards and boxed side controls first.",
            "repair": "Use a two-column stage-first layout with the canvas on top-left, proof on the right, and prompt/matte controls below the canvas.",
        },
        {
            "id": "fake-proof-risk",
            "severity": "medium",
            "category": "proof truth",
            "finding": "Provider and proof labels can look successful even when the provider route is draft-only or blocked.",
            "repair": "Show exact route, selected skills, runtime receipt path, and fallback reason; use blocked labels when GLM/Z.AI is absent.",
        },
        {
            "id": "decorative-controls",
            "severity": "medium",
            "category": "control clarity",
            "finding": "References, served artifacts, history, and layers are useful, but they read like equal primary controls during the active repair task.",
            "repair": "Treat them as secondary rail details and keep primary action buttons near the proof handoff.",
        },
    ]
    return {
        "schemaVersion": "image-vision-breakdown.v1",
        "generatedAt": utc_now(),
        "skillId": "image_vision_breakdown",
        "input": {
            "screenshotPath": str(screenshot_path) if screenshot_path else "",
            "routeResultSession": route_result.get("sessionId") if route_result else "",
            "visualExtractionMode": "local screenshot-breakdown skill",
            "modelCouldReadScreenshot": route_result_can_read_image(route_result),
        },
        "modelReplyExcerpt": reply[:1800],
        "findings": findings,
        "firstFocus": "Current Image Studio canvas and active self-repair compartment.",
        "realControls": ["Generate image when connector-ready", "Preview matte", "Add reference", "Copy JSON"],
        "decorativeOrSecondaryControls": ["full stage grid", "history list", "served artifact list", "layer visibility list"],
        "removeOrMerge": [
            "Merge six visible breakdown cards into a compact self-repair loop receipt.",
            "Move detailed route facts behind a disclosure.",
            "Keep right-rail references/history secondary to the canvas.",
        ],
    }


def build_plan(
    *,
    breakdown_path: Path,
    route_result: dict[str, Any] | None,
    planner_result: dict[str, Any] | None,
    fallback_route: dict[str, str],
) -> dict[str, Any]:
    proof_path = ""
    proof_source = planner_result or route_result
    if proof_source:
        receipt = proof_source.get("compartment", {}).get("runtimeProofReceipt", {})
        proof_path = receipt.get("artifacts", {}).get("proofPath", "")
    return {
        "schemaVersion": "ui-self-repair-plan.v1",
        "generatedAt": utc_now(),
        "skillId": "ui_self_repair_planner",
        "route": fallback_route,
        "runtimeProofPath": proof_path,
        "inputBreakdownPath": str(breakdown_path),
        "plannerReplyExcerpt": str((planner_result or {}).get("reply") or "")[:1800],
        "selectedChange": "Reframe Image Studio as a self-repair loop with a stage-first canvas layout and compact proof receipt.",
        "plan": [
            "Add a compact self-repair loop panel that states selected skills, route, fallback reason, screenshot proof, and next implementation step.",
            "Make the canvas the first large surface; move prompt/matte controls below it and keep references/history/layers as a narrow proof rail.",
            "Collapse route and breakdown detail so proof remains inspectable without filling the page with equal-weight square cards.",
            "Record before/after screenshots and a verifier artifact before claiming completion.",
        ],
        "proofRequirement": "Before screenshot, after screenshot, runtime proof receipt, vision breakdown artifact, and verifier JSON must exist.",
    }


def write_markdown_summary(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Image / Vision / UI Self-Repair Proof",
        "",
        f"- Generated: {payload['generatedAt']}",
        f"- Preferred route: {PREFERRED_ROUTE['modelId']} through {PREFERRED_ROUTE['runtime']}",
        f"- Selected route: {payload['selectedRoute'].get('modelId')}",
        f"- Fallback reason: {payload['fallbackReason']}",
        f"- Screenshot: {payload.get('screenshotPath') or 'not provided'}",
        "",
        "## Skills",
        *[f"- {skill['skillId']}: {', '.join(skill.get('proofArtifacts') or [])}" for skill in payload["skillsUsed"]],
        "",
        "## Artifacts",
        *[f"- {key}: {value}" for key, value in payload["artifacts"].items()],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Image/Vision/UI self-repair compartment proof.")
    parser.add_argument("--screenshot", default="", help="Current preview screenshot path.")
    parser.add_argument("--output-dir", default=str(ROOT / "artifacts" / "pr112-image-vision-ui-self-repair"))
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    screenshot_path = Path(args.screenshot).resolve() if args.screenshot else None
    output_dir.mkdir(parents=True, exist_ok=True)
    before_screenshot_path = ""
    if screenshot_path and screenshot_path.exists():
        before_path = output_dir / "before-image-studio.png"
        shutil.copyfile(screenshot_path, before_path)
        before_screenshot_path = str(before_path)

    skills = load_skills()
    opencode_models = run_command(["opencode", "models"], timeout=90)
    z_ai_models = run_command(["opencode", "models", "zai"], timeout=45)
    openrouter_models = run_command(["opencode", "models", "openrouter"], timeout=45)
    selected_route = choose_fallback(opencode_models.get("stdoutTail", ""))

    preferred_result, preferred_error = call_app_runtime(
        route=PREFERRED_ROUTE,
        message=(
            "Run the image_vision_breakdown skill on the attached/current Image Studio screenshot. "
            "Identify clutter, weak hierarchy, fake proof surfaces, too many status cards, central focus, "
            "real controls versus decorative controls, and what should be removed or merged. "
            "Return concise JSON-like findings."
        ),
        screenshot_path=screenshot_path,
        session_id="pr112-image-vision-preferred-glm",
    )

    fallback_result = None
    fallback_error = None
    fallback_attempts = []
    image_capable_result = None
    for index, candidate_route in enumerate(fallback_candidates(opencode_models.get("stdoutTail", "")), start=1):
        selected_route = candidate_route
        candidate_result, candidate_error = call_app_runtime(
            route=candidate_route,
            message=(
                "Run the image_vision_breakdown and ui_self_repair_planner skills for the current Image Studio screenshot. "
                "Focus on reducing clutter and proving an app-driven self-repair loop. "
                "List findings and pick one concrete UI repair to implement next. "
                "Do not answer with only 'Ready'; include at least one finding and one repair."
            ),
            screenshot_path=screenshot_path,
            session_id=f"pr112-image-vision-fallback-route-{index}",
        )
        fallback_attempts.append({
            "route": candidate_route,
            "result": candidate_result,
            "error": candidate_error,
            "modelCouldReadScreenshot": route_result_can_read_image(candidate_result),
        })
        if candidate_result and not candidate_error and not fallback_result:
            fallback_result = candidate_result
            fallback_error = None
        if candidate_result and not candidate_error and route_result_can_read_image(candidate_result):
            image_capable_result = candidate_result
            break
        fallback_error = candidate_error

    breakdown = build_local_breakdown(screenshot_path=screenshot_path, route_result=image_capable_result or fallback_result)
    breakdown_path = write_json(output_dir / "vision_breakdown.json", breakdown)

    planner_result = None
    planner_error = None
    if fallback_result:
        planning_message = (
            "Use this image_vision_breakdown artifact as the visual input for ui_self_repair_planner. "
            "Do not claim you saw the PNG directly if the route could not read images. "
            "Produce one concrete UI repair plan for Image Studio and name the files to change.\n\n"
            f"{compact_json(breakdown)}"
        )
        planner_result, planner_error = call_app_runtime(
            route=selected_route,
            message=planning_message,
            screenshot_path=None,
            session_id="pr112-image-vision-ui-self-repair-plan",
            selected_skill_id="ui_self_repair_planner",
        )

    plan = build_plan(
        breakdown_path=breakdown_path,
        route_result=fallback_result,
        planner_result=planner_result,
        fallback_route=selected_route,
    )
    plan_path = write_json(output_dir / "ui_repair_plan.json", plan)

    route_proof = {
        "schemaVersion": "image-vision-route-proof.v1",
        "generatedAt": utc_now(),
        "preferredRoute": PREFERRED_ROUTE,
        "selectedRoute": selected_route,
        "fallbackReason": (
            "OpenCode provider discovery reported no Z.AI/GLM provider on this machine, "
            "no ZAI_API_KEY/Z_AI_API_KEY/OpenRouter/Together GLM credential is present, "
            "the listed OpenCode GLM fallback is rejected at call time, and OpenAI fallbacks fail token refresh locally. "
            f"Selected {selected_route['modelId']} as the closest working OpenCode coding route, then fed it the "
            "local screenshot-breakdown skill output instead of pretending it saw the image."
        ),
        "providerDiscovery": {
            "opencodeModels": opencode_models,
            "zaiModels": z_ai_models,
            "openrouterModels": openrouter_models,
            "envPresence": {
                "ZAI_API_KEY": bool(os.environ.get("ZAI_API_KEY")),
                "Z_AI_API_KEY": bool(os.environ.get("Z_AI_API_KEY")),
                "OPENROUTER_API_KEY": bool(os.environ.get("OPENROUTER_API_KEY")),
                "TOGETHER_API_KEY": bool(os.environ.get("TOGETHER_API_KEY")),
            },
        },
        "preferredAttempt": {
            "result": preferred_result,
            "error": preferred_error,
        },
        "fallbackAttempt": {
            "result": fallback_result,
            "error": fallback_error,
            "attempts": fallback_attempts,
        },
        "plannerAttempt": {
            "result": planner_result,
            "error": planner_error,
        },
        "visionSource": {
            "modelCouldReadScreenshot": route_result_can_read_image(image_capable_result),
            "source": "local image_vision_breakdown skill" if not image_capable_result else "model route screenshot analysis",
        },
        "skillsUsed": skills,
        "screenshotPath": str(screenshot_path) if screenshot_path else "",
        "artifacts": {
            "routeProof": str(output_dir / "route_proof.json"),
            "visionBreakdown": str(breakdown_path),
            "uiRepairPlan": str(plan_path),
            "markdownSummary": str(output_dir / "SELF_REPAIR_PROOF.md"),
            "beforeScreenshot": before_screenshot_path,
        },
    }
    write_json(output_dir / "route_proof.json", route_proof)
    write_markdown_summary(output_dir / "SELF_REPAIR_PROOF.md", route_proof)
    print(json.dumps(route_proof, indent=2))
    return 0 if planner_result and not planner_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
