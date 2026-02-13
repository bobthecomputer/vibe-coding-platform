from __future__ import annotations

import json
from pathlib import Path


def build_suite_summary(results: list[dict]) -> dict:
    count = len(results)
    if count == 0:
        return {
            "preset_count": 0,
            "avg_score_delta": 0,
            "avg_resistance": 0,
            "probe_pass_rate": 0,
            "presets": [],
        }

    avg_delta = round(
        sum(int(item.get("training_comparison", {}).get("score_delta", 0)) for item in results) / count,
        2,
    )
    avg_resistance = round(
        sum(int(item.get("probe", {}).get("resistance_score", 0)) for item in results) / count,
        2,
    )
    pass_count = len([item for item in results if item.get("probe", {}).get("status") == "pass"])
    pass_rate = round((pass_count / count) * 100, 1)

    return {
        "preset_count": count,
        "avg_score_delta": avg_delta,
        "avg_resistance": avg_resistance,
        "probe_pass_rate": pass_rate,
        "presets": [item.get("preset", "unknown") for item in results],
    }


def write_suite_artifacts(bundle_root: Path, suite_name: str, results: list[dict], summary: dict) -> dict:
    bundle_root.mkdir(parents=True, exist_ok=True)
    json_path = bundle_root / f"{suite_name}.json"
    md_path = bundle_root / f"{suite_name}.md"

    payload = {
        "summary": summary,
        "results": results,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Demo Suite Report",
        "",
        f"- Presets: {', '.join(summary.get('presets', []))}",
        f"- Avg score delta: {summary.get('avg_score_delta', 0)}",
        f"- Avg resistance: {summary.get('avg_resistance', 0)}",
        f"- Probe pass rate: {summary.get('probe_pass_rate', 0)}%",
        "",
        "## Per Preset",
    ]
    for item in results:
        comp = item.get("training_comparison", {})
        probe = item.get("probe", {})
        lines.extend(
            [
                f"- `{item.get('preset', 'unknown')}`: "
                f"delta={comp.get('score_delta', 0)}, "
                f"probe={probe.get('status', 'unknown')} ({probe.get('resistance_score', 0)})",
            ]
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "suite_json_path": str(json_path),
        "suite_report_path": str(md_path),
    }
