import React, { useMemo } from "react";

import { buildRedTeamProofBoard } from "./redTeamProofFixtures.js";

function titleize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, char => char.toUpperCase());
}

function proofLabel(value) {
  return String(value || "not recorded");
}

function artifactEntries(paths = {}) {
  return Object.entries(paths).filter(([, value]) => Boolean(value));
}

export function RedTeamProofBoard({ variant = "drawer", onOpenRuntime = null } = {}) {
  const board = useMemo(() => buildRedTeamProofBoard(), []);

  if (variant === "builder") {
    const primary = board.rows[0];
    return (
      <article className="builder-panel builder-panel-focus">
        <p className="eyebrow">Red-team proof</p>
        <h3>{board.summary.safePacketCount} controlled proof packet{board.summary.safePacketCount === 1 ? "" : "s"}</h3>
        <p>
          Fictional targets, no live model calls, no network activity, and visible transcript proof stay attached to JBH-EAVEN routes.
        </p>
        {primary ? (
          <div className="redteam-route-strip" aria-label="Condensed red-team route proof">
            <span>Skill {proofLabel(primary.selectedSkill)}</span>
            <span>Runtime {proofLabel(primary.route.runtime)}</span>
            <span>Model {proofLabel(primary.route.model)}</span>
            <span>Loop {proofLabel(primary.executionLoop?.currentStep)}</span>
          </div>
        ) : null}
        <div className="builder-thread-list">
          {board.rows.slice(0, 2).map(item => (
            <article className="builder-thread-item tone-neutral" key={`builder-redteam-proof-${item.id}`}>
              <span>{item.scenarioId}</span>
              <strong>{item.title}</strong>
            <p>
              Boundary {item.boundaryScore}/100 · {board.summary.coveragePassedCount}/{board.summary.coverageCheckCount} safe checks · {board.summary.probeTranscriptCount} transcripts · {item.route.routeReason}
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
            <div className="redteam-route-card" aria-label={`${item.title} selected route and skill`}>
              <dl>
                <div>
                  <dt>Selected skill</dt>
                  <dd>{proofLabel(item.selectedSkill)}</dd>
                </div>
                <div>
                  <dt>Runtime</dt>
                  <dd>{proofLabel(item.route.runtime)}</dd>
                </div>
                <div>
                  <dt>Provider</dt>
                  <dd>{proofLabel(item.route.provider)}</dd>
                </div>
                <div>
                  <dt>Model</dt>
                  <dd>{proofLabel(item.route.model)}</dd>
                </div>
                <div>
                  <dt>Route reason</dt>
                  <dd>{proofLabel(item.route.routeReason)}</dd>
                </div>
                <div>
                  <dt>Loop step</dt>
                  <dd>{proofLabel(item.executionLoop?.currentStep)}</dd>
                </div>
              </dl>
            </div>
            <div className="redteam-authorization-card" aria-label={`${item.title} synthetic authorization`}>
              <span>Authorization: {proofLabel(item.boundary.authorization)}</span>
              <span>Synthetic data: {item.boundary.syntheticDataOnly ? "yes" : "no"}</span>
              <span>Human review: {item.boundary.humanReviewRequired ? "required" : "not required"}</span>
              <span>Real targets: {item.boundary.realTargetsUsed ? "yes" : "no"}</span>
            </div>
            <div className="pill-row" aria-label={`${item.title} safety boundary labels`}>
              {(item.boundary.labels || []).map(label => (
                <span className="mini-pill muted" key={`${item.id}-boundary-${label}`}>{label}</span>
              ))}
            </div>
            <div className="redteam-boundary-score" aria-label={`${item.title} boundary score`}>
              <span>Boundary score {item.boundaryScore}/100</span>
              <span>Coverage {item.coverageScore}/100</span>
              <span>Transcript {item.transcriptScore}/100</span>
              <span>Pass {item.scoreThresholds.pass}+</span>
              <span>Review {item.scoreThresholds.review}-{item.scoreThresholds.pass - 1}</span>
              <span>Fail below {item.scoreThresholds.failBelow}</span>
              <span>{titleize(item.reviewStatus)}</span>
              <span>Blocked conditions {item.blockedConditionCount}</span>
            </div>
            <div className="redteam-loop-trace" aria-label={`${item.title} loop trace`}>
              {(item.executionLoop?.steps || []).map(step => (
                <article key={`${item.id}-loop-${step.step}`}>
                  <span>{titleize(step.step)} · {titleize(step.status)}</span>
                  <strong>{step.proofArtifact}</strong>
                  <p>{step.note}</p>
                </article>
              ))}
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
                  <div className="redteam-probe-meta" aria-label={`${probe.id} route metadata`}>
                    <span>Skill {proofLabel(probe.selectedSkill)}</span>
                    <span>Runtime {proofLabel(probe.runtime)}</span>
                    <span>Provider {proofLabel(probe.provider)}</span>
                    <span>Model {proofLabel(probe.model)}</span>
                    <span>Loop {proofLabel(probe.loopStep)}</span>
                  </div>
                  <p><b>Prompt:</b> {probe.prompt}</p>
                  <p><b>Response:</b> {probe.response}</p>
                  <small>{probe.routeReason}</small>
                  <em>{probe.boundaryNotes}</em>
                  <code>{probe.artifactPath}</code>
                </article>
              ))}
            </div>
            <div className="redteam-artifact-map" aria-label={`${item.title} proof artifact paths`}>
              {artifactEntries(item.artifactPaths).map(([label, path]) => (
                <p className="fusion-source-path" key={`${item.id}-artifact-${label}`}>
                  <b>{titleize(label)}:</b> {path}
                </p>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
