# Inspiration Sources

This file records the public sources that appear to inform Fluxio's direction as of 2026-04-04.

The current repo already references `OpenClaw` and `Hermes` in product docs and runtime code, but it did not have one clean source catalog with upstream links and status notes.

## Verified Upstream Sources

### T3 basis

- T3 Stack / create-t3-app
  - Link: <https://github.com/t3-oss/create-t3-app>
  - Verified status: public and active
  - Why it matters to Fluxio:
    - opinionated but modular defaults
    - strong full-stack ergonomics
    - emphasis on speed, safety, and composable setup

- T3 Chat product
  - Link: <https://t3.chat/>
  - Verified status: public product site
  - Why it matters to Fluxio:
    - prompt-first operator flow
    - fast model selection and thread ergonomics
    - strong consumer-facing UX expectations
  - Note:
    - no official public source repo was verified during this pass
    - treat this as a product reference, not a code dependency

### OpenCode and continuation

- OpenCode
  - Link: <https://github.com/opencode-ai/opencode>
  - Verified status: archived on 2025-09-18
  - Why it matters to Fluxio:
    - terminal-native agent workflow
    - coding-focused session loop
    - practical tool usage patterns

- Crush
  - Link: <https://github.com/charmbracelet/crush>
  - Verified status: public and active
  - Why it matters to Fluxio:
    - current continuation of the OpenCode line
    - session-based agent workflow
    - multi-model routing
    - MCP and LSP integration
    - strong configuration and workflow surface

### Runtime inspirations

- OpenClaw
  - Link: <https://github.com/openclaw/openclaw>
  - Verified status: public and active
  - Why it matters to Fluxio:
    - delegated runtime model
    - cross-platform assistant/runtime shape
    - skills, extensions, and UI-adjacent runtime surfaces

- Hermes Agent
  - Link: <https://github.com/NousResearch/hermes-agent>
  - Verified status: public and active
  - Why it matters to Fluxio:
    - alternate runtime lane
    - skills and agent workflow basis
    - install/runtime expectations already encoded in Fluxio's runtime adapter

## What The Repo Already Had

- `docs/FLUXIO_1_0_RELEASE.md` already names `OpenClaw` and `Hermes` as core runtimes.
- `docs/LIVE_UI_DEVELOPMENT.md` already confirms a live-edit desktop UI loop with Vite HMR and fixture-backed review.
- `src/grant_agent/runtimes/hermes.py` already embeds the Hermes install path pointing at `NousResearch/hermes-agent`.

What was missing was the upstream catalog itself:

- no clean doc listing the GitHub links for the main inspirations
- no distinction between active upstreams and historical references
- no note that `OpenCode` has moved forward as `Crush`
- no clarification that `T3 Chat` is a product reference while `create-t3-app` is the clean open-source T3 basis

## Recommended Basis For Fluxio

Use the sources for ideas, not for product cloning.

- For application structure and opinionated developer ergonomics:
  - lean on the `T3 Stack` mindset

- For coding-agent workflow, session behavior, and configurable tool use:
  - study `OpenCode` historically, but prefer `Crush` as the live reference

- For delegated runtime behavior and agent-lane integration:
  - study `OpenClaw` and `Hermes`

- For Fluxio-specific product work:
  - keep building the parts that those sources do not solve together:
    - one control room across runtimes
    - mission proof and approval truthfulness
    - non-technical guided setup
    - skill creation and workflow creation inside the app
    - Git-aware workspace surfaces
    - live UI review with fixtures and HMR

## Product Implications For The Next UI Pass

If Fluxio is meant to be usable for building future Fluxio versions inside itself, the next design passes should center on these surfaces:

- workspace panel with folder, branch, dirty state, remotes, ahead/behind, and deploy tasks
- mission workbench with plan, runtime lane, approvals, proof, and verification
- skill studio for creating, reviewing, enabling, and disabling skills
- workflow studio for repeatable domain workflows, especially in weaker content-heavy domains
- clearer non-technical and semi-technical modes without hiding expert controls
