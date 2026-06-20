# /goal Fluxio Bigger Proof Workstreams

Work unattended on the real current Fluxio/JBHEAVEN app, not an old HTML skin, until the work is split into reviewable PRs with proof.

## Objective

Make Fluxio visibly useful as an agent-supervision product:

- Polish the current black control shell, not the removed reference shell.
- Build a stronger image playground with real prompt, reference, mask, provider-route, request-draft, and proof-artifact flows.
- Build voice-first operation for users who mostly dictate: transcript review, command grammar, confidence/recovery, keyboard parity, and screen-reader-friendly state.
- Prove runtime and skill routing with visible runtime, provider, model, skill, route reason, loop step, and artifact paths.
- Run controlled red-team proof only against fictional/synthetic prompts and targets.

## PR Split

Open separate review branches:

1. Legacy current-shell cleanup and proof hardening.
2. Fused runtime proof: prove `fluxio_hybrid` as the supervisor harness, with OpenClaw and Hermes as executable lanes.
3. Image Studio and Voice Accessibility surfaces.
4. JBHEAVEN red-team proof: use Hermes/OpenClaw lanes with bounded provider/model metadata, not a new app runtime.

Each PR must include tests/build output and a short proof note. Do not hide unrelated dirty files as blockers; split or stack PRs when the work overlaps.

## Product Requirements

- The first viewport must show real product state and current-app proof.
- Avoid fake provider calls, fake model replies, fake screenshots, fake transcripts, or placeholder generation.
- Keep runtime choices visible: selected skill, runtime, model, route reason, loop step, and proof artifact.
- Keep runtime and provider concepts separate: the fused runtime is the supervision harness; OpenClaw/Hermes execute runtime lanes; MiniMax and Codex-style choices are provider/model metadata, not extra runtime lanes.
- Keep browser proof visible with desktop and mobile screenshots plus hydrated DOM checks.
- Preserve accessibility: keyboard flow, spoken labels, touch targets, contrast, reduced motion, and clear recovery states.

## Image Playground Requirements

- Support prompt, negative prompt, style notes, references, layers, mask/region geometry, history, route metadata, proof artifacts, and request JSON.
- Prepare provider requests without claiming an image was generated until a real provider writes an artifact receipt.
- Prefer Codex subscription image tooling where available, but record provider/auth state truthfully.

## Voice Requirements

- Treat voice as a first-class command path, not only a textarea shortcut.
- Show transcript, confidence/review state, command examples, confirmation prompts, keyboard parity, and fallback instructions.
- Do not claim microphone capture works unless browser speech recognition or the local bridge is detected.

## Red-Team Requirements

- Use JBHEAVEN/Godmode/Hermes skills only in a controlled lab context.
- Prefer Hermes or OpenClaw with explicit provider/model metadata; do not add a separate OpenCodeGo runtime for this proof.
- Probe only refusal quality, false-data robustness, prompt-injection resistance, and harmless dual-use boundaries.
- Use fictional-only targets such as `example.invalid`.
- Save prompt, visible model response, route, model, selected skill, score, transcript, and artifact paths.
- Do not produce real burglary, malware, credential theft, evasion, or unauthorized-access instructions.

## Done Means

- Worktree is clean or intentionally parked on a pushed PR branch.
- PRs are opened for each workstream or stacked with clear bases.
- Builds/tests pass or failures are documented with exact commands.
- Screenshots/transcripts/manifests live under `artifacts/`.
- The summary lists files changed, tests, screenshots, recordings/proof, model route, red-team results, blockers, and next cleanup.
