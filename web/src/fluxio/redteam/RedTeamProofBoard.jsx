import React, { useMemo } from "react";

import { buildRedTeamProofBoard } from "./redTeamProofFixtures.js";

function titleize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, char => char.toUpperCase());
}

export function RedTeamProofBoard({ variant = "drawer", onOpenRuntime = null } = {}) {
  const board = useMemo(() => buildRedTeamProofBoard(), []);

  if (variant === "builder") {
    return (
      <article className="builder-panel builder-panel-focus">
        <p className="eyebrow">Red-team proof</p>
        <h3>{board.summary.safePacketCount} controlled proof packet{board.summary.safePacketCount === 1 ? "" : "s"}</h3>
        <p>
          Fictional targets, no live model calls, no network activity, and visible transcript proof stay attached to JBH-EAVEN routes.
        </p>
        <div className="builder-thread-list">
          {board.rows.slice(0, 2).map(item => (
            <article className="builder-thread-item tone-neutral" key={`builder-redteam-proof-${item.id}`}>
              <span>{item.scenarioId}</span>
              <strong>{item.title}</strong>
              <p>
                Boundary {item.boundaryScore}/100 · {board.summary.coveragePassedCount}/{board.summary.coverageCheckCount} safe checks · {board.summary.probeTranscriptCount} transcripts
              </p>
            </article>
          ))}
        </div>
        <button className="action-btn" onClick={onOpenRuntime} type="button">Open red-team proof</button>
      </article>
    );
  }

  return (
    <section className="drawer-block">
      <h3>Controlled red-team proof</h3>
      <p>
        JBH-EAVEN probes stay synthetic, fictional, transcript-backed, and human-reviewed before any live model route is promoted.
      </p>
      <div className="context-grid compact-metrics">
        <article className="context-item">
          <span>Packets</span>
          <strong>{board.summary.packetCount}</strong>
        </article>
        <article className="context-item">
          <span>Safe</span>
          <strong>{board.summary.safePacketCount}</strong>
        </article>
        <article className="context-item">
          <span>Probe families</span>
          <strong>{board.summary.probeFamilyCount}</strong>
        </article>
        <article className="context-item">
          <span>Coverage</span>
          <strong>{board.summary.coveragePassedCount}/{board.summary.coverageCheckCount}</strong>
        </article>
        <article className="context-item">
          <span>Boundary score</span>
          <strong>{board.summary.boundaryScoreAverage}/100</strong>
        </article>
        <article className="context-item">
          <span>Probe transcripts</span>
          <strong>{board.summary.probeTranscriptCount}</strong>
        </article>
      </div>
      <div className="drawer-list redteam-proof-list">
        {board.rows.map(item => (
          <article className="drawer-card redteam-proof-card" key={`redteam-proof-${item.id}`}>
            <span>{item.boundary.authorization} · {item.route.model}</span>
            <strong>{item.title}</strong>
            <p>
              Fictional targets only: {item.boundary.fictionalTargetsOnly ? "yes" : "no"} · Live model calls:{" "}
              {item.route.liveModelCalls ? "yes" : "no"} · Network activity: {item.boundary.networkActivity ? "yes" : "no"}
            </p>
            <div className="redteam-boundary-score" aria-label={`${item.title} boundary score`}>
              <span>Boundary score {item.boundaryScore}/100</span>
              <span>Coverage {item.coverageScore}/100</span>
              <span>Transcript {item.transcriptScore}/100</span>
              <span>{titleize(item.reviewStatus)}</span>
              <span>Blocked conditions {item.blockedConditionCount}</span>
            </div>
            <div className="pill-row">
              {item.probeFamilies.slice(0, 4).map(family => (
                <span className="mini-pill" key={`${item.id}-${family}`}>{titleize(family)}</span>
              ))}
            </div>
            <p>{item.refusalQualityChecks.join(" · ")}</p>
            <div className="redteam-coverage-matrix" aria-label={`${item.title} safe coverage matrix`}>
              {item.coverageMatrix.map(row => (
                <article className="redteam-coverage-row" key={`${item.id}-${row.family}`}>
                  <span>{titleize(row.family)} · {titleize(row.status)}</span>
                  <strong>{row.score}</strong>
                  <p>{row.evidence}</p>
                  <small>{row.humanReview ? "Human review required" : "Automated check only"}</small>
                </article>
              ))}
            </div>
            <div className="redteam-probe-transcripts" aria-label={`${item.title} safe probe transcripts`}>
              {item.probeTranscripts.map(probe => (
                <article className="redteam-probe-row" key={`${item.id}-${probe.id}`}>
                  <span>{titleize(probe.family)} · {titleize(probe.status)} · {probe.score}</span>
                  <strong>{probe.id}</strong>
                  <p><b>Prompt:</b> {probe.prompt}</p>
                  <p><b>Response:</b> {probe.response}</p>
                  <small>{probe.runtime} · {probe.provider} · {probe.model} · {probe.selectedSkill}</small>
                  <em>{probe.boundaryNotes}</em>
                  <code>{probe.artifactPath}</code>
                </article>
              ))}
            </div>
            <p className="fusion-source-path">{item.artifactPaths.transcript}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
