from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import uuid
from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import time

from .models import (
    DelegatedApprovalRequest,
    DelegatedRuntimeEvent,
    DelegatedRuntimeSession,
    DelegatedSessionSnapshot,
    Mission,
    WorkspaceProfile,
    utc_now_iso,
)
from .execution_truth import derive_execution_target
from .runtimes import runtime_adapter_map

HEARTBEAT_STALE_FLOOR_SECONDS = max(
    int(os.environ.get("FLUXIO_HEARTBEAT_STALE_SECONDS", "35")),
    5,
)
SESSION_SETTLE_TIMEOUT_SECONDS = max(
    float(os.environ.get("FLUXIO_SESSION_SETTLE_SECONDS", "0.9")),
    0.0,
)
SESSION_QUICK_EXIT_GRACE_SECONDS = max(
    float(os.environ.get("FLUXIO_SESSION_QUICK_EXIT_GRACE_SECONDS", "0.45")),
    0.0,
)
SESSION_SETTLE_POLL_SECONDS = max(
    float(os.environ.get("FLUXIO_SESSION_SETTLE_POLL_SECONDS", "0.05")),
    0.01,
)
PID_ALIVE_CACHE_TTL_SECONDS = max(
    float(os.environ.get("FLUXIO_PID_CACHE_TTL_SECONDS", "0.35")),
    0.0,
)
PID_ALIVE_CACHE_MAX_SIZE = max(
    int(os.environ.get("FLUXIO_PID_CACHE_MAX_SIZE", "512")),
    64,
)
_PID_ALIVE_CACHE: dict[int, tuple[float, bool]] = {}


class DelegatedRuntimeSupervisor:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.control_dir = self.root / ".agent_control" / "runtime_sessions"
        self.control_dir.mkdir(parents=True, exist_ok=True)
        self.worker_path = Path(__file__).with_name("runtime_worker.py")

    def start_session(
        self,
        runtime_id: str,
        mission: Mission,
        workspace: WorkspaceProfile,
        source_step_id: str,
        resume: bool = False,
    ) -> DelegatedRuntimeSession:
        adapter = runtime_adapter_map()[runtime_id]
        launch = (
            adapter.resume_mission(mission, workspace)
            if resume
            else adapter.start_mission(mission, workspace)
        )
        delegated_id = f"delegate_{uuid.uuid4().hex[:8]}"
        session_path = self.control_dir / f"{delegated_id}.json"
        log_path = self.control_dir / f"{delegated_id}.log"
        events_path = self.control_dir / f"{delegated_id}.events.jsonl"
        decision_path = self.control_dir / f"{delegated_id}.approval.json"
        mission_scope = getattr(mission, "execution_scope", None)
        workspace_root = (
            str(getattr(mission_scope, "workspace_root", "") or "")
            or workspace.root_path
        )
        execution_root = str(launch.get("workspace") or workspace.root_path)
        session = DelegatedRuntimeSession(
            delegated_id=delegated_id,
            runtime_id=runtime_id,
            launch_command=str(launch.get("launch_command", "")),
            status="queued",
            detail="Delegated runtime worker queued.",
            session_path=str(session_path),
            workspace_root=workspace_root,
            execution_root=execution_root,
            log_path=str(log_path),
            events_path=str(events_path),
            decision_path=str(decision_path),
            source_step_id=source_step_id,
        )
        _apply_execution_truth(session)
        self._write_session(session)
        self._append_structured_event(
            session,
            kind="session.queued",
            message="Delegated runtime worker queued.",
            status="queued",
        )

        process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                str(self.worker_path),
                "--session",
                str(session_path),
                "--cwd",
                execution_root,
                "--command",
                session.launch_command,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_creationflags(),
        )
        session.supervisor_pid = process.pid
        session.status = "launching"
        session.updated_at = utc_now_iso()
        session.detail = "Delegated runtime supervisor started."
        self._write_session(session)
        self._append_structured_event(
            session,
            kind="session.launching",
            message="Delegated runtime supervisor started.",
            status="launching",
        )
        return self._settle_session(session)

    def refresh_session(self, session: DelegatedRuntimeSession | dict | str) -> DelegatedRuntimeSession:
        payload = self._load_session(session)
        if payload is None:
            raise FileNotFoundError(f"Unknown delegated runtime session: {session}")
        payload = self._sync_structured_state(payload)
        _apply_execution_truth(payload)
        _apply_heartbeat_truth(payload)
        if payload.status in {"completed", "failed", "stopped"}:
            return payload

        alive = _pid_alive(payload.supervisor_pid) or _pid_alive(payload.pid)
        if payload.pending_approval and payload.pending_approval.get("status") == "pending":
            payload.status = "waiting_for_approval"
            payload.detail = payload.pending_approval.get(
                "prompt",
                "Delegated runtime is waiting for operator approval.",
            )
        elif alive:
            payload.status = "running" if payload.pid else "launching"
            payload.detail = "Delegated runtime process is active."
        else:
            payload.status = "completed" if payload.exit_code in {0, None} else "failed"
            payload.detail = "Delegated runtime process is no longer active."
            payload.updated_at = utc_now_iso()
            _apply_heartbeat_truth(payload)
            self._write_session(payload)
            return payload
        _apply_heartbeat_truth(payload)
        return payload

    def stop_session(self, session: DelegatedRuntimeSession | dict | str) -> DelegatedRuntimeSession:
        payload = self._load_session(session)
        if payload is None:
            raise FileNotFoundError(f"Unknown delegated runtime session: {session}")
        if payload.pid:
            _terminate_pid(payload.pid)
        if payload.supervisor_pid and payload.supervisor_pid != payload.pid:
            _terminate_pid(payload.supervisor_pid)
        payload.status = "stopped"
        payload.detail = "Delegated runtime session was stopped by Fluxio."
        payload.updated_at = utc_now_iso()
        self._write_session(payload)
        self._append_structured_event(
            payload,
            kind="session.stopped",
            message="Delegated runtime session was stopped by Fluxio.",
            status="stopped",
        )
        return self.refresh_session(payload)

    def resolve_approval(
        self,
        session: DelegatedRuntimeSession | dict | str,
        status: str,
        actor: str = "operator",
    ) -> DelegatedRuntimeSession:
        payload = self._load_session(session)
        if payload is None:
            raise FileNotFoundError(f"Unknown delegated runtime session: {session}")
        if status not in {"approved", "rejected"}:
            raise ValueError(f"Unsupported approval status: {status}")
        if not payload.pending_approval:
            raise ValueError("Delegated runtime session is not waiting for approval.")

        request = dict(payload.pending_approval)
        request["status"] = status
        request["resolved_at"] = utc_now_iso()
        request["resolved_by"] = actor
        approval_history = list(payload.approval_history)
        approval_history.append(request)
        decision_path = Path(payload.decision_path)
        decision_path.write_text(
            json.dumps(
                {
                    "request_id": request.get("request_id"),
                    "status": status,
                    "actor": actor,
                    "resolved_at": request["resolved_at"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        payload.pending_approval = request
        payload.approval_history = approval_history
        payload.updated_at = utc_now_iso()
        payload.detail = f"Delegated approval {status} by {actor}."
        self._write_session(payload)
        self._append_structured_event(
            payload,
            kind="approval.decision",
            message=f"Delegated approval {status} by {actor}.",
            status="waiting_for_approval" if status == "approved" else "failed",
            data={"request_id": request.get("request_id"), "decision": status},
        )
        return self.refresh_session(payload)

    def read_events(self, session: DelegatedRuntimeSession | dict | str, max_lines: int = 5) -> list[dict]:
        payload = self.refresh_session(session)
        return payload.latest_events[-max_lines:]

    def append_operator_follow_up(
        self,
        session: DelegatedRuntimeSession | dict | str,
        message: str,
        *,
        actor: str = "operator",
        channel: str = "desktop",
    ) -> DelegatedRuntimeSession:
        payload = self._load_session(session)
        if payload is None:
            raise FileNotFoundError(f"Unknown delegated runtime session: {session}")
        clean_message = str(message).strip()
        if not clean_message:
            raise ValueError("Follow-up message cannot be empty.")
        self._append_structured_event(
            payload,
            kind="operator.followup",
            message=clean_message,
            status=payload.status,
            data={"actor": actor, "channel": channel},
        )
        return self.refresh_session(payload)

    def build_session_snapshot(
        self,
        session: DelegatedRuntimeSession | dict | str,
        max_events: int = 5,
    ) -> DelegatedSessionSnapshot:
        payload = self.refresh_session(session)
        latest_events = [
            DelegatedRuntimeEvent(**item)
            for item in payload.latest_events[-max_events:]
        ]
        pending_approval = (
            DelegatedApprovalRequest(**payload.pending_approval)
            if payload.pending_approval
            else None
        )
        return DelegatedSessionSnapshot(
            delegated_id=payload.delegated_id,
            runtime_id=payload.runtime_id,
            status=payload.status,
            detail=payload.detail,
            last_event=payload.last_event,
            last_event_kind=payload.last_event_kind,
            latest_events=latest_events,
            pending_approval=pending_approval,
            event_cursor=payload.event_cursor,
            created_at=payload.created_at,
            updated_at=payload.updated_at,
            workspace_root=payload.workspace_root,
            execution_root=payload.execution_root,
            execution_target=payload.execution_target,
            storage_mode=payload.storage_mode,
            host_locality=payload.host_locality,
            execution_target_detail=payload.execution_target_detail,
            session_path=payload.session_path,
            log_path=payload.log_path,
            source_step_id=payload.source_step_id,
            pid=payload.pid,
            supervisor_pid=payload.supervisor_pid,
            exit_code=payload.exit_code,
            heartbeat_at=payload.heartbeat_at,
            heartbeat_status=payload.heartbeat_status,
            heartbeat_age_seconds=payload.heartbeat_age_seconds,
            heartbeat_interval_seconds=payload.heartbeat_interval_seconds,
        )

    def _load_session(self, session: DelegatedRuntimeSession | dict | str) -> DelegatedRuntimeSession | None:
        if isinstance(session, DelegatedRuntimeSession):
            path = Path(session.session_path) if session.session_path else self.control_dir / f"{session.delegated_id}.json"
        elif isinstance(session, dict):
            if session.get("session_path"):
                path = Path(str(session["session_path"]))
            else:
                path = self.control_dir / f"{session['delegated_id']}.json"
        else:
            path = Path(session)
            if not path.suffix:
                path = self.control_dir / f"{session}.json"
        if not path.exists():
            return None
        payload = _read_json_with_retries(path)
        return DelegatedRuntimeSession(**payload)

    def _write_session(self, session: DelegatedRuntimeSession) -> None:
        path = Path(session.session_path) if session.session_path else self.control_dir / f"{session.delegated_id}.json"
        session.session_path = str(path)
        _atomic_write_json(path, asdict(session))

    def _append_structured_event(
        self,
        session: DelegatedRuntimeSession,
        *,
        kind: str,
        message: str,
        status: str = "",
        data: dict | None = None,
    ) -> DelegatedRuntimeEvent:
        events_path = Path(session.events_path) if session.events_path else self.control_dir / f"{session.delegated_id}.events.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        event = DelegatedRuntimeEvent(
            event_id=f"evt_{uuid.uuid4().hex[:10]}",
            delegated_id=session.delegated_id,
            runtime_id=session.runtime_id,
            kind=kind,
            message=message,
            status=status or session.status,
            data=data or {},
        )
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=True) + "\n")
        self._sync_structured_state(session)
        return event

    def _sync_structured_state(self, session: DelegatedRuntimeSession, max_events: int = 5) -> DelegatedRuntimeSession:
        if session.events_path:
            latest_events, event_count = _read_structured_events(
                Path(session.events_path),
                max_events=max_events,
            )
        else:
            latest_events, event_count = [], 0
        session.event_cursor = event_count
        session.latest_events = latest_events
        if session.latest_events:
            latest = session.latest_events[-1]
            session.last_event = latest.get("message", session.last_event)
            session.last_event_kind = latest.get("kind", session.last_event_kind)
        if session.log_path:
            log_path = Path(session.log_path)
            if log_path.exists() and not session.last_event:
                session.last_event = _tail_summary(log_path) or session.last_event
        if session.pending_approval and session.pending_approval.get("status") == "approved":
            session.pending_approval = {}
        return session

    def _settle_session(self, session: DelegatedRuntimeSession) -> DelegatedRuntimeSession:
        current = self.refresh_session(session)
        if SESSION_SETTLE_TIMEOUT_SECONDS <= 0:
            return current
        terminal_statuses = {"completed", "failed", "stopped", "waiting_for_approval"}
        if current.status in terminal_statuses:
            return current
        now = time.monotonic()
        settle_deadline = now + SESSION_SETTLE_TIMEOUT_SECONDS
        quick_exit_deadline = now + min(
            SESSION_SETTLE_TIMEOUT_SECONDS,
            SESSION_QUICK_EXIT_GRACE_SECONDS,
        )
        while time.monotonic() < settle_deadline:
            if current.status in terminal_statuses:
                return current
            if current.status not in {"launching", "running"}:
                return current
            if (
                current.status == "running"
                and time.monotonic() >= quick_exit_deadline
            ):
                return current
            time.sleep(SESSION_SETTLE_POLL_SECONDS)
            current = self.refresh_session(current)
        return current


def _read_structured_events(events_path: Path, max_events: int = 5) -> tuple[list[dict], int]:
    if not events_path.exists():
        return [], 0
    event_count = 0
    tail: deque[dict] = deque(maxlen=max(1, max_events))
    with events_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_count += 1
            tail.append(event)
    return list(tail), event_count


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
    raise RuntimeError(f"Unable to read delegated session state from {path}") from last_error


def _apply_execution_truth(session: DelegatedRuntimeSession) -> DelegatedRuntimeSession:
    truth = derive_execution_target(
        execution_root=session.execution_root,
        workspace_root=session.workspace_root,
        strategy="delegated_runtime",
    )
    session.execution_target = truth["execution_target"]
    session.storage_mode = truth["storage_mode"]
    session.host_locality = truth["host_locality"]
    session.execution_target_detail = truth["execution_target_detail"]
    return session


def _parse_utc_timestamp(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_seconds(value: str) -> int | None:
    parsed = _parse_utc_timestamp(value)
    if parsed is None:
        return None
    delta = datetime.now(timezone.utc) - parsed
    return max(int(delta.total_seconds()), 0)


def _apply_heartbeat_truth(session: DelegatedRuntimeSession) -> DelegatedRuntimeSession:
    active_statuses = {"launching", "running", "waiting_for_approval"}
    if session.status in {"completed", "failed", "stopped"}:
        session.heartbeat_status = "inactive"
        session.heartbeat_age_seconds = _age_seconds(
            session.heartbeat_at or session.updated_at
        )
        return session

    heartbeat_source = session.heartbeat_at or session.updated_at
    heartbeat_age = _age_seconds(heartbeat_source)
    session.heartbeat_age_seconds = heartbeat_age
    if session.status not in active_statuses:
        session.heartbeat_status = "unknown"
        return session
    stale_after = max(
        int(session.heartbeat_interval_seconds or 10) * 3,
        HEARTBEAT_STALE_FLOOR_SECONDS,
    )
    if heartbeat_age is None:
        session.heartbeat_status = "unknown"
    elif heartbeat_age > stale_after:
        session.heartbeat_status = "stale"
    else:
        session.heartbeat_status = "healthy"
    return session


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
    raise PermissionError(f"Unable to atomically update delegated session state at {path}")


def _creationflags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return 0


def _tail_summary(log_path: Path, max_lines: int = 3) -> str:
    lines = [
        line.strip()
        for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    ]
    return " | ".join(lines[-max_lines:])


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    now = time.monotonic()
    if PID_ALIVE_CACHE_TTL_SECONDS > 0:
        cached = _PID_ALIVE_CACHE.get(pid)
        if cached and now - cached[0] <= PID_ALIVE_CACHE_TTL_SECONDS:
            return cached[1]
    if os.name == "nt":
        completed = subprocess.run(  # noqa: S603
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        alive = str(pid) in completed.stdout
        _cache_pid_liveness(pid, alive, now)
        return alive
    try:
        os.kill(pid, 0)
    except OSError:
        _cache_pid_liveness(pid, False, now)
        return False
    _cache_pid_liveness(pid, True, now)
    return True


def _terminate_pid(pid: int) -> None:
    if not pid:
        return
    if os.name == "nt":
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        _PID_ALIVE_CACHE.pop(pid, None)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    _PID_ALIVE_CACHE.pop(pid, None)


def _cache_pid_liveness(pid: int, alive: bool, now: float) -> None:
    if PID_ALIVE_CACHE_TTL_SECONDS <= 0:
        return
    if len(_PID_ALIVE_CACHE) >= PID_ALIVE_CACHE_MAX_SIZE:
        expiry_cutoff = now - PID_ALIVE_CACHE_TTL_SECONDS
        expired = [key for key, value in _PID_ALIVE_CACHE.items() if value[0] < expiry_cutoff]
        for key in expired:
            _PID_ALIVE_CACHE.pop(key, None)
    while len(_PID_ALIVE_CACHE) >= PID_ALIVE_CACHE_MAX_SIZE:
        oldest_pid = min(
            _PID_ALIVE_CACHE.items(),
            key=lambda item: item[1][0],
        )[0]
        _PID_ALIVE_CACHE.pop(oldest_pid, None)
    _PID_ALIVE_CACHE[pid] = (now, alive)
