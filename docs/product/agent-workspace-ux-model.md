# Agent Workspace UX Model

Date: 2026-05-19

## Product Model

Syntelos is a local-first agent workstation. The primary object is a project workspace. Inside each workspace, the user supervises agent threads/runs, reviews changed files, watches terminal and preview evidence, configures skills, and applies rule sets that govern autonomy.

## Navigation Model

- Home: workspace picker and mode entry.
- Agent: active conversation/run workspace.
- Builder: project and thread overview, artifacts, proof, and run history.
- Skills: reusable procedures, trigger conditions, model behaviors, and tool capabilities.
- Rule Sets: permissions, execution scopes, approvals, tool access, and command/file boundaries.
- Images/Workbench: visual artifact generation and preview work if enabled.
- Settings: global app preferences, accounts, providers, theme, local paths, and default models.

Rule Sets should not live only in Settings. Settings may contain defaults, but active rule sets belong in core navigation because they affect every agent action.

## Project, Folder, and Thread Model

- Project: registered root folder or remote/cloud target.
- Workspace: project plus runtime metadata, provider auth, rule set, branch/worktree, and session history.
- Thread: user-agent conversation bound to a workspace and execution target.
- Run: a bounded execution attempt inside a thread.
- Artifact: generated or captured output such as screenshot, image, preview URL, diff, log, test report, or document.

## Agent Run Lifecycle

1. Idle: project selected, model/provider/effort visible, rule set selected, execution mode selected, prompt ready.
2. Planning: objective parsed, risks and assumptions surfaced.
3. Running: current action, commands, files read/changed, tool calls, and timeline visible.
4. Needs approval: run pauses at a permission boundary.
5. Blocked: missing auth, unavailable path/runtime, failed command, or ambiguous input.
6. Verifying: tests/builds/smoke checks running with logs attached.
7. Completed: changes, evidence, tests, and next action summarized.
8. Failed: error cause, attempted recovery, logs, and retry options visible.

## Approval Lifecycle

- Requested: show command/action, scope, affected files, reason, rule set, and risk.
- Editable: safe command approvals should allow editing before running.
- Approved: record operator, timestamp, exact payload.
- Rejected: record reason and suggest safer alternatives.
- Expired/stale: mark disabled and require refresh.
- Audited: approval history stays attached to the run and Builder timeline.

## Permission and Rule Set Model

Rule sets define:

- File read scope.
- File write scope.
- Shell command allow/deny lists.
- Network access.
- Tool access.
- Destructive action policy.
- Git operation policy.
- Runtime target policy: local, managed worktree, existing worktree, cloud, remote/NAS.
- Approval mode: always ask, ask risky actions, autonomous inside folder, review-only, or blocked.

## Provider, Model, and Effort Selection

Selection belongs in Agent idle and compact run header:

- Provider: OpenAI, Anthropic, MiniMax, OpenRouter, or local runtime if configured.
- Model: selected model with availability/auth state.
- Effort: default, low, medium, high, xhigh where supported.
- Route role: planner, executor, verifier.
- Presets: named route combinations are useful, but final selected values must stay visible.

## Execution Model

Execution target states:

- Local folder: operates in current working directory.
- Managed worktree: app creates/owns worktree.
- Existing worktree: user-selected folder already attached to Git.
- Cloud sandbox: remote isolated environment.
- Remote/NAS: bridge target with sync/permission state.

The run header should always show target, branch, worktree/folder, and approval mode.

## Preview and Artifact Model

Artifacts must include:

- Type: screenshot, preview, image, diff, log, test report, document.
- Source: command/tool/panel that generated it.
- Target: route, file, selector, viewport, or surface.
- Status: pending, current, stale, failed.
- Reason: why it was captured.

## Diff and Review Model

- Changed files list must stay visible above or beside the composer.
- Diff review supports file-level and hunk-level accept/reject where implementation allows.
- Large rewrite warnings appear when a small request changes a large file or many lines.
- Feedback can be attached to a file/hunk and sent back into the agent thread.
- Commit/PR actions are disabled until review state is known.

## Error and Recovery Model

Errors should answer:

- What failed?
- Which action caused it?
- What was the exact command/API/tool result?
- Is work safe?
- What can the user do next?

Recovery actions: retry, edit command, change rule set, switch runtime, open logs, discard changes, continue manually, or create issue.

## Empty and First-Run States

First run should ask for the minimum real setup:

- Select project/folder.
- Confirm provider/model auth.
- Choose rule set.
- Choose local/worktree/cloud mode.
- Start from a concrete task.

Avoid marketing examples. Example tasks are acceptable only when backed by real workspace actions.

## Route and Screen Matrix

| Screen | Primary user job | Required controls | State indicators | Dangerous actions | Empty/loading/error |
| --- | --- | --- | --- | --- | --- |
| Login/local account | Unlock local control room | account selector, password, backend status | auth state, backend availability | create/reset admin | backend offline, invalid login |
| Home/mode picker | Pick workspace/mode | workspace cards, recent threads | project health, runtime auth | remove workspace | no projects, backend unavailable |
| Agent idle | Start a run | composer, model, effort, rule set, execution target | folder, branch, provider, approval mode | broad autonomy | no project, no auth |
| Agent running | Supervise work | stop, pause, approve, open diff/log/preview | current task, run status, changed files | stop/approve shell | stream stalled, command failed |
| Agent completed | Review outcome | open diff, commit, PR, continue | tests, verification, artifacts | commit/push | missing verification |
| Agent failed/blocked | Recover | retry, edit command, switch rule set/runtime | failure cause, last command | retry destructive action | logs unavailable |
| Diff review | Inspect changes | file list, hunk actions, feedback | reviewed/unreviewed, rewrite size | accept all, discard | no changes, diff load failed |
| Terminal/log | Diagnose execution | copy, rerun, edit command, filter | exit code, duration, capture status | rerun command | output unavailable |
| Preview/artifact | Verify UI/output | refresh, select region, attach feedback | route, selector, stale/current | publish artifact | screenshot failed |
| Builder overview | Track project work | filters, open thread, review queue | statuses, artifacts, timeline | archive/delete run | no runs |
| Builder detail | Inspect a flow | timeline, files, tests, artifacts | progress, proof, branch | merge/discard | flow missing |
| Skills library | Manage skills | search, enable, open detail | trigger, scope, version | enable powerful skill | no skills |
| Skill detail/editor | Edit procedure | draft/save/publish, version | active/draft, warnings | publish broad skill | invalid definition |
| Rule Sets overview | Choose policy | rule cards, scope filters | active/default, danger level | set broad autonomy | no rule sets |
| Rule Set editor | Edit permissions | file scope, commands, tools, approvals | validation, affected projects | allow destructive commands | invalid scope |
| Settings | Global preferences | provider auth, paths, theme, defaults | auth, storage, backend | clear data, reset auth | provider unavailable |

