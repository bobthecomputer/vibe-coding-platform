function asList(value) {
  return Array.isArray(value) ? value : [];
}

function asRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function titleizeToken(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function toneClass(tone) {
  const normalized = String(tone || "neutral").toLowerCase();
  if (["good", "ok", "success", "ready"].includes(normalized)) return "tone-good";
  if (["warn", "warning", "hold", "needed"].includes(normalized)) return "tone-warn";
  if (["bad", "error", "blocked", "failed"].includes(normalized)) return "tone-bad";
  return "tone-neutral";
}

function checklistTone(status) {
  if (status === "ready") return "good";
  if (status === "needed") return "warn";
  return "neutral";
}

function deriveReadiness(studio) {
  const active = Number(studio.activeCount || 0);
  const blocked = Number(studio.blockedCount || 0);
  const workers = Math.max(1, Number(studio.configuredWorkers || 1));
  if (blocked > 0) {
    return {
      state: "hold",
      tone: "warn",
      label: "Hold spawning",
      reason: "A delegated lane needs approval, proof, or recovery first.",
      nextAction: "Resolve lane blockers before creating new subagents.",
    };
  }
  if (active >= workers) {
    return {
      state: "wait",
      tone: "neutral",
      label: "Wait for active lanes",
      reason: "Configured worker capacity is already in use.",
      nextAction: "Monitor heartbeat and latest events before adding more workers.",
    };
  }
  return {
    state: "ready",
    tone: "good",
    label: "Ready to spawn another lane",
    reason: "There is worker capacity and no delegated lane is blocked.",
    nextAction: "Split the next task by file ownership and assign verifier proof before execution.",
  };
}

function deriveChecklist(studio, lanes) {
  return [
    {
      id: "lane-proof",
      label: "Lane proof captured",
      status: lanes.length > 0 && lanes.every(item => item.proof && !String(item.proof).includes("expected")) ? "ready" : "needed",
    },
    {
      id: "blocked-lanes",
      label: "No blocked lanes",
      status: Number(studio.blockedCount || 0) === 0 ? "ready" : "needed",
    },
    {
      id: "merge-scoreboard",
      label: "Merge scoreboard",
      status: asList(studio.scoreboard).length > 0 ? "ready" : "optional",
    },
    {
      id: "handoff-context",
      label: "Handoff context bounded",
      status: lanes.length > 0 ? "ready" : "needed",
    },
  ];
}

export function SubagentReadinessPanel({ studio }) {
  const orchestration = asRecord(studio);
  const lanes = asList(orchestration.lanes);
  const readiness = deriveReadiness(orchestration);
  const checklist = deriveChecklist(orchestration, lanes);
  const firstLane = lanes[0] || {};
  const route = firstLane.runtime
    ? `${firstLane.runtime} / ${firstLane.provider || "Provider"} / ${firstLane.model || "model"}`
    : `${titleizeToken(orchestration.mergePolicy || "best_score")} merge`;
  const roles = lanes.length > 0
    ? lanes.map(item => titleizeToken(item.role)).filter(Boolean).slice(0, 4).join(" · ")
    : "Researcher · Executor · Verifier";

  return (
    <article className={`subagent-readiness-panel ${toneClass(readiness.tone)}`} aria-label="Subagent spawn readiness">
      <div className="subagent-readiness-head">
        <div>
          <span>Spawn readiness</span>
          <strong>{readiness.label || "Readiness pending"}</strong>
        </div>
        <span className={`mini-pill ${toneClass(readiness.tone)}`}>
          {titleizeToken(readiness.state || "pending")}
        </span>
      </div>
      <p>{readiness.reason || "No readiness reason captured yet."}</p>
      <div className="subagent-handoff-grid">
        <article>
          <span>Handoff packet</span>
          <strong>{route}</strong>
          <small>Give each lane owned files, checks, route, and proof path.</small>
        </article>
        <article>
          <span>Suggested roles</span>
          <strong>{roles || "Assign roles"}</strong>
          <small>Preserve user work during merge.</small>
        </article>
      </div>
      <div className="subagent-merge-checklist" aria-label="Subagent merge checklist">
        {checklist.map(item => (
          <span className={`mini-pill ${toneClass(checklistTone(item.status))}`} key={item.id || item.label}>
            {item.label}: {titleizeToken(item.status)}
          </span>
        ))}
      </div>
      <small>{readiness.nextAction || orchestration.recommendedAction}</small>
    </article>
  );
}

export default SubagentReadinessPanel;
