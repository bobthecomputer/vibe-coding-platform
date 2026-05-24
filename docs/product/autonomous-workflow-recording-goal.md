# Autonomous Workflow Recording Goal

## Goal

Record autonomous mission work as durable, inspectable data without depending on the current UI layout.

## Scope

- Preserve the existing mission, delegated runtime, approval, and evidence architecture.
- Do not redesign screens or add decorative UI for this change.
- Maintain `.agent_control/autonomous_workflows.json` as a compact audit index for autonomous runs.
- Include enough data for resume, review, support, and proof workflows.

## Recorded Signals

- Mission identity, objective, workspace, runtime, mode, status, and current phase.
- Run budget, execution scope, execution policy, and route contract.
- Delegated runtime session counts, active/failed session counts, current lane, and latest runtime event.
- Pending approvals, approval history count, and latest approval decision.
- Verification commands, passed checks, failed checks, and last verification summary.
- Blockers, mutating action risk, stop reason, changed files, event count, and evidence file paths.

## Non-Goals

- No visual redesign.
- No fake workflow buttons or placeholder automation.
- No replacement of the existing mission store or delegated runtime session logs.

