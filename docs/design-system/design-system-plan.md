# Design System Plan

Date: 2026-05-19

## Direction

Syntelos should feel like a calm local workstation: dark, technical, dense enough for repeated use, and explicit about trust boundaries. The UI should use off-black surfaces, subtle borders, restrained accent color, compact typography, and clear status semantics.

## Token Groups

- Background: app, shell, panel, panel-raised, inset.
- Text: primary, secondary, muted, inverse.
- Borders: default, strong, focus, selection.
- Status: success, warning, danger, info, neutral.
- Diff: addition, deletion, modification.
- Execution: local, worktree, cloud, remote.
- Radius: 4, 6, 8, 10, 12, full.
- Spacing: 2, 4, 6, 8, 10, 12, 16, 20, 24, 32.
- Shadows: none by default, panel elevation only when functional.
- Typography: UI sans for most text, mono for paths, command output, counters, hashes, and model IDs.

## Component Inventory

Foundation:

- Button/icon button
- Field/select/textarea
- Segmented control
- Toggle/checkbox
- Tooltip
- Status chip
- Empty state
- Error callout
- Skeleton row

Workspace:

- App shell
- Global rail
- Sidebar nav item
- Context topbar
- Pane header
- Resizable split/pane shell
- Timeline/event feed
- Thread card
- Task card

Agent:

- Composer
- Model selector
- Effort selector
- Provider auth indicator
- Rule set selector
- Execution target selector
- Approval prompt
- Tool call row
- Changed file strip
- Verification summary

Builder:

- Project/flow card
- Artifact preview shell
- Proof timeline
- Review queue row

Review:

- Diff viewer wrapper
- File change row
- Hunk action bar
- Terminal/log viewer
- Preview shell with selection metadata

Governance:

- Skill card
- Skill detail header
- Rule set card
- Permission matrix
- Scope editor

## Implementation Plan

1. Add a small workspace model module for nav items, agent statuses, execution targets, and permission modes.
2. Add semantic CSS tokens in `:root` while preserving existing class names.
3. Gradually replace hard-coded color/spacing in active surfaces with tokens.
4. Extract low-level UI primitives only when they are used by at least two surfaces.
5. Move feature-specific render code out of `FluxioShell.jsx` in small chunks: navigation model, agent header/composer, rule-set list, diff/log panels.
6. Add focused tests for the workspace model and dangerous permission defaults.

## Visual Rules

- No pure black backgrounds.
- No purple-dominant accent system.
- Cards max 8px radius unless they are modal/shell containers.
- Dense UI uses borders and dividers before heavy cards.
- Buttons use icons where function is recognizable.
- Disabled controls must include a reason in tooltip, helper text, or adjacent copy.
- Text must not overlap fixed-format controls on small screens.
- Route, branch, model, provider, effort, rule set, execution target, and approval mode must stay visible during active runs.

## First Implementation Slice

The first slice is intentionally conservative:

- Introduce typed-ish JavaScript constants for core workspace entities.
- Reuse those constants in the shell instead of local magic arrays.
- Add CSS token aliases that current and future components can share.
- Avoid moving large files until the behavior map and tests are in place.

## Runtime Visualization Slice

The second slice promotes runtime operations into the Workbench:

- Show managed service count, health count, update candidates, automatic verification count, and update action count.
- Show OpenClaw, Hermes, WSL/uv/image tooling status as runtime-adjacent operational services.
- Show current and latest versions when available.
- Preserve `autoRunVerify` on service actions so the UI can make post-update verification visible.
- Route runtime service actions through the same safe `settings:run-action` execution path.
