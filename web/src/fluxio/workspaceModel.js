export const WORKSPACE_SURFACES = Object.freeze([
  { id: "agent", label: "Agent", section: "workspace" },
  { id: "builder", label: "Builder", section: "workspace" },
  { id: "phone", label: "Phone", section: "workspace" },
  { id: "skills", label: "Skills", section: "workspace" },
  { id: "rule-sets", label: "Rule Sets", section: "workspace" },
  { id: "images", label: "Images", section: "workspace" },
  { id: "browser", label: "Browser", section: "workspace" },
  { id: "settings", label: "Settings", section: "global" },
]);

export const WORKSPACE_SURFACE_IDS = Object.freeze(WORKSPACE_SURFACES.map(surface => surface.id));

export const AGENT_STATUS_DEFINITIONS = Object.freeze({
  idle: { label: "Idle", tone: "neutral" },
  queued: { label: "Queued", tone: "neutral" },
  planning: { label: "Planning", tone: "info" },
  running: { label: "Running", tone: "good" },
  needs_approval: { label: "Needs approval", tone: "warn" },
  blocked: { label: "Blocked", tone: "bad" },
  verification_failed: { label: "Verification failed", tone: "bad" },
  completed: { label: "Completed", tone: "good" },
  failed: { label: "Failed", tone: "bad" },
  stopped: { label: "Stopped", tone: "neutral" },
});

export const ROUTE_ROLE_OPTIONS = Object.freeze(["planner", "executor", "verifier"]);

export const MODEL_PROVIDER_OPTIONS = Object.freeze([
  { value: "openai-codex", label: "OpenAI Codex" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "minimax", label: "MiniMax" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "opencode-go", label: "OpenCodeGo" },
]);

export const MODEL_EFFORT_OPTIONS = Object.freeze([
  { value: "default", label: "Default" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "xhigh", label: "X High" },
]);

export const EXECUTION_TARGET_OPTIONS = Object.freeze([
  { value: "profile_default", label: "Profile Default" },
  { value: "workspace_root", label: "Workspace Root" },
  { value: "isolated_worktree", label: "Isolated Worktree" },
]);

export const PERMISSION_MODE_OPTIONS = Object.freeze([
  {
    value: "always_ask",
    label: "Always ask",
    tone: "warn",
    description: "Require approval before commands, writes, and external actions.",
  },
  {
    value: "workspace_safe",
    label: "Workspace safe",
    tone: "good",
    description: "Allow low-risk reads and writes inside the selected workspace.",
  },
  {
    value: "review_only",
    label: "Review only",
    tone: "neutral",
    description: "Inspect, plan, and propose changes without mutating files.",
  },
  {
    value: "autonomous_scoped",
    label: "Autonomous scoped",
    tone: "warn",
    description: "Allow broader autonomous work only inside an explicit folder scope.",
  },
]);

function list(value) {
  return Array.isArray(value) ? value : [];
}

function runtimeServiceMatch(service) {
  const haystack = `${service?.serviceId || ""} ${service?.label || ""} ${service?.category || ""}`.toLowerCase();
  return (
    haystack.includes("runtime") ||
    haystack.includes("openclaw") ||
    haystack.includes("hermes") ||
    haystack.includes("wsl") ||
    haystack.includes("uv") ||
    haystack.includes("image tools")
  );
}

export function deriveRuntimeOperations(serviceStudio = {}) {
  const managedServices = list(serviceStudio.services);
  const runtimeServices = managedServices.filter(runtimeServiceMatch);
  const updateServices = managedServices.filter(service => {
    const status = String(service?.status || "").toLowerCase();
    return Boolean(service?.updateAvailable) || status.includes("update");
  });
  const runtimeActions = runtimeServices.flatMap(service =>
    list(service?.actions).map(action => ({
      ...action,
      serviceId: service.serviceId,
      serviceLabel: service.label,
    })),
  );

  return {
    summary: serviceStudio.summary || {},
    services: runtimeServices,
    updates: updateServices,
    actions: runtimeActions,
    autoVerifyCount: runtimeActions.filter(action => action.autoRunVerify).length,
    updateActionCount: runtimeActions.filter(action =>
      String(action.actionId || action.label || "").toLowerCase().includes("update"),
    ).length,
  };
}

export function statusDefinition(status) {
  return AGENT_STATUS_DEFINITIONS[String(status || "").toLowerCase()] || AGENT_STATUS_DEFINITIONS.idle;
}
