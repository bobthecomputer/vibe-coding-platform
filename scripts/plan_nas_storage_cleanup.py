from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.sync_nas_system_audit import (
    DEFAULT_REMOTE_ROOT,
    _connect_nas_client,
    _load_nas_credentials,
    _paramiko,
    _quote_single,
    _run_remote_bash_script,
)


DEFAULT_OUTPUT = ROOT / ".agent_control" / "nas_storage_cleanup_plan_latest.json"
DEFAULT_PRESSURE_OUTPUT = ROOT / ".agent_control" / "nas_storage_pressure_latest.json"


GENERATED_PATHS = (
    ".agent_control/mission_async",
    ".agent_control/release_artifacts",
    ".agent_control/backups",
    ".agent_control/tmp-ui-checks",
    ".agent_control/live_mission_detail_performance",
    ".agent_control/live-agent-stuck-message-check-20260531.png",
    ".agent_control/live-agent-empty-report-switch-normal-20260531.png",
    ".agent_control/live-agent-f1-empty-report-switch-20260531.png",
)

NON_GENERATED_PROBE_PATHS = (
    "/volume1/Duncan/MacBook Air.sparsebundle",
    "/volume1/Saclay/projects/overnight-discovery-lab",
    "/volume1/Saclay/projects/syntelos",
)

VOLUME_ACCOUNTING_PROBE_PATHS = (
    "/volume1/@appdata/ContainerManager",
    "/volume1/@appdata/ContainerManager/all_shares",
    "/volume1/@synologydrive",
    "/volume1/Duncan",
    "/volume1/Saclay",
    "/volume1/Saclay/#recycle",
    "/volume1/Duncan/#recycle",
)


def _parse_df_line(line: str) -> dict[str, Any]:
    parts = line.split()
    if len(parts) < 6 or not parts[1].isdigit():
        return {}
    used_percent = parts[4].rstrip("%")
    return {
        "filesystem": parts[0],
        "sizeBytes": int(parts[1]),
        "usedBytes": int(parts[2]),
        "availableBytes": int(parts[3]),
        "usedPercent": int(used_percent) if used_percent.isdigit() else 0,
        "mount": parts[5],
    }


def _parse_remote_probe(stdout: str, *, host: str) -> dict[str, Any]:
    df: dict[str, Any] = {}
    path_rows: list[dict[str, Any]] = []
    external_rows: list[dict[str, Any]] = []
    missing_paths: list[str] = []
    external_missing_paths: list[str] = []
    timed_out_external_paths: list[str] = []
    volume_accounting_rows: list[dict[str, Any]] = []
    timed_out_volume_accounting_paths: list[str] = []
    btrfs_rows: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("DF|"):
            df = _parse_df_line(line[3:])
            continue
        if line.startswith("DU|"):
            _prefix, kb_raw, path = line.split("|", 2)
            try:
                size_bytes = int(kb_raw) * 1024
            except ValueError:
                continue
            path_rows.append({"path": path, "sizeBytes": size_bytes})
            continue
        if line.startswith("EXTDU|"):
            _prefix, kb_raw, path = line.split("|", 2)
            try:
                size_bytes = int(kb_raw) * 1024
            except ValueError:
                continue
            external_rows.append({"path": path, "sizeBytes": size_bytes})
            continue
        if line.startswith("MISS|"):
            missing_paths.append(line[5:])
            continue
        if line.startswith("EXTMISS|"):
            external_missing_paths.append(line[8:])
            continue
        if line.startswith("EXTTIMEOUT|"):
            timed_out_external_paths.append(line[11:])
            continue
        if line.startswith("VOLDU|"):
            _prefix, kb_raw, path = line.split("|", 2)
            try:
                size_bytes = int(kb_raw) * 1024
            except ValueError:
                continue
            volume_accounting_rows.append({"path": path, "sizeBytes": size_bytes})
            continue
        if line.startswith("VOLTIMEOUT|"):
            timed_out_volume_accounting_paths.append(line[11:])
            continue
        if line.startswith("BTRFS|"):
            btrfs_rows.append(line[6:])
    checked_at = datetime.now(timezone.utc).isoformat()
    available = int(df.get("availableBytes") or 0)
    used_percent = int(df.get("usedPercent") or 0)
    status = "critical" if available <= 0 or used_percent >= 99 else "warning" if used_percent >= 95 else "ok"
    candidates = sorted(
        [
            {
                **row,
                "sizeMB": round(int(row["sizeBytes"]) / (1024 * 1024), 1),
                "generatedEvidencePath": True,
                "destructiveAction": "operator_review_required",
                "reason": "Fixed allowlist generated Syntelos evidence/cache path; planner does not delete it.",
            }
            for row in path_rows
            if int(row.get("sizeBytes") or 0) > 0
        ],
        key=lambda item: int(item["sizeBytes"]),
        reverse=True,
    )
    reclaimable = sum(int(item["sizeBytes"]) for item in candidates)
    suspected_external = sorted(
        [
            {
                **row,
                "sizeMB": round(int(row["sizeBytes"]) / (1024 * 1024), 1),
                "sizeGB": round(int(row["sizeBytes"]) / (1024 * 1024 * 1024), 2),
                "generatedEvidencePath": False,
                "destructiveAction": "operator_review_required",
                "reason": "Bounded non-generated NAS path probe; planner reports this for explanation only and never deletes it.",
            }
            for row in external_rows
            if int(row.get("sizeBytes") or 0) > 0
        ],
        key=lambda item: int(item["sizeBytes"]),
        reverse=True,
    )
    suspected_bytes = sum(int(item["sizeBytes"]) for item in suspected_external)
    volume_accounting = sorted(
        [
            {
                **row,
                "sizeMB": round(int(row["sizeBytes"]) / (1024 * 1024), 1),
                "sizeGB": round(int(row["sizeBytes"]) / (1024 * 1024 * 1024), 2),
                "generatedEvidencePath": False,
                "destructiveAction": "operator_review_required",
                "reason": "Volume-level Synology/ContainerManager accounting probe; may include bind-mounted shared-folder mirrors and must not be deleted as a cleanup candidate.",
            }
            for row in volume_accounting_rows
            if int(row.get("sizeBytes") or 0) > 0
        ],
        key=lambda item: int(item["sizeBytes"]),
        reverse=True,
    )
    volume_accounting_bytes = sum(int(item["sizeBytes"]) for item in volume_accounting)
    largest_volume_path = str(volume_accounting[0]["path"]) if volume_accounting else ""
    largest_external_path = str(suspected_external[0]["path"]) if suspected_external else ""
    if candidates:
        next_action = "Review and remove only the listed generated Syntelos evidence/cache paths, then rerun this planner and `df -B1 /volume1/Saclay`."
        if volume_accounting or suspected_external or btrfs_rows:
            next_action += " Treat non-generated, ContainerManager, and Btrfs/snapshot evidence as separate operator-reviewed storage work; generated cleanup alone may not restore mission write headroom."
    else:
        next_action = (
            "No generated Syntelos cleanup candidates were found; review non-Syntelos NAS data, ContainerManager/shared-folder accounting, or Synology/Btrfs snapshots before expecting mission writes to be reliable."
            if suspected_external or volume_accounting or btrfs_rows
            else "No generated Syntelos cleanup candidates were found in the bounded allowlist; free non-Syntelos NAS data or Synology snapshots."
        )
    return {
        "schema": "fluxio.nas_storage_cleanup_plan.v1",
        "checkedAt": checked_at,
        "source": "bounded_ssh_df_du_allowlist",
        "host": host,
        "mount": df.get("mount") or "/volume1/Saclay",
        "status": "cleanup_candidates_found" if candidates else "no_generated_candidates_found",
        "storageStatus": status,
        "sizeBytes": int(df.get("sizeBytes") or 0),
        "usedBytes": int(df.get("usedBytes") or 0),
        "availableBytes": available,
        "usedPercent": used_percent,
        "candidateCount": len(candidates),
        "estimatedReclaimableBytes": reclaimable,
        "estimatedReclaimableMB": round(reclaimable / (1024 * 1024), 1),
        "cleanupCandidates": candidates,
        "missingAllowlistPaths": missing_paths,
        "suspectedExternalUsage": suspected_external,
        "suspectedExternalBytes": suspected_bytes,
        "suspectedExternalGB": round(suspected_bytes / (1024 * 1024 * 1024), 2),
        "largestSuspectedExternalPath": largest_external_path,
        "missingExternalProbePaths": external_missing_paths,
        "timedOutExternalProbePaths": timed_out_external_paths,
        "volumeAccountingUsage": volume_accounting,
        "volumeAccountingBytes": volume_accounting_bytes,
        "volumeAccountingGB": round(volume_accounting_bytes / (1024 * 1024 * 1024), 2),
        "largestVolumeAccountingPath": largest_volume_path,
        "timedOutVolumeAccountingPaths": timed_out_volume_accounting_paths,
        "btrfsAccounting": btrfs_rows[:20],
        "safeMode": True,
        "destructiveActionsExecuted": False,
        "nextAction": next_action,
    }


def _pressure_from_cleanup_plan(plan: dict[str, Any]) -> dict[str, Any]:
    probe_status = str(plan.get("status") or "")
    probe_timed_out = probe_status == "probe_timeout"
    probe_connect_failed = probe_status == "probe_connect_failed"
    measured_usage_available = not (probe_timed_out or probe_connect_failed)
    available_bytes = int(plan.get("availableBytes") or 0)
    used_percent = int(plan.get("usedPercent") or 0)
    return {
        "schema": "fluxio.nas_storage_pressure.v1",
        "checkedAt": plan.get("checkedAt") or datetime.now(timezone.utc).isoformat(),
        "maxAgeSeconds": 172800,
        "source": "bounded_ssh_timeout"
        if probe_timed_out
        else "bounded_ssh_connect_failed"
        if probe_connect_failed
        else "bounded_ssh_df",
        "host": plan.get("host", ""),
        "mount": plan.get("mount", "/volume1/Saclay"),
        "sizeBytes": int(plan.get("sizeBytes") or 0),
        "usedBytes": int(plan.get("usedBytes") or 0),
        "availableBytes": available_bytes,
        "usedPercent": used_percent,
        "measuredUsageAvailable": measured_usage_available,
        "status": "critical"
        if probe_timed_out or probe_connect_failed or available_bytes <= 0 or used_percent >= 99
        else "warning"
        if used_percent >= 95
        else "ok",
        "probeTimedOut": probe_timed_out,
        "probeConnectFailed": probe_connect_failed,
        "storageStatus": plan.get("storageStatus", ""),
        "generatedCleanupBytesFreed": 0,
        "safeCleanupPerformed": False,
        "cleanupPlanPath": str(DEFAULT_OUTPUT.resolve()),
        "estimatedGeneratedCleanupBytes": int(plan.get("estimatedReclaimableBytes") or 0),
        "suspectedExternalBytes": int(plan.get("suspectedExternalBytes") or 0),
        "suspectedExternalGB": float(plan.get("suspectedExternalGB") or 0),
        "largestSuspectedExternalPath": str(plan.get("largestSuspectedExternalPath") or ""),
        "timedOutExternalProbePaths": plan.get("timedOutExternalProbePaths") or [],
        "volumeAccountingBytes": int(plan.get("volumeAccountingBytes") or 0),
        "volumeAccountingGB": float(plan.get("volumeAccountingGB") or 0),
        "largestVolumeAccountingPath": str(plan.get("largestVolumeAccountingPath") or ""),
        "timedOutVolumeAccountingPaths": plan.get("timedOutVolumeAccountingPaths") or [],
        "nextAction": plan.get("nextAction", "Free NAS volume space before trusting unattended mission writes."),
    }


def _remote_probe_script(remote_root: str) -> str:
    quoted_root = _quote_single(remote_root.rstrip("/"))
    paths = " ".join(_quote_single(path) for path in GENERATED_PATHS)
    external_paths = " ".join(_quote_single(path) for path in NON_GENERATED_PROBE_PATHS)
    volume_paths = " ".join(_quote_single(path) for path in VOLUME_ACCOUNTING_PROBE_PATHS)
    return f"""set -u
set -o pipefail 2>/dev/null || true
ROOT={quoted_root}
df -B1 /volume1/Saclay | awk 'NR==2 {{print "DF|" $0}}'
for rel in {paths}
do
  path="$ROOT/$rel"
  if [ -e "$path" ]; then
    du -sk "$path" 2>/dev/null | awk -v path="$path" '{{print "DU|" $1 "|" path}}'
  else
    echo "MISS|$path"
  fi
done
for path in {external_paths}
do
  if [ -e "$path" ]; then
    if timeout 4 du -sk "$path" 2>/dev/null | awk -v path="$path" '{{print "EXTDU|" $1 "|" path}}'; then
      :
    else
      echo "EXTTIMEOUT|$path"
    fi
  else
    echo "EXTMISS|$path"
  fi
done
for path in {volume_paths}
do
  if [ -e "$path" ]; then
    if timeout 3 du -sk "$path" 2>/dev/null | awk -v path="$path" '{{print "VOLDU|" $1 "|" path}}'; then
      :
    else
      echo "VOLTIMEOUT|$path"
    fi
  fi
done
if command -v btrfs >/dev/null 2>&1; then
  timeout 4 btrfs filesystem df /volume1/Saclay 2>/dev/null | sed 's/^/BTRFS|/' || true
fi
"""


def build_cleanup_plan(
    root: Path,
    *,
    remote_root: str = DEFAULT_REMOTE_ROOT,
    runbook_path: Path | None = None,
    timeout: int = 45,
) -> dict[str, Any]:
    root = root.resolve()
    runbook_path = runbook_path or root / ".agent_control" / "NAS_ACCESS_RUNBOOK.md"
    credentials = _load_nas_credentials(root=root, runbook_path=runbook_path)
    paramiko = _paramiko()
    try:
        client = _connect_nas_client(paramiko, credentials)
    except Exception as exc:
        checked_at = datetime.now(timezone.utc).isoformat()
        return {
            "schema": "fluxio.nas_storage_cleanup_plan.v1",
            "checkedAt": checked_at,
            "source": "bounded_ssh_connect_failed",
            "host": str(credentials.get("host") or ""),
            "mount": "/volume1/Saclay",
            "status": "probe_connect_failed",
            "storageStatus": "unknown",
            "candidateCount": 0,
            "estimatedReclaimableBytes": 0,
            "estimatedReclaimableMB": 0,
            "cleanupCandidates": [],
            "suspectedExternalUsage": [],
            "volumeAccountingUsage": [],
            "timedOutVolumeAccountingPaths": [],
            "safeMode": True,
            "destructiveActionsExecuted": False,
            "remoteRoot": remote_root,
            "sshExitCode": 255,
            "stderrPreview": f"{type(exc).__name__}: {exc}"[:1000],
            "nextAction": "NAS SSH did not complete a bounded handshake for storage accounting. Do not start NAS write-heavy missions until SSH and storage probes return cleanly.",
        }
    try:
        try:
            stdout, stderr, exit_code = _run_remote_bash_script(
                client,
                _remote_probe_script(remote_root),
                timeout=timeout,
            )
        except TimeoutError as exc:
            checked_at = datetime.now(timezone.utc).isoformat()
            return {
                "schema": "fluxio.nas_storage_cleanup_plan.v1",
                "checkedAt": checked_at,
                "source": "bounded_ssh_df_du_allowlist",
                "host": str(credentials.get("host") or ""),
                "mount": "/volume1/Saclay",
                "status": "probe_timeout",
                "storageStatus": "unknown",
                "candidateCount": 0,
                "estimatedReclaimableBytes": 0,
                "estimatedReclaimableMB": 0,
                "cleanupCandidates": [],
                "suspectedExternalUsage": [],
                "volumeAccountingUsage": [],
                "timedOutVolumeAccountingPaths": [],
                "safeMode": True,
                "destructiveActionsExecuted": False,
                "remoteRoot": remote_root,
                "sshExitCode": 124,
                "stderrPreview": str(exc)[:1000],
                "nextAction": "NAS storage probe timed out, which is itself evidence of storage or I/O pressure. Do not start NAS write-heavy missions until a bounded probe returns.",
            }
    finally:
        client.close()
    plan = _parse_remote_probe(stdout, host=str(credentials.get("host") or ""))
    plan["remoteRoot"] = remote_root
    plan["sshExitCode"] = exit_code
    plan["stderrPreview"] = stderr.strip()[:1000]
    if exit_code != 0:
        plan["status"] = "probe_failed"
        plan["nextAction"] = "Fix the bounded NAS cleanup probe before trusting generated cleanup candidates."
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan bounded NAS cleanup candidates without deleting anything.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--runbook", default="")
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--pressure-output", default=str(DEFAULT_PRESSURE_OUTPUT))
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-pressure", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    runbook = Path(args.runbook).resolve() if args.runbook else None
    plan = build_cleanup_plan(
        root,
        remote_root=args.remote_root,
        runbook_path=runbook,
        timeout=args.timeout,
    )
    if args.write:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        plan["outputPath"] = str(output.resolve())
    if args.write_pressure:
        pressure = _pressure_from_cleanup_plan(plan)
        pressure_output = Path(args.pressure_output)
        if not pressure_output.is_absolute():
            pressure_output = root / pressure_output
        pressure_output.parent.mkdir(parents=True, exist_ok=True)
        pressure_output.write_text(json.dumps(pressure, indent=2) + "\n", encoding="utf-8")
        plan["pressureOutputPath"] = str(pressure_output.resolve())
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
