from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


DEFAULT_REMOTE_ROOT = "/volume1/Saclay/projects/syntelos/current"
DEFAULT_REMOTE_PYTHON = "/volume1/Saclay/projects/syntelos/.venv/bin/python"
NON_SECRET_EVIDENCE_FILES = (
    ".agent_control/cross_device_launch_rehearsals/receipts.jsonl",
    ".agent_control/cross_device_launch_rehearsals/latest.json",
    ".agent_control/deployment_evidence/private-nas-web.json",
    ".agent_control/deployment_evidence/public-web.json",
    ".agent_control/release_candidates/public-web/release-candidate.json",
    ".agent_control/release_artifacts/latest.json",
    ".agent_control/red_team_escalation_history.jsonl",
    ".agent_control/t3_code_benchmark_latest.json",
    ".agent_control/self_improvement_evidence/latest.json",
    ".agent_control/self_improvement_evidence/watchdog_latest.json",
    ".agent_control/self_improvement_evidence/watchdog_history.jsonl",
    ".agent_control/parallel_dispatch_evidence/latest.json",
    ".agent_control/route_trust_sampling/latest.json",
    ".agent_control/route_trust_sampling/closeout_review_latest.json",
    ".agent_control/route_trust_sampling/loop_latest.json",
    ".agent_control/launcher_package/latest.json",
    ".agent_control/public_launch_readiness/latest.json",
    ".agent_control/public_launch_readiness/staging-plan.json",
    ".agent_control/public_launch_readiness/doctor.json",
    ".agent_control/publication/github-release-plan.json",
    ".agent_control/publication/github-release.json",
    ".agent_control/live_mission_detail_performance_latest.json",
    ".agent_control/live_mission_detail_status_latest.json",
    ".agent_control/mission_artifact_repair_plan_latest.json",
    ".agent_control/mission_evidence_manifest_latest.json",
    ".agent_control/nas_storage_cleanup_plan_latest.json",
    ".agent_control/nas_storage_pressure_latest.json",
)
ROOT_BROWSER_REPORT_PATTERNS = (
    "*live-agent*check.json",
    "*live-control*check.json",
    "*phone-progress*check.json",
    "*-check.json",
)
ROOT_BROWSER_REPORT_SCHEMAS = {
    "fluxio.authenticated_live_agent.v1",
    "fluxio.authenticated_live_control.v1",
    "fluxio.authenticated_phone_progress.v1",
}


def _parse_runbook(runbook: str) -> dict[str, object]:
    def required(pattern: str, label: str) -> str:
        match = re.search(pattern, runbook)
        if not match:
            raise RuntimeError(f"Missing {label} in NAS access runbook.")
        return match.group(1)

    return {
        "host": required(r"Tailscale IP: `([^`]+)`", "Tailscale IP"),
        "user": required(r"SSH user: `([^`]+)`", "SSH user"),
        "password": required(r"SSH password: `([^`]+)`", "SSH password"),
        "port": int(required(r"SSH port: `([^`]+)`", "SSH port")),
    }


def _decode_windows_dpapi_secret(path: Path) -> str:
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI credentials can only be decrypted on Windows.")
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
        ]

    raw = bytes.fromhex(path.read_text(encoding="utf-8").strip())
    input_buffer = ctypes.create_string_buffer(raw)
    input_blob = DATA_BLOB(len(raw), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        raise RuntimeError("Windows DPAPI credential decrypt failed.")
    try:
        plain = ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
    if b"\x00" in plain:
        return plain.decode("utf-16-le").strip("\x00\r\n ")
    return plain.decode("utf-8").strip()


def _load_nas_credentials(
    *,
    root: Path,
    runbook_path: Path,
    dpapi_decoder: Any = _decode_windows_dpapi_secret,
) -> dict[str, object]:
    credentials = _parse_runbook(runbook_path.read_text(encoding="utf-8"))
    control_dir = root / ".agent_control"
    json_path = control_dir / "nas_codex2_100_125_54_118.json"
    if json_path.exists():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            credentials.update(
                {
                    "host": payload.get("host") or credentials.get("host"),
                    "user": payload.get("user") or credentials.get("user"),
                    "port": int(payload.get("port") or credentials.get("port") or 22),
                    "password": payload.get("secret") or credentials.get("password"),
                }
            )
    env_password = os.environ.get("FLUXIO_NAS_SSH_PASSWORD", "").strip()
    if env_password:
        credentials["password"] = env_password
        return credentials
    host_key = str(credentials.get("host") or "100.125.54.118").replace(".", "_")
    user_key = str(credentials.get("user") or "Codex2").lower()
    dpapi_candidates = [
        control_dir / f"nas_{user_key}_{host_key}.dpapi",
        *sorted(control_dir.glob(f"nas_*_{host_key}.dpapi")),
    ]
    for dpapi_path in dpapi_candidates:
        if not dpapi_path.exists():
            continue
        try:
            secret = str(dpapi_decoder(dpapi_path)).strip()
        except Exception:
            continue
        if secret:
            credentials["password"] = secret
            break
    return credentials


def _extract_json(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        raise RuntimeError("NAS system-audit command returned no JSON.")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("NAS system-audit command did not include a JSON object.")
    return json.loads(text[start : end + 1])


def _quote_single(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _paramiko() -> Any:
    try:
        import paramiko
    except ImportError as exc:
        raise RuntimeError("Install paramiko to sync the NAS system audit over SSH.") from exc
    return paramiko


def _connect_nas_client(paramiko: Any, credentials: dict[str, object]) -> Any:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        str(credentials["host"]),
        port=int(credentials["port"]),
        username=str(credentials["user"]),
        password=str(credentials["password"]),
        timeout=12,
        banner_timeout=12,
        auth_timeout=30,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def _run_remote_bash_script(client: Any, script: str, *, timeout: int) -> tuple[str, str, int]:
    stdin, stdout, _stderr = client.exec_command("bash -s", timeout=max(5, timeout))
    stdin.write(script)
    stdin.channel.shutdown_write()
    channel = stdout.channel
    deadline = time.monotonic() + max(5, timeout)
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []

    def drain() -> None:
        while channel.recv_ready():
            stdout_chunks.append(channel.recv(65536))
        while channel.recv_stderr_ready():
            stderr_chunks.append(channel.recv_stderr(65536))

    while not channel.exit_status_ready():
        drain()
        if time.monotonic() > deadline:
            drain()
            channel.close()
            stderr_preview = b"".join(stderr_chunks).decode("utf-8", "replace").strip()
            raise TimeoutError(
                stderr_preview
                or f"Remote NAS command exceeded {timeout} second timeout before returning an exit status."
            )
        time.sleep(0.1)

    drain()
    drain_until = time.monotonic() + 2
    while time.monotonic() < drain_until and (channel.recv_ready() or channel.recv_stderr_ready()):
        drain()
        time.sleep(0.05)
    exit_code = channel.recv_exit_status()
    return (
        b"".join(stdout_chunks).decode("utf-8", "replace"),
        b"".join(stderr_chunks).decode("utf-8", "replace"),
        exit_code,
    )


def _safe_evidence_relative_path(relative_path: str) -> str:
    path = PurePosixPath(relative_path.replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"Unsafe evidence path: {relative_path}")
    if path.parts[0] != ".agent_control":
        raise ValueError(f"Evidence path must stay under .agent_control: {relative_path}")
    return path.as_posix()


def _latest_release_artifact_paths(local_root: Path) -> tuple[list[tuple[Path, str]], list[str]]:
    latest_path = local_root / ".agent_control" / "release_artifacts" / "latest.json"
    if not latest_path.is_file():
        return [], []
    try:
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], [".agent_control/release_artifacts/latest.json: invalid JSON"]
    archive_root_raw = str(latest.get("archiveRoot") or "").strip()
    if not archive_root_raw:
        return [], [".agent_control/release_artifacts/latest.json: archiveRoot missing"]
    archive_root = Path(archive_root_raw)
    if not archive_root.is_absolute():
        archive_root = local_root / archive_root
    try:
        resolved_archive_root = archive_root.resolve()
        release_artifacts_root = (local_root / ".agent_control" / "release_artifacts").resolve()
        resolved_archive_root.relative_to(release_artifacts_root)
    except (OSError, ValueError):
        return [], [".agent_control/release_artifacts/latest.json: archiveRoot outside release_artifacts"]
    if not resolved_archive_root.is_dir():
        return [], [str(PurePosixPath(".agent_control/release_artifacts") / resolved_archive_root.name)]
    paths: list[tuple[Path, str]] = []
    for path in sorted(resolved_archive_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(local_root).as_posix()
        _safe_evidence_relative_path(relative)
        paths.append((path, relative))
    return paths, []


def _latest_root_browser_report_paths(local_root: Path) -> list[tuple[Path, str]]:
    control_root = local_root / ".agent_control"
    if not control_root.is_dir():
        return []
    selected: dict[str, tuple[float, Path]] = {}
    for pattern in ROOT_BROWSER_REPORT_PATTERNS:
        candidate_paths = [
            *control_root.glob(pattern),
            *(control_root / "screenshots").glob(pattern),
        ]
        for path in candidate_paths:
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict) or payload.get("schema") not in ROOT_BROWSER_REPORT_SCHEMAS:
                continue
            schema = str(payload.get("schema") or pattern)
            timestamp = _parse_evidence_timestamp(json.dumps(payload))
            current = selected.get(schema)
            if current is None or timestamp > current[0]:
                selected[schema] = (timestamp, path)
    paths: list[tuple[Path, str]] = []
    for _timestamp, path in selected.values():
        relative = path.relative_to(local_root).as_posix()
        _safe_evidence_relative_path(relative)
        paths.append((path, relative))
    return sorted(paths, key=lambda item: item[1])


def _collect_local_evidence_candidates(local_root: Path) -> tuple[list[tuple[Path, str]], list[str]]:
    candidates: list[tuple[Path, str]] = []
    missing: list[str] = []
    seen: set[str] = set()
    for relative_path in NON_SECRET_EVIDENCE_FILES:
        safe_relative_path = _safe_evidence_relative_path(relative_path)
        source = local_root / safe_relative_path
        if not source.is_file():
            missing.append(safe_relative_path)
            continue
        candidates.append((source, safe_relative_path))
        seen.add(safe_relative_path)
    release_artifact_paths, release_artifact_missing = _latest_release_artifact_paths(local_root)
    missing.extend(release_artifact_missing)
    for source, relative_path in [
        *release_artifact_paths,
        *_latest_root_browser_report_paths(local_root),
    ]:
        if relative_path in seen:
            continue
        candidates.append((source, relative_path))
        seen.add(relative_path)
    return candidates, missing


def _build_local_evidence_archive(
    local_root: Path,
    *,
    allowed_relative_paths: set[str] | None = None,
) -> tuple[bytes, list[str], list[str]]:
    archive_buffer = io.BytesIO()
    pushed: list[str] = []
    candidates, missing = _collect_local_evidence_candidates(local_root)
    with tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
        for source, relative_path in candidates:
            if allowed_relative_paths is not None and relative_path not in allowed_relative_paths:
                continue
            archive.add(source, arcname=relative_path, recursive=False)
            pushed.append(relative_path)
    return archive_buffer.getvalue(), pushed, missing


def _read_text_if_possible(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _local_evidence_is_newer_than_remote(source: Path, remote_content: str | None) -> bool:
    if remote_content is None:
        return True
    local_content = _read_text_if_possible(source)
    if not local_content:
        return False
    return _should_keep_local_evidence(local_content, remote_content)


def _push_local_evidence_files(
    client: Any,
    *,
    local_root: Path,
    remote_root: str,
    timeout: int,
) -> tuple[list[str], list[str]]:
    candidates, missing = _collect_local_evidence_candidates(local_root)
    allowed_relative_paths: set[str] = set()
    for source, relative_path in candidates:
        remote_content = _read_remote_evidence_file(
            client,
            remote_root=remote_root,
            relative_path=relative_path,
            timeout=timeout,
        )
        if _local_evidence_is_newer_than_remote(source, remote_content):
            allowed_relative_paths.add(relative_path)
    archive_bytes, pushed, missing = _build_local_evidence_archive(
        local_root,
        allowed_relative_paths=allowed_relative_paths,
    )
    if not pushed:
        return pushed, missing
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    remote_archive = f"/tmp/fluxio-local-evidence-{stamp}.tgz"
    stdin, stdout, stderr = client.exec_command(f"cat > {_quote_single(remote_archive)}", timeout=timeout)
    stdin.write(archive_bytes)
    stdin.channel.shutdown_write()
    stdout.read()
    upload_stderr = stderr.read().decode("utf-8", "replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        raise RuntimeError(upload_stderr or f"NAS evidence upload failed with exit code {exit_code}.")
    command = (
        "set -e\n"
        f"ROOT=$(readlink -f {_quote_single(remote_root)})\n"
        f"ARCHIVE={_quote_single(remote_archive)}\n"
        "tar -tzf \"$ARCHIVE\" | while IFS= read -r REL; do\n"
        "  case \"$REL\" in .agent_control/*) ;; *) exit 12 ;; esac\n"
        "  case \"$REL\" in /*|../*|*/../*|*'/../'*) exit 13 ;; esac\n"
        "done\n"
        "tar -xzf \"$ARCHIVE\" -C \"$ROOT\"\n"
        "rm -f \"$ARCHIVE\"\n"
    )
    stdin, stdout, stderr = client.exec_command("bash -s", timeout=timeout)
    stdin.write(command)
    stdin.channel.shutdown_write()
    extract_stdout = stdout.read().decode("utf-8", "replace").strip()
    extract_stderr = stderr.read().decode("utf-8", "replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        raise RuntimeError(extract_stderr or extract_stdout or f"NAS evidence extract failed with exit code {exit_code}.")
    return pushed, missing


def _read_remote_evidence_file(
    client: Any,
    *,
    remote_root: str,
    relative_path: str,
    timeout: int,
) -> str | None:
    if relative_path.startswith("/") or ".." in Path(relative_path).parts:
        raise ValueError(f"Unsafe evidence path: {relative_path}")
    command = (
        "ROOT="
        + _quote_single(remote_root)
        + "; REL="
        + _quote_single(relative_path)
        + '; TARGET="$ROOT/$REL"; '
        + 'case "$TARGET" in "$ROOT"/*) ;; *) exit 9 ;; esac; '
        + 'if test -f "$TARGET"; then cat "$TARGET"; else exit 44; fi'
    )
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    content = stdout.read().decode("utf-8", "replace")
    stderr.read()
    exit_code = stdout.channel.recv_exit_status()
    if exit_code == 44:
        return None
    if exit_code != 0:
        return None
    return content


def _write_remote_text_file(
    client: Any,
    *,
    remote_root: str,
    relative_path: str,
    content: str,
    timeout: int,
) -> None:
    safe_relative_path = _safe_evidence_relative_path(relative_path)
    command = (
        "set -e\n"
        f"ROOT=$(readlink -f {_quote_single(remote_root)})\n"
        f"REL={_quote_single(safe_relative_path)}\n"
        "TARGET=\"$ROOT/$REL\"\n"
        "case \"$TARGET\" in \"$ROOT\"/*) ;; *) exit 9 ;; esac\n"
        "mkdir -p \"$(dirname \"$TARGET\")\"\n"
        "cat > \"$TARGET\"\n"
    )
    stdin, stdout, stderr = client.exec_command("bash -s", timeout=timeout)
    stdin.write(command)
    stdin.write(content)
    stdin.channel.shutdown_write()
    raw_stdout = stdout.read().decode("utf-8", "replace").strip()
    raw_stderr = stderr.read().decode("utf-8", "replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        raise RuntimeError(raw_stderr or raw_stdout or f"NAS evidence write failed with exit code {exit_code}.")


def _parse_evidence_timestamp(content: str) -> float:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        latest = 0.0
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            latest = max(latest, _parse_evidence_timestamp(json.dumps(row)))
        return latest
    if not isinstance(payload, dict):
        return 0.0
    raw_timestamp = str(
        payload.get("checkedAt")
        or payload.get("generatedAt")
        or payload.get("recordedAt")
        or ""
    ).strip()
    if raw_timestamp.endswith("Z"):
        raw_timestamp = raw_timestamp[:-1] + "+00:00"
    if not raw_timestamp:
        return 0.0
    try:
        return datetime.fromisoformat(raw_timestamp).timestamp()
    except ValueError:
        return 0.0


def _should_keep_local_evidence(local_content: str, remote_content: str) -> bool:
    local_ts = _parse_evidence_timestamp(local_content)
    remote_ts = _parse_evidence_timestamp(remote_content)
    return local_ts > 0 and remote_ts > 0 and local_ts > remote_ts


def _sync_remote_evidence_files(
    client: Any,
    *,
    local_root: Path,
    remote_root: str,
    timeout: int,
) -> tuple[list[str], list[str]]:
    synced: list[str] = []
    missing: list[str] = []
    for relative_path in NON_SECRET_EVIDENCE_FILES:
        content = _read_remote_evidence_file(
            client,
            remote_root=remote_root,
            relative_path=relative_path,
            timeout=timeout,
        )
        if content is None:
            missing.append(relative_path)
            continue
        target = local_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            try:
                local_content = target.read_text(encoding="utf-8")
            except OSError:
                local_content = ""
            if local_content and _should_keep_local_evidence(local_content, content):
                synced.append(relative_path)
                continue
        target.write_text(content, encoding="utf-8")
        synced.append(relative_path)
    return synced, missing


def sync_nas_system_audit(
    *,
    root: Path,
    output: Path,
    runbook_path: Path,
    remote_root: str = DEFAULT_REMOTE_ROOT,
    remote_python: str = DEFAULT_REMOTE_PYTHON,
    timeout: int = 180,
    sync_evidence_files: bool = True,
    push_local_evidence_files: bool = False,
    publish_remote_snapshot: bool = False,
) -> dict:
    credentials = _load_nas_credentials(root=root, runbook_path=runbook_path)
    paramiko = _paramiko()
    client = _connect_nas_client(paramiko, credentials)
    try:
        pushed_evidence_files: list[str] = []
        local_missing_evidence_files: list[str] = []
        if push_local_evidence_files:
            pushed_evidence_files, local_missing_evidence_files = _push_local_evidence_files(
                client,
                local_root=root,
                remote_root=remote_root,
                timeout=min(timeout, 60),
            )
        command = f"""set -e
CURRENT=$(readlink -f {remote_root})
cd "$CURRENT"
export PYTHONPATH="$CURRENT/src:$PYTHONPATH"
{remote_python} -m grant_agent.cli system-audit --root "$CURRENT" --json
"""
        raw_stdout, raw_stderr, exit_code = _run_remote_bash_script(
            client,
            command,
            timeout=timeout,
        )
    finally:
        client.close()
    if exit_code != 0:
        raise RuntimeError(raw_stderr.strip() or raw_stdout.strip() or f"NAS system-audit failed with exit code {exit_code}.")
    audit = _extract_json(raw_stdout)
    source_root = str(audit.get("workspaceRoot") or remote_root)
    synced_evidence_files: list[str] = []
    missing_evidence_files: list[str] = []
    if sync_evidence_files:
        client = _connect_nas_client(paramiko, credentials)
        try:
            synced_evidence_files, missing_evidence_files = _sync_remote_evidence_files(
                client,
                local_root=root,
                remote_root=source_root,
                timeout=min(timeout, 60),
            )
        finally:
            client.close()
    checked_at = datetime.now(timezone.utc).isoformat()
    wrapper = {
        "schema": "fluxio.live_nas_system_audit_snapshot.v1",
        "ok": True,
        "checkedAt": checked_at,
        "sourceHost": str(credentials["host"]),
        "sourceRoot": source_root,
        "maxAgeSeconds": 6 * 60 * 60,
        "remoteSnapshotPublished": publish_remote_snapshot,
        "pushedEvidenceFiles": pushed_evidence_files,
        "localMissingEvidenceFiles": local_missing_evidence_files,
        "syncedEvidenceFiles": synced_evidence_files,
        "missingEvidenceFiles": missing_evidence_files,
        "audit": audit,
        "stderrPreview": raw_stderr.strip()[:500],
    }
    if publish_remote_snapshot:
        client = _connect_nas_client(paramiko, credentials)
        try:
            _write_remote_text_file(
                client,
                remote_root=source_root,
                relative_path=".agent_control/live_nas_system_audit_latest.json",
                content=json.dumps(wrapper, indent=2),
                timeout=min(timeout, 60),
            )
        finally:
            client.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")
    return wrapper


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch the current NAS system audit into local evidence.")
    parser.add_argument("--root", default=".", help="Local project root.")
    parser.add_argument("--output", default="", help="Output JSON path.")
    parser.add_argument("--runbook", default="", help="NAS access runbook path.")
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT, help="Remote current release symlink/root.")
    parser.add_argument("--remote-python", default=DEFAULT_REMOTE_PYTHON, help="Remote Python executable.")
    parser.add_argument("--timeout", type=int, default=180, help="SSH command timeout in seconds.")
    parser.add_argument(
        "--push-local-evidence-files",
        action="store_true",
        help="Upload current local non-secret evidence to the NAS before running the live audit.",
    )
    parser.add_argument(
        "--publish-remote-snapshot",
        action="store_true",
        help="Write the fresh live audit wrapper back to the NAS so the web app cannot read an older snapshot.",
    )
    parser.add_argument("--skip-evidence-files", action="store_true", help="Only fetch the audit JSON wrapper.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    output = Path(args.output).resolve() if args.output else root / ".agent_control" / "live_nas_system_audit_latest.json"
    runbook_path = Path(args.runbook).resolve() if args.runbook else root / ".agent_control" / "NAS_ACCESS_RUNBOOK.md"
    wrapper = sync_nas_system_audit(
        root=root,
        output=output,
        runbook_path=runbook_path,
        remote_root=args.remote_root,
        remote_python=args.remote_python,
        timeout=args.timeout,
        sync_evidence_files=not args.skip_evidence_files,
        push_local_evidence_files=args.push_local_evidence_files,
        publish_remote_snapshot=args.publish_remote_snapshot,
    )
    route_trust = wrapper.get("audit", {}).get("routeTrustMaturity", {})
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output),
                "checkedAt": wrapper.get("checkedAt"),
                "sourceRoot": wrapper.get("sourceRoot"),
                "remoteSnapshotPublished": wrapper.get("remoteSnapshotPublished", False),
                "pushedEvidenceFiles": wrapper.get("pushedEvidenceFiles", []),
                "localMissingEvidenceFiles": wrapper.get("localMissingEvidenceFiles", []),
                "syncedEvidenceFiles": wrapper.get("syncedEvidenceFiles", []),
                "missingEvidenceFiles": wrapper.get("missingEvidenceFiles", []),
                "summary": wrapper.get("audit", {}).get("summary", ""),
                "routeTrustMaturity": route_trust,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
