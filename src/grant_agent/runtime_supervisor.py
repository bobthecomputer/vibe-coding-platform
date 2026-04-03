from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

from .models import (
    DelegatedApprovalRequest,
    DelegatedRuntimeEvent,
    DelegatedRuntimeSession,
    DelegatedSessionSnapshot,
    Mission,
    WorkspaceProfile,
    utc_now_iso,
)
from .runtimes import runtime_adapter_map


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
        execution_root = str(launch.get("workspace") or workspace.root_path)
        session = DelegatedRuntimeSession(
            delegated_id=delegated_id,
            runtime_id=runtime_id,
            launch_command=str(launch.get("launch_command", "")),
            status="queued",
            detail="Delegated runtime worker queued.",
            session_path=str(session_path),
            workspace_root=workspace.root_path,
            execution_root=execution_root,
            log_path=str(log_path),
            events_path=str(events_path),
            decision_path=str(decision_path),
            source_step_id=source_step_id,
        )
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
            cwd=str(self.root),
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
        return self.refresh_session(session)

    def refresh_session(self, session: DelegatedRuntimeSession | dict | str) -> DelegatedRuntimeSession:
        payload = self._load_session(session)
        if payload is None:
            raise FileNotFoundError(f"Unknown delegated runtime session: {session}")
        payload = self._sync_structured_state(payload)
        if payload.status in {"completed", "failed", "stopped"}:
            payload.updated_at = utc_now_iso()
            self._write_session(payload)
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
        self._write_session(payload)
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
            session_path=payload.session_path,
            log_path=payload.log_path,
            source_step_id=payload.source_step_id,
            pid=payload.pid,
            supervisor_pid=payload.supervisor_pid,
            exit_code=payload.exit_code,
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
        payload = json.loads(path.read_text(encoding="utf-8"))
        return DelegatedRuntimeSession(**payload)

    def _write_session(self, session: DelegatedRuntimeSession) -> None:
        path = Path(session.session_path) if session.session_path else self.control_dir / f"{session.delegated_id}.json"
        session.session_path = str(path)
        path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")

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
        events = _read_structured_events(Path(session.events_path)) if session.events_path else []
        session.event_cursor = len(events)
        session.latest_events = events[-max_events:]
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


def _read_structured_events(events_path: Path) -> list[dict]:
    if not events_path.exists():
        return []
    events: list[dict] = []
    for line in events_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


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
    if os.name == "nt":
        completed = subprocess.run(  # noqa: S603
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return str(pid) in completed.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
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
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
