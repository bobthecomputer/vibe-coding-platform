# /goal - Make vibe-coding-platform a real usable coding platform

Use this as the goal text for a fresh Codex session working in `C:\Users\paul\Projects\vibe-coding-platform`.

```text
/goal
Objective: make vibe-coding-platform / Fluxio feel like a real web coding platform that a human can use every day: easy mission launch, easy modification, easy continuation, easy verification, clear summaries, and direct access to the agent conversation/thread from inside the app.

Repo and deployment context:
- Local repo: C:\Users\paul\Projects\vibe-coding-platform
- Recent working/deployed versions also exist on the Synology NAS. Treat the NAS copy as important live-state/deployment evidence, not an afterthought.
- Use the local Synology/NAS runbook and credential files when authenticated live checks or deploy verification are needed.
- Current worktree may be dirty. Read user changes carefully and do not revert unrelated edits.
- The T3 Code / OpenCode / OpenClaw / Hermes baseline matters: the app must make those workflows easier to launch, supervise, inspect, continue, and verify from one UI.

Credential and NAS handling:
- Credentials and NAS runbooks are local-only under C:\Users\paul\Projects\vibe-coding-platform\.agent_control.
- Relevant paths include .agent_control\NAS_ACCESS_RUNBOOK.md, .agent_control\nas_codex2_100_125_54_118.dpapi, .agent_control\nas_codex2_100_125_54_118.json, .agent_control\grand_agent_admin_password.txt, .agent_control\grand_agent_web_admin.json, and .agent_control\workspaces.json.
- Read these only when needed for authenticated checks or Synology deployment/state verification.
- Never print, paste, commit, or summarize secret values. Refer to file paths only.
- All normal repo commands, verifiers, local scripts, and NAS checks are authorized; do not pause for permission unless the operation is destructive or would expose secrets.

Human product standard:
- Think like a human operator, not just a test runner.
- The core app should answer: What is running? What happened? What should I do next? Where is the proof? How do I continue or modify this mission?
- Reduce clutter. Remove or demote panels/buttons that do not help the active workflow.
- Put buttons where a user expects them: launch near mission creation, continue/modify near mission state, verify near artifacts/proof, summarize near thread/output, provider setup near route readiness.
- Do not hide essential status behind diagnostic sections.
- No functional bugs should remain in mission launch, modify, continue, verify, summarize, provider connection, or thread inspection flows.

Primary work:
1. Inspect current truth:
   - git status --short
   - docs/SYSTEM_GAP_ANALYSIS.current.md
   - docs/OPENCODEGO_PROVIDER_SETUP.md
   - docs/FLUXIO_OPERATOR_TUTORIAL.md
   - README.md
   - package.json
   - src/grant_agent/web_backend.py
   - src/grant_agent/mission_control.py
   - src/grant_agent/runtime_supervisor.py
   - src/grant_agent/runtimes/hermes.py
   - src/grant_agent/runtimes/openclaw.py
   - web/src/fluxio/FluxioShell.jsx
   - web/src/fluxio/FluxioReferenceShell.jsx
   - web/src/fluxio/workspaceModel.js
   - web/src/fluxio/styles.css
2. Build the app around the essential workflows:
   - Launch a mission from a clear goal field with route/model/provider readiness visible.
   - Modify a mission before or during execution without losing context.
   - Continue/resume a paused, blocked, or stale mission from the mission detail view.
   - Verify a mission with visible proof, artifacts, checks, and failure reasons.
   - Summarize a mission/thread into a useful handoff.
   - Inspect the actual agent conversation/thread inside the app, like one can do in OpenClaw or Hermes separately.
3. Make Agent useful first:
   - First view must show live thread/conversation, latest runtime messages, transcript status, artifacts, verifier state, next repair step, and continue/modify/verify/summarize controls.
   - Do not show stale demo or fixture state as if it is live.
   - Cross-mission switching must update the actual thread and not keep old frames/messages.
4. Make Builder useful first:
   - Show current missions, queue, blocked/running/completed state, project context, and next action.
   - Give one-click drilldown to the right Agent thread.
   - Batch/project features are quality-of-life only after the single-mission path is solid.
5. Fix provider/setup friction:
   - Make OpenCode/OpenClaw/Hermes/provider connection status explicit.
   - Show missing setup, next command/action, and verification receipt.
   - Prefer a simple in-app setup path over scattered docs.
6. Improve design and information architecture:
   - Audit every visible button and panel for purpose.
   - Move secondary diagnostics behind expandable areas.
   - Keep dense operator UI, but remove duplicated or low-value visual noise.
   - Check desktop and phone/tablet layouts for overlapping text, misplaced buttons, and blocked workflows.
7. Synology/NAS reality:
   - Verify against the NAS version when the local runbook allows it.
   - Keep live NAS evidence stronger than stale local snapshots.
   - If local and NAS states differ, document the difference and fix the source of truth.

Useful verification commands:
- python -m pytest tests/test_web_backend.py tests/test_desktop_ui_contract.py tests/test_runtime_supervisor.py tests/test_mission_control.py tests/test_sync_nas_system_audit.py -q
- npm run frontend:build
- npm run verify:fluxio-actions
- npm run verify:live-data
- npm run verify:authenticated-live
- npm run verify:authenticated-live-agent
- npm run verify:authenticated-phone
- npm run verify:live-detail-performance
- npm run sync:nas-audit

Completion criteria:
- A human can launch, modify, continue, verify, summarize, and inspect a mission thread in the app without needing separate OpenClaw/Hermes UI.
- The primary UI is less cluttered and the important actions are in the right places.
- No known functional bugs remain in the essential mission workflows.
- Local and Synology/NAS state are checked or the blocker is documented.
- Tests/verifiers pass, or exact failures and next fixes are documented.
- No secrets are printed, committed, or included in the final response.
```
