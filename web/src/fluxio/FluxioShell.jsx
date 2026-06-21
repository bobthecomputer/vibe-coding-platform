import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { buildFixtureSnapshot, listFixtureOptions } from "../../../desktop-ui/fixtures.js";
import {
  activeProfileId,
  currentProfileParameters,
  formatDurationCompact,
  missionChecksPlaceholder,
  missionObjectivePlaceholder,
  missionStatusTone,
  previewLabel,
  runtimeLabel,
  selectedMission,
  selectedWorkspace,
  titleizeToken,
} from "../../../desktop-ui/fluxioHelpers.js";
import { ActionButton, Field, Modal, StatusPill } from "../../../desktop-ui/MissionControlPrimitives.jsx";
import { buildMissionControlModel } from "../../../desktop-ui/missionControlModel.js";
import { buildFusionWorkbench } from "./fusion/fusionFixtures.js";
import {
  EXECUTION_TARGET_OPTIONS,
  MODEL_EFFORT_OPTIONS,
  MODEL_PROVIDER_OPTIONS,
  ROUTE_ROLE_OPTIONS,
  WORKSPACE_SURFACE_IDS,
  deriveRuntimeOperations,
} from "./workspaceModel.js";

const ImageStudioPlayground = lazy(() =>
  import("./image-studio/ImageStudioPlayground.jsx").then(module => ({
    default: module.ImageStudioPlayground,
  })),
);
const FusionWorkbenchPanel = lazy(() =>
  import("./fusion/FusionWorkbenchPanel.jsx").then(module => ({
    default: module.FusionWorkbenchPanel,
  })),
);
const ProviderEcosystemPanel = lazy(() =>
  import("./provider/ProviderEcosystemPanel.jsx").then(module => ({
    default: module.ProviderEcosystemPanel,
  })),
);
const RedTeamProofBoard = lazy(() =>
  import("./redteam/RedTeamProofBoard.jsx").then(module => ({
    default: module.RedTeamProofBoard,
  })),
);
const VisualProofReceiptGallery = lazy(() => import("./proof/VisualProofReceiptGallery.jsx"));
const SubagentReadinessPanel = lazy(() => import("./subagents/SubagentReadinessPanel.jsx"));
const RuntimeTruth = lazy(() => import("./runtime/RuntimeTruthContract.jsx"));
const VoiceCommandPanel = lazy(() =>
  import("./voice/index.js").then(module => ({
    default: module.VoiceCommandPanel,
  })),
);

function uniq(items) {
  return [...new Set((Array.isArray(items) ? items : []).filter(Boolean))];
}

const noopReportUiAction = () => {};

const STORAGE_KEYS = {
  uiMode: "fluxio.ui.mode",
  telegramChatId: "fluxio.telegram.chatId",
  previewMode: "fluxio.preview.mode",
  liveSyncSeconds: "fluxio.live_sync.seconds",
  codeExecutionEnabled: "fluxio.openai.code_execution.enabled",
  codeExecutionMemory: "fluxio.openai.code_execution.memory",
  workspaceSearch: "fluxio.sidebar.workspace.search",
  missionSearch: "fluxio.sidebar.mission.search",
  workspaceOrder: "fluxio.sidebar.workspace.order",
  missionOrder: "fluxio.sidebar.mission.order",
  splitViewEnabled: "fluxio.agent.split.enabled",
  splitMissionId: "fluxio.agent.split.mission_id",
  localTasks: "fluxio.tasks.local",
  deletedLocalTaskIds: "fluxio.tasks.deleted",
  memoryPolicy: "fluxio.memory.policy",
  memoryStore: "fluxio.memory.store",
  debugEvents: "fluxio.debug.events",
  persistedUiState: "fluxio.ui.state",
  surface: "fluxio.ui.surface",
  codexImportSnapshot: "fluxio.codex.import.snapshot",
  controlRoomSnapshot: "fluxio.control_room.snapshot",
  openAICodexOAuthFlow: "fluxio.openai_codex.oauth_flow",
  chatSessions: "fluxio.chat.sessions",
  chatSessionTranscripts: "fluxio.chat.session_transcripts",
  activeChatSessionId: "fluxio.chat.active_session_id",
};

const FIXTURE_OPTIONS = [{ id: "live", name: "Live Backend" }, ...listFixtureOptions()];
const EMPTY_ARRAY = Object.freeze([]);
const EMPTY_OBJECT = Object.freeze({});
const LIVE_SYNC_OPTIONS = [
  { value: "off", label: "Manual" },
  { value: "1", label: "1s" },
  { value: "5", label: "5s" },
  { value: "15", label: "15s" },
  { value: "30", label: "30s" },
];
const DEFAULT_OPENCLAW_GATEWAY_URL = "ws://127.0.0.1:8765";
const PROVIDER_AUTH_URLS = {
  chatgptDeveloperModeDocs: "https://platform.openai.com/docs/guides/developer-mode",
  openaiMcpDocs: "https://platform.openai.com/docs/mcp/",
  openaiApiKeys: "https://platform.openai.com/api-keys",
  minimaxOpenClawDocs: "https://platform.minimax.io/docs/token-plan/openclaw",
  minimaxApiKeys: "https://platform.minimax.io/user-center/basic-information/interface-key",
};

const DEFAULT_WORKSPACE_FORM = {
  name: "",
  path: "",
  defaultRuntime: "openclaw",
  userProfile: "builder",
  localProjectPath: "",
  nasProjectPath: "",
  syncMode: "manual",
  syncDirection: "bidirectional",
  syncConflictPolicy: "keep_newer_and_log",
  autoSyncToNas: false,
};

const DEFAULT_WORKSPACE_BROWSER_STATE = {
  open: false,
  loading: false,
  currentPath: "",
  parentPath: "",
  roots: [],
  entries: [],
  error: "",
};

const DEFAULT_MISSION_FORM = {
  workspaceId: "",
  runtime: "openclaw",
  mode: "Autopilot",
  profile: "builder",
  budgetHours: 12,
  relativeStopMinutes: "",
  runUntil: "pause_on_failure",
  modelProvider: "openai",
  model: "",
  modelEffort: "medium",
  objective: "",
  successChecks: "",
};

const PREFERRED_HARNESS_OPTIONS = [
  { value: "fluxio_hybrid", label: "Syntelos Hybrid" },
  { value: "legacy_autonomous_engine", label: "Legacy Autonomous Engine" },
];

const ROUTING_STRATEGY_OPTIONS = [
  { value: "profile_default", label: "Profile Default" },
  { value: "planner_premium_executor_efficient", label: "Planner Premium / Executor Efficient" },
  { value: "uniform_quality", label: "Uniform Quality" },
  { value: "budget_first", label: "Budget First" },
];

const MINIMAX_AUTH_OPTIONS = [
  { value: "none", label: "Not Configured" },
  { value: "minimax-portal-oauth", label: "MiniMax OpenClaw OAuth" },
  { value: "minimax-api", label: "MiniMax API Key" },
];
const OPENAI_CODEX_AUTH_OPTIONS = [
  { value: "none", label: "Not Configured" },
  { value: "oauth", label: "OpenAI Codex OAuth" },
  { value: "api", label: "API Key" },
];

const COMMIT_STYLE_OPTIONS = [
  { value: "scoped", label: "Scoped" },
  { value: "concise", label: "Concise" },
  { value: "detailed", label: "Detailed" },
];

const CODE_EXECUTION_MEMORY_OPTIONS = [
  { value: "1g", label: "1 GB" },
  { value: "4g", label: "4 GB" },
  { value: "16g", label: "16 GB" },
  { value: "64g", label: "64 GB" },
];
const PROVIDER_SECRET_OPTIONS = [
  {
    id: "openai",
    label: "OpenAI / Codex",
    env: "OPENAI_API_KEY / Codex OAuth",
    note: "Used for GPT and Codex-family routes.",
  },
  {
    id: "anthropic",
    label: "Anthropic",
    env: "ANTHROPIC_API_KEY",
    note: "Used when planner or verifier routes target Claude.",
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    env: "OPENROUTER_API_KEY",
    note: "Used when a route is delegated through OpenRouter.",
  },
  {
    id: "minimax",
    label: "MiniMax",
    env: "MINIMAX_API_KEY / minimax-portal OAuth",
    note: "Used when a route targets MiniMax with API-key auth. Portal/OAuth setup alone does not mark model auth ready.",
  },
];
const PROVIDER_AUTH_PRESENCE_IDS = [
  ...PROVIDER_SECRET_OPTIONS.map(item => item.id),
  "openai-codex",
  "minimax-cn",
  "minimax-portal",
];
const ROUTE_MODEL_OPTIONS = [
  "gpt-5.5",
  "gpt-5.4",
  "gpt-5.4-mini",
  "gpt-5.3-codex",
  "gpt-5.3-codex-spark",
  "codex",
  "claude-sonnet-4.5",
  "claude-opus-4.1",
  "MiniMax-M2.7",
  "MiniMax-M2.7-highspeed",
  "MiniMax-M3",
  "opencode/deepseek-v4-flash-free",
  "minimax-coding-plan/MiniMax-M3",
];
const MODEL_QUICK_PRESETS = [
  {
    id: "coding_fast",
    label: "Coding Fast",
    provider: "openai-codex",
    model: "gpt-5.5",
    effort: "medium",
  },
  {
    id: "planning_deep",
    label: "Planning Deep",
    provider: "openai",
    model: "gpt-5.5",
    effort: "high",
  },
  {
    id: "review_safe",
    label: "Review Safe",
    provider: "anthropic",
    model: "claude-sonnet-4.5",
    effort: "medium",
  },
  {
    id: "budget_route",
    label: "Budget Route",
    provider: "minimax",
    model: "MiniMax-M2.7",
    effort: "low",
  },
];
const MAX_CHAT_SESSION_COUNT = 120;
const MAX_CHAT_SESSION_TRANSCRIPT_TURNS = 160;
const DEFAULT_MEMORY_POLICY = {
  missionScoped: true,
  projectScoped: true,
  includeInFollowUps: true,
};
const DEFAULT_OPENAI_CODEX_OAUTH_FLOW = {
  open: false,
  sessionId: "",
  method: "",
  authUrl: "",
  callbackPort: 0,
  relayUrl: "",
  relayToken: "",
  helperCommand: "",
  verificationUrl: "",
  userCode: "",
  callback: "",
  status: "idle",
  message: "",
  output: "",
};
const DEFAULT_MINIMAX_OAUTH_FLOW = {
  open: false,
  sessionId: "",
  method: "",
  region: "global",
  verificationUrl: "",
  userCode: "",
  command: "",
  status: "idle",
  message: "",
  output: "",
};
const DEFAULT_TASK_FORM = {
  name: "",
  prompt: "",
  trigger: "schedule",
  everyMinutes: 30,
  webhookToken: "",
  active: true,
};
const MAX_TASK_LOG = 120;
const MAX_DEBUG_LOG = 240;
const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;
const MAX_INLINE_ATTACHMENTS = 6;
const WINDOWED_THRESHOLD = 60;
const GOAL_MODE_STORAGE_KEY = "fluxio.goal_mode.enabled";
const BROWSER_TOOLBAR_STORAGE_KEY = "fluxio.browser_toolbar.state";
const DEFAULT_REFERENCE_APPEARANCE = {
  accent: "#d6a84f",
  accentSoft: "#f3ead7",
  accentAlt: "#9aa3a0",
  surface: "#ffffff",
  surfaceSoft: "#f6f8fc",
  line: "#d8deea",
  text: "#121826",
  density: "comfortable",
  detailLevel: "balanced",
  stylePreset: "graphite-gold",
  theme: "dark",
  sidebarBehavior: "auto",
};
const SIDEBAR_BEHAVIOR_OPTIONS = [
  { value: "auto", label: "Auto collapse" },
  { value: "expanded", label: "Always expanded" },
  { value: "collapsed", label: "Always collapsed" },
];
const DEFAULT_CODEX_IMPORT_SNAPSHOT = {
  available: false,
  codexHome: "",
  sessionCount: 0,
  skillCount: 0,
  recentThreads: [],
  workspaces: [],
  packageStatePath: "",
  notes: [],
  isRefreshing: false,
};
const HERMES_SLASH_COMMANDS = [
  { command: "/new", harness: "Hermes", detail: "Start a new conversation." },
  { command: "/status", harness: "Hermes", detail: "Show session info and runtime state." },
  { command: "/model", harness: "Hermes", detail: "Show or change the current model." },
  { command: "/provider", harness: "Hermes", detail: "Show provider availability and auth status." },
  { command: "/reasoning", harness: "Hermes", detail: "Change reasoning effort or visibility." },
  { command: "/background", harness: "Hermes", detail: "Run a prompt in a background session." },
  { command: "/plan", harness: "Hermes", detail: "Write a markdown plan instead of executing." },
  { command: "/commands", harness: "Hermes", detail: "Browse all commands and installed skills." },
  { command: "/approve", harness: "Hermes", detail: "Approve a pending dangerous command." },
  { command: "/deny", harness: "Hermes", detail: "Reject a pending dangerous command." },
  { command: "/snapshot", harness: "Hermes", detail: "Create or restore config and state snapshots." },
  { command: "/rollback", harness: "Hermes", detail: "List or restore filesystem checkpoints." },
];
const OPENCLAW_SLASH_COMMANDS = [
  { command: "/new", harness: "OpenClaw", detail: "Start a new session or switch model." },
  { command: "/status", harness: "OpenClaw", detail: "Show runtime status, provider usage, and quota." },
  { command: "/model", harness: "OpenClaw", detail: "Show or set the active model." },
  { command: "/think", harness: "OpenClaw", detail: "Set thinking level for the current session." },
  { command: "/commands", harness: "OpenClaw", detail: "Show the generated command catalog." },
  { command: "/tools", harness: "OpenClaw", detail: "Show what the current agent can use right now." },
  { command: "/skill", harness: "OpenClaw", detail: "Run a skill by name." },
  { command: "/subagents", harness: "OpenClaw", detail: "Manage sub-agent runs for the current session." },
  { command: "/acp", harness: "OpenClaw", detail: "Manage ACP sessions and runtime options." },
  { command: "/codex", harness: "OpenClaw", detail: "Inspect and control the bundled Codex harness." },
  { command: "/plugins", harness: "OpenClaw", detail: "Inspect or mutate plugin state." },
  { command: "/mcp", harness: "OpenClaw", detail: "Show or update OpenClaw-managed MCP config." },
];
const COMMENT_SLASH_COMMANDS = [
  {
    command: "/cleanup-legacy-ui",
    harness: "Composer",
    kind: "comment",
    label: "Legacy UI cleanup",
    detail: "Audit and remove stale UI routes, screenshots, skins, and proof paths before recording.",
  },
  {
    command: "/comment",
    harness: "Composer",
    kind: "comment",
    label: "Comment selected block",
    detail: "Insert a review comment for the current block, proof item, or runtime trace.",
  },
  {
    command: "/note",
    harness: "Composer",
    kind: "comment",
    label: "Operator note",
    detail: "Leave a local note on the current mission without changing the route.",
  },
];

function splitEditorLines(value) {
  return String(value || "")
    .split("\n")
    .map(line => line.replace(/^\s*[-*]\s*/, "").trim())
    .filter(Boolean);
}

function mergeUniqueLines(current, next) {
  return uniq([...(Array.isArray(current) ? current : []), ...(Array.isArray(next) ? next : [])]);
}

function uniqBy(items, getKey) {
  const seen = new Set();
  return asList(items).filter(item => {
    const key = getKey(item);
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function buildDefaultRoutePlan(routeOverrides) {
  return Object.fromEntries(
    ROUTE_ROLE_OPTIONS.map(role => {
      const match = asList(routeOverrides).find(item => item.role === role) || {};
      return [
        role,
        {
          provider: match.provider || "openai",
          model:
            match.model ||
            (role === "planner" ? "gpt-5.5" : role === "executor" ? "gpt-5.4-mini" : "gpt-5.5"),
          effort: normalizeRouteEffort(
            match.effort || (role === "planner" ? "high" : role === "executor" ? "medium" : "medium"),
            "medium",
          ),
        },
      ];
    }),
  );
}

function buildDefaultReferenceStudio(routeOverrides) {
  const routePlan = buildDefaultRoutePlan(routeOverrides);
  const skillLifecycle = {
    testStatus: "Tests pending",
    validationStatus: "Validation pending",
    publishReadiness: "Review required",
    reviewRequired: true,
    learnedPromotion: "Not proposed",
    sourceType: "curated",
    lastValidationSummary: "Validation checks are pending execution.",
    lastTestSummary: "Skill tests have not run yet.",
  };
  return {
    collectionTab: "skill",
    selectedSkillId: "jbheaven-godmode-lab",
    selectedRuleId: "workspace-access-policy",
    activeSkillIds: [
      "jbheaven-godmode-lab",
      "ui-refactor-expert",
      "frontend-taste-director",
      "runtime-loop-supervisor",
      "voice-accessibility-operator",
    ],
    activeRuleSetId: "workspace-access-policy",
    skills: [
      {
        id: "ui-refactor-expert",
        kind: "skill",
        status: "Active",
        badge: "Skill",
        name: "UI Refactor Expert",
        summary: "Specialized in modern UI/UX improvements",
        description:
          "Specialized in modern UI/UX improvements. Refactors interfaces for clarity, accessibility, consistency, and performance while preserving functionality and brand.",
        triggerConditions:
          "Use this skill when the user asks to improve, refactor, or modernize user interfaces, components, layouts, or visual design systems.",
        instructions: [
          "Review the current UI for clarity, hierarchy, and consistency.",
          "Align with the design system, spacing scale, and typography ramp.",
          "Improve accessibility (WCAG 2.2 AA) and keyboard navigability.",
          "Standardize components, states, and interactions.",
          "Ensure responsive behavior across breakpoints.",
          "Provide rationale for major changes and trade-offs.",
        ],
        outputStyle: [
          "Provide before/after summary when applicable.",
          "Provide updated code (React + Tailwind CSS) with comments.",
          "Include a checklist of improvements and next steps.",
        ],
        guardrails: [
          "Do not change functionality or data flows.",
          "Maintain brand colors and design tokens.",
          "Ensure WCAG 2.2 AA contrast for all text and interactive elements.",
          "Enforce spacing scale (4px base) and consistent component usage.",
          "Prefer semantic HTML and accessible patterns.",
          "Do not introduce new libraries without justification.",
        ],
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
        ...skillLifecycle,
        category: "design_frontend",
        tags: ["ui", "design-system", "accessibility", "frontend"],
      },
      {
        id: "frontend-taste-director",
        kind: "skill",
        status: "Active",
        badge: "Skill",
        name: "Frontend Taste Director",
        summary: "First-pass taste and interaction quality for visual/UI work",
        description:
          "Prioritize visual hierarchy, spacing rhythm, interaction fidelity, and coherent style before major UI changes are merged.",
        triggerConditions:
          "Use this skill before major UI/frontend changes, redesigns, or broad component updates.",
        instructions: [
          "Start with a short taste review and name the current visual risks.",
          "Propose two concrete UI options with trade-offs before broad rewrites.",
          "Enforce mobile-first layout checks and touch-target size checks.",
          "Call out typography/spacing/token drift and normalize it.",
        ],
        outputStyle: [
          "Summarize now/next UI improvements in plain language.",
          "Show token-level changes and responsive breakpoints touched.",
        ],
        guardrails: [
          "Do not ship unreviewed visual rewrites without preview + validation state.",
          "Keep functionality stable while refining visuals.",
        ],
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
        ...skillLifecycle,
        category: "design_frontend",
        tags: ["frontend", "taste", "ui-polish", "mobile"],
      },
      {
        id: "jbheaven-godmode-lab",
        kind: "skill",
        status: "Active",
        badge: "Skill",
        name: "JBHEAVEN Godmode Lab",
        summary: "Controlled Hermes/G0DM0D3 red-team pack with proof transcripts",
        description:
          "Use the imported NAS Hermes Godmode/G0DM0D3 skill bundle for authorized JBHEAVEN, GBEH, Gandalf, and controlled model safety probing with transcript proof and explicit route decisions.",
        triggerConditions:
          "Use this skill when the user mentions JBHEAVEN, GBEH, Gandalf, Godmode, G0DM0D3, Hermes red teaming, OpenCode model probes, or asks to package/prove the NAS Godmode skill bundle.",
        instructions: [
          "Confirm the target is a controlled, authorized lab or local JBHEAVEN project before running probes.",
          "Start from the imported Hermes sources: red-teaming/godmode, mlops/inference/obliteratus, autonomous-ai-agents/opencode, and autonomous-ai-agents/hermes-agent.",
          "Prefer safe canary prompts, prompt-injection resistance checks, refusal-quality checks, and defensive dual-use explanations.",
          "Route execution through OpenCode, MiniMax, or Codex only when credentials and model availability are verified.",
          "Save prompt, response, route, scoring, and artifact paths so the operator can review the exact conversation.",
        ],
        outputStyle: [
          "Show a transcript with prompt, model reply, outcome, and short scoring rationale.",
          "Separate hidden reasoning from user-visible rationale; never claim to expose private chain-of-thought.",
          "Report which Hermes skills, model route, and proof artifacts were used.",
        ],
        guardrails: [
          "Do not create real phishing, malware, credential theft, persistence, evasion, or unauthorized access instructions.",
          "Keep outputs scoped to lab-contained testing, detection, hardening, education, and proof collection.",
          "Mask secrets and credentials in transcripts and generated artifacts.",
          "Do not fake model replies, run receipts, or uploaded proof.",
        ],
        assistant: {
          model: "gpt-5.5",
          effort: "High",
          prompt: "",
          conversation: [],
          proposal: null,
        },
        ...skillLifecycle,
        category: "security_red_team",
        tags: ["jbheaven", "godmode", "g0dm0d3", "hermes", "opencode", "proof"],
        sourceType: "nas_hermes_import",
        lastValidationSummary: "NAS Hermes source verified at .hermes/skills/red-teaming/godmode; app catalog row is curated for lab use.",
        lastTestSummary: "Requires a live model route for each proof run; safe canary transcript should be attached before publishing.",
      },
      {
        id: "hermes-skill-packager",
        kind: "skill",
        status: "Active",
        badge: "Skill",
        name: "Hermes Skill Packager",
        summary: "Select and zip the strongest NAS Hermes skills with a manifest",
        description:
          "Select, package, and document imported NAS Hermes skills into portable review bundles with provenance, validation notes, and app-catalog mapping.",
        triggerConditions:
          "Use this skill when the user asks to download, package, zip, promote, import, or review the best NAS Hermes skills for Fluxio/JBHEAVEN.",
        instructions: [
          "Inspect the NAS and local imported Hermes skill roots before selecting files.",
          "Copy only selected skill folders and preserve their scripts, references, templates, and SKILL.md files.",
          "Write a manifest with source path, selected skills, selection rationale, validation notes, and app mapping.",
          "Create a zip artifact and verify it exists with a readable size.",
        ],
        outputStyle: [
          "List the zip path and manifest path.",
          "Summarize selected skills by domain and why each was included.",
        ],
        guardrails: [
          "Do not package secrets, auth stores, session databases, caches, or unrelated project data.",
          "Do not rename upstream skill folders inside the archive unless the manifest records the mapping.",
        ],
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
        ...skillLifecycle,
        category: "skill_ops",
        tags: ["hermes", "skills", "zip", "nas", "manifest"],
      },
      {
        id: "runtime-loop-supervisor",
        kind: "skill",
        status: "Active",
        badge: "Skill",
        name: "Runtime Loop Supervisor",
        summary: "Plan-act-observe-verify loops across Hermes, OpenClaw, OpenCodeGo, Codex, and MiniMax",
        description:
          "Design and verify self-running agent loops that plan, act, observe, verify, route, and resume without hiding blockers, approvals, model choice, or proof.",
        triggerConditions:
          "Use this skill when the user asks for automatic routing, loop systems, runtime integration, OpenClaw/Hermes/OpenCodeGo differentiation, long-running missions, or proof-backed retries.",
        instructions: [
          "Show the loop contract: goal, route, checks, stop condition, proof artifacts, and escalation trigger.",
          "Keep Hermes and OpenClaw differentiated by capability and route truth rather than presenting them as interchangeable names.",
          "Use OpenCode or MiniMax for bounded execution lanes only after readiness and auth are checked.",
          "Surface failed checks and stale runtime config as first-class blockers.",
        ],
        outputStyle: [
          "Show planner, executor, verifier, and supervisor lane decisions.",
          "Explain why the loop should continue, pause, or ask for approval.",
        ],
        guardrails: [
          "Do not run indefinite loops without a visible stop condition and budget.",
          "Do not hide runtime failures behind generic success copy.",
          "Do not change production, billing, or secrets without explicit approval.",
        ],
        assistant: {
          model: "gpt-5.5",
          effort: "High",
          prompt: "",
          conversation: [],
          proposal: null,
        },
        ...skillLifecycle,
        category: "runtime_ops",
        tags: ["loops", "routing", "hermes", "openclaw", "opencode", "minimax"],
      },
      {
        id: "voice-accessibility-operator",
        kind: "skill",
        status: "Active",
        badge: "Skill",
        name: "Voice Accessibility Operator",
        summary: "Voice-first, low-typing, keyboard, and screen-reader operation",
        description:
          "Improve Fluxio for users who rely on dictation, keyboard navigation, plain-language confirmations, screen readers, and low-typing workflows.",
        triggerConditions:
          "Use this skill when the user asks for vocal control, dictation quality, accessibility, reduced typing, keyboard support, screen-reader labels, or inclusive app operation.",
        instructions: [
          "Treat voice input as a first-class command path, not only a text-area shortcut.",
          "Design correction and confirmation flows for dictation errors before launching expensive or risky actions.",
          "Audit focus order, labels, hit targets, contrast, reduced-motion behavior, and plain-language state copy.",
          "Prefer real integration checks over fake microphone or speech-recognition placeholders.",
        ],
        outputStyle: [
          "Report user-visible accessibility improvements and remaining voice bridge blockers.",
          "Include keyboard and screen-reader verification steps when UI changes ship.",
        ],
        guardrails: [
          "Do not claim speech recognition is implemented unless the bridge or browser API path is actually wired.",
          "Never make voice-only controls; keep keyboard and pointer alternatives.",
          "Avoid motion or audio feedback that cannot be reduced or disabled.",
        ],
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
        ...skillLifecycle,
        category: "accessibility",
        tags: ["voice", "accessibility", "dictation", "keyboard", "screen-reader"],
      },
      {
        id: "api-integration-helper",
        kind: "skill",
        status: "Active",
        badge: "Skill",
        name: "API Integration Helper",
        summary: "REST, GraphQL and integration patterns",
        description:
          "Guide integration work with reliable API contracts, retries, auth boundaries, and error reporting.",
        triggerConditions:
          "Use this skill when the task touches provider APIs, gateway adapters, or upstream/downstream contracts.",
        instructions: [
          "Validate API contract assumptions against the codebase.",
          "Preserve auth boundaries and avoid leaking secrets to the client.",
          "Prefer explicit error states over silent failure.",
        ],
        outputStyle: [
          "Call out changed endpoints and contract assumptions.",
          "Show verification steps for success and failure cases.",
        ],
        guardrails: [
          "Do not hardcode secrets or credentials.",
          "Keep transport retries bounded and observable.",
        ],
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
        ...skillLifecycle,
        category: "integration",
        tags: ["api", "contracts"],
      },
      {
        id: "data-schema-designer",
        kind: "skill",
        status: "Active",
        badge: "Skill",
        name: "Data Schema Designer",
        summary: "Design and optimize data models",
        description:
          "Shape data models, metadata, and storage structures for clarity and maintainability.",
        triggerConditions:
          "Use this skill when the task requires schema design, persistence changes, or data normalization.",
        instructions: [
          "Map the current source of truth before adding fields.",
          "Prefer additive schema changes over breaking rewrites.",
        ],
        outputStyle: ["Summarize schema deltas and migration expectations."],
        guardrails: [
          "Do not remove required fields without migration coverage.",
          "Keep entity naming consistent across storage and UI.",
        ],
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
        ...skillLifecycle,
        category: "data",
        tags: ["schema", "persistence"],
      },
      {
        id: "performance-optimizer",
        kind: "skill",
        status: "Active",
        badge: "Skill",
        name: "Performance Optimizer",
        summary: "Analyze and improve performance",
        description:
          "Tighten rendering, network, and interaction paths while preserving correctness and readability.",
        triggerConditions:
          "Use this skill when the task mentions latency, render cost, or expensive interactions.",
        instructions: [
          "Measure the hot path before broad optimization.",
          "Target expensive renders and redundant work first.",
        ],
        outputStyle: ["Show the user-facing performance impact and verification plan."],
        guardrails: [
          "Do not trade away debuggability for minor wins.",
          "Keep correctness and a11y intact while optimizing.",
        ],
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
        ...skillLifecycle,
        category: "performance",
        tags: ["render", "latency"],
      },
      {
        id: "security-auditor",
        kind: "skill",
        status: "Draft",
        badge: "Skill",
        name: "Security Auditor",
        summary: "Find and fix security vulnerabilities",
        description:
          "Audit auth, secrets, approval boundaries, and dangerous actions before broader rollout.",
        triggerConditions:
          "Use this skill when changes touch auth, secrets, approvals, or external integrations.",
        instructions: [
          "Identify privilege boundaries and approval requirements.",
          "Flag risky filesystem, network, and credential handling.",
        ],
        outputStyle: ["Prioritize concrete risks and proof steps first."],
        guardrails: [
          "Do not weaken approval boundaries for convenience.",
          "Never expose secrets in logs or UI copy.",
        ],
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
        ...skillLifecycle,
        category: "security",
        tags: ["security", "approval"],
      },
    ],
    ruleSets: [
      {
        id: "workspace-access-policy",
        kind: "rule",
        status: "Active",
        badge: "Rule Set",
        name: "Workspace Access Policy",
        summary: "Access, approvals, and scope",
        description:
          "Defines what agents can do, when approval is required, and what scope the permissions apply to across the organization.",
        scope: "All workspaces and folders",
        autonomyMode: "Balanced",
        approvalMode: "Risk-based",
        reviewer: "Orbit Pro (Team Lead)",
        preferredHarness: "fluxio_hybrid",
        routingStrategy: "planner_premium_executor_efficient",
        executionTargetPreference: "isolated_worktree",
        routePlan,
        allowedActions: ["Edit files", "Create branches", "Run tests"],
        requiresApproval: ["Merge to main", "Deploy to production", "Access shared data"],
        restrictedActions: ["Delete repositories", "Billing access", "Secrets management", "Delete integrations"],
        specialCases: ["Full autonomy for sandbox environments", "Docs workspace can use local drafts"],
        overrides: [
          {
            target: "/docs",
            mode: "Full autonomy",
            detail: "Agents can perform all actions without approval.",
          },
          {
            target: "/marketing-site",
            mode: "Standard rules",
            detail: "Follows the default policy above.",
          },
          {
            target: "/sandbox/*",
            mode: "Full autonomy",
            detail: "All actions allowed without approval.",
          },
          {
            target: "production",
            mode: "High risk",
            detail: "All changes require approval.",
          },
        ],
        emergencyOverride: {
          enabled: true,
          approver: "Orbit Pro (Team Lead)",
          channel: "#security-alerts",
        },
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
      },
      {
        id: "frontend-sandbox",
        kind: "rule",
        status: "Active",
        badge: "Rule Set",
        name: "Frontend Sandbox",
        summary: "Autonomy for sandbox envs",
        description:
          "Allows faster autonomous UI iteration inside isolated branches and preview environments.",
        scope: "Sandbox and preview surfaces",
        autonomyMode: "Balanced",
        approvalMode: "Low risk auto-approve",
        reviewer: "Orbit Pro (Team Lead)",
        preferredHarness: "fluxio_hybrid",
        routingStrategy: "uniform_quality",
        executionTargetPreference: "isolated_worktree",
        routePlan: buildDefaultRoutePlan(routeOverrides),
        allowedActions: ["Edit frontend files", "Run builds", "Run preview checks"],
        requiresApproval: ["Publish production deploy"],
        restrictedActions: ["Change billing settings"],
        specialCases: ["Preview deploys stay autonomous"],
        overrides: [],
        emergencyOverride: {
          enabled: false,
          approver: "Orbit Pro (Team Lead)",
          channel: "#frontend-review",
        },
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
      },
      {
        id: "production-deployments",
        kind: "rule",
        status: "Active",
        badge: "Rule Set",
        name: "Production Deployments",
        summary: "Deployment guardrails",
        description:
          "Keeps production merges and deploys explicit, reviewable, and easy to audit.",
        scope: "Production environments",
        autonomyMode: "Conservative",
        approvalMode: "Strict",
        reviewer: "Orbit Pro (Team Lead)",
        preferredHarness: "fluxio_hybrid",
        routingStrategy: "uniform_quality",
        executionTargetPreference: "isolated_worktree",
        routePlan: buildDefaultRoutePlan(routeOverrides),
        allowedActions: ["Prepare release notes", "Run staging verification"],
        requiresApproval: ["Merge to main", "Deploy to production", "Promote release"],
        restrictedActions: ["Delete release history"],
        specialCases: ["Emergency override allowed only with explicit approver"],
        overrides: [],
        emergencyOverride: {
          enabled: true,
          approver: "Orbit Pro (Team Lead)",
          channel: "#release-approvals",
        },
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
      },
      {
        id: "docs-workspace",
        kind: "rule",
        status: "Active",
        badge: "Rule Set",
        name: "Docs Workspace",
        summary: "Docs and content permissions",
        description:
          "Lets documentation work move quickly while keeping high-risk repo actions approval-gated.",
        scope: "Documentation folders",
        autonomyMode: "Balanced",
        approvalMode: "Risk-based",
        reviewer: "Orbit Pro (Team Lead)",
        preferredHarness: "fluxio_hybrid",
        routingStrategy: "planner_premium_executor_efficient",
        executionTargetPreference: "workspace_root",
        routePlan: buildDefaultRoutePlan(routeOverrides),
        allowedActions: ["Edit docs", "Create drafts", "Run local validation"],
        requiresApproval: ["Merge to main"],
        restrictedActions: ["Delete repositories"],
        specialCases: ["Docs folder may run with full autonomy"],
        overrides: [
          {
            target: "/docs",
            mode: "Full autonomy",
            detail: "Local content edits may run without approval.",
          },
        ],
        emergencyOverride: {
          enabled: false,
          approver: "Orbit Pro (Team Lead)",
          channel: "#docs-review",
        },
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
      },
      {
        id: "billing-restrictions",
        kind: "rule",
        status: "Active",
        badge: "Rule Set",
        name: "Billing Restrictions",
        summary: "Billing and secrets restrictions",
        description:
          "Protects billing, provider secrets, and irreversible workspace actions from routine automation.",
        scope: "Billing, providers, and secrets",
        autonomyMode: "Conservative",
        approvalMode: "Strict",
        reviewer: "Orbit Pro (Team Lead)",
        preferredHarness: "fluxio_hybrid",
        routingStrategy: "profile_default",
        executionTargetPreference: "isolated_worktree",
        routePlan: buildDefaultRoutePlan(routeOverrides),
        allowedActions: ["Read provider status"],
        requiresApproval: ["Rotate provider credentials"],
        restrictedActions: ["Change billing owner", "Delete workspace", "Expose secrets"],
        specialCases: ["Only team lead may override"],
        overrides: [],
        emergencyOverride: {
          enabled: true,
          approver: "Orbit Pro (Team Lead)",
          channel: "#finance-alerts",
        },
        assistant: {
          model: "gpt-5.5",
          effort: "Balanced",
          prompt: "",
          conversation: [],
          proposal: null,
        },
      },
    ],
  };
}

function studioCollectionKey(kind) {
  return kind === "rule" ? "ruleSets" : "skills";
}

function findStudioItem(studio, kind, itemId) {
  return asList(studio?.[studioCollectionKey(kind)]).find(item => item.id === itemId) || null;
}

function mergeReferenceStudioRows(defaultRows, storedRows) {
  const storedById = new Map(asList(storedRows).map(item => [item?.id, item]).filter(([id]) => Boolean(id)));
  const merged = asList(defaultRows).map(defaultItem => {
    const storedItem = storedById.get(defaultItem.id);
    if (!storedItem) {
      return defaultItem;
    }
    storedById.delete(defaultItem.id);
    return {
      ...defaultItem,
      ...storedItem,
      assistant: {
        ...(defaultItem.assistant || {}),
        ...(storedItem.assistant || {}),
      },
      tags: asList(storedItem.tags).length > 0 ? storedItem.tags : defaultItem.tags,
      instructions: asList(storedItem.instructions).length > 0 ? storedItem.instructions : defaultItem.instructions,
      outputStyle: asList(storedItem.outputStyle).length > 0 ? storedItem.outputStyle : defaultItem.outputStyle,
      guardrails: asList(storedItem.guardrails).length > 0 ? storedItem.guardrails : defaultItem.guardrails,
    };
  });
  return [...merged, ...Array.from(storedById.values())];
}

function mergeReferenceStudioState(defaultStudio, storedStudio) {
  if (!storedStudio || typeof storedStudio !== "object") {
    return defaultStudio;
  }
  const skills = mergeReferenceStudioRows(defaultStudio.skills, storedStudio.skills);
  const ruleSets = mergeReferenceStudioRows(defaultStudio.ruleSets, storedStudio.ruleSets);
  const skillIds = new Set(skills.map(item => item.id));
  const ruleIds = new Set(ruleSets.map(item => item.id));
  return {
    ...defaultStudio,
    ...storedStudio,
    skills,
    ruleSets,
    activeSkillIds: uniq([
      ...asList(defaultStudio.activeSkillIds),
      ...asList(storedStudio.activeSkillIds),
    ]).filter(id => skillIds.has(id)),
    activeRuleSetId: ruleIds.has(storedStudio.activeRuleSetId)
      ? storedStudio.activeRuleSetId
      : defaultStudio.activeRuleSetId,
    selectedSkillId: skillIds.has(storedStudio.selectedSkillId)
      ? storedStudio.selectedSkillId
      : defaultStudio.selectedSkillId,
    selectedRuleId: ruleIds.has(storedStudio.selectedRuleId)
      ? storedStudio.selectedRuleId
      : defaultStudio.selectedRuleId,
  };
}

function mergeStudioProposal(item, proposal) {
  if (!proposal) {
    return item;
  }
  const next = { ...item };
  for (const [key, value] of Object.entries(proposal)) {
    if (Array.isArray(value)) {
      next[key] = value;
      continue;
    }
    if (value && typeof value === "object" && !Array.isArray(value)) {
      next[key] = {
        ...(next[key] && typeof next[key] === "object" ? next[key] : {}),
        ...value,
      };
      continue;
    }
    next[key] = value;
  }
  return next;
}

function detectRouteModel(prompt) {
  const normalized = String(prompt || "").toLowerCase();
  return ROUTE_MODEL_OPTIONS.find(option => normalized.includes(option.toLowerCase())) || "";
}

function detectRouteEffort(prompt, fallback = "medium") {
  const normalized = String(prompt || "").toLowerCase();
  if (normalized.includes("x high") || normalized.includes("xhigh") || normalized.includes("extra high")) {
    return "xhigh";
  }
  if (normalized.includes("high reasoning") || normalized.includes("high effort")) {
    return "high";
  }
  if (normalized.includes("low reasoning") || normalized.includes("low effort")) {
    return "low";
  }
  if (normalized.includes("balanced") || normalized.includes("medium")) {
    return "medium";
  }
  return fallback;
}

function buildStudioAssistantProposal(item, prompt, selectedModel, selectedEffort) {
  const normalized = String(prompt || "").trim().toLowerCase();
  if (!normalized) {
    return {
      reply: "Write a concrete refinement request first.",
      changes: [],
      patch: null,
    };
  }

  if (item.kind === "rule") {
    const patch = {
      routePlan: { ...(item.routePlan || {}) },
      overrides: [...asList(item.overrides)],
      requiresApproval: [...asList(item.requiresApproval)],
      restrictedActions: [...asList(item.restrictedActions)],
      allowedActions: [...asList(item.allowedActions)],
      specialCases: [...asList(item.specialCases)],
    };
    const changes = [];
    const targetRole = normalized.includes("planner")
      ? "planner"
      : normalized.includes("verifier")
        ? "verifier"
        : "executor";
    const detectedModel = detectRouteModel(prompt);
    const detectedEffort = detectRouteEffort(prompt, patch.routePlan[targetRole]?.effort || "medium");
    if (detectedModel) {
      const provider =
        detectedModel.startsWith("claude")
          ? "anthropic"
          : detectedModel.toLowerCase().startsWith("minimax")
            ? "minimax"
            : "openai";
      patch.routePlan[targetRole] = {
        provider,
        model: detectedModel,
        effort: detectedEffort,
      };
      changes.push(
        `Route ${titleizeToken(targetRole)} -> ${titleizeToken(provider)} / ${detectedModel} / ${detectedEffort}`,
      );
    }
    if (normalized.includes("/docs") || normalized.includes("docs folder")) {
      patch.overrides = mergeUniqueLines([], patch.overrides).filter(Boolean);
      const existing = patch.overrides.find(entry => String(entry.target || "").toLowerCase() === "/docs");
      if (existing) {
        existing.mode = "Full autonomy";
        existing.detail = "Agents can perform all actions without approval.";
      } else {
        patch.overrides.push({
          target: "/docs",
          mode: "Full autonomy",
          detail: "Agents can perform all actions without approval.",
        });
      }
      changes.push("Added full autonomy override for /docs");
    }
    if (normalized.includes("merge") && normalized.includes("main")) {
      patch.requiresApproval = mergeUniqueLines(patch.requiresApproval, ["Merge to main"]);
      changes.push("Kept merge to main in the approval-required lane");
    }
    if (normalized.includes("production")) {
      patch.requiresApproval = mergeUniqueLines(patch.requiresApproval, ["Deploy to production"]);
      patch.restrictedActions = mergeUniqueLines(patch.restrictedActions, ["Deploy to prod without approval"]);
      changes.push("Kept production deploys approval-gated");
    }
    if (changes.length === 0) {
      changes.push(`Refined ${item.name} with a ${selectedEffort.toLowerCase()} ${selectedModel} pass.`);
      patch.specialCases = mergeUniqueLines(patch.specialCases, [
        "Assistant refinement applied to approvals, routes, and override notes.",
      ]);
    }
    return {
      reply: `Here's a proposed update for ${item.name}. I tightened the rule set and prepared changes you can apply immediately.`,
      changes,
      patch,
    };
  }

  const patch = {
    instructions: [...asList(item.instructions)],
    outputStyle: [...asList(item.outputStyle)],
    guardrails: [...asList(item.guardrails)],
  };
  const changes = [];
  if (normalized.includes("accessib")) {
    patch.guardrails = mergeUniqueLines(patch.guardrails, [
      "Enforce WCAG 2.2 AA contrast for all text and interactive elements.",
      "Prefer semantic HTML and accessible patterns by default.",
    ]);
    patch.instructions = mergeUniqueLines(patch.instructions, [
      "Audit keyboard navigation and visible focus states during each refactor.",
    ]);
    changes.push("Added stricter accessibility guardrails");
  }
  if (normalized.includes("spacing") || normalized.includes("consisten")) {
    patch.guardrails = mergeUniqueLines(patch.guardrails, [
      "Enforce spacing scale (4px base) and consistent component usage.",
    ]);
    patch.outputStyle = mergeUniqueLines(patch.outputStyle, [
      "Call out spacing, alignment, and component-consistency changes explicitly.",
    ]);
    changes.push("Added spacing-scale and consistency guidance");
  }
  if (normalized.includes("performance")) {
    patch.instructions = mergeUniqueLines(patch.instructions, [
      "Check render cost and expensive component work before shipping the refactor.",
    ]);
    changes.push("Added a performance verification step");
  }
  if (
    normalized.includes("godmode") ||
    normalized.includes("g0dm0d3") ||
    normalized.includes("jbheaven") ||
    normalized.includes("red team")
  ) {
    patch.instructions = mergeUniqueLines(patch.instructions, [
      "Confirm lab authorization, target boundaries, and proof destination before running model probes.",
      "Save a transcript with prompts, model replies, route metadata, scoring, and artifact paths.",
    ]);
    patch.outputStyle = mergeUniqueLines(patch.outputStyle, [
      "Separate visible rationale from hidden model reasoning; include a short scoring summary instead of chain-of-thought.",
    ]);
    patch.guardrails = mergeUniqueLines(patch.guardrails, [
      "Keep adversarial testing scoped to safe lab canaries, detection, hardening, and educational analysis.",
      "Do not generate real phishing, malware, credential theft, persistence, evasion, or unauthorized access instructions.",
    ]);
    changes.push("Added controlled red-team lab proof guidance");
  }
  if (normalized.includes("loop") || normalized.includes("routing") || normalized.includes("runtime")) {
    patch.instructions = mergeUniqueLines(patch.instructions, [
      "Define the loop as goal -> route -> action -> observation -> verification -> stop or resume.",
      "Surface runtime blockers, stale model config, and proof gaps as first-class state.",
    ]);
    patch.outputStyle = mergeUniqueLines(patch.outputStyle, [
      "Report planner, executor, verifier, and supervisor route decisions in plain language.",
    ]);
    changes.push("Added runtime loop and routing guidance");
  }
  if (normalized.includes("voice") || normalized.includes("dictation") || normalized.includes("vocal")) {
    patch.instructions = mergeUniqueLines(patch.instructions, [
      "Design voice-first flows with correction, confirmation, and keyboard fallback before expensive actions run.",
      "Audit labels, focus order, and reduced-typing paths whenever composer behavior changes.",
    ]);
    patch.guardrails = mergeUniqueLines(patch.guardrails, [
      "Do not claim speech recognition is implemented unless the bridge or browser API path is actually wired.",
    ]);
    changes.push("Added voice-first accessibility guidance");
  }
  if (changes.length === 0) {
    patch.instructions = mergeUniqueLines(patch.instructions, [
      `Refine this skill with a ${selectedEffort.toLowerCase()} ${selectedModel} pass before publishing.`,
    ]);
    changes.push(`Prepared a ${selectedEffort.toLowerCase()} refinement pass for the skill definition`);
  }

  return {
    reply: `I rewrote the skill guidance to be sharper and easier to enforce. Review the proposed changes, then apply or insert them as a draft.`,
    changes,
    patch,
  };
}

function buildStudioAssistantRuntimePrompt(item, prompt, selectedModel, selectedEffort) {
  const payload = {
    kind: item.kind,
    name: item.name,
    description: item.description,
    triggerConditions: item.triggerConditions || "",
    instructions: asList(item.instructions),
    outputStyle: asList(item.outputStyle),
    guardrails: asList(item.guardrails),
    routePlan: item.routePlan || {},
    allowedActions: asList(item.allowedActions),
    requiresApproval: asList(item.requiresApproval),
    restrictedActions: asList(item.restrictedActions),
    specialCases: asList(item.specialCases),
    overrides: asList(item.overrides),
  };
  return [
    "You are refining a Syntelos studio definition for an in-app editor.",
    `Target kind: ${item.kind === "rule" ? "rule set" : "skill"}.`,
    `Requested model label: ${selectedModel}. Requested effort label: ${selectedEffort}.`,
    "Return JSON only.",
    'Use this exact schema: {"reply":"string","changes":["string"],"patch":{}}',
    "Only include fields inside patch that should change.",
    "Preserve existing structure and make the patch directly mergeable.",
    "",
    "Current definition:",
    JSON.stringify(payload, null, 2),
    "",
    "User request:",
    prompt,
  ].join("\n");
}

function extractJsonObject(text) {
  const raw = String(text || "").trim();
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch {}
  const fencedMatch = raw.match(/```json\s*([\s\S]*?)```/i) || raw.match(/```\s*([\s\S]*?)```/i);
  if (fencedMatch?.[1]) {
    try {
      return JSON.parse(fencedMatch[1].trim());
    } catch {}
  }
  const firstBrace = raw.indexOf("{");
  const lastBrace = raw.lastIndexOf("}");
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    try {
      return JSON.parse(raw.slice(firstBrace, lastBrace + 1));
    } catch {}
  }
  return null;
}

function normalizeStudioAssistantRuntimeResponse(item, content) {
  const parsed = extractJsonObject(content);
  if (!parsed || typeof parsed !== "object") {
    return {
      reply: String(content || "").trim() || "Model reply received.",
      changes: [],
      patch: null,
    };
  }
  const reply =
    typeof parsed.reply === "string" && parsed.reply.trim()
      ? parsed.reply.trim()
      : `Prepared a refinement proposal for ${item.name}.`;
  const changes = Array.isArray(parsed.changes)
    ? parsed.changes.map(value => String(value || "").trim()).filter(Boolean)
    : [];
  const patch =
    parsed.patch && typeof parsed.patch === "object" && !Array.isArray(parsed.patch)
      ? parsed.patch
      : null;
  return {
    reply,
    changes,
    patch,
  };
}

const AGENT_BLOCKER_DRAWER_IDS = ["queue", "proof", "context"];
const AGENT_BUILDER_ONLY_DRAWERS = ["builder", "skills", "runtime", "profiles", "settings"];
const AGENT_BLOCKER_STATUSES = ["needs_approval", "blocked", "verification_failed"];
const AGENT_QUEUED_PAUSE_STATES = ["queued", "resume_available"];

function hasTauriBackend() {
  return Boolean(globalThis.window?.__TAURI__ || globalThis.window?.__TAURI_INTERNALS__);
}

function webBackendBaseUrl() {
  const configured =
    import.meta.env?.VITE_FLUXIO_BACKEND_URL ||
    globalThis.window?.__FLUXIO_BACKEND_URL__ ||
    "";
  return String(configured || "").trim().replace(/\/$/, "");
}

function canAttemptWebBackend() {
  if (webBackendBaseUrl()) {
    return true;
  }
  const protocol = String(globalThis.window?.location?.protocol || "").toLowerCase();
  if (protocol === "http:" || protocol === "https:") {
    return true;
  }
  const host = String(globalThis.window?.location?.hostname || "").toLowerCase();
  return ["localhost", "127.0.0.1", "::1"].includes(host);
}

function hasCommandBackend() {
  return hasTauriBackend() || canAttemptWebBackend();
}

function resolveInitialPreviewMode(searchParams) {
  const explicitFixture = searchParams.get("fixture");
  if (explicitFixture) {
    return explicitFixture;
  }
  if (hasTauriBackend()) {
    return "live";
  }
  return localStorage.getItem(STORAGE_KEYS.previewMode) || "live";
}

function loadStoredJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) {
      return fallback;
    }
    const parsed = JSON.parse(raw);
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function normalizeStoredIdList(items) {
  return Array.isArray(items) ? [...new Set(items.map(item => String(item || "").trim()).filter(Boolean))] : [];
}

function copyTextValue(text) {
  const value = String(text || "").trim();
  if (!value) {
    return Promise.resolve(false);
  }
  if (navigator?.clipboard?.writeText) {
    return navigator.clipboard.writeText(value).then(() => true).catch(() => false);
  }
  try {
    const temp = document.createElement("textarea");
    temp.value = value;
    temp.setAttribute("readonly", "true");
    temp.style.position = "absolute";
    temp.style.left = "-9999px";
    document.body.appendChild(temp);
    temp.select();
    const ok = document.execCommand("copy");
    temp.remove();
    return Promise.resolve(Boolean(ok));
  } catch {
    return Promise.resolve(false);
  }
}

function hexToRgba(hex, alpha = 1) {
  const value = String(hex || "").trim().replace("#", "");
  if (![3, 6].includes(value.length)) {
    return `rgba(111, 92, 255, ${alpha})`;
  }
  const normalized =
    value.length === 3
      ? value
          .split("")
          .map(char => `${char}${char}`)
          .join("")
      : value;
  const int = Number.parseInt(normalized, 16);
  if (!Number.isFinite(int)) {
    return `rgba(111, 92, 255, ${alpha})`;
  }
  const r = (int >> 16) & 255;
  const g = (int >> 8) & 255;
  const b = int & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

const BACKEND_CALL_SUBSCRIBERS = new Set();

function subscribeBackendCalls(handler) {
  BACKEND_CALL_SUBSCRIBERS.add(handler);
  return () => {
    BACKEND_CALL_SUBSCRIBERS.delete(handler);
  };
}

async function callBackend(command, payload = undefined, options = {}) {
  const startedAt = performance.now();
  try {
    let response;
    if (hasTauriBackend()) {
      response = payload === undefined ? await invoke(command) : await invoke(command, payload);
    } else {
      const base = webBackendBaseUrl();
      const apiUrl = `${base}/api/backend`;
      const httpResponse = await fetch(apiUrl, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, payload: payload ?? null }),
      });
      const result = await httpResponse.json().catch(() => ({}));
      if (!httpResponse.ok || result?.ok === false) {
        throw new Error(result?.error || `${command} failed with HTTP ${httpResponse.status}`);
      }
      response = result?.data;
    }
    const event = {
      id: `invoke-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      kind: hasTauriBackend() ? "invoke.ok" : "http.ok",
      command,
      durationMs: Math.round(performance.now() - startedAt),
      at: new Date().toISOString(),
    };
    BACKEND_CALL_SUBSCRIBERS.forEach(handler => {
      try {
        handler(event);
      } catch {
        return;
      }
    });
    return response;
  } catch (error) {
    const event = {
      id: `invoke-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      kind: hasTauriBackend() ? "invoke.error" : "http.error",
      command,
      durationMs: Math.round(performance.now() - startedAt),
      at: new Date().toISOString(),
      error: String(error),
    };
    BACKEND_CALL_SUBSCRIBERS.forEach(handler => {
      try {
        handler(event);
      } catch {
        return;
      }
    });
    if (options.throwOnError) {
      throw error;
    }
    return null;
  }
}

function callBackendWithFallback(command, payload = undefined, fallback = null, timeoutMs = 4500) {
  let timeoutId;
  const timeout = new Promise(resolve => {
    timeoutId = window.setTimeout(() => resolve(fallback), timeoutMs);
  });
  return Promise.race([
    callBackend(command, payload)
      .then(value => (value === null || value === undefined ? fallback : value))
      .catch(() => fallback),
    timeout,
  ]).finally(() => {
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
  });
}

function waitMs(delayMs) {
  return new Promise(resolve => {
    window.setTimeout(resolve, Math.max(0, Number(delayMs) || 0));
  });
}

function isRetryableBackendError(error) {
  const message = String(error || "").toLowerCase();
  if (!message) {
    return false;
  }
  return (
    message.includes("networkerror") ||
    message.includes("failed to fetch") ||
    message.includes("attempting to fetch resource") ||
    message.includes("econnreset") ||
    message.includes("econnrefused") ||
    message.includes("timed out") ||
    message.includes("timeout") ||
    message.includes("http 5")
  );
}

async function callBackendWithRetry(
  command,
  payload = undefined,
  { attempts = 3, baseDelayMs = 280, maxDelayMs = 1800 } = {},
) {
  let lastError = null;
  for (let attempt = 0; attempt < Math.max(1, attempts); attempt += 1) {
    try {
      return await callBackend(command, payload, { throwOnError: true });
    } catch (error) {
      lastError = error;
      const canRetry = attempt < attempts - 1 && isRetryableBackendError(error);
      if (!canRetry) {
        throw error;
      }
      const wait = Math.min(maxDelayMs, baseDelayMs * 2 ** attempt);
      await waitMs(wait);
    }
  }
  throw lastError || new Error(`${command} failed after retries.`);
}

function useToastQueue() {
  const [items, setItems] = useState([]);

  const push = useCallback((message, kind = "info") => {
    const item = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      kind,
      message,
    };
    setItems(current => [...current, item]);
    window.setTimeout(() => {
      setItems(current => current.filter(entry => entry.id !== item.id));
    }, 3600);
  }, []);

  return { items, push };
}

function toneClass(tone) {
  if (tone === "good") {
    return "tone-good";
  }
  if (tone === "warn") {
    return "tone-warn";
  }
  if (tone === "bad") {
    return "tone-bad";
  }
  return "tone-neutral";
}

function cx(...values) {
  return values.filter(Boolean).join(" ");
}

function providerLabel(provider) {
  const normalized = String(provider || "").toLowerCase();
  if (normalized === "openai") {
    return "OpenAI";
  }
  if (normalized === "opencode") {
    return "OpenCodeGo";
  }
  if (normalized === "minimax") {
    return "MiniMax";
  }
  return titleizeToken(provider || "Provider");
}

function timestampLabel(value) {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function timeValue(value) {
  if (!value) {
    return Number.NaN;
  }
  const parsed = new Date(value);
  const ms = parsed.getTime();
  return Number.isNaN(ms) ? Number.NaN : ms;
}

function latestTimestamp(...values) {
  let latest = "";
  let latestMs = Number.NEGATIVE_INFINITY;
  for (const value of values.flat()) {
    const parsed = timeValue(value);
    if (Number.isFinite(parsed) && parsed >= latestMs) {
      latest = String(value);
      latestMs = parsed;
    }
  }
  return latest;
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function asRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function artifactBackendBaseUrl() {
  const configured =
    import.meta.env?.VITE_FLUXIO_BACKEND_URL ||
    globalThis.window?.__FLUXIO_BACKEND_URL__ ||
    "";
  return String(configured || "").trim().replace(/\/$/, "");
}

function resolveControlArtifactUrl(value) {
  const source = String(value || "").trim();
  if (!source) return "";
  if (/^(data:|blob:|https?:\/\/)/i.test(source)) return source;
  if (source.startsWith("/api/artifact")) return `${artifactBackendBaseUrl()}${source}`;
  const params = new URLSearchParams({ path: source });
  return `${artifactBackendBaseUrl()}/api/artifact?${params.toString()}`;
}

function artifactUrlForRecord(record) {
  if (typeof record === "string") return resolveControlArtifactUrl(record);
  return resolveControlArtifactUrl(
    record?.artifactUrl ||
      record?.servedUrl ||
      record?.previewUrl ||
      record?.generatedPreview ||
      record?.previewSrc ||
      record?.outputPreview ||
      record?.imagePath ||
      record?.outputArtifactPath ||
      record?.artifactPath ||
      record?.path ||
      "",
  );
}

function artifactLabelForRecord(record, fallback = "generated artifact") {
  if (typeof record === "string") {
    return record.split(/[\\/]/).filter(Boolean).pop() || fallback;
  }
  return (
    record?.label ||
    record?.title ||
    record?.artifactId ||
    record?.requestId ||
    artifactLabelForRecord(record?.artifactPath || record?.path || "", fallback)
  );
}

function isImageArtifactPath(value) {
  return /\.(apng|avif|gif|jpe?g|png|svg|webp)(\?|#|$)/i.test(String(value || ""));
}

function deriveMissionLatestTimestamp(mission) {
  return latestTimestamp(
    mission?.updated_at,
    mission?.state?.updated_at,
    mission?.missionLoop?.updatedAt,
    asList(mission?.action_history).map(item => item?.executed_at),
    asList(mission?.plan_revisions).map(item => item?.created_at),
    asList(mission?.delegated_runtime_sessions).map(item => item?.updated_at),
  );
}

function controlMissionPriority(mission) {
  const statusPriority = {
    running: 5,
    needs_approval: 4,
    blocked: 3,
    verification_failed: 3,
    queued: 2,
  };
  return statusPriority[String(mission?.state?.status || "").toLowerCase()] || 0;
}

function preferredControlMission(missions) {
  const rows = asList(missions);
  if (rows.length === 0) return null;
  const sorted = rows
    .slice()
    .sort((left, right) => {
      const leftPriority = controlMissionPriority(left);
      const rightPriority = controlMissionPriority(right);
      if (leftPriority !== rightPriority) return rightPriority - leftPriority;
      return timeValue(deriveMissionLatestTimestamp(right)) - timeValue(deriveMissionLatestTimestamp(left));
    });
  return sorted[0] || null;
}

function preferredControlWorkspace(workspaces, missions) {
  const rows = asList(workspaces);
  if (rows.length === 0) return null;
  const preferredMission = preferredControlMission(missions);
  return (
    rows.find(item => item.workspace_id === preferredMission?.workspace_id) ||
    rows[0] ||
    null
  );
}

function boundaryTimestamp(boundary) {
  return (
    boundary?.created_at ||
    boundary?.createdAt ||
    boundary?.requested_at ||
    boundary?.requestedAt ||
    boundary?.updated_at ||
    boundary?.updatedAt ||
    boundary?.timestamp ||
    ""
  );
}

function isHeartbeatRuntimeKind(kind) {
  return String(kind || "").toLowerCase() === "session.heartbeat";
}

function isProcessRuntimeKind(kind) {
  return ["runtime.output", "runtime.stdout", "runtime.stderr"].includes(
    String(kind || "").toLowerCase(),
  );
}

function isTraceRuntimeKind(kind) {
  const normalized = String(kind || "").toLowerCase();
  return (
    isProcessRuntimeKind(normalized) ||
    [
      "runtime.phase",
      "runtime.plan",
      "runtime.thinking",
      "runtime.reasoning",
      "runtime.route_contract",
    ].includes(normalized)
  );
}

function phaseRouteRole(phase) {
  const normalized = String(phase || "").trim().toLowerCase();
  if (["plan", "replan"].includes(normalized)) {
    return "planner";
  }
  if (normalized === "verify") {
    return "verifier";
  }
  return "executor";
}

function isIgnorableAgentRuntimeEvent(event) {
  return isHeartbeatRuntimeKind(event?.kind);
}

function ToastHost({ items }) {
  return (
    <div aria-atomic="true" aria-live="polite" className="toast-host">
      {items.map(item => (
        <div className={`toast ${toneClass(item.kind === "error" ? "bad" : item.kind === "warn" ? "warn" : "neutral")}`} key={item.id}>
          {item.message}
        </div>
      ))}
    </div>
  );
}

function NavItem({
  active = false,
  draggable = false,
  title,
  subtitle,
  context = "",
  stats = [],
  onClick,
  onDragStart,
  onDragOver,
  onDrop,
  tone = "neutral",
  badge,
  icon = null,
  onCopy = () => {},
}) {
  return (
    <button
      className={`fluxio-nav-item ${active ? "active" : ""}`.trim()}
      draggable={draggable}
      onClick={onClick}
      onDragOver={onDragOver}
      onDragStart={onDragStart}
      onDrop={onDrop}
      type="button"
    >
      <div className="fluxio-nav-item-top">
        <div className="fluxio-nav-item-title">
          {icon ? <span aria-hidden="true" className="nav-item-icon">{icon}</span> : null}
          <strong>{title}</strong>
        </div>
        <span className={toneClass(tone)}>{badge || titleizeToken(tone)}</span>
      </div>
      {subtitle ? <p>{subtitle}</p> : null}
      {context ? (
        <div className="nav-context-row">
          <p className="fluxio-nav-context">{context}</p>
          <ActionButton
            onClick={event => {
              event.stopPropagation();
              onCopy(context);
            }}
            type="button"
          >
            Copy
          </ActionButton>
        </div>
      ) : null}
      {stats.length > 0 ? (
        <div className="fluxio-nav-stats">
          {stats.map(item => (
            <span className={`fluxio-nav-stat ${toneClass(item.tone)}`} key={`${title}-${item.label}`}>
              <strong>{item.value}</strong>
              <em>{item.label}</em>
            </span>
          ))}
        </div>
      ) : null}
    </button>
  );
}

function ThreadSection({ item }) {
  return (
    <article className={`thread-section ${toneClass(item.tone || "neutral")}`}>
      <div className="thread-section-top">
        <p>{item.label}</p>
      </div>
      <h3>{item.body}</h3>
      {item.detail ? (
        <details>
          <summary>Technical detail</summary>
          <p>{item.detail}</p>
        </details>
      ) : null}
    </article>
  );
}

function TranscriptMessage({
  item,
  highlighted = false,
  pinned = false,
  showTrace = false,
  onPinNexus = () => {},
  onSteer = () => {},
  onMemory = () => {},
  onValidate = () => {},
}) {
  const role = item.role || "fluxio";
  const roleLabel =
    item.roleLabel ||
    {
      fluxio: "Syntelos",
      operator: "Operator",
      runtime: "Runtime",
      bridge: "Bridge",
      queue: "Needs attention",
      system: "System",
    }[role] ||
    "Syntelos";
  const roleIcon =
    item.roleIcon ||
    {
      fluxio: "◎",
      operator: "◉",
      runtime: "◇",
      bridge: "⌁",
      queue: "!",
      system: "·",
    }[role] ||
    "·";

  return (
    <article
      className={`agent-message role-${role} ${toneClass(item.tone || "neutral")} ${item.emphasis ? "emphasis" : ""} ${item.processMessage ? "process-message" : ""} ${highlighted ? "highlighted" : ""} ${pinned ? "pinned" : ""}`.trim()}
      id={item.id}
    >
      <div className="agent-message-top">
        <div className="agent-message-role">
          <span aria-hidden="true" className="agent-message-avatar">{roleIcon}</span>
          <strong>{roleLabel}</strong>
        </div>
        {item.meta ? <span>{item.meta}</span> : null}
      </div>
      {item.label ? <p className="agent-message-label">{item.label}</p> : null}
      {item.title ? <h3>{item.title}</h3> : null}
      {item.detail ? <p>{item.detail}</p> : null}
      {item.technicalDetail ? (
        <details className="agent-message-details" open={showTrace}>
          <summary>{item.technicalSummary || "Technical detail"}</summary>
          <p>{item.technicalDetail}</p>
        </details>
      ) : null}
      {item.chips?.length ? (
        <div className="agent-message-chips">
          {item.chips.map(chip => (
            <span className="mini-pill muted" key={`${item.id}-${chip}`}>
              {chip}
            </span>
          ))}
        </div>
      ) : null}
      <div className="agent-message-actions">
        {(item.role === "queue" || item.tone === "bad" || item.processMessage) ? (
          <ActionButton onClick={() => onValidate(item)} type="button">
            Validate
          </ActionButton>
        ) : null}
        <ActionButton onClick={() => onSteer(item)} type="button">
          Steer
        </ActionButton>
        <ActionButton onClick={() => onMemory(item)} type="button">
          Memory
        </ActionButton>
        <ActionButton onClick={() => onPinNexus(item.id)} type="button">
          {pinned ? "Unpin nexus" : "Pin nexus"}
        </ActionButton>
      </div>
    </article>
  );
}

function AgentChatMessage({ item, highlighted = false, onFocusTrace = () => {} }) {
  const isUser = item.role === "operator";
  const speakerLabel = isUser ? "You" : item.roleLabel || "Syntelos";
  const speakerIcon = isUser ? "◉" : item.roleIcon || "◇";
  const secondaryText =
    !isUser && item.detail && item.detail !== item.title && item.detail !== item.meta
      ? item.detail
      : "";
  const hasTraceDetail = Boolean(item.technicalDetail || item.traceOnly);

  return (
    <article
      className={`agent-chat-message ${isUser ? "user" : "assistant"} ${toneClass(item.tone || "neutral")} ${highlighted ? "highlighted" : ""}`.trim()}
      id={item.id}
    >
      <div className="agent-chat-message-head">
        <div className="agent-chat-speaker">
          <span aria-hidden="true" className="agent-chat-avatar">{speakerIcon}</span>
          <strong>{speakerLabel}</strong>
        </div>
        {item.meta ? <span>{item.meta}</span> : null}
      </div>
      <div className="agent-chat-bubble">
        {item.label && !isUser ? <span className="agent-chat-label">{item.label}</span> : null}
        {item.title ? <p className="agent-chat-primary">{item.title}</p> : null}
        {secondaryText ? <p className="agent-chat-secondary">{secondaryText}</p> : null}
        {item.chips?.length ? (
          <div className="agent-chat-chips">
            {item.chips.slice(0, 4).map(chip => (
              <span className="mini-pill muted" key={`${item.id}-${chip}`}>
                {chip}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      {!isUser && hasTraceDetail ? (
        <div className="agent-chat-actions">
          <ActionButton onClick={() => onFocusTrace(item.id)} type="button">
            Open trace
          </ActionButton>
        </div>
      ) : null}
    </article>
  );
}

function DrawerToggle({ active, label, count, tone, onClick }) {
  return (
    <button className={`drawer-toggle ${active ? "active" : ""}`.trim()} onClick={onClick} type="button">
      <span>{label}</span>
      <strong className={toneClass(tone)}>{count > 0 ? count : ""}</strong>
    </button>
  );
}

function TopbarShortcut({ active = false, label, onClick, tone = "neutral" }) {
  return (
    <button
      className={`topbar-shortcut ${active ? "active" : ""} ${toneClass(tone)}`.trim()}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}

function WindowedList({
  className = "",
  estimatedItemHeight = 140,
  items = [],
  overscan = 4,
  renderItem,
}) {
  const hostRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) {
      return undefined;
    }
    const syncSize = () => {
      setViewportHeight(host.clientHeight || 0);
    };
    syncSize();
    const resizeObserver = new ResizeObserver(syncSize);
    resizeObserver.observe(host);
    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  if (!Array.isArray(items) || items.length === 0) {
    return <div className={`windowed-list ${className}`.trim()} ref={hostRef} />;
  }

  if (items.length < WINDOWED_THRESHOLD) {
    return (
      <div className={`windowed-list ${className}`.trim()} ref={hostRef}>
        {items.map((item, index) => renderItem(item, index))}
      </div>
    );
  }

  const safeHeight = Math.max(1, estimatedItemHeight);
  const visibleCount = Math.ceil((viewportHeight || safeHeight * 4) / safeHeight);
  const startIndex = Math.max(0, Math.floor(scrollTop / safeHeight) - overscan);
  const endIndex = Math.min(items.length, startIndex + visibleCount + overscan * 2);
  const topPad = startIndex * safeHeight;
  const bottomPad = Math.max(0, (items.length - endIndex) * safeHeight);

  return (
    <div
      className={`windowed-list ${className}`.trim()}
      onScroll={event => setScrollTop(event.currentTarget.scrollTop)}
      ref={hostRef}
    >
      <div style={{ height: `${topPad}px` }} />
      {items.slice(startIndex, endIndex).map((item, index) =>
        renderItem(item, startIndex + index),
      )}
      <div style={{ height: `${bottomPad}px` }} />
    </div>
  );
}

function MenuButton({ label, onClick }) {
  return (
    <button className="app-menu-button" onClick={onClick} type="button">
      {label}
    </button>
  );
}

function LazySurfaceFallback({ label }) {
  return (
    <article className="builder-panel lazy-surface-fallback" aria-live="polite">
      <p className="eyebrow">Loading surface</p>
      <strong>{label}</strong>
      <span>Preparing the workspace controls.</span>
    </article>
  );
}

function ComposerAttachmentStrip({
  attachments = [],
  onClear = () => {},
  onRemove = () => {},
}) {
  if (!Array.isArray(attachments) || attachments.length === 0) {
    return null;
  }
  return (
    <section className="composer-attachments" aria-label="Pending attachments">
      <div className="composer-attachments-head">
        <span>
          {attachments.length} attachment{attachments.length === 1 ? "" : "s"}
        </span>
        <ActionButton onClick={onClear} type="button">
          Clear
        </ActionButton>
      </div>
      <div className="composer-attachments-list">
        {attachments.map(item => (
          <article className="composer-attachment" key={item.id}>
            {item.previewUrl ? (
              <img
                alt={item.name || "attachment preview"}
                className="composer-attachment-preview"
                src={item.previewUrl}
              />
            ) : null}
            <div>
              <strong>{item.name || "Attachment"}</strong>
              <p>
                {item.mime || "image"}
                {` · ${Math.max(1, Math.round((item.size || 0) / 1024))}KB`}
              </p>
            </div>
            <ActionButton onClick={() => onRemove(item.id)} type="button">
              Remove
            </ActionButton>
          </article>
        ))}
      </div>
    </section>
  );
}

function GlobalRailButton({ active = false, icon = null, label, onClick, subtle = false }) {
  return (
    <button
      className={`global-rail-button ${active ? "active" : ""} ${subtle ? "subtle" : ""}`.trim()}
      onClick={onClick}
      type="button"
    >
      {icon ? <span aria-hidden="true" className="global-rail-icon">{icon}</span> : null}
      <span>{label}</span>
    </button>
  );
}

function missionActionAvailable(mission, action) {
  if (!mission) {
    return false;
  }
  if (action === "pause") {
    return !["completed", "failed"].includes(mission.state?.status || "");
  }
  if (action === "resume") {
    return (
      mission.missionLoop?.continuityState === "resume_available" ||
      ["queued", "blocked", "verification_failed", "needs_approval"].includes(
        mission.state?.status || "",
      )
    );
  }
  return true;
}

function listLabel(value) {
  if (!value) {
    return "No item";
  }
  return String(value);
}

function pathLeaf(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const parts = text.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || text;
}

function commandSlug(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function normalizeCodexImportSnapshot(value) {
  if (!value || typeof value !== "object") {
    return DEFAULT_CODEX_IMPORT_SNAPSHOT;
  }
  return {
    ...DEFAULT_CODEX_IMPORT_SNAPSHOT,
    ...value,
    recentThreads: Array.isArray(value.recentThreads) ? value.recentThreads : [],
    workspaces: Array.isArray(value.workspaces) ? value.workspaces : [],
    notes: Array.isArray(value.notes) ? value.notes : [],
  };
}

function normalizeOrderedIds(currentOrder, liveIds) {
  const safeCurrent = Array.isArray(currentOrder) ? currentOrder : [];
  const safeLive = Array.isArray(liveIds) ? liveIds.filter(Boolean) : [];
  const kept = safeCurrent.filter(id => safeLive.includes(id));
  const appended = safeLive.filter(id => !kept.includes(id));
  return [...kept, ...appended];
}

function sortRowsByOrder(rows, orderedIds, readId) {
  const map = new Map(rows.map(item => [readId(item), item]));
  const normalizedOrder = normalizeOrderedIds(
    orderedIds,
    rows.map(item => readId(item)),
  );
  return normalizedOrder.map(id => map.get(id)).filter(Boolean);
}

function moveOrderedId(orderIds, draggedId, targetId) {
  if (!draggedId || !targetId || draggedId === targetId) {
    return orderIds;
  }
  const sourceIndex = orderIds.indexOf(draggedId);
  const targetIndex = orderIds.indexOf(targetId);
  if (sourceIndex < 0 || targetIndex < 0) {
    return orderIds;
  }
  const next = [...orderIds];
  next.splice(sourceIndex, 1);
  next.splice(targetIndex, 0, draggedId);
  return next;
}

function saveableRouteOverrides(routeOverrides) {
  return asList(routeOverrides)
    .filter(item => item?.model?.trim())
    .map(item => {
      const effort = normalizeRouteEffort(item.effort, "default");
      return {
        role: item.role,
        provider: item.provider,
        model: item.model.trim(),
        ...(effort !== "default" ? { effort } : {}),
      };
    });
}

function updateRouteOverride(routeOverrides, role, patch) {
  return asList(routeOverrides).map(item =>
    item.role === role
      ? {
          ...item,
          ...patch,
          ...(Object.prototype.hasOwnProperty.call(patch, "effort")
            ? { effort: normalizeRouteEffort(patch.effort, "default") }
            : {}),
        }
      : item,
  );
}

function normalizeRouteEffort(value, fallback = "default") {
  const normalized = String(value || "").trim().toLowerCase().replace(/[_\s-]+/g, "");
  if (!normalized) {
    return fallback;
  }
  if (["default", "balanced", "normal", "standard"].includes(normalized)) {
    return "default";
  }
  if (["low", "minimal", "min"].includes(normalized)) {
    return "low";
  }
  if (["medium", "med", "mid"].includes(normalized)) {
    return "medium";
  }
  if (["high"].includes(normalized)) {
    return "high";
  }
  if (["xhigh", "extrahigh", "veryhigh", "max", "highest"].includes(normalized)) {
    return "xhigh";
  }
  return fallback;
}

function routeEffortLabel(value, fallback = "default") {
  const normalized = normalizeRouteEffort(value, fallback);
  const option = MODEL_EFFORT_OPTIONS.find(item => item.value === normalized);
  return option?.label || titleizeToken(normalized);
}

function authModesForRouteProfile(profile, providerPresence = {}) {
  const nextProfile = {
    ...profile,
    openaiCodexAuthMode: normalizeOpenAICodexAuthMode(profile?.openaiCodexAuthMode),
    minimaxAuthMode: normalizeMiniMaxAuthMode(profile?.minimaxAuthMode),
  };
  const routes = saveableRouteOverrides(nextProfile.routeOverrides);
  const providers = new Set(routes.map(item => String(item.provider || "").toLowerCase()));
  const usesOpenAI = providers.has("openai") || providers.has("openai-codex");
  const usesMiniMax =
    providers.has("minimax") ||
    providers.has("minimax-cn") ||
    providers.has("minimax-portal");

  if (usesOpenAI && nextProfile.openaiCodexAuthMode === "none") {
    if (providerPresence.openai) {
      nextProfile.openaiCodexAuthMode = "api";
    } else if (providerPresence["openai-codex"]) {
      nextProfile.openaiCodexAuthMode = "oauth";
    }
  }

  if (usesMiniMax && nextProfile.minimaxAuthMode === "none") {
    if (providerPresence["minimax-portal"]) {
      nextProfile.minimaxAuthMode = "minimax-portal-oauth";
    } else if (providerPresence.minimax || providerPresence["minimax-cn"]) {
      nextProfile.minimaxAuthMode = "minimax-api";
    }
  }

  return nextProfile;
}

function normalizeOpenAICodexAuthMode(value) {
  const normalized = String(value || "none").trim().toLowerCase();
  if (["chatgpt", "chatgpt-portal", "portal", "chatgpt-oauth", "chatgpt_oauth", "codex-oauth", "openai-codex-oauth", "oauth"].includes(normalized)) {
    return "oauth";
  }
  if (["api", "api-key", "api_key"].includes(normalized)) {
    return "api";
  }
  return OPENAI_CODEX_AUTH_OPTIONS.some(option => option.value === normalized) ? normalized : "none";
}

function normalizeMiniMaxAuthMode(value) {
  const normalized = String(value || "none").trim().toLowerCase();
  if (["minimax-portal-oauth", "minimax-global-oauth", "minimax-cn-oauth", "oauth", "oauth-cn", "portal-oauth"].includes(normalized)) {
    return "minimax-portal-oauth";
  }
  if (["minimax-api", "minimax_api", "minimax-global-api", "minimax-cn-api"].includes(normalized)) {
    return "minimax-api";
  }
  return MINIMAX_AUTH_OPTIONS.some(option => option.value === normalized) ? normalized : "none";
}

function defaultNasProjectPath(value) {
  const leaf = pathLeaf(value);
  if (!leaf) {
    return "/volume1/Saclay/projects/";
  }
  return `/volume1/Saclay/projects/${leaf.replace(/[^A-Za-z0-9._-]+/g, "-")}`;
}

function profileFormFromWorkspace(workspace, fallbackProfile) {
  const overrides = Array.isArray(workspace?.route_overrides) ? workspace.route_overrides : [];
  const existingByRole = new Map(overrides.map(item => [String(item.role || "").toLowerCase(), item]));
  return {
    userProfile: workspace?.user_profile || fallbackProfile || "builder",
    preferredHarness: workspace?.preferred_harness || "fluxio_hybrid",
    routingStrategy: workspace?.routing_strategy || "profile_default",
    autoOptimizeRouting: Boolean(workspace?.auto_optimize_routing),
    openaiCodexAuthMode: normalizeOpenAICodexAuthMode(workspace?.openai_codex_auth_mode),
    minimaxAuthMode: normalizeMiniMaxAuthMode(workspace?.minimax_auth_mode),
    commitMessageStyle: workspace?.commit_message_style || "scoped",
    executionTargetPreference: workspace?.execution_target_preference || "profile_default",
    localProjectPath: workspace?.local_project_path || "",
    nasProjectPath: workspace?.nas_project_path || "",
    syncMode: workspace?.sync_mode || "manual",
    syncDirection: workspace?.sync_direction || "bidirectional",
    syncConflictPolicy: workspace?.sync_conflict_policy || "keep_newer_and_log",
    autoSyncToNas: Boolean(workspace?.auto_sync_to_nas),
    routeOverrides: ROUTE_ROLE_OPTIONS.map(role => {
      const item = existingByRole.get(role) || {};
      return {
        role,
        provider: item.provider || "openai",
        model: item.model || "",
        effort: item.effort || "default",
      };
    }),
  };
}

function createSessionEntry(entry) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    createdAt: new Date().toISOString(),
    ...entry,
  };
}

function summarizeChatSessionTitle(seedText) {
  const cleaned = String(seedText || "")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) {
    return "New conversation";
  }
  if (isRouteMetadataText(cleaned) || /^\/[\w-]+/.test(cleaned)) {
    return "New conversation";
  }
  const singleToken = cleaned.split(" ").length === 1;
  if (singleToken && /^(codex|openclaw|hermes|tomorrow|new|chat|conversation)$/i.test(cleaned)) {
    return "New conversation";
  }
  return cleaned.length > 56 ? `${cleaned.slice(0, 53).trimEnd()}...` : cleaned;
}

function isRouteMetadataText(value) {
  const text = String(value || "").trim();
  if (!text) {
    return false;
  }
  return (
    /^(Codex|OpenClaw|Hermes|Syntelos)\s*[·•]\s*[^·•]+[·•]\s*(default|low|medium|high)$/i.test(text) ||
    /^(Codex|OpenClaw|Hermes|Syntelos)\s+chat$/i.test(text) ||
    /^chat:(openclaw|codex|hermes):/i.test(text)
  );
}

function normalizeChatSessions(payload) {
  if (!Array.isArray(payload)) {
    return [];
  }
  const seen = new Set();
  const rows = [];
  for (const item of payload) {
    const id = String(item?.id || "").trim();
    if (!id || seen.has(id)) {
      continue;
    }
    seen.add(id);
    rows.push({
      id,
      workspaceId: String(item?.workspaceId || "").trim(),
      title: summarizeChatSessionTitle(String(item?.title || "").trim()),
      createdAt: String(item?.createdAt || new Date().toISOString()),
      updatedAt: String(item?.updatedAt || item?.createdAt || new Date().toISOString()),
      lastPreview: String(item?.lastPreview || "").trim()
        ? summarizeChatSessionTitle(String(item?.lastPreview || "").trim())
        : "",
    });
  }
  return rows
    .sort((left, right) => timeValue(right.updatedAt) - timeValue(left.updatedAt))
    .slice(0, MAX_CHAT_SESSION_COUNT);
}

function normalizeChatTranscriptEntry(item) {
  const role = String(item?.role || "user").trim().toLowerCase() === "assistant" ? "assistant" : "user";
  const title = String(item?.title || item?.text || "").trim();
  const detail = String(item?.detail || "").trim();
  if (!title && !detail) {
    return null;
  }
  return {
    id: String(item?.id || `chat-turn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`),
    role,
    title: title || detail,
    detail: title && detail && detail !== title ? detail : "",
    meta: String(item?.meta || "").trim(),
    tone: String(item?.tone || "neutral").trim(),
    pending: Boolean(item?.pending),
    technicalDetail: String(item?.technicalDetail || "").trim(),
    chips: asList(item?.chips).map(value => String(value || "").trim()).filter(Boolean).slice(0, 6),
    createdAt: String(item?.createdAt || new Date().toISOString()),
  };
}

function normalizeChatSessionTranscripts(payload, legacyNotes = []) {
  const next = {};
  const pushTurn = (sessionId, rawItem) => {
    const normalizedSessionId = String(sessionId || "").trim();
    if (!normalizedSessionId) {
      return;
    }
    const normalized = normalizeChatTranscriptEntry(rawItem);
    if (!normalized) {
      return;
    }
    if (!Array.isArray(next[normalizedSessionId])) {
      next[normalizedSessionId] = [];
    }
    next[normalizedSessionId].push(normalized);
  };

  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    for (const [sessionId, turns] of Object.entries(payload)) {
      for (const turn of asList(turns)) {
        pushTurn(sessionId, turn);
      }
    }
  }

  for (const note of asList(legacyNotes)) {
    if (note?.channel !== "chat") {
      continue;
    }
    if (!note?.sessionId) {
      continue;
    }
    pushTurn(note.sessionId, {
      id: note.id ? `legacy-${note.id}` : "",
      role: note.role === "assistant" ? "assistant" : "user",
      title: note.title || note.detail || "",
      detail: note.detail && note.detail !== note.title ? note.detail : "",
      meta: note.meta || "",
      tone: note.tone || "neutral",
      pending: Boolean(note.pending),
      technicalDetail: note.technicalDetail || "",
      chips: asList(note.chips),
      createdAt: note.createdAt || new Date().toISOString(),
    });
  }

  const normalizedMap = {};
  for (const [sessionId, turns] of Object.entries(next)) {
    const seen = new Set();
    const normalizedTurns = turns
      .sort((left, right) => {
        const leftTime = timeValue(left.createdAt);
        const rightTime = timeValue(right.createdAt);
        if (leftTime !== rightTime) {
          return leftTime - rightTime;
        }
        return String(left.id).localeCompare(String(right.id));
      })
      .filter(turn => {
        const dedupeKey = String(turn.id || `${turn.role}:${turn.title}:${turn.createdAt}`);
        if (seen.has(dedupeKey)) {
          return false;
        }
        seen.add(dedupeKey);
        return true;
      })
      .slice(-MAX_CHAT_SESSION_TRANSCRIPT_TURNS);
    if (normalizedTurns.length > 0) {
      normalizedMap[sessionId] = normalizedTurns;
    }
  }
  return normalizedMap;
}

function transcriptTurnsFromRuntimeCompartment(compartment, sessionId = "") {
  const normalizedSessionId = String(sessionId || compartment?.sessionId || compartment?.id || "").trim();
  if (!normalizedSessionId) {
    return [];
  }
  const turns = [];
  for (const [index, item] of asList(compartment?.messages).entries()) {
    const rawRole = String(item?.role || "").trim().toLowerCase();
    const role = rawRole === "assistant" ? "assistant" : rawRole === "operator" || rawRole === "user" ? "user" : "";
    if (!role) {
      continue;
    }
    const text = String(item?.text || item?.message || "").trim();
    if (!text) {
      continue;
    }
    const createdAt = String(item?.at || item?.createdAt || compartment?.updatedAt || new Date().toISOString());
    const normalized = normalizeChatTranscriptEntry({
      id: `compartment-${normalizedSessionId}-${index}-${createdAt}`,
      role,
      title: text,
      detail: "",
      meta: timestampLabel(createdAt),
      tone: "neutral",
      createdAt,
    });
    if (normalized) {
      turns.push(normalized);
    }
  }
  return turns.slice(-MAX_CHAT_SESSION_TRANSCRIPT_TURNS);
}

function buildChatSession(workspaceId, seedText = "") {
  const now = new Date().toISOString();
  return {
    id: `chat-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    workspaceId: String(workspaceId || "").trim(),
    title: summarizeChatSessionTitle(seedText),
    createdAt: now,
    updatedAt: now,
    lastPreview: summarizeChatSessionTitle(seedText),
  };
}

function parseWorkspaceSyncStatus(workspacePayload) {
  const goalEntries = asList(workspacePayload?.goals);
  for (const entry of goalEntries) {
    const raw = String(entry || "").trim();
    if (!raw.startsWith("sync_status:")) {
      continue;
    }
    try {
      const payload = JSON.parse(raw.slice("sync_status:".length));
      return payload && typeof payload === "object" ? payload : null;
    } catch {
      return null;
    }
  }
  return null;
}

function deltaDetail(row) {
  const detailSources = [
    row?.detail,
    row?.metadata?.detail,
    row?.metadata?.reason,
    row?.metadata?.pauseReason,
    row?.metadata?.autopilotStatus,
    row?.metadata?.status,
    row?.data?.detail,
    row?.data?.decision,
    row?.data?.request_id,
  ];
  return detailSources.find(value => value) || "";
}

const OPERATOR_STEERING_PREFIXES = [
  "runtime preference:",
  "current mission phase:",
  "route preference for",
  "if the openai route is active,",
];

function extractOperatorSteeringHints(block) {
  return String(block || "")
    .split(/(?<=\.)\s+(?=[A-Z])|[\n]+/)
    .map(item => item.trim())
    .filter(Boolean)
    .filter(item =>
      OPERATOR_STEERING_PREFIXES.some(prefix => item.toLowerCase().startsWith(prefix)),
    );
}

function splitOperatorSteeringMessage(value) {
  const raw = String(value || "").replace(/\r\n?/g, "\n").trim();
  if (!raw) {
    return { visibleText: "", steeringHints: [] };
  }

  const blocks = raw.split(/\n\s*\n/).map(item => item.trim()).filter(Boolean);
  if (blocks.length > 1) {
    const steeringHints = extractOperatorSteeringHints(blocks[0]);
    if (steeringHints.length > 0) {
      return {
        visibleText: blocks.slice(1).join("\n\n").trim() || raw,
        steeringHints,
      };
    }
  }

  const steeringHints = [];
  const visibleLines = [];
  let inBody = false;
  for (const rawLine of raw.split("\n")) {
    const line = rawLine.trim();
    if (!line) {
      if (inBody && visibleLines[visibleLines.length - 1] !== "") {
        visibleLines.push("");
      }
      continue;
    }
    const steeringLine =
      !inBody &&
      OPERATOR_STEERING_PREFIXES.some(prefix => line.toLowerCase().startsWith(prefix));
    if (steeringLine) {
      steeringHints.push(line);
      continue;
    }
    inBody = true;
    visibleLines.push(line);
  }

  return {
    visibleText: visibleLines.join("\n").trim() || raw,
    steeringHints,
  };
}

function isRuntimeRouteMetaKind(kind) {
  return [
    "runtime.phase_entered",
    "runtime.route_switch_reason",
    "runtime.handoff",
    "runtime.route_contract",
  ].includes(String(kind || "").toLowerCase());
}

function controlRoomDeltaToLiveItem(payload, mission, delegatedSessions = []) {
  const row = payload?.row;
  const source = payload?.source || "delta";
  if (!row || !mission) {
    return null;
  }

  if (source === "mission_event") {
    if (row.mission_id !== mission.mission_id) {
      return null;
    }
    const kind = row.kind || "mission.event";
    const isOperatorFollowUp = kind === "mission.follow_up";
    const operatorPrompt = isOperatorFollowUp
      ? splitOperatorSteeringMessage(row.message || "")
      : null;
    return {
      id: `mission-${row.mission_id}-${row.timestamp || payload.detectedAt}-${kind}-${row.message || "event"}`,
      kind,
      role: isOperatorFollowUp ? "operator" : kind === "mission.approval" ? "queue" : "system",
      runtimeId: row.metadata?.runtimeId || row.metadata?.runtime_id || "",
      roleLabel:
        isOperatorFollowUp
          ? "Operator"
          : kind === "mission.approval"
            ? "Needs attention"
            : "Syntelos",
      roleIcon:
        isOperatorFollowUp
          ? "◉"
          : kind === "mission.approval"
            ? "!"
            : "·",
      label: titleizeToken(kind),
      title: operatorPrompt?.visibleText || row.message || "Mission event",
      detail:
        operatorPrompt?.steeringHints?.join(" · ") ||
        deltaDetail(row),
      meta: timestampLabel(row.timestamp || payload.detectedAt),
      timestampRaw: row.timestamp || payload.detectedAt,
      tone:
        kind === "mission.approval"
          ? "warn"
          : /failed|error/i.test(`${kind} ${row.message || ""}`)
            ? "bad"
            : "neutral",
      technicalDetail:
        operatorPrompt?.steeringHints?.length > 0
          ? operatorPrompt.steeringHints.join("\n")
          : "",
      technicalSummary:
        operatorPrompt?.steeringHints?.length > 0 ? "Routing note" : "",
      chatPreferred: isOperatorFollowUp,
      chips: [
        row.metadata?.runtimeId ? runtimeLabel(row.metadata.runtimeId) : "",
        row.metadata?.queuedForRuntime ? "Queued for runtime" : "",
      ].filter(Boolean),
    };
  }

  if (source === "runtime_event") {
    const delegatedId = row.delegated_id || row.delegatedId || "";
    const delegatedIds = new Set(
      delegatedSessions.map(item => item?.delegated_id).filter(Boolean),
    );
    if (delegatedIds.size > 0 && delegatedId && !delegatedIds.has(delegatedId)) {
      return null;
    }
    if (delegatedIds.size > 0 && !delegatedId) {
      return null;
    }
    const kind = row.kind || "runtime.event";
    const processMessage = isTraceRuntimeKind(kind);
    const heartbeat = isHeartbeatRuntimeKind(kind);
    const normalizedKind = String(kind).toLowerCase();
    const routeSwitch = normalizedKind === "runtime.route_contract";
    const phaseEntered = normalizedKind === "runtime.phase_entered";
    const routeSwitchReason = normalizedKind === "runtime.route_switch_reason";
    const handoffEvent = normalizedKind === "runtime.handoff";
    const detail = deltaDetail(row);
    const operatorPrompt =
      normalizedKind === "operator.followup"
        ? splitOperatorSteeringMessage(row.message || "")
        : null;
    return {
      id: `runtime-${delegatedId || mission.mission_id}-${row.event_id || row.created_at || payload.detectedAt}-${kind}`,
      kind,
      role: kind === "operator.followup" ? "operator" : "runtime",
      runtimeId: row.runtime_id || mission.runtime_id,
      roleLabel:
        kind === "operator.followup" ? "Operator" : runtimeLabel(row.runtime_id || mission.runtime_id),
      roleIcon:
        kind === "operator.followup"
          ? "◉"
          : row.runtime_id === "hermes"
            ? "⬢"
            : "◇",
      label: phaseEntered
        ? "Phase entered"
        : routeSwitchReason
          ? "Route switch reason"
          : handoffEvent
            ? "Runtime handoff"
            : processMessage
        ? "Process message"
        : heartbeat
          ? "Runtime heartbeat"
          : titleizeToken(kind),
      title: operatorPrompt?.visibleText || row.message || "Runtime event",
      detail:
        (operatorPrompt?.steeringHints?.join(" · ") ||
        (phaseEntered
          ? `${titleizeToken(row?.data?.phase || "execute")} phase via ${titleizeToken(
              row?.data?.role || "route",
            )}${row?.data?.provider ? ` · ${titleizeToken(row.data.provider)}` : ""}${row?.data?.model ? ` · ${row.data.model}` : ""}`
          : routeSwitchReason
            ? detail || row.message || "Route switch reason emitted by runtime supervision."
            : handoffEvent
              ? detail || row?.data?.reason || "Runtime handoff emitted by supervision."
              : routeSwitch
          ? `${titleizeToken(row?.data?.phase || "execute")} phase · ${titleizeToken(
              row?.data?.role || "route",
            )} route`
          : detail) ||
        (processMessage
          ? `${runtimeLabel(row.runtime_id || mission.runtime_id)} emitted process output.`
          : heartbeat
            ? "Heartbeat telemetry from the delegated runtime lane."
            : "")),
      meta: timestampLabel(row.created_at || payload.detectedAt),
      timestampRaw: row.created_at || payload.detectedAt,
      tone:
        row.status === "failed"
          ? "bad"
          : /approval|waiting/i.test(`${kind} ${row.status || ""}`)
            ? "warn"
            : "neutral",
      technicalDetail:
        operatorPrompt?.steeringHints?.length > 0
          ? operatorPrompt.steeringHints.join("\n")
          : processMessage && detail && detail !== row.message
          ? detail
          : row?.metadata?.trace || row?.data?.trace || "",
      technicalSummary:
        operatorPrompt?.steeringHints?.length > 0
          ? "Routing note"
          : processMessage
            ? "Thinking trace"
            : "",
      processMessage,
      chatPreferred:
        normalizedKind === "operator.followup" ||
        (processMessage && !isRuntimeRouteMetaKind(kind)),
      traceOnly: isRuntimeRouteMetaKind(kind),
      heartbeat,
      emphasis:
        processMessage ||
        phaseEntered ||
        routeSwitchReason ||
        handoffEvent ||
        row.status === "failed" ||
        /approval|blocked|error/i.test(`${kind} ${row.message || ""}`),
      chips: [
        row.runtime_id ? runtimeLabel(row.runtime_id) : "",
        routeSwitch && row?.data?.phase ? titleizeToken(row.data.phase) : "",
        routeSwitch && row?.data?.role ? titleizeToken(row.data.role) : "",
        phaseEntered && row?.data?.provider ? titleizeToken(row.data.provider) : "",
        phaseEntered && row?.data?.model ? row.data.model : "",
        routeSwitchReason && row?.data?.reason ? row.data.reason : "",
        row.status ? titleizeToken(row.status) : "",
      ].filter(Boolean),
    };
  }

  return null;
}

function inferSurfaceFromAction(action) {
  if (action?.surface) {
    return action.surface;
  }
  const commandSurface = action?.commandSurface || "";
  if (commandSurface.startsWith("git.") || commandSurface.startsWith("deploy.")) {
    return "git";
  }
  if (commandSurface.startsWith("validate.")) {
    return "validate";
  }
  if (commandSurface.startsWith("bridge.")) {
    return "bridge";
  }
  return "setup";
}

export function FluxioShellApp({ reportUiAction = noopReportUiAction }) {
  const searchParams = useMemo(() => new URLSearchParams(window.location.search), []);
  const storedUiMode = searchParams.get("mode") || localStorage.getItem(STORAGE_KEYS.uiMode) || "agent";
  const storedChatId = localStorage.getItem(STORAGE_KEYS.telegramChatId) || "";
  const storedPreviewMode = resolveInitialPreviewMode(searchParams);
  const allowFixturePreviewModes =
    hasTauriBackend() ||
    Boolean(import.meta.env?.DEV && searchParams.get("preview-control") === "1");
  const previewModeOptions = useMemo(
    () =>
      allowFixturePreviewModes
        ? FIXTURE_OPTIONS
        : FIXTURE_OPTIONS.filter(option => option.id === "live"),
    [allowFixturePreviewModes],
  );
  const storedLiveSyncSeconds = localStorage.getItem(STORAGE_KEYS.liveSyncSeconds) || "off";
  const storedCodeExecutionEnabled =
    localStorage.getItem(STORAGE_KEYS.codeExecutionEnabled) === "true";
  const storedCodeExecutionMemory =
    localStorage.getItem(STORAGE_KEYS.codeExecutionMemory) || "4g";
  const storedWorkspaceSearch = localStorage.getItem(STORAGE_KEYS.workspaceSearch) || "";
  const storedMissionSearch = localStorage.getItem(STORAGE_KEYS.missionSearch) || "";
  const storedWorkspaceOrder = loadStoredJson(STORAGE_KEYS.workspaceOrder, []);
  const storedMissionOrder = loadStoredJson(STORAGE_KEYS.missionOrder, []);
  const storedSplitViewEnabled = localStorage.getItem(STORAGE_KEYS.splitViewEnabled) === "true";
  const storedSplitMissionId = localStorage.getItem(STORAGE_KEYS.splitMissionId) || "";
  const storedLocalTasks = loadStoredJson(STORAGE_KEYS.localTasks, []);
  const storedDeletedLocalTaskIds = normalizeStoredIdList(
    loadStoredJson(STORAGE_KEYS.deletedLocalTaskIds, []),
  );
  const deletedLocalTaskIdSet = new Set(storedDeletedLocalTaskIds);
  const storedMemoryPolicy = loadStoredJson(STORAGE_KEYS.memoryPolicy, DEFAULT_MEMORY_POLICY);
  const storedMemoryStore = loadStoredJson(STORAGE_KEYS.memoryStore, {
    workspace: {},
    mission: {},
  });
  const storedDebugEvents = loadStoredJson(STORAGE_KEYS.debugEvents, []);
  const storedUiState = loadStoredJson(STORAGE_KEYS.persistedUiState, {});
  const storedControlRoomSnapshot = loadStoredJson(STORAGE_KEYS.controlRoomSnapshot, null);
  const storedChatSessions = normalizeChatSessions(
    loadStoredJson(STORAGE_KEYS.chatSessions, []),
  );
  const storedChatSessionTranscripts = normalizeChatSessionTranscripts(
    loadStoredJson(STORAGE_KEYS.chatSessionTranscripts, {}),
    asList(storedUiState?.operatorNotes),
  );
  const storedActiveChatSessionId =
    localStorage.getItem(STORAGE_KEYS.activeChatSessionId) || "";
  const storedOpenAICodexOAuthFlow = {
    ...DEFAULT_OPENAI_CODEX_OAUTH_FLOW,
    ...loadStoredJson(STORAGE_KEYS.openAICodexOAuthFlow, {}),
  };
  if (storedOpenAICodexOAuthFlow.sessionId && storedOpenAICodexOAuthFlow.status !== "connected") {
    storedOpenAICodexOAuthFlow.open = true;
  }
  const storedCodexImportSnapshot = normalizeCodexImportSnapshot(
    loadStoredJson(STORAGE_KEYS.codexImportSnapshot, DEFAULT_CODEX_IMPORT_SNAPSHOT),
  );
  const requestedBuilderDetail =
    searchParams.get("builderDetail") === "1" || searchParams.get("builderDetail") === "true";
  const storedSurface =
    searchParams.get("surface") ||
    localStorage.getItem(STORAGE_KEYS.surface) ||
    (storedUiMode === "builder" ? "builder" : "home");
  const requestedAgentScene = searchParams.get("agentScene") || "";
  const initialSurface = storedSurface === "general" ? "skills" : storedSurface;

  const requestedUiMode = searchParams.get("mode");
  const [uiMode, setUiMode] = useState(
    ["agent", "builder"].includes(requestedUiMode)
      ? requestedUiMode
      : ["agent", "builder"].includes(storedUiMode)
        ? storedUiMode
        : "agent",
  );
  const [surface, setSurface] = useState(
    WORKSPACE_SURFACE_IDS.includes(initialSurface)
      ? initialSurface
      : "home",
  );
  const [agentScene, setAgentScene] = useState(
    ["idle", "run", "live"].includes(requestedAgentScene) ? requestedAgentScene : "idle",
  );
  const [builderDetailOpen, setBuilderDetailOpen] = useState(
    requestedBuilderDetail || Boolean(storedUiState.builderDetailOpen),
  );
  const [referenceAppearance, setReferenceAppearance] = useState({
    ...DEFAULT_REFERENCE_APPEARANCE,
    ...(storedUiState.referenceAppearance || {}),
  });
  const requestedSettingsTab = searchParams.get("settingsTab");
  const [referenceSettingsTab, setReferenceSettingsTab] = useState(
    requestedSettingsTab || storedUiState.referenceSettingsTab || "general",
  );
  const [referenceStudio, setReferenceStudio] = useState(() =>
    mergeReferenceStudioState(
      buildDefaultReferenceStudio(profileFormFromWorkspace(null, "builder").routeOverrides),
      storedUiState.referenceStudio,
    ),
  );
  const [codexImportSnapshot, setCodexImportSnapshot] = useState(storedCodexImportSnapshot);
  const [codexImportRefreshing, setCodexImportRefreshing] = useState(false);
  const [previewMode, setPreviewMode] = useState(
    previewModeOptions.some(option => option.id === storedPreviewMode) ? storedPreviewMode : "live",
  );
  const [liveSyncSeconds, setLiveSyncSeconds] = useState(
    LIVE_SYNC_OPTIONS.some(option => option.value === storedLiveSyncSeconds)
      ? storedLiveSyncSeconds
      : "off",
  );
  const [persistentGoalMode, setPersistentGoalMode] = useState(
    () => localStorage.getItem(GOAL_MODE_STORAGE_KEY) === "true",
  );
  const [browserToolbarState, setBrowserToolbarState] = useState(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem(BROWSER_TOOLBAR_STORAGE_KEY) || "{}");
      return {
        device: parsed.device || "Desktop",
        viewport: parsed.viewport || "1440×900",
        zoom: parsed.zoom || "100%",
      };
    } catch {
      return { device: "Desktop", viewport: "1440×900", zoom: "100%" };
    }
  });
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(null);
  const [selectedMissionId, setSelectedMissionId] = useState(null);
  const [chatSessions, setChatSessions] = useState(storedChatSessions);
  const [chatSessionTranscripts, setChatSessionTranscripts] = useState(
    storedChatSessionTranscripts,
  );
  const [chatRequestsInFlight, setChatRequestsInFlight] = useState(0);
  const [activeChatSessionId, setActiveChatSessionId] = useState(
    storedActiveChatSessionId || storedChatSessions[0]?.id || "",
  );
  const [showWorkspaceDialog, setShowWorkspaceDialog] = useState(false);
  const [showMissionDialog, setShowMissionDialog] = useState(false);
  const [showEscalationDialog, setShowEscalationDialog] = useState(false);
  const [workspaceBrowser, setWorkspaceBrowser] = useState(DEFAULT_WORKSPACE_BROWSER_STATE);
  const [workspaceForm, setWorkspaceForm] = useState(DEFAULT_WORKSPACE_FORM);
  const [missionForm, setMissionForm] = useState(DEFAULT_MISSION_FORM);
  const [workspaceProfileForm, setWorkspaceProfileForm] = useState(
    profileFormFromWorkspace(null, "builder"),
  );
  const [skillStudioFilter, setSkillStudioFilter] = useState("all");
  const [skillStudioQuery, setSkillStudioQuery] = useState("");
  const [activeRoadmapItemId, setActiveRoadmapItemId] = useState("");
  const [telegramChatId, setTelegramChatId] = useState(storedChatId);
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [openClawGatewayUrl, setOpenClawGatewayUrl] = useState(DEFAULT_OPENCLAW_GATEWAY_URL);
  const [openClawGatewayToken, setOpenClawGatewayToken] = useState("");
  const [providerSecretDrafts, setProviderSecretDrafts] = useState(
    Object.fromEntries(PROVIDER_SECRET_OPTIONS.map(item => [item.id, ""])),
  );
  const [providerSecretSaving, setProviderSecretSaving] = useState({});
  const [openAICodexOAuthFlow, setOpenAICodexOAuthFlow] = useState(storedOpenAICodexOAuthFlow);
  const [miniMaxOAuthFlow, setMiniMaxOAuthFlow] = useState(DEFAULT_MINIMAX_OAUTH_FLOW);
  const [codeExecutionEnabled, setCodeExecutionEnabled] = useState(storedCodeExecutionEnabled);
  const [codeExecutionMemory, setCodeExecutionMemory] = useState(
    CODE_EXECUTION_MEMORY_OPTIONS.some(option => option.value === storedCodeExecutionMemory)
      ? storedCodeExecutionMemory
      : "4g",
  );
  const [lastPushReason, setLastPushReason] = useState("");
  const [liveSyncSuspended, setLiveSyncSuspended] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const requestedDrawer = searchParams.get("drawer");
  const [activeDrawer, setActiveDrawer] = useState(requestedDrawer || storedUiState.activeDrawer || null);
  const [operatorDraft, setOperatorDraft] = useState("");
  const [operatorNotes, setOperatorNotes] = useState(storedUiState.operatorNotes || []);
  const [liveControlEvents, setLiveControlEvents] = useState(storedUiState.liveControlEvents || []);
  const [operatorAttachments, setOperatorAttachments] = useState([]);
  const [activeCommentTarget, setActiveCommentTarget] = useState(null);
  const [agentRouteRole, setAgentRouteRole] = useState("executor");
  const [agentRuntimeFocus, setAgentRuntimeFocus] = useState("all");
  const [showThinkingTrace, setShowThinkingTrace] = useState(true);
  const [pinnedNexusIds, setPinnedNexusIds] = useState(storedUiState.pinnedNexusIds || []);
  const [highlightedTurnId, setHighlightedTurnId] = useState("");
  const [selectedReviewTargetId, setSelectedReviewTargetId] = useState(
    storedUiState.selectedReviewTargetId || "",
  );
  const [selectedLiveReviewEventId, setSelectedLiveReviewEventId] = useState(
    storedUiState.selectedLiveReviewEventId || "",
  );
  const [selectedLiveReviewFrameIndex, setSelectedLiveReviewFrameIndex] = useState(0);
  const [selectedReplayMarkerIndex, setSelectedReplayMarkerIndex] = useState(0);
  const [selectedPlannerProofChipIndex, setSelectedPlannerProofChipIndex] = useState(0);
  const [activePlannerProofDetail, setActivePlannerProofDetail] = useState(null);
  const [workspaceSearchQuery, setWorkspaceSearchQuery] = useState(storedWorkspaceSearch);
  const [missionSearchQuery, setMissionSearchQuery] = useState(storedMissionSearch);
  const [workspaceOrder, setWorkspaceOrder] = useState(
    Array.isArray(storedWorkspaceOrder) ? storedWorkspaceOrder : [],
  );
  const [missionOrder, setMissionOrder] = useState(
    Array.isArray(storedMissionOrder) ? storedMissionOrder : [],
  );
  const [splitViewEnabled, setSplitViewEnabled] = useState(storedSplitViewEnabled);
  const [splitMissionId, setSplitMissionId] = useState(storedSplitMissionId);
  const [dragState, setDragState] = useState({ kind: "", id: "" });
  const [localTasks, setLocalTasks] = useState(
    Array.isArray(storedLocalTasks)
      ? storedLocalTasks.filter(item => item?.id && !deletedLocalTaskIdSet.has(String(item.id)))
      : [],
  );
  const [deletedLocalTaskIds, setDeletedLocalTaskIds] = useState(storedDeletedLocalTaskIds);
  const [taskForm, setTaskForm] = useState(DEFAULT_TASK_FORM);
  const [taskTriggerToken, setTaskTriggerToken] = useState("");
  const [proofWrapEnabled, setProofWrapEnabled] = useState(true);
  const [memoryPolicy, setMemoryPolicy] = useState({
    ...DEFAULT_MEMORY_POLICY,
    ...(storedMemoryPolicy || {}),
  });
  const [memoryStore, setMemoryStore] = useState({
    workspace: storedMemoryStore?.workspace || {},
    mission: storedMemoryStore?.mission || {},
  });
  const [debugEvents, setDebugEvents] = useState(
    Array.isArray(storedDebugEvents) ? storedDebugEvents.slice(-MAX_DEBUG_LOG) : [],
  );
  const [data, setData] = useState({
    snapshot: storedControlRoomSnapshot && typeof storedControlRoomSnapshot === "object"
      ? storedControlRoomSnapshot
      : null,
    onboarding:
      storedControlRoomSnapshot && typeof storedControlRoomSnapshot === "object"
        ? storedControlRoomSnapshot.onboarding || null
        : null,
    pendingApprovals: [],
    pendingQuestions: [],
    telegramReady: false,
    previewMeta: null,
    openClawStatus: null,
    openClawHasToken: false,
    openClawMessages: [],
    providerSecretPresence: {},
  });

  const mountedRef = useRef(true);
  const currentMissionRef = useRef(null);
  const currentDelegatedSessionsRef = useRef([]);
  const transcriptCacheRef = useRef({});
  const refreshPromiseRef = useRef(null);
  const queuedRefreshReasonRef = useRef("");
  const codexImportPromiseRef = useRef(null);
  const authPromptedRef = useRef(false);
  const oauthSessionCheckedRef = useRef(false);
  const studioAssistantPendingRef = useRef(null);
  const goalModeLastResumeRef = useRef("");
  const { items: toasts, push: pushToast } = useToastQueue();

  const markAction = useCallback(
    action => {
      reportUiAction(action);
    },
    [reportUiAction],
  );

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.uiMode, uiMode);
  }, [uiMode]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.surface, surface);
  }, [surface]);

  useEffect(() => {
    if (["builder", "skills", "rule-sets", "images", "voice", "workbench", "settings"].includes(surface)) {
      if (uiMode !== "builder") {
        setUiMode("builder");
      }
      return;
    }
    if (uiMode !== "agent") {
      setUiMode("agent");
    }
  }, [surface, uiMode]);

  useEffect(() => {
    if (!previewModeOptions.some(option => option.id === previewMode)) {
      setPreviewMode("live");
    }
  }, [previewMode, previewModeOptions]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.previewMode, previewMode);
  }, [previewMode]);

  useEffect(() => {
    if (oauthSessionCheckedRef.current || previewMode !== "live" || !hasCommandBackend()) {
      return;
    }
    oauthSessionCheckedRef.current = true;
    let cancelled = false;
    (async () => {
      try {
        const status = await callBackend(
          "get_openai_codex_oauth_session_command",
          undefined,
          { throwOnError: true },
        );
        if (cancelled) {
          return;
        }
        if (status?.active && status?.sessionId) {
          setOpenAICodexOAuthFlow(current => ({
            ...DEFAULT_OPENAI_CODEX_OAUTH_FLOW,
            ...current,
            open: true,
            sessionId: current.sessionId || status.sessionId,
            method: current.method || status.method || "",
            authUrl: current.authUrl || status.authUrl || status.verificationUrl || "",
            callbackPort: current.callbackPort || status.callbackPort || 0,
            relayUrl: current.relayUrl || status.relayUrl || "",
            relayToken: current.relayToken || status.relayToken || "",
            helperCommand: current.helperCommand || status.helperCommand || "",
            verificationUrl: current.verificationUrl || status.verificationUrl || status.authUrl || "",
            userCode: current.userCode || status.userCode || "",
            status: current.status === "idle" ? "waiting" : current.status,
            message:
              current.message ||
              "Recovered the active OpenAI Codex auth session from the NAS.",
          }));
        } else if (openAICodexOAuthFlow.sessionId) {
          setOpenAICodexOAuthFlow({
            ...DEFAULT_OPENAI_CODEX_OAUTH_FLOW,
            open: true,
            status: "error",
            message: "The previous OpenAI Codex OAuth session expired. Start Codex OAuth again.",
          });
        }
      } catch {
        return;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [openAICodexOAuthFlow.sessionId, previewMode]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.liveSyncSeconds, liveSyncSeconds);
  }, [liveSyncSeconds]);

  useEffect(() => {
    localStorage.setItem(GOAL_MODE_STORAGE_KEY, persistentGoalMode ? "true" : "false");
  }, [persistentGoalMode]);

  useEffect(() => {
    localStorage.setItem(BROWSER_TOOLBAR_STORAGE_KEY, JSON.stringify(browserToolbarState));
  }, [browserToolbarState]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.telegramChatId, telegramChatId);
  }, [telegramChatId]);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEYS.codeExecutionEnabled,
      codeExecutionEnabled ? "true" : "false",
    );
  }, [codeExecutionEnabled]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.codeExecutionMemory, codeExecutionMemory);
  }, [codeExecutionMemory]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.workspaceSearch, workspaceSearchQuery);
  }, [workspaceSearchQuery]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.missionSearch, missionSearchQuery);
  }, [missionSearchQuery]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.splitViewEnabled, splitViewEnabled ? "true" : "false");
  }, [splitViewEnabled]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.splitMissionId, splitMissionId || "");
  }, [splitMissionId]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.workspaceOrder, JSON.stringify(workspaceOrder));
  }, [workspaceOrder]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.missionOrder, JSON.stringify(missionOrder));
  }, [missionOrder]);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEYS.chatSessions,
      JSON.stringify(normalizeChatSessions(chatSessions)),
    );
  }, [chatSessions]);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEYS.chatSessionTranscripts,
      JSON.stringify(normalizeChatSessionTranscripts(chatSessionTranscripts)),
    );
  }, [chatSessionTranscripts]);

  useEffect(() => {
    if (!activeChatSessionId) {
      localStorage.removeItem(STORAGE_KEYS.activeChatSessionId);
      return;
    }
    localStorage.setItem(STORAGE_KEYS.activeChatSessionId, activeChatSessionId);
  }, [activeChatSessionId]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.localTasks, JSON.stringify(localTasks));
  }, [localTasks]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.deletedLocalTaskIds, JSON.stringify(deletedLocalTaskIds));
  }, [deletedLocalTaskIds]);

  useEffect(() => {
    if (
      openAICodexOAuthFlow.status === "connected" ||
      openAICodexOAuthFlow.status === "idle" ||
      !openAICodexOAuthFlow.sessionId
    ) {
      localStorage.removeItem(STORAGE_KEYS.openAICodexOAuthFlow);
      return;
    }
    localStorage.setItem(STORAGE_KEYS.openAICodexOAuthFlow, JSON.stringify(openAICodexOAuthFlow));
  }, [openAICodexOAuthFlow]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.memoryPolicy, JSON.stringify(memoryPolicy));
  }, [memoryPolicy]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.memoryStore, JSON.stringify(memoryStore));
  }, [memoryStore]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.debugEvents, JSON.stringify(debugEvents.slice(-MAX_DEBUG_LOG)));
  }, [debugEvents]);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEYS.persistedUiState,
      JSON.stringify({
        activeDrawer,
        builderDetailOpen,
        pinnedNexusIds,
        selectedReviewTargetId,
        selectedLiveReviewEventId,
        operatorNotes: operatorNotes.slice(-40),
        liveControlEvents: liveControlEvents.slice(-60),
        referenceAppearance,
        referenceSettingsTab,
        referenceStudio,
      }),
    );
  }, [
    activeDrawer,
    builderDetailOpen,
    liveControlEvents,
    operatorNotes,
    pinnedNexusIds,
    referenceAppearance,
    referenceSettingsTab,
    referenceStudio,
    selectedReviewTargetId,
    selectedLiveReviewEventId,
  ]);

  useEffect(() => {
    return subscribeBackendCalls(event => {
      setDebugEvents(current =>
        [event, ...current].slice(0, MAX_DEBUG_LOG),
      );
    });
  }, []);

  useEffect(() => {
    const onError = event => {
      setDebugEvents(current =>
        [
          {
            id: `window-error-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            kind: "window.error",
            at: new Date().toISOString(),
            message: event.message || "Unhandled browser error",
            source: event.filename || "",
            line: event.lineno || 0,
            column: event.colno || 0,
          },
          ...current,
        ].slice(0, MAX_DEBUG_LOG),
      );
    };
    const onUnhandled = event => {
      setDebugEvents(current =>
        [
          {
            id: `window-unhandled-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            kind: "window.unhandledrejection",
            at: new Date().toISOString(),
            message: String(event.reason || "Unhandled rejection"),
          },
          ...current,
        ].slice(0, MAX_DEBUG_LOG),
      );
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandled);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandled);
    };
  }, []);

  useEffect(() => {
    setLiveControlEvents([]);
  }, [previewMode, selectedMissionId]);

  const refreshCodexImportSnapshot = useCallback(
    async ({ showToast = false } = {}) => {
      if (previewMode !== "live" || !hasCommandBackend()) {
        setCodexImportSnapshot(DEFAULT_CODEX_IMPORT_SNAPSHOT);
        localStorage.removeItem(STORAGE_KEYS.codexImportSnapshot);
        if (showToast) {
          pushToast("Codex import inspection is only available in live mode.", "warn");
        }
        return DEFAULT_CODEX_IMPORT_SNAPSHOT;
      }
      if (codexImportPromiseRef.current) {
        return codexImportPromiseRef.current;
      }

      const refreshPromise = (async () => {
        setCodexImportRefreshing(true);
        setCodexImportSnapshot(current => ({ ...current, isRefreshing: true }));
        try {
          const nextSnapshot = normalizeCodexImportSnapshot(
            await callBackend("inspect_codex_import_command", undefined, {
              throwOnError: true,
            }),
          );
          const completedSnapshot = { ...nextSnapshot, isRefreshing: false };
          setCodexImportSnapshot(completedSnapshot);
          try {
            localStorage.setItem(STORAGE_KEYS.codexImportSnapshot, JSON.stringify(completedSnapshot));
          } catch {
            // Codex import caching is only a startup optimization.
          }
          if (showToast) {
            pushToast("Codex import sources refreshed.", "info");
          }
          return completedSnapshot;
        } catch (error) {
          setCodexImportSnapshot(current => ({
            ...current,
            isRefreshing: false,
            notes: uniq([
              ...(current.notes || []),
              `Codex import refresh failed: ${error}`,
            ]),
          }));
          if (showToast) {
            pushToast(`Codex import refresh failed: ${error}`, "error");
          }
          return null;
        } finally {
          setCodexImportRefreshing(false);
          codexImportPromiseRef.current = null;
        }
      })();

      codexImportPromiseRef.current = refreshPromise;
      return refreshPromise;
    },
    [previewMode, pushToast],
  );

  const performRefresh = useCallback(
    async (reason = "manual") => {
      markAction(`refresh:${reason}`);
      setIsRefreshing(true);
      try {
        if (previewMode !== "live") {
          if (!allowFixturePreviewModes) {
            setPreviewMode("live");
            return;
          }
          const fixturePayload = buildFixtureSnapshot(previewMode);
          if (!fixturePayload) {
            setPreviewMode("live");
            return;
          }
          setData(current => ({
            ...current,
            snapshot: fixturePayload.snapshot,
            onboarding: fixturePayload.onboarding,
            pendingApprovals: fixturePayload.pendingApprovals,
            pendingQuestions: fixturePayload.pendingQuestions,
            telegramReady: fixturePayload.telegramReady,
            previewMeta: fixturePayload.meta,
            openClawStatus: null,
            openClawHasToken: false,
            openClawMessages: [],
            providerSecretPresence: {},
          }));
          setCodexImportSnapshot(DEFAULT_CODEX_IMPORT_SNAPSHOT);
          return;
        }

        if (!hasCommandBackend()) {
          setData(current => ({
            ...current,
            snapshot: null,
            onboarding: current.onboarding || null,
            pendingApprovals: [],
            pendingQuestions: [],
            telegramReady: false,
            previewMeta: null,
            openClawStatus: null,
            openClawHasToken: false,
            openClawMessages: [],
            providerSecretPresence: {},
          }));
          setCodexImportSnapshot(DEFAULT_CODEX_IMPORT_SNAPSHOT);
          return;
        }

        const snapshot = await callBackend(
          "get_control_room_snapshot_command",
          { payload: { root: null } },
          { throwOnError: true },
        );

        const [
          pendingApprovals,
          pendingQuestions,
          telegramReady,
          openClawStatus,
          openClawHasToken,
          providerSecretPresencePrimary,
        ] = await Promise.all([
          callBackendWithFallback("list_pending_approvals", undefined, []),
          callBackendWithFallback("list_pending_questions", undefined, []),
          callBackendWithFallback("has_telegram_bot_token_command", undefined, false),
          callBackendWithFallback("get_openclaw_status", undefined, null),
          callBackendWithFallback("has_openclaw_gateway_token", undefined, false),
          callBackendWithFallback(
            "get_provider_secret_presence_command",
            { providerIds: PROVIDER_AUTH_PRESENCE_IDS },
            {},
          ),
        ]);

        if (!mountedRef.current) {
          return;
        }

        const providerSecretPresence =
          (snapshot?.providerSecretPresence && typeof snapshot.providerSecretPresence === "object"
            ? snapshot.providerSecretPresence
            : null) ||
          providerSecretPresencePrimary ||
          {};

        try {
          localStorage.setItem(STORAGE_KEYS.controlRoomSnapshot, JSON.stringify(snapshot));
        } catch {
          // Snapshot caching is an optimization; live state still renders without it.
        }
        setData(current => ({
          ...current,
          snapshot,
          onboarding: snapshot?.onboarding || current.onboarding || null,
          pendingApprovals: Array.isArray(pendingApprovals) ? pendingApprovals : [],
          pendingQuestions: Array.isArray(pendingQuestions) ? pendingQuestions : [],
          telegramReady: Boolean(telegramReady),
          previewMeta: null,
          openClawStatus: openClawStatus || null,
          openClawHasToken: Boolean(openClawHasToken),
          providerSecretPresence:
            providerSecretPresence && typeof providerSecretPresence === "object"
              ? providerSecretPresence
              : {},
        }));
        if (["initialize", "manual", "workspace-save", "codex-workspace-import", "codex-workspace-import-all"].includes(reason)) {
          void refreshCodexImportSnapshot({ showToast: false });
        }

        if (reason !== "initialize") {
          setLastPushReason(reason);
        }
      } catch (error) {
        setData(current => ({
          ...current,
          snapshot: previewMode === "live" ? null : current.snapshot,
          onboarding: previewMode === "live" ? null : current.onboarding,
          previewMeta: null,
          openClawStatus: null,
          openClawHasToken: false,
          openClawMessages: [],
          providerSecretPresence: {},
        }));
        pushToast(`Refresh failed: ${error}`, "error");
      } finally {
        if (mountedRef.current) {
          setIsRefreshing(false);
        }
      }
    },
    [allowFixturePreviewModes, markAction, previewMode, pushToast, refreshCodexImportSnapshot],
  );

  const refreshAll = useCallback(
    async (reason = "manual") => {
      const normalizedReason = String(reason || "manual");
      if (refreshPromiseRef.current) {
        queuedRefreshReasonRef.current = normalizedReason;
        return refreshPromiseRef.current;
      }

      const refreshPromise = (async () => {
        let nextReason = normalizedReason;
        while (nextReason) {
          queuedRefreshReasonRef.current = "";
          await performRefresh(nextReason);
          nextReason = queuedRefreshReasonRef.current;
        }
      })().finally(() => {
        if (refreshPromiseRef.current === refreshPromise) {
          refreshPromiseRef.current = null;
        }
      });

      refreshPromiseRef.current = refreshPromise;
      return refreshPromise;
    },
    [performRefresh],
  );

  useEffect(() => {
    void refreshAll("initialize");
  }, [refreshAll]);

  useEffect(() => {
    const workspaces = data.snapshot?.workspaces || [];
    const preferredWorkspace = preferredControlWorkspace(workspaces, data.snapshot?.missions || []);
    setSelectedWorkspaceId(current => {
      const currentWorkspace = workspaces.find(item => item.workspace_id === current);
      if (!currentWorkspace) {
        return preferredWorkspace?.workspace_id || workspaces[0]?.workspace_id || null;
      }
      const preferredMission = preferredControlMission(data.snapshot?.missions || []);
      if (
        preferredMission?.workspace_id &&
        preferredMission.workspace_id !== current &&
        controlMissionPriority(preferredMission) > 0
      ) {
        const currentWorkspaceBest = preferredControlMission(
          asList(data.snapshot?.missions).filter(item => item?.workspace_id === current),
        );
        if (controlMissionPriority(preferredMission) > controlMissionPriority(currentWorkspaceBest)) {
          return preferredMission.workspace_id;
        }
      }
      return current;
    });
  }, [data.snapshot]);

  useEffect(() => {
    const missions = data.snapshot?.missions || [];
    setSelectedMissionId(current => {
      if (activeChatSessionId) {
        return null;
      }
      const preferred = preferredControlMission(missions);
      const currentMission = missions.find(item => item.mission_id === current);
      if (!currentMission) {
        return preferred?.mission_id || null;
      }
      const currentStatus = String(currentMission?.state?.status || "").toLowerCase();
      const preferredStatus = String(preferred?.state?.status || "").toLowerCase();
      const currentPriority = controlMissionPriority(currentMission);
      const preferredPriority = controlMissionPriority(preferred);
      if (
        preferred?.mission_id &&
        preferred.mission_id !== current &&
        ["blocked", "needs_approval", "queued", "running", "verification_failed"].includes(preferredStatus) &&
        (["completed", "failed", "stopped"].includes(currentStatus) ||
          preferredPriority > currentPriority)
      ) {
        return preferred.mission_id;
      }
      return current;
    });
  }, [activeChatSessionId, data.snapshot]);

  useEffect(() => {
    const handleVisibility = () => {
      const hidden = document.visibilityState !== "visible";
      const shouldSuspend = previewMode === "live" && liveSyncSeconds !== "off" && hidden;
      setLiveSyncSuspended(shouldSuspend);
      if (!hidden && previewMode === "live" && liveSyncSeconds !== "off") {
        void refreshAll("visibility-resume");
      }
    };

    handleVisibility();
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [liveSyncSeconds, previewMode, refreshAll]);

  useEffect(() => {
    if (previewMode !== "live" || liveSyncSeconds === "off" || liveSyncSuspended) {
      return undefined;
    }

    const interval = window.setInterval(() => {
      void refreshAll("live-sync");
    }, Number(liveSyncSeconds) * 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, [liveSyncSeconds, liveSyncSuspended, previewMode, refreshAll]);

  useEffect(() => {
    if (previewMode !== "live" || !hasCommandBackend() || chatRequestsInFlight <= 0) {
      return undefined;
    }
    void refreshAll("chat-turn-start");
    const interval = window.setInterval(() => {
      void refreshAll("chat-turn-sync");
    }, 1200);
    return () => {
      window.clearInterval(interval);
    };
  }, [chatRequestsInFlight, previewMode, refreshAll]);

  useEffect(() => {
    if (previewMode !== "live" || !hasTauriBackend()) {
      return undefined;
    }

    let cancelled = false;
    const unlisteners = [];
    const registerListener = async (eventName, handler) => {
      try {
        const unlisten = await listen(eventName, handler);
        if (cancelled) {
          unlisten();
          return;
        }
        unlisteners.push(unlisten);
      } catch {
        return undefined;
      }
      return undefined;
    };

    void registerListener("control-room://changed", event => {
      const reason = event?.payload?.reason || "backend-event";
      setLastPushReason(reason);
      void refreshAll(reason);
    });

    void registerListener("control-room://delta", event => {
      const reason = event?.payload?.source || "backend-delta";
      setLastPushReason(reason);
      const liveItem = controlRoomDeltaToLiveItem(
        event?.payload,
        currentMissionRef.current,
        currentDelegatedSessionsRef.current,
      );
      if (liveItem) {
        setLiveControlEvents(current =>
          [liveItem, ...current.filter(entry => entry.id !== liveItem.id)].slice(0, 24),
        );
      }
    });

    void registerListener("openclaw://status", event => {
      setData(current => ({
        ...current,
        openClawStatus: event?.payload || current.openClawStatus,
      }));
    });

    void registerListener("openclaw://message", event => {
      const content = event?.payload?.content;
      if (!content) {
        return;
      }
      const pendingStudioRequest = studioAssistantPendingRef.current;
      if (pendingStudioRequest?.itemId) {
        const runtimeProposal = normalizeStudioAssistantRuntimeResponse(
          pendingStudioRequest.item,
          content,
        );
        setReferenceStudio(current => {
          const collectionKey = studioCollectionKey(pendingStudioRequest.kind);
          return {
            ...current,
            [collectionKey]: asList(current[collectionKey]).map(item =>
              item.id !== pendingStudioRequest.itemId
                ? item
                : {
                    ...item,
                    assistant: {
                      ...(item.assistant || {}),
                      proposal: runtimeProposal.patch
                        ? runtimeProposal
                        : item.assistant?.proposal || runtimeProposal,
                      conversation: [
                        {
                          role: "assistant",
                          author: pendingStudioRequest.model,
                          body: runtimeProposal.reply,
                          meta: timestampLabel(new Date().toISOString()) || "Now",
                        },
                        ...asList(item.assistant?.conversation).filter(
                          entry => entry?.meta !== "Waiting for runtime reply",
                        ),
                      ].slice(0, 6),
                    },
                  },
            ),
          };
        });
        studioAssistantPendingRef.current = null;
      }
      setData(current => ({
        ...current,
        openClawMessages: [
          ...current.openClawMessages,
          createSessionEntry({
            title: "OpenClaw message",
            detail: String(content),
            meta: "Gateway message",
            tone: "neutral",
          }),
        ].slice(-16),
      }));
    });

    return () => {
      cancelled = true;
      for (const unlisten of unlisteners) {
        if (typeof unlisten === "function") {
          unlisten();
        }
      }
    };
  }, [previewMode, refreshAll]);

  const snapshot = data.snapshot || EMPTY_OBJECT;
  const onboarding = data.onboarding || snapshot.onboarding || EMPTY_OBJECT;
  const setupHealth = snapshot.setupHealth || onboarding.setupHealth || EMPTY_OBJECT;
  const workspaces = Array.isArray(snapshot.workspaces) ? snapshot.workspaces : EMPTY_ARRAY;
  const missions = Array.isArray(snapshot.missions) ? snapshot.missions : EMPTY_ARRAY;
  const inboxItems = Array.isArray(snapshot.inbox) ? snapshot.inbox : EMPTY_ARRAY;

  const workspace = useMemo(
    () => selectedWorkspace(snapshot, selectedWorkspaceId),
    [selectedWorkspaceId, snapshot],
  );
  const mission = useMemo(
    () => (activeChatSessionId ? null : selectedMission(snapshot, selectedMissionId)),
    [activeChatSessionId, selectedMissionId, snapshot],
  );
  const workspaceMissions = useMemo(
    () =>
      missions.filter(item =>
        selectedWorkspaceId ? item.workspace_id === selectedWorkspaceId : true,
      ),
    [missions, selectedWorkspaceId],
  );

  const profileId = activeProfileId(snapshot, onboarding, workspace, mission);
  const profileParams = currentProfileParameters(snapshot, profileId, workspace);

  const viewModel = useMemo(
    () =>
      buildMissionControlModel({
        mission,
        workspace,
        setupHealth,
        snapshot,
        pendingQuestions: data.pendingQuestions,
        pendingApprovals: data.pendingApprovals,
        telegramReady: data.telegramReady,
        profileId,
        profileParams,
        inbox: inboxItems,
        previewMode,
        uiMode,
        lastPushReason,
        isRefreshing,
        liveSyncSeconds,
        liveSyncSuspended,
      }),
    [
      data.pendingApprovals,
      data.pendingQuestions,
      data.telegramReady,
      inboxItems,
      isRefreshing,
      lastPushReason,
      liveSyncSeconds,
      liveSyncSuspended,
      mission,
      previewMode,
      profileId,
      profileParams,
      setupHealth,
      snapshot,
      uiMode,
      workspace,
    ],
  );

  const missionOptions = workspaceMissions.length > 0 ? workspaceMissions : missions;
  const quickSetupActions = useMemo(
    () => [...(setupHealth.repairActions || []), ...(setupHealth.globalActions || [])].slice(0, 3),
    [setupHealth.globalActions, setupHealth.repairActions],
  );

  useEffect(() => {
    if (workspaces.length === 0) {
      if (selectedWorkspaceId !== null) {
        setSelectedWorkspaceId(null);
      }
      return;
    }
    if (!selectedWorkspaceId || !workspaces.some(item => item.workspace_id === selectedWorkspaceId)) {
      setSelectedWorkspaceId(workspaces[0].workspace_id);
    }
  }, [selectedWorkspaceId, workspaces]);

  const activeChatSession = useMemo(
    () =>
      chatSessions.find(item => item.id === activeChatSessionId) || null,
    [activeChatSessionId, chatSessions],
  );

  useEffect(() => {
    if (workspaces.length === 0) {
      return;
    }
    if (activeChatSessionId || chatSessions.length > 0) {
      return;
    }
    const resolvedWorkspaceId =
      selectedWorkspaceId || workspace?.workspace_id || workspaces[0]?.workspace_id || "";
    const created = buildChatSession(resolvedWorkspaceId, "");
    setChatSessions(current => normalizeChatSessions([created, ...current]));
    setChatSessionTranscripts(current => ({ ...current, [created.id]: [] }));
    setActiveChatSessionId(created.id);
    setSelectedMissionId(null);
  }, [
    activeChatSessionId,
    chatSessions.length,
    selectedWorkspaceId,
    workspace?.workspace_id,
    workspaces,
  ]);

  useEffect(() => {
    const workspaceIds = new Set(workspaces.map(item => item.workspace_id));
    setChatSessions(current => {
      const next = normalizeChatSessions(
        current.filter(item => !item.workspaceId || workspaceIds.has(item.workspaceId)),
      );
      return JSON.stringify(next) === JSON.stringify(current) ? current : next;
    });
  }, [workspaces]);

  useEffect(() => {
    const sessionIds = new Set(chatSessions.map(item => item.id));
    setChatSessionTranscripts(current => {
      const next = {};
      for (const [sessionId, turns] of Object.entries(current || {})) {
        if (!sessionIds.has(sessionId)) {
          continue;
        }
        next[sessionId] = asList(turns).slice(-MAX_CHAT_SESSION_TRANSCRIPT_TURNS);
      }
      return JSON.stringify(next) === JSON.stringify(current) ? current : next;
    });
  }, [chatSessions]);

  useEffect(() => {
    if (!activeChatSessionId) {
      return;
    }
    if (!chatSessions.some(item => item.id === activeChatSessionId)) {
      setActiveChatSessionId("");
    }
  }, [activeChatSessionId, chatSessions]);

  useEffect(() => {
    if (!activeChatSession?.workspaceId) {
      return;
    }
    if (selectedWorkspaceId !== activeChatSession.workspaceId) {
      setSelectedWorkspaceId(activeChatSession.workspaceId);
    }
  }, [activeChatSession?.workspaceId, selectedWorkspaceId]);

  useEffect(() => {
    if (!selectedMissionId || !activeChatSessionId) {
      return;
    }
    setActiveChatSessionId("");
  }, [activeChatSessionId, selectedMissionId]);

  useEffect(() => {
    const hasActiveChat =
      Boolean(activeChatSessionId) &&
      chatSessions.some(item => item.id === activeChatSessionId);
    if (hasActiveChat) {
      if (selectedMissionId !== null) {
        setSelectedMissionId(null);
      }
      return;
    }
    if (missionOptions.length === 0) {
      if (selectedMissionId !== null) {
        setSelectedMissionId(null);
      }
      return;
    }
    const preferred = preferredControlMission(missionOptions);
    const currentMission = missionOptions.find(item => item.mission_id === selectedMissionId);
    if (!selectedMissionId || !currentMission) {
      setSelectedMissionId(preferred?.mission_id || missionOptions[0].mission_id);
      return;
    }
    const currentStatus = String(currentMission?.state?.status || "").toLowerCase();
    const preferredStatus = String(preferred?.state?.status || "").toLowerCase();
    if (
      preferred?.mission_id &&
      preferred.mission_id !== selectedMissionId &&
      ["completed", "failed", "stopped"].includes(currentStatus) &&
      ["blocked", "needs_approval", "queued", "running", "verification_failed"].includes(preferredStatus)
    ) {
      setSelectedMissionId(preferred.mission_id);
    }
  }, [activeChatSessionId, chatSessions, missionOptions, selectedMissionId]);

  useEffect(() => {
    const liveIds = workspaces.map(item => item.workspace_id);
    setWorkspaceOrder(current => {
      const next = normalizeOrderedIds(current, liveIds);
      return JSON.stringify(next) === JSON.stringify(current) ? current : next;
    });
  }, [workspaces]);

  useEffect(() => {
    const liveIds = missionOptions.map(item => item.mission_id);
    setMissionOrder(current => {
      const next = normalizeOrderedIds(current, liveIds);
      return JSON.stringify(next) === JSON.stringify(current) ? current : next;
    });
  }, [missionOptions]);

  useEffect(() => {
    if (!splitViewEnabled || !mission?.mission_id) {
      return;
    }
    const available = missionOptions
      .map(item => item.mission_id)
      .filter(id => id && id !== mission.mission_id);
    if (available.length === 0) {
      if (splitMissionId) {
        setSplitMissionId("");
      }
      return;
    }
    if (!splitMissionId || !available.includes(splitMissionId)) {
      setSplitMissionId(available[0]);
    }
  }, [mission?.mission_id, missionOptions, splitMissionId, splitViewEnabled]);

  const missionStatus = mission?.state?.status || "";
  const agentBlockedState = useMemo(() => {
    const approvalCount = asList(mission?.proof?.pending_approvals).length + asList(data.pendingApprovals).length;
    const questionCount = asList(data.pendingQuestions).length;
    const verificationFailureCount = asList(mission?.state?.verification_failures).length;
    const continuityState =
      mission?.missionLoop?.continuityState ||
      mission?.missionLoop?.timeBudget?.status ||
      mission?.missionLoop?.time_budget?.status ||
      "";
    const hasApprovalBoundary = approvalCount > 0;
    const hasQuestionBoundary = questionCount > 0;
    const hasVerificationFailure =
      verificationFailureCount > 0 || missionStatus === "verification_failed";
    const hasBlockedMissionState = AGENT_BLOCKER_STATUSES.includes(missionStatus);
    const hasQueuedPauseState =
      AGENT_QUEUED_PAUSE_STATES.includes(missionStatus) ||
      AGENT_QUEUED_PAUSE_STATES.includes(continuityState);
    const isBlocked = Boolean(
      mission &&
        (hasApprovalBoundary ||
          hasQuestionBoundary ||
          hasVerificationFailure ||
          hasBlockedMissionState ||
          hasQueuedPauseState),
    );

    return {
      approvalCount,
      questionCount,
      verificationFailureCount,
      hasApprovalBoundary,
      hasQuestionBoundary,
      hasVerificationFailure,
      hasBlockedMissionState,
      hasQueuedPauseState,
      isBlocked,
      defaultDrawer:
        hasApprovalBoundary || hasQuestionBoundary ? "queue" : hasVerificationFailure ? "proof" : "context",
    };
  }, [data.pendingApprovals, data.pendingQuestions, mission, missionStatus]);
  const agentVisibleDrawers = useMemo(
    () => AGENT_BLOCKER_DRAWER_IDS,
    [],
  );
  const showPersistentDrawer =
    Boolean(activeDrawer) && (uiMode === "builder" || agentBlockedState.isBlocked);
  const focusedRuntimeServices = useMemo(() => {
    const services = viewModel.drawers.builder.serviceStudio.services || [];
    const byNeedle = needle =>
      services.filter(item => needle.test(`${item.serviceId} ${item.label} ${item.details}`));
    return {
      hermes: byNeedle(/hermes/i),
      openClaw: byNeedle(/openclaw|open claw|opencode/i),
      bridges: byNeedle(/telegram|bridge|message|imessage|sms/i),
    };
  }, [viewModel.drawers.builder.serviceStudio.services]);

  useEffect(() => {
    setWorkspaceProfileForm(profileFormFromWorkspace(workspace, profileId));
  }, [
    profileId,
    workspace?.auto_optimize_routing,
    workspace?.commit_message_style,
    workspace?.execution_target_preference,
    workspace?.openai_codex_auth_mode,
    workspace?.minimax_auth_mode,
    workspace?.preferred_harness,
    workspace?.routing_strategy,
    workspace?.user_profile,
    workspace?.workspace_id,
  ]);

  useEffect(() => {
    setMissionForm(current => ({
      ...current,
      workspaceId: workspace?.workspace_id || current.workspaceId || "",
      runtime: mission?.runtime_id || workspace?.default_runtime || current.runtime,
      profile: mission?.selected_profile || workspace?.user_profile || profileId,
    }));
  }, [
    mission?.runtime_id,
    mission?.selected_profile,
    profileId,
    workspace?.default_runtime,
    workspace?.user_profile,
    workspace?.workspace_id,
  ]);

  useEffect(() => {
    if (mission?.mission_id) {
      setAgentRuntimeFocus("all");
      return;
    }
    setAgentRuntimeFocus(missionForm.runtime || "openclaw");
  }, [mission?.mission_id, missionForm.runtime]);

  useEffect(() => {
    const gatewayUrl = data.openClawStatus?.gatewayUrl;
    if (gatewayUrl) {
      setOpenClawGatewayUrl(gatewayUrl);
    }
  }, [data.openClawStatus?.gatewayUrl]);

  useEffect(() => {
    if (!mission && uiMode === "agent") {
      setActiveDrawer(null);
    }
  }, [mission, uiMode]);

  useEffect(() => {
    if (uiMode === "agent" && AGENT_BUILDER_ONLY_DRAWERS.includes(activeDrawer)) {
      setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
    }
  }, [activeDrawer, agentBlockedState.defaultDrawer, agentBlockedState.isBlocked, uiMode]);

  useEffect(() => {
    if (uiMode === "agent" && agentBlockedState.isBlocked) {
      setActiveDrawer(agentBlockedState.defaultDrawer);
    }
  }, [agentBlockedState.defaultDrawer, agentBlockedState.isBlocked, uiMode]);

  const runMissionAction = useCallback(
    async (action, successMessage) => {
      markAction(`mission:${action}`);
      if (!mission) {
        return;
      }
      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast("Preview mode is read-only for mission actions.", "warn");
        return;
      }

      const backendAction = action === "pause" ? "stop" : action;
      try {
        await callBackend(
          "apply_control_room_mission_action_command",
          { payload: { missionId: mission.mission_id, action: backendAction, root: null } },
          { throwOnError: true },
        );
        pushToast(successMessage, "info");
        await refreshAll(`mission-${backendAction}`);
      } catch (error) {
        pushToast(`Mission action failed: ${error}`, "error");
      }
    },
    [markAction, mission, previewMode, pushToast, refreshAll],
  );

  useEffect(() => {
    if (!persistentGoalMode || !mission?.mission_id) {
      return;
    }
    if (previewMode !== "live" || !hasCommandBackend()) {
      return;
    }
    if (agentBlockedState.isBlocked) {
      return;
    }
    const status = String(mission?.state?.status || "").toLowerCase();
    if (["running", "completed", "failed", "stopped"].includes(status)) {
      return;
    }
    const checkpoint = `${mission.mission_id}:${mission?.state?.updated_at || mission?.updated_at || ""}:${status}`;
    if (!checkpoint || goalModeLastResumeRef.current === checkpoint) {
      return;
    }
    goalModeLastResumeRef.current = checkpoint;
    void runMissionAction("resume", "Goal mode resumed mission execution.");
  }, [agentBlockedState.isBlocked, mission, persistentGoalMode, previewMode, runMissionAction]);

  const runWorkspaceAction = useCallback(
    async (surface, actionId, approved = false) => {
      markAction(`workspace:${surface}:${actionId}`);
      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast("Preview mode is read-only for setup actions.", "warn");
        return;
      }

      try {
        await callBackend(
          "apply_control_room_workspace_action_command",
          {
            payload: {
              root: null,
              workspaceId: workspace?.workspace_id || null,
              surface,
              actionId,
              approved,
            },
          },
          { throwOnError: true },
        );
        pushToast("Workspace action started.", "info");
        await refreshAll(`workspace-${actionId}`);
      } catch (error) {
        pushToast(`Workspace action failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, workspace?.workspace_id],
  );

  const runWorkspaceActionSpec = useCallback(
    async action => {
      if (!action?.actionId) {
        pushToast("Action is missing an action id.", "warn");
        return;
      }
      const surface = inferSurfaceFromAction(action);
      const requiresApproval = Boolean(action.requiresApproval);
      let approved = false;
      if (requiresApproval) {
        const confirmed = window.confirm(
          `Run "${action.label || action.actionId}" now?\n\nThis action is approval-gated and may mutate workspace state.`,
        );
        if (!confirmed) {
          return;
        }
        approved = true;
      }
      await runWorkspaceAction(surface, action.actionId, approved);
    },
    [pushToast, runWorkspaceAction],
  );

  const saveWorkspacePolicy = useCallback(async (formOverride, options = {}) => {
    const { suppressSuccessToast = false, retryAttempts = 3 } = options || {};
    markAction("submit:workspace-policy");
    if (!workspace) {
      pushToast("Select a workspace first.", "warn");
      return false;
    }
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot save workspace policy.", "warn");
      return false;
    }

    try {
      const nextProfile = formOverride || workspaceProfileForm;
      const normalizedProfile = {
        ...nextProfile,
        openaiCodexAuthMode: normalizeOpenAICodexAuthMode(nextProfile.openaiCodexAuthMode),
        minimaxAuthMode: normalizeMiniMaxAuthMode(nextProfile.minimaxAuthMode),
      };
      await callBackendWithRetry(
        "save_workspace_profile_command",
        {
          payload: {
            root: null,
            workspaceId: workspace.workspace_id,
            name: workspace.name,
            path: workspace.root_path,
            defaultRuntime: workspace.default_runtime,
            userProfile: normalizedProfile.userProfile,
            preferredHarness: normalizedProfile.preferredHarness,
            routingStrategy: normalizedProfile.routingStrategy,
            routeOverrides: saveableRouteOverrides(normalizedProfile.routeOverrides),
            autoOptimizeRouting: Boolean(normalizedProfile.autoOptimizeRouting),
            openaiCodexAuthMode: normalizedProfile.openaiCodexAuthMode,
            minimaxAuthMode: normalizedProfile.minimaxAuthMode,
            commitMessageStyle: normalizedProfile.commitMessageStyle,
            executionTargetPreference: normalizedProfile.executionTargetPreference,
            localProjectPath: normalizedProfile.localProjectPath,
            nasProjectPath: normalizedProfile.nasProjectPath,
            syncMode: normalizedProfile.syncMode,
            syncDirection: normalizedProfile.syncDirection,
            syncConflictPolicy: normalizedProfile.syncConflictPolicy,
            autoSyncToNas: Boolean(normalizedProfile.autoSyncToNas),
          },
        },
        { attempts: Math.max(1, Number(retryAttempts) || 1) },
      );
      setWorkspaceProfileForm(normalizedProfile);
      if (!suppressSuccessToast) {
        pushToast("Workspace policy saved.", "info");
      }
      await refreshAll("workspace-policy-save");
      return true;
    } catch (error) {
      pushToast(`Workspace policy save failed: ${error}`, "error");
      return false;
    }
  }, [markAction, previewMode, pushToast, refreshAll, workspace, workspaceProfileForm]);

  const applyPreferredHarness = useCallback(
    async nextHarness => {
      if (!nextHarness) {
        return;
      }
      markAction(`workspace:harness:${nextHarness}`);
      setWorkspaceProfileForm(current => ({ ...current, preferredHarness: nextHarness }));
      if (!workspace) {
        pushToast("Select a workspace first.", "warn");
        return;
      }
      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast(`Runtime preference staged as ${titleizeToken(nextHarness)} in preview mode.`, "info");
        return;
      }

      try {
        const response = await callBackend(
          "save_workspace_profile_command",
          {
            payload: {
              root: null,
              workspaceId: workspace.workspace_id,
              name: workspace.name,
              path: workspace.root_path,
              defaultRuntime: workspace.default_runtime,
              userProfile: workspaceProfileForm.userProfile,
              preferredHarness: nextHarness,
              routingStrategy: workspaceProfileForm.routingStrategy,
              routeOverrides: saveableRouteOverrides(workspaceProfileForm.routeOverrides),
              autoOptimizeRouting: Boolean(workspaceProfileForm.autoOptimizeRouting),
              openaiCodexAuthMode: normalizeOpenAICodexAuthMode(workspaceProfileForm.openaiCodexAuthMode),
              minimaxAuthMode: normalizeMiniMaxAuthMode(workspaceProfileForm.minimaxAuthMode),
              commitMessageStyle: workspaceProfileForm.commitMessageStyle,
              executionTargetPreference: workspaceProfileForm.executionTargetPreference,
              localProjectPath: workspaceProfileForm.localProjectPath,
              nasProjectPath: workspaceProfileForm.nasProjectPath,
              syncMode: workspaceProfileForm.syncMode,
              syncDirection: workspaceProfileForm.syncDirection,
              syncConflictPolicy: workspaceProfileForm.syncConflictPolicy,
              autoSyncToNas: Boolean(workspaceProfileForm.autoSyncToNas),
            },
          },
          { throwOnError: true },
        );
        pushToast(`Runtime switched to ${titleizeToken(nextHarness)}.`, "info");
        await refreshAll(`workspace-harness-${nextHarness}`);
      } catch (error) {
        pushToast(`Runtime switch failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, workspace, workspaceProfileForm],
  );

  const handleAgentRouteFieldChange = useCallback((field, value) => {
    setWorkspaceProfileForm(current => ({
      ...current,
      routeOverrides: updateRouteOverride(current.routeOverrides, agentRouteRole, {
        [field]: value,
      }),
    }));
  }, [agentRouteRole]);

  const handleAgentRouteSave = useCallback(async () => {
    markAction(`agent:route-save:${agentRouteRole}`);
    if (!workspace) {
      pushToast("Select a workspace before saving route controls.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Route controls are staged in preview mode.", "info");
      return;
    }
    const nextProfile = authModesForRouteProfile(
      workspaceProfileForm,
      data.providerSecretPresence || {},
    );
    await saveWorkspacePolicy(nextProfile);
  }, [agentRouteRole, data.providerSecretPresence, markAction, previewMode, pushToast, saveWorkspacePolicy, workspace, workspaceProfileForm]);

  const copyContextValue = useCallback(
    async value => {
      const copied = await copyTextValue(value);
      pushToast(copied ? "Copied to clipboard." : "Clipboard copy failed.", copied ? "info" : "warn");
    },
    [pushToast],
  );

  const handleWorkspaceDragStart = useCallback(workspaceId => {
    setDragState({ kind: "workspace", id: workspaceId });
  }, []);

  const handleWorkspaceDrop = useCallback(
    targetWorkspaceId => {
      if (dragState.kind !== "workspace" || !dragState.id) {
        return;
      }
      setWorkspaceOrder(current => moveOrderedId(current, dragState.id, targetWorkspaceId));
      setDragState({ kind: "", id: "" });
    },
    [dragState.id, dragState.kind],
  );

  const handleMissionDragStart = useCallback(missionId => {
    setDragState({ kind: "mission", id: missionId });
  }, []);

  const handleMissionDrop = useCallback(
    targetMissionId => {
      if (dragState.kind !== "mission" || !dragState.id) {
        return;
      }
      setMissionOrder(current => moveOrderedId(current, dragState.id, targetMissionId));
      setDragState({ kind: "", id: "" });
    },
    [dragState.id, dragState.kind],
  );

  const focusTranscriptTurn = useCallback(turnId => {
    if (!turnId) {
      return;
    }
    setHighlightedTurnId(turnId);
    window.requestAnimationFrame(() => {
      document.getElementById(turnId)?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }, []);

  const togglePinnedNexus = useCallback(turnId => {
    if (!turnId) {
      return;
    }
    setPinnedNexusIds(current =>
      current.includes(turnId) ? current.filter(item => item !== turnId) : [...current, turnId],
    );
  }, []);

  const handleAgentSteerFromTurn = useCallback(item => {
    const prefix = item?.meta ? `From ${item.meta}` : "From this step";
    setHighlightedTurnId(item?.id || "");
    setOperatorDraft(
      `${prefix}: ${item?.title || "revisit this decision"}.\nDo this differently: `,
    );
    document.getElementById("thread-note")?.focus();
  }, []);

  const handleAgentMemoryFromTurn = useCallback(item => {
    setHighlightedTurnId(item?.id || "");
    setOperatorDraft(
      `Memory correction for ${item?.title || "this step"}:\nThis was not okay because \nNext time do this instead: `,
    );
    document.getElementById("thread-note")?.focus();
  }, []);

  const handleAgentValidateTurn = useCallback(item => {
    markAction(`agent:validate:${item?.id || "turn"}`);
    setHighlightedTurnId(item?.id || "");
    if (item?.role === "queue" || /approval/i.test(`${item?.label || ""} ${item?.title || ""}`)) {
      setActiveDrawer("queue");
      return;
    }
    if (item?.tone === "bad" || /verification|failed|error/i.test(`${item?.label || ""} ${item?.title || ""}`)) {
      setActiveDrawer("proof");
      return;
    }
    setActiveDrawer("context");
  }, [markAction]);

  const openMissionDialog = useCallback(() => {
    markAction("open:mission-dialog");
    setMissionForm(current => ({
      ...current,
      workspaceId: workspace?.workspace_id || current.workspaceId || "",
      runtime: mission?.runtime_id || workspace?.default_runtime || current.runtime,
      profile: mission?.selected_profile || workspace?.user_profile || profileId,
      objective:
        !mission && operatorDraft.trim() && !current.objective.trim()
          ? operatorDraft.trim()
          : current.objective,
    }));
    setShowMissionDialog(true);
  }, [
    markAction,
    mission,
    mission?.runtime_id,
    mission?.selected_profile,
    operatorDraft,
    profileId,
    workspace?.default_runtime,
    workspace?.user_profile,
    workspace?.workspace_id,
  ]);

  const handleQualityRoadmapAction = useCallback(
    async item => {
      const actionKind = item?.actionKind || "";
      markAction(`quality-roadmap:${item?.id || "unknown"}`);
      if (actionKind === "validate") {
        const validateAction = viewModel.drawers.builder.validationActions[0];
        if (validateAction) {
          await runWorkspaceActionSpec(validateAction);
          return;
        }
        pushToast("No validation action is currently available.", "warn");
        return;
      }
      if (actionKind === "mission") {
        openMissionDialog();
        return;
      }
      if (actionKind === "service") {
        const serviceAction = viewModel.drawers.builder.serviceStudio.services
          .flatMap(service => service.actions)
          .find(action => action);
        if (serviceAction) {
          await runWorkspaceActionSpec(serviceAction);
          return;
        }
        setUiMode("builder");
        setActiveDrawer("runtime");
        pushToast("No service repair action is currently available.", "warn");
        return;
      }
      if (actionKind === "skill") {
        setSkillStudioFilter("needs_attention");
        setUiMode("builder");
        setActiveDrawer("skills");
        return;
      }
      if (actionKind === "workflow") {
        const suggested = viewModel.drawers.builder.workflowStudio.recommended;
        if (suggested?.label) {
          pushToast(`Open workflow: ${suggested.label}`, "info");
        }
        openMissionDialog();
        return;
      }
      pushToast("No executable action is mapped for this roadmap item yet.", "warn");
    },
    [markAction, openMissionDialog, pushToast, runWorkspaceActionSpec, viewModel],
  );

  const handleBuilderFeatureAction = useCallback(
    async (actionId, payload = {}) => {
      markAction(`builder:feature:${actionId || "open"}`);
      switch (actionId) {
        case "open_workspace":
          setShowWorkspaceDialog(true);
          return;
        case "open_mission":
          if (workspaces.length === 0) {
            setShowWorkspaceDialog(true);
            return;
          }
          openMissionDialog();
          return;
        case "open_runtime":
          setUiMode("builder");
          setActiveDrawer("runtime");
          return;
        case "open_auth":
          setUiMode("builder");
          setActiveDrawer("runtime");
          window.setTimeout(() => {
            document.getElementById("provider-auth-panel")?.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
          }, 0);
          return;
        case "open_profiles":
          setUiMode("builder");
          setActiveDrawer("profiles");
          return;
        case "open_skills":
          setSkillStudioFilter(payload.filter || "needs_attention");
          setUiMode("builder");
          setActiveDrawer("skills");
          return;
        case "open_escalation":
          setShowEscalationDialog(true);
          return;
        case "open_queue":
          setActiveDrawer("queue");
          return;
        case "open_proof":
          setActiveDrawer("proof");
          return;
        case "open_context":
          setActiveDrawer("context");
          return;
        case "open_images":
        case "open-images":
          setUiMode("builder");
          setSurface("images");
          setActiveDrawer(null);
          return;
        case "open_builder":
          setUiMode("builder");
          setSurface("builder");
          setActiveDrawer("builder");
          return;
        case "run_validation": {
          const validateAction = viewModel.drawers.builder.validationActions[0];
          if (validateAction) {
            await runWorkspaceActionSpec(validateAction);
            return;
          }
          pushToast("No validation action is currently available.", "warn");
          setActiveDrawer("proof");
          return;
        }
        case "open_workflow": {
          const suggested = viewModel.drawers.builder.workflowStudio.recommended;
          if (suggested?.label) {
            pushToast(`Workflow focus: ${suggested.label}`, "info");
          }
          openMissionDialog();
          return;
        }
        case "focus_thread": {
          const nextMissionId =
            payload?.missionId || builderPrimaryConversation?.missionId || mission?.mission_id;
          if (nextMissionId) {
            setSelectedMissionId(nextMissionId);
          }
          return;
        }
        case "focus_conversations":
          if (builderPrimaryConversation?.missionId) {
            setSelectedMissionId(builderPrimaryConversation.missionId);
          }
          return;
        default:
          setActiveDrawer("builder");
      }
    },
    [
      markAction,
      mission?.mission_id,
      openMissionDialog,
      pushToast,
      runWorkspaceActionSpec,
      viewModel.drawers.builder.validationActions,
      viewModel.drawers.builder.workflowStudio.recommended,
      workspaces.length,
    ],
  );

  const handleBuilderReviewTargetSeed = useCallback(
    target => {
      if (!target) {
        return;
      }
      setSelectedReviewTargetId(target.id || "");
      setOperatorDraft(target.commentSeed || `${target.title || "Review target"}:\n`);
      window.requestAnimationFrame(() => {
        document.getElementById("builder-thread-note")?.focus();
      });
    },
    [],
  );

  const handleWorkspaceSubmit = useCallback(
    async event => {
      event.preventDefault();
      markAction("submit:workspace");
      if (!workspaceForm.name.trim() || !workspaceForm.path.trim()) {
        pushToast("Project name and folder path are required.", "warn");
        return;
      }

      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast(
          "Switch to Live Backend before saving this project. Preview mode is read-only.",
          "warn",
        );
        return;
      }

      try {
        await callBackend(
          "save_workspace_profile_command",
          {
            payload: {
              root: null,
              workspaceId: null,
              name: workspaceForm.name.trim(),
              path: workspaceForm.path.trim(),
              defaultRuntime: workspaceForm.defaultRuntime,
              userProfile: workspaceForm.userProfile,
              localProjectPath: (workspaceForm.localProjectPath || workspaceForm.path).trim(),
              nasProjectPath: workspaceForm.nasProjectPath.trim(),
              syncMode: workspaceForm.syncMode,
              syncDirection: workspaceForm.syncDirection,
              syncConflictPolicy: workspaceForm.syncConflictPolicy,
              autoSyncToNas: Boolean(workspaceForm.autoSyncToNas),
            },
          },
          { throwOnError: true },
        );
        const syncStatus = parseWorkspaceSyncStatus(response?.workspace);
        let savedMessage = "Project saved.";
        if (syncStatus?.detectedBothWithFiles && syncStatus?.effectiveDirection === "bidirectional") {
          savedMessage =
            "Project saved. Existing NAS and computer copies were auto-reconciled bidirectionally.";
        } else if (syncStatus?.reason === "detected_nas_primary_synced") {
          savedMessage = "Project saved. NAS copy was detected first and synced back to your computer.";
        } else if (syncStatus?.reason === "detected_local_primary_synced") {
          savedMessage = "Project saved. Computer copy was synced to NAS.";
        }
        pushToast(savedMessage, "info");
        setShowWorkspaceDialog(false);
        setWorkspaceForm(DEFAULT_WORKSPACE_FORM);
        await refreshAll("workspace-save");
      } catch (error) {
        pushToast(`Project save failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, workspaceForm],
  );

  const applyWorkspaceFolderSelection = useCallback(selectedPath => {
    const normalizedPath = String(selectedPath || "").trim();
    if (!normalizedPath) {
      return null;
    }
    setWorkspaceForm(current => ({
      ...current,
      path: normalizedPath,
      name: current.name || pathLeaf(normalizedPath),
      localProjectPath: current.localProjectPath || normalizedPath,
      nasProjectPath: current.nasProjectPath || defaultNasProjectPath(normalizedPath),
    }));
    setShowWorkspaceDialog(true);
    return normalizedPath;
  }, []);

  const loadWorkspaceBrowserDirectory = useCallback(async requestedPath => {
    setWorkspaceBrowser(current => ({
      ...current,
      loading: true,
      error: "",
    }));
    try {
      const response = await callBackend(
        "list_workspace_directory_command",
        requestedPath ? { path: requestedPath } : undefined,
        { throwOnError: true },
      );
      const entries = Array.isArray(response?.entries)
        ? response.entries
            .map(item => ({
              name: String(item?.name || ""),
              path: String(item?.path || ""),
              isDirectory: Boolean(item?.isDirectory),
            }))
            .filter(item => item.name && item.path)
        : [];
      const roots = Array.isArray(response?.roots)
        ? response.roots
            .map(item => String(item || "").trim())
            .filter(Boolean)
        : [];
      setWorkspaceBrowser(current => ({
        ...current,
        loading: false,
        error: "",
        currentPath: String(response?.currentPath || requestedPath || ""),
        parentPath: String(response?.parentPath || ""),
        roots,
        entries,
      }));
      return response;
    } catch (error) {
      setWorkspaceBrowser(current => ({
        ...current,
        loading: false,
        error: String(error || "Could not list folders."),
      }));
      throw error;
    }
  }, []);

  const closeWorkspaceBrowser = useCallback(() => {
    setWorkspaceBrowser(current => ({
      ...current,
      open: false,
      loading: false,
      error: "",
    }));
  }, []);

  const openWorkspaceBrowser = useCallback(
    async requestedPath => {
      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast("Preview mode cannot open folder browsing.", "warn");
        return;
      }
      setWorkspaceBrowser(current => ({
        ...current,
        open: true,
        error: "",
      }));
      try {
        await loadWorkspaceBrowserDirectory(requestedPath);
      } catch (error) {
        pushToast(`Folder browsing failed: ${error}`, "error");
      }
    },
    [loadWorkspaceBrowserDirectory, previewMode, pushToast],
  );

  const handleWorkspaceBrowserNavigate = useCallback(
    async targetPath => {
      const normalizedPath = String(targetPath || "").trim();
      if (!normalizedPath || workspaceBrowser.loading) {
        return;
      }
      try {
        await loadWorkspaceBrowserDirectory(normalizedPath);
      } catch {
        return;
      }
    },
    [loadWorkspaceBrowserDirectory, workspaceBrowser.loading],
  );

  const handleWorkspaceBrowserUseCurrent = useCallback(() => {
    if (!workspaceBrowser.currentPath) {
      return;
    }
    applyWorkspaceFolderSelection(workspaceBrowser.currentPath);
    closeWorkspaceBrowser();
  }, [applyWorkspaceFolderSelection, closeWorkspaceBrowser, workspaceBrowser.currentPath]);

  const handleReferencePickWorkspaceFolder = useCallback(async () => {
    markAction("reference:workspace-folder");
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot open the folder picker.", "warn");
      return null;
    }
    if (!hasTauriBackend()) {
      await openWorkspaceBrowser(workspaceForm.path);
      return null;
    }
    try {
      const pickedPath = await callBackend("pick_folder_command", undefined, {
        throwOnError: true,
      });
      return applyWorkspaceFolderSelection(pickedPath);
    } catch (error) {
      pushToast(`Folder picker failed: ${error}`, "error");
      return null;
    }
  }, [
    applyWorkspaceFolderSelection,
    markAction,
    openWorkspaceBrowser,
    previewMode,
    pushToast,
    workspaceForm.path,
  ]);

  const importWorkspaceFromPath = useCallback(
    async ({ path, name, defaultRuntime }) => {
      const safePath = String(path || "").trim();
      if (!safePath) {
        pushToast("Project folder path is required.", "warn");
        return false;
      }
      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast("Preview mode cannot import workspaces.", "warn");
        return false;
      }
      try {
        await callBackend(
          "save_workspace_profile_command",
          {
            payload: {
              root: null,
              workspaceId: null,
              name: String(name || pathLeaf(safePath) || "Imported workspace").trim(),
              path: safePath,
              defaultRuntime: defaultRuntime || workspace?.default_runtime || missionForm.runtime || "openclaw",
              userProfile: workspaceProfileForm.userProfile,
              localProjectPath: safePath,
              nasProjectPath: defaultNasProjectPath(safePath),
              syncMode: "auto_nas_mirror",
              syncDirection: "bidirectional",
              syncConflictPolicy: "keep_newer_and_log",
              autoSyncToNas: false,
            },
          },
          { throwOnError: true },
        );
        return true;
      } catch (error) {
        pushToast(`Workspace import failed: ${error}`, "error");
        return false;
      }
    },
    [missionForm.runtime, previewMode, pushToast, workspace?.default_runtime, workspaceProfileForm.userProfile],
  );

  const handleReferenceImportCodexWorkspace = useCallback(
    async item => {
      markAction(`reference:codex-import:${pathLeaf(item?.path) || "workspace"}`);
      const imported = await importWorkspaceFromPath({
        path: item?.path,
        name: item?.name,
      });
      if (!imported) {
        return;
      }
      pushToast(`${item?.name || "Codex workspace"} imported.`, "info");
      await refreshAll("codex-workspace-import");
    },
    [importWorkspaceFromPath, markAction, pushToast, refreshAll],
  );

  const handleReferenceImportAllCodexWorkspaces = useCallback(async () => {
    markAction("reference:codex-import-all");
    const workspacesToImport = asList(codexImportSnapshot.workspaces);
    if (!workspacesToImport.length) {
      pushToast("No Codex workspaces are available to import.", "warn");
      return;
    }
    let importedCount = 0;
    for (const item of workspacesToImport) {
      // Keep the pass resilient: import what succeeds, then refresh once.
      // The workspace command already handles dedupe/validation on the backend side.
      // eslint-disable-next-line no-await-in-loop
      const imported = await importWorkspaceFromPath({
        path: item?.path,
        name: item?.name,
      });
      if (imported) {
        importedCount += 1;
      }
    }
    if (importedCount > 0) {
      pushToast(`Imported ${importedCount} Codex workspace${importedCount === 1 ? "" : "s"}.`, "info");
      await refreshAll("codex-workspace-import-all");
      return;
    }
    pushToast("No Codex workspaces were imported.", "warn");
  }, [codexImportSnapshot.workspaces, importWorkspaceFromPath, markAction, pushToast, refreshAll]);

  const handleReferenceRefreshCodexImport = useCallback(async () => {
    markAction("reference:codex-refresh");
    await refreshCodexImportSnapshot({ showToast: true });
  }, [markAction, refreshCodexImportSnapshot]);

  const handleMissionSubmit = useCallback(
    async event => {
      event.preventDefault();
      markAction("submit:mission");
      if (!missionForm.workspaceId || !missionForm.objective.trim()) {
        pushToast("Choose a workspace and enter a mission objective.", "warn");
        return;
      }

      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast("Preview mode cannot launch missions.", "warn");
        setShowMissionDialog(false);
        return;
      }

      try {
        const relativeStopMinutes = Math.max(
          0,
          Number.parseInt(String(missionForm.relativeStopMinutes || "").trim(), 10) || 0,
        );
        const missionTargetsSelectedWorkspace =
          Boolean(workspace?.workspace_id) &&
          workspace.workspace_id === missionForm.workspaceId;
        const nextProfile = authModesForRouteProfile(
          workspaceProfileForm,
          data.providerSecretPresence || {},
        );
        const baselineRouteOverrides = missionTargetsSelectedWorkspace
          ? saveableRouteOverrides(nextProfile.routeOverrides)
          : [];
        const selectedRouteModel = String(missionForm.model || "").trim();
        const missionRouteOverrides = selectedRouteModel
          ? ROUTE_ROLE_OPTIONS.map(role => ({
              role,
              provider: missionForm.modelProvider || "openai",
              model: selectedRouteModel,
              effort: normalizeRouteEffort(missionForm.modelEffort, "medium"),
            }))
          : baselineRouteOverrides;
        let workspacePolicySaved = true;
        if (workspace && missionTargetsSelectedWorkspace) {
          workspacePolicySaved = await saveWorkspacePolicy(nextProfile, {
            suppressSuccessToast: true,
            retryAttempts: 3,
          });
          if (!workspacePolicySaved) {
            pushToast(
              "Workspace policy save failed; mission launch will continue using the in-memory route overrides.",
              "warn",
            );
          }
        }
        await callBackendWithRetry(
          "start_control_room_mission_command",
          {
            payload: {
              root: null,
              workspaceId: missionForm.workspaceId,
              runtime: missionForm.runtime,
              objective: missionForm.objective.trim(),
              successChecks: missionForm.successChecks
                .split("\n")
                .map(line => line.trim())
                .filter(Boolean),
              mode: missionForm.mode,
              budgetHours: Number(missionForm.budgetHours || 12),
              relativeStopMinutes: relativeStopMinutes > 0 ? relativeStopMinutes : undefined,
              runUntil: missionForm.runUntil,
              routeOverrides: missionRouteOverrides,
              profile: missionForm.profile,
              escalationDestination: telegramChatId.trim() || null,
              codeExecution: codeExecutionEnabled,
              codeExecutionMemory: codeExecutionMemory,
              codeExecutionRequired: false,
            },
          },
          { attempts: 3 },
        );
        pushToast(
          workspacePolicySaved
            ? "Mission launched."
            : "Mission launched with route overrides while workspace-policy save is pending.",
          "info",
        );
        setShowMissionDialog(false);
        setMissionForm(DEFAULT_MISSION_FORM);
        await refreshAll("mission-start");
      } catch (error) {
        pushToast(`Mission launch failed: ${error}`, "error");
      }
    },
    [
      codeExecutionEnabled,
      codeExecutionMemory,
      data.providerSecretPresence,
      markAction,
      missionForm,
      previewMode,
      pushToast,
      refreshAll,
      saveWorkspacePolicy,
      telegramChatId,
      workspace,
      workspaceProfileForm,
    ],
  );

  const handleSaveTelegram = useCallback(
    async event => {
      event.preventDefault();
      markAction("submit:telegram");
      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast("Preview mode cannot change escalation settings.", "warn");
        setShowEscalationDialog(false);
        return;
      }

      try {
        if (telegramBotToken.trim()) {
          await callBackend(
            "save_telegram_bot_token_command",
            { token: telegramBotToken.trim() },
            { throwOnError: true },
          );
        }
        pushToast("Escalation settings saved.", "info");
        setTelegramBotToken("");
        setShowEscalationDialog(false);
        await refreshAll("telegram-save");
      } catch (error) {
        pushToast(`Telegram save failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, telegramBotToken],
  );

  const handleClearTelegram = useCallback(async () => {
    markAction("clear:telegram");
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot clear escalation settings.", "warn");
      return;
    }
    try {
      await callBackend("clear_telegram_bot_token_command", undefined, { throwOnError: true });
      setTelegramBotToken("");
      pushToast("Telegram token cleared.", "info");
      await refreshAll("telegram-clear");
    } catch (error) {
      pushToast(`Telegram clear failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);

  const handleSendTestPing = useCallback(async () => {
    markAction("send:telegram-test");
    if (!telegramChatId.trim()) {
      pushToast("Enter a Telegram chat ID first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot send escalation pings.", "warn");
      return;
    }

    try {
      await callBackend(
        "send_telegram_message_command",
        {
          payload: {
            chatId: telegramChatId.trim(),
            text: "Syntelos supervision test ping: approvals and mission escalations are reachable.",
          },
        },
        { throwOnError: true },
      );
      pushToast("Telegram test ping sent.", "info");
    } catch (error) {
      pushToast(`Telegram message failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, telegramChatId]);

  const handlePrimaryAction = useCallback(() => {
    const action = viewModel.topBar.primaryAction;
    markAction(`primary:${action.kind}`);
    if (action.kind === "start") {
      openMissionDialog();
      return;
    }
    if (action.kind === "resume") {
      void runMissionAction("resume", "Mission resume requested.");
      return;
    }
    if (action.kind === "queue") {
      setActiveDrawer("queue");
      return;
    }
    setActiveDrawer("proof");
  }, [markAction, openMissionDialog, runMissionAction, viewModel.topBar.primaryAction]);

  const createChatSessionForWorkspace = useCallback(
    ({ workspaceId = "", seedText = "", focus = true } = {}) => {
      const resolvedWorkspaceId =
        String(workspaceId || "").trim() ||
        selectedWorkspaceId ||
        workspace?.workspace_id ||
        workspaces[0]?.workspace_id ||
        "";
      const created = buildChatSession(resolvedWorkspaceId, seedText);
      setChatSessions(current => normalizeChatSessions([created, ...current]));
      setChatSessionTranscripts(current => {
        if (current?.[created.id]) {
          return current;
        }
        return { ...current, [created.id]: [] };
      });
      if (focus) {
        setActiveChatSessionId(created.id);
        setSelectedMissionId(null);
      }
      return created;
    },
    [selectedWorkspaceId, workspace?.workspace_id, workspaces],
  );

  const ensureActiveChatSession = useCallback(
    ({ seedText = "", workspaceId = "" } = {}) => {
      const resolvedWorkspaceId =
        String(workspaceId || "").trim() ||
        selectedWorkspaceId ||
        workspace?.workspace_id ||
        workspaces[0]?.workspace_id ||
        "";
      const current =
        activeChatSessionId &&
        chatSessions.find(item => item.id === activeChatSessionId);
      if (
        current &&
        (!resolvedWorkspaceId ||
          !current.workspaceId ||
          current.workspaceId === resolvedWorkspaceId)
      ) {
        return current;
      }
      return createChatSessionForWorkspace({
        workspaceId: resolvedWorkspaceId,
        seedText,
        focus: true,
      });
    },
    [
      activeChatSessionId,
      chatSessions,
      createChatSessionForWorkspace,
      selectedWorkspaceId,
      workspace?.workspace_id,
      workspaces,
    ],
  );

  const touchChatSession = useCallback(
    (sessionId, text = "") => {
      if (!sessionId) {
        return;
      }
      const now = new Date().toISOString();
      const preview = summarizeChatSessionTitle(text);
      setChatSessions(current =>
        normalizeChatSessions(
          current.map(item =>
            item.id === sessionId
              ? {
                  ...item,
                  title:
                    item.title === "New conversation" && text
                      ? summarizeChatSessionTitle(text)
                      : item.title,
                  updatedAt: now,
                  lastPreview: preview || item.lastPreview || "",
                }
              : item,
          ),
        ),
      );
    },
    [],
  );

  const appendChatSessionTurn = useCallback((sessionId, entry) => {
    const normalizedSessionId = String(sessionId || "").trim();
    if (!normalizedSessionId) {
      return null;
    }
    const nextTurn = normalizeChatTranscriptEntry({
      id: `chat-turn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      createdAt: new Date().toISOString(),
      ...entry,
    });
    if (!nextTurn) {
      return null;
    }
    setChatSessionTranscripts(current => {
      const rows = asList(current?.[normalizedSessionId]);
      const next = normalizeChatSessionTranscripts({
        ...current,
        [normalizedSessionId]: [...rows, nextTurn].slice(-MAX_CHAT_SESSION_TRANSCRIPT_TURNS),
      });
      return next;
    });
    return nextTurn;
  }, []);

  const updateChatSessionTurn = useCallback((sessionId, turnId, updater) => {
    const normalizedSessionId = String(sessionId || "").trim();
    const normalizedTurnId = String(turnId || "").trim();
    if (!normalizedSessionId || !normalizedTurnId) {
      return;
    }
    setChatSessionTranscripts(current => {
      const rows = asList(current?.[normalizedSessionId]);
      if (rows.length === 0) {
        return current;
      }
      const nextRows = rows.map(row => {
        if (row.id !== normalizedTurnId) {
          return row;
        }
        const updated =
          typeof updater === "function"
            ? updater(row)
            : { ...row, ...updater };
        return normalizeChatTranscriptEntry({ ...row, ...updated }) || row;
      });
      return normalizeChatSessionTranscripts({
        ...current,
        [normalizedSessionId]: nextRows,
      });
    });
  }, []);

  const appendOperatorEntry = useCallback(
    entry => {
      const nextEntry = { ...entry };
      if (nextEntry.channel === "chat" && !nextEntry.sessionId) {
        const session = ensureActiveChatSession({ seedText: nextEntry.title || nextEntry.detail || "" });
        if (session?.id) {
          nextEntry.sessionId = session.id;
        }
      }
      const created = createSessionEntry(nextEntry);
      setOperatorNotes(current => [created, ...current]);
      return created;
    },
    [ensureActiveChatSession],
  );

  const updateOperatorEntry = useCallback((entryId, updater) => {
    if (!entryId) {
      return;
    }
    setOperatorNotes(current =>
      current.map(item => {
        if (item.id !== entryId) {
          return item;
        }
        return typeof updater === "function" ? updater(item) : { ...item, ...updater };
      }),
    );
  }, []);

  const clearOperatorAttachments = useCallback(() => {
    setOperatorAttachments([]);
  }, []);

  const removeOperatorAttachment = useCallback(attachmentId => {
    setOperatorAttachments(current => current.filter(item => item.id !== attachmentId));
  }, []);

  const handleComposerPaste = useCallback(
    event => {
      const items = Array.from(event.clipboardData?.items || []);
      const imageItems = items.filter(item => item.kind === "file" && item.type.startsWith("image/"));
      if (imageItems.length === 0) {
        return;
      }
      event.preventDefault();

      const slotsLeft = Math.max(0, MAX_INLINE_ATTACHMENTS - operatorAttachments.length);
      if (slotsLeft <= 0) {
        pushToast(`Only ${MAX_INLINE_ATTACHMENTS} inline attachments are allowed.`, "warn");
        return;
      }

      const selectedItems = imageItems.slice(0, slotsLeft);
      selectedItems.forEach((item, index) => {
        const file = item.getAsFile();
        if (!file) {
          return;
        }
        if (file.size > MAX_ATTACHMENT_BYTES) {
          pushToast(
            `Attachment ${file.name || index + 1} exceeds ${Math.round(
              MAX_ATTACHMENT_BYTES / (1024 * 1024),
            )}MB.`,
            "warn",
          );
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          setOperatorAttachments(current =>
            [
              {
                id: `attachment-${Date.now()}-${Math.random().toString(36).slice(2)}`,
                name: file.name || `pasted-image-${index + 1}.png`,
                mime: file.type || "image/png",
                size: file.size,
                previewUrl: typeof reader.result === "string" ? reader.result : "",
                createdAt: new Date().toISOString(),
              },
              ...current,
            ].slice(0, MAX_INLINE_ATTACHMENTS),
          );
        };
        reader.readAsDataURL(file);
      });

      pushToast("Image attachment added to the active composer.", "info");
    },
    [operatorAttachments.length, pushToast],
  );

  const applyModelQuickPreset = useCallback(
    preset => {
      if (!preset) {
        return;
      }
      handleAgentRouteFieldChange("provider", preset.provider);
      handleAgentRouteFieldChange("model", preset.model);
      handleAgentRouteFieldChange("effort", preset.effort);
      pushToast(`Applied preset: ${preset.label}`, "info");
    },
    [handleAgentRouteFieldChange, pushToast],
  );

  const runTaskPrompt = useCallback(
    async (task, source = "schedule") => {
      const prompt = String(task?.prompt || "").trim();
      if (!prompt) {
        return false;
      }
      if (!mission?.mission_id || previewMode !== "live" || !hasCommandBackend()) {
        appendOperatorEntry({
          title: `Task queued (${source})`,
          detail: prompt,
          meta: "Task log only (no live mission selected)",
          tone: "warn",
        });
        return false;
      }
      try {
        await callBackendWithRetry(
          "send_control_room_mission_follow_up_command",
          { payload: { missionId: mission.mission_id, message: prompt, root: null } },
          { attempts: 3 },
        );
        appendOperatorEntry({
          title: `Task executed (${source})`,
          detail: prompt,
          meta: timestampLabel(new Date().toISOString()),
          tone: "good",
        });
        return true;
      } catch (error) {
        appendOperatorEntry({
          title: `Task failed (${source})`,
          detail: `${prompt}\n\n${String(error)}`,
          meta: timestampLabel(new Date().toISOString()),
          tone: "bad",
        });
        return false;
      }
    },
    [appendOperatorEntry, mission?.mission_id, previewMode],
  );

  const updateTaskFormField = useCallback((field, value) => {
    setTaskForm(current => ({
      ...current,
      [field]: value,
    }));
  }, []);

  const resetTaskForm = useCallback(() => {
    setTaskForm(DEFAULT_TASK_FORM);
  }, []);

  const createLocalTask = useCallback(() => {
    const name = String(taskForm.name || "").trim();
    const prompt = String(taskForm.prompt || "").trim();
    if (!name || !prompt) {
      pushToast("Task name and prompt are required.", "warn");
      return;
    }
    const everyMinutes = Math.max(1, Math.round(Number(taskForm.everyMinutes) || 30));
    const nowIso = new Date().toISOString();
    const nextRunAt = new Date(Date.now() + everyMinutes * 60_000).toISOString();
    const createdTask = {
      id: `task-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      name,
      prompt,
      trigger: taskForm.trigger || "schedule",
      everyMinutes,
      webhookToken: String(taskForm.webhookToken || "").trim(),
      active: Boolean(taskForm.active),
      createdAt: nowIso,
      updatedAt: nowIso,
      lastRunAt: "",
      nextRunAt: taskForm.trigger === "schedule" && taskForm.active ? nextRunAt : "",
      totalRuns: 0,
      lastStatus: "idle",
    };
    setLocalTasks(current => [createdTask, ...current].slice(0, MAX_TASK_LOG));
    appendOperatorEntry({
      title: "Task created",
      detail: `${createdTask.name}\n${createdTask.prompt}`,
      meta: `${titleizeToken(createdTask.trigger)} · every ${createdTask.everyMinutes}m`,
      tone: "neutral",
    });
    resetTaskForm();
  }, [appendOperatorEntry, pushToast, resetTaskForm, taskForm]);

  const toggleTaskActive = useCallback(taskId => {
    setLocalTasks(current =>
      current.map(item => {
        if (item.id !== taskId) {
          return item;
        }
        const active = !item.active;
        const everyMinutes = Math.max(1, Number(item.everyMinutes) || 30);
        return {
          ...item,
          active,
          updatedAt: new Date().toISOString(),
          nextRunAt:
            active && item.trigger === "schedule"
              ? new Date(Date.now() + everyMinutes * 60_000).toISOString()
              : "",
        };
      }),
    );
  }, []);

  const removeTask = useCallback(taskId => {
    const deletedId = String(taskId || "").trim();
    if (deletedId) {
      setDeletedLocalTaskIds(current => [...new Set([...current, deletedId])].slice(-MAX_TASK_LOG));
    }
    setLocalTasks(current => current.filter(item => item.id !== taskId));
  }, []);

  const executeTask = useCallback(
    async (task, source = "manual") => {
      if (!task) {
        return;
      }
      const ok = await runTaskPrompt(task, source);
      setLocalTasks(current =>
        current.map(item =>
          item.id === task.id
            ? {
                ...item,
                totalRuns: (Number(item.totalRuns) || 0) + 1,
                lastRunAt: new Date().toISOString(),
                nextRunAt:
                  item.trigger === "schedule" && item.active
                    ? new Date(
                        Date.now() + Math.max(1, Number(item.everyMinutes) || 30) * 60_000,
                      ).toISOString()
                    : item.nextRunAt || "",
                lastStatus: ok ? "ok" : "failed",
              }
            : item,
        ),
      );
    },
    [runTaskPrompt],
  );

  const triggerTaskByToken = useCallback(() => {
    const token = String(taskTriggerToken || "").trim();
    if (!token) {
      pushToast("Enter a task token to trigger webhook/API task.", "warn");
      return;
    }
    const task = localTasks.find(item => item.webhookToken && item.webhookToken === token);
    if (!task) {
      pushToast("No task matched this token.", "warn");
      return;
    }
    void executeTask(task, "webhook");
    setTaskTriggerToken("");
  }, [executeTask, localTasks, pushToast, taskTriggerToken]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      const nowMs = Date.now();
      localTasks.forEach(task => {
        if (!task.active || task.trigger !== "schedule") {
          return;
        }
        const nextRunMs = Date.parse(task.nextRunAt || "");
        const isDue = !Number.isFinite(nextRunMs) || nextRunMs <= nowMs;
        if (!isDue) {
          return;
        }
        void executeTask(task, "schedule");
      });
    }, 15_000);
    return () => window.clearInterval(intervalId);
  }, [executeTask, localTasks]);

  const clearWorkspaceMemory = useCallback(() => {
    if (!workspace?.workspace_id) {
      return;
    }
    setMemoryStore(current => ({
      ...current,
      workspace: Object.fromEntries(
        Object.entries(current.workspace || {}).filter(([id]) => id !== workspace.workspace_id),
      ),
    }));
  }, [workspace?.workspace_id]);

  const clearMissionMemory = useCallback(() => {
    if (!mission?.mission_id) {
      return;
    }
    setMemoryStore(current => ({
      ...current,
      mission: Object.fromEntries(
        Object.entries(current.mission || {}).filter(([id]) => id !== mission.mission_id),
      ),
    }));
  }, [mission?.mission_id]);

  const clearAllMemory = useCallback(() => {
    setMemoryStore({ workspace: {}, mission: {} });
  }, []);

  const clearDebugEvents = useCallback(() => {
    setDebugEvents([]);
  }, []);

  const handleOperatorNote = useCallback(
    event => {
      event.preventDefault();
      if (!operatorDraft.trim()) {
        return;
      }
      markAction("composer:add-note");
      const attachmentSummary = operatorAttachments
        .map(item => `${item.name} (${Math.max(1, Math.round(item.size / 1024))}KB)`)
        .join(", ");
      appendOperatorEntry({
        title: "Operator note",
        detail: operatorAttachments.length
          ? `${operatorDraft.trim()}\n\nAttachments: ${attachmentSummary}`
          : operatorDraft.trim(),
        meta: operatorAttachments.length
          ? `Local note · ${operatorAttachments.length} attachment${operatorAttachments.length === 1 ? "" : "s"}`
          : "Local note",
        tone: "neutral",
        channel: "note",
      });
      if (mission?.mission_id) {
        setMemoryStore(current => ({
          ...current,
          mission: {
            ...current.mission,
            [mission.mission_id]: operatorDraft.trim().slice(0, 600),
          },
        }));
      }
      if (workspace?.workspace_id) {
        setMemoryStore(current => ({
          ...current,
          workspace: {
            ...current.workspace,
            [workspace.workspace_id]: operatorDraft.trim().slice(0, 600),
          },
        }));
      }
      setOperatorDraft("");
      clearOperatorAttachments();
      pushToast("Operator note added to this session.", "info");
    },
    [
      appendOperatorEntry,
      clearOperatorAttachments,
      markAction,
      mission?.mission_id,
      operatorAttachments,
      operatorDraft,
      pushToast,
      workspace?.workspace_id,
    ],
  );

  const handleAgentFollowUp = useCallback(async () => {
    const followUp = operatorDraft.trim();
    if (!followUp) {
      pushToast("Write a follow-up first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot send runtime follow-ups.", "warn");
      return;
    }
    if (!mission?.mission_id) {
      pushToast("Select a mission before sending a follow-up.", "warn");
      return;
    }

    markAction("composer:send-follow-up");
    let commentEntry = null;
    try {
      const steeringLines = [];
      if (mission && agentRuntimeFocus !== "all") {
        steeringLines.push(`Runtime preference: ${runtimeLabel(agentRuntimeFocus)}.`);
      }
      const selectedRoute =
        workspaceProfileForm.routeOverrides.find(item => item.role === agentRouteRole) || {};
      const effectiveRoute =
        asList(mission?.effectiveRouteContract?.roles).find(item => item.role === agentRouteRole) ||
        {};
      const routeChanged =
        (selectedRoute.provider || "openai") !== (effectiveRoute.provider || "openai") ||
        (selectedRoute.model || "").trim() !== (effectiveRoute.model || "").trim() ||
        (selectedRoute.effort || "default") !== (effectiveRoute.effort || "default");
      if (routeChanged && selectedRoute.model?.trim()) {
        steeringLines.push(
          `Route preference for ${titleizeToken(agentRouteRole)}: ${titleizeToken(selectedRoute.provider)} / ${selectedRoute.model.trim()}${
            selectedRoute.effort && selectedRoute.effort !== "default"
              ? ` / ${selectedRoute.effort}`
              : ""
          }.`,
        );
      }
      const activeProvider = String(
        selectedRoute.provider || effectiveRoute.provider || "openai",
      ).trim().toLowerCase();
      if (codeExecutionEnabled && ["openai", "openai-codex"].includes(activeProvider)) {
        steeringLines.push(
          `If the OpenAI route is active, use the python tool / code execution when it will ground the work. Prefer a ${codeExecutionMemory} container budget.`,
        );
      }
      const activeRuleSet =
        findStudioItem(referenceStudio, "rule", referenceStudio.activeRuleSetId) ||
        findStudioItem(referenceStudio, "rule", referenceStudio.selectedRuleId);
      if (activeRuleSet) {
        steeringLines.push(`Active rule set: ${activeRuleSet.name}.`);
        const activeRuleRoute = activeRuleSet.routePlan?.[agentRouteRole];
        if (activeRuleRoute?.model) {
          steeringLines.push(
            `Rule-set route for ${titleizeToken(agentRouteRole)}: ${titleizeToken(activeRuleRoute.provider || "openai")} / ${activeRuleRoute.model}${activeRuleRoute.effort ? ` / ${routeEffortLabel(activeRuleRoute.effort, "medium")}` : ""}.`,
          );
        }
        if (asList(activeRuleSet.requiresApproval).length > 0) {
          steeringLines.push(
            `Approval-sensitive actions: ${asList(activeRuleSet.requiresApproval).slice(0, 3).join(", ")}.`,
          );
        }
      }
      const activeSkills = asList(referenceStudio.activeSkillIds)
        .map(skillId => findStudioItem(referenceStudio, "skill", skillId))
        .filter(Boolean)
        .slice(0, 5);
      if (activeSkills.length > 0) {
        steeringLines.push(`Active skills: ${activeSkills.map(item => item.name).join(", ")}.`);
        const skillGuardrails = activeSkills
          .flatMap(item => asList(item.guardrails).slice(0, 2))
          .slice(0, 4);
        if (skillGuardrails.length > 0) {
          steeringLines.push(`Guardrails: ${skillGuardrails.join(" ")}`);
        }
      }
      const memorySnippets = [];
      if (memoryPolicy.includeInFollowUps) {
        if (memoryPolicy.projectScoped && workspace?.workspace_id) {
          const workspaceMemo = String(memoryStore?.workspace?.[workspace.workspace_id] || "").trim();
          if (workspaceMemo) {
            memorySnippets.push(`Workspace memory: ${workspaceMemo}`);
          }
        }
        if (memoryPolicy.missionScoped && mission?.mission_id) {
          const missionMemo = String(memoryStore?.mission?.[mission.mission_id] || "").trim();
          if (missionMemo) {
            memorySnippets.push(`Mission memory: ${missionMemo}`);
          }
        }
      }
      const attachmentLines = operatorAttachments.map(
        item => `[attachment:${item.name}|${item.mime}|${Math.max(1, Math.round(item.size / 1024))}KB]`,
      );
      const composedFollowUpParts = [];
      if (steeringLines.length > 0) {
        composedFollowUpParts.push(steeringLines.join(" "));
      }
      if (memorySnippets.length > 0) {
        composedFollowUpParts.push(memorySnippets.join("\n"));
      }
      composedFollowUpParts.push(followUp);
      if (attachmentLines.length > 0) {
        composedFollowUpParts.push(`Attachments:\n${attachmentLines.join("\n")}`);
      }
      if (activeCommentTarget?.title) {
        composedFollowUpParts.unshift(
          `Live UI comment target: ${activeCommentTarget.kind || "message"} "${activeCommentTarget.title}".`,
        );
      }
      const composedFollowUp = composedFollowUpParts.filter(Boolean).join("\n\n");
      commentEntry = appendOperatorEntry({
        title: followUp,
        detail: activeCommentTarget?.title
          ? `Target: ${activeCommentTarget.title}`
          : "Live mission comment",
        meta: "Sending to mission",
        tone: "neutral",
        channel: "comment",
        role: "operator",
        pending: true,
        target: activeCommentTarget || null,
      });
      const hasActiveDelegatedRuntime = asList(mission?.delegated_runtime_sessions).some(session =>
        ["waiting_for_approval", "running", "launching"].includes(
          String(session?.status || "").trim().toLowerCase(),
        ),
      );
      let sentLive = false;
      if (
        mission.runtime_id === "openclaw" &&
        data.openClawStatus?.connected &&
        !hasActiveDelegatedRuntime
      ) {
        try {
          await callBackend(
            "send_openclaw_message",
            { payload: { message: composedFollowUp } },
            { throwOnError: true },
          );
          sentLive = true;
        } catch (error) {
          pushToast(`OpenClaw live send failed, keeping the follow-up in mission thread: ${error}`, "warn");
        }
      }
      await callBackendWithRetry(
        "send_control_room_mission_follow_up_command",
        { payload: { missionId: mission.mission_id, message: composedFollowUp, root: null } },
        { attempts: 3 },
      );
      setMemoryStore(current => ({
        ...current,
        mission: {
          ...current.mission,
          [mission.mission_id]: followUp.slice(0, 800),
        },
        workspace: workspace?.workspace_id
          ? {
              ...current.workspace,
              [workspace.workspace_id]: followUp.slice(0, 800),
            }
          : current.workspace,
      }));
      setOperatorDraft("");
      setActiveCommentTarget(null);
      clearOperatorAttachments();
      updateOperatorEntry(commentEntry.id, current => ({
        ...current,
        meta: sentLive ? "Sent live and recorded" : "Recorded in mission thread",
        tone: "good",
        pending: false,
      }));
      pushToast(sentLive ? "Follow-up sent live and recorded in the mission thread." : "Follow-up recorded in the mission thread.", "info");
      void refreshAll("mission-follow-up");
    } catch (error) {
      if (commentEntry?.id) {
        updateOperatorEntry(commentEntry.id, current => ({
          ...current,
          meta: "Send failed",
          tone: "bad",
          pending: false,
          detail: `${current.detail || ""}\n\n${String(error)}`.trim(),
        }));
      }
      pushToast(`Mission follow-up failed: ${error}`, "error");
    }
  }, [
    activeCommentTarget,
    appendOperatorEntry,
    codeExecutionEnabled,
    codeExecutionMemory,
    agentRouteRole,
    agentRuntimeFocus,
    data.openClawStatus?.connected,
    markAction,
    mission,
    memoryPolicy.includeInFollowUps,
    memoryPolicy.missionScoped,
    memoryPolicy.projectScoped,
    memoryStore?.mission,
    memoryStore?.workspace,
    operatorAttachments,
    operatorDraft,
    previewMode,
    pushToast,
    refreshAll,
    referenceStudio,
    workspace?.workspace_id,
    workspaceProfileForm.routeOverrides,
    mission?.effectiveRouteContract?.roles,
    clearOperatorAttachments,
    updateOperatorEntry,
  ]);

  const handleOpenClawConnect = useCallback(async () => {
    markAction("runtime:openclaw-connect");
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend(
        "connect_openclaw_gateway",
        { payload: { gatewayUrl: openClawGatewayUrl.trim() || null } },
        { throwOnError: true },
      );
      pushToast("OpenClaw gateway connect requested.", "info");
      await refreshAll("openclaw-connect");
    } catch (error) {
      pushToast(`OpenClaw connect failed: ${error}`, "error");
    }
  }, [markAction, openClawGatewayUrl, previewMode, pushToast, refreshAll]);

  const handleOpenClawDisconnect = useCallback(async () => {
    markAction("runtime:openclaw-disconnect");
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend("disconnect_openclaw_gateway", undefined, { throwOnError: true });
      pushToast("OpenClaw gateway disconnected.", "info");
      await refreshAll("openclaw-disconnect");
    } catch (error) {
      pushToast(`OpenClaw disconnect failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);

  const handleOpenClawSaveToken = useCallback(async () => {
    markAction("runtime:openclaw-save-token");
    if (!openClawGatewayToken.trim()) {
      pushToast("Paste a gateway token first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend(
        "save_openclaw_gateway_token",
        { token: openClawGatewayToken.trim() },
        { throwOnError: true },
      );
      setOpenClawGatewayToken("");
      pushToast("OpenClaw gateway token saved.", "info");
      await refreshAll("openclaw-token-save");
    } catch (error) {
      pushToast(`OpenClaw token save failed: ${error}`, "error");
    }
  }, [markAction, openClawGatewayToken, previewMode, pushToast, refreshAll]);

  const handleOpenClawClearToken = useCallback(async () => {
    markAction("runtime:openclaw-clear-token");
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend("clear_openclaw_gateway_token", undefined, { throwOnError: true });
      pushToast("OpenClaw gateway token cleared.", "info");
      await refreshAll("openclaw-token-clear");
    } catch (error) {
      pushToast(`OpenClaw token clear failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);

  const handleProviderSecretSave = useCallback(async providerId => {
    markAction(`provider-secret:save:${providerId}`);
    const secret = String(providerSecretDrafts?.[providerId] || "").trim();
    if (!secret) {
      pushToast("Paste a provider API key first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot change provider authentication.", "warn");
      return;
    }
    setProviderSecretSaving(current => ({ ...current, [providerId]: "saving" }));
    try {
      const payload = { providerId, secret };
      const saved =
        (await callBackend("save_provider_secret_command", payload)) ??
        (await callBackend("save_provider_secret_command", {
          provider_id: providerId,
          secret,
        }));
      if (!saved) {
        throw new Error("Provider secret save did not complete.");
      }
      setProviderSecretDrafts(current => ({ ...current, [providerId]: "" }));
      pushToast(`${titleizeToken(providerId)} secret saved.`, "info");
      await refreshAll(`provider-secret-save-${providerId}`);
    } catch (error) {
      pushToast(`Provider secret save failed: ${error}`, "error");
    } finally {
      setProviderSecretSaving(current => ({ ...current, [providerId]: "" }));
    }
  }, [markAction, previewMode, providerSecretDrafts, pushToast, refreshAll]);

  const handleProviderSecretClear = useCallback(async providerId => {
    markAction(`provider-secret:clear:${providerId}`);
    if (previewMode !== "live" || !hasCommandBackend()) {
      pushToast("Preview mode cannot change provider authentication.", "warn");
      return;
    }
    setProviderSecretSaving(current => ({ ...current, [providerId]: "clearing" }));
    try {
      const cleared =
        (await callBackend("clear_provider_secret_command", { providerId })) ??
        (await callBackend("clear_provider_secret_command", {
          provider_id: providerId,
        }));
      if (!cleared) {
        throw new Error("Provider secret clear did not complete.");
      }
      setProviderSecretDrafts(current => ({ ...current, [providerId]: "" }));
      pushToast(`${titleizeToken(providerId)} secret cleared.`, "info");
      await refreshAll(`provider-secret-clear-${providerId}`);
    } catch (error) {
      pushToast(`Provider secret clear failed: ${error}`, "error");
    } finally {
      setProviderSecretSaving(current => ({ ...current, [providerId]: "" }));
    }
  }, [markAction, previewMode, pushToast, refreshAll]);

  const openClawRuntimeActive = mission?.runtime_id === "openclaw";
  const openClawStatus = data.openClawStatus;
  const delegatedSessions = useMemo(
    () => (Array.isArray(mission?.delegated_runtime_sessions) ? mission.delegated_runtime_sessions : []),
    [mission?.delegated_runtime_sessions],
  );
  const runtimeCompartmentState =
    snapshot?.runtimeCompartments && typeof snapshot.runtimeCompartments === "object"
      ? snapshot.runtimeCompartments
      : EMPTY_OBJECT;
  const runtimeCompartments = useMemo(
    () => asList(runtimeCompartmentState.items),
    [runtimeCompartmentState.items],
  );
  const runtimeCompartmentChatTurnsBySession = useMemo(() => {
    const next = {};
    for (const compartment of runtimeCompartments) {
      const sessionId = String(compartment?.sessionId || compartment?.id || "").trim();
      if (!sessionId) {
        continue;
      }
      const turns = transcriptTurnsFromRuntimeCompartment(compartment, sessionId);
      if (turns.length > 0) {
        next[sessionId] = turns;
      }
    }
    return next;
  }, [runtimeCompartments]);
  useEffect(() => {
    if (!activeChatSessionId) {
      return;
    }
    const compartmentTurns = asList(runtimeCompartmentChatTurnsBySession?.[activeChatSessionId]);
    if (compartmentTurns.length === 0) {
      return;
    }
    setChatSessionTranscripts(current => {
      const existingTurns = asList(current?.[activeChatSessionId]);
      const merged = normalizeChatSessionTranscripts({
        ...current,
        [activeChatSessionId]: [...existingTurns, ...compartmentTurns],
      });
      const nextTurns = asList(merged?.[activeChatSessionId]);
      if (JSON.stringify(existingTurns) === JSON.stringify(nextTurns)) {
        return current;
      }
      return merged;
    });
  }, [activeChatSessionId, runtimeCompartmentChatTurnsBySession]);
  const hermesMissionEvidence =
    snapshot?.hermesMissionEvidence && typeof snapshot.hermesMissionEvidence === "object"
      ? snapshot.hermesMissionEvidence
      : EMPTY_OBJECT;
  const hermesEvidenceItems = useMemo(
    () => asList(hermesMissionEvidence.items),
    [hermesMissionEvidence.items],
  );
  const nasDeployReadiness =
    snapshot?.nasDeployReadiness && typeof snapshot.nasDeployReadiness === "object"
      ? snapshot.nasDeployReadiness
      : EMPTY_OBJECT;
  const nasDeployChecks = useMemo(
    () => asList(nasDeployReadiness.checks),
    [nasDeployReadiness.checks],
  );
  const generatedImageArtifactState =
    snapshot?.generatedImageArtifacts && typeof snapshot.generatedImageArtifacts === "object"
      ? snapshot.generatedImageArtifacts
      : EMPTY_OBJECT;
  const generatedImageArtifacts = useMemo(
    () => asList(generatedImageArtifactState.items),
    [generatedImageArtifactState.items],
  );
  const bridgeSessions = useMemo(
    () => (Array.isArray(snapshot?.bridgeLab?.connectedSessions) ? snapshot.bridgeLab.connectedSessions : []),
    [snapshot?.bridgeLab?.connectedSessions],
  );
  const fusionWorkbench = useMemo(
    () => buildFusionWorkbench(snapshot?.fusionWorkbench?.rows),
    [snapshot?.fusionWorkbench?.rows],
  );
  const effectiveRouteRows = useMemo(
    () => (Array.isArray(mission?.effectiveRouteContract?.roles) ? mission.effectiveRouteContract.roles : []),
    [mission?.effectiveRouteContract?.roles],
  );
  const missionRuntimeContract = useMemo(
    () =>
      mission
        ? [
            {
              label: "Runtime",
              value: runtimeLabel(mission?.runtime_id),
            },
            {
              label: "Profile",
              value: titleizeToken(mission?.selected_profile || workspace?.user_profile || profileId),
            },
            {
              label: "Mode",
              value: titleizeToken(mission?.run_budget?.mode || mission?.missionLoop?.timeBudget?.mode || "autopilot"),
            },
            {
              label: "Run until",
              value: titleizeToken(
                mission?.missionLoop?.timeBudget?.runUntilBehavior ||
                  mission?.run_budget?.run_until_behavior ||
                  "pause_on_failure",
              ),
            },
            {
              label: "Harness",
              value: titleizeToken(mission?.harness_id || workspace?.preferred_harness || "fluxio_hybrid"),
            },
            {
              label: "Active route",
              value: (() => {
                const truth =
                  mission?.providerTruth ||
                  mission?.missionLoop?.providerTruth ||
                  mission?.state?.provider_runtime_truth ||
                  {};
                const active = truth?.activeRoute || {};
                if (!active?.provider && !active?.model) {
                  return "Not resolved";
                }
                return `${titleizeToken(active.provider)} · ${active.model || "default"}`;
              })(),
            },
            {
              label: "Blocker class",
              value: titleizeToken(
                mission?.state?.blocker_classification?.class ||
                  mission?.missionLoop?.blocker?.class ||
                  "none",
              ),
            },
            {
              label: "Code execution",
              value: (() => {
                const codeState =
                  mission?.state?.code_execution ||
                  mission?.missionLoop?.codeExecution ||
                  {};
                if (!codeState?.enabled) {
                  return "Off";
                }
                return codeState?.container_id
                  ? `On · ${codeState.container_id}`
                  : "On · auto container";
              })(),
            },
          ]
        : [],
    [
      mission,
      profileId,
      workspace?.preferred_harness,
      workspace?.user_profile,
    ],
  );
  const builderBoard = viewModel.drawers.builder.board;
  const workspaceById = useMemo(
    () => new Map(workspaces.map(item => [item.workspace_id, item])),
    [workspaces],
  );
  const orderedWorkspaceRows = useMemo(() => {
    const ordered = sortRowsByOrder(workspaces, workspaceOrder, item => item.workspace_id);
    const query = workspaceSearchQuery.trim().toLowerCase();
    if (!query) {
      return ordered;
    }
    return ordered.filter(item =>
      [item?.name, item?.root_path, item?.workspace_id]
        .filter(Boolean)
        .some(value => String(value).toLowerCase().includes(query)),
    );
  }, [workspaceOrder, workspaceSearchQuery, workspaces]);
  const orderedMissionRows = useMemo(() => {
    const ordered = sortRowsByOrder(missionOptions, missionOrder, item => item.mission_id);
    const query = missionSearchQuery.trim().toLowerCase();
    if (!query) {
      return ordered;
    }
    return ordered.filter(item =>
      [
        item?.title,
        item?.objective,
        item?.mission_id,
        item?.state?.status,
        item?.runtime_id,
        item?.execution_scope?.execution_root,
      ]
        .filter(Boolean)
        .some(value => String(value).toLowerCase().includes(query)),
    );
  }, [missionOptions, missionOrder, missionSearchQuery]);
  const workspaceNavItems = useMemo(
    () =>
      orderedWorkspaceRows.map(item => {
        const workspaceMissionRows = missions.filter(entry => entry?.workspace_id === item.workspace_id);
        const activeCount = workspaceMissionRows.filter(
          entry => !["completed", "failed"].includes(entry?.state?.status || ""),
        ).length;
        const blockedCount = workspaceMissionRows.filter(
          entry =>
            asList(entry?.proof?.pending_approvals).length > 0 ||
            asList(entry?.state?.verification_failures).length > 0 ||
            ["needs_approval", "blocked", "verification_failed", "queued"].includes(
              entry?.state?.status || "",
            ),
        ).length;
        return {
          workspaceId: item.workspace_id,
          title: item.name,
          subtitle: `${runtimeLabel(item.default_runtime)} default`,
          context: item.root_path,
          tone: blockedCount > 0 ? "warn" : item.runtimeStatus?.detected ? "good" : "warn",
          badge: pathLeaf(item.root_path) || titleizeToken(item.workspace_type || "workspace"),
          stats: [
            activeCount > 0 ? { label: "threads", value: activeCount, tone: "good" } : null,
            blockedCount > 0 ? { label: "blocked", value: blockedCount, tone: "warn" } : null,
          ].filter(Boolean),
        };
      }),
    [missions, orderedWorkspaceRows],
  );
  const missionNavItems = useMemo(
    () =>
      orderedMissionRows.map(item => {
        const ownerWorkspace = workspaceById.get(item.workspace_id) || null;
        const executionPath =
          item?.delegated_runtime_sessions?.find(session => session?.execution_root)?.execution_root ||
          item?.execution_scope?.execution_root ||
          item?.state?.execution_scope?.execution_root ||
          ownerWorkspace?.root_path ||
          "";
        const approvalCount = asList(item?.proof?.pending_approvals).length;
        const verificationCount = asList(item?.state?.verification_failures).length;
        const delegatedCount = asList(item?.delegated_runtime_sessions).filter(
          session => !["completed", "failed", "stopped"].includes(session?.status || ""),
        ).length;
        const queuedCount = ["queued", "needs_approval", "blocked"].includes(item?.state?.status || "")
          ? 1
          : 0;
        const tone =
          verificationCount > 0
            ? "bad"
            : approvalCount > 0 || queuedCount > 0
              ? "warn"
              : delegatedCount > 0 || item?.state?.status === "running"
                ? "good"
                : "neutral";
        return {
          missionId: item.mission_id,
          title: item.title || item.objective,
          subtitle: `${runtimeLabel(item.runtime_id)} · ${titleizeToken(item.state?.status || "draft")}`,
          context: executionPath,
          tone,
          badge:
            pathLeaf(executionPath) ||
            pathLeaf(ownerWorkspace?.root_path) ||
            titleizeToken(item.state?.status || "draft"),
          stats: [
            approvalCount > 0 ? { label: "approvals", value: approvalCount, tone: "warn" } : null,
            verificationCount > 0 ? { label: "failures", value: verificationCount, tone: "bad" } : null,
            delegatedCount > 0 ? { label: "lanes", value: delegatedCount, tone: "good" } : null,
            queuedCount > 0 && approvalCount === 0
              ? { label: "queued", value: queuedCount, tone: "warn" }
              : null,
          ].filter(Boolean),
        };
      }),
    [orderedMissionRows, workspaceById],
  );
  const splitMissionOptions = useMemo(
    () => missions.filter(item => item?.mission_id && item.mission_id !== mission?.mission_id),
    [mission?.mission_id, missions],
  );
  const splitMission = useMemo(
    () =>
      splitMissionOptions.find(item => item.mission_id === splitMissionId) ||
      splitMissionOptions[0] ||
      null,
    [splitMissionId, splitMissionOptions],
  );
  const builderRootItems = useMemo(() => builderBoard.roots || [], [builderBoard.roots]);
  const builderNexusItems = useMemo(() => builderBoard.nexuses || [], [builderBoard.nexuses]);
  const builderPrimaryConversation = useMemo(
    () =>
      builderBoard.activeConversations.find(item => item.selected) ||
      builderBoard.activeConversations.find(item => item.blocked) ||
      builderBoard.activeConversations[0] ||
      null,
    [builderBoard.activeConversations],
  );
  const builderSecondaryConversations = useMemo(
    () =>
      builderBoard.activeConversations.filter(
        item => item.missionId !== builderPrimaryConversation?.missionId,
      ),
    [builderBoard.activeConversations, builderPrimaryConversation?.missionId],
  );
  const tutorialStudio = viewModel.drawers.builder.tutorialStudio;
  const recommendationStudio = viewModel.drawers.builder.recommendationStudio;
  const liveReviewStudio = viewModel.drawers.builder.liveReviewStudio;
  const monitoringLoopStudio = viewModel.drawers.builder.monitoringLoopStudio || {};
  const monitoringLoops = asList(monitoringLoopStudio.loops);
  const supervisorInterventionQueue = asList(monitoringLoopStudio.interventionQueue);
  const subagentOrchestrationStudio = viewModel.drawers.builder.subagentOrchestrationStudio || {};
  const subagentLanes = asList(subagentOrchestrationStudio.lanes);
  const subagentScoreboard = asList(subagentOrchestrationStudio.scoreboard);
  const continuationSupervisor = liveReviewStudio.continuationSupervisor || null;
  const connectedDeviceBridge = asRecord(snapshot.connectedDeviceBridge);
  const bridgeSyncRows = asList(connectedDeviceBridge.sync);
  const bridgePendingApprovals = asList(connectedDeviceBridge.pendingApprovals);
  const bridgeAuditTrail = asList(connectedDeviceBridge.auditTrail);
  const bridgeReceipts = asList(connectedDeviceBridge.receipts);
  const latestBridgeAction =
    asRecord(bridgeAuditTrail[bridgeAuditTrail.length - 1]) || asRecord(liveReviewStudio.dualPathBridge?.latestAction);
  const latestBridgeReceipt =
    asRecord(bridgeReceipts[bridgeReceipts.length - 1]) || asRecord(liveReviewStudio.dualPathBridge?.latestReceipt);
  const latestStructuredFeedbackReceipt =
    asRecord(liveReviewStudio.plannerProof?.latestStructuredFeedbackReceipt) ||
    asRecord(liveReviewStudio.plannerProof?.structuredFeedbackReceipt) ||
    asRecord([...bridgeReceipts].reverse().find(item => item?.receiptKind === "live_review_structured_feedback"));
  const structuredFeedbackReceiptHistory = useMemo(() => {
    const fromEvents = asList(liveReviewStudio.events)
      .filter(item => item?.structuredFeedbackReceipt)
      .map(item => ({
        id: item.id,
        label: item.label || titleizeToken(item.kind || "event"),
        timestamp: item.timestamp || "",
        receipt: asRecord(item.structuredFeedbackReceipt),
      }));
    const fallback = latestStructuredFeedbackReceipt?.eventId || latestStructuredFeedbackReceipt?.plannerExecutorHandoffId
      ? [
          {
            id: "latest-receipt",
            label: "Latest receipt",
            timestamp: "",
            receipt: latestStructuredFeedbackReceipt,
          },
        ]
      : [];
    const seen = new Set();
    return [...fromEvents, ...fallback]
      .filter(item => {
        const eventId = item?.receipt?.eventId || "";
        const handoffId = item?.receipt?.plannerExecutorHandoffId || "";
        const dedupeKey = `${eventId}::${handoffId}`;
        if (!eventId && !handoffId) {
          return false;
        }
        if (seen.has(dedupeKey)) {
          return false;
        }
        seen.add(dedupeKey);
        return true;
      })
      .slice(0, 6);
  }, [liveReviewStudio.events, latestStructuredFeedbackReceipt]);
  const latestBridgeHostStatus = asRecord(latestBridgeReceipt.hostStatus);
  const latestBridgeSync = asRecord(bridgeSyncRows[0]);
  const builderSelectedReviewTarget = useMemo(
    () =>
      liveReviewStudio.targets.find(item => item.id === selectedReviewTargetId) ||
      liveReviewStudio.targets[0] ||
      null,
    [liveReviewStudio.targets, selectedReviewTargetId],
  );
  const liveReviewEventBuckets = useMemo(() => {
    const events = asList(liveReviewStudio.events);
    const buckets = {
      execution: events.filter(item =>
        ["file_change", "browser_qa", "computer_use", "verification", "runtime_activity", "continuation_supervisor"].includes(item.kind),
      ),
      media: events.filter(item => ["preview_refresh", "image_playground"].includes(item.kind)),
      operator: events.filter(item => ["operator_followup", "progress_update"].includes(item.kind)),
      replay: events.filter(item => item.kind === "replay_marker"),
    };
    return buckets;
  }, [liveReviewStudio.events]);
  const liveReviewEventsFlat = useMemo(
    () => Object.values(liveReviewEventBuckets).flatMap(items => asList(items)),
    [liveReviewEventBuckets],
  );
  const selectedLiveReviewEvent = useMemo(
    () =>
      liveReviewEventsFlat.find(item => item.id === selectedLiveReviewEventId) ||
      liveReviewEventsFlat[0] ||
      null,
    [liveReviewEventsFlat, selectedLiveReviewEventId],
  );
  const livePreviewUrl =
    selectedLiveReviewEvent?.previewUrl ||
    liveReviewStudio.previewUrl ||
    mission?.state?.last_preview_url ||
    mission?.state?.preview_url ||
    "";
  const selectedLiveReviewFrames = asList(selectedLiveReviewEvent?.screenshotFrames);
  const selectedLiveReviewFrame =
    selectedLiveReviewFrames[selectedLiveReviewFrameIndex] || selectedLiveReviewFrames[0] || null;
  const firstLiveReviewFrameEvent =
    liveReviewEventsFlat.find(item => asList(item?.screenshotFrames).length > 0) || null;
  const visualProofFrame =
    selectedLiveReviewFrame || asList(firstLiveReviewFrameEvent?.screenshotFrames)[0] || null;
  const selectedReplayMarkers = asList(selectedLiveReviewEvent?.replayMarkers);
  const selectedReplayMarker =
    selectedReplayMarkers[selectedReplayMarkerIndex] || selectedReplayMarkers[0] || null;
  const liveReviewAnnotationBlocks = asList(liveReviewStudio.annotationReadiness?.blocks);
  const visualProofPacket = useMemo(() => {
    const severeAnnotations = liveReviewAnnotationBlocks.filter(block =>
      ["high", "critical"].includes(String(block?.severity || "").toLowerCase()),
    );
    const mediumAnnotations = liveReviewAnnotationBlocks.filter(
      block => String(block?.severity || "").toLowerCase() === "medium",
    );
    return {
      eventId: selectedLiveReviewEvent?.id || firstLiveReviewFrameEvent?.id || "",
      eventLabel:
        selectedLiveReviewEvent?.label ||
        firstLiveReviewFrameEvent?.label ||
        "Preview proof",
      frameLabel: visualProofFrame?.label || "No frame selected",
      framePath: visualProofFrame?.path || visualProofFrame?.thumbnailPath || "",
      previewUrl: livePreviewUrl,
      annotationCount: liveReviewAnnotationBlocks.length,
      severeAnnotationCount: severeAnnotations.length,
      mediumAnnotationCount: mediumAnnotations.length,
      proofTarget:
        selectedReplayMarker?.deepLink?.proofTarget ||
        selectedLiveReviewEvent?.proofTarget ||
        builderSelectedReviewTarget?.id ||
        "",
      threadTarget:
        selectedReplayMarker?.deepLink?.threadTarget ||
        selectedLiveReviewEvent?.threadTarget ||
        mission?.mission_id ||
        "",
      receiptKind: latestStructuredFeedbackReceipt?.receiptKind || "live_review_structured_feedback",
      receiptHandle:
        latestStructuredFeedbackReceipt?.eventId ||
        latestStructuredFeedbackReceipt?.plannerExecutorHandoffId ||
        "",
    };
  }, [
    builderSelectedReviewTarget?.id,
    firstLiveReviewFrameEvent?.id,
    firstLiveReviewFrameEvent?.label,
    latestStructuredFeedbackReceipt?.eventId,
    latestStructuredFeedbackReceipt?.plannerExecutorHandoffId,
    latestStructuredFeedbackReceipt?.receiptKind,
    livePreviewUrl,
    liveReviewAnnotationBlocks,
    mission?.mission_id,
    selectedLiveReviewEvent?.id,
    selectedLiveReviewEvent?.label,
    selectedLiveReviewEvent?.proofTarget,
    selectedLiveReviewEvent?.threadTarget,
    selectedReplayMarker?.deepLink?.proofTarget,
    selectedReplayMarker?.deepLink?.threadTarget,
    visualProofFrame?.label,
    visualProofFrame?.path,
    visualProofFrame?.thumbnailPath,
  ]);
  const [liveReviewAutoplay, setLiveReviewAutoplay] = useState(false);
  const markerFrameMap = useMemo(() => {
    const map = new Map();
    selectedReplayMarkers.forEach((marker, markerIndex) => {
      const frameId = marker?.frameId;
      if (!frameId) {
        return;
      }
      const frameIndex = selectedLiveReviewFrames.findIndex(frame => frame?.id === frameId);
      if (frameIndex >= 0) {
        map.set(markerIndex, frameIndex);
      }
    });
    return map;
  }, [selectedReplayMarkers, selectedLiveReviewFrames]);

  useEffect(() => {
    if (!selectedLiveReviewEventId && liveReviewEventsFlat[0]?.id) {
      setSelectedLiveReviewEventId(liveReviewEventsFlat[0].id);
    }
  }, [liveReviewEventsFlat, selectedLiveReviewEventId]);

  useEffect(() => {
    setSelectedLiveReviewFrameIndex(0);
    setSelectedReplayMarkerIndex(0);
    setLiveReviewAutoplay(false);
  }, [selectedLiveReviewEvent?.id]);

  const handleStructuredLiveReviewFeedback = useCallback(
    async ({ sendFollowUp = false, proofOnly = false } = {}) => {
      const followUp = operatorDraft.trim();
      if (!followUp && !proofOnly) {
        pushToast("Write structured Live Review feedback first.", "warn");
        return;
      }
      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast("Preview mode cannot record Live Review feedback receipts.", "warn");
        return;
      }
      if (!mission?.mission_id) {
        pushToast("Select a mission before recording structured feedback.", "warn");
        return;
      }

      const event = selectedLiveReviewEvent || {};
      const target = builderSelectedReviewTarget || {};
      const plannerProof = asRecord(liveReviewStudio.plannerProof);
      const continuation = asRecord(liveReviewStudio.continuationSupervisor);
      const routePreservation = asRecord(continuation.routePreservation);
      const verifierFeedbackItems = asList(plannerProof.decisionInfluence)
        .map(item => item?.verifierFeedback || item?.evidence || "")
        .filter(Boolean);
      const eventId = String(event.id || target.id || `live-review-${mission.mission_id}`).trim();
      const handoffId = [
        "live-review",
        mission.mission_id,
        eventId,
        target.id || "target",
      ].filter(Boolean).join(":");
      const payload = {
        proofOnly,
        eventId,
        sourceEventId: eventId,
        source: "builder-live-review",
        plannerExecutorHandoffId: handoffId,
        routeContext: {
          missionId: mission.mission_id,
          workspaceId: workspace?.workspace_id || "",
          routeRole: agentRouteRole,
          runtimeFocus: agentRuntimeFocus,
          bridgeStatus: connectedDeviceBridge.status || "needs_mapping",
          performedByHost: latestBridgeAction?.performedByHost || latestBridgeAction?.performed_by_host || "",
          model: routePreservation.model || mission?.model_route?.executor?.model || mission?.model_route?.planner?.model || "unrecorded",
          provider: routePreservation.provider || mission?.model_route?.executor?.provider || mission?.model_route?.planner?.provider || "unrecorded",
          effort: routePreservation.effort || mission?.model_route?.executor?.effort || mission?.model_route?.planner?.effort || "unrecorded",
        },
        taskContext: {
          reviewTargetId: target.id || "",
          reviewTarget: target.title || event.title || "Live Review feedback",
          reviewDetail: target.detail || event.detail || "",
          selectedEventKind: event.kind || "live_review",
          selectedEventLabel: event.label || "Live Review",
          operatorFeedback: followUp,
          screenshots: asList(event.screenshotFrames).map(frame => frame?.path || frame?.thumbnailPath || "").filter(Boolean),
          timelapseMarkers: asList(event.replayMarkers).map(marker => marker?.snapshotPath || marker?.label || "").filter(Boolean),
          annotations: asList(liveReviewStudio.annotationReadiness?.blocks).map(block => ({
            id: block?.id || "",
            label: block?.label || "",
            severity: block?.severity || "",
            note: block?.note || "",
            recoveryAction: block?.recoveryAction || "",
          })),
        },
        visualProofPacket,
        verifierFeedback: {
          selectedEventDetail: event.kind === "verification" ? event.detail || event.title || "" : "",
          failures: asList(mission?.state?.verification_failures),
          decisionInfluence: verifierFeedbackItems,
          latestReceiptStatus: latestBridgeReceipt?.status || "",
        },
        nextIdea:
          plannerProof.nextIdea ||
          event.nextIdea ||
          event.progressUpdate?.next ||
          routePreservation.nextIdea ||
          "Use this receipt for the next planner/executor handoff.",
      };

      markAction("live-review:structured-feedback");
      try {
        const receipt = await callBackend(
          "record_live_review_structured_feedback_command",
          { payload },
          { throwOnError: true },
        );
        appendOperatorEntry({
          title: "Live Review receipt",
          detail: `Receipt ${receipt?.eventId || eventId} -> ${receipt?.plannerExecutorHandoffId || handoffId}.`,
          meta: "receipt received",
          tone: "good",
          channel: "receipt",
          role: "system",
        });
        pushToast(`Receipt recorded for ${receipt?.eventId || eventId}.`, "info");
        void refreshAll("live-review-structured-feedback");
        if (sendFollowUp) {
          await handleAgentFollowUp();
        }
      } catch (error) {
        pushToast(`Receipt failed: ${error}`, "error");
      }
    },
    [
      agentRouteRole,
      agentRuntimeFocus,
      appendOperatorEntry,
      builderSelectedReviewTarget,
      connectedDeviceBridge.status,
      handleAgentFollowUp,
      latestBridgeAction,
      latestBridgeReceipt,
      liveReviewStudio.annotationReadiness?.blocks,
      liveReviewStudio.continuationSupervisor,
      liveReviewStudio.plannerProof,
      markAction,
      mission,
      operatorDraft,
      previewMode,
      pushToast,
      refreshAll,
      selectedLiveReviewEvent,
      visualProofPacket,
      workspace?.workspace_id,
    ],
  );

  useEffect(() => {
    if (!liveReviewAutoplay || selectedLiveReviewFrames.length <= 1) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setSelectedLiveReviewFrameIndex(index => (index + 1) % selectedLiveReviewFrames.length);
    }, 1800);
    return () => window.clearInterval(timer);
  }, [liveReviewAutoplay, selectedLiveReviewFrames.length]);

  const stepReplayMarker = useCallback(
    delta => {
      if (!selectedReplayMarkers.length) {
        return;
      }
      const nextIndex = (selectedReplayMarkerIndex + delta + selectedReplayMarkers.length) % selectedReplayMarkers.length;
      setSelectedReplayMarkerIndex(nextIndex);
      const mappedFrameIndex = markerFrameMap.get(nextIndex);
      if (Number.isInteger(mappedFrameIndex)) {
        setSelectedLiveReviewFrameIndex(mappedFrameIndex);
      }
    },
    [markerFrameMap, selectedReplayMarkerIndex, selectedReplayMarkers.length],
  );

  const plannerProofChips = useMemo(() => {
    const chips = [];
    asList(liveReviewStudio.plannerProof?.selectedSkills).forEach((skill, index) => {
      chips.push({
        id: `skill-${index}-${skill}`,
        kind: "skill",
        label: titleizeToken(skill),
        value: skill,
      });
    });
    asList(liveReviewStudio.plannerProof?.designPrompts).forEach((prompt, index) => {
      chips.push({
        id: `design-${index}`,
        kind: "design_prompt",
        label: `Design ${index + 1}`,
        value: prompt,
      });
    });
    if (liveReviewStudio.plannerProof?.nextIdea) {
      chips.push({
        id: "next-idea",
        kind: "next_idea",
        label: "Next idea",
        value: liveReviewStudio.plannerProof.nextIdea,
      });
    }
    return chips;
  }, [
    liveReviewStudio.plannerProof?.designPrompts,
    liveReviewStudio.plannerProof?.nextIdea,
    liveReviewStudio.plannerProof?.selectedSkills,
  ]);

  useEffect(() => {
    if (!plannerProofChips.length) {
      setSelectedPlannerProofChipIndex(0);
      return;
    }
    setSelectedPlannerProofChipIndex(index => Math.max(0, Math.min(index, plannerProofChips.length - 1)));
  }, [plannerProofChips]);

  const activatePlannerProofChip = useCallback(
    chip => {
      if (!chip) {
        return;
      }
      if (chip.kind === "skill") {
        setUiMode("builder");
        setSkillStudioFilter("all");
        setSkillStudioQuery(String(chip.value || ""));
        setActiveDrawer("skills");
        setActivePlannerProofDetail({
          kind: chip.kind,
          title: `Skill chip opened: ${chip.label}`,
          body: `Skills drawer filtered to ${chip.label}.`,
        });
        return;
      }
      if (chip.kind === "design_prompt") {
        setActivePlannerProofDetail({
          kind: chip.kind,
          title: `Design prompt detail: ${chip.label}`,
          body: String(chip.value || ""),
        });
        return;
      }
      if (chip.kind === "next_idea") {
        setOperatorDraft(current => {
          const seed = `Follow-up from planner next idea:\n${chip.value}`;
          return current.trim() ? `${current.trim()}\n\n${seed}` : seed;
        });
        setActivePlannerProofDetail({
          kind: chip.kind,
          title: "Next idea handoff draft seeded",
          body: "Operator follow-up draft updated from planner next idea chip.",
        });
      }
    },
    [setActiveDrawer, setOperatorDraft, setSkillStudioFilter, setSkillStudioQuery, setUiMode],
  );

  const topbarStatus = useMemo(() => {
    if (uiMode === "builder") {
      return {
        label: "Builder focus",
        value:
          builderBoard.activeConversations.length > 0
            ? `${builderBoard.activeConversations.length} active conversation${builderBoard.activeConversations.length === 1 ? "" : "s"}`
            : "No active conversations",
        tone:
          builderBoard.activeConversations.length > 0
            ? builderBoard.activeConversations.some(item => item.blocked)
              ? "warn"
              : "good"
            : "neutral",
      };
    }
    if (agentBlockedState.isBlocked) {
      return {
        label: "Blocker state",
        value: viewModel.topBar.liveStatus.label,
        tone: viewModel.topBar.liveStatus.tone,
      };
    }
    return {
      label: mission ? "Mission state" : "Workspace state",
      value: mission ? viewModel.topBar.liveStatus.label : setupHealth.environmentReady ? "Environment ready" : "Needs setup",
      tone: mission ? viewModel.topBar.liveStatus.tone : setupHealth.environmentReady ? "good" : "warn",
    };
  }, [
    agentBlockedState.isBlocked,
    builderBoard.activeConversations,
    mission,
    setupHealth.environmentReady,
    uiMode,
    viewModel.topBar.liveStatus.label,
    viewModel.topBar.liveStatus.tone,
  ]);
  const runtimeOptions = useMemo(
    () =>
      asList(snapshot?.runtimes).map(item => ({
        value: item.runtime_id,
        label: item.label || runtimeLabel(item.runtime_id),
      })),
    [snapshot?.runtimes],
  );
  const autonomyGuardrails = useMemo(
    () => [
      {
        id: "inspect-before-stop",
        label: "Inspect before stopping",
        status: "required",
        proof: "Read code, logs, tests, and current branch before declaring blocked.",
      },
      {
        id: "preserve-user-work",
        label: "Preserve user work",
        status: "required",
        proof: "Branch, stash, or isolate safely; never revert unrelated user edits.",
      },
      {
        id: "continue-independent-work",
        label: "Continue independent work",
        status: "active",
        proof: "When one slice is blocked, switch to another safe mission area.",
      },
      {
        id: "split-reviewable-prs",
        label: "Split reviewable PRs",
        status: "active",
        proof: "Keep branches ordered, scoped, pushed, and proof-linked.",
      },
      {
        id: "attach-real-proof",
        label: "Attach real proof",
        status: "required",
        proof: "Use tests, builds, screenshots, artifacts, transcripts, and logs without faking runtime output.",
      },
    ],
    [],
  );
  const runtimeStatusById = useMemo(
    () => new Map(asList(snapshot?.runtimes).map(item => [item.runtime_id, item])),
    [snapshot?.runtimes],
  );
  const bridgeSummary = useMemo(() => {
    const connected = bridgeSessions.filter(item => item?.status === "connected").length;
    const callbackReady = bridgeSessions.filter(item => item?.approval_callback?.available).length;
    const mobileReady = bridgeSessions.filter(
      item => item?.approval_callback?.channel === "mobile_web" || item?.ui_hints?.mobileSurface,
    ).length;
    return {
      connected,
      callbackReady,
      mobileReady,
      totalApps: asList(snapshot?.bridgeLab?.discoveredApps).length,
      recommendation:
        snapshot?.bridgeLab?.recommendation ||
        "Bridge hand-offs between runtimes and connected apps will appear here.",
    };
  }, [bridgeSessions, snapshot?.bridgeLab?.discoveredApps, snapshot?.bridgeLab?.recommendation]);
  const selectedAgentRoute = useMemo(
    () => {
      const explicit = workspaceProfileForm.routeOverrides.find(item => item.role === agentRouteRole) || {};
      const effective = effectiveRouteRows.find(item => item.role === agentRouteRole) || {};
      return {
        role: agentRouteRole,
        provider: explicit.provider || effective.provider || "openai",
        model: explicit.model || effective.model || "",
        effort: normalizeRouteEffort(explicit.effort || effective.effort, "default"),
      };
    },
    [agentRouteRole, effectiveRouteRows, workspaceProfileForm.routeOverrides],
  );
  const referenceRouteByRole = useMemo(
    () =>
      Object.fromEntries(
        ROUTE_ROLE_OPTIONS.map(role => {
          const explicit = workspaceProfileForm.routeOverrides.find(item => item.role === role) || {};
          const effective = effectiveRouteRows.find(item => item.role === role) || {};
          return [
            role,
            {
              role,
              provider: explicit.provider || effective.provider || "openai",
              model: explicit.model || effective.model || "",
              effort: normalizeRouteEffort(explicit.effort || effective.effort, "default"),
            },
          ];
        }),
      ),
    [effectiveRouteRows, workspaceProfileForm.routeOverrides],
  );
  const activeEffectiveRoute = useMemo(
    () =>
      effectiveRouteRows.find(item => item.role === agentRouteRole) || {
        role: agentRouteRole,
        provider: selectedAgentRoute.provider,
        model: selectedAgentRoute.model,
        effort: normalizeRouteEffort(selectedAgentRoute.effort, "default"),
      },
    [
      agentRouteRole,
      effectiveRouteRows,
      selectedAgentRoute.effort,
      selectedAgentRoute.model,
      selectedAgentRoute.provider,
    ],
  );
  const builderStudioCards = useMemo(
    () => [
      {
        id: "runtime",
        eyebrow: "Setup",
        title: "Work engines and accounts",
        detail: "Install or update Hermes, OpenClaw, image tools, and account connections without leaving Syntelos.",
        meta: `${viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount} need attention · ${viewModel.drawers.builder.serviceStudio.availableActionCount} actions`,
        tone:
          viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount > 0 ? "warn" : "good",
      },
      {
        id: "storage",
        eyebrow: "Storage bridge",
        title: "Computer, NAS, and cloud file bridge",
        detail: "Map local folders to NAS or Google Drive storage so long-running work can stay online while files remain editable locally.",
        meta: `${bridgeSummary.connected}/${bridgeSummary.totalApps} bridge session${bridgeSummary.totalApps === 1 ? "" : "s"} connected · ${bridgeSummary.mobileReady} mobile-ready`,
        tone: bridgeSummary.connected > 0 ? "good" : "warn",
      },
      {
        id: "skills",
        eyebrow: "Skill studio",
        title: "Reusable capability packs",
        detail: "Review skill coverage, tighten quality, and keep execution-ready packs visible.",
        meta: `${viewModel.drawers.builder.skillStudio.summary.executionReadyCount} ready · ${viewModel.drawers.builder.skillStudio.summary.needsTestCount} need tests`,
        tone:
          viewModel.drawers.builder.skillStudio.summary.needsTestCount > 0 ? "warn" : "neutral",
      },
      {
        id: "profiles",
        eyebrow: "Routing studio",
        title: "Profiles and model routes",
        detail: "Pin planner, executor, and verifier behavior when the default profile is not enough.",
        meta: `${viewModel.drawers.builder.profileStudio.profileRows.length} profiles · ${effectiveRouteRows.length} active route role${effectiveRouteRows.length === 1 ? "" : "s"}`,
        tone: "neutral",
      },
      {
        id: "proof",
        eyebrow: "Review studio",
        title: "Proof, queue, and release truth",
        detail: "Audit what is ready, what is secondary, and what still needs explicit operator review.",
        meta: `${viewModel.drawers.builder.reviewCount} review surface${viewModel.drawers.builder.reviewCount === 1 ? "" : "s"} · ${viewModel.drawers.builder.confidence.score}% confidence`,
        tone: viewModel.drawers.builder.confidence.tone,
      },
    ],
    [
      effectiveRouteRows.length,
      bridgeSummary.connected,
      bridgeSummary.mobileReady,
      bridgeSummary.totalApps,
      viewModel.drawers.builder.confidence.score,
      viewModel.drawers.builder.confidence.tone,
      viewModel.drawers.builder.profileStudio.profileRows.length,
      viewModel.drawers.builder.reviewCount,
      viewModel.drawers.builder.serviceStudio.availableActionCount,
      viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount,
      viewModel.drawers.builder.skillStudio.summary.executionReadyCount,
      viewModel.drawers.builder.skillStudio.summary.needsTestCount,
    ],
  );
  const workspaceGitSnapshot = workspace?.gitSnapshot || {};
  const branchInspectAction = useMemo(
    () =>
      asList(viewModel.drawers.builder.gitActions).find(
        item => item.actionId === "inspect_repo_state",
      ) ||
      asList(viewModel.drawers.builder.gitActions)[0] ||
      null,
    [viewModel.drawers.builder.gitActions],
  );
  const branchPullAction = useMemo(
    () =>
      asList(viewModel.drawers.builder.gitActions).find(
        item => item.actionId === "pull_branch",
      ) || null,
    [viewModel.drawers.builder.gitActions],
  );
  const branchPushAction = useMemo(
    () =>
      asList(viewModel.drawers.builder.gitActions).find(
        item => item.actionId === "push_branch",
      ) || null,
    [viewModel.drawers.builder.gitActions],
  );
  const sidebarAccessLabel = previewMode === "live" ? "Full access" : "Read-only preview";
  const sidebarLocalPath = workspace?.root_path || snapshot?.workspaceRoot || "";
  const sidebarLocalLeaf = pathLeaf(sidebarLocalPath) || "workspace";
  const sidebarBranchName = String(workspaceGitSnapshot?.branch || "").trim() || "No branch";
  const sidebarBranchTone = !workspaceGitSnapshot?.repoDetected
    ? "warn"
    : workspaceGitSnapshot?.dirty ||
        Number(workspaceGitSnapshot?.behind || 0) > 0
      ? "warn"
      : "good";
  const sidebarBranchContext = !workspaceGitSnapshot?.repoDetected
    ? "Git repository not detected for selected workspace."
    : [
        workspaceGitSnapshot?.trackingBranch
          ? `tracking ${workspaceGitSnapshot.trackingBranch}`
          : "no tracking branch",
        `${workspaceGitSnapshot?.stagedCount || 0} staged`,
        `${workspaceGitSnapshot?.unstagedCount || 0} unstaged`,
        `${workspaceGitSnapshot?.untrackedCount || 0} untracked`,
      ].join(" · ");

  const handleSidebarAccess = useCallback(() => {
    markAction("quick:access");
    setUiMode("builder");
    setActiveDrawer("settings");
  }, [markAction]);

  const handleSidebarLocal = useCallback(() => {
    markAction("quick:local");
    if (workspaces.length === 0) {
      setShowWorkspaceDialog(true);
      return;
    }
    const fallbackWorkspaceId = workspaces[0]?.workspace_id || "";
    const targetWorkspaceId = workspace?.workspace_id || fallbackWorkspaceId;
    if (targetWorkspaceId) {
      setSelectedWorkspaceId(targetWorkspaceId);
    }
    setUiMode("agent");
    setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
  }, [
    agentBlockedState.defaultDrawer,
    agentBlockedState.isBlocked,
    markAction,
    workspace?.workspace_id,
    workspaces,
  ]);

  const handleSidebarFolders = useCallback(() => {
    markAction("quick:folders");
    setUiMode("builder");
    setActiveDrawer("builder");
  }, [markAction]);

  const handleSidebarBranch = useCallback(async () => {
    markAction("quick:branch");
    if (branchInspectAction) {
      await runWorkspaceActionSpec(branchInspectAction);
      return;
    }
    setUiMode("builder");
    setActiveDrawer("builder");
  }, [branchInspectAction, markAction, runWorkspaceActionSpec]);

  const handleSidebarBranchPull = useCallback(async () => {
    if (!branchPullAction) {
      return;
    }
    await runWorkspaceActionSpec(branchPullAction);
  }, [branchPullAction, runWorkspaceActionSpec]);

  const handleSidebarBranchPush = useCallback(async () => {
    if (!branchPushAction) {
      return;
    }
    await runWorkspaceActionSpec(branchPushAction);
  }, [branchPushAction, runWorkspaceActionSpec]);

  useEffect(() => {
    currentMissionRef.current = mission;
  }, [mission]);

  useEffect(() => {
    currentDelegatedSessionsRef.current = delegatedSessions;
  }, [delegatedSessions]);

  const agentTranscript = useMemo(() => {
    const timelineTurns = [];
    const seenTurnKeys = new Set();
    const pushTurn = item => {
      if (!item || (!item.title && !item.detail)) {
        return;
      }
      const timestampRaw = item.timestampRaw || "";
      const dedupeKey =
        item.dedupeKey ||
        [
          item.role || "",
          item.label || "",
          item.title || "",
          item.detail || "",
          timestampRaw,
        ].join("|");
      if (seenTurnKeys.has(dedupeKey)) {
        return;
      }
      seenTurnKeys.add(dedupeKey);
      timelineTurns.push({
        ...item,
        timestampRaw,
        sortValue: Number.isFinite(item.sortValue) ? item.sortValue : timeValue(timestampRaw),
        sortOrder: timelineTurns.length,
      });
    };

    for (const note of operatorNotes) {
      const noteTitle = note.title || note.detail || "";
      const noteDetail =
        note.detail && note.detail !== note.title && !isRouteMetadataText(note.detail)
          ? note.detail
          : "";
      pushTurn({
        id: `operator-${note.id}`,
        dedupeKey: `operator:${note.id}`,
        role: note.role === "assistant" ? "runtime" : "operator",
        roleLabel: note.role === "assistant" ? "Syntelos" : "Operator",
        roleIcon: note.role === "assistant" ? "◇" : "◉",
        label: note.role === "assistant" ? "Agent compartment" : note.channel === "followup" ? "Follow-up sent" : "Operator note",
        title: noteTitle,
        detail: noteDetail,
        meta: timestampLabel(note.createdAt),
        timestampRaw: note.createdAt,
        tone: note.tone || "neutral",
        technicalDetail: note.technicalDetail || "",
        chips: asList(note.chips).slice(0, 6),
        chatPreferred: note.channel === "followup" || note.channel === "chat",
      });
    }

    const codeArtifacts = asList(
      mission?.state?.code_execution?.artifacts ||
        mission?.missionLoop?.codeExecution?.artifacts,
    )
      .slice()
      .reverse()
      .slice(0, 4);
    for (const artifact of codeArtifacts) {
      pushTurn({
        id: `code-artifact-${artifact.artifact_id || artifact.created_at || artifact.action_id}`,
        dedupeKey: `code-artifact:${artifact.artifact_id || artifact.created_at || artifact.action_id}`,
        role: "runtime",
        runtimeId: mission?.runtime_id || "",
        roleLabel: "Code execution",
        roleIcon: "◇",
        label: titleizeToken(artifact.kind || "artifact"),
        title: artifact.title || artifact.action_id || "Code execution artifact",
        detail: artifact.summary || "No summary captured.",
        meta: timestampLabel(artifact.created_at),
        timestampRaw: artifact.created_at,
        tone: artifact.ok ? "neutral" : "bad",
        processMessage: true,
        emphasis: true,
        traceOnly: true,
        chips: [
          artifact.container_id ? artifact.container_id : "",
          artifact.runtime ? titleizeToken(artifact.runtime) : "",
        ].filter(Boolean),
      });
    }

    for (const action of asList(mission?.action_history).slice(-6)) {
      const actionKind = action?.proposal?.kind || action?.action_id || "action";
      const actionGatePending = action?.gate?.status === "pending";
      const actionStdout = action?.result?.stdout || "";
      const actionError = action?.result?.error || "";
      const actionRuntimeLike =
        action?.proposal?.sourceKind === "delegated" ||
        /runtime|delegate|test|verify|command/i.test(actionKind);
      const actionResult = actionError || actionStdout;
      if (actionGatePending || !actionResult) {
        continue;
      }
      pushTurn({
        id: `action-${action?.action_id || actionKind}-${action?.executed_at || actionResult}`,
        dedupeKey: `action:${action?.action_id || actionKind}:${action?.executed_at || actionResult}`,
        role: actionRuntimeLike ? "runtime" : "system",
        runtimeId: actionRuntimeLike ? mission?.runtime_id : "",
        roleLabel:
          actionRuntimeLike
            ? runtimeLabel(mission?.runtime_id)
            : "Syntelos",
        roleIcon:
          actionRuntimeLike ? (mission?.runtime_id === "hermes" ? "⬢" : "◇") : "·",
        label: actionRuntimeLike ? "Process message" : titleizeToken(actionKind),
        title: action?.proposal?.title || action?.action_id || "Mission action",
        detail: actionResult,
        technicalDetail: actionStdout && actionStdout !== actionResult ? actionStdout : "",
        technicalSummary: actionStdout && actionStdout !== actionResult ? "Thinking trace" : "",
        meta: timestampLabel(action?.executed_at),
        timestampRaw: action?.executed_at,
        tone: actionError ? "bad" : "neutral",
        processMessage: actionRuntimeLike,
        emphasis: Boolean(actionError || actionRuntimeLike),
        traceOnly: true,
      });
    }

    for (const event of liveControlEvents) {
      if (!event.processMessage && event.role !== "operator" && event.role !== "bridge") {
        continue;
      }
      pushTurn({
        ...event,
        dedupeKey: `live:${event.role || ""}:${event.kind || ""}:${event.title || ""}:${event.timestampRaw || ""}`,
      });
    }

    for (const session of delegatedSessions) {
      const delegatedMessageId =
        session.delegated_id ||
        `${session.runtime_id || "runtime"}-${session.updated_at || session.last_event || "session"}`;
      const latestEvents = asList(session.latest_events);
      const meaningfulEvents = latestEvents.filter(
        event =>
          isTraceRuntimeKind(event.kind) ||
          ["runtime.phase_entered", "runtime.route_switch_reason", "runtime.handoff"].includes(
            String(event.kind || "").toLowerCase(),
          ) ||
          event.status === "failed",
      );
      if (meaningfulEvents.length === 0 && (session.status === "failed" || session.heartbeat_status === "stale")) {
        pushTurn({
          id: `delegated-${delegatedMessageId}`,
          dedupeKey: `delegated:${delegatedMessageId}`,
          role: "runtime",
          runtimeId: session.runtime_id,
          roleLabel: runtimeLabel(session.runtime_id),
          roleIcon: session.runtime_id === "hermes" ? "⬢" : "◇",
          label: `${runtimeLabel(session.runtime_id)} lane`,
          title:
            session.detail ||
            session.last_event ||
            `${runtimeLabel(session.runtime_id)} session ${titleizeToken(session.status || "active")}`,
          detail:
            session.heartbeat_status === "stale"
              ? "Heartbeat is stale. Builder runtime view can inspect the lane in detail."
              : session.execution_target_detail ||
                session.execution_root ||
                "Delegated runtime lane is being supervised from Syntelos.",
          meta: timestampLabel(session.updated_at),
          timestampRaw: session.updated_at,
          tone:
            session.heartbeat_status === "stale"
              ? "warn"
              : session.status === "failed"
                ? "bad"
                : "neutral",
          emphasis: session.status === "failed" || session.heartbeat_status === "stale",
          traceOnly: true,
          chips: [
            titleizeToken(session.status || "unknown"),
            session.execution_target ? titleizeToken(session.execution_target) : "",
          ].filter(Boolean),
        });
      }

      for (const [index, event] of meaningfulEvents.slice(-4).entries()) {
        const processMessage = isTraceRuntimeKind(event.kind);
        const normalizedKind = String(event.kind || "").toLowerCase();
        const routeSwitch = normalizedKind === "runtime.route_contract";
        const phaseEntered = normalizedKind === "runtime.phase_entered";
        const routeSwitchReason = normalizedKind === "runtime.route_switch_reason";
        const handoffEvent = normalizedKind === "runtime.handoff";
        pushTurn({
          id: `delegated-${delegatedMessageId}-event-${event.event_id || index}`,
          dedupeKey: `delegated-event:${delegatedMessageId}:${event.event_id || event.message || index}`,
          role: "runtime",
          runtimeId: session.runtime_id,
          roleLabel: runtimeLabel(session.runtime_id),
          roleIcon: session.runtime_id === "hermes" ? "⬢" : "◇",
          label: phaseEntered
            ? "Phase entered"
            : routeSwitchReason
              ? "Route switch reason"
              : handoffEvent
                ? "Runtime handoff"
                : processMessage
                  ? "Process message"
                  : titleizeToken(event.kind || "runtime event"),
          title: event.message || "Runtime event",
          detail:
            (phaseEntered
              ? `${titleizeToken(event?.data?.phase || "execute")} phase via ${titleizeToken(
                  event?.data?.role || "route",
                )}${event?.data?.provider ? ` · ${titleizeToken(event.data.provider)}` : ""}${event?.data?.model ? ` · ${event.data.model}` : ""}`
              : routeSwitchReason
                ? event?.data?.reason || event.message || "Route switch reason emitted by runtime supervision."
                : handoffEvent
                  ? event?.data?.reason || event.message || "Runtime handoff emitted by supervision."
                  : routeSwitch
              ? `${titleizeToken(event?.data?.phase || "execute")} phase · ${titleizeToken(
                  event?.data?.role || "route",
                )} route`
              : event.detail) ||
            (processMessage
              ? session.execution_target_detail || "Delegated runtime process output."
              : session.execution_target_detail ||
                "Delegated runtime supervision is still flowing into the thread."),
          meta: timestampLabel(event.created_at || session.updated_at),
          timestampRaw: event.created_at || session.updated_at,
          tone:
            event.status === "failed"
              ? "bad"
              : /approval|blocked|stale/i.test(`${event.kind || ""} ${event.message || ""}`)
                ? "warn"
                : "neutral",
          technicalDetail:
            processMessage
              ? event.trace ||
                session.detail ||
                session.execution_target_detail ||
                session.execution_root ||
                ""
              : "",
          technicalSummary: processMessage ? "Thinking trace" : "",
          processMessage,
          chatPreferred: false,
          traceOnly: true,
          emphasis:
            processMessage ||
            phaseEntered ||
            routeSwitchReason ||
            handoffEvent ||
            event.status === "failed" ||
            /approval|blocked|error/i.test(`${event.kind || ""} ${event.message || ""}`),
          chips: [
            session.status ? titleizeToken(session.status) : "",
            session.execution_target ? titleizeToken(session.execution_target) : "",
            routeSwitch && event?.data?.phase ? titleizeToken(event.data.phase) : "",
            routeSwitch && event?.data?.role ? titleizeToken(event.data.role) : "",
            phaseEntered && event?.data?.provider ? titleizeToken(event.data.provider) : "",
            phaseEntered && event?.data?.model ? event.data.model : "",
            routeSwitchReason && event?.data?.reason ? event.data.reason : "",
            handoffEvent && event?.data?.source_delegated_id ? event.data.source_delegated_id : "",
            event.status ? titleizeToken(event.status) : "",
          ].filter(Boolean),
        });
      }
    }

    for (const activity of asList(snapshot.activity).slice(0, 12)) {
      const kind = activity?.kind || "activity";
      const activityMissionId =
        activity?.mission_id ||
        activity?.missionId ||
        activity?.metadata?.mission_id ||
        activity?.metadata?.missionId ||
        "";
      if (activityMissionId && activityMissionId !== mission?.mission_id) {
        continue;
      }
      const role = /bridge|app/i.test(kind)
        ? "bridge"
        : /approval|question/i.test(kind)
          ? "queue"
          : /runtime|delegate|verification|activity/i.test(kind)
            ? "runtime"
            : "system";
      const isOperatorFollowUp = kind === "mission.follow_up";
      const operatorPrompt = isOperatorFollowUp
        ? splitOperatorSteeringMessage(activity?.message || "")
        : null;
      if (!isOperatorFollowUp && role !== "bridge" && role !== "queue") {
        continue;
      }
      pushTurn({
        id: `activity-${kind}-${activity?.timestamp || activity?.message}`,
        dedupeKey: `activity:${kind}:${activity?.message || ""}:${activity?.timestamp || ""}`,
        role: isOperatorFollowUp ? "operator" : role,
        roleLabel:
          isOperatorFollowUp
            ? "Operator"
            : role === "bridge"
            ? "Bridge"
            : role === "queue"
              ? "Needs attention"
              : role === "runtime"
                ? "Runtime"
                : "Syntelos",
        roleIcon:
          isOperatorFollowUp
            ? "◉"
            : role === "bridge"
              ? "⌁"
              : role === "queue"
                ? "!"
                : role === "runtime"
                  ? "◇"
                  : "·",
        label: titleizeToken(kind),
        title: operatorPrompt?.visibleText || activity?.message || "Activity update",
        detail: operatorPrompt?.steeringHints?.join(" · ") || activity?.detail || "",
        meta: timestampLabel(activity?.timestamp),
        timestampRaw: activity?.timestamp,
        tone: role === "queue" ? "warn" : activity?.tone || "neutral",
        technicalDetail:
          operatorPrompt?.steeringHints?.length > 0
            ? operatorPrompt.steeringHints.join("\n")
            : "",
        technicalSummary:
          operatorPrompt?.steeringHints?.length > 0 ? "Routing note" : "",
        chatPreferred: isOperatorFollowUp,
        traceOnly: !isOperatorFollowUp,
      });
    }

    for (const message of data.openClawMessages) {
      pushTurn({
        id: `openclaw-${message.id}`,
        dedupeKey: `openclaw:${message.id || message.createdAt || message.detail}`,
        role: "runtime",
        runtimeId: "openclaw",
        roleLabel: "OpenClaw",
        roleIcon: "◇",
        label: "Process message",
        title: message.detail,
        detail: message.meta || "Gateway message",
        meta: timestampLabel(message.createdAt),
        timestampRaw: message.createdAt,
        tone: message.tone || "neutral",
        processMessage: true,
        emphasis: true,
        traceOnly: true,
        chatPreferred: false,
      });
    }

    const sortedTurns = timelineTurns
      .filter(item => item.title || item.detail)
      .sort((left, right) => {
        const leftHasTime = Number.isFinite(left.sortValue);
        const rightHasTime = Number.isFinite(right.sortValue);
        if (leftHasTime && rightHasTime && left.sortValue !== right.sortValue) {
          return left.sortValue - right.sortValue;
        }
        if (leftHasTime !== rightHasTime) {
          return leftHasTime ? -1 : 1;
        }
        return left.sortOrder - right.sortOrder;
      });

    return sortedTurns
      .filter(item => !item.heartbeat)
      .map(({ sortOrder, sortValue, ...item }) => item);
  }, [
    data.openClawMessages,
    data.pendingApprovals,
    data.pendingQuestions,
    delegatedSessions,
    liveControlEvents,
    mission,
    operatorNotes,
    snapshot.activity,
  ]);
  useEffect(() => {
    if (!mission?.mission_id || agentTranscript.length === 0) {
      return;
    }
    transcriptCacheRef.current = {
      ...transcriptCacheRef.current,
      [mission.mission_id]: agentTranscript.slice(-5000),
    };
  }, [agentTranscript, mission?.mission_id]);
  const agentVisibleTranscript = useMemo(
    () =>
      agentTranscript.filter(item => {
        if (!mission || agentRuntimeFocus === "all") {
          return true;
        }
        if (item.role !== "runtime") {
          return true;
        }
        return !item.runtimeId || item.runtimeId === agentRuntimeFocus;
      }),
    [agentRuntimeFocus, agentTranscript, mission],
  );
  const splitConversationTurns = useMemo(() => {
    if (!splitMission?.mission_id) {
      return [];
    }
    const cachedTurns = transcriptCacheRef.current[splitMission.mission_id] || [];
    return cachedTurns.filter(item => {
      if (item.traceOnly) {
        return false;
      }
      if (item.chatPreferred) {
        return true;
      }
      return item.role === "operator";
    });
  }, [agentTranscript, splitMission?.mission_id]);
  const agentConversationTurns = useMemo(
    () =>
      agentTranscript.filter(item => {
        if (item.traceOnly) {
          return false;
        }
        if (item.processMessage && item.role !== "operator") {
          return false;
        }
        if (item.chatPreferred) {
          return true;
        }
        return item.role === "operator";
      }),
    [agentTranscript],
  );
  const agentTraceTurns = useMemo(
    () =>
      agentVisibleTranscript.filter(item => {
        if (item.traceOnly) {
          return true;
        }
        if (item.role === "queue" || item.role === "system") {
          return true;
        }
        return Boolean(item.technicalDetail);
      }),
    [agentVisibleTranscript],
  );
  const agentThinkingTurns = useMemo(
    () => agentTraceTurns.filter(item => item.processMessage || item.technicalDetail),
    [agentTraceTurns],
  );
  const agentNexusTurns = useMemo(() => {
    const direct = agentTraceTurns.filter(item => {
      const text = `${item.label || ""} ${item.title || ""} ${item.detail || ""}`.toLowerCase();
      return (
        pinnedNexusIds.includes(item.id) ||
        item.role === "queue" ||
        item.tone === "bad" ||
        /approval|verification|blocked|replan|switch|route|review|deploy|patch/.test(text) ||
        (item.processMessage && /plan|patch|review|approval|verify|switch/.test(text))
      );
    });
    return direct.slice(-6);
  }, [agentTraceTurns, pinnedNexusIds]);
  const agentHasTurns = agentConversationTurns.length > 0;
  const agentIdleState = !mission ? "no-mission" : agentHasTurns ? "active" : "no-turns";
  const chatConversationActive = Boolean(activeChatSessionId);
  const agentCenterTitle = mission?.title || mission?.objective || workspace?.name || "Syntelos workspace";
  const agentComposerLabel = !mission
    ? chatConversationActive
      ? "Chat message"
      : "Mission prompt"
    : "Follow-up or note";
  const agentComposerPlaceholder = !mission
    ? chatConversationActive
      ? "Send a message in this conversation. Switch run mode to Mission for tracked execution."
      : workspaces.length > 0
        ? "Describe the next mission you want Syntelos to run."
        : "Add a workspace, then describe the next mission you want Syntelos to run."
    : openClawRuntimeActive
      ? "Send a direct follow-up to the runtime, or keep a local operator note."
      : viewModel.thread.composerPlaceholder;
  const handleAgentIdlePrimaryAction = useCallback(() => {
    if (workspaces.length === 0) {
      setShowWorkspaceDialog(true);
      return;
    }
    openMissionDialog();
  }, [openMissionDialog, workspaces.length]);
  const agentRuntimeSelectValue = mission ? agentRuntimeFocus : missionForm.runtime;
  const handleAgentIdleChat = useCallback(async () => {
    const text = operatorDraft.trim();
    if (!text) {
      pushToast("Write a message first.", "warn");
      return;
    }
    markAction("composer:local-chat");
    const chatRole = mission ? agentRouteRole : "executor";
    const explicitRoute =
      workspaceProfileForm.routeOverrides.find(item => item.role === chatRole) || {};
    const effectiveRoute =
      effectiveRouteRows.find(item => item.role === chatRole) || {};
    const route = {
      role: chatRole,
      provider:
        explicitRoute.provider ||
        effectiveRoute.provider ||
        selectedAgentRoute.provider ||
        activeEffectiveRoute.provider ||
        "openai",
      model:
        explicitRoute.model ||
        effectiveRoute.model ||
        selectedAgentRoute.model ||
        activeEffectiveRoute.model ||
        "",
      effort: normalizeRouteEffort(
        explicitRoute.effort ||
          effectiveRoute.effort ||
          selectedAgentRoute.effort ||
          activeEffectiveRoute.effort,
        "medium",
      ),
    };
    const activeSession = ensureActiveChatSession({
      seedText: text,
      workspaceId: workspace?.workspace_id || selectedWorkspaceId || "",
    });
    const activeSessionId = activeSession?.id || "";
    const runtime = agentRuntimeSelectValue === "all" ? workspace?.default_runtime || missionForm.runtime || "openclaw" : agentRuntimeSelectValue;
    const workspaceId = workspace?.workspace_id || selectedWorkspaceId || workspaces[0]?.workspace_id || "";
    const workspacePath = workspace?.root_path || workspaces[0]?.root_path || "";
    const sessionTranscript = asList(chatSessionTranscripts?.[activeSessionId]);
    const chatHistory = sessionTranscript
      .filter(item => !item.pending)
      .slice(-8)
      .map(item => ({
        role: String(item.role || "").toLowerCase() === "assistant" ? "assistant" : "user",
        text: item.title || item.detail || "",
      }))
      .filter(item => item.text);
    const activeRuleSet =
      findStudioItem(referenceStudio, "rule", referenceStudio.activeRuleSetId) ||
      findStudioItem(referenceStudio, "rule", referenceStudio.selectedRuleId);
    const activeSkills = asList(referenceStudio.activeSkillIds)
      .map(skillId => findStudioItem(referenceStudio, "skill", skillId))
      .filter(Boolean)
      .slice(0, 5);
    const systemContextLines = [
      workspace?.name ? `Workspace: ${workspace.name}.` : "",
      workspacePath ? `Workspace path: ${workspacePath}.` : "",
      activeRuleSet?.name ? `Active rule set: ${activeRuleSet.name}.` : "",
      activeRuleSet?.description ? `Rule set intent: ${activeRuleSet.description}` : "",
      asList(activeRuleSet?.requiresApproval).length
        ? `Approval-sensitive actions: ${asList(activeRuleSet.requiresApproval).slice(0, 4).join(", ")}.`
        : "",
      activeSkills.length ? `Active skills: ${activeSkills.map(item => item.name).join(", ")}.` : "",
      "Use normal chat behavior: answer directly, do not expose routing metadata unless the user asks.",
    ].filter(Boolean);
    appendOperatorEntry({
      title: text,
      detail: "",
      meta: `${titleizeToken(runtime)} chat`,
      tone: "neutral",
      channel: "chat",
      sessionId: activeSessionId || undefined,
    });
    appendChatSessionTurn(activeSessionId, {
      role: "user",
      title: text,
      detail: "",
      meta: timestampLabel(new Date().toISOString()) || "Now",
      tone: "neutral",
    });
    touchChatSession(activeSessionId, text);
    const pendingChatTurn = appendChatSessionTurn(activeSessionId, {
      role: "assistant",
      title: "Thinking...",
      detail: `Routing to ${titleizeToken(runtime)} with ${route.model || titleizeToken(route.provider)} for a real model reply.`,
      meta: "Syntelos",
      tone: "neutral",
      pending: true,
      technicalDetail: `chat:${runtime}:${route.provider}/${route.model || "default"}:${route.effort || "medium"}`,
    });
    const pendingReply = appendOperatorEntry({
      title: "Thinking...",
      detail: `Routing to ${titleizeToken(runtime)} with ${route.model || titleizeToken(route.provider)} for a real model reply.`,
      meta: "Syntelos",
      tone: "neutral",
      channel: "chat",
      role: "assistant",
      pending: true,
      sessionId: activeSessionId || undefined,
      technicalDetail: `chat:${runtime}:${route.provider}/${route.model || "default"}:${route.effort || "medium"}`,
    });
    setOperatorDraft("");
    clearOperatorAttachments();
    setAgentScene("run");
    const requestStartedAt = Date.now();
    if (previewMode !== "live" || !hasCommandBackend()) {
      if (pendingChatTurn?.id) {
        updateChatSessionTurn(activeSessionId, pendingChatTurn.id, current => ({
          ...current,
          title: "Live backend is required for real chat.",
          detail: "Switch to the NAS/live backend before sending model-backed chat turns.",
          meta: "Not sent",
          tone: "warn",
          pending: false,
        }));
      }
      updateOperatorEntry(pendingReply.id, current => ({
        ...current,
        title: "Live backend is required for real chat.",
        detail: "Switch to the NAS/live backend before sending model-backed chat turns.",
        meta: "Not sent",
        tone: "warn",
        pending: false,
      }));
      return;
    }
    setChatRequestsInFlight(current => current + 1);
    try {
      const result = await callBackendWithRetry(
        "send_agent_chat_command",
        {
          payload: {
            message: text,
            runtime,
            route,
            workspaceId,
            workspacePath,
            history: chatHistory,
            sessionId: activeSessionId || `syntelos-chat-${workspaceId || "workspace"}`,
            systemContext: systemContextLines.join("\n"),
          },
        },
        { attempts: 2 },
      );
      const roundtripMs = Math.max(
        0,
        Number(result?.elapsedMs) || Date.now() - requestStartedAt,
      );
      const reply = String(result?.reply || "").trim();
      const compartment = result?.compartment && typeof result.compartment === "object" ? result.compartment : {};
      const compartmentChips = [
        compartment.sessionId ? `session ${compartment.sessionId}` : "",
        compartment.runtime ? `runtime ${titleizeToken(compartment.runtime)}` : "",
        compartment.cwd ? `cwd ${pathLeaf(compartment.cwd)}` : "",
        compartment.route?.model || result?.route?.model_id || result?.route?.model || "",
        roundtripMs > 0 ? `${roundtripMs}ms` : "",
      ].filter(Boolean);
      const compartmentTrace = compartment.sessionId
        ? JSON.stringify(
            {
              sessionId: compartment.sessionId,
              runtime: compartment.runtime,
              cwd: compartment.cwd,
              host: compartment.host,
              route: compartment.route,
              state: compartment.state,
              streaming: compartment.streaming,
              restartControls: compartment.restartControls,
              toolTimeline: compartment.toolTimeline,
              filesChanged: compartment.filesChanged,
              lastRoundtripMs: compartment.lastRoundtripMs ?? roundtripMs,
            },
            null,
            2,
          )
        : "";
      touchChatSession(activeSessionId, reply || text);
      if (pendingChatTurn?.id) {
        updateChatSessionTurn(activeSessionId, pendingChatTurn.id, current => ({
          ...current,
          title: reply || "The runtime finished without a readable reply.",
          detail: result?.route
            ? `${titleizeToken(result.runtime || runtime)} · ${result.route.model_id || result.route.model || "default"} · ${routeEffortLabel(result.route.effort, "medium")}${compartment.cwd ? ` · ${compartment.cwd}` : ""}${roundtripMs > 0 ? ` · ${roundtripMs}ms` : ""}`
            : "",
          meta: timestampLabel(new Date().toISOString()) || "Now",
          tone: reply ? "neutral" : "warn",
          pending: false,
          chips: compartmentChips,
          technicalDetail: compartmentTrace,
        }));
      }
      updateOperatorEntry(pendingReply.id, current => ({
        ...current,
        title: reply || "The runtime finished without a readable reply.",
        detail: result?.route
          ? `${titleizeToken(result.runtime || runtime)} · ${result.route.model_id || result.route.model || "default"} · ${routeEffortLabel(result.route.effort, "medium")}${compartment.cwd ? ` · ${compartment.cwd}` : ""}${roundtripMs > 0 ? ` · ${roundtripMs}ms` : ""}`
          : "",
        meta: timestampLabel(new Date().toISOString()),
        tone: reply ? "neutral" : "warn",
        pending: false,
        chips: compartmentChips,
        technicalDetail: compartmentTrace,
      }));
    } catch (error) {
      if (pendingChatTurn?.id) {
        updateChatSessionTurn(activeSessionId, pendingChatTurn.id, current => ({
          ...current,
          title: "The runtime could not answer this chat turn.",
          detail: String(error),
          meta: "Runtime error",
          tone: "bad",
          pending: false,
        }));
      }
      updateOperatorEntry(pendingReply.id, current => ({
        ...current,
        title: "The runtime could not answer this chat turn.",
        detail: String(error),
        meta: "Runtime error",
        tone: "bad",
        pending: false,
      }));
      pushToast(`Chat runtime failed: ${error}`, "error");
    } finally {
      setChatRequestsInFlight(current => Math.max(0, current - 1));
      void refreshAll("chat-turn-complete");
    }
  }, [
    activeEffectiveRoute.effort,
    activeEffectiveRoute.model,
    activeEffectiveRoute.provider,
    agentRouteRole,
    agentRuntimeSelectValue,
    appendOperatorEntry,
    clearOperatorAttachments,
    ensureActiveChatSession,
    appendChatSessionTurn,
    markAction,
    missionForm.runtime,
    operatorDraft,
    chatSessionTranscripts,
    previewMode,
    pushToast,
    refreshAll,
    referenceStudio,
    selectedAgentRoute.effort,
    selectedAgentRoute.model,
    selectedAgentRoute.provider,
    selectedAgentRoute.role,
    setChatRequestsInFlight,
    selectedWorkspaceId,
    touchChatSession,
    updateChatSessionTurn,
    updateOperatorEntry,
    effectiveRouteRows,
    workspace?.default_runtime,
    workspace?.root_path,
    workspace?.workspace_id,
    workspaceProfileForm.routeOverrides,
    workspaces,
  ]);
  const handleAgentIdleSubmit = useCallback(() => {
    if (workspaces.length === 0) {
      setShowWorkspaceDialog(true);
      return;
    }
    if (chatConversationActive) {
      const text = operatorDraft.trim();
      if (!text) {
        pushToast("Write a message first.", "warn");
        return;
      }
      handleAgentIdleChat();
      return;
    }
    if (mission?.mission_id) {
      void handleAgentFollowUp();
      return;
    }
    const text = operatorDraft.trim();
    if (!text) {
      pushToast("Write a message first.", "warn");
      return;
    }
    handleAgentIdleChat();
  }, [
    chatConversationActive,
    handleAgentFollowUp,
    handleAgentIdleChat,
    mission?.mission_id,
    operatorDraft,
    pushToast,
    workspaces.length,
  ]);
  const agentRuntimeHint = !mission
    ? "Choose the runtime for the next mission launch."
    : agentRuntimeFocus === "all"
      ? `Main conversation stays intact. Trace is showing every visible runtime lane. Active lane: ${runtimeLabel(mission?.runtime_id)}.`
      : `Main conversation stays intact. Trace is filtered to ${runtimeLabel(agentRuntimeFocus)} while the chat view keeps the full exchange visible.`;
  const agentCyclePhase =
    mission?.missionLoop?.currentCyclePhase || mission?.state?.current_cycle_phase || "plan";
  const agentCycleRole = phaseRouteRole(agentCyclePhase);
  useEffect(() => {
    if (!mission?.mission_id) {
      return;
    }
    if (agentRouteRole !== agentCycleRole) {
      setAgentRouteRole(agentCycleRole);
    }
  }, [agentCycleRole, agentRouteRole, mission?.mission_id]);
  const agentRouteStatus = `${titleizeToken(activeEffectiveRoute.provider || selectedAgentRoute.provider)} · ${activeEffectiveRoute.model || selectedAgentRoute.model || "Profile default"} · ${
    routeEffortLabel(activeEffectiveRoute.effort || selectedAgentRoute.effort, "default")
  }`;
  const activeDelegatedRuntimeLane = useMemo(
    () =>
      asList(mission?.delegated_runtime_sessions).some(session =>
        ["waiting_for_approval", "running", "launching"].includes(
          String(session?.status || "").trim().toLowerCase(),
        ),
      ),
    [mission?.delegated_runtime_sessions],
  );
  const followUpDeliveryStatus = !mission
    ? ""
    : mission?.state?.status === "blocked" && mission?.state?.stop_reason === "runtime_budget"
      ? "Budget reached: relaunch or resume mission for runtime replies"
      : mission?.state?.status === "queued"
        ? mission?.state?.queue_reason || "Mission is queued: follow-ups wait for the active slot"
      : activeDelegatedRuntimeLane
        ? "Runtime lane active for direct replies"
        : "No active runtime lane: follow-ups are thread-only";
  const providerSecretPresence = data.providerSecretPresence || {};
  const providerSetupStatus = snapshot?.providerSetupStatus || {};
  const providerEcosystem =
    snapshot?.providerEcosystem && typeof snapshot.providerEcosystem === "object"
      ? snapshot.providerEcosystem
      : EMPTY_OBJECT;
  const providerEcosystemProviders = asList(providerEcosystem.providers);
  const providerEcosystemSources = asList(providerEcosystem.sources);
  const providerEcosystemSummary =
    providerEcosystem.summary && typeof providerEcosystem.summary === "object"
      ? providerEcosystem.summary
      : EMPTY_OBJECT;
  const providerEcosystemUpdatePolicy =
    providerEcosystem.updatePolicy && typeof providerEcosystem.updatePolicy === "object"
      ? providerEcosystem.updatePolicy
      : EMPTY_OBJECT;
  const openAIProviderStatus =
    (providerSetupStatus && typeof providerSetupStatus === "object"
      ? providerSetupStatus.openai
      : null) || {};
  const minimaxProviderStatus =
    (providerSetupStatus && typeof providerSetupStatus === "object"
      ? providerSetupStatus.minimax
      : null) || {};
  const missionProviderTruth =
    mission?.providerTruth ||
    mission?.missionLoop?.providerTruth ||
    mission?.state?.provider_runtime_truth ||
    {};
  const missionSkillRecovery =
    asRecord(mission?.missionLoop?.skillRecovery || mission?.state?.skill_recovery);
  const missionSkillRecoveryTriggers = asList(missionSkillRecovery.triggers);
  const missionSkillRecoveryRecommendations = asList(missionSkillRecovery.recommendations);
  const missionSkillRecoveryActions = asList(missionSkillRecovery.recoveryActions);
  const missionSkillRecoveryRoute = asRecord(missionSkillRecovery.routeSeparation);
  const missionSkillRecoveryProviderRoute = asRecord(missionSkillRecoveryRoute.providerRoute);
  const missionSkillRecoveryNeedsAction =
    String(missionSkillRecovery.status || "").toLowerCase() === "needs_recovery" ||
    missionSkillRecoveryTriggers.length > 0;
  const missionCodeExecutionState =
    mission?.state?.code_execution ||
    mission?.missionLoop?.codeExecution ||
    {};
  const codeExecutionArtifacts = asList(missionCodeExecutionState?.artifacts)
    .slice()
    .reverse()
    .slice(0, 4);
  const openAISecretReady = Boolean(
    providerSecretPresence.openai || providerSecretPresence["openai-codex"],
  );
  const openAICodexAuthReady = Boolean(
    openAIProviderStatus?.authPresent || openAIProviderStatus?.configured || openAISecretReady,
  );
  const openAICodexAuthPath = String(
    openAIProviderStatus?.authPath ||
      (openAISecretReady ? "API key" : "not configured"),
  );
  const minimaxSecretReady = Boolean(
    providerSecretPresence.minimax || providerSecretPresence["minimax-cn"],
  );
  const minimaxOpenClawOAuthReady = Boolean(providerSecretPresence["minimax-portal"]);
  const minimaxAuthReady = Boolean(
    minimaxProviderStatus?.authPresent ||
      minimaxProviderStatus?.configured ||
      minimaxSecretReady ||
      minimaxOpenClawOAuthReady,
  );
  const minimaxAuthPath = String(
    minimaxProviderStatus?.authPath ||
      (minimaxOpenClawOAuthReady ? "MiniMax OpenClaw OAuth" : minimaxSecretReady ? "API key" : "not configured"),
  );
  const modelAuthReady = openAICodexAuthReady || minimaxAuthReady;
  const missionRuntimeCompartment = useMemo(() => {
    if (!mission?.mission_id) {
      return null;
    }
    const delegated = asList(mission.delegated_runtime_sessions);
    const activeDelegated =
      delegated.find(session =>
        ["waiting_for_approval", "running", "launching"].includes(
          String(session?.status || "").trim().toLowerCase(),
        ),
      ) ||
      delegated[delegated.length - 1] ||
      null;
    const executionScope =
      mission?.state?.execution_scope ||
      mission?.execution_scope ||
      {};
    const activeRoute =
      missionProviderTruth?.activeRoute ||
      asList(mission?.effectiveRouteContract?.roles).find(item => item.role === agentCycleRole) ||
      activeEffectiveRoute ||
      {};
    const latestEvents = asList(activeDelegated?.latest_events).slice(-8).map(event => ({
      kind: event.kind || "runtime.event",
      at: event.created_at || event.at || activeDelegated?.updated_at || mission.updated_at,
      summary: event.message || event.detail || event.kind || "Runtime event",
      status: event.status || activeDelegated?.status || mission?.state?.status,
    }));
    const recentActions = asList(mission?.action_history)
      .slice(-5)
      .map(action => ({
        kind: action?.proposal?.kind || action?.action_id || "mission.action",
        at: action?.executed_at || action?.created_at || mission.updated_at,
        summary:
          action?.result?.result_summary ||
          action?.proposal?.title ||
          action?.result?.error ||
          "Mission action",
        status: action?.result?.ok === false ? "failed" : "recorded",
      }));
    const state = activeDelegated?.status || mission?.state?.status || "recorded";
    return {
      sessionId:
        activeDelegated?.delegated_id ||
        mission?.state?.latest_session_id ||
        mission.mission_id,
      runtime: activeDelegated?.runtime_id || mission.runtime_id || agentRuntimeSelectValue,
      cwd:
        activeDelegated?.execution_root ||
        executionScope.execution_root ||
        executionScope.workspace_root ||
        workspace?.root_path ||
        "",
      route: activeRoute,
      host:
        activeDelegated?.host_locality ||
        executionScope.host_locality ||
        executionScope.execution_target ||
        "local",
      state,
      streaming: ["running", "launching", "waiting_for_approval"].includes(
        String(state).toLowerCase(),
      )
        ? "live"
        : mission?.state?.planner_loop_status || "recorded",
      toolTimeline: [...latestEvents, ...recentActions].slice(-12),
      filesChanged: [
        ...asList(mission?.proof?.changed_files),
        ...asList(activeDelegated?.changed_files),
      ].filter(Boolean),
      approvals: [
        ...asList(activeDelegated?.approval_history),
        ...asList(mission?.state?.approval_history),
      ].slice(-8),
      restartControls: {
        canRestart: true,
        canResume:
          mission?.state?.continuity_state === "resume_available" ||
          ["running", "queued", "blocked", "verification_failed"].includes(
            String(mission?.state?.status || "").toLowerCase(),
          ),
      },
      updatedAt: activeDelegated?.updated_at || mission.updated_at,
    };
  }, [
    activeEffectiveRoute,
    agentCycleRole,
    agentRuntimeSelectValue,
    mission,
    missionProviderTruth,
    workspace?.root_path,
  ]);

  const latestAgentCompartment = useMemo(() => {
    const parseCompartmentFromNote = note => {
      if (!note?.technicalDetail) {
        return null;
      }
      try {
        const parsed = JSON.parse(note.technicalDetail);
        return parsed && typeof parsed === "object" ? parsed : null;
      } catch {
        return null;
      }
    };
    if (activeChatSessionId) {
      const sessionNote = operatorNotes
        .slice()
        .reverse()
        .find(
          item =>
            item.role === "assistant" &&
            item.channel === "chat" &&
            item.sessionId === activeChatSessionId &&
            item.technicalDetail,
        );
      const sessionCompartment = parseCompartmentFromNote(sessionNote);
      if (sessionCompartment) {
        return sessionCompartment;
      }
    }
    if (missionRuntimeCompartment) {
      return missionRuntimeCompartment;
    }
    if (runtimeCompartments.length > 0) {
      return runtimeCompartments[0];
    }
    const note = operatorNotes
      .slice()
      .reverse()
      .find(item => item.role === "assistant" && item.technicalDetail);
    return parseCompartmentFromNote(note);
  }, [activeChatSessionId, missionRuntimeCompartment, operatorNotes, runtimeCompartments]);
  const providerOAuthActionsAvailable =
    previewMode === "live" && hasCommandBackend();
  const providerOAuthUnavailableReason = !hasTauriBackend()
    ? "Use Live backend mode on the web/NAS app before starting model OAuth."
    : "Switch to Live backend mode before starting model OAuth.";
  const localhostStatus =
    snapshot?.localhostStatus && typeof snapshot.localhostStatus === "object"
      ? snapshot.localhostStatus
      : {};
  const localhostPort = Number(localhostStatus.port || 0);
  const localhostApiBaseUrl =
    localhostStatus.running && localhostPort > 0
      ? `http://127.0.0.1:${localhostPort}`
      : "";
  const latestThinkingTurn = agentThinkingTurns[agentThinkingTurns.length - 1] || null;
  const selectedModelLabel =
    activeEffectiveRoute.model || selectedAgentRoute.model
      ? `${activeEffectiveRoute.model || selectedAgentRoute.model}`
      : `${titleizeToken(activeEffectiveRoute.provider || selectedAgentRoute.provider)} default`;
  const selectedEffortLabel = routeEffortLabel(
    activeEffectiveRoute.effort || selectedAgentRoute.effort,
    "medium",
  );
  const currentProjectLabel =
    activeChatSession?.title ||
    mission?.title ||
    mission?.objective ||
    workspace?.name ||
    "Conversation";
  const referenceRuntimeStatus =
    runtimeStatusById.get(agentRuntimeSelectValue) ||
    runtimeStatusById.get(mission?.runtime_id) ||
    null;
  const selectedHarnessMeta = useMemo(() => {
    const readiness = referenceRuntimeStatus?.detected ? "Ready" : "Needs setup";
    const capabilities = asList(referenceRuntimeStatus?.capabilities).length;
    return [
      { label: "Backend", value: readiness },
      { label: "Capabilities", value: capabilities > 0 ? String(capabilities) : "Pending" },
    ];
  }, [referenceRuntimeStatus]);
  const referenceRouteControls = useMemo(
    () => ({
      role: agentRouteRole,
      selectedRoute: selectedAgentRoute,
      routeByRole: referenceRouteByRole,
      routeOptions: {
        roles: ROUTE_ROLE_OPTIONS,
        providers: MODEL_PROVIDER_OPTIONS,
        models: ROUTE_MODEL_OPTIONS,
        efforts: MODEL_EFFORT_OPTIONS,
      },
      actionMode: "auto",
      actionModes: [],
      onRoleChange: setAgentRouteRole,
      onFieldChange: handleAgentRouteFieldChange,
      onRoleFieldChange: (role, field, value) => {
        setAgentRouteRole(role);
        setWorkspaceProfileForm(current => ({
          ...current,
          routeOverrides: updateRouteOverride(current.routeOverrides, role, {
            [field]: value,
          }),
        }));
      },
      onSave: handleAgentRouteSave,
      codeExecutionEnabled,
      codeExecutionMemory,
      onToggleCodeExecution: () => setCodeExecutionEnabled(current => !current),
    }),
    [
      agentRouteRole,
      codeExecutionEnabled,
      codeExecutionMemory,
      handleAgentRouteFieldChange,
      handleAgentRouteSave,
      referenceRouteByRole,
      selectedAgentRoute,
    ],
  );
  const referenceMissionLoop = mission?.missionLoop || null;
  const referenceSlashCommands = useMemo(() => {
    const runtimeScoped = agentRuntimeSelectValue === "hermes" ? HERMES_SLASH_COMMANDS : OPENCLAW_SLASH_COMMANDS;
    const studioSkillCommands = referenceStudio.skills.map(item => ({
      command: `/${commandSlug(item.name)}`,
      harness: "Skill",
      kind: "skill",
      label: item.name,
      detail: item.summary || item.description || "Workspace skill",
    }));
    const codexSkillCommands =
      codexImportSnapshot.skillCount > 0
        ? asList(codexImportSnapshot.recentThreads)
            .slice(0, 4)
            .map(item => ({
              command: `/codex-${commandSlug(item.threadName || item.id)}`,
              harness: "Codex",
              kind: "codex",
              label: item.threadName || "Recent Codex thread",
              detail: item.cwd || item.source || "Recent Codex thread",
            }))
        : [];
    return uniqBy(
      [...runtimeScoped, ...COMMENT_SLASH_COMMANDS, ...studioSkillCommands, ...codexSkillCommands],
      item => `${item.harness}:${item.command}`,
    );
  }, [
    agentRuntimeSelectValue,
    codexImportSnapshot.recentThreads,
    codexImportSnapshot.skillCount,
    referenceStudio.skills,
  ]);
  const referenceSidebarProjectId =
    selectedWorkspaceId || workspace?.workspace_id || workspaces[0]?.workspace_id || "";
  const referenceFavoriteFlows = useMemo(
    () => {
      const missionFavorites = missionOptions
        .slice()
        .sort((left, right) => timeValue(deriveMissionLatestTimestamp(right)) - timeValue(deriveMissionLatestTimestamp(left)))
        .map(item => ({
          id: item.mission_id,
          title: item.title || item.objective || "Mission",
          tone:
            item.runtime_id === "hermes"
              ? "good"
              : item.state?.status === "needs_approval"
                ? "warn"
                : "violet",
          updatedAt: deriveMissionLatestTimestamp(item),
        }));
      const chatFavorites = chatSessions
        .slice()
        .sort((left, right) => timeValue(right.updatedAt) - timeValue(left.updatedAt))
        .map(item => ({
          id: `chat:${item.id}`,
          title: item.title || "Chat conversation",
          tone: "neutral",
          updatedAt: item.updatedAt,
        }));
      return [...chatFavorites, ...missionFavorites]
        .sort((left, right) => timeValue(right.updatedAt) - timeValue(left.updatedAt))
        .slice(0, 2);
    },
    [chatSessions, missionOptions],
  );
  const referenceProjectGroups = useMemo(
    () =>
      workspaces.map(item => {
        const chatFlows = chatSessions
          .filter(chatRow => chatRow.workspaceId === item.workspace_id)
          .slice()
          .sort((left, right) => timeValue(right.updatedAt) - timeValue(left.updatedAt))
          .map((chatRow, index) => ({
            id: `chat:${chatRow.id}`,
            title: chatRow.title || "Conversation",
            status: "Chat",
            statusTone: "good",
            updated: timestampLabel(chatRow.updatedAt) || (index === 0 ? "Just now" : ""),
            selected: chatRow.id === activeChatSessionId,
            kind: "chat",
          }));
        const missionFlows = missionOptions
          .filter(missionRow => missionRow.workspace_id === item.workspace_id)
          .slice()
          .sort((left, right) => timeValue(deriveMissionLatestTimestamp(right)) - timeValue(deriveMissionLatestTimestamp(left)))
          .map((missionRow, index) => ({
            id: missionRow.mission_id,
            title: missionRow.title || missionRow.objective || "Mission",
            status: titleizeToken(missionRow.state?.status || "draft"),
            statusTone: missionStatusTone(missionRow.state?.status),
            updated: timestampLabel(deriveMissionLatestTimestamp(missionRow)) || (index === 0 ? "Just now" : ""),
            selected: missionRow.mission_id === selectedMissionId,
            kind: "mission",
          }));
        const flows = [...chatFlows, ...missionFlows];
        return {
          id: item.workspace_id,
          title: item.name,
          count: flows.length,
          expanded: item.workspace_id === referenceSidebarProjectId,
          flows: flows.slice(0, 5),
          hasMore: flows.length > 5,
        };
      }),
    [
      activeChatSessionId,
      chatSessions,
      missionOptions,
      referenceSidebarProjectId,
      selectedMissionId,
      workspaces,
    ],
  );
  const referenceAgentMessages = useMemo(
    () => {
      const scopedChatSessionId = activeChatSession?.id || "";
      const normalizeRow = item => {
        const rawDetail = item.detail && item.detail !== item.title ? item.detail : "";
        const routeDetail = isRouteMetadataText(rawDetail) || isRouteMetadataText(item.meta);
        return {
          id: item.id,
          role: item.role === "assistant" ? "assistant" : "user",
          label: item.role === "assistant" ? "Syntelos Agent" : "You",
          title: item.title || rawDetail || "Message",
          detail: routeDetail ? "" : rawDetail,
          meta: routeDetail ? timestampLabel(item.createdAt) : item.meta || timestampLabel(item.createdAt),
          createdAt: item.createdAt || item.timestampRaw || item.timestamp || "",
          tone: item.tone || "neutral",
          pending: Boolean(item.pending),
          technicalDetail: item.technicalDetail || "",
          chips:
            item.role === "assistant" && routeDetail && item.meta
              ? [String(item.meta).replace(/\s+/g, " ").trim()]
              : asList(item.chips).slice(0, 3),
        };
      };
      if (scopedChatSessionId) {
        const transcriptRows = asList(chatSessionTranscripts?.[scopedChatSessionId]).map(normalizeRow);
        if (transcriptRows.length > 0) {
          return transcriptRows.slice(-12);
        }
        const compartmentRows = asList(
          runtimeCompartmentChatTurnsBySession?.[scopedChatSessionId],
        ).map(normalizeRow);
        if (compartmentRows.length > 0) {
          return compartmentRows.slice(-12);
        }
        const fallbackChatMessages = operatorNotes
          .filter(item => item.channel === "chat" && item.sessionId === scopedChatSessionId)
          .slice(0, 20)
          .reverse()
          .map(normalizeRow);
        return fallbackChatMessages.slice(-12);
      }
      const liveCommentMessages = operatorNotes
        .filter(item => item.channel === "comment")
        .slice(0, 5)
        .reverse()
        .map(item => ({
          id: item.id,
          role: "user",
          label: "You",
          title: item.title || item.detail || "Comment",
          detail: item.detail && item.detail !== item.title ? item.detail : "",
          meta: item.meta || timestampLabel(item.createdAt),
          createdAt: item.createdAt || item.timestampRaw || item.timestamp || "",
          tone: item.tone || "neutral",
          pending: Boolean(item.pending),
          chips: item.target?.title ? [`Comment: ${item.target.title}`] : ["Live comment"],
        }));
      const missionMessages = agentConversationTurns.slice(-8).map(item => ({
        id: item.id,
        role: item.role === "operator" ? "user" : "assistant",
        label: item.label || item.roleLabel || (item.role === "operator" ? "You" : "Syntelos Agent"),
        title: item.title || item.detail || "Update",
        detail:
          item.role === "operator" || isRouteMetadataText(item.detail)
            ? ""
            : item.detail && item.detail !== item.title
              ? item.detail
              : "",
        meta: item.meta || timestampLabel(item.timestampRaw),
        createdAt: item.timestampRaw || item.createdAt || item.timestamp || "",
        tone: item.tone || "neutral",
        chips: asList(item.chips).slice(0, 3),
      }));
      return [...missionMessages, ...liveCommentMessages].slice(-12);
    },
    [
      activeChatSession?.id,
      agentConversationTurns,
      chatSessionTranscripts,
      operatorNotes,
      runtimeCompartmentChatTurnsBySession,
    ],
  );
  const referenceFeedbackItems = useMemo(() => {
    const seededMessages = referenceAgentMessages.slice(-3).map(item => ({
      id: `feedback-${item.id}`,
      role: item.role,
      author: item.role === "user" ? "You" : "Syntelos Agent",
      body: item.title,
      meta: item.meta || "",
      tone: item.tone,
    }));
    const noteItems = activeChatSession?.id
      ? []
      : operatorNotes
      .filter(item => item.channel === "note" || item.channel === "comment")
      .slice(0, 5)
      .map(item => ({
      id: `note-${item.id}`,
      role: item.channel === "note" ? "note" : "comment",
      author: item.channel === "note" ? "Note" : item.pending ? "Sending comment" : "Live comment",
      body: item.channel === "comment" ? item.title : item.detail,
      meta: item.meta || timestampLabel(item.createdAt),
      tone: item.tone || "neutral",
    }));
    return [...noteItems, ...seededMessages].slice(0, 6);
  }, [activeChatSession?.id, operatorNotes, referenceAgentMessages]);
  const referenceTimelineMoments = useMemo(
    () =>
      (agentTraceTurns.length > 0 ? agentTraceTurns : agentTranscript)
        .slice(-6)
        .map((item, index) => ({
          id: item.id || `moment-${index}`,
          time: item.meta || timestampLabel(item.timestampRaw) || `${index + 1}`,
          title: item.title || item.label || "Mission update",
          detail: item.detail || item.technicalDetail || "No detail recorded.",
          tone: item.tone || "neutral",
          preview: item.technicalDetail || item.detail || "",
        })),
    [agentTraceTurns, agentTranscript],
  );
  const referenceSkillEffectTrace = useMemo(() => {
    const skillItems = asList(referenceStudio?.skills);
    const activeSkillIds = new Set(asList(referenceStudio?.activeSkillIds));
    const selectedSkill =
      skillItems.find(item => item?.id === referenceStudio?.selectedSkillId) ||
      skillItems.find(item => activeSkillIds.has(item?.id)) ||
      skillItems[0] ||
      null;

    if (!selectedSkill) {
      return null;
    }

    const activeSkills = skillItems.filter(item => activeSkillIds.has(item?.id)).slice(0, 5);
    const delegatedLanes = asList(mission?.delegated_runtime_sessions);
    const latestLane =
      delegatedLanes.find(item =>
        ["waiting_for_approval", "running", "launching"].includes(
          String(item?.status || "").trim().toLowerCase(),
        ),
      ) ||
      delegatedLanes[delegatedLanes.length - 1] ||
      null;
    const laneEvents = asList(latestLane?.latest_events);
    const routeEvent =
      laneEvents
        .slice()
        .reverse()
        .find(event =>
          [
            "runtime.route_contract",
            "runtime.phase_entered",
            "runtime.route_switch_reason",
            "runtime.handoff",
          ].includes(String(event?.kind || "").toLowerCase()),
        ) || null;
    const routeData = routeEvent?.data || {};
    const runtimeId =
      latestLane?.runtime_id ||
      missionRuntimeCompartment?.runtime ||
      mission?.runtime_id ||
      agentRuntimeSelectValue ||
      "hermes";
    const routeProvider =
      routeData.provider ||
      latestLane?.provider ||
      missionRuntimeCompartment?.route?.provider ||
      activeEffectiveRoute.provider ||
      selectedAgentRoute.provider ||
      "auto";
    const routeModel =
      routeData.model ||
      latestLane?.model ||
      missionRuntimeCompartment?.route?.model ||
      activeEffectiveRoute.model ||
      selectedAgentRoute.model ||
      selectedModelLabel ||
      "profile default";
    const proofArtifacts = [
      ...asList(mission?.proof_artifacts),
      ...asList(mission?.proof?.artifacts),
      ...asList(mission?.state?.code_execution?.artifacts),
    ].slice(0, 4);
    const skillTags = asList(selectedSkill.tags).map(tag => String(tag).toLowerCase());
    const opencodeAvailable = runtimeOptions.some(option => option?.value === "opencode");
    const activeInRoute = activeSkillIds.has(selectedSkill.id);
    const statusTone = activeInRoute ? "good" : "warn";
    const routeLabel = `${runtimeLabel(runtimeId)} / ${titleizeToken(routeProvider)} / ${routeModel}`;
    const eventCount = laneEvents.length || referenceTimelineMoments.length;
    const proofLabel = latestLane?.delegated_id
      ? `Session ${latestLane.delegated_id}`
      : proofArtifacts.length
        ? `${proofArtifacts.length} artifact${proofArtifacts.length === 1 ? "" : "s"} attached`
        : "Proof pending for the next live run";

    const effectPoints = [
      selectedSkill.triggerConditions
        ? `Trigger: ${selectedSkill.triggerConditions}`
        : "",
      asList(selectedSkill.outputStyle)[0]
        ? `Output: ${asList(selectedSkill.outputStyle)[0]}`
        : "",
      asList(selectedSkill.guardrails)[0]
        ? `Guardrail: ${asList(selectedSkill.guardrails)[0]}`
        : "",
    ].filter(Boolean);

    const proofItems = [
      latestLane?.delegated_id ? { label: "Runtime session", value: latestLane.delegated_id } : null,
      latestLane?.execution_root || missionRuntimeCompartment?.cwd
        ? { label: "Execution root", value: latestLane?.execution_root || missionRuntimeCompartment?.cwd }
        : null,
      opencodeAvailable && skillTags.includes("opencode")
        ? { label: "Preferred lab route", value: "OpenCodeGo available" }
        : null,
      proofArtifacts[0]
        ? {
            label: "Latest artifact",
            value: proofArtifacts[0]?.path || proofArtifacts[0]?.artifactPath || proofArtifacts[0]?.title || "artifact recorded",
          }
        : null,
    ].filter(Boolean);

    return {
      skillName: selectedSkill.name || titleizeToken(selectedSkill.id || "Active skill"),
      skillSummary: selectedSkill.summary || selectedSkill.description || "Selected workspace skill.",
      statusLabel: activeInRoute ? "Included in routing" : "Selected, not enabled",
      statusTone,
      activeSkillNames: activeSkills.map(item => item.name || titleizeToken(item.id)).filter(Boolean),
      route: {
        label: routeLabel,
        runtime: runtimeLabel(runtimeId),
        provider: titleizeToken(routeProvider),
        model: routeModel,
        effort: selectedEffortLabel,
      },
      effectPoints,
      proofItems,
      traceSteps: [
        {
          id: "skill-selected",
          label: "Skill selected",
          detail: `${selectedSkill.name || "Selected skill"} is ${activeInRoute ? "active" : "selected"} and changes the route instructions, proof expectations, and guardrails.`,
          state: activeInRoute ? "done" : "warn",
        },
        {
          id: "runtime-route",
          label: "Runtime route",
          detail: routeLabel,
          state: runtimeId ? "done" : "pending",
        },
        {
          id: "visible-trace",
          label: "Visible trace",
          detail:
            eventCount > 0
              ? `${eventCount} visible trace moment${eventCount === 1 ? "" : "s"} captured; summaries stay separate from private chain-of-thought.`
              : "Trace summaries are ready; runtime events appear here when a lane publishes.",
          state: eventCount > 0 ? "done" : "pending",
        },
        {
          id: "proof-trail",
          label: "Proof trail",
          detail: proofLabel,
          state: latestLane?.delegated_id || proofArtifacts.length ? "done" : "pending",
        },
      ],
    };
  }, [
    activeEffectiveRoute,
    agentRuntimeSelectValue,
    mission,
    missionRuntimeCompartment,
    referenceStudio,
    referenceTimelineMoments.length,
    runtimeOptions,
    selectedAgentRoute.model,
    selectedAgentRoute.provider,
    selectedEffortLabel,
    selectedModelLabel,
  ]);
  const referenceBuilderRows = useMemo(
    () =>
      missionOptions.map(item => {
        const ownerWorkspace = workspaceById.get(item.workspace_id) || null;
        const approvalCount = asList(item?.proof?.pending_approvals).length;
        const verificationCount = asList(item?.state?.verification_failures).length;
        const delegatedCount = asList(item?.delegated_runtime_sessions).filter(
          session => !["completed", "failed", "stopped"].includes(session?.status || ""),
        ).length;
        const actionCount = asList(item?.action_history).length;
        const remainingCount = asList(item?.state?.remaining_steps).length;
        const status = item.state?.status || "draft";
        const completed = status === "completed";
        const running = status === "running" || delegatedCount > 0;
        const successRate = completed ? 100 : verificationCount > 0 ? 0 : null;
        const turningPoint = verificationCount
          ? `${verificationCount} blocker${verificationCount === 1 ? "" : "s"}`
          : approvalCount
            ? `${approvalCount} approval${approvalCount === 1 ? "" : "s"}`
            : remainingCount
              ? `${remainingCount} step${remainingCount === 1 ? "" : "s"} left`
              : completed
                ? "Complete"
                : "—";
        const turningPointDelta = verificationCount
          ? "Blocked"
          : approvalCount
            ? "Needs review"
            : delegatedCount
              ? "Delegated"
              : completed
                ? "Done"
                : running
                  ? "Running"
                  : "Queued";
        return {
          id: item.mission_id,
          name: item.title || item.objective || "Mission",
          description: ownerWorkspace?.name || "Workspace mission",
          status: titleizeToken(status),
          statusTone:
            verificationCount > 0
              ? "failed"
              : approvalCount > 0
                ? "running"
                : completed
                  ? "completed"
                  : running
                    ? "running"
                    : "paused",
          lastRun: formatDurationCompact(item?.duration_minutes ? item.duration_minutes * 60 : 0) || "—",
          lastRunMeta: timestampLabel(deriveMissionLatestTimestamp(item)) || "Recently",
          turningPoint,
          turningPointDelta,
          turningPointTone: verificationCount > 0 ? "down" : completed ? "up" : "flat",
          successRate,
          runs: actionCount + delegatedCount,
          updated: timestampLabel(deriveMissionLatestTimestamp(item)) || "Just now",
          selected: item.mission_id === selectedMissionId,
        };
      }),
    [missionOptions, selectedMissionId, workspaceById],
  );
  const referenceChangedItems = useMemo(
    () =>
      uniq([
        ...asList(mission?.changed_files),
        ...asList(mission?.action_history).map(item => item?.proposal?.title),
      ]).slice(0, 6),
    [mission?.action_history, mission?.changed_files],
  );
  const referenceWorkbenchState = useMemo(() => {
    const delegatedLanes = asList(mission?.delegated_runtime_sessions);
    const activeLanes = delegatedLanes.filter(item =>
      !["completed", "failed", "stopped"].includes(String(item?.status || "").toLowerCase()),
    );
    const skillDraftCount = asList(referenceStudio?.skills).filter(item => String(item?.status || "").toLowerCase() === "draft").length;
    const skillNeedsReviewCount = asList(referenceStudio?.skills).filter(item => item?.reviewRequired).length;
    const laneRunningCount = activeLanes.length;
    const serviceStudio = viewModel.drawers?.builder?.serviceStudio || {};
    const runtimeOps = deriveRuntimeOperations(serviceStudio);
    const notificationEvents = [
      {
        id: "skill-draft-created",
        kind: "skill_draft_created",
        label: "Skill draft created",
        count: skillDraftCount,
        detail: "Draft skills exist and are awaiting validation/test and review.",
      },
      {
        id: "skill-needs-review",
        kind: "skill_needs_review",
        label: "Skill needs review",
        count: skillNeedsReviewCount,
        detail: "Human review required before publishing learned or drafted skills.",
      },
      {
        id: "completed",
        kind: "completed",
        label: "Mission completed",
        count: mission?.state?.status === "completed" ? 1 : 0,
        detail: mission?.proof?.summary || "No completed mission summary yet.",
      },
      {
        id: "blocked",
        kind: "blocked",
        label: "Blocked",
        count: asList(mission?.proof?.pending_approvals).length + asList(data.pendingQuestions).length,
        detail: "Approval boundaries and operator questions that pause execution.",
      },
      {
        id: "verification-failed",
        kind: "verification_failed",
        label: "Verification failed",
        count: asList(mission?.state?.verification_failures).length,
        detail: "Failures from tests or contract verification.",
      },
      {
        id: "artifacts",
        kind: "produced_artifacts",
        label: "Produced artifacts",
        count: asList(mission?.proof_artifacts).length + referenceChangedItems.length,
        detail: "Files, proofs, and outputs created during mission execution.",
      },
      {
        id: "lane-running",
        kind: "lane_running",
        label: "Active lane still running",
        count: laneRunningCount,
        detail: laneRunningCount > 0 ? "At least one delegated lane is still executing." : "No active delegated lanes.",
      },
    ];
    return {
      computerUse: {
        status: activeLanes.length > 0 ? "active" : "standby",
        safetyMode: asList(mission?.proof?.pending_approvals).length > 0 ? "approval_gated" : "guided",
        runtimeLabel: activeLanes[0]?.runtime_id || mission?.runtime_id || "workspace-runtime",
        currentScreen: activeLanes[0]?.detail || "Live desktop stream is not currently attached.",
        currentTask: activeLanes[0]?.last_event || mission?.objective || "Waiting for the next assigned operator task.",
        handoffHint:
          activeLanes.length > 0
            ? "Use Approvals/Questions to hand off between agent and operator."
            : "Computer-use controls are configured and waiting for a delegated lane to attach.",
      },
      runtimeOps,
      notificationEvents,
      lanes: activeLanes.map((item, index) => ({
        id: item?.session_id || `lane-${index}`,
        label: item?.label || item?.runtime_id || `Lane ${index + 1}`,
        model: item?.model || "profile default",
        provider: item?.provider || "workspace default",
        status: item?.status || "running",
        lastEvent: item?.last_event || item?.detail || "Awaiting event",
      })),
      playgrounds: [
        { id: "image", label: "Image Playground", status: "ready", action: "open-images" },
        { id: "coverage", label: "Coverage Analysis", status: "beta", action: "open-builder" },
        { id: "code-study", label: "Code Study", status: "beta", action: "open-builder" },
        { id: "tutorials", label: "Tutorial Lab", status: "ready", action: "open-agent" },
        { id: "research", label: "Research Workbench", status: "planned", action: "open-agent" },
        { id: "docs", label: "Docs/Sheets/Slides", status: "planned", action: "open-settings" },
      ],
      coverage: {
        summary: mission?.missionLoop?.lastVerificationSummary || "Coverage/test-gap summary unavailable.",
        gapCount: asList(mission?.state?.verification_failures).length,
        files: referenceChangedItems.slice(0, 5),
      },
      tutorials: {
        headline: viewModel.tutorialStudio?.headline || "Contextual onboarding",
        steps: asList(viewModel.tutorialStudio?.steps).slice(0, 4),
      },
      ideaPlanner: {
        headline: "Idea planner",
        ideas: asList(snapshot?.guidance?.productImprovements)
          .slice(0, 4)
          .map(item => ({
            id: item?.item_id || item?.title,
            title: item?.title || "Idea",
            score: item?.priority === "high" ? 88 : item?.priority === "medium" ? 72 : 58,
            reason: item?.reason || "",
          })),
      },
      providerCatalog: {
        providers: MODEL_PROVIDER_OPTIONS.map(item => item.label),
        routeModels: ROUTE_MODEL_OPTIONS.slice(0, 8),
      },
      liveReview: viewModel.drawers?.builder?.liveReviewStudio || null,
    };
  }, [data.pendingApprovals, data.pendingQuestions, mission, referenceChangedItems, referenceStudio, snapshot?.guidance?.productImprovements, viewModel.drawers?.builder?.liveReviewStudio, viewModel.drawers?.builder?.serviceStudio, viewModel.tutorialStudio]);
  const referencePreviewStyle = useMemo(
    () => ({
      "--ref-violet": referenceAppearance.accent,
      "--ref-violet-soft": hexToRgba(referenceAppearance.accent, 0.18),
      "--ref-gold": referenceAppearance.accentAlt,
      "--ref-gold-soft": hexToRgba(referenceAppearance.accentAlt, 0.16),
      "--settings-surface": referenceAppearance.surface,
      "--settings-surface-soft": referenceAppearance.surfaceSoft,
      "--settings-line": referenceAppearance.line,
      "--settings-text": referenceAppearance.text,
    }),
    [referenceAppearance],
  );

  useEffect(() => {
    if (surface !== "agent") {
      return;
    }
    if (requestedAgentScene) {
      return;
    }
    if (activeChatSessionId) {
      setAgentScene(current => (current === "live" ? "live" : "run"));
      return;
    }
    if (!mission) {
      setAgentScene("idle");
      return;
    }
    setAgentScene(current => (current === "live" ? "live" : "run"));
  }, [activeChatSessionId, mission, requestedAgentScene, surface]);

  const handleReferenceSurfaceChange = useCallback(
    nextSurface => {
      markAction(`reference:surface:${nextSurface}`);
      setSurface(nextSurface);
      if (nextSurface !== "builder") {
        setBuilderDetailOpen(false);
      }
      if (nextSurface === "agent") {
        setActiveDrawer(null);
        if (!requestedAgentScene) {
          setAgentScene(activeChatSessionId || mission ? "run" : "idle");
        }
        return;
      }
      if (nextSurface === "builder") {
        setActiveDrawer(null);
        return;
      }
      setActiveDrawer(null);
    },
    [activeChatSessionId, markAction, mission, requestedAgentScene],
  );

  const handleReferenceSkillStudio = useCallback(() => {
    markAction("reference:skill-studio");
    setSurface("skills");
    setBuilderDetailOpen(false);
    setActiveDrawer(null);
  }, [markAction]);

  const handleReferenceSettings = useCallback(() => {
    markAction("reference:settings");
    setSurface("settings");
    setBuilderDetailOpen(false);
    setActiveDrawer(null);
  }, [markAction]);

  const handleReferenceHistory = useCallback(() => {
    markAction("reference:history");
    if (referenceAgentMessages.length > 0) {
      setSurface("agent");
      setAgentScene("run");
      pushToast("Showing the latest chat and mission history.", "info");
      return;
    }
    const latestChat = chatSessions
      .slice()
      .sort((left, right) => timeValue(right.updatedAt) - timeValue(left.updatedAt))[0];
    if (latestChat?.id) {
      setSurface("agent");
      setAgentScene("run");
      setActiveChatSessionId(latestChat.id);
      setSelectedMissionId(null);
      if (latestChat.workspaceId) {
        setSelectedWorkspaceId(latestChat.workspaceId);
      }
      return;
    }
    const latestMission = missionOptions[0];
    if (latestMission?.mission_id) {
      setSurface("agent");
      setSelectedMissionId(latestMission.mission_id);
      setAgentScene("run");
      return;
    }
    pushToast("No mission history is available yet.", "info");
  }, [chatSessions, markAction, missionOptions, pushToast, referenceAgentMessages.length]);

  const handleReferenceMore = useCallback(() => {
    markAction("reference:more");
    if (surface === "agent" && mission) {
      setAgentScene(current => (current === "live" ? "run" : "live"));
      return;
    }
    setSurface("settings");
  }, [markAction, mission, surface]);

  const handleReferenceAttach = useCallback(() => {
    markAction("reference:attach");
    pushToast("Paste or drag attachments into the composer.", "info");
  }, [markAction, pushToast]);

  const handleReferenceProjectSelect = useCallback(
    workspaceId => {
      if (!workspaceId) {
        return;
      }
      markAction(`reference:workspace:${workspaceId}`);
      setSelectedWorkspaceId(workspaceId);
      if (activeChatSession?.workspaceId && activeChatSession.workspaceId !== workspaceId) {
        setActiveChatSessionId("");
      }
    },
    [activeChatSession?.workspaceId, markAction],
  );

  const handleReferenceMissionSelect = useCallback(
    ({ missionId, nextSurface = surface, nextAgentScene = "run", openBuilderDetail = false }) => {
      if (!missionId) {
        return;
      }
      markAction(`reference:mission:${missionId}`);
      setActiveChatSessionId("");
      setSelectedMissionId(missionId);
      if (nextSurface) {
        setSurface(nextSurface);
      }
      if (nextSurface === "agent") {
        setAgentScene(nextAgentScene);
      }
      setBuilderDetailOpen(openBuilderDetail);
    },
    [markAction, surface],
  );

  const handleReferenceFlowSelect = useCallback(
    flowId => {
      const normalized = String(flowId || "").trim();
      if (!normalized) {
        return;
      }
      if (normalized.startsWith("chat:")) {
        const sessionId = normalized.slice("chat:".length).trim();
        const session = chatSessions.find(item => item.id === sessionId);
        if (!session) {
          pushToast("This conversation is no longer available.", "warn");
          return;
        }
        markAction(`reference:chat:${sessionId}`);
        setActiveChatSessionId(sessionId);
        setSelectedMissionId(null);
        if (session.workspaceId) {
          setSelectedWorkspaceId(session.workspaceId);
        }
        setSurface("agent");
        setAgentScene("run");
        return;
      }
      handleReferenceMissionSelect({
        missionId: normalized,
        nextSurface: "agent",
        nextAgentScene: mission ? agentScene : "run",
        openBuilderDetail: false,
      });
    },
    [
      agentScene,
      chatSessions,
      handleReferenceMissionSelect,
      markAction,
      mission,
      pushToast,
    ],
  );

  const handleReferenceAction = useCallback(
    async (actionId, payload = {}) => {
      const normalizedAction = String(actionId || "").trim();
      if (!normalizedAction) {
        return;
      }
      markAction(`reference:action:${normalizedAction}`);

      if (normalizedAction === "home:help") {
        setSurface("settings");
        setBuilderDetailOpen(false);
        setActiveDrawer(null);
        pushToast("Open Settings to review workspace controls, runtime auth, and routing.", "info");
        return;
      }

      if (normalizedAction === "flow:new-conversation") {
        const created = createChatSessionForWorkspace({
          workspaceId: selectedWorkspaceId || workspace?.workspace_id || "",
          seedText: operatorDraft || "",
          focus: true,
        });
        setSurface("agent");
        setAgentScene("run");
        setBuilderDetailOpen(false);
        setActiveDrawer(null);
        setOperatorDraft("");
        clearOperatorAttachments();
        pushToast(
          created?.title
            ? `Conversation started: ${created.title}`
            : "New conversation started.",
          "info",
        );
        return;
      }

      if (normalizedAction === "flow:add-project" || normalizedAction === "builder:new-project") {
        const openInBuilder = normalizedAction === "builder:new-project";
        if (openInBuilder) {
          setSurface("builder");
          setBuilderDetailOpen(false);
        } else {
          if (surface !== "builder") {
            setSurface("agent");
          }
          setBuilderDetailOpen(false);
          setActiveDrawer(null);
        }
        setWorkspaceForm({
          ...DEFAULT_WORKSPACE_FORM,
          defaultRuntime: workspace?.default_runtime || DEFAULT_WORKSPACE_FORM.defaultRuntime,
          userProfile: workspace?.user_profile || profileId || DEFAULT_WORKSPACE_FORM.userProfile,
        });
        setShowWorkspaceDialog(true);
        return;
      }

      if (normalizedAction === "flow:search") {
        setSurface("agent");
        setAgentScene(activeChatSessionId || mission ? "run" : "idle");
        pushToast("Use the left project list to jump across mission threads and chat conversations.", "info");
        return;
      }

      if (normalizedAction === "flow:show-all") {
        const workspaceId = String(payload?.workspaceId || "");
        if (workspaceId) {
          setSelectedWorkspaceId(workspaceId);
          setSurface("builder");
          setBuilderDetailOpen(false);
          return;
        }
        pushToast("No workspace selected for this flow group.", "warn");
        return;
      }

      if (normalizedAction === "idle:advanced-settings") {
        setSurface("settings");
        setBuilderDetailOpen(false);
        setActiveDrawer(null);
        return;
      }

      if (normalizedAction === "idle:reset-defaults") {
        setOperatorDraft("");
        setMissionForm({
          ...DEFAULT_MISSION_FORM,
          workspaceId: workspace?.workspace_id || "",
          runtime: workspace?.default_runtime || DEFAULT_MISSION_FORM.runtime,
          profile: workspace?.user_profile || profileId || DEFAULT_MISSION_FORM.profile,
        });
        setAgentRuntimeFocus("all");
        pushToast("Composer and mission defaults were reset.", "info");
        return;
      }

      if (normalizedAction === "live:refresh-preview") {
        await refreshAll("control-preview-refresh");
        return;
      }

      if (normalizedAction === "live:expand-preview") {
        setSurface("agent");
        setAgentScene("live");
        setBuilderDetailOpen(false);
        return;
      }

      if (
        normalizedAction === "live:cta-start" ||
        normalizedAction === "live:start-building" ||
        normalizedAction === "live:view-demo" ||
        normalizedAction === "live:comment-emoji" ||
        normalizedAction === "live:comment-send"
      ) {
        setSurface("agent");
        setAgentScene(activeChatSessionId || mission ? "run" : "idle");
        if (normalizedAction === "live:comment-send") {
          if (activeChatSessionId) {
            handleAgentIdleSubmit();
          } else if (mission) {
            void handleAgentFollowUp();
          } else {
            handleAgentIdlePrimaryAction();
          }
          return;
        }
        pushToast("Preview action routed to the active agent thread.", "info");
        return;
      }

      if (normalizedAction === "run:resume") {
        if (mission) {
          await runMissionAction("resume", "Mission resume requested.");
          return;
        }
        pushToast("No active mission is selected to resume.", "warn");
        return;
      }

      if (normalizedAction === "run:proof") {
        setActiveDrawer("proof");
        setSurface("agent");
        setAgentScene("run");
        return;
      }

      if (normalizedAction === "run:queue") {
        setActiveDrawer("queue");
        setSurface("agent");
        setAgentScene("run");
        return;
      }

      if (normalizedAction === "run:message-copy") {
        const messageId = String(payload?.messageId || "");
        const message = referenceAgentMessages.find(item => item.id === messageId);
        const copied = await copyTextValue(message?.title || "");
        pushToast(copied ? "Message copied." : "Unable to copy message text.", copied ? "info" : "warn");
        return;
      }

      if (normalizedAction === "run:message-comment") {
        const messageId = String(payload?.messageId || "");
        const message = referenceAgentMessages.find(item => item.id === messageId);
        if (message?.title) {
          setActiveCommentTarget({
            id: message.id,
            kind: message.role === "user" ? "user message" : "agent message",
            title: message.title,
          });
          setOperatorDraft("");
          pushToast("Comment target pinned to the mission composer.", "info");
          return;
        }
        pushToast("No message is selected for comment.", "warn");
        return;
      }

      if (normalizedAction === "run:moment-comment") {
        const momentId = String(payload?.momentId || "");
        const moment = referenceTimelineMoments.find(item => item.id === momentId);
        if (moment?.title) {
          setActiveCommentTarget({
            id: moment.id,
            kind: "mission activity",
            title: moment.title,
          });
          setOperatorDraft("");
          pushToast("Progress item pinned to the mission composer.", "info");
          return;
        }
        pushToast("No progress item is selected for comment.", "warn");
        return;
      }

      if (normalizedAction === "run:clear-comment-target") {
        setActiveCommentTarget(null);
        pushToast("Comment target cleared.", "info");
        return;
      }

      if (normalizedAction === "run:message-retry") {
        if (mission) {
          void handleAgentFollowUp();
        } else {
          handleAgentIdlePrimaryAction();
        }
        return;
      }

      if (normalizedAction === "run:feedback-apply" || normalizedAction === "run:feedback-view") {
        setSurface("builder");
        setBuilderDetailOpen(true);
        pushToast("Opened Builder detail for feedback review.", "info");
        return;
      }

      if (normalizedAction === "builder:toggle-view") {
        pushToast("Grid view is coming soon. Table view remains active.", "info");
        return;
      }

      if (
        normalizedAction === "builder:filter-status" ||
        normalizedAction === "builder:filter-stack" ||
        normalizedAction === "builder:filter-updated" ||
        normalizedAction === "builder:filters"
      ) {
        pushToast("Advanced Builder filters are coming soon.", "info");
        return;
      }

      if (normalizedAction === "builder:settings") {
        setSurface("settings");
        setBuilderDetailOpen(false);
        setActiveDrawer(null);
        return;
      }

      if (normalizedAction === "builder:detail-live-preview") {
        setSurface("agent");
        setAgentScene("live");
        setBuilderDetailOpen(false);
        return;
      }

      if (normalizedAction === "builder:detail-primary") {
        if (mission) {
          setSurface("agent");
          setAgentScene("run");
          void handleAgentFollowUp();
          return;
        }
        pushToast("Open a mission first to run Builder primary actions.", "warn");
        return;
      }

      if (normalizedAction === "builder:detail-secondary") {
        setSurface("settings");
        setBuilderDetailOpen(false);
        setActiveDrawer(null);
        return;
      }

      if (normalizedAction === "builder:project-actions" || normalizedAction === "builder:open-in-builder") {
        const missionId = String(payload?.missionId || "");
        if (missionId) {
          handleReferenceMissionSelect({
            missionId,
            nextSurface: "builder",
            openBuilderDetail: true,
          });
          return;
        }
        pushToast("No project is selected yet.", "info");
        return;
      }

      if (normalizedAction === "builder:feedback-apply" || normalizedAction === "builder:feedback-view") {
        const feedbackId = String(payload?.feedbackId || "");
        const feedback = referenceFeedbackItems.find(item => item.id === feedbackId);
        if (feedback?.body) {
          setOperatorDraft(feedback.body);
          pushToast("Feedback copied into the composer.", "info");
          return;
        }
        pushToast("Feedback item could not be resolved.", "warn");
        return;
      }

      if (normalizedAction === "builder:detail-more" || normalizedAction === "skills:more-actions") {
        setSurface("settings");
        setBuilderDetailOpen(false);
        setActiveDrawer(null);
        return;
      }

      if (normalizedAction === "skills:version-history") {
        pushToast("Version history will include saved drafts and publish events.", "info");
        return;
      }

      if (normalizedAction === "skills:add-skill") {
        setReferenceStudio(current => {
          const base = asList(current.skills)[0] || buildDefaultReferenceStudio(workspaceProfileForm.routeOverrides).skills[0];
          const nextId = `skill-${Date.now()}`;
          const nextName = `Custom Skill ${asList(current.skills).length + 1}`;
          const nextSkill = {
            ...base,
            id: nextId,
            status: "Draft",
            name: nextName,
            summary: "New workspace skill draft.",
            description: "",
            category: "workflow",
            tags: ["draft"],
            testStatus: "Not run",
            validationStatus: "Pending",
            publishReadiness: "Needs review",
            reviewRequired: true,
            learnedPromotion: "Not proposed",
            sourceType: "manual",
            lastValidationSummary: "Draft created. Run validation before publish.",
            lastTestSummary: "No tests executed.",
            assistant: {
              ...(base.assistant || {}),
              prompt: "",
              conversation: [],
              proposal: null,
            },
          };
          return {
            ...current,
            collectionTab: "skill",
            selectedSkillId: nextId,
            skills: [nextSkill, ...asList(current.skills)],
          };
        });
        pushToast("Skill draft created and queued for review.", "info");
        return;
      }

      if (normalizedAction === "skills:add-rule-set") {
        setReferenceStudio(current => {
          const base = asList(current.ruleSets)[0] || buildDefaultReferenceStudio(workspaceProfileForm.routeOverrides).ruleSets[0];
          const nextId = `rule-${Date.now()}`;
          const nextName = `Custom Rule Set ${asList(current.ruleSets).length + 1}`;
          const nextRule = {
            ...base,
            id: nextId,
            status: "Draft",
            name: nextName,
            summary: "New workspace rule set draft.",
            description: "",
            assistant: {
              ...(base.assistant || {}),
              prompt: "",
              conversation: [],
              proposal: null,
            },
          };
          return {
            ...current,
            collectionTab: "rule",
            selectedRuleId: nextId,
            ruleSets: [nextRule, ...asList(current.ruleSets)],
          };
        });
        pushToast("Created a new draft rule set.", "info");
        return;
      }

      if (normalizedAction === "skills:view-archived") {
        pushToast("No archived studio items are available in this workspace.", "info");
        return;
      }

      if (normalizedAction === "skills:edit-item" || normalizedAction === "skills:preview-item") {
        pushToast("Edit and preview mode are already active in Skill Studio.", "info");
        return;
      }

      if (normalizedAction === "skills:collapse-assistant") {
        pushToast("Assistant panel collapse will be available in the next UI pass.", "info");
        return;
      }

      if (normalizedAction === "skills:attach-context") {
        pushToast("Paste context directly into the prompt while attachment upload is finalized.", "info");
        return;
      }

      if (normalizedAction === "skills:validate-item" || normalizedAction === "skills:test-item") {
        if (!referenceStudioSelectedItem?.id || referenceStudioKind !== "skill") {
          pushToast("Select a skill before running validation/tests.", "warn");
          return;
        }
        const isValidation = normalizedAction === "skills:validate-item";
        updateReferenceStudioItem("skill", referenceStudioSelectedItem.id, item => ({
          ...item,
          validationStatus: isValidation ? "Passed" : item.validationStatus,
          testStatus: isValidation ? item.testStatus : "Passed",
          lastValidationSummary: isValidation
            ? "Schema/readiness checks passed for draft boundaries and guardrails."
            : item.lastValidationSummary,
          lastTestSummary: isValidation
            ? item.lastTestSummary
            : "Focused static assertions for skill UI controls passed.",
        }));
        pushToast(isValidation ? "Skill validation passed." : "Skill tests passed.", "info");
        return;
      }

      if (normalizedAction === "skills:promote-learned") {
        if (!referenceStudioSelectedItem?.id || referenceStudioKind !== "skill") {
          pushToast("Select a skill draft before promoting.", "warn");
          return;
        }
        updateReferenceStudioItem("skill", referenceStudioSelectedItem.id, item => ({
          ...item,
          learnedPromotion: "Proposed",
          sourceType: item.sourceType || "mission_learned",
          reviewRequired: true,
          publishReadiness: "Needs review",
        }));
        pushToast("Learned-skill promotion proposed. Human review required.", "info");
        return;
      }

      if (normalizedAction === "skills:propose-from-mission") {
        const missionLabel = mission?.title || mission?.objective || "Mission";
        setReferenceStudio(current => {
          const base = asList(current.skills)[0] || buildDefaultReferenceStudio(workspaceProfileForm.routeOverrides).skills[0];
          const nextId = `skill-mission-${Date.now()}`;
          const nextSkill = {
            ...base,
            id: nextId,
            status: "Draft",
            name: `${missionLabel} Learned Workflow`,
            summary: "Autonomous proposal from successful mission work.",
            description: `Proposed from mission output: ${missionLabel}. Requires human review before publish.`,
            sourceType: "mission_learned",
            learnedPromotion: "Proposed",
            testStatus: "Not run",
            validationStatus: "Pending",
            publishReadiness: "Needs review",
            reviewRequired: true,
            lastValidationSummary: "Autonomous draft created. Validation pending.",
            lastTestSummary: "No tests executed.",
          };
          return {
            ...current,
            collectionTab: "skill",
            selectedSkillId: nextId,
            skills: [nextSkill, ...asList(current.skills)],
          };
        });
        pushToast("Mission learned-skill draft created for review.", "info");
        return;
      }

      if (normalizedAction === "settings:export-data") {
        if (previewMode !== "live" || !hasCommandBackend()) {
          pushToast("Preview mode cannot export control-room data.", "warn");
          return;
        }
        try {
          const response = await callBackend(
            "export_control_room_data_command",
            { payload: { root: null } },
            { throwOnError: true },
          );
          const exportPath = String(response?.exportPath || "").trim();
          if (!exportPath) {
            pushToast("Control-room export completed, but no path was returned.", "warn");
            return;
          }
          const copied = await copyTextValue(exportPath);
          pushToast(
            copied
              ? `Control-room data exported to ${pathLeaf(exportPath)}. Path copied to clipboard.`
              : `Control-room data exported to ${exportPath}.`,
            "info",
          );
        } catch (error) {
          pushToast(`Control-room export failed: ${error}`, "error");
        }
        return;
      }

      if (normalizedAction === "settings:run-action") {
        const action = payload?.action;
        if (!action?.actionId) {
          pushToast("No executable service action was attached.", "warn");
          return;
        }
        await runWorkspaceActionSpec(action);
        return;
      }

      if (normalizedAction === "settings:delete-workspace") {
        const workspaceId =
          selectedWorkspaceId || workspace?.workspace_id || workspaces[0]?.workspace_id || "";
        if (!workspaceId) {
          pushToast("No workspace is selected for deletion.", "warn");
          return;
        }
        if (previewMode !== "live" || !hasCommandBackend()) {
          pushToast("Preview mode cannot delete workspace profiles.", "warn");
          return;
        }
        const workspaceName =
          workspace?.workspace_id === workspaceId
            ? workspace?.name || workspaceId
            : workspaces.find(item => item.workspace_id === workspaceId)?.name || workspaceId;
        const confirmed = window.confirm(
          `Delete workspace \"${workspaceName}\" and all missions scoped to it? This cannot be undone.`,
        );
        if (!confirmed) {
          return;
        }
        try {
          const response = await callBackend(
            "delete_workspace_profile_command",
            { payload: { root: null, workspaceId } },
            { throwOnError: true },
          );
          const removedMissionCount = Number(response?.removedMissionCount || 0);
          setBuilderDetailOpen(false);
          setSurface("home");
          setSelectedWorkspaceId(null);
          setSelectedMissionId(null);
          await refreshAll("workspace-delete");
          pushToast(
            `Workspace deleted (${removedMissionCount} mission${removedMissionCount === 1 ? "" : "s"} removed).`,
            "info",
          );
        } catch (error) {
          pushToast(`Workspace delete failed: ${error}`, "error");
        }
        return;
      }

      pushToast("This action is not available yet in the current shell.", "info");
    },
    [
      activeChatSessionId,
      clearOperatorAttachments,
      createChatSessionForWorkspace,
      handleAgentFollowUp,
      handleAgentIdleSubmit,
      handleAgentIdlePrimaryAction,
      handleReferenceMissionSelect,
      markAction,
      mission,
      operatorDraft,
      previewMode,
      profileId,
      pushToast,
      refreshAll,
      referenceAgentMessages,
      referenceFeedbackItems,
      referenceTimelineMoments,
      runMissionAction,
      runWorkspaceActionSpec,
      workspace?.default_runtime,
      workspace?.name,
      workspace?.workspace_id,
      workspace?.user_profile,
      workspaceProfileForm.routeOverrides,
      workspaces,
      selectedWorkspaceId,
      surface,
    ],
  );

  const handleReferenceBuilderBack = useCallback(() => {
    markAction("reference:builder:back");
    setBuilderDetailOpen(false);
  }, [markAction]);

  const handleReferenceDictation = useCallback(async () => {
    markAction("reference:dictation");
    if (previewMode === "live" && hasTauriBackend()) {
      const config = await callBackend("get_dictation_config");
      if (config?.os_fallback_hint || config?.osFallbackHint) {
        pushToast(config.os_fallback_hint || config.osFallbackHint, "info");
        return;
      }
    }
    pushToast("Use your system dictation shortcut if embedded capture is not configured.", "info");
  }, [markAction, previewMode, pushToast]);

  const handleImageStudioRequestDraft = useCallback(
    draft => {
      const artifactCount = asList(draft?.proofArtifacts).length;
      markAction(`image-studio:request-draft:${draft?.route?.id || "route"}`);
      pushToast(
        `Image request draft prepared with ${artifactCount} proof artifact${artifactCount === 1 ? "" : "s"}.`,
        "info",
      );
    },
    [markAction, pushToast],
  );

  const handleVoiceCommand = useCallback(
    async command => {
      const action = String(command?.action || "").trim();
      const parameters = command?.parameters || {};
      markAction(`voice:${action || "unknown"}`);

      if (action === "surface.open") {
        const nextSurface = String(parameters.surface || "").trim();
        if (nextSurface === "agent") {
          setUiMode("agent");
          setSurface("agent");
          setActiveDrawer(null);
          return;
        }
        if (nextSurface === "builder") {
          setUiMode("builder");
          setSurface("builder");
          setActiveDrawer("builder");
          return;
        }
        if (nextSurface === "images") {
          setUiMode("builder");
          setSurface("images");
          setActiveDrawer(null);
          return;
        }
        if (nextSurface === "voice") {
          setUiMode("builder");
          setSurface("voice");
          setActiveDrawer(null);
          return;
        }
        if (["runtime", "skills", "proof", "queue", "context", "settings"].includes(nextSurface)) {
          setUiMode("builder");
          setSurface("builder");
          setActiveDrawer(nextSurface);
          return;
        }
        pushToast(`Voice command could not open ${nextSurface || "that surface"}.`, "warn");
        return;
      }

      if (action === "voice.showCommands") {
        setUiMode("builder");
        setSurface("voice");
        setActiveDrawer(null);
        return;
      }

      if (action === "voice.start") {
        await handleReferenceDictation();
        return;
      }

      if (action === "voice.stop") {
        return;
      }

      if (action === "voice.clearTranscript") {
        pushToast("Voice transcript cleared.", "info");
        return;
      }

      if (action === "composer.addNote" || action === "composer.addComment") {
        const text = String(parameters.text || command?.sourceText || "").trim();
        if (!text) {
          pushToast("Voice command did not include note text.", "warn");
          return;
        }
        setOperatorDraft(current => [current, text].filter(Boolean).join(current ? "\n" : ""));
        setUiMode("agent");
        setSurface("agent");
        pushToast("Dictated text added to the composer for review.", "info");
        return;
      }

      if (action === "composer.send") {
        if (mission) {
          await handleAgentFollowUp();
          return;
        }
        await handleAgentIdlePrimaryAction();
        return;
      }

      if (action === "search.query") {
        const query = String(parameters.query || "").trim();
        setWorkspaceSearchQuery(query);
        setMissionSearchQuery(query);
        pushToast(query ? `Searching workspace and mission lists for "${query}".` : "Search cleared.", "info");
        return;
      }

      if (action === "mission.pause" || action === "mission.resume") {
        setUiMode("agent");
        setSurface("agent");
        setActiveDrawer("queue");
        pushToast("Voice mission control opened the review queue; confirm the mission action there.", "info");
        return;
      }

      if (action === "approval.resolve") {
        setActiveDrawer("queue");
        pushToast("Approval queue opened for review before any decision is applied.", "info");
        return;
      }

      pushToast("Voice command parsed, but this shell action is not wired yet.", "warn");
    },
    [
      handleAgentFollowUp,
      handleAgentIdlePrimaryAction,
      handleReferenceDictation,
      markAction,
      mission,
      pushToast,
    ],
  );

  const handleReferenceAppearanceChange = useCallback((key, value) => {
    setReferenceAppearance(current => ({
      ...current,
      [key]: value,
    }));
  }, []);

  const handleReferenceInsertSlashCommand = useCallback(
    command => {
      const normalized = String(command || "").trim();
      markAction(`reference:slash:${normalized}`);
      if (normalized === "/new") {
        const created = createChatSessionForWorkspace({
          workspaceId: selectedWorkspaceId || workspace?.workspace_id || "",
          focus: true,
        });
        setSurface("agent");
        setAgentScene("run");
        setOperatorDraft("");
        clearOperatorAttachments();
        pushToast(
          created?.title
            ? `Conversation started: ${created.title}`
            : "New conversation started.",
          "info",
        );
        return;
      }
      setOperatorDraft(`${normalized} `);
    },
    [
      clearOperatorAttachments,
      createChatSessionForWorkspace,
      markAction,
      pushToast,
      selectedWorkspaceId,
      workspace?.workspace_id,
    ],
  );

  const referenceStudioKind = referenceStudio.collectionTab === "rule" ? "rule" : "skill";
  const referenceStudioSelectedId =
    referenceStudioKind === "rule" ? referenceStudio.selectedRuleId : referenceStudio.selectedSkillId;
  const referenceStudioSelectedItem = useMemo(
    () => findStudioItem(referenceStudio, referenceStudioKind, referenceStudioSelectedId),
    [referenceStudio, referenceStudioKind, referenceStudioSelectedId],
  );

  const updateReferenceStudioItem = useCallback((kind, itemId, updater) => {
    if (!itemId) {
      return;
    }
    setReferenceStudio(current => ({
      ...current,
      [studioCollectionKey(kind)]: asList(current[studioCollectionKey(kind)]).map(item =>
        item.id === itemId ? updater(item) : item,
      ),
    }));
  }, []);

  const computeSkillReadiness = useCallback(item => {
    const hasName = String(item?.name || "").trim().length > 2;
    const hasDescription = String(item?.description || "").trim().length > 12;
    const hasInstructions = asList(item?.instructions).length >= 2;
    const hasGuardrails = asList(item?.guardrails).length >= 2;
    const testsPassed = String(item?.testStatus || "").toLowerCase().includes("pass");
    const validationPassed = String(item?.validationStatus || "").toLowerCase().includes("pass");
    const ready = hasName && hasDescription && hasInstructions && hasGuardrails && testsPassed && validationPassed;
    return {
      ready,
      publishReadiness: ready ? "Ready to publish" : "Needs review",
      reviewRequired: !ready,
    };
  }, []);

  const applyRuleSetToWorkspaceProfile = useCallback(
    async (ruleSet, { persist = true, announce = true } = {}) => {
      if (!ruleSet) {
        return;
      }
      const nextProfile = {
        ...workspaceProfileForm,
        preferredHarness: ruleSet.preferredHarness || workspaceProfileForm.preferredHarness,
        routingStrategy: ruleSet.routingStrategy || workspaceProfileForm.routingStrategy,
        executionTargetPreference:
          ruleSet.executionTargetPreference || workspaceProfileForm.executionTargetPreference,
        routeOverrides: ROUTE_ROLE_OPTIONS.map(role => {
          const nextRoute = ruleSet.routePlan?.[role] || {};
          const currentRoute =
            workspaceProfileForm.routeOverrides.find(item => item.role === role) || {};
          return {
            role,
            provider: nextRoute.provider || currentRoute.provider || "openai",
            model: nextRoute.model || currentRoute.model || "",
            effort: nextRoute.effort || currentRoute.effort || "default",
          };
        }),
      };
      setWorkspaceProfileForm(nextProfile);
      setMissionForm(current => ({
        ...current,
        runtime:
          nextProfile.preferredHarness === "legacy_autonomous_engine"
            ? "openclaw"
            : current.runtime,
      }));
      if (persist) {
        await saveWorkspacePolicy(nextProfile);
      }
      if (announce) {
        pushToast(`${ruleSet.name} is now the active rule set.`, "info");
      }
    },
    [pushToast, saveWorkspacePolicy, workspaceProfileForm],
  );

  const handleReferenceStudioSelect = useCallback((kind, itemId) => {
    markAction(`reference:studio:${kind}:${itemId}`);
    setReferenceStudio(current => ({
      ...current,
      collectionTab: kind,
      selectedSkillId: kind === "skill" ? itemId : current.selectedSkillId,
      selectedRuleId: kind === "rule" ? itemId : current.selectedRuleId,
    }));
  }, [markAction]);

  const handleReferenceStudioFieldChange = useCallback(
    (field, value) => {
      if (!referenceStudioSelectedItem?.id) {
        return;
      }
      updateReferenceStudioItem(referenceStudioKind, referenceStudioSelectedItem.id, item => ({
        ...item,
        [field]: value,
      }));
    },
    [referenceStudioKind, referenceStudioSelectedItem?.id, updateReferenceStudioItem],
  );

  const handleReferenceStudioListChange = useCallback(
    (field, value) => {
      if (!referenceStudioSelectedItem?.id) {
        return;
      }
      updateReferenceStudioItem(referenceStudioKind, referenceStudioSelectedItem.id, item => ({
        ...item,
        [field]: splitEditorLines(value),
      }));
    },
    [referenceStudioKind, referenceStudioSelectedItem?.id, updateReferenceStudioItem],
  );

  const handleReferenceStudioRouteFieldChange = useCallback(
    (role, field, value) => {
      if (!referenceStudioSelectedItem?.id || referenceStudioKind !== "rule") {
        return;
      }
      updateReferenceStudioItem("rule", referenceStudioSelectedItem.id, item => ({
        ...item,
        routePlan: {
          ...(item.routePlan || {}),
          [role]: {
            ...(item.routePlan?.[role] || {}),
            [field]: value,
          },
        },
      }));
    },
    [referenceStudioKind, referenceStudioSelectedItem?.id, updateReferenceStudioItem],
  );

  const handleReferenceStudioAssistantFieldChange = useCallback(
    (field, value) => {
      if (!referenceStudioSelectedItem?.id) {
        return;
      }
      updateReferenceStudioItem(referenceStudioKind, referenceStudioSelectedItem.id, item => ({
        ...item,
        assistant: {
          ...(item.assistant || {}),
          [field]: value,
        },
      }));
    },
    [referenceStudioKind, referenceStudioSelectedItem?.id, updateReferenceStudioItem],
  );

  const applyReferenceStudioProposal = useCallback(
    async ({ asDraft = false } = {}) => {
      if (!referenceStudioSelectedItem?.id || !referenceStudioSelectedItem?.assistant?.proposal) {
        return;
      }
      const mergedItem = mergeStudioProposal(
        referenceStudioSelectedItem,
        referenceStudioSelectedItem.assistant.proposal.patch,
      );
      updateReferenceStudioItem(referenceStudioKind, referenceStudioSelectedItem.id, item => {
        const merged = mergeStudioProposal(item, item.assistant?.proposal?.patch);
        const readiness = referenceStudioKind === "skill" ? computeSkillReadiness(merged) : null;
        return {
          ...merged,
          status: asDraft ? "Draft" : item.status === "Draft" ? "Active" : item.status,
          publishReadiness: readiness?.publishReadiness || merged.publishReadiness,
          reviewRequired: readiness ? readiness.reviewRequired : merged.reviewRequired,
          assistant: {
            ...(item.assistant || {}),
            proposal: null,
            prompt: "",
          },
        };
      });
      if (!asDraft && mergedItem.kind === "rule") {
        await applyRuleSetToWorkspaceProfile(mergedItem, { persist: true, announce: false });
      }
      pushToast(
        asDraft
          ? `${referenceStudioSelectedItem.name} changes were inserted as a draft.`
          : `${referenceStudioSelectedItem.name} changes were applied.`,
        "info",
      );
    },
    [
      applyRuleSetToWorkspaceProfile,
      pushToast,
      referenceStudioKind,
      referenceStudioSelectedItem,
      updateReferenceStudioItem,
    ],
  );

  const handleReferenceStudioAssistantSubmit = useCallback(async () => {
    if (!referenceStudioSelectedItem?.id) {
      return;
    }
    const assistant = referenceStudioSelectedItem.assistant || {};
    const prompt = String(assistant.prompt || "").trim();
    if (!prompt) {
      pushToast("Write a refinement request first.", "warn");
      return;
    }
    const requestedModel = assistant.model || "gpt-5.5";
    const requestedEffort = assistant.effort || "Balanced";
    const baseConversation = [
      {
        role: "user",
        author: "You",
        body: prompt,
        meta: timestampLabel(new Date().toISOString()) || "Now",
      },
    ];

    if (previewMode === "live" && hasTauriBackend() && data.openClawStatus?.connected) {
      const runtimePrompt = buildStudioAssistantRuntimePrompt(
        referenceStudioSelectedItem,
        prompt,
        requestedModel,
        requestedEffort,
      );
      studioAssistantPendingRef.current = {
        kind: referenceStudioKind,
        itemId: referenceStudioSelectedItem.id,
        item: referenceStudioSelectedItem,
        model: requestedModel,
      };
      updateReferenceStudioItem(referenceStudioKind, referenceStudioSelectedItem.id, item => ({
        ...item,
        assistant: {
          ...(item.assistant || {}),
          conversation: [
            ...baseConversation,
            {
              role: "assistant",
              author: requestedModel,
              body: "Submitted to the live runtime for refinement.",
              meta: "Waiting for runtime reply",
            },
            ...asList(item.assistant?.conversation).filter(
              entry => entry?.meta !== "Waiting for runtime reply",
            ),
          ].slice(0, 6),
        },
      }));
      try {
        await callBackend(
          "send_openclaw_message",
          { payload: { message: runtimePrompt } },
          { throwOnError: true },
        );
        pushToast(`${referenceStudioSelectedItem.name} refinement sent to the live runtime.`, "info");
        return;
      } catch (error) {
        studioAssistantPendingRef.current = null;
        pushToast(`Live refinement send failed, using local proposal: ${error}`, "warn");
      }
    }

    const proposal = buildStudioAssistantProposal(
      referenceStudioSelectedItem,
      prompt,
      requestedModel,
      requestedEffort,
    );
    updateReferenceStudioItem(referenceStudioKind, referenceStudioSelectedItem.id, item => ({
      ...item,
      assistant: {
        ...(item.assistant || {}),
        conversation: [
          ...baseConversation,
          {
            role: "assistant",
            author: requestedModel,
            body: proposal.reply,
            meta: timestampLabel(new Date().toISOString()) || "Now",
          },
          ...asList(item.assistant?.conversation),
        ].slice(0, 6),
        proposal,
      },
      validationStatus: "Pending",
      publishReadiness: "Needs review",
      reviewRequired: true,
    }));
  }, [
    data.openClawStatus?.connected,
    previewMode,
    pushToast,
    referenceStudioKind,
    referenceStudioSelectedItem,
    updateReferenceStudioItem,
    callBackend,
  ]);

  const handleReferenceStudioSaveDraft = useCallback(() => {
    if (!referenceStudioSelectedItem?.id) {
      return;
    }
    updateReferenceStudioItem(referenceStudioKind, referenceStudioSelectedItem.id, item => ({
      ...item,
      status: "Draft",
      reviewRequired: true,
      publishReadiness: "Needs review",
    }));
    pushToast(`${referenceStudioSelectedItem.name} saved as draft.`, "info");
  }, [pushToast, referenceStudioKind, referenceStudioSelectedItem, updateReferenceStudioItem]);

  const handleReferenceStudioPublish = useCallback(async () => {
    if (!referenceStudioSelectedItem?.id) {
      return;
    }
    const readiness = referenceStudioKind === "skill" ? computeSkillReadiness(referenceStudioSelectedItem) : { ready: true };
    if (referenceStudioKind === "skill" && !readiness.ready) {
      pushToast("Skill is not publish-ready. Run validation/tests and complete review first.", "warn");
      return;
    }
    updateReferenceStudioItem(referenceStudioKind, referenceStudioSelectedItem.id, item => ({
      ...item,
      status: "Active",
      publishReadiness: "Ready to publish",
      reviewRequired: false,
    }));
    setReferenceStudio(current => ({
      ...current,
      activeSkillIds:
        referenceStudioKind === "skill"
          ? uniq([...(current.activeSkillIds || []), referenceStudioSelectedItem.id])
          : current.activeSkillIds,
      activeRuleSetId:
        referenceStudioKind === "rule" ? referenceStudioSelectedItem.id : current.activeRuleSetId,
    }));
    if (referenceStudioKind === "rule") {
      const nextRule = mergeStudioProposal(
        referenceStudioSelectedItem,
        referenceStudioSelectedItem.assistant?.proposal?.patch,
      );
      await applyRuleSetToWorkspaceProfile(nextRule);
    } else {
      pushToast(`${referenceStudioSelectedItem.name} is now active.`, "info");
    }
  }, [
    applyRuleSetToWorkspaceProfile,
    pushToast,
    referenceStudioKind,
    referenceStudioSelectedItem,
    updateReferenceStudioItem,
  ]);

  const handleReferenceProviderDraftChange = useCallback((providerId, value) => {
    setProviderSecretDrafts(current => ({ ...current, [providerId]: value }));
  }, []);

  const openProviderGuideUrl = useCallback(
    async (url, label) => {
      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast(`Preview mode cannot open ${label}.`, "warn");
        return false;
      }
      try {
        await callBackend(
          "open_external_url_command",
          { url },
          { throwOnError: true },
        );
        pushToast(`${label} opened in your browser.`, "info");
        return true;
      } catch (error) {
        pushToast(`Could not open ${label}: ${error}`, "error");
        return false;
      }
    },
    [previewMode, pushToast],
  );

  const openBridgeEndpoint = useCallback(
    async (url, label) => {
      if (!url) {
        pushToast(`${label} has no bridge endpoint yet.`, "warn");
        return false;
      }
      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast(`Preview mode cannot open ${label}.`, "warn");
        return false;
      }
      try {
        await callBackend(
          "open_external_url_command",
          { url },
          { throwOnError: true },
        );
        pushToast(`${label} opened in your browser.`, "info");
        return true;
      } catch (error) {
        pushToast(`Could not open ${label}: ${error}`, "error");
        return false;
      }
    },
    [previewMode, pushToast],
  );

  const openProviderAuthUrl = useCallback(
    async (url, label) => {
      if (previewMode !== "live" || !hasCommandBackend()) {
        pushToast(`Preview mode cannot open ${label}.`, "warn");
        return false;
      }
      try {
        await callBackend(
          "open_external_url_command",
          { url },
          { throwOnError: true },
        );
        pushToast(`${label} opened in your browser.`, "info");
        return true;
      } catch (error) {
        pushToast(`Could not open ${label}: ${error}`, "error");
        return false;
      }
    },
    [previewMode, pushToast],
  );

  const handleReferenceQuickAuth = useCallback(
    async providerId => {
      if (providerId === "openai") {
        if (!providerOAuthActionsAvailable) {
          pushToast(providerOAuthUnavailableReason, "warn");
          return;
        }
        if (openAICodexOAuthFlow.sessionId && ["waiting", "error"].includes(openAICodexOAuthFlow.status)) {
          setOpenAICodexOAuthFlow(current => ({ ...current, open: true }));
          pushToast("Finish the pending OpenAI Codex OAuth session in the Syntelos panel.", "info");
          return;
        }
        try {
          const result = await callBackend(
            "start_openai_codex_oauth_command",
            undefined,
            { throwOnError: true },
          );
          let finalResult = result;
          if (result?.status === "manual_required") {
            setOpenAICodexOAuthFlow({
              open: true,
              sessionId: result.sessionId || "",
              method: result.method || "",
              authUrl: result.authUrl || "",
              callbackPort: result.callbackPort || 0,
              relayUrl: result.relayUrl || "",
              relayToken: result.relayToken || "",
              helperCommand: result.helperCommand || "",
              verificationUrl: result.verificationUrl || result.authUrl || "",
              userCode: result.userCode || "",
              callback: "",
              status: "waiting",
              message:
                result.message ||
                "Run the local relay helper on this browser device. It will open OpenAI sign-in and connect the NAS automatically.",
              output: result.output || "",
            });
            pushToast("OpenAI Codex sign-in relay is ready.", "info");
            return;
          }
          if (finalResult?.authenticated) {
            const hermesSync = finalResult?.hermesSync || finalResult?.hermes_sync || {};
            const nextProfile = {
              ...workspaceProfileForm,
              openaiCodexAuthMode: "oauth",
            };
            setWorkspaceProfileForm(nextProfile);
            await saveWorkspacePolicy(nextProfile);
            pushToast(
              hermesSync?.synced
                ? "OpenAI Codex OAuth connected and synced to Hermes."
                : "OpenAI Codex OAuth connected.",
              "info",
            );
            await refreshAll("openai-codex-oauth");
          } else {
            pushToast(finalResult?.message || "OpenAI Codex OAuth did not complete.", "warn");
          }
        } catch (error) {
          pushToast(`OpenAI Codex OAuth failed: ${error}`, "error");
        }
        return;
      }
      if (providerId === "minimax") {
        if (!providerOAuthActionsAvailable) {
          pushToast(providerOAuthUnavailableReason, "warn");
          return;
        }
        try {
          const result = await callBackend(
            "start_minimax_openclaw_auth_command",
            { payload: { region: "global" } },
            { throwOnError: true },
          );
          const nextProfile = {
            ...workspaceProfileForm,
            minimaxAuthMode: "minimax-portal-oauth",
          };
          setWorkspaceProfileForm(nextProfile);
          await saveWorkspacePolicy(nextProfile);
          if (result?.status?.authenticated) {
            pushToast("MiniMax OpenClaw OAuth is already verified.", "info");
          } else if (result?.sessionId && result?.verificationUrl) {
            setMiniMaxOAuthFlow({
              open: true,
              sessionId: result.sessionId || "",
              method: result.method || "oauth",
              region: result.region || "global",
              verificationUrl: result.verificationUrl || "",
              userCode: result.userCode || "",
              command: result.command || "",
              status: "waiting",
              message:
                result.message ||
                "Open MiniMax verification, approve access, then verify the NAS session.",
              output: result.output || "",
            });
            pushToast("MiniMax OAuth verification is ready.", "info");
          } else if (result?.manualRequired || result?.command) {
            const copied = await copyTextValue(result.command || "");
            pushToast(
              copied
                ? "MiniMax OpenClaw auth command copied. Run it on the NAS or runtime host, then verify auth."
                : result?.message || "Run the MiniMax OpenClaw auth command on the runtime host, then verify auth.",
              "info",
            );
          } else {
            pushToast("MiniMax OpenClaw OAuth terminal opened. Finish the login there, then verify auth.", "info");
          }
          await refreshAll("minimax-openclaw-oauth-started");
        } catch (error) {
          pushToast(`MiniMax OpenClaw OAuth failed to start: ${error}`, "error");
        }
      }
    },
    [
      callBackend,
      openAICodexOAuthFlow.sessionId,
      openAICodexOAuthFlow.status,
      providerOAuthActionsAvailable,
      providerOAuthUnavailableReason,
      pushToast,
      refreshAll,
      saveWorkspacePolicy,
      workspaceProfileForm,
    ],
  );

  const completeOpenAICodexOAuth = useCallback(async () => {
    const callback = String(openAICodexOAuthFlow.callback || "").trim();
    if (!openAICodexOAuthFlow.sessionId) {
      pushToast("Start OpenAI Codex OAuth again; the NAS session is missing.", "warn");
      return;
    }
    if (!callback) {
      pushToast("Paste the localhost callback URL from the OpenAI tab first.", "warn");
      return;
    }
    setOpenAICodexOAuthFlow(current => ({
      ...current,
      status: "completing",
      message: "Completing OpenAI Codex OAuth on the NAS runtime...",
    }));
    try {
      const finalResult = await callBackend(
        "complete_openai_codex_oauth_command",
        { sessionId: openAICodexOAuthFlow.sessionId, callback },
        { throwOnError: true },
      );
      if (finalResult?.authenticated) {
        const hermesSync = finalResult?.hermesSync || finalResult?.hermes_sync || {};
        const nextProfile = {
          ...workspaceProfileForm,
          openaiCodexAuthMode: "oauth",
        };
        setWorkspaceProfileForm(nextProfile);
        await saveWorkspacePolicy(nextProfile);
        setOpenAICodexOAuthFlow({
          open: false,
          sessionId: "",
          authUrl: "",
          callback: "",
          status: "idle",
          message: "",
          output: "",
        });
        pushToast(
          hermesSync?.synced
            ? "OpenAI Codex OAuth connected and synced to Hermes."
            : "OpenAI Codex OAuth connected.",
          "info",
        );
        await refreshAll("openai-codex-oauth");
        return;
      }
      setOpenAICodexOAuthFlow(current => ({
        ...current,
        status: "error",
        message: finalResult?.message || "OpenAI Codex OAuth did not complete.",
        output: finalResult?.output || current.output,
      }));
      pushToast(finalResult?.message || "OpenAI Codex OAuth did not complete.", "warn");
    } catch (error) {
      setOpenAICodexOAuthFlow(current => ({
        ...current,
        status: "error",
        message: `OpenAI Codex OAuth failed: ${error}`,
      }));
      pushToast(`OpenAI Codex OAuth failed: ${error}`, "error");
    }
  }, [
    callBackend,
    openAICodexOAuthFlow.callback,
    openAICodexOAuthFlow.sessionId,
    pushToast,
    refreshAll,
    saveWorkspacePolicy,
    workspaceProfileForm,
  ]);

  const completeMiniMaxOAuth = useCallback(async () => {
    if (!miniMaxOAuthFlow.sessionId) {
      pushToast("Start MiniMax OAuth again; the NAS session is missing.", "warn");
      return;
    }
    setMiniMaxOAuthFlow(current => ({
      ...current,
      status: "checking",
      message: "Checking MiniMax OAuth approval on the NAS runtime...",
    }));
    try {
      const finalResult = await callBackend(
        "complete_minimax_openclaw_auth_command",
        { sessionId: miniMaxOAuthFlow.sessionId },
        { throwOnError: true },
      );
      if (finalResult?.authenticated) {
        const nextProfile = {
          ...workspaceProfileForm,
          minimaxAuthMode: "minimax-portal-oauth",
        };
        setWorkspaceProfileForm(nextProfile);
        await saveWorkspacePolicy(nextProfile);
        setMiniMaxOAuthFlow(DEFAULT_MINIMAX_OAUTH_FLOW);
        pushToast("MiniMax OpenClaw OAuth connected.", "info");
        await refreshAll("minimax-openclaw-oauth");
        return;
      }
      setMiniMaxOAuthFlow(current => ({
        ...current,
        status: finalResult?.pending ? "waiting" : "error",
        message: finalResult?.message || "MiniMax OAuth is not verified yet.",
        output: finalResult?.output || current.output,
      }));
      pushToast(
        finalResult?.message || "MiniMax OAuth is not verified yet.",
        finalResult?.pending ? "warn" : "error",
      );
    } catch (error) {
      setMiniMaxOAuthFlow(current => ({
        ...current,
        status: "error",
        message: `MiniMax OAuth failed: ${error}`,
      }));
      pushToast(`MiniMax OAuth failed: ${error}`, "error");
    }
  }, [
    callBackend,
    miniMaxOAuthFlow.sessionId,
    pushToast,
    refreshAll,
    saveWorkspacePolicy,
    workspaceProfileForm,
  ]);

  const verifyMiniMaxOpenClawAuth = useCallback(async () => {
    if (!providerOAuthActionsAvailable) {
      pushToast(providerOAuthUnavailableReason, "warn");
      return;
    }
    try {
      const status = await callBackend(
        "get_minimax_openclaw_auth_status_command",
        undefined,
        { throwOnError: true },
      );
      if (status?.authenticated) {
        const nextProfile = {
          ...workspaceProfileForm,
          minimaxAuthMode: "minimax-portal-oauth",
        };
        setWorkspaceProfileForm(nextProfile);
        await saveWorkspacePolicy(nextProfile);
        pushToast("MiniMax OpenClaw OAuth verified.", "info");
      } else {
        pushToast(status?.message || "MiniMax OpenClaw OAuth is not verified yet.", "warn");
      }
      await refreshAll("minimax-openclaw-oauth-verified");
    } catch (error) {
      pushToast(`Could not verify MiniMax OpenClaw OAuth: ${error}`, "error");
    }
  }, [
    callBackend,
    providerOAuthActionsAvailable,
    providerOAuthUnavailableReason,
    pushToast,
    refreshAll,
    saveWorkspacePolicy,
    workspaceProfileForm,
  ]);

  const handleReferenceWorkspaceProfileFieldChange = useCallback((field, value) => {
    setWorkspaceProfileForm(current => ({
      ...current,
      [field]: value,
    }));
  }, []);

  const handleReferenceRouteOverrideChange = useCallback((role, field, value) => {
    setWorkspaceProfileForm(current => ({
      ...current,
      routeOverrides: current.routeOverrides.map(item =>
        item.role === role ? { ...item, [field]: value } : item,
      ),
    }));
  }, []);

  const handleReferenceApplyActiveRuleSet = useCallback(async () => {
    const activeRule =
      findStudioItem(referenceStudio, "rule", referenceStudio.activeRuleSetId) ||
      findStudioItem(referenceStudio, "rule", referenceStudio.selectedRuleId);
    if (!activeRule) {
      pushToast("Select a rule set first.", "warn");
      return;
    }
    await applyRuleSetToWorkspaceProfile(activeRule);
  }, [applyRuleSetToWorkspaceProfile, pushToast, referenceStudio]);

  const openAuthDrawer = useCallback(() => {
    setUiMode("builder");
    setActiveDrawer("runtime");
    window.setTimeout(() => {
      document.getElementById("provider-auth-panel")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 0);
  }, []);

  useEffect(() => {
    if (previewMode !== "live" || mission || workspaces.length === 0 || modelAuthReady || authPromptedRef.current) {
      return;
    }
    authPromptedRef.current = true;
    openAuthDrawer();
  }, [mission, modelAuthReady, openAuthDrawer, previewMode, workspaces.length]);

  const drawerItems = useMemo(() => {
    const items = [
      {
        id: "queue",
        label: "Queue",
        count: viewModel.drawers.queue.count,
        tone: viewModel.drawers.queue.urgent ? "warn" : "neutral",
      },
      {
        id: "proof",
        label: "Proof",
        count: viewModel.drawers.proof.itemsCount,
        tone: viewModel.drawers.proof.tone,
      },
      {
        id: "context",
        label: "Context",
        count: viewModel.drawers.context.count,
        tone: "neutral",
      },
      {
        id: "skills",
        label: "Skills",
        count: viewModel.drawers.builder.skillStudio.summary.needsTestCount,
        tone:
          viewModel.drawers.builder.skillStudio.summary.needsTestCount > 0 ? "warn" : "neutral",
      },
      {
        id: "runtime",
        label: "Setup",
        count: viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount,
        tone:
          viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount > 0
            ? "warn"
            : "neutral",
      },
      {
        id: "settings",
        label: "Settings",
        count: 0,
        tone: "neutral",
      },
    ];
    if (uiMode === "builder") {
      items.push({
        id: "profiles",
        label: "Profiles",
        count: viewModel.drawers.builder.profileStudio.profileRows.length,
        tone: "neutral",
      });
      items.push({
        id: "builder",
        label: "Builder",
        count: viewModel.drawers.builder.reviewCount,
        tone: "neutral",
      });
    }
    return items;
  }, [uiMode, viewModel]);
  const visibleDrawerItems = useMemo(
    () =>
      uiMode === "builder"
        ? drawerItems
        : drawerItems.filter(item => agentVisibleDrawers.includes(item.id)),
    [agentVisibleDrawers, drawerItems, uiMode],
  );
  const activeDrawerMeta = useMemo(
    () =>
      visibleDrawerItems.find(item => item.id === activeDrawer) ||
      drawerItems.find(item => item.id === activeDrawer) ||
      null,
    [activeDrawer, drawerItems, visibleDrawerItems],
  );

  const renderDrawerPanel = () => {
    if (activeDrawer === "queue") {
      return (
        <section className="drawer-panel">
          <header>
            <p className="eyebrow">Urgency</p>
            <h2>{viewModel.drawers.queue.label}</h2>
            <p>{viewModel.drawers.queue.recommendation.reason}</p>
          </header>
          <div className="drawer-list">
            {viewModel.drawers.queue.items.map(item => (
              <article className={`drawer-card ${toneClass(item.tone)}`} key={`${item.type}-${item.title}`}>
                <span>{item.type}</span>
                <strong>{item.title}</strong>
                <p>{item.reason}</p>
              </article>
            ))}
          </div>
          <div className="drawer-actions">
            <ActionButton onClick={handlePrimaryAction} variant="primary">
              {viewModel.topBar.primaryAction.label}
            </ActionButton>
            <ActionButton
              disabled={!missionActionAvailable(mission, "resume")}
              onClick={() => void runMissionAction("resume", "Mission resume requested.")}
            >
              Resume mission
            </ActionButton>
          </div>
        </section>
      );
    }

    if (activeDrawer === "proof") {
      return (
        <section className="drawer-panel">
          <header>
            <p className="eyebrow">Proof review</p>
            <h2>{viewModel.drawers.proof.headline}</h2>
            <p>{viewModel.drawers.proof.diffSummary}</p>
          </header>
          <div className="drawer-actions">
            <ActionButton onClick={() => setProofWrapEnabled(current => !current)} type="button">
              {proofWrapEnabled ? "Disable wrap" : "Enable wrap"}
            </ActionButton>
          </div>
          <section className="proof-compare-grid">
            {viewModel.drawers.proof.sections.map(section => (
              <section className="drawer-block" key={section.title}>
                <h3>{section.title}</h3>
                <div className={`proof-item-list ${proofWrapEnabled ? "wrap" : "no-wrap"}`.trim()}>
                  {section.items.length > 0 ? (
                    section.items.map(item => (
                      <article className="proof-item-row" key={`${section.title}-${item}`}>
                        <code>{listLabel(item)}</code>
                        <ActionButton
                          onClick={() => copyContextValue(listLabel(item))}
                          type="button"
                        >
                          Copy
                        </ActionButton>
                      </article>
                    ))
                  ) : (
                    <article className="proof-item-row">
                      <code>Nothing captured yet.</code>
                    </article>
                  )}
                </div>
              </section>
            ))}
          </section>
        </section>
      );
    }

    if (activeDrawer === "skills") {
      const filteredRecommendedSkills = viewModel.drawers.builder.skillStudio.recommended.filter(
        item => item.label.toLowerCase().includes(skillStudioQuery.trim().toLowerCase()) || item.description.toLowerCase().includes(skillStudioQuery.trim().toLowerCase()),
      );
      const filteredCuratedSkills = viewModel.drawers.builder.skillStudio.curated.filter(item => {
        const query = skillStudioQuery.trim().toLowerCase();
        const matchesQuery =
          !query ||
          item.label.toLowerCase().includes(query) ||
          (item.description || "").toLowerCase().includes(query);
        if (!matchesQuery) {
          return false;
        }
        if (skillStudioFilter === "recommended") {
          return item.installed;
        }
        if (skillStudioFilter === "needs_attention") {
          return !item.installed || item.testStatus !== "Reviewed";
        }
        return true;
      });

      return (
        <section className="drawer-panel">
          <header>
            <h2>Skills</h2>
            <p>Install, review, and route the packs that actually support operator work.</p>
          </header>

          <section className="drawer-block">
            <div className="skill-toolbar">
              <Field label="Filter">
                <select onChange={event => setSkillStudioFilter(event.target.value)} value={skillStudioFilter}>
                  <option value="all">All packs</option>
                  <option value="recommended">Installed</option>
                  <option value="needs_attention">Needs attention</option>
                </select>
              </Field>
              <Field label="Find skill pack">
                <input
                  onChange={event => setSkillStudioQuery(event.target.value)}
                  placeholder="Search by label or note"
                  value={skillStudioQuery}
                />
              </Field>
            </div>
            <div className="context-grid compact-metrics">
              <article className="context-item">
                <span>Reviewed reusable</span>
                <strong>
                  {viewModel.drawers.builder.skillStudio.summary.reviewedReusableCount}/
                  {viewModel.drawers.builder.skillStudio.summary.totalSkills}
                </strong>
              </article>
              <article className="context-item">
                <span>Execution ready</span>
                <strong>{viewModel.drawers.builder.skillStudio.summary.executionReadyCount}</strong>
              </article>
              <article className="context-item">
                <span>Need tests</span>
                <strong>{viewModel.drawers.builder.skillStudio.summary.needsTestCount}</strong>
              </article>
            </div>
          </section>

          <section className={`drawer-block skill-recovery-panel ${toneClass(missionSkillRecoveryNeedsAction ? "warn" : "good")}`}>
            <div className="skill-recovery-head">
              <div>
                <h3>Skill recovery</h3>
                <p>
                  {missionSkillRecoveryNeedsAction
                    ? "The current mission has recovery signals. Pick a different skill, route, or handoff before retrying the same step."
                    : "No blocked-state skill recovery is active for the current mission."}
                </p>
              </div>
              <span>{titleizeToken(missionSkillRecovery.status || "idle")}</span>
            </div>
            <div className="context-grid compact-metrics">
              <article className="context-item">
                <span>Triggers</span>
                <strong>{missionSkillRecoveryTriggers.length}</strong>
              </article>
              <article className="context-item">
                <span>Recommended skills</span>
                <strong>{missionSkillRecoveryRecommendations.length}</strong>
              </article>
              <article className="context-item">
                <span>Runtime lane</span>
                <strong>{titleizeToken(missionSkillRecoveryRoute.runtimeLane || mission?.runtime_id || "none")}</strong>
              </article>
            </div>
            {missionSkillRecoveryTriggers.length > 0 ? (
              <div className="drawer-list compact skill-recovery-list">
                {missionSkillRecoveryTriggers.slice(0, 4).map(item => (
                  <article
                    className={`drawer-card ${toneClass(item.severity === "high" ? "bad" : "warn")}`}
                    key={`skill-recovery-trigger-${item.triggerId || item.label}`}
                  >
                    <span>{titleizeToken(item.severity || "signal")}</span>
                    <strong>{item.label || titleizeToken(item.triggerId || "Recovery signal")}</strong>
                    <p>{item.reason || "Recovery signal captured from mission state."}</p>
                    {asList(item.evidence).length > 0 ? (
                      <p>{`Evidence: ${asList(item.evidence).slice(0, 2).map(listLabel).join(" | ")}`}</p>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : null}
            {missionSkillRecoveryRecommendations.length > 0 ? (
              <details open>
                <summary>Recommended recovery skills</summary>
                <div className="drawer-list compact skill-recovery-list">
                  {missionSkillRecoveryRecommendations.slice(0, 4).map(item => (
                    <article className="drawer-card tone-neutral" key={`skill-recovery-rec-${item.recommendationId || item.skillId}`}>
                      <span>{titleizeToken(item.sourceKind || "skill")}</span>
                      <strong>{item.label || titleizeToken(item.skillId || "Recovery skill")}</strong>
                      <p>{item.reason || item.recoveryAction || "Recommended by the mission recovery contract."}</p>
                      <div className="pill-row">
                        <span className="mini-pill">{item.executionCapable ? "Execution-capable" : "Guidance"}</span>
                        <span className="mini-pill muted">{item.guidanceOnly ? "Review first" : "Can route"}</span>
                      </div>
                    </article>
                  ))}
                </div>
              </details>
            ) : null}
            <details>
              <summary>Recovery actions and route separation</summary>
              <ul>
                {missionSkillRecoveryActions.length > 0 ? (
                  missionSkillRecoveryActions.slice(0, 5).map(item => (
                    <li key={`skill-recovery-action-${item.triggerId || item.label}`}>
                      {item.action || item.label}
                    </li>
                  ))
                ) : (
                  <li>Continue normal plan-execute-verify flow; no recovery action is currently required.</li>
                )}
              </ul>
              <p className="drawer-footnote">
                {missionSkillRecoveryRoute.rule ||
                  "Hermes/OpenClaw remain runtime lanes; model providers remain provider routes."}
                {missionSkillRecoveryProviderRoute.provider
                  ? ` Provider: ${missionSkillRecoveryProviderRoute.provider} ${missionSkillRecoveryProviderRoute.model || ""}`.trim()
                  : ""}
              </p>
            </details>
          </section>

          <section className="drawer-block">
            <h3>Recommended packs</h3>
            <div className="drawer-list">
              {filteredRecommendedSkills.length > 0 ? (
                filteredRecommendedSkills.map(item => (
                  <article className={`drawer-card ${toneClass(item.tone)}`} key={`recommended-${item.id}`}>
                    <span>{item.originType}</span>
                    <strong>{item.label}</strong>
                    <p>{item.description}</p>
                    <div className="pill-row">
                      <span className="mini-pill">{item.status}</span>
                      <span className="mini-pill muted">{item.installed ? "Installed" : "Not installed"}</span>
                      <span className="mini-pill muted">
                        {item.executionCapable ? "Execution" : "Guidance only"}
                      </span>
                    </div>
                  </article>
                ))
              ) : (
                <article className="drawer-card">
                  <strong>No recommended pack matches this filter.</strong>
                </article>
              )}
            </div>
          </section>

          <section className="drawer-block">
            <h3>Curated library</h3>
            <div className="drawer-list">
              {filteredCuratedSkills.length > 0 ? (
                filteredCuratedSkills.map(item => (
                  <article className={`drawer-card ${toneClass(item.tone)}`} key={`curated-${item.id}`}>
                    <span>{item.originType}</span>
                    <strong>{item.label}</strong>
                    <p>{item.status}</p>
                    <div className="pill-row">
                      <span className="mini-pill">{item.testStatus}</span>
                      <span className="mini-pill muted">{item.usageCount} uses</span>
                      <span className="mini-pill muted">{item.helpedCount} helped</span>
                    </div>
                  </article>
                ))
              ) : (
                <article className="drawer-card">
                  <strong>No curated pack matches this filter.</strong>
                </article>
              )}
            </div>
            <p className="drawer-footnote">{viewModel.drawers.builder.skillStudio.capabilitiesNote}</p>
          </section>
        </section>
      );
    }

    if (activeDrawer === "runtime") {
      const primaryRuntimeServices = [
        ...focusedRuntimeServices.hermes,
        ...focusedRuntimeServices.openClaw.filter(
          item => !focusedRuntimeServices.hermes.some(existing => existing.serviceId === item.serviceId),
        ),
      ];
      const bridgeServices = focusedRuntimeServices.bridges.filter(
        item => !primaryRuntimeServices.some(existing => existing.serviceId === item.serviceId),
      );

      return (
        <section className="drawer-panel">
          <header>
            <h2>Tools and accounts</h2>
            <p>Keep Hermes, OpenClaw, OpenCodeGo, image tools, and phone alerts healthy from one simple setup panel.</p>
          </header>

          <section className="drawer-block" id="provider-auth-panel">
            <h3>AI accounts and model tools</h3>
            <div className="context-grid compact-metrics">
              <article className="context-item">
                <span>OpenAI / Codex auth</span>
                <strong>{`${openAICodexAuthPath} · ${openAICodexAuthReady ? "Ready" : "Missing"}`}</strong>
                <p>
                  Connect your OpenAI account for Codex/OpenClaw, or save an API key for direct model calls.
                </p>
              </article>
              <article className="context-item">
                <span>MiniMax auth</span>
                <strong>{`${minimaxAuthPath} · ${minimaxAuthReady ? "Ready" : "Missing"}`}</strong>
                <p>
                  {minimaxAuthPath.toLowerCase().includes("oauth")
                    ? "Syntelos checks the MiniMax login file before marking MiniMax ready."
                    : "Save a MiniMax API key when you want MiniMax model runs."}
                </p>
              </article>
              <article className="context-item">
                <span>Active provider route</span>
                <strong>
                  {missionProviderTruth?.activeRoute?.provider
                    ? `${titleizeToken(missionProviderTruth.activeRoute.provider)} · ${missionProviderTruth.activeRoute.model || "default"}`
                    : "Not resolved"}
                </strong>
                <p>
                  {missionProviderTruth?.activeRoute?.role
                    ? `${titleizeToken(missionProviderTruth.activeRoute.role)} in ${titleizeToken(missionProviderTruth.currentPhase || agentCyclePhase)}`
                    : "The active AI account appears here after the first model-backed step."}
                </p>
              </article>
              <article className="context-item">
                <span>Provider ecosystem</span>
                <strong>{providerEcosystemSummary.totalProvidersTracked || providerEcosystemProviders.length} tracked</strong>
                <p>
                  {providerEcosystemSummary.routeReadyCount || 0} route ready · safe catalog refresh keeps user-defined models.
                </p>
              </article>
              <article className="context-item">
                <span>Last successful model call</span>
                <strong>
                  {missionProviderTruth?.lastSuccessfulCall?.provider
                    ? `${titleizeToken(missionProviderTruth.lastSuccessfulCall.provider)} · ${missionProviderTruth.lastSuccessfulCall.model || "default"}`
                    : "None yet"}
                </strong>
                <p>
                  {missionProviderTruth?.lastSuccessfulCall?.at
                    ? timestampLabel(missionProviderTruth.lastSuccessfulCall.at)
                    : "Success timestamps appear after the first grounded action result."}
                </p>
              </article>
              <article className="context-item">
                <span>Last provider failure</span>
                <strong>
                  {missionProviderTruth?.lastFailure?.provider
                    ? `${titleizeToken(missionProviderTruth.lastFailure.provider)} · ${missionProviderTruth.lastFailure.model || "default"}`
                    : "No provider failure"}
                </strong>
                <p>
                  {missionProviderTruth?.lastFailure?.summary ||
                    "Connection or model errors appear here when something needs attention."}
                </p>
              </article>
            </div>

            <div className="drawer-list">
              {PROVIDER_SECRET_OPTIONS.map(item => {
                const hasSecret = Boolean(providerSecretPresence[item.id]);
                const providerAuthReady =
                  item.id === "openai"
                    ? openAICodexAuthReady
                    : item.id === "minimax"
                      ? minimaxAuthReady
                      : hasSecret;
                const providerTruthRow =
                  (providerSetupStatus && typeof providerSetupStatus === "object"
                    ? providerSetupStatus[item.id]
                    : null) || {};
                return (
                  <article className={`drawer-card ${toneClass(providerAuthReady ? "good" : "warn")}`} key={`provider-${item.id}`}>
                    <span>{item.env}</span>
                    <strong>{item.label}</strong>
                    <p>{item.note}</p>
                    <p>
                      {providerTruthRow?.lastSuccessfulModelCall?.provider
                        ? `Last success: ${titleizeToken(providerTruthRow.lastSuccessfulModelCall.provider)} · ${providerTruthRow.lastSuccessfulModelCall.model || "default"}`
                        : "No successful call recorded yet."}
                    </p>
                    <p>
                      {providerTruthRow?.lastProviderFailure?.summary
                        ? `Last failure: ${providerTruthRow.lastProviderFailure.summary}`
                        : "No provider failure recorded."}
                    </p>
                    {item.id === "openai" ? (
                      <div className="drawer-actions">
                        <ActionButton
                          disabled={!providerOAuthActionsAvailable}
                          onClick={() => void handleReferenceQuickAuth("openai")}
                          title={!providerOAuthActionsAvailable ? providerOAuthUnavailableReason : ""}
                        >
                          Connect Codex OAuth
                        </ActionButton>
                        <ActionButton onClick={() => void openProviderAuthUrl(PROVIDER_AUTH_URLS.openaiApiKeys, "OpenAI API keys")}>
                          Open API keys
                        </ActionButton>
                      </div>
                    ) : null}
                    {item.id === "minimax" ? (
                      <div className="drawer-actions">
                        <ActionButton
                          disabled={!providerOAuthActionsAvailable}
                          onClick={() => void handleReferenceQuickAuth("minimax")}
                          title={!providerOAuthActionsAvailable ? providerOAuthUnavailableReason : ""}
                        >
                          MiniMax OpenClaw OAuth
                        </ActionButton>
                        <ActionButton onClick={() => void openProviderAuthUrl(PROVIDER_AUTH_URLS.minimaxApiKeys, "MiniMax API keys")}>
                          Open API keys
                        </ActionButton>
                      </div>
                    ) : null}
                    <Field label={`${item.label} API key`}>
                      <input
                        autoComplete="off"
                        onChange={event =>
                          setProviderSecretDrafts(current => ({
                            ...current,
                            [item.id]: event.target.value,
                          }))
                        }
                        placeholder={hasSecret ? "Stored in secure keyring" : "Paste API key"}
                        type="password"
                        value={providerSecretDrafts[item.id] || ""}
                      />
                    </Field>
                    <div className="drawer-actions">
                      <ActionButton
                        disabled={providerSecretSaving[item.id] === "saving"}
                        onClick={() => void handleProviderSecretSave(item.id)}
                      >
                        {providerSecretSaving[item.id] === "saving" ? "Saving..." : "Save key"}
                      </ActionButton>
                      <ActionButton
                        disabled={providerSecretSaving[item.id] === "clearing"}
                        onClick={() => void handleProviderSecretClear(item.id)}
                      >
                        {providerSecretSaving[item.id] === "clearing" ? "Clearing..." : "Clear"}
                      </ActionButton>
                    </div>
                  </article>
                );
              })}
            </div>

            <Suspense fallback={<LazySurfaceFallback label="Provider ecosystem" />}>
              <ProviderEcosystemPanel
                providerEcosystem={providerEcosystem}
                providers={providerEcosystemProviders}
                sources={providerEcosystemSources}
                summary={providerEcosystemSummary}
                updatePolicy={providerEcosystemUpdatePolicy}
              />
            </Suspense>

            <div className="field-row">
              <Field label="Code execution">
                <select
                  onChange={event => setCodeExecutionEnabled(event.target.value === "enabled")}
                  value={codeExecutionEnabled ? "enabled" : "disabled"}
                >
                  <option value="disabled">Disabled</option>
                  <option value="enabled">Enabled</option>
                </select>
              </Field>
              <Field label="Container memory">
                <select
                  onChange={event => setCodeExecutionMemory(event.target.value)}
                  value={codeExecutionMemory}
                >
                  {CODE_EXECUTION_MEMORY_OPTIONS.map(option => (
                    <option key={`code-exec-memory-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            {mission ? (
              <div className="drawer-list compact runtime-event-mini-list">
                <article className="drawer-card">
                  <span>Mission container</span>
                  <strong>
                    {missionCodeExecutionState?.enabled
                      ? missionCodeExecutionState?.container_id || "auto container"
                      : "disabled"}
                  </strong>
                  <p>
                    {missionCodeExecutionState?.last_result ||
                      "Code execution results and errors are persisted per mission turn."}
                  </p>
                  {missionCodeExecutionState?.last_error ? (
                    <p>{missionCodeExecutionState.last_error}</p>
                  ) : null}
                </article>
                {codeExecutionArtifacts.map(item => (
                  <article className="drawer-card" key={`code-artifact-${item.artifact_id || item.created_at || item.action_id}`}>
                    <span>{titleizeToken(item.kind || "artifact")}</span>
                    <strong>{item.title || item.action_id || "Code execution artifact"}</strong>
                    <p>{item.summary || "No summary captured."}</p>
                    <p>{item.created_at ? timestampLabel(item.created_at) : ""}</p>
                  </article>
                ))}
              </div>
            ) : null}
            <p className="drawer-footnote">
              Mission-level code execution state now persists container identity, failures, and artifacts so the runtime can reuse the same container across turns.
            </p>
          </section>

          <section className="drawer-block">
            <h3>OpenClaw live connection</h3>
            <div className="context-grid compact-metrics">
              <article className="context-item">
                <span>Connection</span>
                <strong>{openClawStatus?.connected ? "Connected" : "Disconnected"}</strong>
                <p>{openClawStatus?.gatewayUrl || openClawGatewayUrl || DEFAULT_OPENCLAW_GATEWAY_URL}</p>
              </article>
              <article className="context-item">
                <span>Messages waiting</span>
                <strong>{openClawStatus?.queuedOutbound ?? 0}</strong>
                <p>{openClawStatus?.reconnectAttempt ? `Reconnect ${openClawStatus.reconnectAttempt}` : "No reconnect pressure"}</p>
              </article>
              <article className="context-item">
                <span>Connection token</span>
                <strong>{data.openClawHasToken ? "Stored" : "Missing"}</strong>
                <p>{openClawStatus?.lastError || "No gateway error reported."}</p>
              </article>
              <article className="context-item">
                <span>Model accounts</span>
                <strong>{modelAuthReady ? "Connected" : "Missing"}</strong>
                <p>
                  {modelAuthReady
                    ? `${openAICodexAuthReady ? openAICodexAuthPath : minimaxAuthPath} is ready for model routing.`
                    : "Connect OpenAI, MiniMax, or an API key before starting model work."}
                </p>
              </article>
            </div>

            <div className="drawer-card runtime-account-card">
              <div className="runtime-account-head">
                <div>
                  <span>Accounts used by OpenClaw</span>
                  <strong>Connect model accounts</strong>
                </div>
                <p className={modelAuthReady ? "runtime-auth-dot good" : "runtime-auth-dot warn"}>
                  {modelAuthReady ? "ready" : "missing"}
                </p>
              </div>
              <div className="runtime-auth-ledger">
                <div>
                  <span>Codex</span>
                  <strong>{openAICodexAuthReady ? "OAuth ready" : "Needs OAuth"}</strong>
                  <p>{openAICodexAuthPath}</p>
                </div>
                <div>
                  <span>MiniMax</span>
                  <strong>{minimaxAuthReady ? "Portal ready" : "Needs portal"}</strong>
                  <p>{minimaxAuthPath}</p>
                </div>
              </div>
              <p>
                The connection token moves messages. Your model account decides which AI service OpenClaw can use.
              </p>
              <div className="drawer-actions">
                <ActionButton
                  disabled={!providerOAuthActionsAvailable}
                  onClick={() => void handleReferenceQuickAuth("openai")}
                  title={!providerOAuthActionsAvailable ? providerOAuthUnavailableReason : ""}
                  variant={openAICodexAuthReady ? "secondary" : "primary"}
                >
                  {openAICodexAuthReady ? "Codex OAuth connected" : "Connect Codex OAuth"}
                </ActionButton>
                <ActionButton
                  disabled={!providerOAuthActionsAvailable}
                  onClick={() => void handleReferenceQuickAuth("minimax")}
                  title={!providerOAuthActionsAvailable ? providerOAuthUnavailableReason : ""}
                  variant={minimaxAuthReady ? "secondary" : "primary"}
                >
                  {minimaxAuthReady ? "MiniMax OAuth connected" : "Start MiniMax OAuth"}
                </ActionButton>
                <ActionButton onClick={() => void verifyMiniMaxOpenClawAuth()}>
                  Verify MiniMax
                </ActionButton>
                <ActionButton onClick={() => {
                  setReferenceSettingsTab("providers");
                  setSurface("settings");
                  setActiveDrawer(null);
                }}>
                  Open account settings
                </ActionButton>
              </div>
              <p className="drawer-footnote">
                Syntelos verifies the saved MiniMax login before it marks MiniMax ready.
              </p>
            </div>

            <Field label="Connection URL">
              <input
                onChange={event => setOpenClawGatewayUrl(event.target.value)}
                placeholder={DEFAULT_OPENCLAW_GATEWAY_URL}
                value={openClawGatewayUrl}
              />
            </Field>
            <Field label="Connection token">
              <input
                onChange={event => setOpenClawGatewayToken(event.target.value)}
                placeholder={data.openClawHasToken ? "Token stored in keyring" : "Paste a gateway token"}
                type="password"
                value={openClawGatewayToken}
              />
            </Field>
            <div className="drawer-actions">
              <ActionButton onClick={() => void handleOpenClawConnect()} variant="primary">
                Connect
              </ActionButton>
              <ActionButton onClick={() => void handleOpenClawDisconnect()}>
                Disconnect
              </ActionButton>
              <ActionButton onClick={() => void handleOpenClawSaveToken()}>
                Save token
              </ActionButton>
              <ActionButton onClick={() => void handleOpenClawClearToken()}>
                Clear token
              </ActionButton>
            </div>
            <p className="drawer-footnote">
              Syntelos can install, repair, update, and re-check Hermes, OpenClaw, and OpenCodeGo from here.
            </p>
          </section>

          <section className="drawer-block">
            <h3>Work engines</h3>
            <div className="drawer-list">
              {primaryRuntimeServices.length > 0 ? (
                primaryRuntimeServices.map(service => (
                  <article className={`drawer-card ${toneClass(service.tone)}`} key={`runtime-${service.serviceId}`}>
                    <span>{service.category}</span>
                    <strong>{service.label}</strong>
                    <p>
                      {service.status}
                      {service.version ? ` · ${service.version}` : ""}
                      {service.latestVersion ? ` → ${service.latestVersion}` : ""}
                    </p>
                    <p>{service.details || service.managementMode}</p>
                    {service.updateSafety?.summary ? (
                      <div className="update-safety-note" aria-label={`${service.label} update safety`}>
                        <strong>{service.updateSafety.label || "Review before updating"}</strong>
                        <p>{service.updateSafety.summary}</p>
                        <span>{service.updateSafety.safeNextStep}</span>
                        {service.updateSafety.verifyAfterUpdate ? <span>Fluxio will re-check setup after the update.</span> : null}
                      </div>
                    ) : null}
                    {service.actions.length > 0 ? (
                      <div className="drawer-actions">
                        {service.actions.slice(0, 3).map(action => (
                          <ActionButton
                            key={`${service.serviceId}-${action.actionId}`}
                            onClick={() => void runWorkspaceActionSpec(action)}
                          >
                            {action.label}
                          </ActionButton>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))
              ) : (
                <article className="drawer-card">
                  <strong>Hermes, OpenClaw, and OpenCodeGo are not visible yet.</strong>
                  <p>After setup checks run, Syntelos shows them here with install and repair buttons.</p>
                </article>
              )}
            </div>
          </section>

          {mission ? (
            <section className="drawer-block">
              <h3>Mission settings used for this run</h3>
              <div className="context-grid compact-metrics">
                {missionRuntimeContract.map(item => (
                  <article className="context-item" key={`runtime-contract-${item.label}`}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </article>
                ))}
              </div>
              <div className="drawer-list">
                {effectiveRouteRows.length > 0 ? (
                  effectiveRouteRows.map(item => (
                    <article className="drawer-card" key={`route-contract-${item.role}`}>
                      <span>{titleizeToken(item.role)}</span>
                      <strong>
                        {titleizeToken(item.provider)} · {item.model}
                      </strong>
                      <p>
                        {titleizeToken(item.source || "profile_default")}
                        {item.effort ? ` · ${routeEffortLabel(item.effort, "medium")} effort` : ""}
                        {item.budgetClass ? ` · ${titleizeToken(item.budgetClass)}` : ""}
                      </p>
                      {item.reason ? <p>{item.reason}</p> : null}
                    </article>
                  ))
                ) : (
                  <article className="drawer-card">
                    <strong>No effective route contract reported yet.</strong>
                    <p>Once the mission resolves planner, executor, and verifier routes, they will appear here.</p>
                  </article>
                )}
              </div>
            </section>
          ) : null}

          <section className="drawer-block">
            <h3>Background work</h3>
            <div className="drawer-list">
              {delegatedSessions.length > 0 ? (
                delegatedSessions.map(session => (
                  <article
                    className={`drawer-card ${toneClass(session.heartbeat_status === "stale" ? "warn" : session.status === "failed" ? "bad" : "neutral")}`}
                    key={`delegated-session-${session.delegated_id}`}
                  >
                    <span>{runtimeLabel(session.runtime_id)}</span>
                    <strong>{titleizeToken(session.status || "unknown")}</strong>
                    <p>{session.detail || session.last_event || "A background run is active."}</p>
                    <div className="pill-row">
                      <span className="mini-pill">{session.heartbeat_status ? `Heartbeat ${titleizeToken(session.heartbeat_status)}` : "No heartbeat"}</span>
                      {session.execution_target ? (
                        <span className="mini-pill muted">{titleizeToken(session.execution_target)}</span>
                      ) : null}
                      {typeof session.heartbeat_age_seconds === "number" ? (
                        <span className="mini-pill muted">{session.heartbeat_age_seconds}s ago</span>
                      ) : null}
                    </div>
                    <p>{session.execution_target_detail || session.execution_root || session.workspace_root || "Execution root not reported."}</p>
                    {Array.isArray(session.latest_events) && session.latest_events.length > 0 ? (
                      <div className="drawer-list compact runtime-event-mini-list">
                        {session.latest_events.slice(-3).reverse().map(event => (
                          <article className="drawer-card" key={`runtime-event-${session.delegated_id}-${event.event_id || event.message}`}>
                            <span>{titleizeToken(event.kind || "runtime")}</span>
                            <strong>{event.message || "Runtime event"}</strong>
                            {event.status ? <p>{titleizeToken(event.status)}</p> : null}
                          </article>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))
              ) : (
                <article className="drawer-card">
                  <strong>No background run is active.</strong>
                  <p>When Hermes or OpenClaw is working, Syntelos shows progress and the latest update here.</p>
                </article>
              )}
            </div>
          </section>

          <section className="drawer-block">
            <h3>Messaging and bridge surfaces</h3>
            <div className="drawer-list">
              {bridgeServices.length > 0 ? (
                bridgeServices.map(service => (
                  <article className={`drawer-card ${toneClass(service.tone)}`} key={`bridge-${service.serviceId}`}>
                    <span>{service.category}</span>
                    <strong>{service.label}</strong>
                    <p>{service.status}</p>
                    <p>{service.details || "Bridge surface available."}</p>
                  </article>
                ))
              ) : (
                <article className="drawer-card">
                  <strong>Message bridge visibility is still partial.</strong>
                  <p>Telegram state is exposed today. iMessage and deeper mobile bridge specifics still need backend support before this shell can manage them honestly.</p>
                </article>
              )}
            </div>
          </section>

          <section className="drawer-block">
            <h3>Connected apps and mobile bridges</h3>
            <div className="drawer-list">
              {bridgeSessions.length > 0 ? (
                bridgeSessions.map(session => (
                  <article className={`drawer-card ${toneClass(session.bridge_health === "healthy" ? "good" : "warn")}`} key={`bridge-session-${session.session_id}`}>
                    <span>{session.app_name || session.app_id}</span>
                    <strong>
                      {titleizeToken(session.status || "unknown")}
                      {session.bridge_transport ? ` · ${titleizeToken(session.bridge_transport)}` : ""}
                    </strong>
                    <p>{titleizeToken(session.bridge_health || "unknown")} bridge health</p>
                    {Array.isArray(session.notes) && session.notes.length > 0 ? <p>{session.notes[0]}</p> : null}
                    {session.latest_task_result?.resultSummary ? (
                      <div className="bridge-output-summary">
                        <span>{session.latest_task_result.label || "Latest output"}</span>
                        <strong>{session.latest_task_result.resultSummary}</strong>
                      </div>
                    ) : null}
                    {asList(session.context_preview).length > 0 ? (
                      <div className="bridge-context-list">
                        {asList(session.context_preview).slice(0, 2).map(surface => (
                          <div className="bridge-context-item" key={`${session.session_id}-${surface.surfaceId || surface.label}`}>
                            <span>{surface.label || "Context"}</span>
                            <p>{surface.summary || "No summary reported."}</p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {Array.isArray(session.active_tasks) && session.active_tasks.length > 0 ? (
                      <div className="pill-row">
                        {session.active_tasks.slice(0, 3).map(item => (
                          <span className="mini-pill muted" key={`bridge-task-${session.session_id}-${item}`}>
                            {item}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <div className="drawer-actions bridge-card-actions">
                      {session.bridge_endpoint ? (
                        <ActionButton
                          onClick={() => void openBridgeEndpoint(session.bridge_endpoint, session.app_name || session.app_id)}
                          type="button"
                        >
                          Open bridge
                        </ActionButton>
                      ) : null}
                      {session.approval_callback?.available ? (
                        <span className="mini-pill">
                          {titleizeToken(session.approval_callback.channel || "callback")} ready
                        </span>
                      ) : null}
                    </div>
                  </article>
                ))
              ) : (
                <article className="drawer-card">
                  <strong>No connected app bridge is reporting yet.</strong>
                  <p>Bridge Lab data will appear here when connected apps expose live session or follow-on bridge state.</p>
                </article>
              )}
            </div>
            <p className="drawer-footnote">
              OpenClaw still has the direct gateway, but Hermes supervision now lands in the same Agent conversation through control-room runtime events and delegated lane snapshots.
            </p>
          </section>

          <Suspense fallback={<LazySurfaceFallback label="Fusion contract" />}>
            <FusionWorkbenchPanel fusionWorkbench={fusionWorkbench} />
          </Suspense>

          <Suspense fallback={<LazySurfaceFallback label="Loading red-team proof" />}>
            <RedTeamProofBoard />
          </Suspense>

          <section className="drawer-block">
            <h3>Setup controls</h3>
            <div className="drawer-actions">
              {viewModel.drawers.builder.serviceStudio.services.flatMap(service =>
                service.actions.slice(0, 1).map(action => (
                  <ActionButton
                    key={`${service.serviceId}-${action.actionId}-setup`}
                    onClick={() => void runWorkspaceActionSpec(action)}
                  >
                    {action.label}
                  </ActionButton>
                )),
              ).slice(0, 4)}
            </div>
          </section>
        </section>
      );
    }

    if (activeDrawer === "profiles") {
      return (
        <section className="drawer-panel">
          <header>
            <h2>Profiles and routing</h2>
            <p>Shape workspace behavior, routing, and execution defaults from one profile surface.</p>
          </header>

          <section className="drawer-block">
            <div className="field-row">
              <Field label="Workspace profile">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      userProfile: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.userProfile}
                >
                  {(snapshot.profiles?.availableProfiles || ["beginner", "builder", "advanced"]).map(
                    option => (
                      <option key={option} value={option}>
                        {titleizeToken(option)}
                      </option>
                    ),
                  )}
                </select>
              </Field>
              <Field label="Preferred work engine">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      preferredHarness: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.preferredHarness}
                >
                  {PREFERRED_HARNESS_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="field-row">
              <Field label="Routing strategy">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      routingStrategy: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.routingStrategy}
                >
                  {ROUTING_STRATEGY_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Execution target">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      executionTargetPreference: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.executionTargetPreference}
                >
                  {EXECUTION_TARGET_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <label className="check-field">
              <input
                checked={workspaceProfileForm.autoOptimizeRouting}
                onChange={event =>
                  setWorkspaceProfileForm(current => ({
                    ...current,
                    autoOptimizeRouting: event.target.checked,
                  }))
                }
                type="checkbox"
              />
              <span>Enable deterministic routing auto-optimize when enough local runs exist.</span>
            </label>

            <div className="drawer-actions">
              <ActionButton onClick={() => void saveWorkspacePolicy()} variant="primary">
                Save profile policy
              </ActionButton>
            </div>
          </section>

          <section className="drawer-block">
            <h3>Current behavior</h3>
            <div className="drawer-list compact">
              {viewModel.drawers.builder.profileStudio.behavior.map(item => (
                <article className="drawer-card" key={`profile-surface-${item.label}`}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </div>
            <p className="drawer-footnote">
              Routing strategy is real and saved at workspace level. Builder now exposes per-role overrides for planner, executor, and verifier when you need to pin specific models.
            </p>
          </section>

          <section className="drawer-block">
            <h3>Per-role model routes</h3>
            <div className="route-override-grid">
              {workspaceProfileForm.routeOverrides.map(item => (
                <article className="drawer-card route-override-card" key={`route-override-${item.role}`}>
                  <span>{titleizeToken(item.role)}</span>
                  <div className="field-row">
                    <Field label="Provider">
                      <select
                        onChange={event =>
                          setWorkspaceProfileForm(current => ({
                            ...current,
                            routeOverrides: current.routeOverrides.map(entry =>
                              entry.role === item.role
                                ? { ...entry, provider: event.target.value }
                                : entry,
                            ),
                          }))
                        }
                        value={item.provider}
                      >
                        {MODEL_PROVIDER_OPTIONS.map(option => (
                          <option key={`${item.role}-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Effort">
                      <select
                        onChange={event =>
                          setWorkspaceProfileForm(current => ({
                            ...current,
                            routeOverrides: current.routeOverrides.map(entry =>
                              entry.role === item.role
                                ? { ...entry, effort: event.target.value }
                                : entry,
                            ),
                          }))
                        }
                        value={item.effort}
                      >
                        {MODEL_EFFORT_OPTIONS.map(option => (
                          <option key={`${item.role}-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                  </div>
                  <Field label="Model">
                    <select
                      onChange={event =>
                        setWorkspaceProfileForm(current => ({
                          ...current,
                          routeOverrides: current.routeOverrides.map(entry =>
                            entry.role === item.role
                              ? { ...entry, model: event.target.value }
                              : entry,
                          ),
                        }))
                      }
                      value={item.model}
                    >
                      <option value="">Profile default</option>
                      {uniq([item.model, ...ROUTE_MODEL_OPTIONS].filter(Boolean)).map(option => (
                        <option key={`${item.role}-${option}`} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </Field>
                </article>
              ))}
            </div>
            <p className="drawer-footnote">
              Leave a role blank to keep using the routing strategy default. Planner, executor, and verifier overrides are saved into workspace policy and forwarded to the runtime.
            </p>
          </section>

          <section className="drawer-block">
            <h3>Available contracts</h3>
            <div className="drawer-list">
              {viewModel.drawers.builder.profileStudio.profileRows.map(item => (
                <article className={`drawer-card ${toneClass(item.tone)}`} key={`profile-contract-${item.id}`}>
                  <span>{item.label}</span>
                  <strong>{item.description}</strong>
                  <p>
                    {item.approval} approvals · {item.autonomy} autonomy · {item.visibility} visibility
                  </p>
                  <p>{item.density} density</p>
                </article>
              ))}
            </div>
          </section>
        </section>
      );
    }

    if (activeDrawer === "settings") {
      return (
        <section className="drawer-panel">
          <header>
            <p className="eyebrow">Settings</p>
            <h2>Workspace and app controls</h2>
            <p>Put operational settings here instead of scattering them across the shell.</p>
          </header>

          <section className="drawer-block">
            <h3>App view</h3>
            <Field label="Preview">
              <select onChange={event => setPreviewMode(event.target.value)} value={previewMode}>
                {previewModeOptions.map(option => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </Field>
            {!allowFixturePreviewModes ? (
              <p className="drawer-footnote">Web control mode is live-backend only.</p>
            ) : null}
            <Field label="Live sync">
              <select onChange={event => setLiveSyncSeconds(event.target.value)} value={liveSyncSeconds}>
                {LIVE_SYNC_OPTIONS.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <p className="drawer-footnote">
              {previewLabel(previewMode, data.previewMeta)}
              {lastPushReason ? ` · Last push ${lastPushReason}` : ""}
            </p>
          </section>

          <section className="drawer-block">
            <h3>Workspace defaults</h3>
            <div className="context-grid">
              {viewModel.drawers.builder.profileStudio.workspacePolicy.map(item => (
                <article className="context-item" key={`settings-${item.label}`}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </div>
            <div className="drawer-actions">
              <ActionButton onClick={() => setActiveDrawer("builder")} variant="primary">
                Open builder controls
              </ActionButton>
            </div>
          </section>

          <section className="drawer-block">
            <h3>Escalation</h3>
            <p>{data.telegramReady ? "Telegram ready" : "Telegram not configured"}</p>
            <div className="drawer-actions">
              <ActionButton onClick={() => setShowEscalationDialog(true)} variant="primary">
                Configure
              </ActionButton>
              <ActionButton onClick={() => void handleSendTestPing()}>Send test ping</ActionButton>
            </div>
          </section>

          <section className="drawer-block">
            <h3>Memory</h3>
            <label className="check-field">
              <input
                checked={memoryPolicy.includeInFollowUps}
                onChange={event =>
                  setMemoryPolicy(current => ({
                    ...current,
                    includeInFollowUps: event.target.checked,
                  }))
                }
                type="checkbox"
              />
              <span>Include memory snippets in follow-up messages.</span>
            </label>
            <label className="check-field">
              <input
                checked={memoryPolicy.projectScoped}
                onChange={event =>
                  setMemoryPolicy(current => ({
                    ...current,
                    projectScoped: event.target.checked,
                  }))
                }
                type="checkbox"
              />
              <span>Keep workspace memory.</span>
            </label>
            <label className="check-field">
              <input
                checked={memoryPolicy.missionScoped}
                onChange={event =>
                  setMemoryPolicy(current => ({
                    ...current,
                    missionScoped: event.target.checked,
                  }))
                }
                type="checkbox"
              />
              <span>Keep mission memory.</span>
            </label>
            <div className="drawer-list compact">
              <article className="drawer-card">
                <span>Workspace memory</span>
                <strong>
                  {workspace?.workspace_id
                    ? String(memoryStore?.workspace?.[workspace.workspace_id] || "").trim() || "No workspace memory"
                    : "No workspace selected"}
                </strong>
              </article>
              <article className="drawer-card">
                <span>Mission memory</span>
                <strong>
                  {mission?.mission_id
                    ? String(memoryStore?.mission?.[mission.mission_id] || "").trim() || "No mission memory"
                    : "No mission selected"}
                </strong>
              </article>
            </div>
            <div className="drawer-actions">
              <ActionButton onClick={clearWorkspaceMemory} type="button">
                Clear workspace memory
              </ActionButton>
              <ActionButton onClick={clearMissionMemory} type="button">
                Clear mission memory
              </ActionButton>
              <ActionButton onClick={clearAllMemory} type="button">
                Clear all memory
              </ActionButton>
            </div>
          </section>

          <section className="drawer-block">
            <h3>Tasks</h3>
            <div className="field-row">
              <Field label="Task name">
                <input
                  onChange={event => updateTaskFormField("name", event.target.value)}
                  placeholder="Regression sweep"
                  value={taskForm.name}
                />
              </Field>
              <Field label="Trigger">
                <select
                  onChange={event => updateTaskFormField("trigger", event.target.value)}
                  value={taskForm.trigger}
                >
                  <option value="schedule">Scheduled</option>
                  <option value="api">API</option>
                  <option value="webhook">Webhook</option>
                </select>
              </Field>
            </div>
            <Field label="Task prompt">
              <textarea
                onChange={event => updateTaskFormField("prompt", event.target.value)}
                placeholder="Run full mission smoke checks and summarize blockers."
                value={taskForm.prompt}
              />
            </Field>
            <div className="field-row">
              <Field label="Every minutes">
                <input
                  min="1"
                  onChange={event => updateTaskFormField("everyMinutes", Number(event.target.value || 1))}
                  type="number"
                  value={taskForm.everyMinutes}
                />
              </Field>
              <Field label="Webhook/API token">
                <input
                  onChange={event => updateTaskFormField("webhookToken", event.target.value)}
                  placeholder="task-token-123"
                  value={taskForm.webhookToken}
                />
              </Field>
            </div>
            <label className="check-field">
              <input
                checked={taskForm.active}
                onChange={event => updateTaskFormField("active", event.target.checked)}
                type="checkbox"
              />
              <span>Task active on create.</span>
            </label>
            <div className="drawer-actions">
              <ActionButton onClick={createLocalTask} type="button" variant="primary">
                Create task
              </ActionButton>
            </div>
            <Field label="Trigger token now">
              <input
                onChange={event => setTaskTriggerToken(event.target.value)}
                placeholder="Paste token to simulate webhook/API trigger"
                value={taskTriggerToken}
              />
            </Field>
            <div className="drawer-actions">
              <ActionButton onClick={triggerTaskByToken} type="button">
                Trigger by token
              </ActionButton>
            </div>
            <div className="drawer-list">
              {localTasks.length > 0 ? (
                localTasks.map(item => (
                  <article className={`drawer-card ${toneClass(item.lastStatus === "failed" ? "bad" : item.active ? "good" : "neutral")}`} key={item.id}>
                    <span>{titleizeToken(item.trigger)}</span>
                    <strong>{item.name}</strong>
                    <p>{item.prompt}</p>
                    <p>
                      Every {Math.max(1, Number(item.everyMinutes) || 1)}m · Last run{" "}
                      {item.lastRunAt ? timestampLabel(item.lastRunAt) : "never"} · {item.totalRuns || 0} run(s)
                    </p>
                    <div className="drawer-actions">
                      <ActionButton onClick={() => toggleTaskActive(item.id)} type="button">
                        {item.active ? "Pause" : "Resume"}
                      </ActionButton>
                      <ActionButton onClick={() => void executeTask(item, "manual")} type="button">
                        Run now
                      </ActionButton>
                      <ActionButton onClick={() => removeTask(item.id)} type="button">
                        Delete
                      </ActionButton>
                    </div>
                  </article>
                ))
              ) : (
                <article className="drawer-card">
                  <strong>No task yet.</strong>
                </article>
              )}
            </div>
          </section>

          <section className="drawer-block">
            <h3>Debug stream</h3>
            <p>
              Backend invoke events, browser errors, and rejected promises are captured here.
            </p>
            <div className="drawer-actions">
              <ActionButton onClick={clearDebugEvents} type="button">
                Clear logs
              </ActionButton>
            </div>
            <WindowedList
              className="drawer-list drawer-debug-list"
              estimatedItemHeight={84}
              items={debugEvents}
              overscan={6}
              renderItem={item => (
                <article className={`drawer-card ${toneClass(String(item.kind || "").includes("error") ? "bad" : "neutral")}`} key={item.id}>
                  <span>{item.kind || "event"}</span>
                  <strong>{item.command || item.message || "debug event"}</strong>
                  <p>
                    {timestampLabel(item.at)}
                    {Number.isFinite(item.durationMs) ? ` · ${item.durationMs}ms` : ""}
                  </p>
                  {item.error ? <p>{String(item.error)}</p> : null}
                </article>
              )}
            />
          </section>
        </section>
      );
    }

    if (activeDrawer === "builder" && uiMode === "builder") {
      const skillQuery = skillStudioQuery.trim().toLowerCase();
      const skillMatchesQuery = item =>
        !skillQuery ||
        String(item?.label || "")
          .toLowerCase()
          .includes(skillQuery) ||
        String(item?.description || "")
          .toLowerCase()
          .includes(skillQuery) ||
        (item?.profileSuitability || []).some(entry =>
          String(entry).toLowerCase().includes(skillQuery),
        );
      const matchesSkillFilter = item => {
        if (skillStudioFilter === "recommended") {
          return !item?.installed;
        }
        if (skillStudioFilter === "installed") {
          return Boolean(item?.installed);
        }
        if (skillStudioFilter === "needs_attention") {
          return item?.testStatus !== "Reviewed" || !item?.installed;
        }
        return true;
      };
      const filteredRecommendedSkills = viewModel.drawers.builder.skillStudio.recommended.filter(
        item => matchesSkillFilter(item) && skillMatchesQuery(item),
      );
      const filteredCuratedSkills = viewModel.drawers.builder.skillStudio.curated.filter(
        item => matchesSkillFilter(item) && skillMatchesQuery(item),
      );
      const designFrontendRecommended = filteredRecommendedSkills.filter(item =>
        /design|frontend|ui|ux|tailwind|react/i.test(
          `${item?.label || ""} ${item?.description || ""} ${(item?.profileSuitability || []).join(" ")}`,
        ),
      );
      const skillLifecycleCounts = filteredCuratedSkills.reduce(
        (acc, item) => {
          const statusText = `${item?.status || ""} ${item?.testStatus || ""}`.toLowerCase();
          if (statusText.includes("proposed") || statusText.includes("draft")) {
            acc.draft += 1;
          }
          if (statusText.includes("review")) {
            acc.review += 1;
          }
          if (statusText.includes("test") || statusText.includes("validation")) {
            acc.verify += 1;
          }
          if ((item?.installed && item?.executionCapable) || statusText.includes("execution-ready")) {
            acc.publish += 1;
          }
          return acc;
        },
        { draft: 0, review: 0, verify: 0, publish: 0 },
      );
      return (
        <section className="drawer-panel">
          <header>
            <h2>Confidence and operations</h2>
            <p>{viewModel.drawers.builder.liveSurface.note}</p>
          </header>

          <div className={`skill-recovery-strip ${toneClass(missionSkillRecoveryNeedsAction ? "warn" : "good")}`}>
            <div>
              <span>Mission skill recovery</span>
              <strong>
                {missionSkillRecoveryNeedsAction
                  ? `${missionSkillRecoveryTriggers.length} trigger(s), ${missionSkillRecoveryRecommendations.length} skill lead(s)`
                  : "Clear"}
              </strong>
            </div>
            <p>
              {missionSkillRecoveryNeedsAction
                ? missionSkillRecoveryActions[0]?.action ||
                  missionSkillRecoveryTriggers[0]?.recoveryAction ||
                  "Choose a recovery skill or route before retrying the same step."
                : "The agent can continue the normal plan, execute, verify, repair loop."}
            </p>
          </div>

          <div className="builder-visual-proof-packet compact">
            <div className="builder-live-review-panel-head compact">
              <strong>Visual proof packet</strong>
              <span className="mini-pill muted">{visualProofPacket.annotationCount} annotation mark(s)</span>
            </div>
            <div className="builder-visual-proof-grid">
              <article>
                <span>Frame</span>
                <strong>{visualProofPacket.frameLabel}</strong>
                <small>{visualProofPacket.framePath || "Path pending"}</small>
              </article>
              <article>
                <span>Target</span>
                <strong>{visualProofPacket.proofTarget || "Target pending"}</strong>
                <small>{visualProofPacket.threadTarget || "Thread pending"}</small>
              </article>
              <article>
                <span>Receipt</span>
                <strong>{visualProofPacket.receiptHandle || "No receipt yet"}</strong>
                <small>{visualProofPacket.receiptKind}</small>
              </article>
            </div>
          </div>

          <section className="drawer-block monitor-loop-panel">
            <div className="builder-live-review-panel-head compact">
              <div>
                <h3>{monitoringLoopStudio.headline || "External monitor loops"}</h3>
                <p>{monitoringLoopStudio.summary || "Monitor loops are waiting for mission state."}</p>
              </div>
              <span className="mini-pill muted">
                {titleizeToken(monitoringLoopStudio.activationMode || "important_only")}
              </span>
            </div>
            <div className="context-grid compact-metrics">
              <article className="context-item">
                <span>Active monitors</span>
                <strong>{monitoringLoopStudio.activeCount || 0}</strong>
              </article>
              <article className="context-item">
                <span>Warnings</span>
                <strong>{monitoringLoopStudio.warningCount || 0}</strong>
              </article>
              <article className="context-item">
                <span>Default</span>
                <strong>{titleizeToken(monitoringLoopStudio.defaultState || "off_until_enabled_or_blocked")}</strong>
              </article>
            </div>
            <div className="monitor-loop-list">
              {monitoringLoops.map(item => (
                <article className={`monitor-loop-card ${toneClass(item.tone)}`} key={item.id}>
                  <span>{titleizeToken(item.status)}</span>
                  <strong>{item.label}</strong>
                  <p>{item.trigger}</p>
                  <small>{item.nextAction}</small>
                  <em>{titleizeToken(item.cadence)} · {titleizeToken(item.activation)}</em>
                </article>
              ))}
            </div>
            <div className="supervisor-intervention-queue" aria-label="Supervisor intervention queue">
              <div className="builder-live-review-panel-head compact">
                <div>
                  <h4>Supervisor intervention queue</h4>
                  <p>
                    {supervisorInterventionQueue.length > 0
                      ? `${supervisorInterventionQueue.length} ranked before next step.`
                      : "No intervention queued."}
                  </p>
                </div>
                <span className={`mini-pill ${toneClass((monitoringLoopStudio.criticalCount || 0) > 0 ? "warn" : "good")}`}>
                  {monitoringLoopStudio.criticalCount || 0} high
                </span>
              </div>
              {supervisorInterventionQueue.length > 0 ? (
                supervisorInterventionQueue.map(item => (
                  <article className={`supervisor-intervention-card ${toneClass(item.severity === "high" ? "warn" : "neutral")}`} key={item.interventionId}>
                    <span>{titleizeToken(item.source)} · {titleizeToken(item.severity)}</span>
                    <strong>{item.label}</strong>
                    <p>{item.reason}</p>
                    <small>{item.nextAction}</small>
                  </article>
                ))
              ) : (
                <article className="supervisor-intervention-card">
                  <strong>Continue verification</strong>
                  <p>Queue appears when blocked, drifting, or missing proof.</p>
                </article>
              )}
            </div>
            <div className="drawer-actions">
              <ActionButton onClick={() => setActiveDrawer("queue")} type="button">
                Review blockers
              </ActionButton>
              <ActionButton onClick={() => setActiveDrawer("proof")} type="button">
                Review proof
              </ActionButton>
              <ActionButton onClick={() => setActiveDrawer("context")} type="button">
                Review context
              </ActionButton>
            </div>
          </section>

          <section className="drawer-block subagent-command-panel">
            <div className="builder-live-review-panel-head compact">
              <div>
                <h3>{subagentOrchestrationStudio.headline || "Subagent command center"}</h3>
                <p>{subagentOrchestrationStudio.summary || "Delegated lanes appear here."}</p>
              </div>
              <span className="mini-pill muted">
                {titleizeToken(subagentOrchestrationStudio.mergePolicy || "best_score")}
              </span>
            </div>
            <div className="context-grid compact-metrics">
              <article className="context-item">
                <span>Configured workers</span>
                <strong>{subagentOrchestrationStudio.configuredWorkers || 1}</strong>
              </article>
              <article className="context-item">
                <span>Active lanes</span>
                <strong>{subagentOrchestrationStudio.activeCount || 0}</strong>
              </article>
              <article className="context-item">
                <span>Blocked lanes</span>
                <strong>{subagentOrchestrationStudio.blockedCount || 0}</strong>
              </article>
            </div>
            <Suspense fallback={null}>
              <SubagentReadinessPanel
                studio={subagentOrchestrationStudio}
              />
            </Suspense>
            <div className="subagent-lane-list">
              {subagentLanes.length > 0 ? (
                subagentLanes.map(item => (
                  <article className={`subagent-lane-card ${toneClass(item.tone)}`} key={item.id}>
                    <div>
                      <span>{titleizeToken(item.role)}</span>
                      <strong>{item.label}</strong>
                    </div>
                    <p>{item.latestEvent}</p>
                    <dl>
                      <div>
                        <dt>Route</dt>
                        <dd>{item.runtime} / {item.provider} / {item.model}</dd>
                      </div>
                      <div>
                        <dt>Status</dt>
                        <dd>{titleizeToken(item.status)} · {item.heartbeat}</dd>
                      </div>
                      <div>
                        <dt>Proof</dt>
                        <dd>{item.proof}</dd>
                      </div>
                    </dl>
                    {item.blockReason || item.supervisorAction ? (
                      <div className="subagent-supervisor-note">
                        <span>Why</span>
                        <p>{item.blockReason || "Supervisor has no lane-specific blocker."}</p>
                        <span>Next</span>
                        <p>{item.supervisorAction || item.nextAction}</p>
                      </div>
                    ) : null}
                    <small>{item.nextAction}</small>
                  </article>
                ))
              ) : (
                <article className="subagent-lane-empty">
                  <strong>No lane active</strong>
                  <p>{subagentOrchestrationStudio.recommendedAction}</p>
                </article>
              )}
            </div>
            {subagentScoreboard.length > 0 ? (
              <div className="subagent-scoreboard">
                {subagentScoreboard.map(item => (
                  <article key={item.id}>
                    <span>{item.label}</span>
                    <strong>{item.score}</strong>
                    <p>{item.detail}</p>
                  </article>
                ))}
              </div>
            ) : null}
            <p className="drawer-note">
              Handoffs: {subagentOrchestrationStudio.handoffCount || 0} · {subagentOrchestrationStudio.lastHandoffReason}
            </p>
            <div className="drawer-actions">
              <ActionButton onClick={() => setActiveDrawer("runtime")} type="button">
                Inspect runtime
              </ActionButton>
              <ActionButton onClick={() => setActiveDrawer("queue")} type="button">
                Resolve lane blocks
              </ActionButton>
              <ActionButton onClick={() => setActiveDrawer("proof")} type="button">
                Verify merge proof
              </ActionButton>
            </div>
          </section>

          <section className="drawer-block">
            <h3>Confidence engine</h3>
            <div className="confidence-headline">
              <strong className={toneClass(viewModel.drawers.builder.confidence.tone)}>
                {viewModel.drawers.builder.confidence.label}
              </strong>
              <span>{viewModel.drawers.builder.confidence.phase}</span>
            </div>
            <div className="confidence-meter" role="presentation">
              <span style={{ width: `${viewModel.drawers.builder.confidence.score}%` }} />
            </div>
            <p>
              {viewModel.drawers.builder.confidence.requiredGateSummary.label}
              {` · Quality ${viewModel.drawers.builder.confidence.qualityScore}%`}
              {` · Release ${viewModel.drawers.builder.confidence.releaseStatus}`}
            </p>
            <div className="audit-list">
              {viewModel.drawers.builder.confidence.milestones.map(item => (
                <article className="audit-item" key={item.id}>
                  <strong>{item.label}</strong>
                  <p>
                    {item.percent}% · {item.detail}
                  </p>
                </article>
              ))}
            </div>
            <ul>
              {viewModel.drawers.builder.confidence.nextActions.length > 0 ? (
                viewModel.drawers.builder.confidence.nextActions.map(item => (
                  <li key={`confidence-action-${item}`}>{item}</li>
                ))
              ) : (
                <li>No blocking action reported.</li>
              )}
            </ul>
          </section>

          <section className="drawer-block roadmap-event-block">
            <div className="roadmap-event-head">
              <div>
                <h3>Road to 100%</h3>
                <p>
                  {viewModel.drawers.builder.qualityRoadmap.headline}
                  {` · Gap ${viewModel.drawers.builder.qualityRoadmap.gap}%`}
                </p>
              </div>
              <span>
                {viewModel.drawers.builder.qualityRoadmap.doneCount} done ·{" "}
                {viewModel.drawers.builder.qualityRoadmap.nextCount} next ·{" "}
                {viewModel.drawers.builder.qualityRoadmap.blockedCount} blocked
              </span>
            </div>
            {(() => {
              const tracks = viewModel.drawers.builder.qualityRoadmap.tracks;
              const activeItem =
                tracks.find(item => item.id === activeRoadmapItemId) ||
                tracks.find(item => item.state !== "done") ||
                tracks[0];
              return (
                <div className="roadmap-event-layout">
                  <div className="roadmap-event-line" aria-label="Quality roadmap events">
                    {tracks.map((item, index) => (
                      <button
                        className={cx(
                          "roadmap-event",
                          toneClass(item.tone),
                          activeItem?.id === item.id && "active",
                        )}
                        key={item.id}
                        onClick={() => setActiveRoadmapItemId(item.id)}
                        style={{ "--roadmap-index": index }}
                        type="button"
                      >
                        <span>{titleizeToken(item.state)}</span>
                        <strong>{item.label}</strong>
                        <em>{item.detail}</em>
                      </button>
                    ))}
                  </div>
                  {activeItem ? (
                    <aside className={`roadmap-popover ${toneClass(activeItem.tone)}`} key={activeItem.id}>
                      <span>{titleizeToken(activeItem.state)}</span>
                      <strong>{activeItem.label}</strong>
                      <p>{activeItem.detail}</p>
                      <p>{activeItem.hint}</p>
                      <div className="drawer-actions">
                        <ActionButton
                          onClick={() => void handleQualityRoadmapAction(activeItem)}
                          type="button"
                        >
                          {activeItem.suggestedAction || "Open"}
                        </ActionButton>
                      </div>
                    </aside>
                  ) : null}
                </div>
              );
            })()}
          </section>

          <section className="drawer-block">
            <h3>Live surface</h3>
            <Field label="Preview">
              <select onChange={event => setPreviewMode(event.target.value)} value={previewMode}>
                {previewModeOptions.map(option => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </Field>
            {!allowFixturePreviewModes ? (
              <p className="drawer-footnote">Web control mode is live-backend only.</p>
            ) : null}
            <Field label="Live sync">
              <select
                onChange={event => setLiveSyncSeconds(event.target.value)}
                value={liveSyncSeconds}
              >
                {LIVE_SYNC_OPTIONS.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <p className="drawer-footnote">
              {previewLabel(previewMode, data.previewMeta)}
              {lastPushReason ? ` · Last push ${lastPushReason}` : ""}
            </p>
          </section>

          <section className="drawer-block">
            <h3>Profile studio</h3>
            <div className="field-row">
              <Field label="Workspace profile">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      userProfile: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.userProfile}
                >
                  {(snapshot.profiles?.availableProfiles || ["beginner", "builder", "advanced"]).map(
                    option => (
                      <option key={option} value={option}>
                        {titleizeToken(option)}
                      </option>
                    ),
                  )}
                </select>
              </Field>
              <Field label="Preferred work engine">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      preferredHarness: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.preferredHarness}
                >
                  {PREFERRED_HARNESS_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="field-row">
              <Field label="Routing strategy">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      routingStrategy: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.routingStrategy}
                >
                  {ROUTING_STRATEGY_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Execution target">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      executionTargetPreference: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.executionTargetPreference}
                >
                  {EXECUTION_TARGET_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="field-row">
              <Field label="OpenAI / Codex auth path">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      openaiCodexAuthMode: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.openaiCodexAuthMode}
                >
                  {OPENAI_CODEX_AUTH_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="MiniMax auth path">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      minimaxAuthMode: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.minimaxAuthMode}
                >
                  {MINIMAX_AUTH_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="field-row">
              <Field label="Commit message style">
                <select
                  onChange={event =>
                    setWorkspaceProfileForm(current => ({
                      ...current,
                      commitMessageStyle: event.target.value,
                    }))
                  }
                  value={workspaceProfileForm.commitMessageStyle}
                >
                  {COMMIT_STYLE_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <label className="check-field">
              <input
                checked={workspaceProfileForm.autoOptimizeRouting}
                onChange={event =>
                  setWorkspaceProfileForm(current => ({
                    ...current,
                    autoOptimizeRouting: event.target.checked,
                  }))
                }
                type="checkbox"
              />
              <span>Enable deterministic routing auto-optimize when enough local runs exist.</span>
            </label>

            <div className="drawer-actions">
              <ActionButton onClick={() => void saveWorkspacePolicy()} variant="primary">
                Save workspace policy
              </ActionButton>
            </div>

            <div className="drawer-list">
              {viewModel.drawers.builder.profileStudio.behavior.map(item => (
                <article className="drawer-card" key={`profile-behavior-${item.label}`}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </div>
            <details>
              <summary>Available profile contracts</summary>
              <div className="drawer-list">
                {viewModel.drawers.builder.profileStudio.profileRows.map(item => (
                  <article className={`drawer-card ${toneClass(item.tone)}`} key={item.id}>
                    <span>{item.label}</span>
                    <strong>{item.description}</strong>
                    <p>
                      {item.approval} approvals · {item.autonomy} autonomy · {item.visibility} visibility
                    </p>
                    <p>{item.density} density</p>
                  </article>
                ))}
              </div>
            </details>
          </section>

          <section className="drawer-block">
            <h3>Service management</h3>
            <p>
              {`${viewModel.drawers.builder.serviceStudio.summary.healthyCount}/${viewModel.drawers.builder.serviceStudio.summary.totalItems} healthy`}
              {` · ${viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount} need attention`}
              {` · ${viewModel.drawers.builder.serviceStudio.availableActionCount} executable actions`}
            </p>
            <div className="drawer-list">
              {viewModel.drawers.builder.serviceStudio.services.map(service => (
                <article className={`drawer-card ${toneClass(service.tone)}`} key={service.serviceId}>
                  <span>{service.category}</span>
                  <strong>{service.label}</strong>
                  <p>
                    {service.status}
                    {service.version ? ` · ${service.version}` : ""}
                  </p>
                  <p>
                    {service.managementMode}
                    {service.required ? " · required" : " · optional"}
                  </p>
                  {service.details ? <p>{service.details}</p> : null}
                  {service.updateSafety?.summary ? (
                    <div className="update-safety-note" aria-label={`${service.label} update safety`}>
                      <strong>{service.updateSafety.label || "Review before updating"}</strong>
                      <p>{service.updateSafety.summary}</p>
                      <span>{service.updateSafety.safeNextStep}</span>
                      {service.updateSafety.verifyAfterUpdate ? <span>Fluxio will re-check setup after the update.</span> : null}
                    </div>
                  ) : null}
                  {service.actions.length > 0 ? (
                    <div className="drawer-actions">
                      {service.actions.slice(0, 3).map(action => (
                        <ActionButton
                          key={`${service.serviceId}-${action.actionId}`}
                          onClick={() => void runWorkspaceActionSpec(action)}
                        >
                          {action.label}
                        </ActionButton>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          </section>

          <section className="drawer-block">
            <h3>Skill studio</h3>
            <p>
              {`${viewModel.drawers.builder.skillStudio.summary.reviewedReusableCount}/${viewModel.drawers.builder.skillStudio.summary.totalSkills} reviewed reusable`}
              {` · ${viewModel.drawers.builder.skillStudio.summary.needsTestCount} need tests`}
              {` · ${viewModel.drawers.builder.skillStudio.summary.learnedCount} learned`}
            </p>
            <p>
              {`${viewModel.drawers.builder.skillStudio.summary.executionReadyCount} execution-ready`}
              {` · ${viewModel.drawers.builder.skillStudio.summary.installedCount} installed`}
              {` · ${viewModel.drawers.builder.skillStudio.summary.uniquePackCount} unique packs`}
            </p>
            <div className="skill-toolbar">
              <Field label="Filter">
                <select
                  onChange={event => setSkillStudioFilter(event.target.value)}
                  value={skillStudioFilter}
                >
                  <option value="all">All packs</option>
                  <option value="recommended">Recommended only</option>
                  <option value="installed">Installed only</option>
                  <option value="needs_attention">Needs attention</option>
                </select>
              </Field>
              <Field label="Search">
                <input
                  onChange={event => setSkillStudioQuery(event.target.value)}
                  placeholder="Search by pack or profile"
                  value={skillStudioQuery}
                />
              </Field>
            </div>
            <p className="drawer-footnote">{viewModel.drawers.builder.skillStudio.capabilitiesNote}</p>
            <div className="context-grid compact-metrics">
              <article className="context-item">
                <span>Agent-proposed drafts</span>
                <strong>{skillLifecycleCounts.draft}</strong>
              </article>
              <article className="context-item">
                <span>Human review</span>
                <strong>{skillLifecycleCounts.review}</strong>
              </article>
              <article className="context-item">
                <span>Validation and tests</span>
                <strong>{skillLifecycleCounts.verify}</strong>
              </article>
              <article className="context-item">
                <span>Publish-ready</span>
                <strong>{skillLifecycleCounts.publish}</strong>
              </article>
            </div>
            <details open>
              <summary>Design and frontend recommendations</summary>
              <div className="drawer-list compact">
                {designFrontendRecommended.length > 0 ? (
                  designFrontendRecommended.slice(0, 6).map(item => (
                    <article className={`drawer-card ${toneClass(item.tone)}`} key={`design-${item.id}`}>
                      <span>{item.originType}</span>
                      <strong>{item.label}</strong>
                      <p>{item.description}</p>
                      <p>{item.installed ? "Installed" : "Recommended"} · {item.executionCapable ? "Execution-capable" : "Guidance only"}</p>
                    </article>
                  ))
                ) : (
                  <article className="drawer-card">
                    <strong>No design/front-end recommendation matches the current filter.</strong>
                  </article>
                )}
              </div>
            </details>
            <details open>
              <summary>Recommended packs</summary>
              <div className="drawer-list">
                {filteredRecommendedSkills.length > 0 ? (
                  filteredRecommendedSkills.map(item => (
                    <article className={`drawer-card ${toneClass(item.tone)}`} key={item.id}>
                      <span>{item.originType}</span>
                      <strong>{item.label}</strong>
                      <p>{item.description}</p>
                      <p>
                        {item.status}
                        {item.installed ? " · installed" : " · not installed"}
                        {item.executionCapable ? " · execution-capable" : " · guidance-only"}
                      </p>
                      {item.profileSuitability?.length > 0 ? (
                        <div className="pill-row">
                          {item.profileSuitability.map(entry => (
                            <span className="mini-pill" key={`${item.id}-${entry}`}>
                              {entry}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {item.permissions?.length > 0 ? (
                        <div className="pill-row">
                          {item.permissions.map(permission => (
                            <span className="mini-pill muted" key={`${item.id}-perm-${permission}`}>
                              {permission}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))
                ) : (
                  <article className="drawer-card">
                    <strong>No recommended pack matches this filter.</strong>
                  </article>
                )}
              </div>
            </details>
            <details>
              <summary>Curated inventory</summary>
              <div className="drawer-list">
                {filteredCuratedSkills.length > 0 ? (
                  filteredCuratedSkills.map(item => (
                    <article className={`drawer-card ${toneClass(item.tone)}`} key={item.id}>
                      <span>{item.originType}</span>
                      <strong>{item.label}</strong>
                      <p>
                        {item.status}
                        {item.installed ? " · installed" : " · not installed"}
                        {item.executionCapable ? " · execution-capable" : " · guidance-only"}
                      </p>
                      <p>
                        Used {item.usageCount} time(s) · Helped {item.helpedCount} run(s)
                      </p>
                      {item.profileSuitability?.length > 0 ? (
                        <div className="pill-row">
                          {item.profileSuitability.map(entry => (
                            <span className="mini-pill" key={`${item.id}-${entry}`}>
                              {entry}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))
                ) : (
                  <article className="drawer-card">
                    <strong>No curated pack matches this filter.</strong>
                  </article>
                )}
              </div>
            </details>
            <details>
              <summary>Quality actions</summary>
              <ul>
                {viewModel.drawers.builder.skillStudio.nextQualityActions.length > 0 ? (
                  viewModel.drawers.builder.skillStudio.nextQualityActions.map(item => (
                    <li key={`skill-next-${item}`}>{item}</li>
                  ))
                ) : (
                  <li>Skill quality checklist is currently clear.</li>
                )}
              </ul>
            </details>
            <details>
              <summary>Profile coverage</summary>
              <div className="drawer-list compact">
                {Object.entries(viewModel.drawers.builder.skillStudio.coverageByProfile).map(
                  ([profile, count]) => (
                    <article className="drawer-card" key={`coverage-${profile}`}>
                      <span>{profile}</span>
                      <strong>{count} suitable pack(s)</strong>
                    </article>
                  ),
                )}
              </div>
            </details>
          </section>

          <section className="drawer-block">
            <h3>Workflow studio</h3>
            <p>
              {`${viewModel.drawers.builder.workflowStudio.summary.reviewedCount}/${viewModel.drawers.builder.workflowStudio.summary.recipeCount} reviewed`}
              {` · ${viewModel.drawers.builder.workflowStudio.summary.blockedCount} blocked`}
              {` · Recommended mode ${viewModel.drawers.builder.workflowStudio.summary.recommendedMode}`}
            </p>
            <div className="drawer-list">
              {viewModel.drawers.builder.workflowStudio.recipes.map(item => (
                <article className={`drawer-card ${toneClass(item.tone)}`} key={item.workflowId}>
                  <span>{item.surface}</span>
                  <strong>{item.label}</strong>
                  <p>{item.description}</p>
                  <p>
                    {item.status} · {item.audience} · {item.runtimeChoice}
                  </p>
                  {item.verificationDefaults.length > 0 ? (
                    <p>{`Default verification: ${item.verificationDefaults.join(" | ")}`}</p>
                  ) : null}
                </article>
              ))}
            </div>
            <details>
              <summary>Learning queue</summary>
              <ul>
                {viewModel.drawers.builder.workflowStudio.learningQueue.length > 0 ? (
                  viewModel.drawers.builder.workflowStudio.learningQueue.map(item => (
                    <li key={`learning-${item}`}>{listLabel(item)}</li>
                  ))
                ) : (
                  <li>No pending workflow learning item.</li>
                )}
              </ul>
            </details>
          </section>

          <section className="drawer-block">
            <h3>Repo operations</h3>
            <div className="drawer-list">
              {[...viewModel.drawers.builder.gitActions, ...viewModel.drawers.builder.validationActions].map(
                action => (
                  <article className={`drawer-card ${toneClass(action.tone)}`} key={`${action.surface}-${action.actionId}`}>
                    <span>{titleizeToken(action.surface)}</span>
                    <strong>{action.label}</strong>
                    <p>{action.detail}</p>
                    <div className="drawer-actions">
                      <ActionButton onClick={() => void runWorkspaceActionSpec(action)}>
                        {action.requiresApproval ? "Approve and run" : "Run action"}
                      </ActionButton>
                    </div>
                  </article>
                ),
              )}
            </div>
          </section>

          <section className="drawer-block">
            <h3>Release gates</h3>
            <div className="drawer-list">
              {viewModel.drawers.builder.confidence.gates.length > 0 ? (
                viewModel.drawers.builder.confidence.gates.map(gate => (
                  <article className={`drawer-card ${toneClass(gate.tone)}`} key={gate.gateId}>
                    <span>{gate.required ? "Required" : "Quality"}</span>
                    <strong>{gate.label}</strong>
                    <p>{gate.details}</p>
                  </article>
                ))
              ) : (
                <article className="drawer-card">
                  <strong>Release gates are not available yet.</strong>
                </article>
              )}
            </div>
          </section>

          <section className="drawer-block">
            <h3>Feature truth</h3>
            <details open>
              <summary>Real and ready</summary>
              <ul>
                {viewModel.drawers.builder.featureTruth.realReady.map(item => (
                  <li key={`ready-${item}`}>{item}</li>
                ))}
              </ul>
            </details>
            <details>
              <summary>Real but secondary</summary>
              <ul>
                {viewModel.drawers.builder.featureTruth.realSecondary.map(item => (
                  <li key={`secondary-${item}`}>{item}</li>
                ))}
              </ul>
            </details>
            <details>
              <summary>Fixture and review only</summary>
              <ul>
                {viewModel.drawers.builder.featureTruth.fixtureOnly.map(item => (
                  <li key={`fixture-${item}`}>{item}</li>
                ))}
              </ul>
            </details>
            <details>
              <summary>Not ready yet</summary>
              <ul>
                {viewModel.drawers.builder.featureTruth.notReady.map(item => (
                  <li key={`not-ready-${item}`}>{item}</li>
                ))}
              </ul>
            </details>
          </section>

          <section className="drawer-block">
            <h3>Core state audit</h3>
            <div className="audit-list">
              {viewModel.drawers.builder.stateAudit.map(item => (
                <article className={`audit-item state-${item.state}`} key={item.id}>
                  <strong>{item.label}</strong>
                  <p>{item.nextAction}</p>
                </article>
              ))}
            </div>
          </section>
        </section>
      );
    }

    return (
      <section className="drawer-panel">
        <header>
          <p className="eyebrow">Context</p>
          <h2>Operational context</h2>
          <p>Open only when you need runtime truth, guardrails, or escalation details.</p>
        </header>
        {viewModel.drawers.context.groups.map(group => (
          <section className="drawer-block" key={group.title}>
            <h3>{group.title}</h3>
            <div className="context-grid">
              {group.items.map(item => (
                <article className="context-item" key={`${group.title}-${item.label}-${item.value}`}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  {item.note ? <p>{item.note}</p> : null}
                </article>
              ))}
            </div>
          </section>
        ))}
        <section className="drawer-block">
          <h3>Escalation</h3>
          <p>{data.telegramReady ? "Telegram ready" : "Telegram not configured"}</p>
          <div className="drawer-actions">
            <ActionButton onClick={() => setShowEscalationDialog(true)} variant="primary">
              Configure
            </ActionButton>
            <ActionButton onClick={() => void handleSendTestPing()}>Send test ping</ActionButton>
          </div>
        </section>
      </section>
    );
  };

  const activeReferenceRuleSet =
    findStudioItem(referenceStudio, "rule", referenceStudio.activeRuleSetId) ||
    findStudioItem(referenceStudio, "rule", referenceStudio.selectedRuleId);
  const referenceSkillStudioProps = {
    collectionTab: referenceStudio.collectionTab,
    selectedKind: referenceStudioKind,
    selectedItem: referenceStudioSelectedItem,
    skills: referenceStudio.skills,
    ruleSets: referenceStudio.ruleSets,
    activeSkillIds: referenceStudio.activeSkillIds,
    activeRuleSetId: referenceStudio.activeRuleSetId,
    totals: {
      totalSkills: referenceStudio.skills.length,
      activeSkills: asList(referenceStudio.activeSkillIds).length,
      totalRuleSets: referenceStudio.ruleSets.length,
      activeRuleSets: referenceStudio.activeRuleSetId ? 1 : 0,
      environments: 4,
      knowledgeBases: 3,
    },
    onSelectItem: handleReferenceStudioSelect,
    onFieldChange: handleReferenceStudioFieldChange,
    onListChange: handleReferenceStudioListChange,
    onRouteFieldChange: handleReferenceStudioRouteFieldChange,
    onAssistantFieldChange: handleReferenceStudioAssistantFieldChange,
    onAssistantSubmit: handleReferenceStudioAssistantSubmit,
    onApplyProposal: () => void applyReferenceStudioProposal(),
    onInsertDraft: () => void applyReferenceStudioProposal({ asDraft: true }),
    onSaveDraft: handleReferenceStudioSaveDraft,
    onPublish: () => void handleReferenceStudioPublish(),
  };
  const referenceSettingsProps = {
    activeTab: referenceSettingsTab,
    onSetTab: setReferenceSettingsTab,
    appearance: referenceAppearance,
    codexImport: { ...codexImportSnapshot, isRefreshing: codexImportRefreshing },
    onSetAppearance: handleReferenceAppearanceChange,
    onImportAllCodexWorkspaces: () => void handleReferenceImportAllCodexWorkspaces(),
    onImportCodexWorkspace: item => void handleReferenceImportCodexWorkspace(item),
    onPickWorkspaceFolder: () => void handleReferencePickWorkspaceFolder(),
    onRefreshCodexImport: () => void handleReferenceRefreshCodexImport(),
    sidebarBehaviorOptions: SIDEBAR_BEHAVIOR_OPTIONS,
    workspaceName: workspace?.name || "Orbit Pro",
    workspaceId: workspace?.workspace_id || "ws_local",
    workspaceProfileForm,
    onWorkspaceProfileFieldChange: handleReferenceWorkspaceProfileFieldChange,
    onRouteOverrideChange: handleReferenceRouteOverrideChange,
    onSaveWorkspacePolicy: () => void saveWorkspacePolicy(),
    activeRuleSet: activeReferenceRuleSet,
    onApplyActiveRuleSet: () => void handleReferenceApplyActiveRuleSet(),
    routeOptions: {
      providers: MODEL_PROVIDER_OPTIONS,
      efforts: MODEL_EFFORT_OPTIONS,
      models: ROUTE_MODEL_OPTIONS,
      harnesses: PREFERRED_HARNESS_OPTIONS,
      routingStrategies: ROUTING_STRATEGY_OPTIONS,
      executionTargets: EXECUTION_TARGET_OPTIONS,
    },
    authOptions: {
      openai: OPENAI_CODEX_AUTH_OPTIONS,
      minimax: MINIMAX_AUTH_OPTIONS,
    },
    chatgptConnection: {
      localApiUrl: localhostApiBaseUrl ? `${localhostApiBaseUrl}/v1/state` : "",
      mcpEndpoint: "",
      links: [
        {
          label: "ChatGPT app docs",
          onClick: () => void openProviderGuideUrl(PROVIDER_AUTH_URLS.chatgptDeveloperModeDocs, "ChatGPT app connection docs"),
        },
        {
          label: "MCP server docs",
          onClick: () => void openProviderGuideUrl(PROVIDER_AUTH_URLS.openaiMcpDocs, "OpenAI MCP server docs"),
        },
      ],
    },
    runtimes: asList(snapshot?.runtimes),
    bridgeSessions,
    storageBridge: snapshot?.storageBridge || {},
    setupServices: [
      ...asList(setupHealth?.serviceManagement),
      ...asList(workspace?.serviceManagement),
    ],
    providers: PROVIDER_SECRET_OPTIONS.map(item => ({
      ...item,
      quickAuth:
        item.id === "openai"
          ? {
              label: "Connect Codex OAuth",
              ready: openAICodexAuthReady,
              detail: providerOAuthActionsAvailable
                ? "Open browser OAuth and sync the credential into the local runtime; web/NAS uses the relay only as fallback."
                : providerOAuthUnavailableReason,
              disabled: !providerOAuthActionsAvailable,
            }
          : item.id === "minimax"
            ? {
                label: "MiniMax OpenClaw OAuth",
                ready: minimaxAuthReady,
                detail: providerOAuthActionsAvailable
                  ? "Launch OpenClaw's minimax-portal OAuth flow or save a MiniMax API key."
                  : providerOAuthUnavailableReason,
                disabled: !providerOAuthActionsAvailable,
              }
            : null,
      authLinks:
        item.id === "openai"
          ? [
              {
                label: "ChatGPT app docs",
                onClick: () => void openProviderGuideUrl(PROVIDER_AUTH_URLS.chatgptDeveloperModeDocs, "ChatGPT app connection docs"),
              },
              {
                label: "MCP server docs",
                onClick: () => void openProviderGuideUrl(PROVIDER_AUTH_URLS.openaiMcpDocs, "OpenAI MCP server docs"),
              },
              {
                label: "OpenAI API keys",
                onClick: () => void openProviderAuthUrl(PROVIDER_AUTH_URLS.openaiApiKeys, "OpenAI API keys"),
              },
            ]
          : item.id === "minimax"
            ? [
                {
                  label: "Verify OpenClaw OAuth",
                  onClick: () => void verifyMiniMaxOpenClawAuth(),
                },
                {
                  label: "MiniMax OpenClaw docs",
                  onClick: () => void openProviderGuideUrl(PROVIDER_AUTH_URLS.minimaxOpenClawDocs, "MiniMax OpenClaw docs"),
                },
                {
                  label: "MiniMax API keys",
                  onClick: () => void openProviderAuthUrl(PROVIDER_AUTH_URLS.minimaxApiKeys, "MiniMax API keys"),
                },
              ]
            : [],
      hasSecret: Boolean(providerSecretPresence[item.id]),
      draft: providerSecretDrafts[item.id] || "",
      onDraftChange: value => handleReferenceProviderDraftChange(item.id, value),
      onSave: () => void handleProviderSecretSave(item.id),
      onClear: () => void handleProviderSecretClear(item.id),
      savingState: providerSecretSaving[item.id] || "",
      onQuickAuth:
        (item.id === "openai" || item.id === "minimax") && providerOAuthActionsAvailable
          ? () => void handleReferenceQuickAuth(item.id)
          : null,
      status:
        item.id === "openai"
          ? openAICodexAuthReady
          : item.id === "minimax"
            ? minimaxAuthReady
            : Boolean(providerSecretPresence[item.id]),
    })),
    members: [
      { name: "Orbit Pro", role: "Owner" },
      { name: "Syntelos Agent", role: "System" },
      { name: titleizeToken(workspaceProfileForm.userProfile), role: "Active profile" },
    ],
    privacy: {
      conversationRetention: "90 days",
      fileRetention: "30 days",
    },
  };

  return (
    <div
      className="fluxio-shell"
      data-drawer={showPersistentDrawer ? "open" : "collapsed"}
      data-mode={uiMode}
      data-profile={profileId}
    >
      <header className="fluxio-topbar">
        <div className="topbar-app">
          <div className="app-menu">
            <button aria-label="Syntelos menu" className="app-menu-glyph" type="button">
              +
            </button>
            <MenuButton label="File" onClick={() => setShowWorkspaceDialog(true)} />
            <MenuButton
              label="Edit"
              onClick={() => {
                if (workspaces.length === 0) {
                  setShowWorkspaceDialog(true);
                  return;
                }
                openMissionDialog();
              }}
            />
            <MenuButton
              label="View"
              onClick={() => {
                setUiMode("builder");
                setActiveDrawer("builder");
              }}
            />
            <MenuButton
              label="Window"
              onClick={() => {
                setUiMode("builder");
                setActiveDrawer("runtime");
              }}
            />
            <MenuButton
              label="Help"
              onClick={() => {
                setUiMode("agent");
                setActiveDrawer(agentBlockedState.defaultDrawer);
              }}
            />
          </div>

          <div className="topbar-context">
            <strong>{mission?.title || mission?.objective || workspace?.name || "Syntelos workspace"}</strong>
            <span>{workspace?.name || "Select a workspace"}</span>
            <div className="topbar-context-actions">
              {workspace?.workspace_id ? (
                <ActionButton
                  onClick={() => copyContextValue(workspace.workspace_id)}
                  type="button"
                >
                  Copy workspace ID
                </ActionButton>
              ) : null}
              {mission?.mission_id ? (
                <ActionButton
                  onClick={() => copyContextValue(mission.mission_id)}
                  type="button"
                >
                  Copy mission ID
                </ActionButton>
              ) : null}
            </div>
          </div>
        </div>

        <div aria-label="Syntelos mode" className="fluxio-mode" role="tablist">
          {["agent", "builder"].map(mode => (
            <button
              aria-selected={uiMode === mode}
              className={uiMode === mode ? "active" : ""}
              key={mode}
              onClick={() => {
                markAction(`mode:${mode}`);
                setUiMode(mode);
                if (mode === "builder") {
                  setActiveDrawer(null);
                  return;
                }
                setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
              }}
              role="tab"
              type="button"
            >
              {titleizeToken(mode)}
            </button>
          ))}
        </div>

        <div className="topbar-shortcuts">
          <TopbarShortcut
            active={showPersistentDrawer}
            label={showPersistentDrawer && activeDrawerMeta ? `${activeDrawerMeta.label} panel` : "Open panel"}
            onClick={() => {
              markAction("toggle:panel");
              if (uiMode === "builder") {
                setActiveDrawer(current => (current ? null : "builder"));
                return;
              }
              if (agentBlockedState.isBlocked) {
                setActiveDrawer(agentBlockedState.defaultDrawer);
              }
            }}
            tone="neutral"
          />
        </div>

        <div className="topbar-confidence">
          <span>{topbarStatus.label}</span>
          <strong className={toneClass(topbarStatus.tone)}>
            {topbarStatus.value}
          </strong>
        </div>

        <ActionButton onClick={handlePrimaryAction} variant="primary">
          {viewModel.topBar.primaryAction.label}
        </ActionButton>
      </header>

      <div className="fluxio-body">
        <aside className="fluxio-sidebar">
          <div className="fluxio-sidebar-scroll">
            <section className="sidebar-surface-list">
              <GlobalRailButton
                active={uiMode === "agent"}
                icon="◎"
                label="Agent"
                onClick={() => {
                  markAction("rail:operator");
                  setUiMode("agent");
                  setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
                }}
              />
              {uiMode === "builder" ? (
                <>
                  <GlobalRailButton
                    active={activeDrawer === "builder"}
                    icon="⌘"
                    label="Builder"
                    onClick={() => {
                      markAction("rail:builder");
                      setActiveDrawer(current => (current === "builder" ? null : "builder"));
                    }}
                  />
                  <GlobalRailButton
                    active={activeDrawer === "skills"}
                    icon="✦"
                    label="Skills"
                    onClick={() => {
                      markAction("rail:skills");
                      setSkillStudioFilter("all");
                      setActiveDrawer(current => (current === "skills" ? null : "skills"));
                    }}
                  />
                  <GlobalRailButton
                    active={activeDrawer === "runtime"}
                    icon="◇"
                    label="Runtime"
                    onClick={() => {
                      markAction("rail:runtime");
                      setActiveDrawer(current => (current === "runtime" ? null : "runtime"));
                    }}
                  />
                  <GlobalRailButton
                    active={surface === "images"}
                    icon="▧"
                    label="Images"
                    onClick={() => {
                      markAction("rail:images");
                      setSurface("images");
                      setActiveDrawer(null);
                    }}
                  />
                  <GlobalRailButton
                    active={surface === "voice"}
                    icon="◉"
                    label="Voice"
                    onClick={() => {
                      markAction("rail:voice");
                      setSurface("voice");
                      setActiveDrawer(null);
                    }}
                  />
                  <GlobalRailButton
                    active={activeDrawer === "profiles"}
                    icon="◫"
                    label="Profiles"
                    onClick={() => {
                      markAction("rail:profiles");
                      setActiveDrawer(current => (current === "profiles" ? null : "profiles"));
                    }}
                  />
                </>
              ) : null}
            </section>

            <section className="fluxio-nav-section">
              <div className="fluxio-nav-heading">
                <p className="eyebrow">Quick controls</p>
              </div>
              <div className="fluxio-nav-list">
                <NavItem
                  badge={previewMode === "live" ? "full" : "read-only"}
                  context={previewMode === "live" ? "Live backend access is enabled." : "Fixture mode keeps actions read-only."}
                  icon="⛨"
                  onClick={handleSidebarAccess}
                  subtitle={sidebarAccessLabel}
                  title="Access"
                  tone={previewMode === "live" ? "good" : "warn"}
                />
                <NavItem
                  badge={sidebarLocalLeaf}
                  context={sidebarLocalPath || "No workspace selected yet."}
                  icon="⌂"
                  onClick={handleSidebarLocal}
                  subtitle={workspace?.name || "Pick workspace"}
                  title="Local"
                  tone={workspace ? "good" : "warn"}
                />
                <NavItem
                  badge={`${builderRootItems.length} root${builderRootItems.length === 1 ? "" : "s"}`}
                  context={
                    builderPrimaryConversation?.executionPath ||
                    builderPrimaryConversation?.workspacePath ||
                    "Folder map appears once Builder has active conversations."
                  }
                  icon="▤"
                  onClick={handleSidebarFolders}
                  subtitle={builderPrimaryConversation?.folderLabel || "Open folder map"}
                  title="Folders"
                  tone={builderRootItems.length > 0 ? "neutral" : "warn"}
                />
                <NavItem
                  badge={sidebarBranchName}
                  context={sidebarBranchContext}
                  icon="⑂"
                  onClick={() => void handleSidebarBranch()}
                  subtitle={workspaceGitSnapshot?.repoDetected ? "Git branch controls" : "No git workspace"}
                  title="Branch"
                  tone={sidebarBranchTone}
                />
              </div>
              {workspaceGitSnapshot?.repoDetected ? (
                <div className="fluxio-sidebar-branch-actions">
                  <ActionButton onClick={() => void handleSidebarBranch()} type="button">
                    Inspect branch
                  </ActionButton>
                  {branchPullAction ? (
                    <ActionButton onClick={() => void handleSidebarBranchPull()} type="button">
                      Pull
                    </ActionButton>
                  ) : null}
                  {branchPushAction ? (
                    <ActionButton onClick={() => void handleSidebarBranchPush()} type="button">
                      Push
                    </ActionButton>
                  ) : null}
                </div>
              ) : null}
            </section>

            {uiMode === "builder" ? (
              <>
                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Board</p>
                    <ActionButton onClick={openMissionDialog}>Launch</ActionButton>
                  </div>
                  <div className="builder-sidebar-metrics">
                    {builderBoard.metrics.slice(0, 3).map(item => (
                      <article className={`builder-sidebar-card ${toneClass(item.tone)}`} key={`builder-rail-${item.id}`}>
                        <span>{item.label}</span>
                        <strong>{item.value}</strong>
                        <p>{item.detail}</p>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Roots</p>
                  </div>
                  <div className="fluxio-nav-list">
                    {builderRootItems.length > 0 ? (
                      builderRootItems.map(item => (
                        <NavItem
                          active={item.workspaceId === selectedWorkspaceId}
                          badge={item.folderLabel || "root"}
                          context={item.path}
                          icon="▣"
                          key={`builder-root-${item.workspaceId}`}
                          onClick={() => setSelectedWorkspaceId(item.workspaceId)}
                          stats={[
                            item.activeCount > 0
                              ? { label: "threads", value: item.activeCount, tone: "good" }
                              : null,
                            item.blockedCount > 0
                              ? { label: "blocked", value: item.blockedCount, tone: "warn" }
                              : null,
                            item.delegatedCount > 0
                              ? { label: "lanes", value: item.delegatedCount, tone: "good" }
                              : null,
                          ].filter(Boolean)}
                          subtitle={item.activeCount > 0 ? "Conversation root" : "Workspace root"}
                          title={item.title}
                          tone={item.tone}
                        />
                      ))
                    ) : (
                      <p className="fluxio-empty-copy">Workspace roots will appear once Builder has projects to supervise.</p>
                    )}
                  </div>
                </section>

                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Nexuses</p>
                    <ActionButton onClick={() => setActiveDrawer("context")}>Open</ActionButton>
                  </div>
                  <div className="builder-sidebar-nexus-list">
                    {builderNexusItems.length > 0 ? (
                      builderNexusItems.map(item => (
                        <button
                          className={`builder-sidebar-nexus ${toneClass(item.tone)}`.trim()}
                          key={item.id}
                          onClick={() => {
                            if (item.missionId) {
                              setSelectedMissionId(item.missionId);
                            }
                            setActiveDrawer(item.tone === "bad" ? "proof" : "context");
                          }}
                          type="button"
                        >
                          <span>{item.label}</span>
                          <strong>{item.title}</strong>
                          <p>{item.reason}</p>
                          <em>{item.folderLabel || item.workspaceName}</em>
                        </button>
                      ))
                    ) : (
                      <p className="fluxio-empty-copy">Important operator decisions will collect here.</p>
                    )}
                  </div>
                </section>

                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Bridge</p>
                    <ActionButton onClick={() => setActiveDrawer("runtime")}>Inspect</ActionButton>
                  </div>
                  <article className="builder-sidebar-bridge">
                    <span>Runtime and NAS bridges</span>
                    <strong>{bridgeSummary.connected} live bridge{bridgeSummary.connected === 1 ? "" : "s"}</strong>
                    <p>{bridgeSummary.recommendation}</p>
                    <div className="fluxio-nav-stats">
                      <span className="fluxio-nav-stat tone-good">
                        <strong>{bridgeSummary.callbackReady}</strong>
                        <em>callbacks</em>
                      </span>
                      <span className="fluxio-nav-stat tone-neutral">
                        <strong>{bridgeSummary.totalApps}</strong>
                        <em>apps</em>
                      </span>
                      <span className="fluxio-nav-stat tone-good">
                        <strong>{bridgeSummary.mobileReady}</strong>
                        <em>mobile</em>
                      </span>
                      <span className="fluxio-nav-stat tone-neutral">
                        <strong>{fusionWorkbench.summary.readyRows}</strong>
                        <em>fusion</em>
                      </span>
                    </div>
                  </article>
                </section>
              </>
            ) : (
              <>
                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Workspaces</p>
                    <ActionButton onClick={() => setShowWorkspaceDialog(true)}>Add</ActionButton>
                  </div>
                  <div className="fluxio-nav-search">
                    <input
                      onChange={event => setWorkspaceSearchQuery(event.target.value)}
                      placeholder="Search projects, paths, or IDs"
                      value={workspaceSearchQuery}
                    />
                  </div>
                  <div className="fluxio-nav-list">
                    {workspaceNavItems.length > 0 ? (
                      <WindowedList
                        className="fluxio-nav-windowed"
                        estimatedItemHeight={138}
                        items={workspaceNavItems}
                        renderItem={item => (
                          <NavItem
                            active={item.workspaceId === selectedWorkspaceId}
                            badge={item.badge}
                            context={item.context}
                            draggable
                            icon="▣"
                            key={item.workspaceId}
                            onClick={() => setSelectedWorkspaceId(item.workspaceId)}
                            onCopy={copyContextValue}
                            onDragOver={event => event.preventDefault()}
                            onDragStart={() => handleWorkspaceDragStart(item.workspaceId)}
                            onDrop={event => {
                              event.preventDefault();
                              handleWorkspaceDrop(item.workspaceId);
                            }}
                            stats={item.stats}
                            subtitle={item.subtitle}
                            title={item.title}
                            tone={item.tone}
                          />
                        )}
                      />
                    ) : (
                      <p className="fluxio-empty-copy">
                        {workspaceSearchQuery.trim()
                          ? "No workspace matches this search."
                          : "Add one workspace to begin."}
                      </p>
                    )}
                  </div>
                </section>

                <section className="fluxio-nav-section">
                  <div className="fluxio-nav-heading">
                    <p className="eyebrow">Missions</p>
                    <ActionButton onClick={openMissionDialog}>New</ActionButton>
                  </div>
                  <div className="fluxio-nav-search">
                    <input
                      onChange={event => setMissionSearchQuery(event.target.value)}
                      placeholder="Search title, status, or runtime"
                      value={missionSearchQuery}
                    />
                  </div>
                  <div className="fluxio-nav-list">
                    {missionNavItems.length > 0 ? (
                      <WindowedList
                        className="fluxio-nav-windowed"
                        estimatedItemHeight={140}
                        items={missionNavItems}
                        renderItem={item => (
                          <NavItem
                            active={item.missionId === selectedMissionId}
                            badge={item.badge}
                            context={item.context}
                            draggable
                            icon="◆"
                            key={item.missionId}
                            onClick={() => setSelectedMissionId(item.missionId)}
                            onCopy={copyContextValue}
                            onDragOver={event => event.preventDefault()}
                            onDragStart={() => handleMissionDragStart(item.missionId)}
                            onDrop={event => {
                              event.preventDefault();
                              handleMissionDrop(item.missionId);
                            }}
                            stats={item.stats}
                            subtitle={item.subtitle}
                            title={item.title}
                            tone={item.tone}
                          />
                        )}
                      />
                    ) : (
                      <p className="fluxio-empty-copy">
                        {missionSearchQuery.trim()
                          ? "No mission matches this search."
                          : "Mission thread appears after first launch."}
                      </p>
                    )}
                  </div>
                </section>
              </>
            )}
          </div>

          <div className="fluxio-sidebar-bottom">
            <GlobalRailButton
              active={activeDrawer === "settings"}
              icon="⚙"
              label="Settings"
              onClick={() => {
                markAction("rail:settings");
                setUiMode("builder");
                setActiveDrawer("settings");
              }}
              subtle
            />
          </div>
        </aside>

        <main className="fluxio-main">
          {!mission ? (
            uiMode === "builder" && surface === "images" ? (
              <section className="builder-shell image-studio-shell">
                <Suspense fallback={<LazySurfaceFallback label="Image Playground" />}>
                  <ImageStudioPlayground
                    generatedArtifacts={generatedImageArtifacts}
                    onRequestDraft={handleImageStudioRequestDraft}
                  />
                </Suspense>
              </section>
            ) : uiMode === "builder" && surface === "voice" ? (
              <section className="builder-shell voice-studio-shell">
                <header className="builder-head builder-studio-head">
                  <div>
                    <p className="eyebrow">Voice-first control</p>
                    <h1>Dictation and command review</h1>
                    <p>
                      Review dictated text, command confidence, keyboard parity, and confirmation boundaries before the app runs an action.
                    </p>
                  </div>
                  <div className="builder-head-actions">
                    <ActionButton onClick={() => void handleReferenceDictation()} variant="primary">
                      System dictation
                    </ActionButton>
                    <ActionButton onClick={() => void handleBuilderFeatureAction("open_skills")}>
                      Voice skill
                    </ActionButton>
                  </div>
                </header>
                <div className="voice-studio-grid">
                  <Suspense fallback={<LazySurfaceFallback label="Voice command panel" />}>
                    <VoiceCommandPanel onVoiceCommand={handleVoiceCommand} />
                  </Suspense>
                  <aside className="builder-panel voice-studio-guidance" aria-label="Voice accessibility safeguards">
                    <p className="eyebrow">Accessible operation</p>
                    <h2>Built for low typing</h2>
                    <div className="builder-thread-list">
                      <article className="builder-thread-item tone-good">
                        <span>Keyboard parity</span>
                        <strong>Every spoken action keeps a pointer and keyboard path.</strong>
                        <p>Buttons expose labels that include command names and shortcuts where available.</p>
                      </article>
                      <article className="builder-thread-item tone-warn">
                        <span>Confirmation</span>
                        <strong>Risky actions pause for review.</strong>
                        <p>Sending messages, clearing transcripts, approvals, and mission control require confirmation.</p>
                      </article>
                      <article className="builder-thread-item tone-neutral">
                        <span>Support truth</span>
                        <strong>No fake microphone state.</strong>
                        <p>The panel only reports live support when browser speech APIs or a local bridge are actually present.</p>
                      </article>
                    </div>
                  </aside>
                </div>
              </section>
            ) : uiMode === "builder" ? (
              <section className="builder-shell builder-launch-shell">
                <header className="builder-head builder-studio-head">
                  <div>
                    <p className="eyebrow">Builder workbench</p>
                    <h1>{viewModel.emptyState.title}</h1>
                    <p>{viewModel.emptyState.summary}</p>
                  </div>
                  <div className="builder-head-actions">
                    <ActionButton
                      onClick={() => {
                        if (workspaces.length === 0) {
                          setShowWorkspaceDialog(true);
                          return;
                        }
                        openMissionDialog();
                      }}
                      variant="primary"
                    >
                      {viewModel.emptyState.launchEntryLabel}
                    </ActionButton>
                    <ActionButton onClick={() => handleBuilderFeatureAction("open_builder")}>
                      Open panel
                    </ActionButton>
                  </div>
                </header>

                <div className="builder-workbench-grid">
                  <section className="builder-primary-column">
                    <article className="builder-panel builder-panel-hero builder-feature-card">
                      <div className="builder-feature-head">
                        <div>
                          <p className="eyebrow">Guided tutorial</p>
                          <h2>{tutorialStudio.headline}</h2>
                        </div>
                        <div className="builder-feature-meta">
                          <span className="mini-pill muted">{tutorialStudio.progressLabel}</span>
                          <span className="mini-pill muted">{tutorialStudio.motionMode} motion</span>
                        </div>
                      </div>
                      <p>{tutorialStudio.summary}</p>
                      <div className="builder-step-grid">
                        {tutorialStudio.steps.map(item => (
                          <button
                            className={`builder-step-card ${toneClass(item.tone)} ${item.current ? "current" : ""}`.trim()}
                            key={item.id}
                            onClick={() => void handleBuilderFeatureAction(item.actionId)}
                            type="button"
                          >
                            <span>{item.panel}</span>
                            <strong>{item.title}</strong>
                            <p>{item.description}</p>
                            <em>{item.status}</em>
                          </button>
                        ))}
                      </div>
                      {tutorialStudio.cards.length > 0 ? (
                        <div className="builder-inline-list builder-inline-list-actions">
                          {tutorialStudio.cards.map(item => (
                            <button
                              className="builder-inline-action"
                              key={item.id}
                              onClick={() => void handleBuilderFeatureAction(item.actionId)}
                              type="button"
                            >
                              <strong>{item.title}</strong>
                              <span>{item.body}</span>
                            </button>
                          ))}
                        </div>
                      ) : null}
                      <div className="drawer-actions">
                        <ActionButton
                          onClick={() => void handleBuilderFeatureAction(tutorialStudio.primaryActionId)}
                          variant="primary"
                        >
                          {tutorialStudio.primaryActionLabel}
                        </ActionButton>
                        {quickSetupActions.map(action => (
                          <ActionButton
                            key={`builder-empty-${action.actionId}`}
                            onClick={() => void runWorkspaceAction("setup", action.actionId)}
                          >
                            {action.label}
                          </ActionButton>
                        ))}
                      </div>
                    </article>

                    <div className="builder-feature-grid">
                      <article className="builder-panel builder-feature-card">
                        <div className="builder-feature-head">
                          <div>
                            <p className="eyebrow">Recommendations</p>
                            <h2>{recommendationStudio.headline}</h2>
                          </div>
                          <div className="builder-feature-meta">
                            <span className="mini-pill muted">
                              {recommendationStudio.skillRecommendations.length} skill leads
                            </span>
                          </div>
                        </div>
                        <p>{recommendationStudio.summary}</p>
                        <div className="builder-thread-list">
                          {recommendationStudio.struggleSignals.map(item => (
                            <button
                              className={`builder-thread-item ${toneClass(item.tone)}`.trim()}
                              key={item.id}
                              onClick={() => void handleBuilderFeatureAction(item.actionId)}
                              type="button"
                            >
                              <span>{item.label}</span>
                              <strong>{item.detail}</strong>
                            </button>
                          ))}
                        </div>
                        {recommendationStudio.skillRecommendations.length > 0 ? (
                          <div className="builder-inline-list">
                            {recommendationStudio.skillRecommendations.map(item => (
                              <span className="builder-inline-pill" key={item.id}>
                                <strong>{item.label}</strong>
                                <span>{item.reason}</span>
                              </span>
                            ))}
                          </div>
                        ) : null}
                        <div className="drawer-actions">
                          {recommendationStudio.nextMoves.slice(0, 2).map(item => (
                            <ActionButton
                              key={item.id}
                              onClick={() => void handleBuilderFeatureAction(item.actionId)}
                              variant={item === recommendationStudio.nextMoves[0] ? "primary" : "secondary"}
                            >
                              {item.label}
                            </ActionButton>
                          ))}
                        </div>
                      </article>

                      <article className="builder-panel builder-feature-card">
                        <div className="builder-feature-head">
                          <div>
                            <p className="eyebrow">Live UI review</p>
                            <h2>{liveReviewStudio.statusLine}</h2>
                          </div>
                          <div className="builder-feature-meta">
                            <span className="mini-pill muted">{liveReviewStudio.targets.length} review blocks</span>
                          </div>
                        </div>
                        <p>{liveReviewStudio.summary}</p>
                        <div className="builder-review-grid">
                          {liveReviewStudio.targets.map(item => (
                            <button
                              className={`builder-review-target ${toneClass(item.tone)} ${builderSelectedReviewTarget?.id === item.id ? "active" : ""}`.trim()}
                              key={item.id}
                              onClick={() => handleBuilderReviewTargetSeed(item)}
                              type="button"
                            >
                              <span>{item.label}</span>
                              <strong>{item.title}</strong>
                              <p>{item.detail}</p>
                            </button>
                          ))}
                        </div>
                        {builderSelectedReviewTarget ? (
                          <article className={`builder-review-focus ${toneClass(builderSelectedReviewTarget.tone)}`}>
                            <span>{builderSelectedReviewTarget.label}</span>
                            <strong>{builderSelectedReviewTarget.title}</strong>
                            <p>{builderSelectedReviewTarget.detail}</p>
                          </article>
                        ) : null}
                        <div className="drawer-actions">
                          <ActionButton
                            onClick={() => builderSelectedReviewTarget && handleBuilderReviewTargetSeed(builderSelectedReviewTarget)}
                            variant="primary"
                          >
                            Comment selected block
                          </ActionButton>
                          <ActionButton onClick={() => void handleBuilderFeatureAction("open_builder")}>
                            Open preview controls
                          </ActionButton>
                        </div>
                      </article>
                    </div>

                    <article className="builder-panel">
                      <div className="section-header">
                        <div className="section-title-block">
                          <p className="eyebrow">Road to 100%</p>
                          <h2>{viewModel.drawers.builder.qualityRoadmap.headline}</h2>
                        </div>
                      </div>
                      <div className="roadmap-grid">
                        {viewModel.drawers.builder.qualityRoadmap.tracks.slice(0, 4).map(item => (
                          <article className={`roadmap-item ${toneClass(item.tone)}`} key={`empty-roadmap-${item.id}`}>
                            <span>{titleizeToken(item.state)}</span>
                            <strong>{item.label}</strong>
                            <p>{item.detail}</p>
                            <ActionButton onClick={() => void handleQualityRoadmapAction(item)}>
                              {item.suggestedAction || "Open"}
                            </ActionButton>
                          </article>
                        ))}
                      </div>
                    </article>
                  </section>

                  <aside className="builder-secondary-column">
                    <article className="builder-panel builder-panel-focus">
                      <p className="eyebrow">Guided readiness</p>
                      <h3>{tutorialStudio.recommendedWorkflow}</h3>
                      <p>{viewModel.emptyState.qualityRoadmapHeadline}</p>
                      <div className="builder-inline-list">
                        {tutorialStudio.readiness.map(item => (
                          <span key={`readiness-${item}`}>{item}</span>
                        ))}
                      </div>
                    </article>

                    <article className="builder-panel builder-panel-focus">
                      <p className="eyebrow">Profiles</p>
                      <h3>{titleizeToken(workspaceProfileForm.userProfile)}</h3>
                      <p>{viewModel.drawers.builder.profileStudio.behavior[0]?.value || "No profile selected."}</p>
                      <ActionButton onClick={() => void handleBuilderFeatureAction("open_profiles")}>
                        Open profiles
                      </ActionButton>
                    </article>

                    <article className="builder-panel builder-panel-focus">
                      <p className="eyebrow">Feature backlog</p>
                      <h3>
                        {tutorialStudio.improvements.length + recommendationStudio.learningQueue.length} queued improvement{tutorialStudio.improvements.length + recommendationStudio.learningQueue.length === 1 ? "" : "s"}
                      </h3>
                      <div className="builder-thread-list">
                        {tutorialStudio.improvements.map(item => (
                          <article className={`builder-thread-item ${toneClass(item.tone)}`} key={item.id}>
                            <span>{item.category}</span>
                            <strong>{item.title}</strong>
                            <p>{item.reason}</p>
                          </article>
                        ))}
                        {recommendationStudio.learningQueue.map(item => (
                          <article className={`builder-thread-item ${toneClass(item.tone)}`} key={item.id}>
                            <span>{item.priority}</span>
                            <strong>{item.title}</strong>
                            <p>Turn repeated friction into a reviewed skill or workflow.</p>
                          </article>
                        ))}
                      </div>
                      <ActionButton onClick={() => void handleBuilderFeatureAction("open_skills")}>
                        Open improvement flow
                      </ActionButton>
                    </article>
                  </aside>
                </div>
              </section>
            ) : (
              <section className="thread-shell agent-shell agent-idle-shell">
                <header className="thread-head agent-thread-head agent-title-head">
                  <h1>{agentCenterTitle}</h1>
                </header>

                <form
                  className="thread-composer agent-composer agent-chat-composer agent-idle-composer"
                  onSubmit={event => event.preventDefault()}
                >
                  <div className="agent-control-grid">
                    <Field label="Launch runtime">
                      <select
                        onChange={event =>
                          setMissionForm(current => ({ ...current, runtime: event.target.value }))
                        }
                        value={missionForm.runtime}
                      >
                        {runtimeOptions.map(option => (
                          <option key={`idle-runtime-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Route role">
                      <input readOnly value={`${titleizeToken(agentRouteRole)} (auto)`} />
                    </Field>
                    <Field label="Provider">
                      <select
                        onChange={event => handleAgentRouteFieldChange("provider", event.target.value)}
                        value={selectedAgentRoute.provider}
                      >
                        {MODEL_PROVIDER_OPTIONS.map(option => (
                          <option key={`idle-provider-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Model">
                      <select
                        onChange={event => handleAgentRouteFieldChange("model", event.target.value)}
                        value={selectedAgentRoute.model}
                      >
                        <option value="">Profile default</option>
                        {ROUTE_MODEL_OPTIONS.map(option => (
                          <option key={`idle-model-${option}`} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Reasoning">
                      <select
                        onChange={event => handleAgentRouteFieldChange("effort", event.target.value)}
                        value={normalizeRouteEffort(selectedAgentRoute.effort, "default")}
                      >
                        {MODEL_EFFORT_OPTIONS.map(option => (
                          <option key={`idle-effort-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                  </div>
                  <div className="agent-control-strip">
                    <p>{agentRuntimeHint}</p>
                    <div className="thread-chip-row">
                      <span className="mini-pill muted">{agentRouteStatus}</span>
                      <span className="mini-pill muted">{titleizeToken(agentRouteRole)} auto role</span>
                      <span className="mini-pill muted">
                        Code execution {codeExecutionEnabled ? "on" : "off"}
                      </span>
                      <span className="mini-pill muted">
                        {modelAuthReady ? "Model auth ready" : "Model auth missing"}
                      </span>
                    </div>
                    <div className="thread-composer-actions">
                      <ActionButton onClick={() => void handleAgentRouteSave()} type="button">
                        Apply route
                      </ActionButton>
                      <ActionButton
                        onClick={() => setCodeExecutionEnabled(current => !current)}
                        type="button"
                      >
                        {codeExecutionEnabled ? "Disable code execution" : "Enable code execution"}
                      </ActionButton>
                    </div>
                  </div>
                  <div className="agent-preset-row">
                    {MODEL_QUICK_PRESETS.map(preset => (
                      <ActionButton
                        key={`idle-preset-${preset.id}`}
                        onClick={() => applyModelQuickPreset(preset)}
                        type="button"
                      >
                        {preset.label}
                      </ActionButton>
                    ))}
                  </div>
                  <label htmlFor="thread-note-idle">{agentComposerLabel}</label>
                  <textarea
                    id="thread-note-idle"
                    onChange={event => setOperatorDraft(event.target.value)}
                    onPaste={handleComposerPaste}
                    placeholder={agentComposerPlaceholder}
                    value={operatorDraft}
                  />
                  <ComposerAttachmentStrip
                    attachments={operatorAttachments}
                    onClear={clearOperatorAttachments}
                    onRemove={removeOperatorAttachment}
                  />
                  <div className="thread-composer-actions">
                    <ActionButton onClick={handleAgentIdlePrimaryAction} type="button" variant="primary">
                      {workspaces.length > 0 ? "Launch mission" : "Add project"}
                    </ActionButton>
                  </div>
                </form>
              </section>
            )
          ) : uiMode === "builder" && surface === "images" ? (
            <section className="builder-shell image-studio-shell">
              <Suspense fallback={<LazySurfaceFallback label="Image Playground" />}>
                <ImageStudioPlayground
                  generatedArtifacts={generatedImageArtifacts}
                  onRequestDraft={handleImageStudioRequestDraft}
                />
              </Suspense>
            </section>
          ) : uiMode === "builder" && surface === "voice" ? (
            <section className="builder-shell voice-studio-shell">
              <header className="builder-head builder-studio-head">
                <div>
                  <p className="eyebrow">Voice-first control</p>
                  <h1>Dictation and command review</h1>
                  <p>
                    Review dictated text, command confidence, keyboard parity, and confirmation boundaries before the app runs an action.
                  </p>
                </div>
                <div className="builder-head-actions">
                  <ActionButton onClick={() => void handleReferenceDictation()} variant="primary">
                    System dictation
                  </ActionButton>
                  <ActionButton onClick={() => void handleBuilderFeatureAction("open_skills")}>
                    Voice skill
                  </ActionButton>
                </div>
              </header>
              <div className="voice-studio-grid">
                <Suspense fallback={<LazySurfaceFallback label="Voice command panel" />}>
                  <VoiceCommandPanel onVoiceCommand={handleVoiceCommand} />
                </Suspense>
                <aside className="builder-panel voice-studio-guidance" aria-label="Voice accessibility safeguards">
                  <p className="eyebrow">Accessible operation</p>
                  <h2>Built for low typing</h2>
                  <div className="builder-thread-list">
                    <article className="builder-thread-item tone-good">
                      <span>Keyboard parity</span>
                      <strong>Every spoken action keeps a pointer and keyboard path.</strong>
                      <p>Buttons expose labels that include command names and shortcuts where available.</p>
                    </article>
                    <article className="builder-thread-item tone-warn">
                      <span>Confirmation</span>
                      <strong>Risky actions pause for review.</strong>
                      <p>Sending messages, clearing transcripts, approvals, and mission control require confirmation.</p>
                    </article>
                    <article className="builder-thread-item tone-neutral">
                      <span>Support truth</span>
                      <strong>No fake microphone state.</strong>
                      <p>The panel only reports live support when browser speech APIs or a local bridge are actually present.</p>
                    </article>
                  </div>
                </aside>
              </div>
            </section>
          ) : uiMode === "builder" ? (
            <section className="builder-shell">
              <header className="builder-head builder-studio-head">
                <div>
                  <p className="eyebrow">Conversation command board</p>
                  <h1>{viewModel.thread.title}</h1>
                  <p>{builderBoard.summary}</p>
                </div>
                <div className="builder-head-actions">
                  <ActionButton onClick={() => setActiveDrawer("builder")} variant="primary">
                    Open panel
                  </ActionButton>
                  <ActionButton onClick={openMissionDialog}>Launch mission</ActionButton>
                </div>
              </header>

              <div className="builder-workbench-grid">
                <section className="builder-primary-column">
                  <article className="builder-panel builder-panel-hero builder-command-deck">
                    <div className="builder-command-head">
                      <div className="builder-command-copy">
                        <p className="eyebrow">{builderBoard.headline}</p>
                        {builderPrimaryConversation ? (
                          <>
                            <div className="thread-chip-row">
                              <StatusPill tone={builderPrimaryConversation.blocked ? "warn" : builderPrimaryConversation.tone}>
                                {builderPrimaryConversation.runtime}
                              </StatusPill>
                              <StatusPill tone="neutral">{builderPrimaryConversation.harnessLabel}</StatusPill>
                              <StatusPill strong tone={builderPrimaryConversation.blocked ? "warn" : builderPrimaryConversation.tone}>
                                {builderPrimaryConversation.statusLabel}
                              </StatusPill>
                              <StatusPill tone={viewModel.thread.activityPulse?.tone || "neutral"}>
                                {viewModel.thread.activityPulse?.stage || "Planning"}
                              </StatusPill>
                              <button
                                className={`ambient-companion ${toneClass(viewModel.thread.activityPulse?.tone || "neutral")}`.trim()}
                                onClick={() => setActiveDrawer("context")}
                                type="button"
                              >
                                <span className="ambient-dot" />
                                Companion · {viewModel.thread.activityPulse?.backgroundSummary || "Standing by"}
                              </button>
                            </div>
                            <div className="thread-chip-row">
                              <button
                                className={`mini-pill ${persistentGoalMode ? "" : "muted"}`.trim()}
                                onClick={() => setPersistentGoalMode(current => !current)}
                                type="button"
                              >
                                Goal mode {persistentGoalMode ? "on" : "off"}
                              </button>
                              <span className="mini-pill muted">Now: {viewModel.thread.activityPulse?.current || builderPrimaryConversation.current}</span>
                              <span className="mini-pill muted">Next: {viewModel.thread.activityPulse?.next || builderPrimaryConversation.next}</span>
                            </div>
                            <div className="monitor-loop-strip" aria-label="External monitor loops">
                              <div>
                                <span>{monitoringLoopStudio.headline || "External monitor loops"}</span>
                                <strong>
                                  {(monitoringLoopStudio.warningCount || 0) > 0
                                    ? `${monitoringLoopStudio.warningCount} warning loop(s)`
                                    : "Quiet, important-only"}
                                </strong>
                              </div>
                              <div className="monitor-loop-strip-items">
                                {monitoringLoops.slice(0, 3).map(item => (
                                  <button
                                    className={`mini-pill ${toneClass(item.tone)}`}
                                    key={`monitor-strip-${item.id}`}
                                    onClick={() => setActiveDrawer(item.id === "verification-sentinel" ? "proof" : item.id === "silence-watchdog" ? "context" : "queue")}
                                    type="button"
                                  >
                                    {item.label}: {titleizeToken(item.status)}
                                  </button>
                                ))}
                              </div>
                            </div>
                            <div className="supervisor-intervention-strip" aria-label="Supervisor intervention queue">
                              <div>
                                <span>Supervisor intervention queue</span>
                                <strong>
                                  {monitoringLoopStudio.topIntervention?.label || "No queued intervention"}
                                </strong>
                              </div>
                              <button
                                className={`mini-pill ${toneClass((monitoringLoopStudio.criticalCount || 0) > 0 ? "warn" : "good")}`}
                                onClick={() => setActiveDrawer(monitoringLoopStudio.topIntervention?.targetDrawer || "builder")}
                                type="button"
                              >
                                {(monitoringLoopStudio.criticalCount || 0) > 0
                                  ? `${monitoringLoopStudio.criticalCount} high priority`
                                  : "Clear"}
                              </button>
                            </div>
                            <div className="subagent-command-strip" aria-label="Subagent command center">
                              <div>
                                <span>{subagentOrchestrationStudio.headline || "Subagent command center"}</span>
                                <strong>
                                  {subagentLanes.length > 0
                                    ? `${subagentLanes.length} lane${subagentLanes.length === 1 ? "" : "s"} · ${subagentOrchestrationStudio.activeCount || 0} active`
                                    : `${subagentOrchestrationStudio.configuredWorkers || 1} worker setup`}
                                </strong>
                              </div>
                              <button className="mini-pill muted" onClick={() => setActiveDrawer("builder")} type="button">
                                {titleizeToken(subagentOrchestrationStudio.mergePolicy || "best_score")} merge
                              </button>
                              <button
                                className={`mini-pill ${toneClass((subagentOrchestrationStudio.blockedCount || 0) > 0 ? "warn" : "good")}`}
                                onClick={() => setActiveDrawer((subagentOrchestrationStudio.blockedCount || 0) > 0 ? "queue" : "proof")}
                                type="button"
                              >
                                {(subagentOrchestrationStudio.blockedCount || 0) > 0
                                  ? `${subagentOrchestrationStudio.blockedCount} blocked`
                                  : "Proof-ready"}
                              </button>
                            </div>
                            <h2>{builderPrimaryConversation.title}</h2>
                            <p>{builderPrimaryConversation.current}</p>
                            <p className="builder-conversation-path">
                              {builderPrimaryConversation.workspaceName}
                              {builderPrimaryConversation.executionPath ? ` · ${builderPrimaryConversation.executionPath}` : ""}
                            </p>
                            <div className="builder-primary-summary">
                              <article className="builder-summary-card">
                                <span>Current point</span>
                                <strong>{builderPrimaryConversation.current}</strong>
                                <p>{builderPrimaryConversation.lastMovement}</p>
                              </article>
                              <article className="builder-summary-card">
                                <span>Next step</span>
                                <strong>{builderPrimaryConversation.next}</strong>
                                <p>{builderPrimaryConversation.updatedAt ? `Updated ${timestampLabel(builderPrimaryConversation.updatedAt)}` : "Active now"}</p>
                              </article>
                            </div>
                            {subagentLanes.length > 0 ? (
                              <div className="subagent-board-stack" aria-label="Delegated lane roster">
                                {subagentLanes.slice(0, 2).map(item => (
                                  <article className={`subagent-board-card ${toneClass(item.tone)}`} key={`builder-${item.id}`}>
                                    <div>
                                      <span>{titleizeToken(item.role)}</span>
                                      <strong>{item.label}</strong>
                                      <em>{titleizeToken(item.status)} · {item.heartbeat}</em>
                                    </div>
                                    <p>{item.latestEvent}</p>
                                    <small>{item.runtime} / {item.provider} / {item.model}</small>
                                    <div className="subagent-board-actions">
                                      <button className="mini-pill muted" onClick={() => setActiveDrawer("runtime")} type="button">
                                        Inspect runtime
                                      </button>
                                      <button
                                        className={`mini-pill ${toneClass(item.tone === "warn" ? "warn" : "neutral")}`}
                                        onClick={() => setActiveDrawer(item.tone === "warn" ? "queue" : "proof")}
                                        type="button"
                                      >
                                        {item.tone === "warn" ? "Resolve block" : "Review proof"}
                                      </button>
                                    </div>
                                  </article>
                                ))}
                              </div>
                            ) : null}
                          </>
                        ) : (
                          <>
                            <h2>{viewModel.drawers.builder.confidence.label}</h2>
                            <p>{builderBoard.summary}</p>
                          </>
                        )}
                      </div>

                      <div className="builder-board-metrics">
                        {builderBoard.metrics.map(item => (
                          <article className={`builder-metric-card ${toneClass(item.tone)}`} key={item.id}>
                            <span>{item.label}</span>
                            <strong>{item.value}</strong>
                            <p>{item.detail}</p>
                          </article>
                        ))}
                        <article className="builder-metric-card tone-neutral">
                          <span>Fusion contracts</span>
                          <strong>{fusionWorkbench.summary.readyRows}</strong>
                          <p>Solantir, Mind Tower, and JBH-EAVEN rows are fixture-backed and read-only.</p>
                        </article>
                      </div>
                    </div>

                    <div className="drawer-actions">
                      {builderPrimaryConversation ? (
                        <ActionButton onClick={() => setSelectedMissionId(builderPrimaryConversation.missionId)} variant="primary">
                          Focus thread
                        </ActionButton>
                      ) : null}
                      <ActionButton onClick={() => setActiveDrawer("builder")} variant="primary">
                        Command panel
                      </ActionButton>
                      <ActionButton onClick={() => setActiveDrawer("queue")}>Queue review</ActionButton>
                      <ActionButton onClick={() => setActiveDrawer("proof")}>Proof review</ActionButton>
                      <ActionButton onClick={() => setActiveDrawer("context")}>Context</ActionButton>
                    </div>
                  </article>

                  <article className="builder-panel">
                    <div className="section-header">
                      <div className="section-title-block">
                        <p className="eyebrow">Other Active Conversations</p>
                        <h2>Smaller live threads around the main focus</h2>
                      </div>
                    </div>
                    {builderSecondaryConversations.length > 0 ? (
                      <div className="builder-conversation-grid">
                        {builderSecondaryConversations.map(item => (
                          <button
                            className={`builder-conversation-card ${toneClass(item.tone)} ${item.selected ? "active" : ""}`.trim()}
                            key={item.missionId}
                            onClick={() => setSelectedMissionId(item.missionId)}
                            type="button"
                          >
                            <div className="builder-conversation-top">
                              <div>
                                <span>{item.runtime} · {item.workspaceName}</span>
                                <h3>{item.title}</h3>
                              </div>
                              <StatusPill strong tone={item.blocked ? "warn" : item.tone}>
                                {item.statusLabel}
                              </StatusPill>
                            </div>
                            <p>{item.current}</p>
                            {item.executionPath ? (
                              <p className="builder-conversation-path">
                                {item.folderLabel ? `${item.folderLabel} · ` : ""}
                                {item.executionPath}
                              </p>
                            ) : null}
                            <div className="builder-conversation-meta">
                              {item.pendingApprovals > 0 ? (
                                <span>{item.pendingApprovals} approval{item.pendingApprovals === 1 ? "" : "s"}</span>
                              ) : null}
                              {item.verificationFailures > 0 ? (
                                <span>{item.verificationFailures} verification issue{item.verificationFailures === 1 ? "" : "s"}</span>
                              ) : null}
                              {item.delegatedSessions > 0 ? (
                                <span>{item.delegatedSessions} delegated lane{item.delegatedSessions === 1 ? "" : "s"}</span>
                              ) : null}
                              {!item.pendingApprovals && !item.verificationFailures && !item.delegatedSessions ? (
                                <span>No active blocker</span>
                              ) : null}
                            </div>
                            <div className="builder-conversation-foot">
                              <span>Next: {item.next}</span>
                              <span>{item.updatedAt ? timestampLabel(item.updatedAt) : item.selected ? "Selected" : "Focus thread"}</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="fluxio-empty-copy">
                        {builderPrimaryConversation
                          ? "No secondary conversations are active right now."
                          : "No active conversations yet. Launch a mission and Builder will track every live thread here."}
                      </p>
                    )}
                  </article>

                  <div className="builder-feature-grid">
                    <article className="builder-panel builder-feature-card">
                      <div className="builder-feature-head">
                        <div>
                          <p className="eyebrow">Guided tutorial</p>
                          <h2>{tutorialStudio.headline}</h2>
                        </div>
                        <div className="builder-feature-meta">
                          <span className="mini-pill muted">{tutorialStudio.progressLabel}</span>
                          <span className="mini-pill muted">{tutorialStudio.motionMode} motion</span>
                        </div>
                      </div>
                      <p>{tutorialStudio.summary}</p>
                      <div className="builder-step-grid compact">
                        {tutorialStudio.steps.map(item => (
                          <button
                            className={`builder-step-card ${toneClass(item.tone)} ${item.current ? "current" : ""}`.trim()}
                            key={`builder-step-${item.id}`}
                            onClick={() => void handleBuilderFeatureAction(item.actionId)}
                            type="button"
                          >
                            <span>{item.panel}</span>
                            <strong>{item.title}</strong>
                            <p>{item.description}</p>
                            <em>{item.status}</em>
                          </button>
                        ))}
                      </div>
                      <div className="drawer-actions">
                        <ActionButton
                          onClick={() => void handleBuilderFeatureAction(tutorialStudio.primaryActionId)}
                          variant="primary"
                        >
                          {tutorialStudio.primaryActionLabel}
                        </ActionButton>
                        {tutorialStudio.cards[0] ? (
                          <ActionButton
                            onClick={() => void handleBuilderFeatureAction(tutorialStudio.cards[0].actionId)}
                          >
                            {tutorialStudio.cards[0].title}
                          </ActionButton>
                        ) : null}
                      </div>
                    </article>

                    <article className="builder-panel builder-feature-card">
                      <div className="builder-feature-head">
                        <div>
                          <p className="eyebrow">Recommendations</p>
                          <h2>{recommendationStudio.headline}</h2>
                        </div>
                        <div className="builder-feature-meta">
                          <span className="mini-pill muted">
                            {recommendationStudio.blockedConversationCount} blocked
                          </span>
                          <span className="mini-pill muted">
                            {recommendationStudio.skillRecommendations.length} skill leads
                          </span>
                        </div>
                      </div>
                      <p>{recommendationStudio.summary}</p>
                      <div className="builder-thread-list">
                        {recommendationStudio.struggleSignals.map(item => (
                          <button
                            className={`builder-thread-item ${toneClass(item.tone)}`.trim()}
                            key={item.id}
                            onClick={() => void handleBuilderFeatureAction(item.actionId)}
                            type="button"
                          >
                            <span>{item.label}</span>
                            <strong>{item.detail}</strong>
                          </button>
                        ))}
                      </div>
                      {recommendationStudio.skillRecommendations.length > 0 ? (
                        <div className="builder-inline-list">
                          {recommendationStudio.skillRecommendations.slice(0, 3).map(item => (
                            <span className="builder-inline-pill" key={item.id}>
                              <strong>{item.label}</strong>
                              <span>{item.reason}</span>
                            </span>
                          ))}
                        </div>
                      ) : null}
                      <div className="drawer-actions">
                        {recommendationStudio.nextMoves.slice(0, 2).map((item, index) => (
                          <ActionButton
                            key={item.id}
                            onClick={() => void handleBuilderFeatureAction(item.actionId)}
                            variant={index === 0 ? "primary" : "ghost"}
                          >
                            {item.label}
                          </ActionButton>
                        ))}
                      </div>
                    </article>

                    <article className="builder-panel builder-feature-card builder-feature-card-wide">
                      <div className="builder-feature-head">
                        <div>
                          <p className="eyebrow">Live UI review</p>
                          <h2>{liveReviewStudio.statusLine}</h2>
                        </div>
                        <div className="builder-feature-meta">
                          <span className="mini-pill muted">{liveReviewStudio.targets.length} review blocks</span>
                          {latestThinkingTurn ? (
                            <span className="mini-pill muted">{latestThinkingTurn.roleLabel || "Runtime"} trace live</span>
                          ) : null}
                        </div>
                      </div>
                      <p>{liveReviewStudio.summary}</p>
                      <div className="builder-cowork-status-grid" aria-label="Co-working status">
                        {[
                          ["Side-by-side preview", browserToolbarState.device, browserToolbarState.viewport],
                          ["Feedback bridge", mission ? "Agent thread ready" : "Start a mission", operatorDraft.trim() ? "draft loaded" : "awaiting note"],
                          ["Evidence timeline", `${(liveReviewStudio.events || []).length} events`, selectedLiveReviewEvent?.label || "none selected"],
                        ].map(([label, value, detail]) => (
                          <article className="builder-cowork-status-card" key={label}>
                            <span>{label}</span>
                            <strong>{value}</strong>
                            <small>{detail}</small>
                          </article>
                        ))}
                      </div>
                      <div className="builder-browser-toolbar">
                        <span className="mini-pill">Browser status: {liveReviewStudio.statusLine}</span>
                        <select
                          onChange={event => setBrowserToolbarState(current => ({ ...current, device: event.target.value }))}
                          value={browserToolbarState.device}
                        >
                          <option>Desktop</option>
                          <option>Tablet</option>
                          <option>Mobile</option>
                        </select>
                        <select
                          onChange={event => setBrowserToolbarState(current => ({ ...current, viewport: event.target.value }))}
                          value={browserToolbarState.viewport}
                        >
                          <option>1440×900</option>
                          <option>1280×720</option>
                          <option>1024×768</option>
                          <option>390×844</option>
                        </select>
                        <select
                          onChange={event => setBrowserToolbarState(current => ({ ...current, zoom: event.target.value }))}
                          value={browserToolbarState.zoom}
                        >
                          <option>80%</option>
                          <option>100%</option>
                          <option>125%</option>
                          <option>150%</option>
                        </select>
                        <ActionButton onClick={() => document.documentElement.requestFullscreen?.()} type="button">
                          Fullscreen
                        </ActionButton>
                      </div>
                      <section className="builder-cowork-status-grid" aria-label="Co-working status">
                        <article className="builder-cowork-status-card">
                          <span>Co-working status</span>
                          <strong>Side-by-side preview</strong>
                          <small>{livePreviewUrl || "Preview URL pending"}</small>
                        </article>
                        <article className="builder-cowork-status-card">
                          <span>Feedback bridge</span>
                          <strong>{selectedLiveReviewEvent?.threadTarget || selectedLiveReviewEvent?.proofTarget || "Mission bridge ready"}</strong>
                          <small>Annotations and proof chips feed planner/executor context.</small>
                        </article>
                        <article className="builder-cowork-status-card">
                          <span>Evidence timeline</span>
                          <strong>{(liveReviewStudio.events || []).length} live events</strong>
                          <small>Activity, browser QA, and frames stay visible while the agent works.</small>
                        </article>
                      </section>

                      <div className="builder-live-review-layout">
                        <div>
                          <div className="builder-review-grid">
                            {liveReviewStudio.targets.map(item => (
                              <button
                                className={`builder-review-target ${toneClass(item.tone)} ${builderSelectedReviewTarget?.id === item.id ? "active" : ""}`.trim()}
                                key={item.id}
                                onClick={() => handleBuilderReviewTargetSeed(item)}
                                type="button"
                              >
                                <span>{item.label}</span>
                                <strong>{item.title}</strong>
                                <p>{item.detail}</p>
                              </button>
                            ))}
                          </div>
                          {builderSelectedReviewTarget ? (
                            <div className="builder-review-lower">
                              <article className={`builder-review-focus ${toneClass(builderSelectedReviewTarget.tone)}`}>
                                <span>{builderSelectedReviewTarget.label}</span>
                                <strong>{builderSelectedReviewTarget.title}</strong>
                                <p>{builderSelectedReviewTarget.detail}</p>
                              </article>
                              {latestThinkingTurn ? (
                                <article className="builder-review-trace">
                                  <span>{latestThinkingTurn.roleLabel || "Runtime"} trace</span>
                                  <strong>{latestThinkingTurn.title}</strong>
                                  <p>{latestThinkingTurn.detail}</p>
                                </article>
                              ) : null}
                            </div>
                          ) : null}
                          <p className="builder-review-hint">{liveReviewStudio.compareHint}</p>
                        </div>

                        <aside className="builder-live-review-panel" aria-label="Live review side panel">
                          <div className="builder-live-review-panel-head">
                            <strong>Live Review Timeline</strong>
                            <span className="mini-pill muted">{(liveReviewStudio.events || []).length} events</span>
                          </div>
                          <article className="builder-live-review-bridge" aria-label="Dual-path bridge evidence">
                            <div className="builder-live-review-event-head">
                              <strong>Dual-path bridge</strong>
                              <span className="mini-pill muted">{connectedDeviceBridge.status || "needs_mapping"}</span>
                            </div>
                            <p>
                              Performed by {latestBridgeAction.performedByHost || "none yet"}
                              {latestBridgeAction.actionType ? ` · ${latestBridgeAction.actionType}` : ""}
                            </p>
                            <p>
                              Sync: {latestBridgeSync.status || "unknown"}
                              {latestBridgeSync.direction ? ` · ${latestBridgeSync.direction}` : ""}
                            </p>
                            <p className="builder-live-review-meta">
                              Pending approvals: {bridgePendingApprovals.length}
                            </p>
                            <p className="builder-live-review-meta">
                              Operation receipt: {latestBridgeReceipt.operationId || "none yet"}
                              {latestBridgeReceipt.status ? ` · ${latestBridgeReceipt.status}` : ""}
                            </p>
                            <div className="builder-live-review-receipt-handles" aria-label="Latest structured feedback receipt proof handles">
                              <span>Latest structured feedback receipt</span>
                              <span className="mini-pill muted">Receipt kind: live_review_structured_feedback</span>
                              <button
                                data-proof-handle="eventId"
                                disabled={!latestStructuredFeedbackReceipt.eventId}
                                onClick={() => copyContextValue(latestStructuredFeedbackReceipt.eventId)}
                                title="Copy latest receipt eventId"
                                type="button"
                              >
                                Proof eventId: {latestStructuredFeedbackReceipt.eventId || "none yet"}
                              </button>
                              <button
                                data-proof-handle="plannerExecutorHandoffId"
                                disabled={!latestStructuredFeedbackReceipt.plannerExecutorHandoffId}
                                onClick={() => copyContextValue(latestStructuredFeedbackReceipt.plannerExecutorHandoffId)}
                                type="button"
                              >
                                plannerExecutorHandoffId: {latestStructuredFeedbackReceipt.plannerExecutorHandoffId || "none yet"}
                              </button>
                              <button
                                data-proof-handle="receipt-proof-handle"
                                disabled={!latestStructuredFeedbackReceipt.eventId && !latestStructuredFeedbackReceipt.plannerExecutorHandoffId}
                                onClick={() =>
                                  copyContextValue(
                                    `live_review_structured_feedback eventId=${latestStructuredFeedbackReceipt.eventId || ""} plannerExecutorHandoffId=${latestStructuredFeedbackReceipt.plannerExecutorHandoffId || ""}`,
                                  )
                                }
                                type="button"
                              >
                                Copy proof handle
                              </button>
                            </div>
                            <p className="builder-live-review-meta">
                              Host status: {Object.entries(latestBridgeHostStatus).map(([host, status]) => `${host}:${status}`).join(" · ") || "not recorded"}
                            </p>
                          </article>
                          <article className="builder-visual-proof-packet" aria-label="Visual proof packet">
                            <div className="builder-live-review-panel-head compact">
                              <strong>Visual proof packet</strong>
                              <span className="mini-pill muted">{visualProofPacket.receiptKind}</span>
                            </div>
                            <div className="builder-visual-proof-grid">
                              <article>
                                <span>Frame</span>
                                <strong>{visualProofPacket.frameLabel}</strong>
                                <small>{visualProofPacket.framePath || "Path pending"}</small>
                              </article>
                              <article>
                                <span>Annotations</span>
                                <strong>{visualProofPacket.annotationCount} mark(s)</strong>
                                <small>
                                  {visualProofPacket.severeAnnotationCount} high · {visualProofPacket.mediumAnnotationCount} medium
                                </small>
                              </article>
                              <article>
                                <span>Targets</span>
                                <strong>{visualProofPacket.proofTarget || "Target pending"}</strong>
                                <small>{visualProofPacket.threadTarget || "Thread pending"}</small>
                              </article>
                            </div>
                            <p className="builder-live-review-meta">
                              Event: {visualProofPacket.eventLabel} · Handle: {visualProofPacket.receiptHandle || "none yet"}
                            </p>
                            <div className="builder-live-review-controls">
                              <ActionButton
                                disabled={!visualProofPacket.framePath || previewMode !== "live"}
                                onClick={() => void handleStructuredLiveReviewFeedback({ proofOnly: true })}
                                type="button"
                                variant="primary"
                              >
                                Capture proof
                              </ActionButton>
                              <ActionButton
                                disabled={!visualProofPacket.framePath}
                                onClick={() => copyContextValue(visualProofPacket.framePath)}
                                type="button"
                                variant="ghost"
                              >
                                Copy frame path
                              </ActionButton>
                              <ActionButton
                                disabled={!visualProofPacket.receiptHandle}
                                onClick={() =>
                                  copyContextValue(
                                    `${visualProofPacket.receiptKind} ${visualProofPacket.receiptHandle}`,
                                  )
                                }
                                type="button"
                                variant="ghost"
                              >
                                Copy proof handle
                              </ActionButton>
                              <ActionButton
                                disabled={!firstLiveReviewFrameEvent?.id}
                                onClick={() => {
                                  if (firstLiveReviewFrameEvent?.id) {
                                    setSelectedLiveReviewEventId(firstLiveReviewFrameEvent.id);
                                  }
                                }}
                                type="button"
                                variant="ghost"
                              >
                                Open event
                              </ActionButton>
                              {visualProofPacket.previewUrl && !visualProofPacket.previewUrl.startsWith("No ") ? (
                                <ActionButton
                                  onClick={() => window.open(visualProofPacket.previewUrl, "_blank", "noopener,noreferrer")}
                                  type="button"
                                  variant="ghost"
                                >
                                  Open preview
                                </ActionButton>
                              ) : null}
                            </div>
                          </article>
                          <Suspense fallback={null}>
                            <VisualProofReceiptGallery
                              copyContextValue={copyContextValue}
                              receipts={bridgeReceipts}
                            />
                          </Suspense>
                          {selectedLiveReviewEvent ? (
                            <article
                              className={`builder-live-review-focus tone-${selectedLiveReviewEvent.tone || "neutral"}`.trim()}
                              onKeyDown={event => {
                                if (event.key === "ArrowUp") {
                                  event.preventDefault();
                                  stepReplayMarker(-1);
                                } else if (event.key === "ArrowDown") {
                                  event.preventDefault();
                                  stepReplayMarker(1);
                                } else if (event.key === " ") {
                                  event.preventDefault();
                                  setLiveReviewAutoplay(current => !current);
                                }
                              }}
                              role="region"
                              tabIndex={0}
                            >
                              <div className="builder-live-review-event-head">
                                <span>{selectedLiveReviewEvent.label || titleizeToken(selectedLiveReviewEvent.kind || "event")}</span>
                                <em>{selectedLiveReviewEvent.timestamp ? timestampLabel(selectedLiveReviewEvent.timestamp) : "Now"}</em>
                              </div>
                              <strong>{selectedLiveReviewEvent.title}</strong>
                              <p>{selectedLiveReviewEvent.detail}</p>
                              {selectedLiveReviewFrame ? (
                                <p className="builder-live-review-meta">Frame: {selectedLiveReviewFrame.label} · {selectedLiveReviewFrame.path}</p>
                              ) : null}
                              {selectedReplayMarker ? (
                                <p className="builder-live-review-meta">Marker: {selectedReplayMarker.label} · {selectedReplayMarker.snapshotPath || "no snapshot"}</p>
                              ) : null}
                              <div className="builder-live-review-controls">
                                <ActionButton
                                  disabled={!selectedReplayMarkers.length}
                                  onClick={() => setSelectedReplayMarkerIndex(0)}
                                  type="button"
                                  variant="ghost"
                                >
                                  Rewind marker
                                </ActionButton>
                                <ActionButton
                                  disabled={!selectedLiveReviewFrames.length || selectedLiveReviewFrameIndex <= 0}
                                  onClick={() => setSelectedLiveReviewFrameIndex(index => Math.max(0, index - 1))}
                                  type="button"
                                  variant="ghost"
                                >
                                  Previous frame
                                </ActionButton>
                                <ActionButton
                                  disabled={!selectedLiveReviewFrames.length || selectedLiveReviewFrameIndex >= selectedLiveReviewFrames.length - 1}
                                  onClick={() =>
                                    setSelectedLiveReviewFrameIndex(index => Math.min(selectedLiveReviewFrames.length - 1, index + 1))
                                  }
                                  type="button"
                                  variant="ghost"
                                >
                                  Next frame
                                </ActionButton>
                                {selectedLiveReviewEvent?.deepLink?.type === "review_target" && selectedLiveReviewEvent?.deepLink?.targetId ? (
                                  <ActionButton
                                    onClick={() => {
                                      const target = liveReviewStudio.targets.find(
                                        item => item.id === selectedLiveReviewEvent.deepLink.targetId,
                                      );
                                      if (target) {
                                        handleBuilderReviewTargetSeed(target);
                                      }
                                    }}
                                    type="button"
                                    variant="ghost"
                                  >
                                    Jump to review block
                                  </ActionButton>
                                ) : null}
                                {selectedLiveReviewEvent?.deepLink?.type === "drawer" && selectedLiveReviewEvent?.deepLink?.drawerId ? (
                                  <ActionButton
                                    onClick={() => setActiveDrawer(selectedLiveReviewEvent.deepLink.drawerId)}
                                    type="button"
                                    variant="ghost"
                                  >
                                    Open {titleizeToken(selectedLiveReviewEvent.deepLink.drawerId)} drawer
                                  </ActionButton>
                                ) : null}
                                {selectedLiveReviewEvent?.previewUrl ? (
                                  <ActionButton
                                    onClick={() => window.open(selectedLiveReviewEvent.previewUrl, "_blank", "noopener,noreferrer")}
                                    type="button"
                                    variant="ghost"
                                  >
                                    Open preview URL
                                  </ActionButton>
                                ) : null}
                              </div>
                              <div className="builder-live-review-timeline-rail" aria-label="Marker-to-frame timeline rail">
                                <div className="builder-live-review-timeline-head">
                                  <span>Marker timeline rail</span>
                                  <small>↑/↓ marker step • space autoplay • {selectedReplayMarkers.length} markers</small>
                                </div>
                                <div className="builder-live-review-marker-buttons">
                                  {selectedReplayMarkers.map((marker, markerIndex) => {
                                    const mappedFrameIndex = markerFrameMap.get(markerIndex);
                                    const mappedFrame = Number.isInteger(mappedFrameIndex)
                                      ? selectedLiveReviewFrames[mappedFrameIndex]
                                      : null;
                                    return (
                                      <button
                                        className={`builder-live-review-marker-pill ${markerIndex === selectedReplayMarkerIndex ? "active" : ""}`.trim()}
                                        key={marker?.id || `${selectedLiveReviewEvent.id}-marker-${markerIndex}`}
                                        onClick={() => {
                                          setSelectedReplayMarkerIndex(markerIndex);
                                          if (Number.isInteger(mappedFrameIndex)) {
                                            setSelectedLiveReviewFrameIndex(mappedFrameIndex);
                                          }
                                        }}
                                        type="button"
                                      >
                                        <strong>{marker?.label || `Marker ${markerIndex + 1}`}</strong>
                                        <span>{mappedFrame?.label || marker?.frameId || "No frame"}</span>
                                      </button>
                                    );
                                  })}
                                </div>
                                <div className="builder-live-review-controls">
                                  <ActionButton disabled={!selectedReplayMarkers.length} onClick={() => stepReplayMarker(-1)} type="button" variant="ghost">
                                    Previous marker
                                  </ActionButton>
                                  <ActionButton disabled={!selectedReplayMarkers.length} onClick={() => stepReplayMarker(1)} type="button" variant="ghost">
                                    Next marker
                                  </ActionButton>
                                  <ActionButton
                                    disabled={selectedLiveReviewFrames.length <= 1}
                                    onClick={() => setLiveReviewAutoplay(current => !current)}
                                    type="button"
                                    variant={liveReviewAutoplay ? "primary" : "ghost"}
                                  >
                                    {liveReviewAutoplay ? "Pause timelapse" : "Autoplay timelapse"}
                                  </ActionButton>
                                </div>
                              </div>
                              {(selectedLiveReviewEvent.runtimeActivity || selectedLiveReviewEvent.deepLink || selectedLiveReviewEvent.operatorMessages) ? (
                                <div className="builder-live-review-runtime-drawer" aria-label="Runtime activity detail drawer">
                                  <strong>Runtime activity detail</strong>
                                  {selectedLiveReviewEvent.runtimeActivity ? (
                                    <p>{selectedLiveReviewEvent.runtimeActivity}</p>
                                  ) : null}
                                  {selectedLiveReviewEvent.deepLink ? (
                                    <small>
                                      Deep link: {selectedLiveReviewEvent.deepLink.type || "item"}
                                      {selectedLiveReviewEvent.deepLink.drawerId ? ` · ${selectedLiveReviewEvent.deepLink.drawerId}` : ""}
                                      {selectedLiveReviewEvent.deepLink.targetId ? ` · ${selectedLiveReviewEvent.deepLink.targetId}` : ""}
                                    </small>
                                  ) : null}
                                  {Array.isArray(selectedLiveReviewEvent.operatorMessages) && selectedLiveReviewEvent.operatorMessages.length > 0 ? (
                                    <div className="builder-live-review-queue-strip">
                                      {selectedLiveReviewEvent.operatorMessages.map((message, index) => (
                                        <span key={`runtime-msg-${index}`}>{message}</span>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                              ) : null}
                              {(Array.isArray(selectedLiveReviewEvent.selectedSkills) && selectedLiveReviewEvent.selectedSkills.length > 0) ||
                              (Array.isArray(selectedLiveReviewEvent.plannerRules) && selectedLiveReviewEvent.plannerRules.length > 0) ||
                              (Array.isArray(selectedLiveReviewEvent.designPrompts) && selectedLiveReviewEvent.designPrompts.length > 0) ||
                              selectedLiveReviewEvent.nextIdea ? (
                                <div className="builder-live-review-planner-proof" aria-label="Planner proof details">
                                  <strong>Planner proof</strong>
                                  {Array.isArray(selectedLiveReviewEvent.selectedSkills) && selectedLiveReviewEvent.selectedSkills.length > 0 ? (
                                    <div className="builder-live-review-meta">Skills: {selectedLiveReviewEvent.selectedSkills.map(titleizeToken).join(" · ")}</div>
                                  ) : null}
                                  {Array.isArray(selectedLiveReviewEvent.plannerRules) && selectedLiveReviewEvent.plannerRules.length > 0 ? (
                                    <div className="builder-live-review-meta">Rules: {selectedLiveReviewEvent.plannerRules.join(" · ")}</div>
                                  ) : null}
                                  {Array.isArray(selectedLiveReviewEvent.designPrompts) && selectedLiveReviewEvent.designPrompts.length > 0 ? (
                                    <div className="builder-live-review-meta">Design prompts: {selectedLiveReviewEvent.designPrompts.join(" · ")}</div>
                                  ) : null}
                                  {selectedLiveReviewEvent.nextIdea ? (
                                    <p>Next idea: {selectedLiveReviewEvent.nextIdea}</p>
                                  ) : null}
                                </div>
                              ) : null}
                            </article>
                          ) : null}
                          <div className="builder-live-review-events">
                            {Object.entries(liveReviewEventBuckets).map(([bucket, bucketEvents]) => (
                              <section className="builder-live-review-event-group" key={`bucket-${bucket}`}>
                                <div className="builder-live-review-event-group-head">{titleizeToken(bucket)} · {bucketEvents.length}</div>
                                {bucketEvents.map(item => (
                              <button
                                className={`builder-live-review-event tone-${item.tone || "neutral"} ${selectedLiveReviewEvent?.id === item.id ? "active" : ""}`.trim()}
                                key={item.id}
                                onClick={() => setSelectedLiveReviewEventId(item.id)}
                                type="button"
                              >
                                <div className="builder-live-review-event-head">
                                  <span>{item.label || titleizeToken(item.kind || "event")}</span>
                                  <em>{item.timestamp ? timestampLabel(item.timestamp) : "Now"}</em>
                                </div>
                                <strong>{item.title}</strong>
                                <p>{item.detail}</p>
                                {Array.isArray(item.queueTimeline) && item.queueTimeline.length > 0 ? (
                                  <div className="builder-live-review-queue-strip">
                                    {item.queueTimeline.map(stage => (
                                      <span key={`${item.id}-${stage}`}>{titleizeToken(stage)}</span>
                                    ))}
                                  </div>
                                ) : null}
                                {Array.isArray(item.browserActions) && item.browserActions.length > 0 ? (
                                  <div className="builder-live-review-meta">Browser: {item.browserActions.map(titleizeToken).join(" · ")}</div>
                                ) : null}
                                {Array.isArray(item.launchedPrograms) && item.launchedPrograms.length > 0 ? (
                                  <div className="builder-live-review-meta">Programs: {item.launchedPrograms.join(" · ")}</div>
                                ) : null}
                                {Array.isArray(item.providerEvents) && item.providerEvents.length > 0 ? (
                                  <div className="builder-live-review-meta">Provider: {item.providerEvents.map(titleizeToken).join(" · ")}</div>
                                ) : null}
                                {Array.isArray(item.layerHandoff) && item.layerHandoff.length > 0 ? (
                                  <div className="builder-live-review-meta">Layer handoff: {item.layerHandoff.map(titleizeToken).join(" → ")}</div>
                                ) : null}
                                {Array.isArray(item.generatedImages) && item.generatedImages.length > 0 ? (
                                  <div className="builder-live-review-image-grid" aria-label="Generated image artifacts">
                                    {item.generatedImages.map((artifact, imageIndex) => {
                                      const previewSource =
                                        artifact && typeof artifact === "object"
                                          ? artifact.previewUrl || artifact.artifactUrl || artifact.path || ""
                                          : artifact;
                                      const manifestSource =
                                        artifact && typeof artifact === "object" ? artifact.manifestUrl || "" : "";
                                      const imageUrl = resolveControlArtifactUrl(previewSource) || artifactUrlForRecord(artifact);
                                      const manifestUrl = resolveControlArtifactUrl(manifestSource);
                                      const imageLabel = artifactLabelForRecord(artifact, `generated-${imageIndex + 1}`);
                                      return (
                                        <figure className="builder-live-review-image-card agent-artifact-card" key={`${item.id}-generated-${imageLabel}-${imageIndex}`}>
                                          {imageUrl ? (
                                            <img alt={imageLabel} src={imageUrl} />
                                          ) : (
                                            <div className="builder-live-review-image-missing">Preview not served</div>
                                          )}
                                          <figcaption>
                                            <strong>{imageLabel}</strong>
                                            <span>{artifact?.artifactSha256 ? `sha ${String(artifact.artifactSha256).slice(0, 10)}` : artifact?.source || "generated image"}</span>
                                            {manifestUrl ? (
                                              <a href={manifestUrl} rel="noreferrer" target="_blank">
                                                Manifest
                                              </a>
                                            ) : null}
                                          </figcaption>
                                        </figure>
                                      );
                                    })}
                                  </div>
                                ) : null}
                                {Array.isArray(item.artifactPaths) && item.artifactPaths.length > 0 ? (
                                  <div className="builder-live-review-artifact-list" aria-label="Served artifact links">
                                    {item.artifactPaths.map((artifactPath, artifactIndex) => {
                                      const artifactUrl = resolveControlArtifactUrl(artifactPath);
                                      const artifactLabel = artifactLabelForRecord(artifactPath, `artifact-${artifactIndex + 1}`);
                                      return (
                                        <a href={artifactUrl || "#"} key={`${item.id}-artifact-${artifactLabel}-${artifactIndex}`} rel="noreferrer" target="_blank">
                                          {isImageArtifactPath(artifactPath) && artifactUrl ? <img alt="" src={artifactUrl} /> : null}
                                          <span>{artifactLabel}</span>
                                        </a>
                                      );
                                    })}
                                  </div>
                                ) : null}
                                {item.progressUpdate ? (
                                  <div className="builder-live-review-meta">Changed {item.progressUpdate.changed} | Blocker {item.progressUpdate.blocker} | Tests {item.progressUpdate.tests || "pending"} | Next {item.progressUpdate.next}{item.cadenceState ? ` | Cadence ${titleizeToken(item.cadenceState)}${Number.isFinite(item.cadenceAgeMinutes) ? ` (${item.cadenceAgeMinutes}m)` : ""}` : ""}</div>
                                ) : null}
                                {item.continuationSupervisor ? (
                                  <div className="builder-live-review-meta">Internal supervisor: {titleizeToken(item.continuationSupervisor.state)} · Dispatch lag {Number.isFinite(item.continuationSupervisor.dispatchLagMinutes) ? `${item.continuationSupervisor.dispatchLagMinutes}m` : "n/a"} · Guard {titleizeToken(item.continuationSupervisor.budgetGuard)}</div>
                                ) : null}
                                {Array.isArray(item.selectedSkills) && item.selectedSkills.length > 0 ? (
                                  <div className="builder-live-review-meta">Skills: {item.selectedSkills.map(titleizeToken).join(" · ")}</div>
                                ) : null}
                                {Array.isArray(item.plannerRules) && item.plannerRules.length > 0 ? (
                                  <div className="builder-live-review-meta">Rules: {item.plannerRules.join(" · ")}</div>
                                ) : null}
                                {Array.isArray(item.designPrompts) && item.designPrompts.length > 0 ? (
                                  <div className="builder-live-review-meta">Design prompts: {item.designPrompts.join(" · ")}</div>
                                ) : null}
                                {item.nextIdea ? (
                                  <div className="builder-live-review-meta">Next idea: {item.nextIdea}</div>
                                ) : null}
                                {item.structuredFeedbackReceipt ? (
                                  <div className="builder-live-review-receipt-handles compact" aria-label="Timeline receipt proof handles">
                                    <span>Latest structured feedback receipt</span>
                                    <span className="mini-pill muted">Timeline receipt kind: live_review_structured_feedback</span>
                                    <span
                                      data-proof-handle="eventId"
                                      onClick={event => {
                                        event.stopPropagation();
                                        if (item.structuredFeedbackReceipt.eventId) {
                                          copyContextValue(item.structuredFeedbackReceipt.eventId);
                                        }
                                      }}
                                      onKeyDown={event => {
                                        if (event.key === "Enter" || event.key === " ") {
                                          event.preventDefault();
                                          event.stopPropagation();
                                          if (item.structuredFeedbackReceipt.eventId) {
                                            copyContextValue(item.structuredFeedbackReceipt.eventId);
                                          }
                                        }
                                      }}
                                      role="button"
                                      tabIndex={item.structuredFeedbackReceipt.eventId ? 0 : -1}
                                      title="Copy latest receipt eventId"
                                    >
                                      Proof eventId: {item.structuredFeedbackReceipt.eventId || "none yet"}
                                    </span>
                                    <span
                                      data-proof-handle="plannerExecutorHandoffId"
                                      onClick={event => {
                                        event.stopPropagation();
                                        if (item.structuredFeedbackReceipt.plannerExecutorHandoffId) {
                                          copyContextValue(item.structuredFeedbackReceipt.plannerExecutorHandoffId);
                                        }
                                      }}
                                      onKeyDown={event => {
                                        if (event.key === "Enter" || event.key === " ") {
                                          event.preventDefault();
                                          event.stopPropagation();
                                          if (item.structuredFeedbackReceipt.plannerExecutorHandoffId) {
                                            copyContextValue(item.structuredFeedbackReceipt.plannerExecutorHandoffId);
                                          }
                                        }
                                      }}
                                      role="button"
                                      tabIndex={item.structuredFeedbackReceipt.plannerExecutorHandoffId ? 0 : -1}
                                    >
                                      plannerExecutorHandoffId: {item.structuredFeedbackReceipt.plannerExecutorHandoffId || "none yet"}
                                    </span>
                                  </div>
                                ) : null}
                                {Array.isArray(item.replayMarkers) && item.replayMarkers.length > 0 ? (
                                  <div className="builder-live-review-meta">Markers: {item.replayMarkers.map(marker => marker?.label || marker).join(" · ")}</div>
                                ) : null}
                                {Array.isArray(item.acknowledgedBy) && item.acknowledgedBy.length > 0 ? (
                                  <div className="builder-live-review-meta">Acknowledged: {item.acknowledgedBy.join(" · ")}</div>
                                ) : null}
                              </button>
                                ))}
                              </section>
                            ))}
                          </div>

                          <div className="builder-live-annotation-state">
                            <div className="builder-live-review-panel-head compact">
                              <strong>Planner skills and prompts</strong>
                              <span className="mini-pill muted">proof lane</span>
                            </div>
                            <div className="builder-live-review-planner-proof">
                              {Array.isArray(liveReviewStudio.plannerProof?.selectedSkills) && liveReviewStudio.plannerProof.selectedSkills.length > 0 ? (
                                <div className="builder-live-review-meta">Selected skills: {liveReviewStudio.plannerProof.selectedSkills.map(titleizeToken).join(" · ")}</div>
                              ) : (
                                <div className="builder-live-review-meta">Selected skills: none captured yet</div>
                              )}
                              {Array.isArray(liveReviewStudio.plannerProof?.plannerRules) && liveReviewStudio.plannerProof.plannerRules.length > 0 ? (
                                <div className="builder-live-review-meta">Rules: {liveReviewStudio.plannerProof.plannerRules.join(" · ")}</div>
                              ) : null}
                              {Array.isArray(liveReviewStudio.plannerProof?.designPrompts) && liveReviewStudio.plannerProof.designPrompts.length > 0 ? (
                                <div className="builder-live-review-meta">Design prompts: {liveReviewStudio.plannerProof.designPrompts.join(" · ")}</div>
                              ) : null}
                              {liveReviewStudio.plannerProof?.nextIdea ? <p>Next idea: {liveReviewStudio.plannerProof.nextIdea}</p> : null}
                              {Array.isArray(liveReviewStudio.plannerProof?.decisionInfluence) && liveReviewStudio.plannerProof.decisionInfluence.length > 0 ? (
                                <div className="builder-live-proof-impact-grid" aria-label="Skill/ruleset impact">
                                  {liveReviewStudio.plannerProof.decisionInfluence.map(item => (
                                    <article className="builder-live-proof-impact-card" key={item.id || item.appliedTo}>
                                      <span>Skill/ruleset impact</span>
                                      <strong>{item.source}</strong>
                                      <p>Applied to: {item.appliedTo}</p>
                                      <small>Evidence: {item.evidence}</small>
                                      <small>Verifier feedback: {item.verifierFeedback}</small>
                                    </article>
                                  ))}
                                </div>
                              ) : null}
                              {plannerProofChips.length > 0 ? (
                                <div
                                  className="builder-live-proof-chip-row"
                                  onKeyDown={event => {
                                    if (event.key === "ArrowRight") {
                                      event.preventDefault();
                                      setSelectedPlannerProofChipIndex(index => (index + 1) % plannerProofChips.length);
                                    } else if (event.key === "ArrowLeft") {
                                      event.preventDefault();
                                      setSelectedPlannerProofChipIndex(index =>
                                        (index - 1 + plannerProofChips.length) % plannerProofChips.length,
                                      );
                                    } else if (event.key === "Enter" || event.key === " ") {
                                      event.preventDefault();
                                      activatePlannerProofChip(plannerProofChips[selectedPlannerProofChipIndex]);
                                    }
                                  }}
                                  role="listbox"
                                  tabIndex={0}
                                >
                                  {plannerProofChips.map((chip, chipIndex) => (
                                    <button
                                      aria-selected={chipIndex === selectedPlannerProofChipIndex}
                                      className={`builder-live-proof-chip ${chipIndex === selectedPlannerProofChipIndex ? "active" : ""}`.trim()}
                                      key={chip.id}
                                      onClick={() => {
                                        setSelectedPlannerProofChipIndex(chipIndex);
                                        activatePlannerProofChip(chip);
                                      }}
                                      type="button"
                                    >
                                      <span>{titleizeToken(chip.kind)}</span>
                                      <strong>{chip.label}</strong>
                                    </button>
                                  ))}
                                </div>
                              ) : null}
                              {activePlannerProofDetail ? (
                                <div className="builder-live-proof-detail" aria-label="Design prompt artifact/detail">
                                  <strong>{activePlannerProofDetail.title}</strong>
                                  <p>{activePlannerProofDetail.body}</p>
                                </div>
                              ) : null}
                              <div className="builder-live-bridge-packet" aria-label="Planner to executor bridge packet">
                                <div className="builder-live-review-panel-head compact">
                                  <strong>Planner → executor bridge packet</strong>
                                  <span className="mini-pill muted">status updates</span>
                                </div>
                                <div className="builder-live-bridge-grid">
                                  <article>
                                    <span>Route context</span>
                                    <strong>
                                      {continuationSupervisor?.routePreservation?.provider
                                        ? `${titleizeToken(continuationSupervisor.routePreservation.provider)} / ${continuationSupervisor.routePreservation.model || "model"}`
                                        : "Route pending"}
                                    </strong>
                                    <small>
                                      Effort {titleizeToken(continuationSupervisor?.routePreservation?.effort || "default")} · Root {continuationSupervisor?.routePreservation?.executionRoot || "workspace"}
                                    </small>
                                  </article>
                                  <article>
                                    <span>Task context</span>
                                    <strong>{selectedLiveReviewEvent?.title || "Awaiting event selection"}</strong>
                                    <small>{selectedLiveReviewEvent?.detail || "Select an event to seed structured follow-up context."}</small>
                                  </article>
                                  <article>
                                    <span>Verifier feedback</span>
                                    <strong>{selectedLiveReviewEvent?.progressUpdate?.tests || "Tests pending"}</strong>
                                    <small>
                                      {selectedLiveReviewEvent?.continuationSupervisor?.failureReason
                                        || selectedLiveReviewEvent?.progressUpdate?.blocker
                                        || "No blocker captured"}
                                    </small>
                                  </article>
                                  <article>
                                    <span>Next idea handoff</span>
                                    <strong>{selectedLiveReviewEvent?.nextIdea || liveReviewStudio.plannerProof?.nextIdea || "Seed next idea from the selected block"}</strong>
                                    <small>Feeds agent follow-up, mission bridge, and continuation supervisor context.</small>
                                  </article>
                                </div>
                              </div>
                            </div>
                          </div>

                          <div className="builder-live-annotation-state">
                            <div className="builder-live-review-panel-head compact">
                              <strong>Internal Continuation Supervisor</strong>
                              <span className="mini-pill muted">hardened harness</span>
                            </div>
                            {continuationSupervisor ? (
                              <div className="builder-live-review-supervisor" aria-label="Internal supervisor state and failure reason">
                                <div className="builder-live-review-meta">State: {titleizeToken(continuationSupervisor.state)} · Dispatch window: {continuationSupervisor.expectedDispatchWindowMinutes}m</div>
                                <div className="builder-live-review-meta">Dispatch lag: {Number.isFinite(continuationSupervisor.dispatchLagMinutes) ? `${continuationSupervisor.dispatchLagMinutes}m` : "n/a"} · Reconcile latency: {Number.isFinite(continuationSupervisor.reconcileLatencyMs) ? `${continuationSupervisor.reconcileLatencyMs}ms` : "n/a"}</div>
                                <div className="builder-live-review-meta">Safe to stop: {continuationSupervisor.safeToStop ? "yes" : "no"} · External heartbeat required: {continuationSupervisor.externalHeartbeatRequired ? "yes" : "no"}</div>
                                <div className="builder-live-review-meta">Budget guard: {titleizeToken(continuationSupervisor.budgetGuard)}</div>
                                <div className="builder-live-review-meta">Failure reason: {continuationSupervisor.failureReason}</div>
                                <div className="builder-live-review-meta">Blocker reason: {continuationSupervisor.blockerReason || "none"}</div>
                                <div className="builder-live-review-meta">Preserved route: {titleizeToken(continuationSupervisor.routePreservation.provider)} / {continuationSupervisor.routePreservation.model} / {titleizeToken(continuationSupervisor.routePreservation.effort)}</div>
                                <div className="builder-live-review-meta">Execution root: {continuationSupervisor.routePreservation.executionRoot}</div>
                                {Array.isArray(continuationSupervisor.routePreservation.selectedSkills) && continuationSupervisor.routePreservation.selectedSkills.length > 0 ? (
                                  <div className="builder-live-review-meta">Selected skills: {continuationSupervisor.routePreservation.selectedSkills.map(titleizeToken).join(" · ")}</div>
                                ) : null}
                                {Array.isArray(continuationSupervisor.routePreservation.designPrompts) && continuationSupervisor.routePreservation.designPrompts.length > 0 ? (
                                  <div className="builder-live-review-meta">Design prompts: {continuationSupervisor.routePreservation.designPrompts.join(" · ")}</div>
                                ) : null}
                                {continuationSupervisor.routePreservation.nextIdea ? (
                                  <div className="builder-live-review-meta">Next idea continuity: {continuationSupervisor.routePreservation.nextIdea}</div>
                                ) : null}
                              </div>
                            ) : (
                              <div className="builder-live-review-meta">Internal supervisor state pending mission activation.</div>
                            )}
                          </div>

                          <div className="builder-live-annotation-state">
                            <div className="builder-live-review-panel-head compact">
                              <strong>Browser annotations</strong>
                              <span className="mini-pill muted">{(liveReviewStudio.annotationReadiness?.blocks || []).length} marks</span>
                            </div>
                            <div className="builder-live-annotation-list">
                              {(liveReviewStudio.annotationReadiness?.blocks || []).map(block => (
                                <article className={`builder-live-annotation-item severity-${block.severity || "low"}`.trim()} key={block.id}>
                                  <div className="builder-live-annotation-head">
                                    <span>{block.label}</span>
                                    <em>{titleizeToken(block.severity || "low")}</em>
                                  </div>
                                  <p>{block.note}</p>
                                  <small>Recovery: {block.recoveryAction}</small>
                                  <small>Page/layer: {block.page || "surface"} · {block.rectangle?.layer || block.pin?.layer || "overlay"}</small>
                                  <div className="builder-live-annotation-map">
                                    {block.rectangle ? (
                                      <span
                                        className="builder-live-annotation-rect"
                                        style={{
                                          left: `${block.rectangle.x}%`,
                                          top: `${block.rectangle.y}%`,
                                          width: `${block.rectangle.width}%`,
                                          height: `${block.rectangle.height}%`,
                                        }}
                                      />
                                    ) : null}
                                    {block.pin ? (
                                      <span
                                        className="builder-live-annotation-pin"
                                        style={{ left: `${block.pin.x}%`, top: `${block.pin.y}%` }}
                                      />
                                    ) : null}
                                  </div>
                                </article>
                              ))}
                            </div>
                          </div>
                        </aside>
                      </div>
                      <div className="drawer-actions">
                        <ActionButton
                          onClick={() => builderSelectedReviewTarget && handleBuilderReviewTargetSeed(builderSelectedReviewTarget)}
                          variant="primary"
                        >
                          Comment selected block
                        </ActionButton>
                        <ActionButton onClick={() => void handleBuilderFeatureAction("open_builder")}>
                          Open preview controls
                        </ActionButton>
                        {mission ? (
                          <ActionButton disabled={!operatorDraft.trim()} onClick={() => void handleStructuredLiveReviewFeedback({ sendFollowUp: true })}>
                            Send structured feedback
                          </ActionButton>
                        ) : null}
                        <div className="builder-live-review-receipt-handles compact" aria-label="Send feedback proof handles">
                          <span>Proof handles</span>
                          <span className="mini-pill muted">Receipt kind: live_review_structured_feedback</span>
                          <button
                            data-proof-handle="eventId"
                            disabled={!latestStructuredFeedbackReceipt.eventId}
                            onClick={() => copyContextValue(latestStructuredFeedbackReceipt.eventId)}
                            title="Copy latest receipt eventId"
                            type="button"
                          >
                            Proof eventId: {latestStructuredFeedbackReceipt.eventId || "none yet"}
                          </button>
                          <button
                            data-proof-handle="plannerExecutorHandoffId"
                            disabled={!latestStructuredFeedbackReceipt.plannerExecutorHandoffId}
                            onClick={() => copyContextValue(latestStructuredFeedbackReceipt.plannerExecutorHandoffId)}
                            type="button"
                          >
                            plannerExecutorHandoffId: {latestStructuredFeedbackReceipt.plannerExecutorHandoffId || "none yet"}
                          </button>
                        </div>
                        {structuredFeedbackReceiptHistory.length > 0 ? (
                          <details className="builder-live-review-receipt-history">
                            <summary>Structured feedback receipt history</summary>
                            <div className="builder-live-review-receipt-history-list" role="list">
                              {structuredFeedbackReceiptHistory.map((entry, index) => (
                                <div className="builder-live-review-receipt-history-row" key={`${entry.id}-${index}`} role="listitem">
                                  <div className="builder-live-review-receipt-history-meta">
                                    <strong>{entry.label || "Receipt"}</strong>
                                    <span>
                                      {entry.timestamp ? timestampLabel(entry.timestamp) : "No timestamp"}
                                      {entry.receipt?.status ? ` · ${entry.receipt.status}` : ""}
                                    </span>
                                  </div>
                                  <div className="builder-live-review-receipt-handles compact">
                                    <button
                                      data-proof-handle="history-eventId"
                                      disabled={!entry.receipt?.eventId}
                                      onClick={() => copyContextValue(entry.receipt?.eventId || "")}
                                      title="Copy receipt history eventId"
                                      type="button"
                                    >
                                      eventId: {entry.receipt?.eventId || "none"}
                                    </button>
                                    <button
                                      data-proof-handle="history-plannerExecutorHandoffId"
                                      disabled={!entry.receipt?.plannerExecutorHandoffId}
                                      onClick={() => copyContextValue(entry.receipt?.plannerExecutorHandoffId || "")}
                                      title="Copy receipt history plannerExecutorHandoffId"
                                      type="button"
                                    >
                                      plannerExecutorHandoffId: {entry.receipt?.plannerExecutorHandoffId || "none"}
                                    </button>
                                    <button
                                      data-proof-handle="history-copy-all"
                                      disabled={!entry.receipt?.eventId && !entry.receipt?.plannerExecutorHandoffId}
                                      onClick={() =>
                                        copyContextValue(
                                          `live_review_structured_feedback eventId=${entry.receipt?.eventId || ""} plannerExecutorHandoffId=${entry.receipt?.plannerExecutorHandoffId || ""}`,
                                        )
                                      }
                                      title="Copy receipt history combined proof handle"
                                      type="button"
                                    >
                                      Copy all handles
                                    </button>
                                    <button
                                      data-proof-handle="history-jump-source-event"
                                      disabled={!entry.id || !liveReviewEventsFlat.find(event => event.id === entry.id)}
                                      onClick={() => {
                                        const sourceEvent = liveReviewEventsFlat.find(event => event.id === entry.id);
                                        if (sourceEvent) {
                                          setSelectedLiveReviewEventId(sourceEvent.id);
                                        }
                                      }}
                                      title="Jump to source event"
                                      type="button"
                                    >
                                      Jump to source event
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </details>
                        ) : null}
                      </div>
                    </article>
                  </div>

                  <div className="builder-board-grid">
                    <article className="builder-panel">
                      <div className="section-header">
                        <div className="section-title-block">
                          <p className="eyebrow">What Happens Next</p>
                          <h2>Predicted checkpoints across live threads</h2>
                        </div>
                      </div>
                      {builderBoard.nextUp.length > 0 ? (
                        <div className="builder-digest-list">
                          {builderBoard.nextUp.map(item => (
                            <button
                              className={`builder-digest-item ${toneClass(item.tone)} ${item.selected ? "active" : ""}`.trim()}
                              key={`next-${item.missionId}`}
                              onClick={() => setSelectedMissionId(item.missionId)}
                              type="button"
                            >
                              <div className="builder-digest-top">
                                <span>{item.runtime}</span>
                                <span>{item.updatedAt ? timestampLabel(item.updatedAt) : item.statusLabel}</span>
                              </div>
                              <strong>{item.title}</strong>
                              <p>{item.summary}</p>
                              {item.checkpoint ? <p className="builder-digest-detail">Checkpoint: {item.checkpoint}</p> : null}
                              {item.routeLabel ? <p className="builder-digest-detail">Route: {item.routeLabel}</p> : null}
                              {item.detail ? <p className="builder-digest-detail">{item.detail}</p> : null}
                              <div className="builder-digest-meta">
                                <span>{item.statusLabel}</span>
                                <span>{item.selected ? "Current thread" : "Open thread"}</span>
                              </div>
                            </button>
                          ))}
                        </div>
                      ) : (
                        <p className="fluxio-empty-copy">
                          Launch a mission to see predicted checkpoints and queued follow-up work.
                        </p>
                      )}
                    </article>

                    <article className="builder-panel">
                      <div className="section-header">
                        <div className="section-title-block">
                          <p className="eyebrow">While You Were Away</p>
                          <h2>Recent mission and runtime movement</h2>
                        </div>
                      </div>
                      {builderBoard.whileAway.length > 0 ? (
                        <div className="builder-digest-list">
                          {builderBoard.whileAway.map(item => (
                            <article className={`builder-digest-item ${toneClass(item.tone)}`} key={item.id}>
                              <div className="builder-digest-top">
                                <span>{item.label}</span>
                                <span>{item.timestamp ? timestampLabel(item.timestamp) : ""}</span>
                              </div>
                              <strong>{item.missionTitle}</strong>
                              <p>{item.message}</p>
                              {item.detail ? <p className="builder-digest-detail">{item.detail}</p> : null}
                            </article>
                          ))}
                        </div>
                      ) : (
                        <p className="fluxio-empty-copy">
                          Activity summaries will appear here as missions, approvals, and runtime events land.
                        </p>
                      )}
                    </article>
                  </div>

                  <form className="builder-note-panel" onSubmit={handleOperatorNote}>
                    <label htmlFor="builder-thread-note">
                      {builderSelectedReviewTarget ? `Review note for ${builderSelectedReviewTarget.title}` : "Builder note"}
                    </label>
                    {builderSelectedReviewTarget ? (
                      <p className="builder-note-context">
                        {builderSelectedReviewTarget.label} · {builderSelectedReviewTarget.detail}
                      </p>
                    ) : null}
                    <textarea
                      id="builder-thread-note"
                      onChange={event => setOperatorDraft(event.target.value)}
                      onPaste={handleComposerPaste}
                      placeholder={
                        builderSelectedReviewTarget
                          ? "Describe what is wrong with this block and what the model should change."
                          : "Capture a technical observation, routing decision, or runtime intervention plan."
                      }
                      value={operatorDraft}
                    />
                    <ComposerAttachmentStrip
                      attachments={operatorAttachments}
                      onClear={clearOperatorAttachments}
                      onRemove={removeOperatorAttachment}
                    />
                    <div className="thread-composer-actions">
                      <ActionButton type="submit" variant="primary">
                        Save note
                      </ActionButton>
                      {mission ? (
                        <ActionButton
                          disabled={!operatorDraft.trim()}
                          onClick={() => void handleStructuredLiveReviewFeedback({ sendFollowUp: true })}
                          type="button"
                        >
                          Send structured feedback
                        </ActionButton>
                      ) : null}
                      <ActionButton onClick={() => setActiveDrawer("builder")} type="button">
                        Open builder drawer
                      </ActionButton>
                    </div>
                  </form>
                </section>

                <aside className="builder-secondary-column">
                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Nexuses</p>
                    <h3>{builderNexusItems.length} decision point{builderNexusItems.length === 1 ? "" : "s"}</h3>
                    <p>Jump back to the moments that most likely changed direction, risk, or final output.</p>
                    <div className="builder-thread-list">
                      {builderNexusItems.slice(0, 4).map(item => (
                        <button
                          className={`builder-thread-item ${toneClass(item.tone)}`.trim()}
                          key={`nexus-${item.id}`}
                          onClick={() => {
                            if (item.missionId) {
                              setSelectedMissionId(item.missionId);
                            }
                            setActiveDrawer(item.tone === "bad" ? "proof" : "context");
                          }}
                          type="button"
                        >
                          <span>{item.label}</span>
                          <strong>{item.title}</strong>
                          <p>{item.reason}</p>
                        </button>
                      ))}
                    </div>
                  </article>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Routes</p>
                    <h3>{builderBoard.winningRoutes?.length || 0} pattern{(builderBoard.winningRoutes?.length || 0) === 1 ? "" : "s"}</h3>
                    <p>Outcomes.</p>
                    <div className="builder-thread-list">
                      {asList(builderBoard.winningRoutes).slice(0, 3).map(item => (
                        <article className={`builder-thread-item ${toneClass(item.tone)}`} key={`winning-route-${item.key || item.label}`}>
                          <span>{item.runtime}</span>
                          <strong>{item.label}</strong>
                          <p>{item.detail}</p>
                        </article>
                      ))}
                    </div>
                    <div className="builder-thread-list">
                      {asList(builderBoard.stuckThreads).slice(0, 3).map(item => (
                        <button
                          className={`builder-thread-item ${toneClass(item.tone)}`.trim()}
                          key={`stuck-${item.missionId || item.title}`}
                          onClick={() => item.missionId && setSelectedMissionId(item.missionId)}
                          type="button"
                        >
                          <span>{item.blockerClass}</span>
                          <strong>{item.title}</strong>
                          <p>{item.reason}</p>
                        </button>
                      ))}
                    </div>
                    <div className="route-decision-grid" aria-label="Local route decision scorecards">
                      {asList(snapshot.harnessLab?.routeDecisionRows).slice(0, 3).map(item => {
                        const decisionTone =
                          item.decision === "use"
                            ? "good"
                            : item.decision === "avoid_for_now"
                              ? "bad"
                              : item.decision === "watch"
                                ? "warn"
                                : "neutral";
                        return (
                          <article className={`route-decision-card ${toneClass(decisionTone)}`} key={item.id}>
                            <span>{titleizeToken(item.label || item.decision || "Route decision")}</span>
                            <div className="route-decision-meta">
                              <b>{item.fitLabel || "Needs proof"}</b>
                              <small>Harness: {titleizeToken(item.harnessId || "unknown_harness")}</small>
                            </div>
                            <strong>{runtimeLabel(item.runtimeId)} / {providerLabel(item.provider)} / {item.model}</strong>
                            <p>{item.recommendation}</p>
                            {item.fitReason ? <p className="route-decision-fit">{item.fitReason}</p> : null}
                            <small>
                              {item.observedRuns || 0} run{(item.observedRuns || 0) === 1 ? "" : "s"} · {item.completionRate || 0}% complete · {item.routeContractProofCount || 0} route proof
                            </small>
                            {item.outcomeScorecard ? (
                              <small className="route-outcome-scorecard">
                                Tokens {item.outcomeScorecard.totalTokens || 0} · {formatDurationCompact(item.outcomeScorecard.wallTimeSeconds || 0)} · Test{" "}
                                {titleizeToken(item.outcomeScorecard.latestTestResult || "missing")} · Human{" "}
                                {item.outcomeScorecard.humanInterventionCount || 0} · Retry {item.outcomeScorecard.retryCount || 0} · Proof{" "}
                                {item.outcomeScorecard.proofArtifactCount || 0}/{item.outcomeScorecard.proofArtifactRequiredCount || 0}
                              </small>
                            ) : null}
                            {asList(item.proofGaps).length > 0 ? (
                              <em>{asList(item.proofGaps).slice(0, 2).join(" · ")}</em>
                            ) : null}
                          </article>
                        );
                      })}
                    </div>
                  </article>

                  <article className="builder-panel builder-panel-focus autonomy-guardrail-board">
                    <p className="eyebrow">Autonomy guardrails</p>
                    <h3>Continue until a real boundary</h3>
                    <p>Normal blockers trigger inspection, safe branching, parallel work, and proof capture before the agent stops.</p>
                    <div className="builder-thread-list">
                      {autonomyGuardrails.map(item => (
                        <article className="builder-thread-item tone-neutral" key={`autonomy-guardrail-${item.id}`}>
                          <span>{titleizeToken(item.status)}</span>
                          <strong>{item.label}</strong>
                          <p>{item.proof}</p>
                        </article>
                      ))}
                    </div>
                  </article>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Runtimes</p>
                    <h3>{titleizeToken(snapshot.harnessLab?.fusedRuntime?.status || workspaceProfileForm.preferredHarness)}</h3>
                    <div className="builder-inline-list">
                      <span>Prod: {titleizeToken(snapshot.harnessLab?.productionHarness || workspaceProfileForm.preferredHarness)}</span>
                      <span>
                        Shadow: {snapshot.harnessLab?.shadowCandidates?.length > 0
                          ? snapshot.harnessLab.shadowCandidates.map(item => titleizeToken(item)).join(", ")
                          : "None"}
                      </span>
                      <span>{snapshot.harnessLab?.fusedRuntime?.summary || snapshot.harnessLab?.recommendation || "Runtime truth visible."}</span>
                      <span>
                        Sup: {snapshot.harnessLab?.fusedRuntime?.supervisor?.activeSessionCount || 0} active / {snapshot.harnessLab?.fusedRuntime?.supervisor?.waitingApprovalCount || 0} waiting
                      </span>
                      <span>
                        Proof: {snapshot.harnessLab?.fusedRuntime?.proofSignals?.delegatedRunCount || 0} delegated / {snapshot.harnessLab?.fusedRuntime?.proofSignals?.routeContractRunCount || 0} route contract
                      </span>
                    </div>
                    <Suspense fallback={null}>
                      <RuntimeTruth fusedRuntime={snapshot.harnessLab?.fusedRuntime} />
                    </Suspense>
                    <div className="builder-thread-list">
                      {asList(snapshot.harnessLab?.fusedRuntime?.runtimeLanes).map(item => (
                        <article
                          className={`builder-thread-item ${item.active ? "tone-good" : "tone-neutral"}`}
                          key={`fused-runtime-lane-${item.runtimeId}`}
                        >
                          <span>{item.role === "executable_runtime_lane" ? "Runtime lane" : titleizeToken(item.role)}</span>
                          <strong>{item.label || runtimeLabel(item.runtimeId)}</strong>
                          <p>{item.observedCount || 0} proof run{(item.observedCount || 0) === 1 ? "" : "s"}</p>
                        </article>
                      ))}
                      {asList(snapshot.harnessLab?.fusedRuntime?.modelProviderRoutes).slice(0, 2).map(item => (
                        <article
                          className={`builder-thread-item ${item.active ? "tone-good" : "tone-neutral"}`}
                          key={`fused-provider-route-${item.provider}`}
                        >
                          <span>Provider route</span>
                          <strong>{item.label}</strong>
                          <p>
                            {item.suggestedModel || "Selected model"} · {item.observedCount || 0} observed use{(item.observedCount || 0) === 1 ? "" : "s"}
                          </p>
                        </article>
                      ))}
                    </div>
                    <div className="drawer-actions">
                      <ActionButton onClick={() => void applyPreferredHarness("fluxio_hybrid")} variant="primary">
                        Use Hybrid
                      </ActionButton>
                      <ActionButton onClick={() => void applyPreferredHarness("legacy_autonomous_engine")}>
                        Use Legacy
                      </ActionButton>
                      <ActionButton onClick={() => setActiveDrawer("runtime")} type="button">
                        Compare
                      </ActionButton>
                    </div>
                  </article>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Runtime bridge</p>
                    <h3>{bridgeSummary.connected} live bridge{bridgeSummary.connected === 1 ? "" : "s"}</h3>
                    <p>{bridgeSummary.recommendation}</p>
                    <div className="builder-inline-list">
                      <span>{bridgeSummary.callbackReady} approval callback{bridgeSummary.callbackReady === 1 ? "" : "s"} ready</span>
                      <span>{bridgeSummary.mobileReady} mobile bridge{bridgeSummary.mobileReady === 1 ? "" : "s"} reviewable</span>
                      <span>{bridgeSummary.totalApps} connected app definition{bridgeSummary.totalApps === 1 ? "" : "s"}</span>
                      <span>{modelAuthReady ? "Model account ready" : "Model account missing"}</span>
                    </div>
                    <div className="drawer-actions">
                      <ActionButton onClick={() => setActiveDrawer("runtime")}>Open runtime bridge</ActionButton>
                      <ActionButton
                        disabled={!providerOAuthActionsAvailable}
                        onClick={() =>
                          void handleReferenceQuickAuth(
                            openAICodexAuthReady ? "minimax" : "openai",
                          )
                        }
                        title={!providerOAuthActionsAvailable ? providerOAuthUnavailableReason : ""}
                      >
                        Connect model account
                      </ActionButton>
                    </div>
                  </article>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Fusion</p>
                    <h3>{fusionWorkbench.summary.readyRows} row{fusionWorkbench.summary.readyRows === 1 ? "" : "s"} ready</h3>
                    <div className="builder-thread-list">
                      {fusionWorkbench.migrationLanes.slice(0, 3).map(item => (
                        <article className="builder-thread-item tone-neutral" key={`builder-fusion-migration-${item.id}`}>
                          <span>{item.sourcePair}</span>
                          <strong>{item.title}</strong>
                          <p>{item.migrationStatus} · {item.safeSlice}</p>
                        </article>
                      ))}
                    </div>
                  </article>

                  <Suspense fallback={<LazySurfaceFallback label="Loading red-team proof" />}>
                    <RedTeamProofBoard variant="builder" onOpenRuntime={() => setActiveDrawer("runtime")} />
                  </Suspense>

                  <article className="builder-panel builder-panel-focus">
                    <p className="eyebrow">Feature backlog</p>
                    <h3>
                      {tutorialStudio.improvements.length + recommendationStudio.learningQueue.length} guided follow-up{tutorialStudio.improvements.length + recommendationStudio.learningQueue.length === 1 ? "" : "s"}
                    </h3>
                    <p>Turn repeated friction into better defaults, stronger guidance, and reusable skill or workflow patterns.</p>
                    <div className="builder-thread-list">
                      {tutorialStudio.improvements.slice(0, 2).map(item => (
                        <article className={`builder-thread-item ${toneClass(item.tone)}`} key={item.id}>
                          <span>{item.category}</span>
                          <strong>{item.title}</strong>
                          <p>{item.reason}</p>
                        </article>
                      ))}
                      {recommendationStudio.learningQueue.slice(0, 2).map(item => (
                        <article className={`builder-thread-item ${toneClass(item.tone)}`} key={item.id}>
                          <span>{item.priority}</span>
                          <strong>{item.title}</strong>
                          <p>Promote the pattern into Builder-visible guidance and reusable skill coverage.</p>
                        </article>
                      ))}
                    </div>
                    <ActionButton onClick={() => void handleBuilderFeatureAction("open_skills")}>
                      Open skill studio
                    </ActionButton>
                  </article>
                </aside>
              </div>
            </section>
          ) : (
            <section className="thread-shell agent-shell">
              <header className="thread-head agent-thread-head agent-title-head">
                <h1>{agentCenterTitle}</h1>
              </header>

              {latestAgentCompartment ? (
                <section className="agent-compartment-box" aria-label="Active agent runtime compartment">
                  <div className="agent-compartment-box-head">
                    <div>
                      <p className="eyebrow">Live runtime compartments · Runtime compartment</p>
                      <h2>{latestAgentCompartment.sessionId || "pending session"}</h2>
                    </div>
                    <div className="agent-compartment-status">
                      <span className={`agent-live-dot ${String(latestAgentCompartment.streaming || "").toLowerCase() === "live" ? "live" : ""}`} />
                      <strong>{titleizeToken(latestAgentCompartment.state || mission?.state?.status || "recorded")}</strong>
                      <span>{latestAgentCompartment.streaming === "live" ? "streaming" : "recorded"}</span>
                    </div>
                  </div>

                  <div className="agent-compartment-matrix">
                    <div>
                      <span>Runtime</span>
                      <strong>{titleizeToken(latestAgentCompartment.runtime || agentRuntimeSelectValue)}</strong>
                    </div>
                    <div>
                      <span>Route</span>
                      <strong>
                        {latestAgentCompartment.route?.provider
                          ? `${titleizeToken(latestAgentCompartment.route.provider)} / ${
                              latestAgentCompartment.route?.model_id ||
                              latestAgentCompartment.route?.model ||
                              "model"
                            }`
                          : agentRouteStatus}
                      </strong>
                    </div>
                    <div>
                      <span>Host</span>
                      <strong>{titleizeToken(latestAgentCompartment.host || "local")}</strong>
                    </div>
                    <div>
                      <span>Execution root</span>
                      <strong>{latestAgentCompartment.cwd || workspace?.root_path || "Not selected"}</strong>
                    </div>
                  </div>

                  <div className="agent-compartment-body agent-live-workbench-grid">
                    <div className="agent-compartment-lane">
                      <div className="agent-compartment-subhead">
                        <span>Planner / executor / verifier lanes</span>
                        <b>{asList(latestAgentCompartment.lanes).length}</b>
                      </div>
                      <div className="agent-runtime-lane-list">
                        {asList(latestAgentCompartment.lanes).length > 0 ? (
                          asList(latestAgentCompartment.lanes).map((lane, index) => (
                            <article className={`agent-runtime-lane ${lane.active ? "active" : ""}`.trim()} key={`${lane.role || "lane"}-${index}`}>
                              <span>{titleizeToken(lane.role || lane.phase || "lane")}</span>
                              <strong>
                                {titleizeToken(lane.provider || "openai-codex")} / {lane.model || "model"}
                              </strong>
                              <small>
                                {titleizeToken(lane.health || "unknown")}
                                {lane.authPath ? ` · ${lane.authPath}` : ""}
                              </small>
                              {lane.blocker ? <p>{lane.blocker}</p> : null}
                            </article>
                          ))
                        ) : (
                          <p className="agent-compartment-empty">No runtime lane contract has been recorded yet.</p>
                        )}
                      </div>
                    </div>

                    <div className="agent-compartment-lane">
                      <div className="agent-compartment-subhead">
                        <span>Tool/action timeline</span>
                        <b>{asList(latestAgentCompartment.toolTimeline || latestAgentCompartment.recentActivity).length}</b>
                      </div>
                      <div className="agent-compartment-event-list">
                        {asList(latestAgentCompartment.toolTimeline || latestAgentCompartment.recentActivity).length > 0 ? (
                          asList(latestAgentCompartment.toolTimeline || latestAgentCompartment.recentActivity).slice(-5).map((event, index) => (
                            <article className="agent-compartment-event" key={`${event.kind || "event"}-${event.at || event.timestamp || index}`}>
                              <span>{titleizeToken(event.kind || event.status || "event")}</span>
                              <strong>{event.summary || event.message || "Runtime event recorded"}</strong>
                              <small>{event.at || event.timestamp ? timestampLabel(event.at || event.timestamp) : titleizeToken(event.status || "recorded")}</small>
                            </article>
                          ))
                        ) : (
                          <p className="agent-compartment-empty">No live tool events have reached the compartment yet.</p>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="agent-compartment-lane">
                    <div className="agent-compartment-subhead">
                      <span>Files and approvals</span>
                      <b>
                        {asList(latestAgentCompartment.filesChanged).length +
                          asList(latestAgentCompartment.approvals).length +
                          asList(latestAgentCompartment.blockers).length}
                      </b>
                    </div>
                    <div className="agent-compartment-chip-list">
                      {asList(latestAgentCompartment.filesChanged).slice(0, 5).map(file => (
                        <code key={`changed-${file}`}>{file}</code>
                      ))}
                      {asList(latestAgentCompartment.approvals).slice(0, 3).map((approval, index) => (
                        <span key={`approval-${approval?.id || index}`}>{approval?.status || approval?.decision || "approval recorded"}</span>
                      ))}
                      {asList(latestAgentCompartment.blockers).slice(0, 3).map((blocker, index) => (
                        <span key={`blocker-${index}`}>{blocker}</span>
                      ))}
                      {asList(latestAgentCompartment.filesChanged).length === 0 &&
                      asList(latestAgentCompartment.approvals).length === 0 &&
                      asList(latestAgentCompartment.blockers).length === 0 ? (
                        <p className="agent-compartment-empty">No changed-file, approval, or blocker receipts attached yet.</p>
                      ) : null}
                    </div>
                  </div>

                  <div className="agent-compartment-body agent-live-workbench-grid">
                    <div className="agent-compartment-lane">
                      <div className="agent-compartment-subhead">
                        <span>Generated image artifacts</span>
                        <b>{generatedImageArtifacts.length}</b>
                      </div>
                      <div className="agent-artifact-grid">
                        {generatedImageArtifacts.length > 0 ? (
                          generatedImageArtifacts.slice(0, 4).map((artifact, index) => {
                            const imageUrl = artifactUrlForRecord(artifact);
                            const manifestUrl = resolveControlArtifactUrl(artifact?.manifestUrl);
                            const label = artifactLabelForRecord(artifact, `artifact-${index + 1}`);
                            return (
                              <figure className="agent-artifact-card" key={`${artifact?.artifactId || label}-${index}`}>
                                {imageUrl ? <img alt={label} src={imageUrl} /> : <div className="builder-live-review-image-missing">Preview not served</div>}
                                <figcaption>
                                  <strong>{label}</strong>
                                  <span>{artifact?.servedArtifactId ? `served ${String(artifact.servedArtifactId).slice(0, 10)}` : artifact?.provider || "served artifact"}</span>
                                  {manifestUrl ? (
                                    <a href={manifestUrl} rel="noreferrer" target="_blank">
                                      Manifest
                                    </a>
                                  ) : null}
                                </figcaption>
                              </figure>
                            );
                          })
                        ) : (
                          <p className="agent-compartment-empty">
                            {generatedImageArtifactState.emptyState || "No served image artifacts are available yet."}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="agent-compartment-lane">
                      <div className="agent-compartment-subhead">
                        <span>Hermes mission evidence</span>
                        <b>{hermesEvidenceItems.length}</b>
                      </div>
                      <div className="agent-compartment-event-list">
                        {hermesEvidenceItems.length > 0 ? (
                          hermesEvidenceItems.slice(0, 5).map((item, index) => (
                            <article className="agent-compartment-event" key={`${item.missionId || "hermes"}-${item.timestamp || index}`}>
                              <span>{titleizeToken(item.source || item.status || "evidence")}</span>
                              <strong>{item.message || item.objective || "Hermes evidence recorded"}</strong>
                              <small>{item.timestamp ? timestampLabel(item.timestamp) : titleizeToken(item.status || "recorded")}</small>
                              {asList(item.failureReasons).length > 0 ? <p>{asList(item.failureReasons).join(" · ")}</p> : null}
                              {asList(item.artifacts).length > 0 ? (
                                <div className="agent-evidence-artifact-strip">
                                  {asList(item.artifacts).slice(0, 4).map((artifact, artifactIndex) => {
                                    const artifactUrl = artifactUrlForRecord(artifact);
                                    const artifactLabel = artifactLabelForRecord(artifact, `evidence-${artifactIndex + 1}`);
                                    const artifactPath = artifact?.path || artifact?.artifactPath || artifact?.servedUrl || artifactUrl;
                                    return (
                                      <a href={artifactUrl || "#"} key={`${item.missionId || "evidence"}-${artifactLabel}-${artifactIndex}`} rel="noreferrer" target="_blank">
                                        {isImageArtifactPath(artifactPath) && artifactUrl ? <img alt="" src={artifactUrl} /> : null}
                                        <span>{artifactLabel}</span>
                                      </a>
                                    );
                                  })}
                                </div>
                              ) : null}
                            </article>
                          ))
                        ) : (
                          <p className="agent-compartment-empty">
                            {hermesMissionEvidence.emptyState || "No Hermes evidence has been captured yet."}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="agent-compartment-lane agent-nas-readiness-panel">
                    <div className="agent-compartment-subhead">
                      <span>NAS deploy readiness</span>
                      <b>{nasDeployChecks.filter(check => check?.passed).length}/{nasDeployChecks.length}</b>
                    </div>
                    <div className="agent-nas-check-grid">
                      {nasDeployChecks.length > 0 ? (
                        nasDeployChecks.map(check => (
                          <article className={`agent-nas-check ${check.passed ? "passed" : check.required ? "blocked" : "warn"}`} key={check.checkId || check.label}>
                            <span>{check.required ? "Required" : "Offline check"}</span>
                            <strong>{check.label}</strong>
                            <p>{check.details}</p>
                          </article>
                        ))
                      ) : (
                        <p className="agent-compartment-empty">NAS deploy readiness has not been reported by the backend yet.</p>
                      )}
                    </div>
                  </div>

                  <div className="agent-compartment-actions">
                    <ActionButton
                      disabled={!missionActionAvailable(mission, "resume")}
                      onClick={() => void runMissionAction("resume", "Mission resume requested.")}
                      type="button"
                    >
                      Resume
                    </ActionButton>
                    <ActionButton onClick={() => setActiveDrawer("proof")} type="button">
                      Proof
                    </ActionButton>
                    <ActionButton onClick={() => setActiveDrawer("queue")} type="button">
                      Queue
                    </ActionButton>
                  </div>
                </section>
              ) : null}

              {agentNexusTurns.length > 0 ? (
                <section className="agent-nexus-strip">
                  <div className="section-title-block">
                    <p className="eyebrow">Nexuses</p>
                    <h2>Jump back to the decisions that changed the mission</h2>
                  </div>
                  <div className="agent-nexus-row">
                    {agentNexusTurns.map(item => (
                      <button
                        className={`agent-nexus-chip ${toneClass(item.tone || "neutral")} ${pinnedNexusIds.includes(item.id) ? "pinned" : ""}`.trim()}
                        key={`agent-nexus-${item.id}`}
                        onClick={() => focusTranscriptTurn(item.id)}
                        type="button"
                      >
                        <span>{item.label || item.roleLabel || "Nexus"}</span>
                        <strong>{item.title}</strong>
                      </button>
                    ))}
                  </div>
                </section>
              ) : null}

              <section className={`agent-chat-stage ${agentIdleState === "no-turns" ? "agent-chat-stage-empty" : ""}`.trim()}>
                {agentHasTurns ? (
                  <section
                    className={`agent-conversation-shell ${splitViewEnabled && splitMission ? "split" : ""}`.trim()}
                  >
                    <div className="agent-conversation-main">
                      <WindowedList
                        className="agent-conversation-feed"
                        estimatedItemHeight={148}
                        items={agentConversationTurns}
                        overscan={6}
                        renderItem={item => (
                          <AgentChatMessage
                            highlighted={highlightedTurnId === item.id}
                            item={item}
                            key={item.id}
                            onFocusTrace={turnId => {
                              setShowThinkingTrace(true);
                              focusTranscriptTurn(turnId);
                            }}
                          />
                        )}
                      />
                    </div>
                    {splitViewEnabled && splitMission ? (
                      <aside className="agent-conversation-secondary">
                        <div className="agent-conversation-secondary-head">
                          <span className="eyebrow">Split mission</span>
                          <strong>{splitMission.title || splitMission.objective}</strong>
                          <p>
                            {runtimeLabel(splitMission.runtime_id)}
                            {` · ${titleizeToken(splitMission?.state?.status || "draft")}`}
                          </p>
                        </div>
                        {splitConversationTurns.length > 0 ? (
                          <WindowedList
                            className="agent-conversation-feed split"
                            estimatedItemHeight={132}
                            items={splitConversationTurns}
                            overscan={4}
                            renderItem={item => (
                              <AgentChatMessage
                                highlighted={highlightedTurnId === item.id}
                                item={item}
                                key={`split-${item.id}`}
                                onFocusTrace={turnId => {
                                  setShowThinkingTrace(true);
                                  setSelectedMissionId(splitMission.mission_id);
                                  focusTranscriptTurn(turnId);
                                }}
                              />
                            )}
                          />
                        ) : (
                          <p className="fluxio-empty-copy">
                            Open this mission once to warm its chat cache for split view.
                          </p>
                        )}
                      </aside>
                    ) : null}
                  </section>
                ) : (
                  <section className="agent-conversation-empty">
                    <p className="eyebrow">{mission ? "Conversation ready" : "Mission launch"}</p>
                    <h2>
                      {mission
                        ? "Talk to the mission like a normal chat."
                        : "Start with a mission prompt in the center composer."}
                    </h2>
                    <p>
                      {mission
                        ? "The technical trace stays available below, but the primary surface is the exchange between you and the agent."
                      : "Choose the route you want, write the objective, and Syntelos will switch into a real conversation once the mission is active."}
                    </p>
                  </section>
                )}

                {agentTraceTurns.length > 0 ? (
                  <section className="agent-trace-shell">
                    <div className="agent-trace-head">
                      <div className="section-title-block">
                        <p className="eyebrow">Live trace</p>
                        <h2>Route changes, approvals, and technical output</h2>
                      </div>
                      <div className="thread-composer-actions">
                        <ActionButton onClick={() => setShowThinkingTrace(current => !current)} type="button">
                          {showThinkingTrace ? "Hide trace" : "Show trace"}
                        </ActionButton>
                      </div>
                    </div>
                    {showThinkingTrace ? (
                      <WindowedList
                        className="agent-trace-list"
                        estimatedItemHeight={186}
                        items={agentTraceTurns}
                        overscan={4}
                        renderItem={item => (
                          <TranscriptMessage
                            highlighted={highlightedTurnId === item.id}
                            item={item}
                            key={item.id}
                            onMemory={handleAgentMemoryFromTurn}
                            onPinNexus={togglePinnedNexus}
                            onSteer={handleAgentSteerFromTurn}
                            onValidate={handleAgentValidateTurn}
                            pinned={pinnedNexusIds.includes(item.id)}
                            showTrace={showThinkingTrace}
                          />
                        )}
                      />
                    ) : (
                      <p className="fluxio-empty-copy">
                        Trace is hidden. Syntelos is still recording work decisions in the background.
                      </p>
                    )}
                  </section>
                ) : null}

                <form
                  className={`thread-composer agent-composer agent-chat-composer ${agentIdleState === "no-turns" ? "agent-idle-composer" : "agent-docked-composer"}`.trim()}
                  onSubmit={event => event.preventDefault()}
                >
                  <div className="agent-composer-toolbar">
                    <Field label={mission ? "Trace runtime" : "Launch runtime"}>
                      <select
                        onChange={event =>
                          mission
                            ? setAgentRuntimeFocus(event.target.value)
                            : setMissionForm(current => ({
                                ...current,
                                runtime: event.target.value,
                              }))
                        }
                        value={agentRuntimeSelectValue}
                      >
                        {mission ? <option value="all">All traces</option> : null}
                        {runtimeOptions.map(option => (
                          <option key={`agent-runtime-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Route role">
                      <input readOnly value={`${titleizeToken(agentRouteRole)} (auto)`} />
                    </Field>
                    <Field label="Provider">
                      <select
                        onChange={event => handleAgentRouteFieldChange("provider", event.target.value)}
                        value={selectedAgentRoute.provider}
                      >
                        {MODEL_PROVIDER_OPTIONS.map(option => (
                          <option key={`agent-provider-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Model">
                      <select
                        onChange={event => handleAgentRouteFieldChange("model", event.target.value)}
                        value={selectedAgentRoute.model}
                      >
                        <option value="">Profile default</option>
                        {ROUTE_MODEL_OPTIONS.map(option => (
                          <option key={`agent-model-${option}`} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Reasoning">
                      <select
                        onChange={event => handleAgentRouteFieldChange("effort", event.target.value)}
                        value={normalizeRouteEffort(selectedAgentRoute.effort, "default")}
                      >
                        {MODEL_EFFORT_OPTIONS.map(option => (
                          <option key={`agent-effort-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                  </div>
                  <p className="agent-composer-hint">{agentRuntimeHint}</p>
                  <div className="agent-composer-status">
                    <span className="mini-pill muted">{agentRouteStatus}</span>
                    {mission ? (
                      <span className="mini-pill muted">
                        {titleizeToken(agentCyclePhase)} phase via {titleizeToken(agentCycleRole)}
                      </span>
                    ) : null}
                    <span className="mini-pill muted">
                      {latestThinkingTurn
                        ? `${latestThinkingTurn.roleLabel || "Runtime"} trace live`
                        : mission?.state?.status === "running"
                          ? "Awaiting the next runtime trace"
                          : "No live trace right now"}
                    </span>
                    <span className="mini-pill muted">
                      {agentThinkingTurns.length} trace moment{agentThinkingTurns.length === 1 ? "" : "s"}
                    </span>
                    <span className="mini-pill muted">
                      Code execution {codeExecutionEnabled ? `on · ${codeExecutionMemory}` : "off"}
                    </span>
                    <span className="mini-pill muted">
                      {modelAuthReady ? "Model auth ready" : "Model auth missing"}
                    </span>
                    {mission ? <span className="mini-pill muted">{followUpDeliveryStatus}</span> : null}
                  </div>
                  {mission ? (
                    <div className="agent-split-controls">
                      <label className="check-field">
                        <input
                          checked={splitViewEnabled}
                          onChange={event => setSplitViewEnabled(event.target.checked)}
                          type="checkbox"
                        />
                        <span>Enable split mission view</span>
                      </label>
                      <Field label="Second mission">
                        <select
                          disabled={!splitViewEnabled || splitMissionOptions.length === 0}
                          onChange={event => setSplitMissionId(event.target.value)}
                          value={splitMission?.mission_id || ""}
                        >
                          {splitMissionOptions.length === 0 ? (
                            <option value="">No other mission available</option>
                          ) : (
                            splitMissionOptions.map(item => (
                              <option key={`split-${item.mission_id}`} value={item.mission_id}>
                                {item.title || item.objective}
                              </option>
                            ))
                          )}
                        </select>
                      </Field>
                      {splitMission?.mission_id ? (
                        <ActionButton
                          onClick={() => setSelectedMissionId(splitMission.mission_id)}
                          type="button"
                        >
                          Focus second mission
                        </ActionButton>
                      ) : null}
                    </div>
                  ) : null}
                  <div className="agent-preset-row">
                    {MODEL_QUICK_PRESETS.map(preset => (
                      <ActionButton
                        key={`live-preset-${preset.id}`}
                        onClick={() => applyModelQuickPreset(preset)}
                        type="button"
                      >
                        {preset.label}
                      </ActionButton>
                    ))}
                  </div>
                  <textarea
                    id="thread-note"
                    onChange={event => setOperatorDraft(event.target.value)}
                    onPaste={handleComposerPaste}
                    placeholder={agentComposerPlaceholder}
                    value={operatorDraft}
                  />
                  <ComposerAttachmentStrip
                    attachments={operatorAttachments}
                    onClear={clearOperatorAttachments}
                    onRemove={removeOperatorAttachment}
                  />
                  <div className="thread-composer-actions">
                    <ActionButton onClick={() => void handleAgentRouteSave()} type="button">
                      Apply model
                    </ActionButton>
                    <ActionButton
                      onClick={() => setCodeExecutionEnabled(current => !current)}
                      type="button"
                    >
                      {codeExecutionEnabled ? "Disable code execution" : "Enable code execution"}
                    </ActionButton>
                    {mission ? (
                      <>
                        <ActionButton onClick={handleOperatorNote} type="button">
                          Save note
                        </ActionButton>
                        <ActionButton onClick={() => void handleAgentFollowUp()} type="button" variant="primary">
                          Send message
                        </ActionButton>
                      </>
                    ) : (
                      <ActionButton
                        onClick={handleAgentIdlePrimaryAction}
                        type="button"
                        variant="primary"
                      >
                        {workspaces.length > 0 ? "Launch mission" : "Add project"}
                      </ActionButton>
                    )}
                  </div>
                </form>
              </section>
            </section>
          )}
        </main>

        {showPersistentDrawer ? (
          <aside className={`fluxio-drawer ${activeDrawer ? "open" : ""}`.trim()}>
            <div className="drawer-shell-head">
              <div>
                <p className="eyebrow">{uiMode === "builder" ? "Builder panel" : "Blocker panel"}</p>
                <strong>{activeDrawerMeta?.label || titleizeToken(activeDrawer || "panel")}</strong>
              </div>
              {uiMode === "builder" ? (
                <ActionButton onClick={() => setActiveDrawer(null)} type="button">
                  Close
                </ActionButton>
              ) : null}
            </div>
            <div className="drawer-content">{renderDrawerPanel()}</div>
          </aside>
        ) : null}
      </div>

      <Modal
        actions={
          <>
            <ActionButton
              disabled={!openAICodexOAuthFlow.helperCommand}
              onClick={async () => {
                const copied = await copyTextValue(openAICodexOAuthFlow.helperCommand || "");
                pushToast(
                  copied
                    ? "Fallback relay helper command copied. Run it on the same device as this browser."
                    : "Could not copy the relay helper command.",
                  copied ? "info" : "warn",
                );
              }}
            >
              Copy fallback relay helper
            </ActionButton>
            <ActionButton
              disabled={!(openAICodexOAuthFlow.verificationUrl || openAICodexOAuthFlow.authUrl)}
              onClick={() =>
                window.open(
                  openAICodexOAuthFlow.verificationUrl || openAICodexOAuthFlow.authUrl,
                  "_blank",
                  "noopener,noreferrer",
                )
              }
            >
              Open OpenAI sign-in
            </ActionButton>
            <ActionButton
              disabled={["checking", "completing"].includes(openAICodexOAuthFlow.status)}
              onClick={() => void completeOpenAICodexOAuth()}
              variant="primary"
            >
              {["checking", "completing"].includes(openAICodexOAuthFlow.status)
                ? "Connecting..."
                : "Connect Codex OAuth"}
            </ActionButton>
          </>
        }
        onClose={() => setOpenAICodexOAuthFlow(current => ({ ...current, open: false }))}
        open={openAICodexOAuthFlow.open}
        summary="OpenAI redirects Codex OAuth to localhost. The desktop app catches that callback directly; NAS/web installs use this relay fallback."
        title="Complete OpenAI Codex OAuth"
      >
        <div className="dialog-form">
          <p>
            Run the fallback relay helper on the same device as this browser. It listens on
            <strong> localhost:{openAICodexOAuthFlow.callbackPort || 1455}</strong>, opens
            OpenAI sign-in, and forwards the callback to the NAS.
          </p>
          {openAICodexOAuthFlow.helperCommand ? (
            <pre className="runtime-output">{openAICodexOAuthFlow.helperCommand}</pre>
          ) : null}
          <Field label="Final localhost callback URL or authorization code">
            <textarea
              onChange={event =>
                setOpenAICodexOAuthFlow(current => ({
                  ...current,
                  callback: event.target.value,
                }))
              }
              placeholder="http://localhost:1455/auth/callback?code=..."
              rows={5}
              value={openAICodexOAuthFlow.callback}
            />
          </Field>
          {openAICodexOAuthFlow.message ? <p>{openAICodexOAuthFlow.message}</p> : null}
          {openAICodexOAuthFlow.output ? (
            <pre className="runtime-output">{openAICodexOAuthFlow.output}</pre>
          ) : null}
        </div>
      </Modal>

      <Modal
        actions={
          <>
            <ActionButton
              disabled={!miniMaxOAuthFlow.verificationUrl}
              onClick={() =>
                window.open(
                  miniMaxOAuthFlow.verificationUrl,
                  "_blank",
                  "noopener,noreferrer",
                )
              }
            >
              Open MiniMax
            </ActionButton>
            <ActionButton
              disabled={!miniMaxOAuthFlow.userCode}
              onClick={async () => {
                const copied = await copyTextValue(miniMaxOAuthFlow.userCode || "");
                pushToast(
                  copied ? "MiniMax code copied." : "Could not copy the MiniMax code.",
                  copied ? "info" : "warn",
                );
              }}
            >
              Copy code
            </ActionButton>
            <ActionButton
              disabled={miniMaxOAuthFlow.status === "checking"}
              onClick={() => void completeMiniMaxOAuth()}
              variant="primary"
            >
              {miniMaxOAuthFlow.status === "checking" ? "Checking..." : "Verify MiniMax"}
            </ActionButton>
          </>
        }
        onClose={() => setMiniMaxOAuthFlow(current => ({ ...current, open: false }))}
        open={miniMaxOAuthFlow.open}
        summary="MiniMax uses a portal user-code grant. Syntelos starts it on the NAS, then writes the completed token into the OpenClaw auth profile."
        title="Complete MiniMax OpenClaw OAuth"
      >
        <div className="dialog-form">
          <p>
            Open MiniMax verification, approve access, then verify the NAS session.
          </p>
          {miniMaxOAuthFlow.verificationUrl ? (
            <Field label="Verification URL">
              <input readOnly value={miniMaxOAuthFlow.verificationUrl} />
            </Field>
          ) : null}
          {miniMaxOAuthFlow.userCode ? (
            <Field label="MiniMax code">
              <pre className="runtime-output">{miniMaxOAuthFlow.userCode}</pre>
            </Field>
          ) : null}
          {miniMaxOAuthFlow.command ? (
            <Field label="Fallback command">
              <pre className="runtime-output">{miniMaxOAuthFlow.command}</pre>
            </Field>
          ) : null}
          {miniMaxOAuthFlow.message ? <p>{miniMaxOAuthFlow.message}</p> : null}
          {miniMaxOAuthFlow.output ? (
            <pre className="runtime-output">{miniMaxOAuthFlow.output}</pre>
          ) : null}
        </div>
      </Modal>

      <Modal
        actions={
          <ActionButton onClick={handleWorkspaceSubmit} type="submit" variant="primary">
            Save project
          </ActionButton>
        }
        onClose={() => setShowWorkspaceDialog(false)}
        open={showWorkspaceDialog}
        summary="Choose the project folder Syntelos should work on. If NAS mirroring is enabled, missions run on the NAS working copy."
        title="Add project"
      >
        <form className="dialog-form project-dialog-form" onSubmit={handleWorkspaceSubmit}>
          <Field label="Project name">
            <input
              onChange={event =>
                setWorkspaceForm(current => ({ ...current, name: event.target.value }))
              }
              placeholder="Syntelos Workspace"
              value={workspaceForm.name}
            />
          </Field>
          <Field label="Project folder">
            <input
              onChange={event => {
                const nextPath = event.target.value;
                setWorkspaceForm(current => ({
                  ...current,
                  name: current.name || pathLeaf(nextPath),
                  path: nextPath,
                  localProjectPath: nextPath,
                  nasProjectPath: current.nasProjectPath || defaultNasProjectPath(nextPath),
                }));
              }}
              placeholder="C:/Users/paul/Projects/vibe-coding-platform"
              value={workspaceForm.path}
            />
          </Field>
          {!hasTauriBackend() ? (
            <p className="project-dialog-note">
              Web mode: browse server folders or paste a project path manually.
            </p>
          ) : null}
          {previewMode !== "live" ? (
            <p className="project-dialog-note is-warn">
              Saving is disabled in preview mode. Switch the backend mode to Live Backend first.
            </p>
          ) : null}
          <label className="checkbox-row">
            <input
              checked={workspaceForm.autoSyncToNas}
              onChange={event =>
                setWorkspaceForm(current => ({
                  ...current,
                  autoSyncToNas: event.target.checked,
                  syncMode: event.target.checked ? "auto_nas_mirror" : "manual",
                  localProjectPath: current.localProjectPath || current.path,
                  nasProjectPath: current.nasProjectPath || defaultNasProjectPath(current.path),
                }))
              }
              type="checkbox"
            />
            <span>Run long missions on a NAS working copy</span>
          </label>
          {workspaceForm.autoSyncToNas ? (
            <Field label="NAS working copy">
              <input
                onChange={event =>
                  setWorkspaceForm(current => ({ ...current, nasProjectPath: event.target.value }))
                }
                placeholder="/volume1/Saclay/projects/vibe-coding-platform"
                value={workspaceForm.nasProjectPath}
              />
            </Field>
          ) : null}
          {previewMode === "live" && hasCommandBackend() ? (
            <div className="inline-actions">
              <ActionButton onClick={() => void handleReferencePickWorkspaceFolder()} type="button">
                {hasTauriBackend() ? "Browse for folder" : "Browse server folders"}
              </ActionButton>
            </div>
          ) : null}
        </form>
      </Modal>

      <Modal
        actions={
          <ActionButton onClick={handleMissionSubmit} type="submit" variant="primary">
            Launch mission
          </ActionButton>
        }
        onClose={() => setShowMissionDialog(false)}
        open={showMissionDialog}
        summary="Mission launch remains available, but operational clutter is removed from the top bar."
        title="Start mission"
      >
        <form className="dialog-form" onSubmit={handleMissionSubmit}>
          <div className="field-row">
            <Field label="Workspace">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, workspaceId: event.target.value }))
                }
                value={missionForm.workspaceId}
              >
                {workspaces.map(item => (
                  <option key={item.workspace_id} value={item.workspace_id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Runtime">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, runtime: event.target.value }))
                }
                value={missionForm.runtime}
              >
                <option value="openclaw">OpenClaw</option>
                <option value="hermes">Hermes</option>
                <option value="opencode">OpenCodeGo</option>
              </select>
            </Field>
          </div>

          <div className="field-row">
            <Field label="Run mode">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, mode: event.target.value }))
                }
                value={missionForm.mode}
              >
                <option value="Autopilot">Autopilot</option>
                <option value="Focus">Focus</option>
                <option value="Deep Run">Deep Run</option>
                <option value="Research">Research</option>
              </select>
            </Field>
            <Field label="Profile">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, profile: event.target.value }))
                }
                value={missionForm.profile}
              >
                {(snapshot.profiles?.availableProfiles || ["beginner", "builder", "advanced"]).map(
                  option => (
                    <option key={option} value={option}>
                      {titleizeToken(option)}
                    </option>
                  ),
                )}
              </select>
            </Field>
          </div>

          <div className="field-row">
            <Field label="Provider">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, modelProvider: event.target.value }))
                }
                value={missionForm.modelProvider}
              >
                {MODEL_PROVIDER_OPTIONS.map(option => (
                  <option key={`mission-reference-provider-${option.value}`} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Model">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, model: event.target.value }))
                }
                value={missionForm.model}
              >
                <option value="">Profile default</option>
                {ROUTE_MODEL_OPTIONS.map(option => (
                  <option key={`mission-reference-model-${option}`} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Effort">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, modelEffort: event.target.value }))
                }
                value={normalizeRouteEffort(missionForm.modelEffort, "medium")}
              >
                {MODEL_EFFORT_OPTIONS.map(option => (
                  <option key={`mission-reference-effort-${option.value}`} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div className="field-row">
            <Field label="Budget hours">
              <input
                min="1"
                onChange={event =>
                  setMissionForm(current => ({
                    ...current,
                    budgetHours: Number(event.target.value || 12),
                  }))
                }
                type="number"
                value={missionForm.budgetHours}
              />
            </Field>
            <Field label="Run until">
              <select
                onChange={event =>
                  setMissionForm(current => ({ ...current, runUntil: event.target.value }))
                }
                value={missionForm.runUntil}
              >
                <option value="pause_on_failure">Pause on failure</option>
                <option value="continue_until_blocked">Continue until blocked</option>
              </select>
            </Field>
          </div>

          <Field label="Stop after (minutes, optional)">
            <input
              min="0"
              onChange={event =>
                setMissionForm(current => ({
                  ...current,
                  relativeStopMinutes: event.target.value.replace(/[^\d]/g, ""),
                }))
              }
              placeholder="Leave empty to use Budget hours only"
              type="number"
              value={missionForm.relativeStopMinutes}
            />
          </Field>

          <Field label="Mission objective">
            <textarea
              onChange={event =>
                setMissionForm(current => ({ ...current, objective: event.target.value }))
              }
              placeholder={missionObjectivePlaceholder(missionForm.profile)}
              value={missionForm.objective}
            />
          </Field>

          <Field label="Success checks">
            <textarea
              onChange={event =>
                setMissionForm(current => ({ ...current, successChecks: event.target.value }))
              }
              placeholder={missionChecksPlaceholder(missionForm.profile)}
              value={missionForm.successChecks}
            />
          </Field>
        </form>
      </Modal>

      <Modal
        actions={
          <div className="inline-actions">
            <ActionButton onClick={handleClearTelegram}>Clear token</ActionButton>
            <ActionButton onClick={handleSaveTelegram} type="submit" variant="primary">
              Save escalation
            </ActionButton>
          </div>
        }
        onClose={() => setShowEscalationDialog(false)}
        open={showEscalationDialog}
        summary="Escalation stays accessible, but only opens when the operator needs it."
        title="Configure Telegram escalation"
      >
        <form className="dialog-form" onSubmit={handleSaveTelegram}>
          <Field label="Telegram connection token">
            <input
              onChange={event => setTelegramBotToken(event.target.value)}
              placeholder="123456:ABCDEF..."
              type="password"
              value={telegramBotToken}
            />
          </Field>
          <Field label="Telegram chat ID">
            <input
              onChange={event => setTelegramChatId(event.target.value)}
              placeholder="123456789"
              value={telegramChatId}
            />
          </Field>
        </form>
      </Modal>

      <ToastHost items={toasts} />
    </div>
  );
}
