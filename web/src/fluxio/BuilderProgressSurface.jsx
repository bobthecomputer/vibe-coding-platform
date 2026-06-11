/**
 * BuilderProgressSurface.jsx
 *
 * Polished phone/tablet Builder progress surface — shows:
 *   - Mission status strip (all active missions across workspaces)
 *   - Notification receipts (Telegram, ntfy, and Web Push status)
 *   - First Watchdog repair step (highest-priority open issue + next action)
 *
 * Task-aware routing integration:
 *   - Codex  → planning surfaces (proof, queue, review studio)
 *   - MiniMax-M3 -> frontend/UI polish pass (this surface)
 *   - Hermes / OpenClaw → runtime supervision + Watchdog verification
 *
 * Mounts inside the Builder drawer (activeDrawer === "builder" && uiMode === "builder")
 * as a dedicated progress rail below the confidence engine.
 */

import React, { useMemo } from "react";
import {
  ActivityIcon,
  Bell,
  Broadcast,
  CheckCircle,
  CircleDashed,
  Compass,
  Envelope,
  Funnel,
  ShieldCheck,
  Siren,
  Warning,
  Watch,
  Wrench,
  XCircle,
} from "@phosphor-icons/react";
import {
  missionStatusTone,
  titleizeToken,
} from "../../../desktop-ui/fluxioHelpers.js";
import { ActionButton, MetricStrip, StatusPill } from "../../../desktop-ui/MissionControlPrimitives.jsx";

// ---------------------------------------------------------------------------
// Tone helpers
// ---------------------------------------------------------------------------

/** Maps Fluxio tone strings to phosphor icon weight / colour tokens. */
function toneClass(tone) {
  const map = {
    good: "tone-good",
    warn: "tone-warn",
    bad: "tone-bad",
    muted: "tone-muted",
    neutral: "tone-neutral",
  };
  return map[String(tone || "neutral").toLowerCase()] || "tone-neutral";
}
export { toneClass };

/** Returns the appropriate Phosphor icon component for a tone. */
function toneIcon(tone, size = 16) {
  const t = String(tone || "neutral").toLowerCase();
  if (t === "good") return <CheckCircle size={size} weight="fill" />;
  if (t === "warn") return <Warning size={size} weight="fill" />;
  if (t === "bad") return <XCircle size={size} weight="fill" />;
  return <CircleDashed size={size} weight="regular" />;
}

/** Returns the Phosphor icon component for a notification channel. */
function channelIcon(channel, size = 14) {
  const c = String(channel || "").toLowerCase();
  if (c === "telegram") return <Siren size={size} />;
  if (c === "ntfy") return <Broadcast size={size} />;
  if (c === "web_push" || c === "webpush") return <Broadcast size={size} />;
  if (c === "browser" || c === "window_notification") return <Bell size={size} />;
  return <Envelope size={size} />;
}

// ---------------------------------------------------------------------------
// Mission status strip
// ---------------------------------------------------------------------------

function toneColourVar(tone) {
  const map = {
    good: "var(--flux-good, #22c55e)",
    warn: "var(--flux-warn, #f59e0b)",
    bad: "var(--flux-bad, #ef4444)",
    muted: "var(--flux-muted, #94a3b8)",
    neutral: "var(--flux-muted, #94a3b8)",
  };
  return map[String(tone || "neutral").toLowerCase()] || map.neutral;
}

const CLOSED_MISSION_STATUSES = new Set(["completed", "failed", "cancelled", "canceled", "closed", "done"]);

function sanitizeProgressText(value) {
  return String(value || "")
    .replace(/\bsystem-loss improvement mission\b/gi, "system improvement mission")
    .replace(/\bsystem loss improvement mission\b/gi, "system improvement mission")
    .replace(/\bsystem-loss\b/gi, "system improvement")
    .replace(/\bsystem loss\b/gi, "system improvement");
}

export function normalizeMissionProgressRow(row = {}, index = 0) {
  const state = row.state && typeof row.state === "object" ? row.state : {};
  const missionId = row.mission_id || row.missionId || row.id || state.mission_id || state.missionId || "";
  const rawStatus = state.status || row.status || row.badge || state.badge || "unknown";
  const status = String(rawStatus || "unknown").toLowerCase();
  const tone = row.tone || state.tone || missionStatusTone(status);
  const title = sanitizeProgressText(row.title || row.name || row.objective || row.label || (missionId ? `Mission ${missionId}` : "Mission"));
  const key = String(missionId || `${title}-${status}-${index}`);
  return {
    ...row,
    key,
    missionId,
    status,
    tone,
    title,
    objective: row.objective || row.description || "",
  };
}

export function MissionStatusStrip({ missionRows }) {
  const activeRows = (Array.isArray(missionRows) ? missionRows : [])
    .map((m, index) => normalizeMissionProgressRow(m, index))
    .filter((m) => !CLOSED_MISSION_STATUSES.has(m.status));
  if (activeRows.length === 0) {
    return (
      <div className="builder-progress-missions-empty" aria-label="No active missions">
        <Compass size={18} />
        <span>No active missions</span>
      </div>
    );
  }

  return (
    <div
      className="builder-progress-missions-strip"
      role="list"
      aria-label="Mission status strip"
      data-phone-mission-stack="true"
    >
      {activeRows.map((m) => {
        const tone = m.tone || missionStatusTone(m.status);
        return (
          <div
            key={m.key}
            className={`mission-status-dot ${toneClass(tone)}`}
            role="listitem"
            data-phone-mission-card="true"
            data-mission-id={m.missionId || undefined}
            title={`${m.title || m.objective || "Mission"} · ${titleizeToken(m.status || "unknown")}`}
          >
            <span
              className="mission-dot-indicator"
              style={{ background: toneColourVar(tone) }}
              aria-hidden="true"
            />
            <span className="mission-dot-label">
              {m.title || m.objective?.slice(0, 22) || "…"}{" "}
              <em>{titleizeToken(m.status || "")}</em>
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Notification receipts
// ---------------------------------------------------------------------------

const CHANNEL_LABELS = {
  telegram: "Telegram",
  ntfy: "ntfy",
  web_push: "Web Push",
  webpush: "Web Push",
  browser: "Browser",
  window_notification: "Window",
};

export function NotificationReceipts({ receipts, webPushStatus, ntfyStatus }) {
  const items = useMemo(() => {
    const out = [];
    // Telegram delivery receipts from Watchdog
    if (Array.isArray(receipts)) {
      for (const r of receipts) {
        out.push({
          channel: r.channel || r.deliveryMethod || "telegram",
          status: r.status || "unknown",
          sentAt: r.sentAt || r.generatedAt || "",
          detail: r.detail || r.message || "",
          missionId: r.missionId || "",
        });
      }
    }
    // Web Push status from the backend snapshot
    if (webPushStatus && typeof webPushStatus === "object") {
      out.push({
        channel: "web_push",
        status: webPushStatus.status || (webPushStatus.configured
          ? webPushStatus.senderConfigured
            ? "subscribed"
            : "delivery_skipped"
          : "not_configured"),
        detail: webPushStatus.nextAction || webPushStatus.detail || "",
        sentAt: webPushStatus.sentAt || "",
        missionId: webPushStatus.missionId || "",
      });
    }
    if (ntfyStatus && typeof ntfyStatus === "object") {
      out.push({
        channel: "ntfy",
        status: ntfyStatus.status || (ntfyStatus.configured ? "ready" : "not_configured"),
        detail: ntfyStatus.nextAction || ntfyStatus.detail || "",
        sentAt: ntfyStatus.sentAt || "",
        missionId: ntfyStatus.missionId || "",
      });
    }
    return out;
  }, [receipts, webPushStatus, ntfyStatus]);

  if (items.length === 0) {
    return (
      <div className="builder-progress-receipts-empty" aria-label="No notification receipts">
        <Bell size={16} />
        <span>No live delivery receipts yet — completion proof stays pending until ntfy, Telegram, Web Push, or browser receipt rows arrive.</span>
      </div>
    );
  }

  return (
    <div
      className="builder-progress-receipts"
      role="list"
      aria-label="Notification receipts"
      data-phone-notification-stack="true"
    >
      {items.map((item, i) => {
        const label = CHANNEL_LABELS[item.channel] || titleizeToken(item.channel);
        const statusTone =
          ["delivered", "subscribed", "visible", "sent", "ready", "success"].includes(item.status)
            ? "good"
            : ["failed", "error", "blocked"].includes(item.status)
              ? "bad"
              : ["not_configured", "delivery_skipped", "unsupported", "local_only"].includes(item.status)
                ? "muted"
                : "neutral";
        return (
          <div
            key={`${item.channel}-${item.missionId || item.sentAt || i}`}
            className={`receipt-row ${toneClass(statusTone)}`}
            role="listitem"
            data-phone-notification-card="true"
            aria-label={`${label} notification receipt: ${titleizeToken(item.status || "unknown")}${item.detail ? `. ${item.detail}` : ""}`}
          >
            <span className="receipt-channel-icon">{channelIcon(item.channel)}</span>
            <span className="receipt-channel">
              {label}
              {item.detail ? <small className="receipt-detail">{item.detail}</small> : null}
            </span>
            <span className={`receipt-status ${toneClass(statusTone)}`}>
              {toneIcon(statusTone, 13)}
              {titleizeToken(item.status || "unknown")}
              {item.sentAt ? <small className="receipt-time">{item.sentAt}</small> : null}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Watchdog repair step — first open issue + next action
// ---------------------------------------------------------------------------

export function WatchdogRepairStep({ missionWatchdog }) {
  // missionWatchdog is the flat report dict from build_mission_watchdog_report.
  const severityRank = { bad: 0, critical: 0, error: 0, warn: 1, warning: 1, info: 2, neutral: 3, good: 4 };
  const problemRegistry = missionWatchdog?.problemRegistry || {};
  const openProblems = [
    problemRegistry?.firstOpenProblem,
    problemRegistry?.firstProblem,
    ...(Array.isArray(problemRegistry?.problems) ? problemRegistry.problems : []),
    ...(Array.isArray(missionWatchdog?.issues) ? missionWatchdog.issues : []),
  ].filter((item, index, rows) => {
    if (!item) return false;
    const status = String(item.status || item.state || "open").toLowerCase();
    const id = item.problemId || item.issueId || item.title || `${item.kind || "issue"}-${index}`;
    return !["closed", "resolved", "ignored", "dismissed"].includes(status)
      && rows.findIndex(other => (other?.problemId || other?.issueId || other?.title || "") === id) === index;
  });
  const explicitIssueCount = Number(missionWatchdog?.issueCount || 0);
  const effectiveIssueCount = explicitIssueCount > 0 ? explicitIssueCount : openProblems.length;
  const hasIssues = effectiveIssueCount > 0;
  const firstProblem = openProblems.sort((a, b) =>
    (severityRank[String(a.severity || a.tone || "neutral").toLowerCase()] ?? 3)
    - (severityRank[String(b.severity || b.tone || "neutral").toLowerCase()] ?? 3)
  )[0] || null;
  const nextAction = missionWatchdog?.nextAction ||
    firstProblem?.firstStep ||
    firstProblem?.firstRepairStep ||
    "No watchdog issues. Keep the scheduled loop active.";

  const issuesSummary = `${effectiveIssueCount} issue${effectiveIssueCount === 1 ? "" : "s"}`
    + ` · Bad: ${missionWatchdog?.bad || 0}`
    + ` · Warn: ${missionWatchdog?.warn || 0}`;

  const loopLabel = missionWatchdog?.loopActive
    ? "Loop active"
    : titleizeToken(missionWatchdog?.loopStatus || "paused");

  const loopTone = missionWatchdog?.loopActive ? "good" : "muted";

  return (
    <div className="builder-watchdog-repair-step" aria-label="Watchdog repair step">
      <div className="repair-step-header">
        <span className="repair-step-eyebrow">
          {toneIcon(hasIssues ? "warn" : "good", 14)}
          Watchdog
        </span>
        <span className="repair-step-issues">{issuesSummary}</span>
        <StatusPill tone={loopTone}>{loopLabel}</StatusPill>
      </div>

      {firstProblem ? (
        <div className="repair-step-problem" key={firstProblem.problemId}>
          <div className="repair-problem-kind">
            {toneIcon(firstProblem.severity, 13)} {titleizeToken(firstProblem.kind || "watchdog problem")}
          </div>
          <strong className="repair-problem-title">{firstProblem.title}</strong>
          <p className="repair-problem-detail">{firstProblem.detail}</p>
          <div className={`repair-problem-first-step ${toneClass(firstProblem.severity)}`}>
            <Wrench size={12} />
            <span>{firstProblem.firstStep || firstProblem.firstRepairStep || nextAction}</span>
          </div>
        </div>
      ) : (
        <div className="repair-step-clear">
          <ShieldCheck size={18} />
          <p>No open watchdog problems.</p>
        </div>
      )}

      <div className="repair-step-next-action" aria-label="Next watchdog action">
        <Funnel size={12} />
        <span>{nextAction}</span>
      </div>

      {(missionWatchdog?.loopIntervalSeconds || 0) > 0 && (
        <div className="repair-step-cadence" aria-label="Watchdog cadence">
          <Watch size={11} />
          <span>
            Every{" "}
            {Math.max(1, Math.round((missionWatchdog.loopIntervalSeconds || 0) / 60))}m
            {missionWatchdog?.loopRunsCompleted
              ? ` · ${missionWatchdog.loopRunsCompleted} run${missionWatchdog.loopRunsCompleted === 1 ? "" : "s"}`
              : ""}
          </span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main surface
// ---------------------------------------------------------------------------

/**
 * BuilderProgressSurface
 *
 * Props (injected by parent via destructured viewModel / snapshot / etc.):
 *   - missionRows          – flat mission list (default: [])
 *   - missionWatchdog      – Watchdog report (default: {})
 *   - notificationReceipts – array of delivery receipt objects (default: [])
 *   - webPushStatus        – web push configuration status (default: {})
 *   - ntfyStatus           – ntfy configuration status (default: {})
 *   - telegramReady        – bool (default: false)
 *   - onWatchdogRefresh    – callback to trigger Watchdog refresh (optional)
 */
export function BuilderProgressSurface({
  missionRows = [],
  missionWatchdog = {},
  notificationReceipts = [],
  webPushStatus = {},
  ntfyStatus = {},
  telegramReady = false,
  onWatchdogRefresh,
}) {
  const normalizedMissions = useMemo(
    () => (Array.isArray(missionRows) ? missionRows : []).map((m, index) => normalizeMissionProgressRow(m, index)),
    [missionRows],
  );

  const activeMissions = useMemo(
    () => normalizedMissions.filter((m) => !CLOSED_MISSION_STATUSES.has(m.status)),
    [normalizedMissions],
  );

  const completedMissions = useMemo(
    () => normalizedMissions.filter((m) => CLOSED_MISSION_STATUSES.has(m.status)),
    [normalizedMissions],
  );

  const metricItems = useMemo(() => [
    {
      label: "Active",
      value: activeMissions.length,
      note: "missions",
    },
    {
      label: "Done",
      value: completedMissions.length,
      note: "completed",
    },
    {
      label: "Issues",
      value: missionWatchdog?.issueCount ?? 0,
      note: missionWatchdog?.bad ? `(${missionWatchdog.bad} bad)` : "",
      tone: (missionWatchdog?.issueCount ?? 0) > 0
        ? (missionWatchdog?.bad ? "bad" : "warn")
        : "good",
    },
    {
      label: "Receipts",
      value: notificationReceipts.length,
      note: telegramReady ? "Telegram ready" : "no Telegram",
    },
  ], [activeMissions.length, completedMissions.length, missionWatchdog, notificationReceipts.length, telegramReady]);

  return (
    <section className="builder-progress-surface" aria-label="Builder progress surface">
      {/* Mission status strip */}
      <div className="builder-progress-section" aria-label="Mission status">
        <div className="builder-progress-section-head">
          <ActivityIcon size={14} />
          <span>Mission status</span>
          <span className="builder-progress-section-meta">
            {activeMissions.length} active · {completedMissions.length} done
          </span>
        </div>
        <MissionStatusStrip missionRows={missionRows} />
      </div>

      {/* Metric strip */}
      <div className="builder-progress-metrics" aria-label="Progress metrics">
        <MetricStrip items={metricItems} columns={4} />
      </div>

      {/* Notification receipts */}
      <div className="builder-progress-section" aria-label="Notification receipts">
        <div className="builder-progress-section-head">
          <Bell size={14} />
          <span>Notification receipts</span>
          <span className="builder-progress-section-meta">
            {notificationReceipts.length} sent
          </span>
        </div>
        <NotificationReceipts
          receipts={notificationReceipts}
          webPushStatus={webPushStatus}
          ntfyStatus={ntfyStatus}
        />
      </div>

      {/* Watchdog repair step */}
      <div className="builder-progress-section" aria-label="Watchdog repair step">
        <div className="builder-progress-section-head">
          <ShieldCheck size={14} />
          <span>Watchdog repair</span>
          {onWatchdogRefresh && (
            <ActionButton
              onClick={onWatchdogRefresh}
              title="Refresh Watchdog"
              variant="ghost"
              className="builder-progress-refresh-btn"
            >
              Refresh
            </ActionButton>
          )}
        </div>
        <WatchdogRepairStep missionWatchdog={missionWatchdog} />
      </div>
    </section>
  );
}
