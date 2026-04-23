# Fluxio Operator Tutorial

Fluxio `1.0` is not a generic agent playground. The supported path is a Windows desktop app with WSL2-backed runtimes, installer-grade setup, and one reliable workbench for long-running missions.

## Before You Trust A Long Run

Use this order every time on a fresh machine:

1. Open Fluxio and stay in `Agent View`.
2. In `Setup`, verify `WSL2`, `Node`, `Python`, `uv`, `OpenClaw`, `Hermes`, and Tauri prerequisites.
3. Treat `uv` and `Hermes` as hard blockers.
4. If `Hermes` is missing, repair it from Fluxio setup first, then run `Verify setup health`.
5. Add a workspace and choose the profile that matches your comfort level.
6. Launch one small proving mission before attempting an unattended long run.

If `Hermes` is not installed and usable, do not treat the machine as `1.0` ready.

## First Mission Flow

Use this exact first mission loop:

1. Add a workspace that points at the real repo root.
2. Start with the `Builder` profile unless you have a reason to prefer `Beginner` or `Advanced`.
3. Set a bounded objective:
   Example: `Tighten the desktop launch path and capture proof for the changes.`
4. Add success checks:
   `python -m pytest tests -q`
   `npm run frontend:build`
   `npm run tauri build -- --debug`
   or run the canonical desktop verification command:
   `npm run verify:desktop`
5. If Hermes setup is still being repaired, use `OpenClaw` only for a bounded proving run; that does not make the machine `1.0` ready.
6. Move to `Hermes` only after setup health is green, repair verification has passed, and you want the delegated long-run path.

The first mission should prove four things:

- Fluxio can plan and execute without losing the thread.
- Proof is visible in the workbench.
- Approvals are understandable.
- Restart and resume do not destroy continuity.

## Recommended Workflows

These are the reviewed workflows to use first:

- `Installer-Grade Setup Repair`
  Use when `uv`, `Hermes`, or another required dependency is missing or needs repair.
- `Long-Run Agent Session`
  Use once setup is green and you want Fluxio to work through an objective over many hours.
- `Live UI Review Loop`
  Use when refining the desktop workbench with fixtures, HMR, and proof capture.
- `Skill And Workflow Authoring`
  Use when turning something learned during a mission into a reusable reviewed skill or recipe.
- `Safe Push Or Deploy`
  Use only after repo truth, verification, and approvals are already clear.

## Hermes Readiness

For Fluxio `1.0`, Hermes is not “nice to have.” It is part of the supported runtime contract.

Hermes should read as healthy only when:

- the CLI is detected
- setup health shows it as installed
- verification has been run after install or repair
- the service shows as healthy in setup and builder surfaces
- a Hermes-backed mission can enter delegated approval flow and resume correctly

If any of those conditions fail, treat Hermes as not ready.

## Product Review Loop

Fluxio still needs to feel competitive with modern coding-agent apps during day-to-day building. Use this review loop when working on the product itself:

1. Run `npm run tauri:dev`.
2. Keep `Preview` on `Live Backend` when validating real mission truth.
3. Switch to fixtures when reviewing blocked, resumed, failed, and long-run states.
4. After each meaningful UI pass, run:
   `python -m pytest tests -q`
   `npm run frontend:build`
   `npm run tauri build -- --debug`
   or use:
   `npm run verify:desktop`
5. If the pass changes setup, workflows, or mission truth, check the tutorial and workflow surfaces in the desktop app before considering it done.

## Release Safety Bar

Do not call the machine ready for unattended Fluxio use unless all of these are true:

- setup health is green
- Hermes is healthy
- one real proving mission has been launched
- proof is visible and coherent
- restart continuity has been exercised
- the release verification commands pass

The default release command for that bar is:
`npm run verify:desktop`

That is the minimum bar for “launch the project without an unexpected error.”
