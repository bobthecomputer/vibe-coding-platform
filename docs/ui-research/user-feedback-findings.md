# User Feedback Findings

Date: 2026-05-19

## Findings

1. Diff trust is fragile.
   - Cursor users reported agent changes applying without the expected review/accept flow, with the workaround being the Review panel or manual `git diff`.
   - Source: https://forum.cursor.com/t/agent-mode-no-longer-shows-review-accept-interface-and-applies-file-changes-automatically-after-recent-update/152581/3
   - Design implication: The app must never make "reviewed" implicit. Changed files, review status, and acceptance state need a persistent surface.

2. Repeated context and invisible token/cost behavior damages long-session trust.
   - Cursor forum feedback described repeated branch diff context adding large token overhead across turns.
   - Source: https://forum.cursor.com/t/critical-bug-git-diff-context-is-sent-repeatedly-with-every-message-wasting-10-15k-tokens-per-interaction/150387
   - Design implication: Show context sources, what is being resent, and when context is compressed, cached, or omitted.

3. Terminal output needs to be visible to both user and agent.
   - Cursor users reported agent terminal output not being accessible, with workarounds involving new chats or legacy terminal settings.
   - Source: https://forum.cursor.com/t/terminal-output-not-accessible/149481
   - Design implication: Terminal/log panel must have command, output, exit code, timeout, and capture status. Failed output capture is itself an error state.

4. Long transcripts can make the UI unusable.
   - Copilot users described long agent sessions causing severe UI lag, delayed approval clicks, forced reloads, and session termination.
   - Source: https://www.reddit.com/r/GithubCopilot/comments/1pg71di/long_copilot_agent_sessions_cause_severe_ui_lag/
   - Design implication: Timeline/chat must virtualize or window long lists, collapse noisy tool calls, and offer transcript view modes.

5. Preview evidence must point to the actual changed area.
   - Replit users complained about checkpoints and screenshots that captured irrelevant front pages instead of the edited UI.
   - Source: https://www.reddit.com/r/replit/comments/1kpupsy/replit_makes_checkpoints_unnecessarily_and/
   - Design implication: Preview/artifact evidence needs target metadata: route, selector/region, viewport, and why the screenshot was taken.

6. Agents need precise edit tools, not whole-file rewrites.
   - Zed users reported agents rewriting entire files for small edits, wasting time and context.
   - Source: https://www.reddit.com/r/ZedEditor/comments/1sllu4d/zeds_agent_keeps_rewriting_entire_files_instead/
   - Design implication: Diff/review should make edit granularity visible and warn when a small task creates a large rewrite.

7. Operators want to intercept or edit commands.
   - Zed feedback asked for a way to edit commands the agent wants to run before execution.
   - Source: https://www.reddit.com/r/ZedEditor/comments/1rau42m/how_to_edit_commands_the_agent_decides_to_run_in/
   - Design implication: Approval prompts should support approve, reject, and edit command where safe.

8. Worktree/local/cloud mental models are easy to confuse.
   - Codex users reported confusion when trying to make Codex use an existing worktree instead of creating/managing its own.
   - Source: https://www.reddit.com/r/codex/comments/1t8yez9/how_do_you_actually_make_codex_use_existing_git/
   - Design implication: Execution target must be explicit: local folder, managed worktree, existing worktree, cloud sandbox, or remote/NAS.

9. Handoff actions must be dependable and state-specific.
   - Codex users reported a missing "Hand off" button in a worktree thread where they expected it.
   - Source: https://www.reddit.com/r/ChatGPT/comments/1sknk06/codex_hand_off_button_missing_in_worktree_thread/
   - Design implication: If an action is unavailable, show why and what state transition is needed.

10. Parallel sessions solve visibility, but create conflict and cost questions.
   - Claude Code feedback praised multi-session UI and integrated terminal, but raised questions about same-file conflicts, usage caps, RAM, and whether UI alone solves the bottleneck.
   - Source: https://www.reddit.com/r/ClaudeCode/comments/1sljk0t/claude_code_just_got_a_full_desktop_redesign/
   - Design implication: Builder must show session isolation, branch/worktree, edited files, cost/usage, and conflict risk.

## Design Principles Extracted

- Make execution scope visible before the prompt is sent.
- Put Rule Sets next to the Agent, not only in Settings.
- Treat diff review as a primary product surface.
- Treat terminal output capture as a reliability contract.
- Collapse noisy traces by default, but preserve full audit detail.
- Virtualize long timelines and avoid rendering thousands of tool-call rows.
- Show cost/context pressure before it becomes a surprise.
- Every preview screenshot needs a route/selector/reason.
- Approval prompts need edit/reject/approve/retry paths.
- Disabled actions must say why they are disabled.

