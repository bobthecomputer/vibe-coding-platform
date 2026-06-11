# Notification Bot Architecture

Status: ntfy is the proven phone/tablet push transport; Huginn is the recommended NAS-hosted worker graph; Matrix/Maubot is the optional interactive chat-bot layer.

## Decision

Use Huginn plus ntfy as the first external notification/bot layer.

- Huginn owns normal software workers: mission watcher, watchdog, digest builder, verification receipt collector, and retry planner.
- ntfy owns phone/tablet push delivery through an existing iOS app and a simple HTTP publish API.
- Matrix plus Maubot remains the second option if the product needs interactive chat commands instead of one-way alerts.
- Do not replace these workers with an LLM loop. The LLM can write summaries and repair plans, but timestamps, receipts, dedupe, retries, and watchdog checks should be deterministic workers.

Research checked 2026-06-02:

- Huginn: https://github.com/huginn/huginn
- ntfy: https://github.com/binwiederhier/ntfy
- ntfy publish API: https://docs.ntfy.sh/publish/
- ntfy iOS/self-hosting note: https://docs.ntfy.sh/config/#ios-instant-notifications
- ntfy iOS app: https://apps.apple.com/us/app/ntfy/id1625396347
- Maubot: https://github.com/maubot/maubot
- Element open source clients: https://element.io/open-source

## Why This Fits Fluxio

Fluxio already has live mission rows, Hermes runtime reports, Builder/Agent proof surfaces, and watchdog state. The missing layer is a small, durable worker graph that can run without a model:

1. Mission event is created or updated.
2. Watcher records the mission id, runtime, state, and timestamp.
3. Watchdog checks stale time, blocked gates, missing proof, and exhausted budgets.
4. Digest worker summarizes only live NAS facts.
5. Notifier sends slice-complete, blocked, approval, and overnight digest notifications.
6. Receipt worker records delivery status back into Fluxio.

This avoids asking an LLM to do bookkeeping that a normal worker should handle.

## Integration State

1. Done: add `FLUXIO_NTFY_TOPIC`, `FLUXIO_NTFY_SERVER_URL`, `FLUXIO_NTFY_TOKEN`, or ignored `.agent_control/ntfy_settings.json` support.
2. Done: add `get_ntfy_status_command` and `send_ntfy_notification_command` with title, message, tags, priority, click URL, dry-run support, and delivery receipts.
3. Done: expose ntfy status in live summary/snapshot payloads and phone proof UI.
4. Keep current browser/Web Push UI as secondary proof, not the primary mobile notification path.
5. Done: watchdog one-shot and loop commands support `--notify-ntfy`, including clear-state receipts when explicitly requested.
6. Next: install Huginn as the external scenario runner and point it at Fluxio's live NAS endpoints plus the existing ntfy topic.

## Why ntfy Wins The Phone Layer

The ntfy project describes itself as push notifications to phone or desktop via HTTP PUT/POST. The publish API supports titles, priorities, tags, click actions, action buttons, webhooks, delayed delivery, and updating or deleting delivered notifications. That matches Fluxio's needs for slice-complete, approval-needed, watchdog, and digest events.

For iOS, self-hosted instant push still needs an APNS/Firebase-connected upstream for `poll_request` forwarding. For the current closeout, use `https://ntfy.sh` with a private random topic because that path is already proven live. For production, move to a token-protected self-hosted ntfy server with `upstream-base-url` configured for iOS instant notifications.

## Why Huginn Wins The Worker Layer

Huginn is open source and built around agents that create and consume events in a directed graph. It can watch webhooks, poll APIs, run schedules, send digests, and invoke HTTP endpoints without turning bookkeeping into fragile Python scripts. The Fluxio scenario should be:

1. `FluxioMissionPoller`: poll `/api/control/live-summary` and mission detail endpoints.
2. `SliceCompleteDetector`: emit only new mission slice completions using event ids.
3. `WatchdogProblemDetector`: emit stale, blocked, approval, provider, and budget problems.
4. `DigestBuilder`: build a timed overnight/phone digest from live NAS facts only.
5. `NtfyNotifier`: publish to the configured ntfy topic with click URLs back to Fluxio.
6. `ReceiptWriter`: write delivery receipts back into Fluxio so the UI shows proof.

## Current NAS Proof

- `get_ntfy_status_command` reports an active topic from `.agent_control/ntfy_settings.json`.
- `send_ntfy_notification_command` recorded a delivered live broker receipt through `https://ntfy.sh`.
- The phone verifier now checks both `summary-ntfy-status-live` and `phone-ntfy-proof-visible`.
- The external mission watchdog supports `--notify-ntfy` and records ntfy watchdog receipts with duplicate suppression.
- Production hardening should move the topic to a token-protected or self-hosted ntfy server before sending sensitive mission details.

## Recommended Event Types

- `mission.slice.completed`
- `mission.blocked`
- `mission.runtime_budget.exhausted`
- `mission.approval.required`
- `mission.watchdog.problem`
- `mission.digest.overnight`
- `system.audit.changed`

## Rejected For First Slice

- Custom iOS app: too much platform work before the product loop is stable.
- Browser-only Web Push: useful but fragile for closed-tab phone use and permission UX.
- Telegram-only: practical but not open-source/self-hosted enough for the requested direction.
- Novu first: strong product notification service, but heavier than needed for the first NAS-hosted worker loop.
