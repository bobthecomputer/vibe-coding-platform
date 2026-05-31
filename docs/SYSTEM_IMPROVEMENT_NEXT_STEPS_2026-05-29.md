# Fluxio Improvement Notes - 2026-05-29

## Current Evidence

- Authenticated NAS Builder verification passed at `2026-05-29T19:19:48Z`.
- Authenticated NAS Agent drill-down verification passed at `2026-05-29T19:20:02Z`.
- Current live NAS summary shows `52` mission rows, `2` running Hermes missions, `0` queued rows, `44` completed missions, `24` notifications, and `17` slice-completed notifications.
- Runtime split is `48` Hermes rows and `4` OpenClaw rows, so Hermes is the dominant harness in the current mission set.
- The Builder first-paint path now uses a live `summaryMode: "bootstrap"` control-room summary. Direct NAS measurement showed `52` mission rows and `24` notifications in about `744 ms`, before heavier audit/snapshot data finishes.
- Latest local T3 Code check observed `v0.0.24` as the stable tag and `v0.0.25-nightly.20260529.411` as the latest prerelease tag from `github.com/pingdotgg/t3code`; `t3.codes` still presents T3 Code as a web/desktop control plane for Claude Code, Codex, OpenCode, and Cursor.
- The current system-loss digest now reports explicit loss drivers. The highest current driver is red-team escalation pressure: the aggregate-only hackaprompt benchmark advanced from `37` to `39` next attempts after a clean `37/37` blocked run at resistance `100`.

## What Is Still Bad

- Public distribution is still not finished: private NAS web, release-candidate artifacts, launcher proof, and web checks exist, but public registry publication or a signed installer is not proven.
- Closed-tab browser notifications have a sender path now, but production VAPID keys and a real browser subscription still need to be provisioned before closed-tab Web Push is fully operational.
- The UI is improving, but the operator experience still needs cleaner mobile density and clearer proof of progress when a mission only exposes summary state.
- Skills were too easy to perceive as missing when the NAS returned feedback-loop data but no full skill catalog rows.
- Perceived speed was a real defect: the old Builder path could sit on `pending` while the summary API was still building heavy metadata. The fast live bootstrap path fixes first paint, and the live-data verifier now guards that path.

## Immediate Direction

- Keep Hermes as the default mission harness unless a route has stronger live evidence for another runtime.
- Keep route trust promoted only while repeated value-scored missions by category remain green, not from static capability claims.
- Prefer live NAS summary/detail evidence over local snapshots, fixture rows, and stale browser reports.
- Make every empty UI state explicit: if a live contract is absent, say which contract is missing; if live data exists, show the best available live evidence.
- Keep T3 Code as the usability baseline: low-friction launch, fast multi-agent surface, provider connections, diff review, worktrees, and one-click PR flow are the comparison floor.

## Patch Applied From This Review

- Skills now fall back to live mission-slice feedback rows when the full NAS skill catalog is absent, instead of showing an apparently empty skills surface.
- Running and queued missions now show status-derived live progress bars while waiting for detailed mission progress events.
- Builder now requests a fast live bootstrap summary first, so current mission rows and notifications paint before the full control-room snapshot.
- `verify:live-data` now checks that the frontend requests the bootstrap summary and that the backend supports it, preventing regression to stale pending/fallback behavior.
- Mission notifications now expose explicit `Show all`, `Show less`, and `Restore dismissed` controls; mobile no longer silently hides notification cards after the third row.
- The Agent live surface now scopes selected-message state by mission/thread and exposes `data-preview-state`; the authenticated F1-message verifier fails if clicking a live message leaves any stale iframe instead of a selected-message proof panel.
- Builder now receives a `fluxio.system_loss_breakdown.v1` digest in the fast bootstrap summary, so the first live paint shows ranked system-loss drivers instead of only broad scores.
