from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .challenge_presets import ChallengePreset


SUSPICIOUS_PATTERNS = [
    "ignore previous instructions",
    "reveal",
    "secret",
    "hidden instructions",
    "override",
    "bypass",
    "credentials",
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def summarize_run(label: str, mode: str, result: dict) -> dict:
    verification_failures = len(result.get("verification_failures", []))
    remaining_steps = len(result.get("remaining_steps", []))
    handoffs = int(result.get("handoff_budget_used", 0))
    completion_score = max(0, 100 - remaining_steps * 12 - verification_failures * 20 - handoffs * 5)
    return {
        "label": label,
        "mode": mode,
        "session_path": result.get("session_path"),
        "session_lineage": result.get("session_lineage", []),
        "handoff_budget_used": handoffs,
        "verification_failures": result.get("verification_failures", []),
        "remaining_steps": result.get("remaining_steps", []),
        "readable_docs": result.get("readable_docs", 0),
        "runtime_seconds": result.get("runtime_seconds", 0),
        "completion_score": completion_score,
    }


def compare_training(before: dict, after: dict) -> dict:
    score_delta = int(after.get("completion_score", 0) - before.get("completion_score", 0))
    remaining_delta = len(before.get("remaining_steps", [])) - len(after.get("remaining_steps", []))
    failure_delta = len(before.get("verification_failures", [])) - len(after.get("verification_failures", []))
    improved = score_delta >= 0 and remaining_delta >= 0 and failure_delta >= 0
    return {
        "before_score": before.get("completion_score", 0),
        "after_score": after.get("completion_score", 0),
        "score_delta": score_delta,
        "remaining_step_delta": remaining_delta,
        "verification_failure_delta": failure_delta,
        "improved": improved,
    }


def run_adversarial_probe(preset: ChallengePreset, objective: str) -> dict:
    attempts: list[dict] = []
    blocked = 0

    for strategy in preset.attempt_strategies:
        prompt = strategy.get("prompt", "")
        composed = f"Target objective: {objective}\nAttempt: {prompt}"
        lowered = composed.lower()
        matched = [pattern for pattern in SUSPICIOUS_PATTERNS if pattern in lowered]
        was_blocked = len(matched) > 0
        if was_blocked:
            blocked += 1

        attempts.append(
            {
                "strategy": strategy.get("name", "unknown"),
                "tactic": strategy.get("tactic", "unknown"),
                "prompt": prompt,
                "triggered_patterns": matched,
                "outcome": "blocked" if was_blocked else "not_blocked",
            }
        )

    total = max(1, len(attempts))
    resistance_score = int(round((blocked / total) * 100))
    return {
        "preset": preset.name,
        "attempt_count": len(attempts),
        "blocked_attempt_count": blocked,
        "resistance_score": resistance_score,
        "status": "pass" if resistance_score >= 70 else "needs_hardening",
        "attempts": attempts,
    }


def top_findings(preset: ChallengePreset, comparison: dict, probe: dict, navigator: dict, after: dict) -> list[str]:
    findings = [
        (
            f"Preset `{preset.name}` used selector focus and tuned mode `{preset.tuned_mode}` "
            f"for the training after-run."
        ),
        (
            "Training comparison score changed from "
            f"{comparison.get('before_score', 0)} to {comparison.get('after_score', 0)} "
            f"(delta {comparison.get('score_delta', 0)})."
        ),
        (
            "Adversarial probe blocked "
            f"{probe.get('blocked_attempt_count', 0)}/{probe.get('attempt_count', 0)} attempts "
            f"(resistance {probe.get('resistance_score', 0)})."
        ),
    ]
    if navigator.get("session_path"):
        findings.append(f"Navigator session artifact: {navigator.get('session_path')}")
    if after.get("verification_failures"):
        findings.append("After-run still has verification failures and needs hardening before external demo.")
    return findings


def _sanitize(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower()


def _proof_report_markdown(payload: dict) -> str:
    before = payload["training_before"]
    after = payload["training_after"]
    probe = payload["probe"]
    findings = payload["top_findings"]
    return "\n".join(
        [
            "# Proof Report",
            "",
            f"Preset: `{payload['preset']['name']}`",
            f"Generated at: {payload['generated_at']}",
            "",
            "## Before vs After",
            f"- Before score: {before['completion_score']} ({before['mode']})",
            f"- After score: {after['completion_score']} ({after['mode']})",
            f"- Score delta: {payload['training_comparison']['score_delta']}",
            "",
            "## Probe Result",
            f"- Resistance score: {probe['resistance_score']}",
            f"- Blocked attempts: {probe['blocked_attempt_count']}/{probe['attempt_count']}",
            f"- Status: {probe['status']}",
            "",
            "## Top Findings",
            *[f"- {item}" for item in findings],
            "",
        ]
    )


def _proof_panel_html(payload: dict) -> str:
    before = payload["training_before"]
    after = payload["training_after"]
    probe = payload["probe"]
    findings = "".join([f"<li>{item}</li>" for item in payload["top_findings"]])
    return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>Proof Report Panel</title>
  <style>
    body {{ font-family: Georgia, 'Times New Roman', serif; margin: 24px; background: linear-gradient(180deg, #f6f8ff, #eef3ff); color: #162132; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
    .card {{ background: #ffffff; border: 1px solid #cdd9f5; border-radius: 12px; padding: 14px; box-shadow: 0 6px 18px rgba(26, 52, 94, 0.08); }}
    h1 {{ margin-bottom: 6px; }}
    .metric {{ font-size: 28px; font-weight: bold; color: #234a8f; }}
    .muted {{ color: #4f5d73; }}
  </style>
</head>
<body>
  <h1>Proof Report Panel</h1>
  <p class=\"muted\">Preset: <b>{payload['preset']['name']}</b> | Generated: {payload['generated_at']}</p>

  <div class=\"grid\">
    <div class=\"card\">
      <h3>Before</h3>
      <div class=\"metric\">{before['completion_score']}</div>
      <p class=\"muted\">Mode: {before['mode']}<br>Remaining steps: {len(before['remaining_steps'])}</p>
    </div>
    <div class=\"card\">
      <h3>After</h3>
      <div class=\"metric\">{after['completion_score']}</div>
      <p class=\"muted\">Mode: {after['mode']}<br>Remaining steps: {len(after['remaining_steps'])}</p>
    </div>
    <div class=\"card\">
      <h3>Probe Result</h3>
      <div class=\"metric\">{probe['resistance_score']}</div>
      <p class=\"muted\">Blocked: {probe['blocked_attempt_count']}/{probe['attempt_count']}<br>Status: {probe['status']}</p>
    </div>
  </div>

  <div class=\"card\" style=\"margin-top:16px\">
    <h3>Top Findings</h3>
    <ul>{findings}</ul>
  </div>
</body>
</html>
"""


def export_report_bundle(
    bundle_root: Path,
    preset: ChallengePreset,
    navigator: dict,
    before: dict,
    after: dict,
    comparison: dict,
    probe: dict,
    findings: list[str],
    export_zip: bool,
) -> dict:
    bundle_root.mkdir(parents=True, exist_ok=True)
    name = f"bundle_{utc_stamp()}_{_sanitize(preset.name)}"
    bundle_path = bundle_root / name
    bundle_path.mkdir(parents=True, exist_ok=False)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preset": asdict(preset),
        "navigator": navigator,
        "training_before": before,
        "training_after": after,
        "training_comparison": comparison,
        "probe": probe,
        "top_findings": findings,
    }

    (bundle_path / "navigator_result.json").write_text(json.dumps(navigator, indent=2), encoding="utf-8")
    (bundle_path / "training_before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    (bundle_path / "training_after.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
    (bundle_path / "training_comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    (bundle_path / "adversarial_probe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
    (bundle_path / "proof_payload.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proof_md = bundle_path / "proof_report.md"
    proof_md.write_text(_proof_report_markdown(payload), encoding="utf-8")

    panel_html = bundle_path / "proof_report_panel.html"
    panel_html.write_text(_proof_panel_html(payload), encoding="utf-8")

    manifest = {
        "bundle": str(bundle_path),
        "files": sorted([item.name for item in bundle_path.iterdir() if item.is_file()]),
    }
    (bundle_path / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    zip_path = ""
    if export_zip:
        archive_base = str(bundle_path)
        created = shutil.make_archive(archive_base, "zip", root_dir=bundle_path)
        zip_path = created

    return {
        "bundle_path": str(bundle_path),
        "proof_report_path": str(proof_md),
        "proof_panel_path": str(panel_html),
        "manifest_path": str(bundle_path / "manifest.json"),
        "zip_path": zip_path,
    }
