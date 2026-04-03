# Fluxio 1.0 Release Definition

This document defines the stop point for `Fluxio 1.0`.

The purpose of 1.0 is not "every future feature shipped". The purpose is:

- the app is good enough to use as the environment for building future versions of itself
- the desktop experience is strong enough that you can genuinely test and operate it
- the autonomy model is useful, inspectable, and safe enough for real multi-hour runs

## 1.0 Product Promise

Fluxio 1.0 is a desktop-first autonomous coding control room that lets a user:

- manage multiple projects in one app
- run long missions on OpenClaw or Hermes behind one shared Fluxio harness
- separate planning, execution, verification, summarization, and guidance model roles
- review real action history, delegated runtime state, approvals, and proof
- configure safer defaults for non-technical users
- iterate on the UI live with real HMR and fixture-backed preview states

If those things are not true, it is not 1.0 yet.

## 1.0 Must-Haves

### Core mission loop

- Mission creation from the desktop UI works end to end.
- Fluxio planner loop supports plan, execute, verify, and replan instead of one-shot planning.
- One mission can continue across restarts with state, plan revisions, derived tasks, and proof intact.
- Multi-project support exists in one app.
- One active mission per workspace by default, with clear queueing and collision avoidance.

### Runtime integration

- OpenClaw and Hermes are both selectable runtimes.
- Delegated runtime lanes have authoritative lifecycle states:
  - `queued`
  - `launching`
  - `running`
  - `waiting_for_approval`
  - `completed`
  - `failed`
  - `stopped`
- Stop, resume, and restart recovery work without orphaned delegated sessions.
- Runtime activity is surfaced truthfully in the control room.

### Action and proof quality

- Real file, patch, shell, git, test, and delegated actions are persisted in action history.
- Approval-gated actions are reviewable and resumable.
- Mission proof clearly shows:
  - what changed
  - what passed
  - what failed
  - what still needs approval
  - what blocked progress
- Local and delegated actions are visually distinguishable.

### Model routing

- Role-based model routing exists for:
  - `planner`
  - `executor`
  - `verifier`
  - `summarizer`
  - `skill_curator`
  - `guide_author`
- Planner-premium and executor-efficient is available as a recommended default.
- Users can override routing by role.

### Safety and accessibility

- Guided profiles exist and work:
  - `Beginner`
  - `Builder`
  - `Advanced`
  - `Experimental`
- Safe-by-default execution scope exists.
- Approval strictness changes meaningfully by profile.
- Onboarding is persistent across restarts.
- Phone escalation works through Telegram for blocked approvals and completion summaries.
- Reduced-motion support works.
- The UI remains usable on narrower desktop widths and smaller laptop screens.

### Skills and setup

- Skill library is visible and understandable for non-technical users.
- Recommended skill packs and integrations are surfaced from workspace context.
- Learned skills remain reviewable and disable-able.
- Windows-first setup guidance covers WSL2, Node, Python, uv, OpenClaw, and Hermes.

### UI and live iteration

- The desktop frontend has real live edit support through HMR in development.
- The app includes fixture-backed preview states for UI review.
- The control room is no longer just a long dashboard; it behaves like an operator workbench.
- The UI quality is strong enough that a user can supervise missions, approvals, proof, skills, setup, and bridge-lab surfaces without confusion.

### App capability standard

- Fluxio 1.0 ships the design-grade standard artifacts:
  - manifest schema draft
  - local bridge handshake shape
  - capability grants model
  - bridge-lab registry view
- 1.0 does not require a full public ecosystem rollout.
- 1.0 should include at least one real reference integration target planned and scaffolded, but not necessarily fully productized.

## 1.0 Explicit Non-Goals

These are allowed to remain incomplete in 1.0:

- public marketplace for third-party connected apps
- full mobile app
- unrestricted arbitrary app orchestration
- perfect native event parity with every external runtime
- complete plugin ecosystem
- large-scale cloud sync or multi-user team features

## Release Blockers

Any of these block 1.0:

- no real HMR/live frontend editing loop
- delegated approvals still unreliable across restart
- mission proof still vague or misleading
- the desktop UI still feels like a stitched admin panel instead of one coherent workbench
- non-technical onboarding still leaves users stuck on setup
- OpenClaw or Hermes path is clearly broken in ordinary use

## Remaining Workstreams To Reach 1.0

### Workstream A: Control room refactor

- Split the current desktop UI into stronger workbench surfaces.
- Tighten hierarchy, density, operator actions, and empty/error states.
- Make mission supervision, approvals, proof, and runtime lanes the center of the app.

### Workstream B: Fixture and review tooling

- Expand fixture preview states beyond the current seeded examples.
- Add screenshot and replay scenarios for visual review.
- Make UI iteration fast enough that product review can happen while coding.

### Workstream C: Delegated runtime quality

- Improve adapter-specific structured event mapping for OpenClaw and Hermes.
- Normalize approval callbacks and richer runtime-native events.
- Ensure proof and mission timeline stay consistent when work is delegated.

### Workstream D: Setup and accessibility hardening

- Tighten onboarding recovery paths.
- Improve setup repair actions and plain-language explanations.
- Close the remaining accessibility and motion gaps.

### Workstream E: Reference connected-app path

- Keep Bridge Lab mock support.
- Define the first real reference integration target.
- Implement only enough to validate the standard inside Fluxio, not a full ecosystem.

## 1.0 Acceptance Checks

Fluxio is ready for a 1.0 test cycle when all of these are true:

- `python -m pytest tests -q` passes
- `npm run tauri build -- --debug` passes
- the desktop app can launch and supervise at least one mission on OpenClaw and one on Hermes
- delegated approval waiting can be triggered, approved, resumed, and completed
- a fixture-backed preview mode can be used during live UI editing
- the UI can be reviewed in three meaningful states:
  - first run
  - delegated approval waiting
  - verification failure
- a non-technical user can understand how to:
  - add a workspace
  - start a mission
  - approve or reject work
  - understand what happened

## Definition Of Done

We call it `Fluxio 1.0` when:

- the app is coherent enough to use as the development environment for future Fluxio versions
- the product feels trustworthy during real autonomous runs
- the operator UI is strong, legible, and fast to iterate
- the remaining gaps are future-version improvements, not foundations that are still missing
