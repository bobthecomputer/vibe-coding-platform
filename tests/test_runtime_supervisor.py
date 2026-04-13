from __future__ import annotations

import os
import pathlib
import json
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.models import Mission, WorkspaceProfile
from grant_agent.runtime_supervisor import DelegatedRuntimeSupervisor


class RuntimeSupervisorTests(unittest.TestCase):
    @mock.patch("grant_agent.runtime_supervisor.runtime_adapter_map")
    def test_supervisor_launches_and_completes_delegated_session(
        self,
        runtime_map: mock.Mock,
    ) -> None:
        class _FakeAdapter:
            def start_mission(self, mission, workspace):
                return {
                    "launch_command": f'"{sys.executable}" -c "import time; print(\'lane started\'); time.sleep(0.2); print(\'lane done\')"',
                    "workspace": workspace.root_path,
                }

            def resume_mission(self, mission, workspace):
                return self.start_mission(mission, workspace)

        runtime_map.return_value = {"hermes": _FakeAdapter()}

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            with mock.patch.dict(
                os.environ,
                {"FLUXIO_HEARTBEAT_INTERVAL_SECONDS": "0.05"},
                clear=False,
            ):
                supervisor = DelegatedRuntimeSupervisor(root)
                mission = Mission(
                    mission_id="mission_delegate",
                    workspace_id="workspace_primary",
                    runtime_id="hermes",
                    objective="Delegated runtime lifecycle",
                    success_checks=[],
                )
                workspace = WorkspaceProfile(
                    workspace_id="workspace_primary",
                    name="Demo",
                    root_path=str(root),
                    default_runtime="hermes",
                    workspace_type="python",
                )

                session = supervisor.start_session(
                    runtime_id="hermes",
                    mission=mission,
                    workspace=workspace,
                    source_step_id="step_delegate",
                )
                self.assertIn(session.status, {"launching", "running", "completed"})

                for _ in range(20):
                    time.sleep(0.15)
                    session = supervisor.refresh_session(session)
                    if session.status in {"completed", "failed"}:
                        break

                self.assertEqual(session.status, "completed")
                self.assertTrue(pathlib.Path(session.session_path).exists())
                self.assertTrue(pathlib.Path(session.log_path).exists())
                self.assertTrue(pathlib.Path(session.events_path).exists())
                self.assertIn("lane", pathlib.Path(session.log_path).read_text(encoding="utf-8"))
                self.assertTrue(any(item["kind"].startswith("session.") for item in session.latest_events))
                self.assertTrue(session.heartbeat_at)
                self.assertIn(session.heartbeat_status, {"healthy", "inactive"})
                self.assertTrue(
                    any(item["kind"] == "session.heartbeat" for item in session.latest_events)
                )
                # Explicit shutdown avoids transient file locks on Windows temp cleanup.
                supervisor.stop_session(session)
                time.sleep(0.2)

    @mock.patch("grant_agent.runtime_supervisor.runtime_adapter_map")
    def test_supervisor_handles_structured_approval_callbacks(
        self,
        runtime_map: mock.Mock,
    ) -> None:
        class _FakeAdapter:
            def start_mission(self, mission, workspace):
                return {
                    "launch_command": f'"{sys.executable}" "{worker_script}"',
                    "workspace": workspace.root_path,
                }

            def resume_mission(self, mission, workspace):
                return self.start_mission(mission, workspace)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            worker_script = root / "delegate_worker.py"
            worker_script.write_text(
                textwrap.dedent(
                    """
                    import json
                    import os
                    import pathlib
                    import sys
                    import time

                    print("FLUXIO_EVENT:" + json.dumps({
                        "kind": "runtime.phase",
                        "message": "Lane booted",
                        "status": "running"
                    }), flush=True)
                    print("FLUXIO_EVENT:" + json.dumps({
                        "kind": "approval.request",
                        "message": "Approve delegated deploy step?",
                        "risk_level": "high",
                        "data": {"surface": "deploy"}
                    }), flush=True)
                    approval_path = pathlib.Path(os.environ["FLUXIO_APPROVAL_FILE"])
                    for _ in range(100):
                        if approval_path.exists():
                            payload = json.loads(approval_path.read_text(encoding="utf-8"))
                            if payload.get("status") == "approved":
                                print("FLUXIO_EVENT:" + json.dumps({
                                    "kind": "runtime.phase",
                                    "message": "Approval received",
                                    "status": "running"
                                }), flush=True)
                                sys.exit(0)
                            sys.exit(4)
                        time.sleep(0.05)
                    sys.exit(5)
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            runtime_map.return_value = {"hermes": _FakeAdapter()}
            supervisor = DelegatedRuntimeSupervisor(root)
            mission = Mission(
                mission_id="mission_delegate",
                workspace_id="workspace_primary",
                runtime_id="hermes",
                objective="Delegated runtime approval lifecycle",
                success_checks=[],
            )
            workspace = WorkspaceProfile(
                workspace_id="workspace_primary",
                name="Demo",
                root_path=str(root),
                default_runtime="hermes",
                workspace_type="python",
            )

            session = supervisor.start_session(
                runtime_id="hermes",
                mission=mission,
                workspace=workspace,
                source_step_id="step_delegate",
            )

            for _ in range(30):
                time.sleep(0.1)
                session = supervisor.refresh_session(session)
                if session.status == "waiting_for_approval":
                    break

            self.assertEqual(session.status, "waiting_for_approval")
            self.assertEqual(session.pending_approval.get("prompt"), "Approve delegated deploy step?")

            session = supervisor.resolve_approval(session, "approved")
            for _ in range(30):
                time.sleep(0.1)
                session = supervisor.refresh_session(session)
                if session.status == "completed":
                    break

            self.assertEqual(session.status, "completed")
            self.assertTrue(session.approval_history)
            kinds = [item["kind"] for item in session.latest_events]
            self.assertTrue(any(kind in {"approval.request", "approval.resolved"} for kind in kinds))
            # Explicit shutdown avoids transient file locks on Windows temp cleanup.
            supervisor.stop_session(session)
            time.sleep(0.2)

    def test_refresh_session_keeps_tail_for_large_event_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            supervisor = DelegatedRuntimeSupervisor(root)
            sessions_dir = root / ".agent_control" / "runtime_sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            session_path = sessions_dir / "delegate_perf.json"
            events_path = sessions_dir / "delegate_perf.events.jsonl"
            log_path = sessions_dir / "delegate_perf.log"
            decision_path = sessions_dir / "delegate_perf.approval.json"
            log_path.write_text("", encoding="utf-8")
            event_lines = []
            for index in range(120):
                event_lines.append(
                    json.dumps(
                        {
                            "event_id": f"evt_{index:03d}",
                            "delegated_id": "delegate_perf",
                            "runtime_id": "hermes",
                            "kind": "runtime.output",
                            "message": f"event {index}",
                            "status": "running",
                            "created_at": "2026-04-12T10:00:00+00:00",
                            "data": {},
                        }
                    )
                )
            events_path.write_text("\n".join(event_lines) + "\n", encoding="utf-8")
            session_path.write_text(
                json.dumps(
                    {
                        "delegated_id": "delegate_perf",
                        "runtime_id": "hermes",
                        "launch_command": "python -V",
                        "status": "completed",
                        "detail": "Completed",
                        "session_path": str(session_path),
                        "workspace_root": str(root),
                        "execution_root": str(root),
                        "log_path": str(log_path),
                        "events_path": str(events_path),
                        "decision_path": str(decision_path),
                        "source_step_id": "step_delegate",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            session = supervisor.refresh_session(str(session_path))

            self.assertEqual(session.event_cursor, 120)
            self.assertEqual(len(session.latest_events), 5)
            self.assertEqual(session.latest_events[0]["message"], "event 115")
            self.assertEqual(session.latest_events[-1]["message"], "event 119")


if __name__ == "__main__":
    unittest.main()
