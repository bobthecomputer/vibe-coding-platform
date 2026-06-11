from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from textwrap import wrap
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS = Path(".agent_control") / "live_mission_detail_status_latest.json"
DEFAULT_PRESSURE = Path(".agent_control") / "nas_storage_pressure_latest.json"
DEFAULT_CLEANUP = Path(".agent_control") / "nas_storage_cleanup_plan_latest.json"
DEFAULT_OUTPUT_DIR = Path(".agent_control") / "mission_result_screenshots"
DEFAULT_MANIFEST = Path(".agent_control") / "mission_evidence_manifest_latest.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip().lower()).strip("-")
    return text[:80] or "mission"


def _mission_verdict(row: dict[str, Any]) -> list[str]:
    gate = row.get("artifactGate") if isinstance(row.get("artifactGate"), dict) else {}
    transcript = row.get("runtimeTranscript") if isinstance(row.get("runtimeTranscript"), dict) else {}
    title = str(row.get("title") or row.get("missionId") or "mission")
    if gate.get("passed") and str(transcript.get("status") or "") == "attached":
        return [
            f"This mission has real Hermes activity: status {row.get('status', 'unknown')}, transcript attached, artifact gate passed.",
            "It produced concrete runtime-output and artifact-path evidence visible from the live NAS mission detail endpoint.",
            "This is still evidence quality, not a product-completion claim; review the artifact output before calling the app finished.",
        ]
    return [
        f"This mission is not close enough: {title} is {row.get('status', 'unknown')} and lacks enough runtime proof.",
        f"The runtime transcript is {transcript.get('status', 'missing')} and the artifact gate is {gate.get('status', 'missing')}.",
        "Resume with a hard artifact gate only after NAS write headroom is available.",
    ]


def _storage_lines(pressure: dict[str, Any], cleanup: dict[str, Any]) -> list[str]:
    mount = pressure.get("mount") or cleanup.get("mount") or "/volume1/Saclay"
    probe_failed = bool(pressure.get("probeTimedOut")) or bool(pressure.get("probeConnectFailed"))
    measured = bool(pressure.get("measuredUsageAvailable", not probe_failed))
    used = pressure.get("usedPercent", cleanup.get("usedPercent", "?"))
    available = pressure.get("availableBytes", cleanup.get("availableBytes", "?"))
    big_path = (
        cleanup.get("largestSuspectedExternalPath")
        or pressure.get("largestSuspectedExternalPath")
        or cleanup.get("largestVolumeAccountingPath")
        or pressure.get("largestVolumeAccountingPath")
        or ""
    )
    big_gb = (
        cleanup.get("suspectedExternalGB")
        or pressure.get("suspectedExternalGB")
        or cleanup.get("volumeAccountingGB")
        or pressure.get("volumeAccountingGB")
        or 0
    )
    timed_out = [
        *list(cleanup.get("timedOutExternalProbePaths") or [])[:3],
        *list(cleanup.get("timedOutVolumeAccountingPaths") or [])[:3],
    ]
    lines = [
        (
            f"{mount}: live usage unavailable because the bounded NAS probe failed"
            if not measured
            else f"{mount}: {used}% used, available {available} bytes"
        ),
        f"Generated cleanup candidates: {cleanup.get('candidateCount', 0)} ({cleanup.get('estimatedReclaimableMB', 0)} MB)",
    ]
    if big_path:
        lines.append(f"Largest bounded non-generated path: {big_path} ({big_gb} GB)")
    if timed_out:
        lines.append("Timed out probes: " + ", ".join(str(item) for item in timed_out))
    return lines


def _font(name: str, size: int):
    from PIL import ImageFont

    font_dir = Path("C:/Windows/Fonts")
    for candidate in (font_dir / name, font_dir / "arial.ttf"):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _draw_wrapped(draw, text: str, xy: tuple[int, int], *, width: int, font, fill: str, line_height: int) -> int:
    x, y = xy
    for paragraph in str(text).splitlines() or [""]:
        for line in wrap(paragraph, width=width) or [""]:
            draw.text((x, y), line, fill=fill, font=font)
            y += line_height
    return y


def _draw_badge(draw, x: int, y: int, text: str, fill: str, font, text_fill: str) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0] + 22
    draw.rounded_rectangle((x, y, x + width, y + 30), radius=7, fill=fill)
    draw.text((x + 11, y + 6), text, fill=text_fill, font=font)
    return x + width + 9


def render_screenshot(
    *,
    row: dict[str, Any],
    pressure: dict[str, Any],
    cleanup: dict[str, Any],
    checked_at: str,
    output_path: Path,
) -> dict[str, Any]:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - depends on optional local renderer dependency
        raise SystemExit("Pillow is required to render mission evidence screenshots.") from exc

    title_font = _font("segoeuib.ttf", 34)
    h1_font = _font("segoeuib.ttf", 28)
    h2_font = _font("segoeuib.ttf", 20)
    body_font = _font("segoeui.ttf", 17)
    small_font = _font("segoeui.ttf", 14)
    number_font = _font("segoeuib.ttf", 36)

    colors = {
        "bg": "#090f17",
        "header": "#0f1724",
        "panel": "#151c25",
        "line": "#35465d",
        "text": "#edf3fb",
        "muted": "#b8c5d6",
        "blue": "#274264",
        "green": "#187354",
        "amber": "#84531b",
        "red": "#7e3434",
    }

    gate = row.get("artifactGate") if isinstance(row.get("artifactGate"), dict) else {}
    transcript = row.get("runtimeTranscript") if isinstance(row.get("runtimeTranscript"), dict) else {}
    image = Image.new("RGB", (1500, 950), colors["bg"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1500, 78), fill=colors["header"])
    draw.text((38, 25), "Fluxio live NAS mission evidence", fill=colors["text"], font=title_font)
    refresh = checked_at[:19].replace("T", " ")
    draw.text((1110, 32), f"live refresh {refresh} UTC", fill=colors["muted"], font=small_font)

    draw.text((44, 126), str(row.get("title") or row.get("missionId") or "Mission"), fill=colors["text"], font=h1_font)
    draw.text((44, 166), str(row.get("missionId") or ""), fill=colors["muted"], font=small_font)
    x = 44
    x = _draw_badge(draw, x, 186, f"runtime: {row.get('runtime', 'unknown')}", colors["blue"], small_font, colors["text"])
    state_color = colors["green"] if row.get("status") in {"running", "completed"} else colors["red"]
    x = _draw_badge(draw, x, 186, f"status: {row.get('status', 'unknown')}", state_color, small_font, colors["text"])
    gate_color = colors["green"] if gate.get("status") == "passed" else colors["amber"]
    x = _draw_badge(draw, x, 186, f"artifact gate: {gate.get('status', 'missing')}", gate_color, small_font, colors["text"])
    transcript_color = colors["green"] if transcript.get("status") == "attached" else colors["amber"]
    _draw_badge(draw, x, 186, f"transcript: {transcript.get('status', 'missing')}", transcript_color, small_font, colors["text"])

    def panel(box: tuple[int, int, int, int], heading: str) -> None:
        draw.rounded_rectangle(box, radius=10, fill=colors["panel"], outline=colors["line"], width=1)
        draw.text((box[0] + 22, box[1] + 20), heading, fill=colors["text"], font=h2_font)

    panel((44, 245, 484, 455), "Mission counters")
    metrics = [
        (row.get("agentMessages", 0), "Agent messages"),
        (transcript.get("messageCount", 0), "Transcript messages"),
        (gate.get("runtimeOutputCount", 0), "Runtime outputs"),
        (gate.get("artifactCount", 0), "Artifact paths"),
    ]
    y = 326
    for number, label in metrics:
        draw.text((74, y), str(number), fill=colors["text"], font=number_font)
        draw.text((154, y + 11), label, fill=colors["muted"], font=body_font)
        y += 36

    panel((510, 245, 1456, 455), "Storage / write safety")
    y = 316
    for line in _storage_lines(pressure, cleanup):
        y = _draw_wrapped(draw, line, (540, y), width=108, font=body_font, fill=colors["muted"], line_height=24)

    panel((44, 490, 1456, 715), "Verdict")
    y = 558
    for line in _mission_verdict(row):
        y = _draw_wrapped(draw, f"- {line}", (78, y), width=130, font=body_font, fill=colors["text"], line_height=34)

    panel((44, 748, 1456, 925), "Evidence excerpts")
    excerpts: list[str] = []
    for item in gate.get("runtimeOutputEvidence") or []:
        if isinstance(item, dict):
            excerpts.append(f"{item.get('source', 'runtime output')}: {item.get('detail', '')}")
    if not excerpts and gate.get("failure"):
        excerpts.append(f"Hard artifact gate failure: {gate.get('failure')}")
    if transcript.get("detail"):
        excerpts.append(f"Transcript detail: {transcript.get('detail')}")
    for item in gate.get("artifactEvidence") or []:
        if isinstance(item, dict):
            excerpts.append(f"Artifact path: {item.get('detail', '')}")
    y = 814
    for excerpt in excerpts[:4]:
        y = _draw_wrapped(draw, excerpt, (78, y), width=135, font=small_font, fill=colors["muted"], line_height=22)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return {
        "missionId": row.get("missionId", ""),
        "title": row.get("title", ""),
        "status": row.get("status", ""),
        "runtime": row.get("runtime", ""),
        "artifactGateStatus": gate.get("status", ""),
        "runtimeTranscriptStatus": transcript.get("status", ""),
        "screenshotPath": str(output_path.resolve()),
    }


def render_manifest(
    *,
    root: Path,
    mission_ids: set[str],
    output_dir: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    root = root.resolve()
    status = _load_json(root / DEFAULT_STATUS)
    pressure = _load_json(root / DEFAULT_PRESSURE)
    cleanup = _load_json(root / DEFAULT_CLEANUP)
    checked_at = str(status.get("checkedAt") or datetime.now(timezone.utc).isoformat())
    rows = status.get("missionRows", []) if isinstance(status.get("missionRows"), list) else []
    rendered: list[dict[str, Any]] = []
    stamp = checked_at.replace(":", "").replace("-", "").replace("+", "Z").replace(".", "_").replace("T", "T")[:24]
    for row in rows:
        if not isinstance(row, dict):
            continue
        mission_id = str(row.get("missionId") or "").strip()
        if not mission_id or (mission_ids and mission_id not in mission_ids):
            continue
        filename = f"{_slug(mission_id)}-{_slug(str(row.get('title') or 'mission'))}-{stamp}.png"
        rendered.append(
            render_screenshot(
                row=row,
                pressure=pressure,
                cleanup=cleanup,
                checked_at=checked_at,
                output_path=output_dir / filename,
            )
        )
    manifest = {
        "schema": "fluxio.mission_evidence_screenshot_manifest.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceStatusPath": str((root / DEFAULT_STATUS).resolve()),
        "sourceCheckedAt": checked_at,
        "screenshotCount": len(rendered),
        "screenshots": rendered,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Render live mission evidence screenshots from NAS mission detail JSON.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--mission-id", action="append", default=[])
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    manifest = Path(args.manifest)
    if not manifest.is_absolute():
        manifest = root / manifest
    payload = render_manifest(
        root=root,
        mission_ids={str(item).strip() for item in args.mission_id if str(item).strip()},
        output_dir=output_dir,
        manifest_path=manifest,
    )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
