# UI Reference Board

Date: 2026-05-19
Screenshot folder: `docs/ui-research/screenshots/2026-05-19/`

## T3 Code

- Source URL: https://t3.codes/
- Screenshot: `t3-code-thread-list-dark.png`
- What works: Clear "control plane" positioning, bring-your-own-harness model, per-thread branch/diff/PR flow, concise proof of changed files.
- What does not work: Marketing page is louder than a workstation UI; screenshots are product-promo views rather than full failure/approval states.
- Principle to steal: Every agent thread should have visible branch, diff, changed files, and PR/commit path.
- Avoid copying: Branding, exact copy, screenshots, and social-proof treatment.
- Relevance: High. This is closest to the desired multi-agent control-plane direction.

## OpenAI Codex

- Source URL: https://openai.com/codex/
- Screenshot: `codex-app-diff-review.png`, `openai-codex-product.png`
- What works: Product model makes multi-agent workflows explicit: worktrees, cloud environments, skills, automations, commit/PR flow, reviewable diffs, and connected surfaces.
- What does not work: Public product page does not expose enough low-level UI detail for local shell state design.
- Principle to steal: Treat local, worktree, cloud, skills, automations, and PR review as first-class states, not settings footnotes.
- Avoid copying: OpenAI layout, visual assets, model labels, and brand language.
- Relevance: Very high. The app should surface the same categories of agent state and execution trust.

## Cursor

- Source URL: https://cursor.com/product and https://docs.cursor.com/en/background-agents
- Screenshot: `cursor-agent-dashboard.png`, `cursor-background-agents.png`
- What works: Strong IDE-adjacent mental model; background agents are discoverable as a sidebar/workflow concept; rules and permissions exist as project/global concepts.
- What does not work: User feedback shows trust breaks when diffs auto-apply or terminal output is not visible to the agent.
- Principle to steal: Rules, background work, and review affordances must be visible next to the agent, not hidden after the fact.
- Avoid copying: Cursor visual identity, IDE chrome, and exact command/UI names.
- Relevance: High for rules, background agent supervision, and failure modes.

## Claude Code Desktop

- Source URL: https://code.claude.com/docs/en/desktop
- Screenshot: `claude-code-desktop-parallel-tasks.png`
- What works: Pane model is explicit: chat, diff, preview, terminal, file, plan, tasks, subagent. It also has view modes, terminal, file editing, preview, permissions, model, and effort shortcuts.
- What does not work: Parallel sessions raise conflict, cost, and memory questions in user feedback.
- Principle to steal: Workstation panes should be rearrangeable/resizable and stateful; transcript verbosity should be a user-controlled mode.
- Avoid copying: Anthropic pane styling, copy, shortcuts, and naming.
- Relevance: Very high for the target desktop/workstation feel.

## VS Code Copilot Agents Window

- Source URL: https://code.visualstudio.com/docs/copilot/agents/agents-window
- Screenshot: `vscode-copilot-agent-sidebar.png`
- What works: Dedicated Changes panel separates files changed from chat; diff view supports feedback directly inside edits.
- What does not work: Long-session feedback shows chat/tool-call clutter can degrade performance and require reloads.
- Principle to steal: Diff review needs its own durable surface with feedback anchored to edits.
- Avoid copying: VS Code layout and iconography.
- Relevance: High for diff/review and long-session performance.

## Replit Agent

- Source URL: https://docs.replit.com/core-concepts/agent/
- Screenshot: `replit-agent-workspace.png`
- What works: Clear build/test/deploy lifecycle and approachable agent mode selection.
- What does not work: User feedback flags irrelevant screenshots, excessive checkpoints, unclear cost/credit burn, and weak control over destructive behavior.
- Principle to steal: Checkpoints and preview evidence must be relevant to the changed surface and cost should be legible.
- Avoid copying: Consumer app-builder tone and "no constraints" framing.
- Relevance: Medium-high for preview/artifact and checkpoint design.

## Windsurf Cascade

- Source URL: https://docs.windsurf.com/windsurf/cascade
- Screenshot: `windsurf-cascade-agent.png`
- What works: Modes, tool calls, plans/todos, checkpoints/reverts, voice input, linter integration, ignore rules, and simultaneous Cascade sessions are documented as part of one assistant model.
- What does not work: Tool-call limits and continue behavior create credit/cost concerns.
- Principle to steal: A long-running agent should expose a plan/todo model, checkpoint model, and continuation/cost boundaries.
- Avoid copying: Cascade naming and IDE treatment.
- Relevance: High for plans, checkpoints, and rule/ignore boundaries.

## Bolt

- Source URL: https://support.bolt.new/building/using-bolt/interacting-ai
- Screenshot: `bolt-chat-preview.png`
- What works: Preview selection lets users target a UI element/layer and attach that target to a prompt.
- What does not work: Browser app-builder context is less relevant to local code agents and can hide real code ownership.
- Principle to steal: Preview/artifact panels should allow direct selection and feedback against UI regions.
- Avoid copying: Bolt's chatbox flow and app-builder framing.
- Relevance: Medium-high for image/preview/workbench.

## Zed

- Source URL: https://zed.dev/docs/ai/agent-panel
- Screenshot: `zed-agent-panel.png`
- What works: Edited-file accordion, review changes button, multi-buffer diff, hunk-level accept/reject, and explicit context mentions.
- What does not work: Recent feedback points to full-file rewrites and missing terminal command edit affordances.
- Principle to steal: Changed files must be visible above the composer, and review must support hunk-level decisions.
- Avoid copying: Zed visual chrome.
- Relevance: High for diff and file-change ergonomics.

## Blackcrab

- Source URL: https://www.blackcrab.app/
- Screenshot: `blackcrab-parallel-agent-workspace.png`
- What works: Session history, grid, terminal, preview, usage dashboard, verification tools, local transcript history, and multi-session density.
- What does not work: It is tightly tied to Claude Code history and may over-index on session management.
- Principle to steal: Usage/cost/context should be visible before it surprises the operator.
- Avoid copying: Product name, exact grid, and copy.
- Relevance: High for local desktop supervision.

## Raycast

- Source URL: https://www.raycast.com/
- Screenshot: `raycast-command-density.png`
- What works: Dense command palette, fast keyboard-first command hierarchy, restrained surfaces.
- What does not work: Not an agent workspace; too command-centric for rich diff/preview flows.
- Principle to steal: Commands should be quick, searchable, and keyboard-first.
- Avoid copying: Brand, launcher UI, and extension store structure.
- Relevance: Medium for command palette and action menus.

## Linear

- Source URL: https://linear.app/
- Screenshot: `linear-issue-density.png`
- What works: Calm hierarchy, status taxonomy, issue/project density, keyboard-friendly product feel.
- What does not work: Issue tracker patterns do not solve agent execution trace complexity by themselves.
- Principle to steal: Status labels and work queues should be compact, consistent, and scannable.
- Avoid copying: Linear's visual system and issue layout.
- Relevance: Medium for Builder/project overview.

## Superhuman

- Source URL: https://superhuman.com/
- Screenshot: `superhuman-command-flow.png`
- What works: Speed, command flow, keyboard-first posture, minimal surface switching.
- What does not work: Mail workflow is too linear for multi-pane agent work.
- Principle to steal: Keep primary actions fast and explicit; avoid burying workflows in secondary UI.
- Avoid copying: Brand and messaging.
- Relevance: Low-medium for command ergonomics.

## Arc

- Source URL: https://arc.net/
- Screenshot: `arc-browser-workspace.png`
- What works: Workspace/sidebar mental model and browser-as-workbench framing.
- What does not work: Not enough execution state or trust controls for agentic coding.
- Principle to steal: Persistent project spaces can reduce context loss.
- Avoid copying: Sidebar styling and brand.
- Relevance: Low-medium for workspace switching.

