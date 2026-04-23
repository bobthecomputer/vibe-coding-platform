from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path

try:
    from .subprocess_utils import background_creationflags
except ImportError:  # pragma: no cover - direct script fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from grant_agent.subprocess_utils import background_creationflags

STRUCTURED_EVENT_PREFIX = "FLUXIO_EVENT:"
HEARTBEAT_INTERVAL_SECONDS = max(
    float(os.environ.get("FLUXIO_HEARTBEAT_INTERVAL_SECONDS", "10")),
    0.05,
)


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    return _read_json_with_retries(path)


def _write_state(path: Path, updates: dict) -> dict:
    payload = _load_state(path)
    payload.update(updates)
    _atomic_write_json(path, payload)
    return payload


def _append_event(session_path: Path, *, kind: str, message: str, status: str = "", data: dict | None = None) -> dict:
    payload = _load_state(session_path)
    events_path = Path(payload.get("events_path", session_path.with_suffix(".events.jsonl"))).resolve()
    events_path.parent.mkdir(parents=True, exist_ok=True)
    event_timestamp = _utc_now()
    event = {
        "event_id": f"evt_{uuid.uuid4().hex[:10]}",
        "delegated_id": payload.get("delegated_id", ""),
        "runtime_id": payload.get("runtime_id", ""),
        "kind": kind,
        "message": message,
        "status": status or payload.get("status", ""),
        "created_at": event_timestamp,
        "data": data or {},
    }
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True) + "\n")
    latest_events, event_count = _read_events(events_path, max_events=5)
    updates = {
        "updated_at": event_timestamp,
        "last_event": message,
        "last_event_kind": kind,
        "latest_events": latest_events,
        "event_cursor": event_count,
    }
    current_status = str(event["status"] or "")
    if current_status in {"launching", "running", "waiting_for_approval"}:
        updates["heartbeat_at"] = event_timestamp
        updates["heartbeat_status"] = "healthy"
        updates["heartbeat_interval_seconds"] = max(
            int(round(HEARTBEAT_INTERVAL_SECONDS)),
            1,
        )
    elif current_status in {"completed", "failed", "stopped"}:
        updates["heartbeat_status"] = "inactive"
    _write_state(
        session_path,
        updates,
    )
    return event


def _read_events(path: Path, max_events: int = 0) -> tuple[list[dict], int]:
    if not path.exists():
        return [], 0
    event_count = 0
    if max_events > 0:
        rows: deque[dict] = deque(maxlen=max_events)
    else:
        rows = deque()
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_count += 1
            rows.append(event)
    return list(rows), event_count


def _read_json_with_retries(path: Path, retries: int = 8, delay: float = 0.02) -> dict:
    last_error: json.JSONDecodeError | None = None
    for attempt in range(retries):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            last_error = exc
            if attempt == retries - 1:
                break
            time.sleep(delay)
    raise RuntimeError(f"Unable to read delegated runtime state from {path}") from last_error


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for attempt in range(10):
        try:
            temp_path.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                break
            time.sleep(0.02)
    try:
        temp_path.unlink(missing_ok=True)
    except OSError:
        pass
    raise PermissionError(f"Unable to atomically update delegated runtime state at {path}")


def _creationflags() -> int:
    return background_creationflags()


def _runtime_env(session_path: Path, cwd: Path) -> dict[str, str]:
    payload = _load_state(session_path)
    env = os.environ.copy()
    env["FLUXIO_SESSION_FILE"] = str(session_path.resolve())
    env["FLUXIO_EVENTS_FILE"] = str(Path(payload.get("events_path", session_path.with_suffix(".events.jsonl"))).resolve())
    env["FLUXIO_LOG_FILE"] = str(Path(payload.get("log_path", session_path.with_suffix(".log"))).resolve())
    env["FLUXIO_APPROVAL_FILE"] = str(Path(payload.get("decision_path", session_path.with_suffix(".approval.json"))).resolve())
    env["FLUXIO_EXECUTION_ROOT"] = str(cwd.resolve())
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _parse_structured_event(line: str) -> dict | None:
    candidate = line.strip()
    if candidate.startswith(STRUCTURED_EVENT_PREFIX):
        candidate = candidate[len(STRUCTURED_EVENT_PREFIX) :].strip()
    else:
        return None
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _wait_for_approval(session_path: Path, child: subprocess.Popen, request: dict) -> str:
    payload = _load_state(session_path)
    decision_path = Path(payload.get("decision_path", session_path.with_suffix(".approval.json"))).resolve()
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        if decision_path.exists():
            try:
                decision = json.loads(decision_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                decision = {}
            status = str(decision.get("status", "approved"))
            resolved_at = str(decision.get("resolved_at", _utc_now()))
            request["status"] = status
            request["resolved_at"] = resolved_at
            request["resolved_by"] = str(decision.get("actor", "operator"))
            history = list(payload.get("approval_history", []))
            history.append(request)
            if status == "approved":
                _write_state(
                    session_path,
                    {
                        "status": "running",
                        "detail": "Delegated runtime resumed after approval.",
                        "pending_approval": {},
                        "approval_history": history,
                    },
                )
                _append_event(
                    session_path,
                    kind="approval.resolved",
                    message="Delegated approval approved by operator.",
                    status="running",
                    data={"request_id": request.get("request_id"), "decision": "approved"},
                )
                return "approved"
            _terminate_child(child)
            _write_state(
                session_path,
                {
                    "status": "failed",
                    "detail": "Delegated runtime was rejected by operator.",
                    "pending_approval": request,
                    "approval_history": history,
                },
            )
            _append_event(
                session_path,
                kind="approval.rejected",
                message="Delegated approval rejected by operator.",
                status="failed",
                data={"request_id": request.get("request_id"), "decision": "rejected"},
            )
            return "rejected"

        if child.poll() is not None:
            return "child_exited"
        time.sleep(0.1)


def _heartbeat_message(status: str) -> str:
    normalized = (status or "running").strip().lower()
    if normalized == "waiting_for_approval":
        return "Delegated runtime heartbeat: waiting for approval."
    if normalized == "launching":
        return "Delegated runtime heartbeat: launch still in progress."
    return "Delegated runtime heartbeat: session is healthy."


def _heartbeat_loop(
    session_path: Path,
    child: subprocess.Popen,
    stop_event: threading.Event,
) -> None:
    while not stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):
        if child.poll() is not None:
            return
        payload = _load_state(session_path)
        status = str(payload.get("status", "running"))
        if status in {"completed", "failed", "stopped"}:
            return
        _append_event(
            session_path,
            kind="session.heartbeat",
            message=_heartbeat_message(status),
            status=status,
            data={"phase": status},
        )


def run(session_path: Path, cwd: Path, command: str) -> int:
    session_path = session_path.resolve()
    cwd = cwd.resolve()
    payload = _load_state(session_path)
    log_path = Path(payload.get("log_path", session_path.with_suffix(".log"))).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    events_path = Path(payload.get("events_path", session_path.with_suffix(".events.jsonl"))).resolve()
    decision_path = Path(payload.get("decision_path", session_path.with_suffix(".approval.json"))).resolve()

    _write_state(
        session_path,
        {
            "status": "launching",
            "supervisor_pid": os.getpid(),
            "updated_at": _utc_now(),
            "detail": "Launching delegated runtime process.",
            "events_path": str(events_path),
            "decision_path": str(decision_path),
            "heartbeat_at": _utc_now(),
            "heartbeat_status": "healthy",
            "heartbeat_interval_seconds": max(
                int(round(HEARTBEAT_INTERVAL_SECONDS)),
                1,
            ),
        },
    )
    _append_event(
        session_path,
        kind="session.launching",
        message="Launching delegated runtime process.",
        status="launching",
    )

    with log_path.open("a", encoding="utf-8") as handle:
        child = subprocess.Popen(  # noqa: S603
            command,
            shell=True,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=_creationflags(),
            env=_runtime_env(session_path, cwd),
        )

        _write_state(
            session_path,
            {
                "status": "running",
                "pid": child.pid,
                "updated_at": _utc_now(),
                "detail": "Delegated runtime process is running.",
            },
        )
        _append_event(
            session_path,
            kind="session.running",
            message="Delegated runtime process is running.",
            status="running",
        )
        heartbeat_stop = threading.Event()
        heartbeat_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(session_path, child, heartbeat_stop),
            daemon=True,
        )
        heartbeat_thread.start()

        if child.stdout is not None:
            for raw_line in iter(child.stdout.readline, ""):
                if not raw_line:
                    if child.poll() is not None:
                        break
                    continue
                handle.write(raw_line)
                handle.flush()
                line = raw_line.strip()
                if not line:
                    continue
                structured = _parse_structured_event(line)
                if structured is None:
                    _append_event(
                        session_path,
                        kind="runtime.output",
                        message=line,
                        status="running",
                    )
                    continue

                kind = str(structured.get("kind", "runtime.event"))
                message = str(structured.get("message", line))
                runtime_status = str(structured.get("status", "running"))
                event_data = dict(structured.get("data", {}))
                if kind == "approval.request":
                    request = {
                        "request_id": str(structured.get("request_id", f"approval_{uuid.uuid4().hex[:8]}")),
                        "delegated_id": payload.get("delegated_id", ""),
                        "runtime_id": payload.get("runtime_id", ""),
                        "prompt": message,
                        "risk_level": str(structured.get("risk_level", event_data.get("risk_level", "medium"))),
                        "status": "pending",
                        "created_at": _utc_now(),
                        "resolved_at": None,
                        "resolved_by": "",
                        "metadata": event_data,
                    }
                    _write_state(
                        session_path,
                        {
                            "status": "waiting_for_approval",
                            "detail": "Delegated runtime is waiting for approval.",
                            "pending_approval": request,
                        },
                    )
                    _append_event(
                        session_path,
                        kind="approval.request",
                        message=message,
                        status="waiting_for_approval",
                        data=event_data,
                    )
                    decision = _wait_for_approval(session_path, child, request)
                    if decision == "rejected":
                        break
                    continue

                _write_state(
                    session_path,
                    {
                        "status": runtime_status or "running",
                        "detail": message,
                    },
                )
                _append_event(
                    session_path,
                    kind=kind,
                    message=message,
                    status=runtime_status or "running",
                    data=event_data,
                )

    heartbeat_stop.set()
    heartbeat_thread.join(timeout=1)
    return_code = child.wait()
    summary = _tail_summary(log_path)
    existing = _load_state(session_path)
    try:
        decision_path.unlink(missing_ok=True)
    except OSError:
        pass
    if existing.get("status") == "failed" and existing.get("pending_approval", {}).get("status") == "rejected":
        final_status = "failed"
    elif existing.get("status") == "stopped":
        final_status = "stopped"
    else:
        final_status = "completed" if return_code == 0 else "failed"
    _write_state(
        session_path,
        {
            "status": final_status,
            "exit_code": return_code,
            "updated_at": _utc_now(),
            "detail": (
                "Delegated runtime process completed."
                if final_status == "completed"
                else "Delegated runtime process failed."
            ),
            "last_event": summary or "runtime_finished",
            "heartbeat_status": "inactive",
        },
    )
    _append_event(
        session_path,
        kind="session.completed" if final_status == "completed" else "session.failed",
        message=summary or ("Delegated runtime completed." if final_status == "completed" else "Delegated runtime failed."),
        status=final_status,
        data={"exit_code": return_code},
    )
    return return_code


def _terminate_child(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(child.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return
    try:
        child.send_signal(signal.SIGTERM)
    except OSError:
        return


def _tail_summary(log_path: Path, max_lines: int = 3) -> str:
    if not log_path.exists():
        return ""
    lines = [line.strip() for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    return " | ".join(lines[-max_lines:])


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fluxio delegated runtime worker")
    parser.add_argument("--session", required=True, help="Delegated session JSON path")
    parser.add_argument("--cwd", required=True, help="Working directory")
    parser.add_argument("--command", required=True, help="Shell command to execute")
    args = parser.parse_args(argv)
    return run(Path(args.session), Path(args.cwd), args.command)


if __name__ == "__main__":
    raise SystemExit(main())
