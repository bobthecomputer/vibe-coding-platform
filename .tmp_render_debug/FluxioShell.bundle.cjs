var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __commonJS = (cb, mod) => function __require() {
  return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
};
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// .tmp_render_debug/tauri-core-stub.js
var require_tauri_core_stub = __commonJS({
  ".tmp_render_debug/tauri-core-stub.js"(exports2) {
    exports2.invoke = async () => null;
  }
});

// .tmp_render_debug/tauri-event-stub.js
var require_tauri_event_stub = __commonJS({
  ".tmp_render_debug/tauri-event-stub.js"(exports2) {
    exports2.listen = async () => (() => {
    });
  }
});

// t3code/apps/web/src/fluxio/FluxioShell.jsx
var FluxioShell_exports = {};
__export(FluxioShell_exports, {
  FluxioShellApp: () => FluxioShellApp
});
module.exports = __toCommonJS(FluxioShell_exports);
var import_react = require("react");
var import_core = __toESM(require_tauri_core_stub(), 1);
var import_event = __toESM(require_tauri_event_stub(), 1);

// desktop-ui/fixtures.js
var now = "2026-04-14T10:30:00Z";
function clone(value) {
  return JSON.parse(JSON.stringify(value));
}
var profiles = {
  defaultProfile: "builder",
  availableProfiles: ["beginner", "builder", "advanced", "experimental"],
  details: {
    beginner: {
      description: "Safer approvals, stronger explanations, and slower autonomy.",
      ui: { motion: "reduced" },
      parameters: { profileName: "beginner", autonomyLevel: "guided", approvalStrictness: "strict", verificationCadence: "each_cycle", explanationLevel: "high", explorationBreadth: "bounded", autoContinueBehavior: "pause_on_failure", gitActionPolicy: "approval_gated", setupAutomationPolicy: "installer_guided", learningAggressiveness: "guarded", uiDensity: "comfortable", visibilityLevel: "guided" }
    },
    builder: {
      description: "Balanced profile for autonomous delivery with guided control.",
      ui: { motion: "standard" },
      parameters: { profileName: "builder", autonomyLevel: "balanced", approvalStrictness: "tiered", verificationCadence: "each_cycle", explanationLevel: "medium", explorationBreadth: "bounded", autoContinueBehavior: "pause_on_failure", gitActionPolicy: "approval_gated", setupAutomationPolicy: "repair_and_verify", learningAggressiveness: "bounded", uiDensity: "comfortable", visibilityLevel: "balanced" }
    },
    advanced: {
      description: "Concise, higher-autonomy profile for experienced builders.",
      ui: { motion: "standard" },
      parameters: { profileName: "advanced", autonomyLevel: "high", approvalStrictness: "tiered", verificationCadence: "continuous_until_blocked", explanationLevel: "low", explorationBreadth: "wide", autoContinueBehavior: "continue_until_blocked", gitActionPolicy: "approval_gated", setupAutomationPolicy: "repair_and_verify", learningAggressiveness: "bounded", uiDensity: "comfortable", visibilityLevel: "detailed" }
    },
    experimental: {
      description: "Broad autonomy, wider experimentation, and faster iteration.",
      ui: { motion: "standard" },
      parameters: { profileName: "experimental", autonomyLevel: "maximum", approvalStrictness: "hands_free", verificationCadence: "continuous_until_blocked", explanationLevel: "low", explorationBreadth: "wide", autoContinueBehavior: "continue_until_blocked", gitActionPolicy: "profile_resolved", setupAutomationPolicy: "repair_and_verify", learningAggressiveness: "aggressive", uiDensity: "comfortable", visibilityLevel: "expert" }
    }
  }
};
var baseSnapshot = {
  workspaceRoot: "C:/Users/paul/Projects/vibe-coding-platform",
  ui: {
    uiMode: "agent",
    defaultMode: "agent",
    availableModes: ["agent", "builder"],
    layout: "t3_workbench",
    sharedMissionState: true
  },
  workspaces: [
    {
      workspace_id: "workspace_primary",
      name: "Fluxio Platform",
      root_path: "C:/Users/paul/Projects/vibe-coding-platform",
      default_runtime: "openclaw",
      workspace_type: "tauri-python",
      user_profile: "builder",
      runtimeStatus: { detected: true },
      gitSnapshot: {
        repoDetected: true,
        branch: "main",
        trackingBranch: "origin/main",
        dirty: true,
        stagedCount: 2,
        unstagedCount: 1,
        untrackedCount: 0,
        ahead: 1,
        behind: 0,
        remotes: [{ name: "origin", url: "git@github.com:paul/vibe-coding-platform.git" }],
        deployTarget: {
          provider: "github_pages",
          available: true,
          configured: false,
          requiresApproval: true,
          detail: "GitHub remote detected. Pages can be scaffolded after explicit approval."
        },
        detail: "main \xB7 dirty \xB7 1 remote(s)"
      },
      gitActions: [
        { actionId: "inspect_repo_state", label: "Inspect repository state", command: "git status --short --branch", commandSurface: "git.inspect", requiresApproval: false, detail: "Review branch, changes, and ahead/behind before mutating actions." },
        { actionId: "push_branch", label: "Push current branch", command: "git push", commandSurface: "git.push", requiresApproval: true, detail: "Policy-resolved push action. Approval stays on by default." },
        { actionId: "deploy_pages", label: "Publish deploy target", command: "git push origin HEAD", commandSurface: "deploy.pages", requiresApproval: true, detail: "GitHub remote detected. Pages can be scaffolded after explicit approval." }
      ],
      workspaceActionHistory: [],
      profileParameters: {
        profileName: "builder",
        autonomyLevel: "balanced",
        approvalStrictness: "tiered",
        verificationCadence: "each_cycle",
        explanationLevel: "medium",
        explorationBreadth: "bounded",
        autoContinueBehavior: "pause_on_failure",
        gitActionPolicy: "approval_gated",
        setupAutomationPolicy: "repair_and_verify",
        learningAggressiveness: "bounded",
        uiDensity: "comfortable",
        visibilityLevel: "balanced"
      },
      skillRecommendations: [
        { label: "Repo Scan", reason: "Ground planning in the actual repo." },
        { label: "Frontend Proof", reason: "Track UI regressions and screenshots." }
      ],
      integrationRecommendations: [
        { label: "Filesystem MCP", reason: "Safe workspace inspection.", command: "npx @modelcontextprotocol/server-filesystem ." },
        { label: "Playwright MCP", reason: "Visual proof and smoke tests.", command: "npx @playwright/mcp@latest" }
      ]
    }
  ],
  missions: [],
  runtimes: [
    {
      runtime_id: "openclaw",
      label: "OpenClaw",
      detected: true,
      doctor_summary: "Ready for delegated execution.",
      install_hint: "",
      capabilities: [{ label: "Remote approvals" }, { label: "Skills" }]
    },
    {
      runtime_id: "hermes",
      label: "Hermes",
      detected: true,
      doctor_summary: "Ready for long-horizon delegated work.",
      install_hint: "",
      capabilities: [{ label: "Delegation" }, { label: "Skills and memory" }]
    }
  ],
  activity: [
    { kind: "mission.runtime_cycle", message: "OpenClaw control cycle finished with status running.", timestamp: now },
    { kind: "approval.request", message: "Delegated runtime requested approval for deploy simulation.", timestamp: now }
  ],
  inbox: [],
  onboarding: {
    tutorial: {
      selectedProfile: "builder",
      completedSteps: ["detect_environment", "choose_profile", "add_workspace"],
      currentStepId: "launch_mission",
      isComplete: false,
      steps: [
        { step_id: "detect_environment", title: "Check local setup", description: "Verify runtimes and tooling.", status: "pending", panel: "Setup" },
        { step_id: "choose_profile", title: "Choose a guided profile", description: "Set safe defaults.", status: "completed", panel: "Guidance" },
        { step_id: "add_workspace", title: "Add a workspace", description: "Register a project.", status: "completed", panel: "Projects" },
        { step_id: "launch_mission", title: "Launch a mission", description: "Start a real loop.", status: "pending", panel: "Missions" }
      ]
    },
    profileChoices: [],
    checks: {
      node: { installed: true, version: "v24.2.0" },
      python: { installed: true, version: "3.13.2" },
      uv: { installed: true, version: "0.7.20" },
      openclaw: { installed: true, version: "2026.4.14" },
      hermes: { installed: true, version: "v0.9.0" }
    },
    wsl: { installed: true, details: "WSL2 detected and ready." },
    nextActions: ["Launch a first mission to unlock the planner timeline and proof surfaces.", "Configure Telegram escalation before long unattended runs.", "Review runtime lanes and connected app bridges in Builder after launch."]
  },
  guidance: {
    profileChoices: [
      { name: "beginner", description: "Safer approvals and richer teaching.", executionScope: "isolated", approvalMode: "strict", motion: "reduced" },
      { name: "builder", description: "Balanced autonomy and clarity.", executionScope: "isolated", approvalMode: "tiered", motion: "standard" },
      { name: "advanced", description: "Faster autonomy with less guidance.", executionScope: "isolated", approvalMode: "tiered", motion: "standard" },
      { name: "experimental", description: "Broader experimentation and autonomy.", executionScope: "isolated", approvalMode: "hands_free", motion: "standard" }
    ],
    guidanceCards: [
      { card_id: "guide_launch", title: "Run a first mission", body: "The planner and proof feed become much clearer after one real mission cycle.", kind: "mission", panel: "Missions" },
      { card_id: "guide_phone", title: "Enable phone escalation", body: "Configure Telegram before long unattended runs.", kind: "integration", panel: "Integrations" }
    ],
    productImprovements: [
      { item_id: "pi_1", title: "Improve approval handoff language", reason: "Operators still hesitate on delegated approvals.", priority: "high", category: "ux" },
      { item_id: "pi_2", title: "Add screenshot proof lane", reason: "UI review still lacks a native visual check surface.", priority: "medium", category: "proof" }
    ]
  },
  profiles,
  setupHealth: {
    installState: "missing",
    environmentReady: true,
    installerReady: true,
    firstMissionLaunched: false,
    telegramReady: false,
    missingDependencies: ["First guided mission"],
    dependencies: [
      { dependencyId: "wsl2", label: "WSL2", category: "platform", required: true, installed: true, version: "WSL2", details: "WSL2 detected and ready.", repairActions: [], latestAction: {}, stage: "healthy", blocked: false },
      { dependencyId: "node", label: "Node", category: "runtime", required: true, installed: true, version: "v24.2.0", details: "Installed and reachable.", repairActions: [], latestAction: {}, stage: "healthy", blocked: false },
      { dependencyId: "python", label: "Python", category: "runtime", required: true, installed: true, version: "3.13.2", details: "Installed and reachable.", repairActions: [], latestAction: {}, stage: "healthy", blocked: false },
      { dependencyId: "uv", label: "uv", category: "tooling", required: true, installed: true, version: "0.7.20", details: "Installed and reachable.", repairActions: [], latestAction: {}, stage: "healthy", blocked: false },
      { dependencyId: "openclaw", label: "OpenClaw", category: "agent_runtime", required: true, installed: true, version: "2026.4.14", details: "Installed and verified against the latest npm release.", repairActions: [], latestAction: {}, stage: "healthy", blocked: false },
      { dependencyId: "hermes", label: "Hermes", category: "agent_runtime", required: true, installed: true, version: "v0.9.0", details: "Installed in WSL2 and verified against the latest upstream release.", repairActions: [], latestAction: {}, stage: "healthy", blocked: false },
      { dependencyId: "tauri_prereqs", label: "Tauri prerequisites", category: "desktop", required: false, installed: true, version: "stable", details: "Rust and Cargo are available for Tauri builds.", repairActions: [], latestAction: {}, stage: "healthy", blocked: false },
      { dependencyId: "telegram_ready", label: "Telegram escalation", category: "readiness", required: false, installed: false, version: "", details: "Add a Telegram destination so long unattended runs can escalate approvals.", repairActions: [], latestAction: {}, stage: "missing", blocked: false },
      { dependencyId: "guided_mission", label: "First guided mission", category: "readiness", required: true, installed: false, version: "", details: "Finish setup by launching one real guided mission from Fluxio.", repairActions: [], latestAction: {}, stage: "missing", blocked: true }
    ],
    repairActions: [],
    globalActions: [
      {
        actionId: "verify_setup_health",
        label: "Verify setup health",
        description: "Re-check local dependencies, runtimes, and blockers after a repair.",
        commandSurface: "setup.verify"
      }
    ],
    actionHistory: [],
    actionHistoryByDependency: {},
    blockerExplanations: ["Launch one real guided mission from Fluxio."]
  },
  skillLibrary: {
    recommendedPacks: [{ label: "Repo Scan", execution_capable: true }],
    curatedPacks: [{ label: "Verification Suite", execution_capable: false }],
    userInstalledSkills: [],
    learnedSkills: [{ label: "Approval Recovery Pattern", execution_capable: false }]
  },
  workflowStudio: {
    recommendedMode: "agent",
    recipes: [
      { workflowId: "agent_long_run", label: "Long-Run Agent Session", description: "Leave Fluxio to plan, execute, verify, and replan over many hours with approvals and proof kept visible.", status: "ready", audience: "all", surface: "agent_view" },
      { workflowId: "ui_review_loop", label: "Live UI Review Loop", description: "Use HMR, fixtures, proof, and replay-ready states while refining the desktop workbench.", status: "ready", audience: "builder", surface: "builder_view" },
      { workflowId: "safe_git_push", label: "Safe Push Or Deploy", description: "Inspect repo truth first, then offer profile-resolved push and GitHub Pages actions with approvals.", status: "ready", audience: "advanced", surface: "builder_view" },
      { workflowId: "skill_authoring", label: "Skill And Workflow Authoring", description: "Create a new skill or workflow recipe, test it locally, and keep it reviewable inside Fluxio.", status: "ready", audience: "builder", surface: "skill_studio" }
    ],
    learningQueue: [{ title: "Promote approval recovery pattern", priority: "medium" }]
  },
  harnessLab: {
    productionHarness: "fluxio_hybrid",
    shadowCandidates: ["legacy_autonomous_engine"],
    recentRuns: [
      { sessionId: "session_aa12", harnessId: "fluxio_hybrid", runtimeId: "openclaw", autopilotStatus: "running", pauseReason: "" },
      { sessionId: "session_bb34", harnessId: "legacy_autonomous_engine", runtimeId: "openclaw", autopilotStatus: "completed", pauseReason: "" }
    ],
    recommendation: "Fluxio hybrid harness is active; keep shadow comparisons visible."
  },
  bridgeLab: {
    schemaVersion: "fluxio.app-capability/v0-draft",
    recommendation: "OratioViva and Mind Tower are live reference integrations. Solantir remains in manifest-only follow-on review.",
    phases: [
      "Phase A: manifest and policy contract",
      "Phase B: live reference integrations for OratioViva and Mind Tower",
      "Phase C: Solantir follow-on after the bridge standard is proven"
    ],
    discoveredApps: [
      {
        name: "Oratio Viva",
        description: "Speech workflows exposed through a local bridge.",
        bridge: { transport: "http" },
        permissions: ["task.run", "context.read", "action.invoke"],
        tasks: [{ label: "Render voice preview" }]
      },
      {
        name: "Mind Tower",
        description: "Monitoring and digest workflows exposed through a local bridge.",
        bridge: { transport: "http" },
        permissions: ["task.run", "context.read", "approval.callback"],
        tasks: [{ label: "Run monitoring digest" }]
      },
      {
        name: "Solantir Terminal",
        description: "Operator dashboard surfaces exposed through IPC.",
        bridge: { transport: "ipc" },
        permissions: ["task.run", "context.read", "approval.request"],
        tasks: [{ label: "Refresh watchlist" }]
      }
    ],
    connectedSessions: [
      {
        session_id: "bridge_oratio_viva",
        app_id: "oratio-viva",
        app_name: "Oratio Viva",
        status: "connected",
        bridge_health: "healthy",
        handshake_status: "connected",
        bridge_transport: "http",
        active_tasks: [],
        context_preview: [{ summary: "3 voice engines detected in oratio-viva-ui 0.1.0" }],
        latest_task_result: {
          label: "Render voice preview",
          resultSummary: "Queued and completed a local preview bridge task for the dia2 voice engine."
        },
        granted_capabilities: [
          { capability_key: "task.run", status: "granted" },
          { capability_key: "context.read", status: "granted" }
        ],
        notes: ["Bridge session is live and available for follow-on orchestration."],
        last_seen_at: now
      },
      {
        session_id: "bridge_mind_tower",
        app_id: "mind-tower",
        app_name: "Mind Tower",
        status: "connected",
        bridge_health: "healthy",
        handshake_status: "connected",
        bridge_transport: "http",
        active_tasks: [],
        context_preview: [{ summary: "42 admin files and 2 service modules detected." }],
        latest_task_result: {
          label: "Run monitoring digest",
          resultSummary: "Ran the local monitoring digest bridge task and captured session proof."
        },
        approval_callback: {
          detail: "Telegram listener detected for escalation-aware callback handling."
        },
        granted_capabilities: [
          { capability_key: "task.run", status: "granted" },
          { capability_key: "context.read", status: "granted" },
          { capability_key: "approval.callback", status: "review" }
        ],
        notes: ["Bridge session is healthy and can push approval-aware follow-ups."],
        last_seen_at: now
      },
      {
        session_id: "bridge_solantir_terminal",
        app_id: "solantir-terminal",
        app_name: "Solantir Terminal",
        status: "follow_on_manifest",
        bridge_health: "manifest_only",
        handshake_status: "manifest_loaded",
        bridge_transport: "ipc",
        active_tasks: [],
        latest_task_result: {
          label: "Refresh watchlist",
          resultSummary: "Solantir stays in follow-on review for the first post-1.0 bridge activation."
        },
        granted_capabilities: [
          { capability_key: "task.run", status: "granted" },
          { capability_key: "context.read", status: "granted" },
          { capability_key: "approval.request", status: "review" }
        ],
        notes: ["Still held in manifest-only follow-on review."],
        last_seen_at: now
      }
    ]
  }
};
baseSnapshot.workspaces[0].serviceManagement = [
  {
    serviceId: "wsl2",
    label: "WSL2",
    serviceCategory: "runtime_substrate",
    installSource: "windows_feature",
    currentHealthStatus: "healthy",
    lastVerificationResult: "passed",
    lastRepairAction: {},
    managementMode: "fluxio_managed",
    version: "WSL2",
    details: "WSL2 detected and ready."
  },
  {
    serviceId: "openclaw",
    label: "OpenClaw",
    serviceCategory: "runtime",
    installSource: "npm",
    currentHealthStatus: "healthy",
    lastVerificationResult: "passed",
    lastRepairAction: {},
    managementMode: "fluxio_managed",
    version: "2026.4.14",
    details: "Installed and aligned with the latest npm release."
  },
  {
    serviceId: "hermes",
    label: "Hermes",
    serviceCategory: "runtime",
    installSource: "wsl_script",
    currentHealthStatus: "healthy",
    lastVerificationResult: "passed",
    lastRepairAction: {},
    managementMode: "fluxio_managed",
    version: "v0.9.0",
    details: "Installed in WSL2 and aligned with the latest upstream release."
  },
  {
    serviceId: "filesystem_mcp",
    label: "Filesystem MCP",
    serviceCategory: "mcp_tool_server",
    installSource: "npx @modelcontextprotocol/server-filesystem .",
    currentHealthStatus: "recommended",
    lastVerificationResult: "not_run",
    lastRepairAction: {},
    managementMode: "fluxio_managed",
    version: "",
    details: "Safe workspace inspection."
  },
  {
    serviceId: "mind-tower",
    label: "Mind Tower",
    serviceCategory: "connected_app_bridge",
    installSource: "http",
    currentHealthStatus: "healthy",
    lastVerificationResult: "passed",
    lastRepairAction: {},
    managementMode: "externally_managed",
    version: "",
    details: "Monitoring bridge connected and verified."
  }
];
baseSnapshot.workspaces[0].serviceManagementSummary = {
  totalItems: 5,
  healthyCount: 4,
  needsAttentionCount: 1,
  runtimeCount: 2,
  toolServerCount: 1,
  bridgeCount: 1
};
baseSnapshot.setupHealth.serviceManagement = [
  {
    serviceId: "wsl2",
    label: "WSL2",
    serviceCategory: "runtime_substrate",
    installSource: "windows_feature",
    currentHealthStatus: "healthy",
    lastVerificationResult: "passed",
    lastRepairAction: {},
    managementMode: "fluxio_managed",
    version: "WSL2",
    details: "WSL2 detected and ready.",
    required: true
  },
  {
    serviceId: "uv",
    label: "uv",
    serviceCategory: "tooling",
    installSource: "winget",
    currentHealthStatus: "healthy",
    lastVerificationResult: "passed",
    lastRepairAction: {},
    managementMode: "fluxio_managed",
    version: "0.7.20",
    details: "Installed and reachable.",
    required: true
  },
  {
    serviceId: "openclaw",
    label: "OpenClaw",
    serviceCategory: "runtime",
    installSource: "npm",
    currentHealthStatus: "healthy",
    lastVerificationResult: "passed",
    lastRepairAction: {},
    managementMode: "fluxio_managed",
    version: "2026.4.14",
    details: "Installed and aligned with the latest npm release.",
    required: true
  },
  {
    serviceId: "hermes",
    label: "Hermes",
    serviceCategory: "runtime",
    installSource: "wsl_script",
    currentHealthStatus: "healthy",
    lastVerificationResult: "passed",
    lastRepairAction: {},
    managementMode: "fluxio_managed",
    version: "v0.9.0",
    details: "Installed in WSL2 and aligned with the latest upstream release.",
    required: true
  },
  {
    serviceId: "telegram_ready",
    label: "Telegram escalation",
    serviceCategory: "connected_app_bridge",
    installSource: "telegram_destination",
    currentHealthStatus: "missing",
    lastVerificationResult: "blocked",
    lastRepairAction: {},
    managementMode: "fluxio_managed",
    version: "",
    details: "Add a Telegram destination so long unattended runs can escalate approvals.",
    required: false
  }
];
baseSnapshot.setupHealth.serviceManagementSummary = {
  totalItems: 5,
  healthyCount: 4,
  needsAttentionCount: 1,
  fluxioManagedCount: 5,
  externalCount: 0
};
baseSnapshot.skillLibrary.managementSummary = {
  totalSkills: 4,
  needsTestCount: 2,
  reviewedReusableCount: 1,
  learnedCount: 1,
  disabledCount: 0
};
baseSnapshot.skillLibrary.recommendedPacks = [
  {
    label: "Repo Scan",
    execution_capable: true,
    originType: "curated",
    editableStatus: "available",
    testStatus: "recommended",
    promotionState: "recommended",
    lastUsedAt: null,
    lastHelpedAt: null
  }
];
baseSnapshot.skillLibrary.curatedPacks = [
  {
    label: "Verification Suite",
    execution_capable: false,
    originType: "curated",
    editableStatus: "active",
    testStatus: "reviewed",
    promotionState: "reviewed",
    lastUsedAt: "2026-04-01T12:00:00Z",
    lastHelpedAt: "2026-04-01T12:00:00Z",
    description: "Reusable verification defaults for Python and frontend missions."
  }
];
baseSnapshot.skillLibrary.userInstalledSkills = [
  {
    label: "Local Builder Notes",
    executionCapable: true,
    originType: "user_authored",
    editableStatus: "active",
    testStatus: "sample_ready",
    promotionState: "reviewed",
    lastUsedAt: "2026-04-02T18:00:00Z",
    lastHelpedAt: "2026-04-02T18:00:00Z",
    description: "A locally authored builder helper under review inside Skill Studio."
  }
];
baseSnapshot.skillLibrary.learnedSkills = [
  {
    label: "Approval Recovery Pattern",
    execution_capable: false,
    originType: "learned",
    editableStatus: "active",
    testStatus: "untested",
    promotionState: "learning",
    lastUsedAt: "2026-04-02T21:15:00Z",
    lastHelpedAt: "2026-04-02T21:15:00Z",
    description: "Promote approval recovery into a reusable reviewed skill after a successful test run."
  }
];
baseSnapshot.workflowStudio.managementSummary = {
  recipeCount: 4,
  reviewedCount: 4,
  blockedCount: 0
};
baseSnapshot.workflowStudio.recipes = baseSnapshot.workflowStudio.recipes.map((item) => ({
  ...item,
  reviewStatus: "reviewed",
  runtimeChoice: item.workflowId === "agent_long_run" ? "openclaw_or_hermes" : "openclaw",
  skillIds: item.workflowId === "skill_authoring" ? ["Local Builder Notes", "Approval Recovery Pattern"] : ["Repo Scan"],
  serviceIds: item.workflowId === "skill_authoring" ? ["uv", "hermes"] : ["wsl2", "filesystem_mcp"],
  verificationDefaults: ["python -m pytest tests -q", "npm run frontend:build"]
}));
var liveReviewFixture = (() => {
  const snapshot = clone(baseSnapshot);
  snapshot.missions = [
    {
      mission_id: "mission_skill_studio",
      workspace_id: "workspace_primary",
      runtime_id: "hermes",
      selected_profile: "builder",
      title: "Stabilize skill studio management",
      objective: "Make installed, reusable, and needs-test skill lanes easier to supervise and improve.",
      run_budget: { mode: "Autopilot" },
      state: {
        status: "running",
        current_cycle_phase: "execute",
        cycle_count: 3,
        last_verification_result: "passed",
        remaining_steps: ["Review weak skills", "Route fixes into skill studio"],
        verification_failures: [],
        active_step_id: "skill_audit",
        last_plan_summary: "Hermes is indexing skills, identifying weak packs, and preparing quality actions."
      },
      proof: {
        summary: "Installed skills and learned packs are now being compared against execution readiness.",
        pending_approvals: [],
        failed_checks: []
      },
      missionLoop: {
        continuityState: "running",
        continuityDetail: "Skill studio audit is still in progress.",
        timeBudget: {
          budgetHours: 6,
          elapsedSeconds: 9420,
          remainingSeconds: 12180,
          status: "running",
          runUntilBehavior: "pause_on_failure"
        }
      },
      execution_scope: {
        strategy: "workspace_root",
        execution_root: "C:/Users/paul/Projects/vibe-coding-platform/t3code/apps/web"
      },
      plan_revisions: [
        {
          revision_id: "rev_skill_1",
          trigger: "skill_audit",
          summary: "Inspect installed skills, sort by quality, and queue improvements.",
          created_at: now,
          steps: [
            { title: "Index reusable skills", status: "completed" },
            { title: "Review low-confidence skills", status: "in_progress" },
            { title: "Open skill studio with filtered queue", status: "pending" }
          ]
        }
      ],
      action_history: [
        {
          action_id: "action_skill_1",
          executed_at: now,
          proposal: {
            kind: "runtime_delegate",
            title: "Delegate skill coverage audit to Hermes",
            sourceKind: "delegated"
          },
          gate: { status: "not_required" },
          result: {
            result_summary: "Hermes is indexing installed skills and identifying packs that still need tests.",
            sourceKind: "delegated"
          }
        }
      ],
      delegated_runtime_sessions: [
        {
          delegated_id: "delegated_skill_studio",
          runtime_id: "hermes",
          status: "running",
          last_event: "Indexing installed skills and test coverage.",
          detail: "Hermes is auditing the skill library and prioritizing weak packs.",
          heartbeat_status: "healthy",
          heartbeat_age_seconds: 12,
          execution_target: "workspace_root",
          execution_root: "C:/Users/paul/Projects/vibe-coding-platform/t3code/apps/web",
          execution_target_detail: "Workspace-root review lane for skill packages and management metadata.",
          updated_at: now,
          pending_approval: {},
          approval_history: [],
          latest_events: [
            { event_id: "evt_skill_1", kind: "runtime.output", message: "Indexing installed skills and test coverage.", status: "running" }
          ]
        }
      ]
    },
    {
      mission_id: "mission_bridge_context",
      workspace_id: "workspace_primary",
      runtime_id: "openclaw",
      selected_profile: "builder",
      title: "Map bridge context and app follow-up surfaces",
      objective: "Compare bridge sessions, context previews, and callback readiness without blocking the main UI mission.",
      run_budget: { mode: "Autopilot" },
      state: {
        status: "queued",
        current_cycle_phase: "plan",
        cycle_count: 1,
        last_verification_result: "pending",
        remaining_steps: ["Wait for the main UI review mission to clear workspace contention", "Inspect bridge context rows"],
        verification_failures: [],
        active_step_id: "bridge_queue",
        last_plan_summary: "This thread is queued behind the main workbench mission and is waiting for workspace access."
      },
      proof: {
        summary: "Bridge context inspection is staged and ready once the current workspace lock clears.",
        pending_approvals: [],
        failed_checks: []
      },
      missionLoop: {
        continuityState: "resume_available",
        continuityDetail: "Queued behind the active review mission.",
        timeBudget: {
          budgetHours: 3,
          elapsedSeconds: 900,
          remainingSeconds: 9900,
          status: "queued",
          runUntilBehavior: "pause_on_failure"
        }
      },
      execution_scope: {
        strategy: "workspace_root",
        execution_root: "C:/Users/paul/Projects/vibe-coding-platform/desktop-ui"
      },
      plan_revisions: [
        {
          revision_id: "rev_bridge_1",
          trigger: "workspace_collision",
          summary: "Queue this bridge-context review until the active UI mission releases the workspace.",
          created_at: now,
          steps: [
            { title: "Queue behind current workspace lock", status: "in_progress" },
            { title: "Inspect bridge session summaries", status: "pending" }
          ]
        }
      ],
      action_history: [],
      delegated_runtime_sessions: []
    },
    {
      mission_id: "mission_live_review",
      workspace_id: "workspace_primary",
      runtime_id: "openclaw",
      selected_profile: "builder",
      title: "Redesign delegated approval workbench",
      objective: "Tighten the mission control UI, add fixture preview mode, and keep delegated approvals obvious.",
      run_budget: { mode: "Autopilot" },
      state: {
        status: "needs_approval",
        current_cycle_phase: "execute",
        cycle_count: 2,
        last_verification_result: "pending",
        last_replan_reason: "delegated_approval",
        remaining_steps: ["Review new approval surface", "Patch delegated-lane stack", "Run fixture-backed UI check"],
        verification_failures: [],
        active_step_id: "step_review",
        pending_mutating_actions: 1,
        execution_scope: { execution_root: "C:/Users/paul/Projects/vibe-coding-platform" },
        planner_loop_status: "paused",
        last_plan_summary: "Planner paused after a delegated lane asked for approval on a high-risk action."
      },
      proof: {
        summary: "Approve delegated deploy simulation before Fluxio continues.",
        pending_approvals: ["Approve delegated deploy simulation?"],
        failed_checks: []
      },
      missionLoop: {
        currentCyclePhase: "execute",
        cycleCount: 2,
        lastVerificationResult: "pending",
        lastVerificationSummary: "Verification is still pending.",
        lastReplanReason: "delegated_approval",
        lastReplanTrigger: "delegated_approval",
        improvementQueue: [{ title: "Split planner panel into approval rail and execution rail", priority: "high" }],
        resumeReady: true,
        continuityState: "approval_waiting",
        continuityDetail: "Approve delegated deploy simulation?",
        currentRuntimeLane: "openclaw delegated approval lane",
        timeBudget: {
          budgetHours: 12,
          elapsedSeconds: 18720,
          remainingSeconds: 24480,
          status: "approval_waiting",
          runUntilBehavior: "pause_on_failure",
          lastPauseReason: "Approve delegated deploy simulation?"
        }
      },
      changed_files: ["desktop-ui/FluxioDesktop.jsx", "desktop-ui/styles.css", "tests/test_desktop_ui_contract.py"],
      proof_artifacts: ["Approval screenshot pending", "Mission diff review queued", "Desktop verification pass required"],
      execution_scope: { strategy: "git_worktree", execution_root: "C:/Users/paul/Projects/.fluxio-worktrees-vibe/live-review" },
      execution_policy: { approval_mode: "tiered" },
      plan_revisions: [
        {
          revision_id: "rev_live_2",
          trigger: "delegated_approval",
          summary: "Planner paused to request approval for a delegated deploy simulation.",
          created_at: now,
          steps: [
            { title: "Review current delegated lane output", status: "completed" },
            { title: "Approve delegated deploy simulation", status: "in_progress" },
            { title: "Continue UI refinement after approval", status: "pending" }
          ]
        }
      ],
      route_configs: [
        { role: "planner", provider: "openai", model: "gpt-5.4", budget_class: "premium", explanation: "Better planning quality." },
        { role: "executor", provider: "openai", model: "gpt-5.4-mini", budget_class: "efficient", explanation: "Cheaper execution." }
      ],
      effectiveRouteContract: {
        roles: [
          { role: "planner", provider: "openai", model: "gpt-5.4", budgetClass: "premium", effort: "high", source: "workspace_override", reason: "Keep approval planning explicit." },
          { role: "executor", provider: "openai", model: "gpt-5.4-mini", budgetClass: "efficient", effort: "medium", source: "workspace_override", reason: "Execution stays cheaper during UI iteration." },
          { role: "verifier", provider: "openai", model: "gpt-5.4", budgetClass: "premium", effort: "high", source: "profile_default", reason: "Verification still uses the stronger route." }
        ]
      },
      action_history: [
        {
          action_id: "action_live_1",
          executed_at: now,
          proposal: {
            kind: "runtime_delegate",
            title: "Delegate deploy simulation to OpenClaw",
            policy_decision: "auto_run",
            target_scope: "worktree",
            sourceKind: "delegated"
          },
          gate: { status: "not_required" },
          result: { result_summary: "Delegated runtime lane launched under Fluxio supervision.", sourceKind: "delegated" }
        },
        {
          action_id: "action_live_2",
          executed_at: now,
          proposal: {
            kind: "file_patch",
            title: "Patch mission review surface",
            policy_decision: "requires_approval",
            target_scope: "worktree",
            sourceKind: "local"
          },
          gate: { status: "pending" },
          result: { result_summary: "Waiting for operator approval.", sourceKind: "local" }
        }
      ],
      delegated_runtime_sessions: [
        {
          delegated_id: "delegated_live_review",
          runtime_id: "openclaw",
          status: "waiting_for_approval",
          last_event: "Approve delegated deploy simulation?",
          detail: "Delegated runtime is waiting for approval.",
          heartbeat_status: "healthy",
          heartbeat_age_seconds: 18,
          execution_target: "isolated_worktree",
          execution_root: "C:/Users/paul/Projects/.fluxio-worktrees-vibe/live-review",
          execution_target_detail: "Isolated worktree review lane for desktop UI changes.",
          updated_at: now,
          pending_approval: { prompt: "Approve delegated deploy simulation?" },
          approval_history: [],
          latest_events: [
            { event_id: "evt_live_review_1", kind: "runtime.phase", message: "Deploy simulation reached approval gate.", status: "running" },
            { event_id: "evt_live_review_2", kind: "approval.request", message: "Approve delegated deploy simulation?", status: "waiting" }
          ]
        }
      ],
      improvement_queue: [
        { title: "Split planner panel into approval rail and execution rail", reason: "The current planner stack is too dense.", priority: "high" }
      ],
      derived_tasks: [
        { title: "Add fixture-backed review mode", reason: "UI work needs fast scenario switching.", status: "pending" }
      ]
    }
  ];
  snapshot.inbox = [
    {
      missionId: "mission_live_review",
      channel: "telegram",
      destination: "123456789",
      ready: true,
      pendingCount: 1,
      previewMessage: "Approve delegated deploy simulation before Fluxio continues."
    }
  ];
  snapshot.activity = [
    { kind: "mission.queued", mission_id: "mission_bridge_context", message: "Bridge context thread queued behind the active UI mission.", timestamp: now, metadata: { queuePosition: 2, blockingMissionId: "mission_live_review" } },
    { kind: "runtime.output", mission_id: "mission_skill_studio", message: "Hermes indexed installed skills and flagged two packs for follow-up.", timestamp: now, metadata: { runtimeId: "hermes" } },
    ...snapshot.activity
  ];
  return {
    name: "Live Review",
    description: "Shows the delegated approval state while refining the operator workbench.",
    snapshot
  };
})();
var emptyStartFixture = (() => {
  const snapshot = clone(baseSnapshot);
  snapshot.workspaces = [];
  snapshot.missions = [];
  snapshot.activity = [];
  snapshot.inbox = [];
  snapshot.guidance.guidanceCards = [
    { card_id: "guide_add_workspace", title: "Add your first workspace", body: "Register a project to unlock missions and recommendations.", kind: "setup", panel: "Projects" }
  ];
  snapshot.guidance.productImprovements = [
    { item_id: "pi_empty", title: "Improve first-run empty states", reason: "The shell should feel guided even before the first mission exists.", priority: "high", category: "tutorial" }
  ];
  snapshot.onboarding.tutorial.currentStepId = "add_workspace";
  snapshot.onboarding.tutorial.isComplete = false;
  snapshot.onboarding.tutorial.completedSteps = ["detect_environment", "choose_profile"];
  return {
    name: "First Run",
    description: "Shows the no-workspace, no-mission onboarding state.",
    snapshot
  };
})();
var verificationFailureFixture = (() => {
  const snapshot = clone(baseSnapshot);
  snapshot.missions = [
    {
      mission_id: "mission_verification_failure",
      workspace_id: "workspace_primary",
      runtime_id: "hermes",
      selected_profile: "advanced",
      title: "Repair verification failure and broaden diagnosis",
      objective: "Hermes widened the search after repeated failures.",
      run_budget: { mode: "Deep Run" },
      state: {
        status: "verification_failed",
        current_cycle_phase: "replan",
        cycle_count: 3,
        last_verification_result: "failed",
        last_replan_reason: "verification_failed",
        remaining_steps: ["Inspect failing environment assumptions", "Retry focused fix"],
        verification_failures: ["python -m pytest tests -q"],
        active_step_id: "step_diag",
        pending_mutating_actions: 0,
        execution_scope: { execution_root: "C:/Users/paul/Projects/vibe-coding-platform" },
        planner_loop_status: "paused",
        last_plan_summary: "Verification failed twice, so Fluxio broadened diagnosis into environment and tooling."
      },
      proof: {
        summary: "Verification failed after execution. Review the widened diagnosis lane.",
        pending_approvals: [],
        failed_checks: ["python -m pytest tests -q"]
      },
      missionLoop: {
        currentCyclePhase: "replan",
        cycleCount: 3,
        lastVerificationResult: "failed",
        lastVerificationSummary: "Failed: python -m pytest tests -q",
        lastReplanReason: "verification_failed",
        lastReplanTrigger: "verification_failed",
        improvementQueue: [{ title: "Add automatic screenshot proof for failing UIs", priority: "medium" }],
        resumeReady: true,
        continuityState: "resume_available",
        continuityDetail: "Mission can resume safely from the last recorded session.",
        currentRuntimeLane: "hermes verification lane",
        timeBudget: {
          budgetHours: 10,
          elapsedSeconds: 13200,
          remainingSeconds: 22800,
          status: "paused_after_failure",
          runUntilBehavior: "pause_on_failure",
          lastPauseReason: "Verification failed: python -m pytest tests -q"
        }
      },
      changed_files: ["src/grant_agent/runtime_worker.py", "desktop-ui/FluxioDesktop.jsx"],
      proof_artifacts: ["pytest failure log captured", "Environment diagnosis note drafted", "Retry plan waiting for review"],
      execution_scope: { strategy: "direct", execution_root: "C:/Users/paul/Projects/vibe-coding-platform" },
      execution_policy: { approval_mode: "tiered" },
      plan_revisions: [
        {
          revision_id: "rev_fail_3",
          trigger: "verification_failed",
          summary: "Planner broadened root-cause search after repeated failure.",
          created_at: now,
          steps: [
            { title: "Inspect dependency graph", status: "completed" },
            { title: "Check environment assumptions", status: "in_progress" },
            { title: "Retry focused fix", status: "pending" }
          ]
        }
      ],
      route_configs: [
        { role: "planner", provider: "openai", model: "gpt-5.4", budget_class: "premium", explanation: "Broader diagnosis benefits from stronger planning." },
        { role: "verifier", provider: "openai", model: "gpt-5.4", budget_class: "premium", explanation: "Verification quality matters here." }
      ],
      effectiveRouteContract: {
        roles: [
          { role: "planner", provider: "openai", model: "gpt-5.4", budgetClass: "premium", effort: "high", source: "profile_default", reason: "Broader diagnosis benefits from stronger planning." },
          { role: "executor", provider: "openai", model: "gpt-5.4-mini", budgetClass: "efficient", effort: "medium", source: "profile_default", reason: "Execution stays efficient during diagnosis." },
          { role: "verifier", provider: "openai", model: "gpt-5.4", budgetClass: "premium", effort: "high", source: "workspace_override", reason: "Verification quality matters here." }
        ]
      },
      action_history: [
        {
          action_id: "action_fail_1",
          executed_at: now,
          proposal: {
            kind: "test_run",
            title: "Run verification for environment diagnosis",
            policy_decision: "auto_run",
            target_scope: "workspace"
          },
          gate: { status: "not_required" },
          result: { result_summary: "test_run completed with exit code 1." }
        }
      ],
      delegated_runtime_sessions: [],
      improvement_queue: [
        { title: "Add automatic screenshot proof for failing UIs", reason: "Verification failures need faster visual evidence.", priority: "medium" }
      ],
      derived_tasks: [
        { title: "Inspect environment assumptions", reason: "Repeated failure triggered broader diagnosis.", status: "in_progress" }
      ]
    }
  ];
  snapshot.inbox = [
    {
      missionId: "mission_verification_failure",
      channel: "telegram",
      destination: "123456789",
      ready: true,
      pendingCount: 1,
      previewMessage: "Verification failed after execution. Review the widened diagnosis lane."
    }
  ];
  return {
    name: "Verification Failure",
    description: "Shows a widened-diagnosis state after repeated verification failures.",
    snapshot
  };
})();
var approvalResumedFixture = (() => {
  const snapshot = clone(baseSnapshot);
  snapshot.missions = [
    {
      mission_id: "mission_approval_resumed",
      workspace_id: "workspace_primary",
      runtime_id: "hermes",
      selected_profile: "builder",
      title: "Resume after delegated approval",
      objective: "Hermes resumed after operator approval and is finishing the remaining lane.",
      run_budget: { mode: "Autopilot" },
      state: {
        status: "queued",
        current_cycle_phase: "execute",
        cycle_count: 4,
        last_verification_result: "pending",
        last_verification_summary: "Verification is still pending.",
        last_replan_reason: "delegated_approval",
        last_replan_trigger: "delegated_approval",
        continuity_state: "resume_available",
        continuity_detail: "Mission can resume safely from the last recorded session.",
        remaining_steps: ["Resume delegated lane", "Collect proof", "Run verification"],
        verification_failures: [],
        active_step_id: "step_resume",
        pending_mutating_actions: 0,
        execution_scope: { execution_root: "C:/Users/paul/Projects/vibe-coding-platform" },
        planner_loop_status: "paused",
        last_plan_summary: "Approval was granted while the operator was away. Fluxio is ready to resume from the same mission state."
      },
      proof: {
        summary: "Latest approval requirement approved. Resume mission to continue.",
        pending_approvals: [],
        failed_checks: []
      },
      missionLoop: {
        currentCyclePhase: "execute",
        cycleCount: 4,
        lastVerificationResult: "pending",
        lastVerificationSummary: "Verification is still pending.",
        lastReplanReason: "delegated_approval",
        lastReplanTrigger: "delegated_approval",
        improvementQueue: [{ title: "Persist clearer resume banners after approval", priority: "medium" }],
        resumeReady: true,
        continuityState: "resume_available",
        continuityDetail: "Mission can resume safely from the last recorded session.",
        currentRuntimeLane: "hermes resumed verification lane",
        timeBudget: {
          budgetHours: 12,
          elapsedSeconds: 21540,
          remainingSeconds: 21660,
          status: "resume_available",
          runUntilBehavior: "continue_until_blocked",
          lastPauseReason: "Waiting for operator to resume from the last recorded checkpoint."
        }
      },
      changed_files: ["src/grant_agent/mission_control.py", "docs/FLUXIO_1_0_RELEASE.md"],
      proof_artifacts: ["Approval resolution recorded", "Delegated lane completion report ready"],
      execution_scope: { strategy: "direct", execution_root: "C:/Users/paul/Projects/vibe-coding-platform" },
      route_configs: [
        { role: "planner", provider: "openai", model: "gpt-5.4", budget_class: "premium", explanation: "Planner keeps the resumed mission coherent." }
      ],
      effectiveRouteContract: {
        roles: [
          { role: "planner", provider: "openai", model: "gpt-5.4", budgetClass: "premium", effort: "high", source: "profile_default", reason: "Planner keeps the resumed mission coherent." },
          { role: "executor", provider: "openai", model: "gpt-5.4-mini", budgetClass: "efficient", effort: "medium", source: "workspace_override", reason: "Execution stays lighter for resumed follow-through." },
          { role: "verifier", provider: "openai", model: "gpt-5.4", budgetClass: "premium", effort: "high", source: "profile_default", reason: "Verification still uses the premium route." }
        ]
      },
      action_history: [
        {
          action_id: "action_resume_1",
          executed_at: now,
          proposal: { kind: "runtime_delegate", title: "Delegate verification follow-up to Hermes", policy_decision: "auto_run", target_scope: "workspace", sourceKind: "delegated" },
          gate: { status: "not_required" },
          result: { result_summary: "Delegated runtime lane resumed under Fluxio supervision.", sourceKind: "delegated" }
        }
      ],
      delegated_runtime_sessions: [
        {
          delegated_id: "delegated_approval_resumed",
          runtime_id: "hermes",
          status: "completed",
          last_event: "Delegated lane resumed after approval and finished cleanly.",
          detail: "Delegated lane completed while the desktop was away.",
          heartbeat_status: "healthy",
          heartbeat_age_seconds: 7,
          execution_target: "workspace_root",
          execution_root: "C:/Users/paul/Projects/vibe-coding-platform",
          execution_target_detail: "Workspace-root resume lane under Hermes supervision.",
          updated_at: now,
          pending_approval: {},
          approval_history: [
            { status: "approved", resolved_by: "operator", resolved_at: now }
          ],
          latest_events: [
            { event_id: "evt_resume_1", kind: "approval.resolved", message: "Delegated approval approved by operator.", status: "approved" },
            { event_id: "evt_resume_2", kind: "session.completed", message: "Delegated lane resumed after approval and finished cleanly.", status: "completed" }
          ]
        }
      ],
      improvement_queue: [
        { title: "Persist clearer resume banners after approval", reason: "Operators need immediate clarity after returning to the app.", priority: "medium" }
      ],
      derived_tasks: []
    }
  ];
  return {
    name: "Approval Resumed",
    description: "Shows the restart-safe state after approval was granted and the mission can resume.",
    snapshot
  };
})();
var longRunResumedFixture = (() => {
  const snapshot = clone(baseSnapshot);
  snapshot.missions = [
    {
      mission_id: "mission_long_run",
      workspace_id: "workspace_primary",
      runtime_id: "openclaw",
      selected_profile: "advanced",
      title: "Long-run mission resumed after several hours",
      objective: "OpenClaw planned, executed, verified, and left a clear continuity trail.",
      run_budget: { mode: "Deep Run" },
      state: {
        status: "running",
        current_cycle_phase: "verify",
        cycle_count: 7,
        last_verification_result: "passed",
        last_verification_summary: "Passed 2 verification check(s).",
        last_replan_reason: "action_completed",
        last_replan_trigger: "action_completed",
        continuity_state: "delegated_active",
        continuity_detail: "openclaw lane is still active and restart-safe.",
        remaining_steps: ["Summarize proof bundle", "Prepare final review"],
        verification_failures: [],
        active_step_id: "step_summary",
        pending_mutating_actions: 0,
        execution_scope: { execution_root: "C:/Users/paul/Projects/vibe-coding-platform" },
        planner_loop_status: "running",
        last_plan_summary: "Fluxio completed the main execution and is waiting for the final proof summary before closing the mission."
      },
      proof: {
        summary: "Delegated runtime lane is active. Fluxio will continue when it finishes.",
        passed_checks: ["python -m pytest tests -q", "npm run frontend:build"],
        pending_approvals: [],
        failed_checks: []
      },
      missionLoop: {
        currentCyclePhase: "verify",
        cycleCount: 7,
        lastVerificationResult: "passed",
        lastVerificationSummary: "Passed 2 verification check(s).",
        lastReplanReason: "action_completed",
        lastReplanTrigger: "action_completed",
        improvementQueue: [{ title: "Add a calmer post-run state for long unattended missions", priority: "medium" }],
        resumeReady: true,
        continuityState: "delegated_active",
        continuityDetail: "openclaw lane is still active and restart-safe.",
        currentRuntimeLane: "openclaw long-run summary lane",
        timeBudget: {
          budgetHours: 16,
          elapsedSeconds: 36120,
          remainingSeconds: 21480,
          status: "delegated_active",
          runUntilBehavior: "continue_until_blocked",
          lastPauseReason: "Delegated runtime lane is still active and restart-safe."
        }
      },
      changed_files: ["desktop-ui/FluxioDesktop.jsx", "desktop-ui/styles.css", "artifacts/ui-audit/long-run-proof.png"],
      proof_artifacts: ["Completion report draft", "Verification proof bundle assembled", "Return summary pending operator review"],
      route_configs: [
        { role: "planner", provider: "openai", model: "gpt-5.4", budget_class: "premium", explanation: "Stronger planner for long unattended loops." }
      ],
      effectiveRouteContract: {
        roles: [
          { role: "planner", provider: "openai", model: "gpt-5.4", budgetClass: "premium", effort: "high", source: "profile_default", reason: "Long unattended loops benefit from stronger planning." },
          { role: "executor", provider: "openai", model: "gpt-5.4-mini", budgetClass: "efficient", effort: "medium", source: "workspace_override", reason: "Execution can stay efficient over long runs." },
          { role: "verifier", provider: "openai", model: "gpt-5.4", budgetClass: "premium", effort: "high", source: "profile_default", reason: "Verification remains premium for unattended completion." }
        ]
      },
      action_history: [
        {
          action_id: "action_long_1",
          executed_at: now,
          proposal: { kind: "runtime_delegate", title: "Delegate long-run verification sweep", policy_decision: "auto_run", target_scope: "workspace", sourceKind: "delegated" },
          gate: { status: "not_required" },
          result: { result_summary: "Delegated long-run verification sweep is still active.", sourceKind: "delegated" }
        }
      ],
      delegated_runtime_sessions: [
        {
          delegated_id: "delegated_long_run",
          runtime_id: "openclaw",
          status: "running",
          last_event: "Preparing the final proof summary and completion report.",
          detail: "Delegated lane is still running.",
          heartbeat_status: "healthy",
          heartbeat_age_seconds: 23,
          execution_target: "isolated_worktree",
          execution_root: "C:/Users/paul/Projects/vibe-coding-platform",
          execution_target_detail: "Long-run summary lane in an isolated worktree.",
          updated_at: now,
          pending_approval: {},
          approval_history: [],
          latest_events: [
            { event_id: "evt_long_run_1", kind: "runtime.phase", message: "Verification passed and the lane moved into summary mode.", status: "running" },
            { event_id: "evt_long_run_2", kind: "runtime.output", message: "Preparing the final proof summary and completion report.", status: "running" }
          ]
        }
      ],
      improvement_queue: [
        { title: "Add a calmer post-run state for long unattended missions", reason: "Returning operators need faster long-run orientation.", priority: "medium" }
      ],
      derived_tasks: []
    }
  ];
  return {
    name: "Long-Run Resumed",
    description: "Shows a long unattended mission with clear continuity, proof, and active delegated state.",
    snapshot
  };
})();
var fixtures = {
  live_review: liveReviewFixture,
  first_run: emptyStartFixture,
  verification_failure: verificationFailureFixture,
  approval_resumed: approvalResumedFixture,
  long_run_resumed: longRunResumedFixture
};
function listFixtureOptions() {
  return Object.entries(fixtures).map(([id, item]) => ({
    id,
    name: item.name,
    description: item.description
  }));
}
function buildFixtureSnapshot(id) {
  const fixture = fixtures[id];
  if (!fixture) {
    return null;
  }
  return {
    snapshot: clone(fixture.snapshot),
    onboarding: clone(fixture.snapshot.onboarding),
    pendingApprovals: [],
    pendingQuestions: [],
    telegramReady: true,
    meta: {
      id,
      name: fixture.name,
      description: fixture.description
    }
  };
}

// desktop-ui/fluxioHelpers.js
function titleizeToken(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
function runtimeLabel(runtimeId) {
  if (runtimeId === "openclaw") return "OpenClaw";
  if (runtimeId === "hermes") return "Hermes";
  return runtimeId || "Runtime";
}
function missionStatusTone(status) {
  switch (status) {
    case "completed":
    case "healthy":
    case "passed":
      return "good";
    case "blocked":
    case "verification_failed":
    case "failed":
    case "missing":
      return "bad";
    case "needs_approval":
    case "waiting_for_approval":
    case "verify_pending":
    case "install_available":
    case "installing":
    case "detected":
    case "running":
      return "warn";
    default:
      return "neutral";
  }
}
function formatDurationCompact(totalSeconds) {
  const seconds = Math.max(0, Number(totalSeconds || 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds % 3600 / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}
function selectedWorkspace(snapshot, selectedWorkspaceId) {
  const workspaces = snapshot?.workspaces || [];
  return workspaces.find((item) => item.workspace_id === selectedWorkspaceId) || workspaces[0] || null;
}
function selectedMission(snapshot, selectedMissionId) {
  const missions = snapshot?.missions || [];
  return missions.find((item) => item.mission_id === selectedMissionId) || missions[missions.length - 1] || null;
}
function activeProfileId(snapshot, onboarding, workspace, mission) {
  const tutorial = onboarding?.tutorial || snapshot?.onboarding?.tutorial || {};
  return workspace?.user_profile || mission?.selected_profile || tutorial.selectedProfile || snapshot?.profiles?.defaultProfile || "builder";
}
function profileDetails(snapshot, profileId) {
  return snapshot?.profiles?.details?.[profileId] || {};
}
function currentProfileParameters(snapshot, profileId, workspace) {
  return profileDetails(snapshot, profileId)?.parameters || workspace?.profileParameters || {};
}
function visibilityProfileState(profileParams) {
  const level = profileParams?.visibilityLevel || "balanced";
  return {
    level,
    guided: level === "guided",
    detailed: level === "detailed" || level === "expert",
    expert: level === "expert"
  };
}
function describeApprovalBehavior(level) {
  switch (level) {
    case "strict":
      return "Fluxio asks before risky work, explains more, and keeps the loop safer.";
    case "hands_free":
      return "Fluxio keeps moving unless proof, safety, or environment boundaries force an interruption.";
    default:
      return "Fluxio keeps moving on bounded work, but still stops at meaningful risk and trust boundaries.";
  }
}
function describeExplanationBehavior(level) {
  switch (level) {
    case "high":
      return "Expect more plain-language explanation and slower, safer framing.";
    case "low":
      return "Expect denser system truth and less narration.";
    default:
      return "Expect concise, practical explanation without hiding the real state.";
  }
}
function describeVisibilityBehavior(level) {
  switch (level) {
    case "guided":
      return "The UI foregrounds the next action and hides less-important detail until needed.";
    case "expert":
      return "The UI keeps more raw state visible so advanced operators can inspect without extra clicks.";
    case "detailed":
      return "The UI keeps routing, proof, and runtime detail visible during the mission.";
    default:
      return "The UI balances clarity with enough system truth to stay trustworthy.";
  }
}
function describeProfileFit(profileId) {
  switch (profileId) {
    case "beginner":
      return "Best when you want more help, more explanation, and lower-risk autonomy.";
    case "advanced":
      return "Best when you already know the shape of the work and want faster iteration.";
    case "experimental":
      return "Best when you accept broader autonomy and more aggressive exploration.";
    default:
      return "Best when you want a reliable default that still feels free to build.";
  }
}
function missionObjectivePlaceholder(profileId) {
  switch (profileId) {
    case "beginner":
      return "Describe the outcome in plain language, what good looks like, and what Fluxio should avoid.";
    case "advanced":
      return "State the target change, proof bar, and any constraints Fluxio must keep.";
    case "experimental":
      return "State the target, proof bar, and what exploration or broader search is acceptable.";
    default:
      return "Describe the outcome, proof expectations, and what success looks like.";
  }
}
function missionChecksPlaceholder(profileId) {
  switch (profileId) {
    case "beginner":
      return "One per line: app still opens, tests pass, summary is easy to review";
    case "advanced":
      return "One per line: targeted tests pass, patch is coherent, proof is captured";
    case "experimental":
      return "One per line: baseline verified, new branch explored, best path justified";
    default:
      return "One per line: tests pass, run report written, proof summary ready";
  }
}
function resolveMissionPauseReason(mission) {
  const missionLoop = mission?.missionLoop || {};
  const timeBudget = missionLoop.timeBudget;
  return missionLoop.pauseReason || timeBudget?.lastPauseReason || mission?.state?.last_budget_pause_reason || mission?.proof?.pending_approvals?.[0] || (missionLoop.continuityState === "approval_waiting" ? missionLoop.continuityDetail : "") || mission?.state?.stop_reason || mission?.state?.pause_reason || mission?.state?.pauseReason || "";
}
function resolveCurrentRuntimeLane(mission) {
  const currentRuntimeLane = mission?.missionLoop?.currentRuntimeLane || mission?.state?.current_runtime_lane;
  return currentRuntimeLane || `${runtimeLabel(mission?.runtime_id)} primary lane ${titleizeToken(
    mission?.state?.status || "draft"
  )}`;
}
function firstPendingQuestion(pendingQuestions) {
  return Array.isArray(pendingQuestions) ? pendingQuestions[0] || null : null;
}
function describeMissionKnownState(mission) {
  const missionLoop = mission?.missionLoop || {};
  const approvals = (mission?.proof?.pending_approvals || []).length;
  const failedChecks = (mission?.proof?.failed_checks || mission?.state?.verification_failures || []).length;
  const phase = missionLoop.currentCyclePhase || mission?.state?.current_cycle_phase || "plan";
  return `${titleizeToken(mission?.state?.status || "draft")} in ${titleizeToken(phase)}. ${approvals} approval ${approvals === 1 ? "item" : "items"} waiting. ${failedChecks} failed check${failedChecks === 1 ? "" : "s"}.`;
}
function describeMissionAssumption(mission, pendingQuestions) {
  if ((mission?.proof?.pending_approvals || []).length > 0) {
    return "The proposed next step is directionally right, but the risk is high enough to keep operator approval in the loop.";
  }
  if (firstPendingQuestion(pendingQuestions)) {
    return "Fluxio does not have enough scope clarity to keep moving safely without your answer.";
  }
  if ((mission?.state?.verification_failures || []).length > 0) {
    return "The first failed check is the best current lead, but the root cause may still be broader than the latest patch.";
  }
  const pauseReason = resolveMissionPauseReason(mission);
  if (pauseReason) {
    return `Fluxio can continue once this boundary is resolved: ${pauseReason}.`;
  }
  return "Current context is strong enough to keep moving inside the mission boundary without another clarification pass.";
}
function describeMissionNeedsInput(mission, pendingQuestions) {
  const pendingApproval = mission?.proof?.pending_approvals?.[0];
  if (pendingApproval) {
    return pendingApproval;
  }
  const question = firstPendingQuestion(pendingQuestions);
  if (question?.question) {
    return question.question;
  }
  if ((mission?.state?.verification_failures || []).length > 0) {
    return `Review ${mission.state.verification_failures[0]} and decide whether Fluxio should repair, retry, or widen the diagnosis.`;
  }
  return "Nothing right now. Fluxio has enough context to continue.";
}
function describeNextOperatorAction(mission, pendingQuestions) {
  const pendingApprovals = (mission?.proof?.pending_approvals || []).length;
  const pendingQuestionCount = Array.isArray(pendingQuestions) ? pendingQuestions.length : 0;
  const verificationFailures = (mission?.state?.verification_failures || []).length;
  const pauseReason = resolveMissionPauseReason(mission);
  if (pendingApprovals > 0) {
    return "Review the next approval so Fluxio can continue without losing the mission thread.";
  }
  if (pendingQuestionCount > 0) {
    return "Answer the pending planning question so Fluxio can continue with the right scope and context.";
  }
  if (verificationFailures > 0) {
    return "Inspect the first failed verification and decide whether Fluxio should repair, retry, or widen the search.";
  }
  if (pauseReason) {
    return `Resolve the pause reason: ${pauseReason}.`;
  }
  return "Let the mission run, watch proof and time budget, and step in only when the next real boundary appears.";
}
function previewLabel(previewMode, previewMeta) {
  if (previewMode === "live") {
    if (previewMeta?.id && previewMeta.id !== "live") {
      return `${previewMeta?.name || "Review fixture"} fallback`;
    }
    return "Live backend";
  }
  return `${previewMeta?.name || "Fixture"} preview`;
}

// desktop-ui/MissionControlPrimitives.jsx
var import_jsx_runtime = require("react/jsx-runtime");
function StatusPill({ tone = "neutral", children, strong = false }) {
  return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { className: `status-pill tone-${tone} ${strong ? "strong" : ""}`.trim(), children });
}
function ActionButton({
  children,
  onClick,
  variant = "ghost",
  disabled = false,
  title = "",
  type = "button"
}) {
  return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(
    "button",
    {
      className: `action-btn ${variant}`.trim(),
      disabled,
      onClick,
      title,
      type,
      children
    }
  );
}
function Field({ label, children, className = "" }) {
  return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", { className: `field ${className}`.trim(), children: [
    /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: label }),
    children
  ] });
}
function SectionHeader({ eyebrow, title, summary, actions }) {
  return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { className: "section-header", children: [
    /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { className: "section-title-block", children: [
      eyebrow ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", { className: "eyebrow", children: eyebrow }) : null,
      /* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", { children: title }),
      summary ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", { className: "section-summary", children: summary }) : null
    ] }),
    actions ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: "section-actions", children: actions }) : null
  ] });
}
function Modal({ open, title, summary, onClose, children, actions }) {
  if (!open) {
    return null;
  }
  return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: "modal-backdrop", role: "presentation", onClick: onClose, children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(
    "section",
    {
      "aria-modal": "true",
      className: "modal-panel",
      onClick: (event) => event.stopPropagation(),
      role: "dialog",
      children: [
        /* @__PURE__ */ (0, import_jsx_runtime.jsx)(
          SectionHeader,
          {
            actions: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ActionButton, { onClick: onClose, variant: "ghost", children: "Close" }),
            summary,
            title
          }
        ),
        /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: "modal-body", children }),
        actions ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: "modal-actions", children: actions }) : null
      ]
    }
  ) });
}

// desktop-ui/missionControlModel.js
function asList(value) {
  return Array.isArray(value) ? value : [];
}
function uniq(items) {
  return [...new Set(asList(items).filter(Boolean).map((item) => String(item).trim()))];
}
function asInt(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.round(parsed) : fallback;
}
function clampPercent(value) {
  return Math.max(0, Math.min(100, asInt(value)));
}
function listLabel(value) {
  if (!value) {
    return "Item";
  }
  return String(value);
}
function ratioPercent(part, total) {
  if (total <= 0) {
    return 0;
  }
  return clampPercent(Math.round(part / total * 100));
}
function scoreTone(score) {
  if (score >= 85) {
    return "good";
  }
  if (score >= 65) {
    return "warn";
  }
  return "bad";
}
function serviceStatusTone(status) {
  if (["healthy", "connected", "ready", "passed"].includes(status)) {
    return "good";
  }
  if ([
    "missing",
    "blocked",
    "failed",
    "error",
    "degraded",
    "unavailable",
    "stale"
  ].includes(status)) {
    return "bad";
  }
  return "warn";
}
function topBarLiveStatus(mission, pendingQuestions, pendingApprovals) {
  const approvalCount = asList(pendingApprovals).length + asList(mission?.proof?.pending_approvals).length;
  if (!mission) {
    return { label: "No active mission", tone: "neutral" };
  }
  if (approvalCount > 0) {
    return { label: "Needs approval", tone: "warn" };
  }
  if (asList(pendingQuestions).length > 0) {
    return { label: "Needs operator input", tone: "warn" };
  }
  if (asList(mission?.state?.verification_failures).length > 0) {
    return { label: "Verification failed", tone: "bad" };
  }
  if (mission?.state?.status === "completed") {
    return { label: "Completed", tone: "good" };
  }
  if (mission?.state?.status === "running") {
    return { label: "Active run", tone: "good" };
  }
  return {
    label: titleizeToken(mission?.state?.status || mission?.missionLoop?.continuityState || "active"),
    tone: missionStatusTone(mission?.state?.status)
  };
}
function deriveCurrentTask(mission) {
  const latestRevision = asList(mission?.plan_revisions).slice(-1)[0];
  const revisionStep = asList(latestRevision?.steps).find((step) => step?.status === "in_progress");
  if (revisionStep?.title) {
    return revisionStep.title;
  }
  if (asList(mission?.state?.remaining_steps).length > 0) {
    return mission.state.remaining_steps[0];
  }
  if (asList(mission?.delegated_runtime_sessions).length > 0) {
    const delegated = mission.delegated_runtime_sessions[0];
    return delegated?.detail || delegated?.last_event || "Delegated runtime lane active";
  }
  return mission?.proof?.summary || "Waiting for the next mission checkpoint.";
}
function deriveNextCheckpoint(mission) {
  const latestRevision = asList(mission?.plan_revisions).slice(-1)[0];
  const nextRevisionStep = asList(latestRevision?.steps).find((step) => step?.status === "pending");
  if (nextRevisionStep?.title) {
    return nextRevisionStep.title;
  }
  const remaining = asList(mission?.state?.remaining_steps);
  if (remaining.length > 1) {
    return remaining[1];
  }
  if (mission?.state?.status === "completed") {
    return "Finalize review and close mission";
  }
  return "Awaiting next checkpoint";
}
function deriveChanged(mission, workspace) {
  if (asList(mission?.changed_files).length > 0) {
    return mission.changed_files;
  }
  const actionTitles = asList(mission?.action_history).map((action) => action?.proposal?.title).filter(Boolean);
  if (actionTitles.length > 0) {
    return actionTitles.slice(0, 5);
  }
  const git = workspace?.gitSnapshot || {};
  if (git.repoDetected) {
    return [
      `${git.stagedCount || 0} staged`,
      `${git.unstagedCount || 0} unstaged`,
      `${git.untrackedCount || 0} untracked`
    ];
  }
  return ["No changed files captured yet."];
}
function deriveChecks(mission) {
  const checks = [
    ...asList(mission?.proof?.passed_checks).map((item) => `Passed: ${item}`),
    ...asList(mission?.proof?.failed_checks).map((item) => `Failed: ${item}`),
    ...asList(mission?.state?.verification_failures).map((item) => `Failure: ${item}`)
  ];
  const actionResults = asList(mission?.action_history).map(
    (action) => action?.result?.result_summary || action?.result?.error || action?.result?.stdout
  );
  return uniq([...checks, ...actionResults]).slice(0, 8);
}
function deriveArtifacts(mission, inbox) {
  const explicit = asList(mission?.proof_artifacts);
  if (explicit.length > 0) {
    return explicit.slice(0, 8);
  }
  return uniq([
    mission?.proof?.summary,
    mission?.missionLoop?.continuityDetail,
    inbox?.previewMessage,
    asList(mission?.delegated_runtime_sessions)[0]?.detail
  ]).slice(0, 6);
}
function deriveVerificationSummary(mission) {
  return mission?.missionLoop?.lastVerificationSummary || mission?.state?.last_verification_summary || mission?.proof?.summary || "Verification detail has not been recorded yet.";
}
function deriveDiffSummary(workspace) {
  const git = workspace?.gitSnapshot || {};
  if (!git.repoDetected) {
    return "No Git diff detected for this workspace.";
  }
  return `${git.branch || "unknown"} \xB7 ${git.stagedCount || 0} staged \xB7 ${git.unstagedCount || 0} unstaged \xB7 ${git.untrackedCount || 0} untracked`;
}
function deriveQueueItems(mission, pendingQuestions, pendingApprovals) {
  const items = [];
  for (const approval of [
    ...asList(mission?.proof?.pending_approvals),
    ...asList(pendingApprovals).map((item) => item?.reason || item?.toolId || item?.approval_id)
  ]) {
    if (!approval) {
      continue;
    }
    items.push({
      tone: "warn",
      type: "Approval",
      title: approval,
      reason: "Mission is paused at a review boundary."
    });
  }
  for (const question of asList(pendingQuestions)) {
    items.push({
      tone: "warn",
      type: "Question",
      title: question?.question || "Operator input required",
      reason: question?.summary || "Fluxio needs a scope answer before it can continue safely."
    });
  }
  for (const failure of asList(mission?.state?.verification_failures)) {
    items.push({
      tone: "bad",
      type: "Verification",
      title: failure,
      reason: "Review the failing check before approving additional execution."
    });
  }
  if (items.length === 0) {
    items.push({
      tone: "good",
      type: "Recommended",
      title: describeNextOperatorAction(mission, pendingQuestions),
      reason: mission?.proof?.summary || mission?.missionLoop?.continuityDetail || "Run can continue inside the current guardrails."
    });
  }
  return items.slice(0, 8);
}
function derivePrimaryAction(mission, queueItems) {
  const firstQueue = queueItems[0];
  if (!mission) {
    return {
      kind: "start",
      label: "Launch mission",
      reason: "Start one bounded mission to unlock proof, approvals, and a readable thread."
    };
  }
  if (firstQueue?.tone === "warn" || firstQueue?.tone === "bad") {
    return {
      kind: "queue",
      label: "Review queue",
      reason: firstQueue?.title || "A boundary needs judgment before Fluxio can continue."
    };
  }
  if (mission?.missionLoop?.continuityState === "resume_available" || mission?.state?.status === "queued") {
    return {
      kind: "resume",
      label: "Resume mission",
      reason: mission?.missionLoop?.continuityDetail || mission?.state?.continuity_detail || "Resume from the last safe checkpoint."
    };
  }
  if (mission?.state?.status === "completed") {
    return {
      kind: "proof",
      label: "Review proof",
      reason: deriveVerificationSummary(mission)
    };
  }
  return {
    kind: "proof",
    label: "Open proof",
    reason: deriveVerificationSummary(mission)
  };
}
function deriveThreadSections({ mission, pendingQuestions, workspace }) {
  if (!mission) {
    return [];
  }
  const currentTask = deriveCurrentTask(mission);
  const nextCheckpoint = deriveNextCheckpoint(mission);
  const pauseReason = resolveMissionPauseReason(mission);
  const knownState = describeMissionKnownState(mission);
  const assumptions = describeMissionAssumption(mission, pendingQuestions);
  const needsInput = describeMissionNeedsInput(mission, pendingQuestions);
  const changed = deriveChanged(mission, workspace).join(" \xB7 ");
  const verification = deriveVerificationSummary(mission);
  return [
    {
      id: "current-task",
      label: "Current task",
      body: currentTask,
      detail: `Next checkpoint: ${nextCheckpoint}`,
      tone: missionStatusTone(mission?.state?.status)
    },
    {
      id: "known-state",
      label: "What Fluxio knows",
      body: knownState,
      detail: resolveCurrentRuntimeLane(mission),
      tone: "neutral"
    },
    {
      id: "assumptions",
      label: "What Fluxio assumes",
      body: assumptions,
      detail: pauseReason ? `Pause boundary: ${pauseReason}` : "",
      tone: "neutral"
    },
    {
      id: "needs-input",
      label: "What Fluxio needs from operator",
      body: needsInput,
      detail: describeNextOperatorAction(mission, pendingQuestions),
      tone: "warn"
    },
    {
      id: "changed",
      label: "What changed",
      body: changed,
      detail: deriveDiffSummary(workspace),
      tone: "neutral"
    },
    {
      id: "proof",
      label: "What proof exists",
      body: verification,
      detail: mission?.proof?.summary || "Proof keeps accumulating while the mission runs.",
      tone: asList(mission?.state?.verification_failures).length > 0 ? "bad" : "good"
    }
  ];
}
function timelineEntry(kind, title, detail, tone = "neutral", meta = "") {
  return { kind, title, detail, tone, meta };
}
function deriveEvents(mission, snapshot) {
  const events = [];
  for (const session of asList(mission?.delegated_runtime_sessions)) {
    for (const event of asList(session?.latest_events)) {
      const kind = String(event?.kind || "runtime").toLowerCase();
      const eventDetail = kind === "runtime.phase_entered" ? `${titleizeToken(event?.data?.phase || "execute")} phase via ${titleizeToken(
        event?.data?.role || "route"
      )}${event?.data?.provider ? ` \xB7 ${titleizeToken(event.data.provider)}` : ""}${event?.data?.model ? ` \xB7 ${event.data.model}` : ""}` : kind === "runtime.route_switch_reason" ? event?.data?.reason || event?.message || session?.detail || "" : kind === "runtime.handoff" ? event?.data?.reason || event?.message || session?.detail || "" : session?.detail || session?.last_event || "";
      events.push(
        timelineEntry(
          event?.kind || "runtime",
          event?.message || "Runtime update",
          eventDetail,
          missionStatusTone(session?.status),
          runtimeLabel(session?.runtime_id)
        )
      );
    }
  }
  for (const action of asList(mission?.action_history)) {
    events.push(
      timelineEntry(
        action?.proposal?.kind || "action",
        action?.proposal?.title || action?.action_id || "Action",
        action?.result?.result_summary || action?.result?.error || action?.result?.stdout || "",
        action?.result?.error ? "bad" : action?.gate?.status === "pending" ? "warn" : "neutral",
        action?.executed_at || ""
      )
    );
  }
  for (const activity of asList(snapshot?.activity)) {
    events.push(
      timelineEntry(
        activity?.kind || "activity",
        activity?.message || "Activity update",
        "",
        activity?.kind === "approval.request" ? "warn" : "neutral",
        activity?.timestamp || ""
      )
    );
  }
  if (events.length === 0) {
    events.push(
      timelineEntry(
        "timeline",
        "Mission thread is waiting for the next event",
        "New actions, delegated lane events, and approvals will appear here."
      )
    );
  }
  return events.slice(0, 24);
}
function deriveConfidenceSurface({
  mission,
  snapshot,
  setupHealth,
  queueItems,
  pendingQuestions,
  pendingApprovals
}) {
  const release = snapshot?.releaseReadiness || {};
  const requiredGateSummary = release?.requiredGateSummary || {};
  const requiredPassed = asInt(requiredGateSummary?.passed);
  const requiredTotal = asInt(requiredGateSummary?.total);
  const requiredScore = clampPercent(
    requiredGateSummary?.score ?? ratioPercent(requiredPassed, requiredTotal)
  );
  const qualityScore = clampPercent(release?.qualityScore ?? 0);
  const releaseScore = clampPercent(release?.score ?? 0);
  const verificationFailures = asList(mission?.state?.verification_failures).length;
  const questionCount = asList(pendingQuestions).length;
  const approvalCount = asList(mission?.proof?.pending_approvals).length + asList(pendingApprovals).length;
  const missingDependencyCount = asList(setupHealth?.missingDependencies).length;
  const urgentQueueCount = queueItems.filter(
    (item) => item?.tone === "warn" || item?.tone === "bad"
  ).length;
  const frictionPenalty = Math.min(
    36,
    urgentQueueCount * 4 + questionCount * 4 + approvalCount * 3 + verificationFailures * 6 + missingDependencyCount * 5
  );
  const fallbackBase = requiredTotal > 0 ? requiredScore : qualityScore;
  const blendedBase = releaseScore > 0 ? releaseScore : fallbackBase;
  const confidenceScore = clampPercent(
    Math.round(blendedBase * 0.78 + requiredScore * 0.14 + qualityScore * 0.08) - frictionPenalty + (mission ? 4 : -4)
  );
  const setupSummary = setupHealth?.serviceManagementSummary || {
    totalItems: asList(setupHealth?.serviceManagement).length,
    healthyCount: asList(setupHealth?.serviceManagement).filter(
      (item) => serviceStatusTone(item?.currentHealthStatus) === "good"
    ).length
  };
  const environmentPercent = asInt(setupSummary?.totalItems) > 0 ? ratioPercent(asInt(setupSummary?.healthyCount), asInt(setupSummary?.totalItems)) : setupHealth?.environmentReady ? 100 : 40;
  const proofChecks = asList(release?.proofReadiness?.proofs);
  const proofPassed = proofChecks.filter((item) => item?.passed).length;
  const proofPercent = proofChecks.length > 0 ? ratioPercent(proofPassed, proofChecks.length) : mission ? 60 : 0;
  const continuityPercent = !mission ? 0 : mission?.state?.status === "completed" ? 100 : mission?.state?.status === "running" ? 84 : mission?.missionLoop?.continuityState === "resume_available" ? 78 : mission?.state?.status === "queued" ? 62 : 70;
  const operatorPercent = clampPercent(
    100 - Math.min(75, questionCount * 12 + approvalCount * 10 + verificationFailures * 15)
  );
  const phase = confidenceScore >= 85 && requiredPassed === requiredTotal && requiredTotal > 0 ? "Validation ready" : confidenceScore >= 70 ? "Close to validation" : "Hardening required";
  const nextActions = uniq([
    ...asList(release?.nextActions),
    ...queueItems.filter((item) => item?.tone === "warn" || item?.tone === "bad").map((item) => item?.title || item?.reason),
    ...asList(setupHealth?.blockerExplanations)
  ]).slice(0, 6);
  const gates = asList(release?.gates).slice(0, 10).map((gate) => ({
    gateId: gate?.gateId || gate?.label || "",
    label: gate?.label || "Gate",
    required: Boolean(gate?.required),
    passed: Boolean(gate?.passed),
    details: gate?.details || "",
    tone: gate?.passed ? "good" : gate?.required ? "bad" : "warn"
  }));
  return {
    score: confidenceScore,
    tone: scoreTone(confidenceScore),
    label: `${confidenceScore}% release confidence`,
    phase,
    releaseStatus: titleizeToken(release?.status || "building"),
    releaseScore,
    qualityScore,
    qualitySignals: {
      completionRate: asInt(release?.qualitySignals?.completionRate),
      delegatedRunRate: asInt(release?.qualitySignals?.delegatedRunRate),
      resumeRunRate: asInt(release?.qualitySignals?.resumeRunRate),
      resumeCompletionRate: asInt(release?.qualitySignals?.resumeCompletionRate),
      verificationPauseRate: asInt(release?.qualitySignals?.verificationPauseRate)
    },
    proofReady: Boolean(release?.proofReadiness?.ready),
    requiredGateSummary: {
      passed: requiredPassed,
      total: requiredTotal,
      score: requiredScore,
      label: requiredTotal > 0 ? `${requiredPassed}/${requiredTotal} required gates passed` : "Required gates not reported yet"
    },
    calculatedAt: release?.calculatedAt || "",
    milestones: [
      {
        id: "environment",
        label: "Environment and services",
        percent: environmentPercent,
        detail: asInt(setupSummary?.totalItems) > 0 ? `${asInt(setupSummary?.healthyCount)}/${asInt(setupSummary?.totalItems)} services healthy` : "Service health snapshot unavailable"
      },
      {
        id: "continuity",
        label: "Mission continuity",
        percent: continuityPercent,
        detail: mission ? titleizeToken(
          mission?.missionLoop?.continuityState || mission?.state?.status || "active"
        ) : "No active mission yet"
      },
      {
        id: "proof",
        label: "Proof and verification",
        percent: proofPercent,
        detail: proofChecks.length > 0 ? `${proofPassed}/${proofChecks.length} proving checks passed` : "Proof checks appear after first proving cycle"
      },
      {
        id: "operator",
        label: "Operator confidence",
        percent: operatorPercent,
        detail: questionCount + approvalCount + verificationFailures > 0 ? `${questionCount} questions \xB7 ${approvalCount} approvals \xB7 ${verificationFailures} failures` : "No active friction in queue"
      }
    ],
    gates,
    nextActions
  };
}
function deriveProfileStudio(snapshot, workspace, profileId, profileParams) {
  const profiles2 = snapshot?.profiles || {};
  const availableProfiles = asList(profiles2?.availableProfiles);
  const details = profiles2?.details || {};
  const activeDetail = details?.[profileId] || {};
  const activeAgent = activeDetail?.agent || {};
  const visibilityState = visibilityProfileState(profileParams);
  const profileRows = availableProfiles.slice(0, 10).map((name) => {
    const item = details?.[name] || {};
    const params = item?.parameters || {};
    return {
      id: name,
      label: titleizeToken(name),
      description: item?.description || describeProfileFit(name),
      approval: titleizeToken(params?.approvalStrictness || "tiered"),
      autonomy: titleizeToken(params?.autonomyLevel || "balanced"),
      visibility: titleizeToken(params?.visibilityLevel || "balanced"),
      density: titleizeToken(params?.uiDensity || "comfortable"),
      tone: name === profileId ? "good" : "neutral"
    };
  });
  return {
    activeProfileId: profileId,
    activeProfileLabel: titleizeToken(profileId),
    availableProfiles,
    activeDescription: activeDetail?.description || describeProfileFit(profileId),
    behavior: [
      {
        label: "Approval boundary",
        value: describeApprovalBehavior(profileParams?.approvalStrictness || "tiered")
      },
      {
        label: "Explanation style",
        value: describeExplanationBehavior(
          profileParams?.explanationLevel || activeAgent?.explanation_depth || "medium"
        )
      },
      {
        label: "Visibility policy",
        value: describeVisibilityBehavior(profileParams?.visibilityLevel || "balanced")
      },
      {
        label: "Profile fit",
        value: describeProfileFit(profileId)
      }
    ],
    visibilityState: {
      level: visibilityState?.level || "balanced",
      guided: Boolean(visibilityState?.guided),
      detailed: Boolean(visibilityState?.detailed),
      expert: Boolean(visibilityState?.expert)
    },
    workspacePolicy: [
      {
        label: "Current workspace profile",
        value: titleizeToken(workspace?.user_profile || profileId)
      },
      {
        label: "Preferred harness",
        value: titleizeToken(workspace?.preferred_harness || "fluxio_hybrid")
      },
      {
        label: "Routing strategy",
        value: titleizeToken(workspace?.routing_strategy || "profile_default")
      },
      {
        label: "Auto-optimize routing",
        value: workspace?.auto_optimize_routing ? "Enabled" : "Disabled"
      },
      {
        label: "Commit style",
        value: titleizeToken(workspace?.commit_message_style || "scoped")
      },
      {
        label: "Execution target",
        value: titleizeToken(workspace?.execution_target_preference || "profile_default")
      }
    ],
    profileRows
  };
}
function deriveServiceStudio(workspace, setupHealth) {
  const workspaceServices = asList(workspace?.serviceManagement);
  const setupServices = asList(setupHealth?.serviceManagement);
  const services = workspaceServices.length > 0 ? workspaceServices : setupServices;
  const summary = workspace?.serviceManagementSummary || setupHealth?.serviceManagementSummary || {};
  const normalized = services.map((item) => {
    const status = item?.currentHealthStatus || item?.lastVerificationResult || item?.status || "unknown";
    const tone = serviceStatusTone(status);
    const actions = [
      ...asList(item?.serviceActions),
      ...item?.verifyAction?.actionId ? [item.verifyAction] : []
    ].filter((action) => action?.actionId).map((action) => {
      const surface = action?.surface ? action.surface : action?.commandSurface?.startsWith("git.") ? "git" : action?.commandSurface?.startsWith("validate.") ? "validate" : "setup";
      return {
        actionId: action.actionId,
        label: action.label || action.actionId,
        commandSurface: action.commandSurface || "",
        detail: action.description || action.detail || action.followUp || "",
        requiresApproval: Boolean(action.requiresApproval),
        surface
      };
    });
    return {
      serviceId: item?.serviceId || item?.label || "service",
      label: item?.label || item?.serviceId || "Service",
      category: titleizeToken(item?.serviceCategory || "service"),
      status: titleizeToken(status),
      tone,
      managementMode: titleizeToken(item?.managementMode || "externally_managed"),
      required: Boolean(item?.required),
      details: [
        item?.details || "",
        item?.updateAvailable && item?.latestVersion ? `Latest ${item.latestVersion}` : ""
      ].filter(Boolean).join(" \xB7 "),
      version: item?.version || "",
      latestVersion: item?.latestVersion || "",
      updateAvailable: Boolean(item?.updateAvailable),
      actions
    };
  }).sort((left, right) => {
    const rank = { bad: 0, warn: 1, good: 2, neutral: 3 };
    const leftRank = rank[left.tone] ?? 3;
    const rightRank = rank[right.tone] ?? 3;
    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }
    return left.label.localeCompare(right.label);
  });
  return {
    summary: {
      totalItems: asInt(summary?.totalItems, normalized.length),
      healthyCount: asInt(
        summary?.healthyCount,
        normalized.filter((item) => item.tone === "good").length
      ),
      needsAttentionCount: asInt(
        summary?.needsAttentionCount,
        normalized.filter((item) => item.tone !== "good").length
      ),
      runtimeCount: asInt(summary?.runtimeCount),
      toolServerCount: asInt(summary?.toolServerCount),
      bridgeCount: asInt(summary?.bridgeCount)
    },
    services: normalized.slice(0, 20),
    urgent: normalized.filter((item) => item.tone === "bad" || item.tone === "warn").slice(0, 6),
    availableActionCount: normalized.reduce((total, item) => total + item.actions.length, 0)
  };
}
function skillPackTone(item) {
  if (item?.installed && item?.testStatus === "reviewed") {
    return "good";
  }
  if (item?.installed) {
    return "warn";
  }
  return item?.recommended ? "neutral" : "warn";
}
function deriveSkillStudio(snapshot, workspace) {
  const skillLibrary = snapshot?.skillLibrary || {};
  const summary = skillLibrary?.managementSummary || {};
  const curatedPacks = asList(skillLibrary?.curatedPacks);
  const recommendedPacks = asList(skillLibrary?.recommendedPacks);
  const workspaceRecommendations = asList(workspace?.recommendedSkillPacks);
  const recommended = (workspaceRecommendations.length > 0 ? workspaceRecommendations : recommendedPacks).slice(0, 8).map((item) => ({
    id: item?.packId || item?.pack_id || item?.label,
    label: item?.label || item?.packId || "Pack",
    description: item?.description || "",
    audience: titleizeToken(item?.audience || "all"),
    status: titleizeToken(item?.testStatus || item?.promotionState || "recommended"),
    tone: skillPackTone(item),
    installed: Boolean(item?.installed),
    executionCapable: Boolean(item?.execution_capable),
    guidanceOnly: Boolean(item?.guidance_only),
    permissions: asList(item?.permissions),
    profileSuitability: asList(item?.profile_suitability).map((entry) => titleizeToken(entry)),
    originType: titleizeToken(item?.originType || item?.source?.kind || "recommended"),
    testStatus: titleizeToken(item?.testStatus || "recommended")
  }));
  const curated = curatedPacks.slice(0, 10).map((item) => ({
    id: item?.packId || item?.pack_id || item?.label,
    label: item?.label || item?.packId || "Pack",
    status: titleizeToken(item?.testStatus || item?.promotionState || "active"),
    usageCount: asInt(item?.usageCount),
    helpedCount: asInt(item?.helpedCount),
    tone: skillPackTone(item),
    installed: Boolean(item?.installed),
    executionCapable: Boolean(item?.execution_capable),
    guidanceOnly: Boolean(item?.guidance_only),
    permissions: asList(item?.permissions),
    profileSuitability: asList(item?.profile_suitability).map((entry) => titleizeToken(entry)),
    originType: titleizeToken(item?.originType || item?.source?.kind || "curated"),
    testStatus: titleizeToken(item?.testStatus || "active")
  }));
  const allPacks = uniq([...recommended.map((item) => item.id), ...curated.map((item) => item.id)]);
  const needsAttention = curated.filter(
    (item) => item.status !== "Reviewed" || !item.installed || item.testStatus !== "Reviewed"
  );
  const executionReadyCount = curated.filter(
    (item) => item.installed && item.executionCapable && item.testStatus === "Reviewed"
  ).length;
  const coverageByProfile = {
    Beginner: curated.filter((item) => item.profileSuitability.includes("Beginner")).length,
    Builder: curated.filter((item) => item.profileSuitability.includes("Builder")).length,
    Advanced: curated.filter((item) => item.profileSuitability.includes("Advanced")).length
  };
  const nextQualityActions = uniq([
    asInt(summary?.needsTestCount) > 0 ? `Review and test ${asInt(summary?.needsTestCount)} skill pack(s) with missing verification status.` : "",
    recommended.some((item) => !item.installed) ? "Install or promote recommended packs before claiming full workflow coverage." : "",
    executionReadyCount < Math.max(1, Math.ceil(curated.length * 0.6)) ? "Increase execution-capable reviewed packs to support broader operator workflows." : "",
    asInt(summary?.learnedCount) === 0 ? "Capture at least one learned skill event from a real mission cycle." : ""
  ]).slice(0, 4);
  return {
    summary: {
      totalSkills: asInt(summary?.totalSkills, curatedPacks.length),
      reviewedReusableCount: asInt(summary?.reviewedReusableCount),
      needsTestCount: asInt(summary?.needsTestCount),
      learnedCount: asInt(summary?.learnedCount),
      disabledCount: asInt(summary?.disabledCount),
      installedCount: curatedPacks.filter((item) => item?.installed).length,
      executionReadyCount,
      uniquePackCount: allPacks.length
    },
    recommended,
    curated,
    needsAttention: needsAttention.slice(0, 8),
    coverageByProfile,
    nextQualityActions,
    capabilitiesNote: "Skill CRUD is not exposed as a dedicated control-room command yet, so this studio is review-first."
  };
}
function workflowTone(status) {
  if (status === "ready") {
    return "good";
  }
  if (status === "blocked") {
    return "bad";
  }
  return "warn";
}
function deriveWorkflowStudio(snapshot, profileId) {
  const studio = snapshot?.workflowStudio || {};
  const recipes = asList(studio?.recipes).map((item) => ({
    workflowId: item?.workflowId || item?.label || "",
    label: item?.label || "Workflow",
    description: item?.description || "",
    status: titleizeToken(item?.status || "available"),
    audience: titleizeToken(item?.audience || "all"),
    surface: titleizeToken(item?.surface || "builder_view"),
    reviewStatus: titleizeToken(item?.reviewStatus || "reviewed"),
    runtimeChoice: runtimeLabel(item?.runtimeChoice),
    skillIds: asList(item?.skillIds),
    serviceIds: asList(item?.serviceIds),
    verificationDefaults: asList(item?.verificationDefaults),
    tone: workflowTone(item?.status)
  }));
  const recommended = recipes.find(
    (item) => item.tone !== "bad" && ["All", titleizeToken(profileId), "Builder", "Beginner", "Advanced"].includes(
      item.audience
    )
  ) || recipes[0] || null;
  return {
    summary: {
      recipeCount: asInt(studio?.managementSummary?.recipeCount, recipes.length),
      reviewedCount: asInt(studio?.managementSummary?.reviewedCount),
      blockedCount: asInt(studio?.managementSummary?.blockedCount),
      recommendedMode: titleizeToken(studio?.recommendedMode || "agent")
    },
    recipes: recipes.slice(0, 10),
    recommended,
    learningQueue: asList(studio?.learningQueue).slice(0, 6)
  };
}
function deriveBuilderOps(workspace) {
  return {
    gitActions: asList(workspace?.gitActions).map((item) => ({
      actionId: item?.actionId || "",
      label: item?.label || item?.actionId || "Git action",
      detail: item?.detail || item?.command || "",
      requiresApproval: Boolean(item?.requiresApproval),
      surface: "git",
      tone: item?.requiresApproval ? "warn" : "neutral"
    })),
    validationActions: asList(workspace?.validationActions).map((item) => ({
      actionId: item?.actionId || "",
      label: item?.label || item?.actionId || "Validation action",
      detail: item?.detail || item?.command || "",
      requiresApproval: Boolean(item?.requiresApproval),
      surface: "validate",
      tone: item?.requiresApproval ? "warn" : "good"
    }))
  };
}
function roadmapState(done, blocked = false) {
  if (done) {
    return "done";
  }
  return blocked ? "blocked" : "next";
}
function roadmapTone(state) {
  if (state === "done") {
    return "good";
  }
  if (state === "blocked") {
    return "bad";
  }
  return "warn";
}
function deriveQualityRoadmap({
  confidence,
  mission,
  setupHealth,
  serviceStudio,
  skillStudio,
  workflowStudio,
  builderOps
}) {
  const requiredDone = confidence?.requiredGateSummary?.total > 0 && confidence?.requiredGateSummary?.passed >= confidence?.requiredGateSummary?.total;
  const completionRate = asInt(confidence?.qualitySignals?.completionRate);
  const delegatedRate = asInt(confidence?.qualitySignals?.delegatedRunRate);
  const resumeCompletionRate = asInt(confidence?.qualitySignals?.resumeCompletionRate);
  const verificationPauseRate = asInt(confidence?.qualitySignals?.verificationPauseRate);
  const serviceHealthy = asInt(serviceStudio?.summary?.needsAttentionCount) === 0 && asInt(setupHealth?.missingDependencies?.length) === 0;
  const skillQualityReady = asInt(skillStudio?.summary?.needsTestCount) === 0;
  const workflowReady = asInt(workflowStudio?.summary?.blockedCount) === 0;
  const proofReady = Boolean(confidence?.proofReady);
  const hasMission = Boolean(mission);
  const hasValidationAction = asList(builderOps?.validationActions).length > 0;
  const tracks = [
    {
      id: "required-gates",
      label: "Required gates stay green",
      state: roadmapState(requiredDone),
      detail: confidence?.requiredGateSummary?.label || "Required gate summary unavailable.",
      hint: requiredDone ? "All required gates are currently passing." : "Resolve failed required gates before quality tuning.",
      suggestedAction: hasValidationAction ? "Run validation action" : "",
      actionKind: hasValidationAction ? "validate" : ""
    },
    {
      id: "completion-rate",
      label: "Lift completion rate above 50%",
      state: roadmapState(completionRate >= 50, !hasMission),
      detail: `Current completion rate: ${completionRate}%`,
      hint: hasMission ? "Run bounded missions end-to-end and close them with proof." : "Launch a mission first to generate quality data.",
      suggestedAction: hasMission ? "Launch one bounded run" : "Start first mission",
      actionKind: "mission"
    },
    {
      id: "delegated-usage",
      label: "Lift delegated run rate above 20%",
      state: roadmapState(delegatedRate >= 20, !hasMission),
      detail: `Current delegated run rate: ${delegatedRate}%`,
      hint: "Use runtime lanes that exercise delegated execution with approval boundaries.",
      suggestedAction: "Launch delegated mission",
      actionKind: "mission"
    },
    {
      id: "resume-reliability",
      label: "Lift resumed-run completion above 60%",
      state: roadmapState(resumeCompletionRate >= 60, !hasMission),
      detail: `Current resumed completion rate: ${resumeCompletionRate}%`,
      hint: "Pause/resume real runs and ensure they still close with proof.",
      suggestedAction: "Run resume scenario",
      actionKind: "mission"
    },
    {
      id: "verification-friction",
      label: "Keep verification pauses below 25%",
      state: roadmapState(verificationPauseRate < 25),
      detail: `Current verification pause rate: ${verificationPauseRate}%`,
      hint: "Use validation actions continuously and tighten proof expectations.",
      suggestedAction: hasValidationAction ? "Run validation action" : "Review verification defaults",
      actionKind: hasValidationAction ? "validate" : ""
    },
    {
      id: "skill-quality",
      label: "Skill studio quality bar",
      state: roadmapState(skillQualityReady),
      detail: `${asInt(skillStudio?.summary?.needsTestCount)} pack(s) still need test/review coverage.`,
      hint: skillQualityReady ? "Skill packs are currently reviewed." : "Focus on packs marked as not reviewed or not installed.",
      suggestedAction: asList(skillStudio?.nextQualityActions)[0] || "Review skill studio inventory",
      actionKind: "skill"
    },
    {
      id: "service-health",
      label: "Service health stays stable",
      state: roadmapState(serviceHealthy),
      detail: `${asInt(serviceStudio?.summary?.needsAttentionCount)} service(s) need attention.`,
      hint: serviceHealthy ? "All tracked services are currently healthy." : "Repair service blockers before long unattended runs.",
      suggestedAction: "Run service repair action",
      actionKind: "service"
    },
    {
      id: "workflow-readiness",
      label: "Workflow recipes stay ready",
      state: roadmapState(workflowReady && proofReady),
      detail: `${asInt(workflowStudio?.summary?.blockedCount)} workflow(s) blocked \xB7 proof cycle ${proofReady ? "ready" : "not ready"}.`,
      hint: "Use one recommended workflow end-to-end and capture proof.",
      suggestedAction: "Execute recommended workflow",
      actionKind: "workflow"
    }
  ].map((item) => ({
    ...item,
    tone: roadmapTone(item.state)
  }));
  const doneCount = tracks.filter((item) => item.state === "done").length;
  const nextCount = tracks.filter((item) => item.state === "next").length;
  const blockedCount = tracks.filter((item) => item.state === "blocked").length;
  return {
    targetScore: 100,
    currentScore: confidence?.score || 0,
    gap: Math.max(0, 100 - (confidence?.score || 0)),
    doneCount,
    nextCount,
    blockedCount,
    tracks,
    headline: nextCount === 0 && blockedCount === 0 ? "Quality roadmap is complete." : `${nextCount + blockedCount} quality step(s) remain for 100%.`
  };
}
function classifyFeatureTruth({ mission, snapshot, setupHealth, previewMode }) {
  const realReady = [];
  const realSecondary = [];
  const fixtureOnly = [];
  const notReady = [];
  if (mission) {
    realReady.push("Mission thread and action history");
  }
  if ((snapshot?.workspaces || []).length > 0) {
    realReady.push("Workspace registration and runtime selection");
  }
  if ((snapshot?.workspaces || []).some((item) => asList(item?.serviceManagement).length > 0)) {
    realReady.push("Service management summary and health detail");
  }
  if ((snapshot?.skillLibrary?.curatedPacks || []).length > 0) {
    realReady.push("Skill catalog with reviewed pack metadata");
  }
  if ((snapshot?.workflowStudio?.recipes || []).length > 0) {
    realReady.push("Workflow recipe studio");
  }
  if (snapshot?.releaseReadiness?.score !== void 0) {
    realReady.push("Release-readiness scoring and gate evidence");
  }
  if ((snapshot?.runtimes || []).some((item) => item?.detected)) {
    realReady.push("Runtime detection and health telemetry");
  }
  if ((snapshot?.bridgeLab?.connectedSessions || []).length > 0) {
    realSecondary.push("Connected app bridge telemetry");
  }
  if ((snapshot?.skillLibrary?.recommendedPacks || []).length > 0) {
    realSecondary.push("Skill recommendation signals");
  }
  if (snapshot?.profiles?.availableProfiles?.length > 0) {
    realSecondary.push("Profile parameter matrix and behavior defaults");
  }
  if (previewMode !== "live") {
    fixtureOnly.push("Fixture-backed snapshot review");
  }
  fixtureOnly.push("Builder review controls");
  fixtureOnly.push("Live sync cadence controls");
  for (const blocker of asList(setupHealth?.blockerExplanations)) {
    notReady.push(blocker);
  }
  for (const gate of asList(snapshot?.releaseReadiness?.gates)) {
    if (gate?.required && !gate?.passed) {
      notReady.push(`${gate.label}: ${gate.details}`);
    }
  }
  if (asList(snapshot?.workspaces).length === 0) {
    notReady.push("No workspace selected");
  }
  if (!mission) {
    notReady.push("No active mission");
  }
  return {
    realReady: uniq(realReady),
    realSecondary: uniq(realSecondary),
    fixtureOnly: uniq(fixtureOnly),
    notReady: uniq(notReady)
  };
}
function deriveStateAudit({ mission, setupHealth }) {
  const status = mission?.state?.status || "none";
  const approvalWait = asList(mission?.proof?.pending_approvals).length > 0 || status === "needs_approval" || status === "waiting_for_approval";
  const verificationFailure = asList(mission?.state?.verification_failures).length > 0 || status === "verification_failed";
  const firstRun = !mission;
  const blockedSetup = !setupHealth?.environmentReady;
  return [
    {
      id: "first-run",
      label: "First run",
      state: firstRun ? "active" : "resolved",
      nextAction: firstRun ? "Pick workspace and launch one bounded mission." : "Already passed."
    },
    {
      id: "no-mission",
      label: "No mission",
      state: firstRun ? "active" : "resolved",
      nextAction: firstRun ? "Launch mission from the primary action button." : "Mission exists."
    },
    {
      id: "blocked-setup",
      label: "Blocked setup",
      state: blockedSetup ? "active" : "resolved",
      nextAction: blockedSetup ? asList(setupHealth?.blockerExplanations)[0] || "Run setup repair actions." : "Setup health is ready."
    },
    {
      id: "mission-launch",
      label: "Mission launch",
      state: mission ? "resolved" : "waiting",
      nextAction: mission ? "Mission launched." : "Pending first launch."
    },
    {
      id: "approval-wait",
      label: "Approval wait",
      state: approvalWait ? "active" : "resolved",
      nextAction: approvalWait ? "Review queue and approve or reject." : "No approval boundary active."
    },
    {
      id: "active-run",
      label: "Active run",
      state: status === "running" ? "active" : "resolved",
      nextAction: status === "running" ? "Monitor thread and proof deltas." : "Run is not currently active."
    },
    {
      id: "verification-failure",
      label: "Verification failure",
      state: verificationFailure ? "active" : "resolved",
      nextAction: verificationFailure ? asList(mission?.state?.verification_failures)[0] || "Open proof drawer." : "No current failure."
    },
    {
      id: "resumed-run",
      label: "Resumed run",
      state: mission?.missionLoop?.continuityState === "resume_available" || status === "queued" ? "active" : "resolved",
      nextAction: mission?.missionLoop?.continuityState === "resume_available" || status === "queued" ? "Use Resume mission." : "No resume boundary active."
    },
    {
      id: "completed-run",
      label: "Completed run",
      state: status === "completed" ? "active" : "resolved",
      nextAction: status === "completed" ? "Review proof and close out." : "Mission has not completed yet."
    }
  ];
}
function deriveEnvironmentLabel(setupHealth, mission, workspace) {
  const runtime = mission?.runtime_id || workspace?.default_runtime || asList(setupHealth?.dependencies).find((item) => item?.category === "agent_runtime")?.dependencyId;
  if (!runtime) {
    return "Environment status";
  }
  return `${runtimeLabel(runtime)} lane`;
}
function deriveElapsed(mission) {
  const seconds = mission?.missionLoop?.timeBudget?.elapsedSeconds || mission?.state?.elapsed_runtime_seconds;
  if (typeof seconds === "number") {
    return formatDurationCompact(seconds);
  }
  return "0m";
}
function deriveRemaining(mission) {
  const seconds = mission?.missionLoop?.timeBudget?.remainingSeconds || mission?.state?.remaining_runtime_seconds;
  if (typeof seconds === "number") {
    return formatDurationCompact(seconds);
  }
  return "Unknown";
}
function timeValue(value) {
  if (!value) {
    return Number.NaN;
  }
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}
function latestTimestamp(...values) {
  let best = "";
  let bestValue = Number.NEGATIVE_INFINITY;
  for (const value of values.flat()) {
    const score = timeValue(value);
    if (Number.isFinite(score) && score >= bestValue) {
      best = String(value);
      bestValue = score;
    }
  }
  return best;
}
function isTerminalMissionStatus(status) {
  return ["completed", "failed", "cancelled", "stopped"].includes(
    String(status || "").toLowerCase()
  );
}
function latestMeaningfulDelegatedEvent(mission) {
  for (const session of asList(mission?.delegated_runtime_sessions).slice().reverse()) {
    const event = asList(session?.latest_events).slice().reverse().find((item) => item?.message && item?.kind !== "session.heartbeat");
    if (event) {
      return event;
    }
  }
  return null;
}
function deriveMissionLatestTimestamp(mission) {
  return latestTimestamp(
    mission?.updated_at,
    mission?.state?.updated_at,
    mission?.missionLoop?.updatedAt,
    asList(mission?.action_history).map((item) => item?.executed_at),
    asList(mission?.plan_revisions).map((item) => item?.created_at),
    asList(mission?.delegated_runtime_sessions).map((item) => item?.updated_at)
  );
}
function deriveMissionLastMovement(mission) {
  const latestAction = asList(mission?.action_history).slice(-1)[0];
  if (latestAction?.result?.result_summary || latestAction?.proposal?.title) {
    return latestAction?.result?.result_summary || latestAction?.result?.error || latestAction?.proposal?.title;
  }
  const delegatedEvent = latestMeaningfulDelegatedEvent(mission);
  if (delegatedEvent?.message) {
    return delegatedEvent.message;
  }
  return mission?.state?.last_plan_summary || mission?.missionLoop?.continuityDetail || mission?.proof?.summary || "Waiting for the next mission movement.";
}
function deriveMissionExecutionPath(mission, workspace) {
  const delegated = asList(mission?.delegated_runtime_sessions).find(
    (item) => item?.execution_root || item?.workspace_root
  );
  return delegated?.execution_root || delegated?.workspace_root || mission?.execution_scope?.execution_root || mission?.state?.execution_scope?.execution_root || workspace?.root_path || "";
}
function pathLeafLabel(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const parts = text.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || text;
}
function missionNeedsAttention(mission) {
  return Boolean(
    asList(mission?.proof?.pending_approvals).length > 0 || asList(mission?.state?.verification_failures).length > 0 || ["needs_approval", "blocked", "verification_failed", "queued"].includes(
      mission?.state?.status || ""
    )
  );
}
function activityTone(activity) {
  const kind = String(activity?.kind || "").toLowerCase();
  const action = String(activity?.metadata?.action || "").toLowerCase();
  const message = `${kind} ${activity?.message || ""}`;
  if (/failed|error|verification_failed/.test(message)) {
    return "bad";
  }
  if (kind === "approval.request" || kind === "mission.queued" || /approval|blocked|queued/.test(message)) {
    return "warn";
  }
  if (action === "complete" || /completed|healthy|ready/.test(message)) {
    return "good";
  }
  return "neutral";
}
function deriveActivityDetail(activity, missionById) {
  const metadata = activity?.metadata || {};
  const missionTitle = missionById.get(activity?.mission_id)?.title || missionById.get(activity?.mission_id)?.objective || "";
  const blockingMissionTitle = missionById.get(metadata.blockingMissionId)?.title || missionById.get(metadata.blockingMissionId)?.objective || metadata.blockingMissionId || "";
  return uniq([
    missionTitle,
    metadata.runtimeId ? runtimeLabel(metadata.runtimeId) : metadata.runtime_id ? runtimeLabel(metadata.runtime_id) : "",
    metadata.provider ? `${titleizeToken(metadata.provider)}${metadata.model ? `:${metadata.model}` : ""}` : "",
    metadata.queuePosition ? `Queue ${metadata.queuePosition}` : "",
    metadata.action ? `Action ${titleizeToken(metadata.action)}` : "",
    metadata.autopilotStatus ? titleizeToken(metadata.autopilotStatus) : "",
    metadata.pauseReason ? `Pause ${titleizeToken(metadata.pauseReason)}` : "",
    metadata.blockerClass ? `Blocker ${titleizeToken(metadata.blockerClass)}` : "",
    blockingMissionTitle ? `Blocked by ${blockingMissionTitle}` : ""
  ]).join(" \xB7 ");
}
function deriveMissionNexus(mission, workspace) {
  const pendingApproval = asList(mission?.proof?.pending_approvals)[0];
  const verificationFailure = asList(mission?.state?.verification_failures)[0];
  const latestPlan = asList(mission?.plan_revisions).slice(-1)[0];
  const delegatedEvent = latestMeaningfulDelegatedEvent(mission);
  const status = mission?.state?.status || mission?.missionLoop?.continuityState || "active";
  const executionPath = deriveMissionExecutionPath(mission, workspace);
  let label = "";
  let reason = "";
  let tone = "neutral";
  if (verificationFailure) {
    label = "Verification nexus";
    reason = verificationFailure;
    tone = "bad";
  } else if (pendingApproval) {
    label = "Approval nexus";
    reason = pendingApproval;
    tone = "warn";
  } else if (["needs_approval", "blocked", "queued"].includes(status)) {
    label = "Operator nexus";
    reason = mission?.state?.last_plan_summary || mission?.missionLoop?.continuityDetail || deriveMissionLastMovement(mission);
    tone = "warn";
  } else if (latestPlan?.summary) {
    label = "Plan nexus";
    reason = latestPlan.summary;
    tone = "neutral";
  } else if (delegatedEvent?.message) {
    label = "Runtime nexus";
    reason = delegatedEvent.message;
    tone = missionStatusTone(status);
  } else {
    return null;
  }
  return {
    id: `nexus-${mission?.mission_id || mission?.title || reason}`,
    missionId: mission?.mission_id || "",
    title: mission?.title || mission?.objective || "Mission",
    label,
    reason,
    detail: deriveCurrentTask(mission),
    next: deriveNextCheckpoint(mission),
    tone,
    timestamp: deriveMissionLatestTimestamp(mission),
    workspaceName: workspace?.name || "Workspace",
    executionPath,
    folderLabel: pathLeafLabel(executionPath) || pathLeafLabel(workspace?.root_path || "")
  };
}
function deriveBuilderBoard({ mission, workspace, snapshot, confidence, uiMode = "agent" }) {
  const workspaceId = uiMode === "builder" ? "" : workspace?.workspace_id || "";
  const workspaces = asList(snapshot?.workspaces);
  const workspaceById = new Map(workspaces.map((item) => [item?.workspace_id, item]));
  const missions = asList(snapshot?.missions).filter(
    (item) => workspaceId ? item?.workspace_id === workspaceId : true
  );
  const missionById = new Map(missions.map((item) => [item?.mission_id, item]));
  const activeMissions = missions.filter((item) => !isTerminalMissionStatus(item?.state?.status));
  const blockedCount = activeMissions.filter((item) => missionNeedsAttention(item)).length;
  const delegatedLaneCount = activeMissions.reduce(
    (total, item) => total + asList(item?.delegated_runtime_sessions).filter(
      (session) => !["completed", "failed", "stopped"].includes(session?.status || "")
    ).length,
    0
  );
  const runtimeCount = new Set(activeMissions.map((item) => item?.runtime_id).filter(Boolean)).size;
  const selectedMissionId = mission?.mission_id || "";
  const productionHarness = snapshot?.harnessLab?.productionHarness || workspace?.preferred_harness || "fluxio_hybrid";
  const activeConversations = activeMissions.slice().sort((left, right) => {
    const delta = timeValue(deriveMissionLatestTimestamp(right)) - timeValue(deriveMissionLatestTimestamp(left));
    if (Number.isFinite(delta) && delta !== 0) {
      return delta;
    }
    return String(left?.title || left?.objective || "").localeCompare(
      String(right?.title || right?.objective || "")
    );
  }).map((item) => {
    const ownerWorkspace = workspaceById.get(item?.workspace_id) || workspace;
    const status = item?.state?.status || item?.missionLoop?.continuityState || "active";
    const executionPath = deriveMissionExecutionPath(item, ownerWorkspace);
    const providerTruth = item?.providerTruth || item?.missionLoop?.providerTruth || item?.state?.provider_runtime_truth || {};
    const activeRoute = providerTruth?.activeRoute || {};
    const blocker = item?.missionLoop?.blocker || item?.state?.blocker_classification || {};
    const stuckReason = blocker?.summary || resolveMissionPauseReason(item) || "";
    return {
      missionId: item?.mission_id || "",
      workspaceId: item?.workspace_id || "",
      workspaceName: ownerWorkspace?.name || "Workspace",
      workspacePath: ownerWorkspace?.root_path || "",
      folderLabel: pathLeafLabel(executionPath) || pathLeafLabel(ownerWorkspace?.root_path || ""),
      title: item?.title || item?.objective || "Mission",
      runtime: runtimeLabel(item?.runtime_id),
      statusLabel: titleizeToken(status),
      tone: missionStatusTone(item?.state?.status),
      selected: item?.mission_id === selectedMissionId,
      blocked: missionNeedsAttention(item),
      current: deriveCurrentTask(item),
      next: deriveNextCheckpoint(item),
      lastMovement: deriveMissionLastMovement(item),
      updatedAt: deriveMissionLatestTimestamp(item),
      pendingApprovals: asList(item?.proof?.pending_approvals).length,
      verificationFailures: asList(item?.state?.verification_failures).length,
      delegatedSessions: asList(item?.delegated_runtime_sessions).filter(
        (session) => !["completed", "failed", "stopped"].includes(session?.status || "")
      ).length,
      executionPath,
      harnessLabel: titleizeToken(item?.harness_id || productionHarness),
      providerLabel: activeRoute?.provider ? titleizeToken(activeRoute.provider) : "Unresolved",
      modelLabel: activeRoute?.model || "Profile default",
      routeRole: activeRoute?.role ? titleizeToken(activeRoute.role) : "Route",
      blockerClass: blocker?.class || "",
      stuckReason,
      nextCheckpointPrediction: deriveNextCheckpoint(item)
    };
  });
  const roots = workspaces.filter((item) => workspaceId ? item?.workspace_id === workspaceId : true).map((item) => {
    const workspaceConversations = activeConversations.filter(
      (entry) => entry.workspaceId === item?.workspace_id
    );
    const blocked = workspaceConversations.filter((entry) => entry.blocked).length;
    const delegated = workspaceConversations.reduce(
      (total, entry) => total + asInt(entry.delegatedSessions),
      0
    );
    return {
      workspaceId: item?.workspace_id || "",
      title: item?.name || "Workspace",
      path: item?.root_path || "",
      folderLabel: pathLeafLabel(item?.root_path),
      activeCount: workspaceConversations.length,
      blockedCount: blocked,
      delegatedCount: delegated,
      tone: blocked > 0 ? "warn" : workspaceConversations.length > 0 || item?.runtimeStatus?.detected ? "good" : "neutral"
    };
  }).sort((left, right) => {
    if (left.blockedCount !== right.blockedCount) {
      return right.blockedCount - left.blockedCount;
    }
    if (left.activeCount !== right.activeCount) {
      return right.activeCount - left.activeCount;
    }
    return String(left.title).localeCompare(String(right.title));
  });
  const nexuses = activeMissions.map((item) => deriveMissionNexus(item, workspaceById.get(item?.workspace_id) || workspace)).filter(Boolean).sort((left, right) => timeValue(right.timestamp) - timeValue(left.timestamp)).slice(0, 8);
  const whileAway = asList(snapshot?.activity).filter((item) => {
    if (!item?.mission_id) {
      return true;
    }
    const missionRow = missionById.get(item.mission_id);
    return workspaceId ? missionRow?.workspace_id === workspaceId : true;
  }).slice(0, 10).map((item, index) => ({
    id: `${item?.mission_id || "workspace"}-${item?.timestamp || index}-${item?.kind || "activity"}`,
    missionId: item?.mission_id || "",
    missionTitle: missionById.get(item?.mission_id)?.title || missionById.get(item?.mission_id)?.objective || "Workspace activity",
    label: titleizeToken(item?.kind || "activity"),
    message: item?.message || "Activity update",
    detail: deriveActivityDetail(item, missionById),
    tone: activityTone(item),
    timestamp: item?.timestamp || ""
  }));
  const nextUpSource = activeConversations.length > 0 ? activeConversations : [];
  const nextUp = nextUpSource.slice(0, 8).map((item) => ({
    missionId: item.missionId,
    title: item.title,
    statusLabel: item.statusLabel,
    runtime: item.runtime,
    summary: item.next,
    detail: item.blocked ? item.lastMovement : item.current,
    routeLabel: `${item.providerLabel} \xB7 ${item.modelLabel}`,
    checkpoint: item.nextCheckpointPrediction,
    tone: item.blocked ? "warn" : item.tone,
    updatedAt: item.updatedAt,
    selected: item.selected
  }));
  const stuckThreads = activeConversations.filter((item) => item.blocked || item.blockerClass || item.stuckReason).slice(0, 6).map((item) => ({
    missionId: item.missionId,
    title: item.title,
    blockerClass: titleizeToken(item.blockerClass || "operator_only"),
    reason: item.stuckReason || item.lastMovement || "Blocked without a recorded reason.",
    routeLabel: `${item.providerLabel} \xB7 ${item.modelLabel}`,
    runtime: item.runtime,
    tone: item.tone === "bad" ? "bad" : "warn"
  }));
  const winningRouteMap = /* @__PURE__ */ new Map();
  for (const item of activeConversations) {
    const key = `${item.runtime}|${item.providerLabel}|${item.modelLabel}`;
    const existing = winningRouteMap.get(key) || {
      key,
      runtime: item.runtime,
      provider: item.providerLabel,
      model: item.modelLabel,
      activeCount: 0,
      blockedCount: 0
    };
    existing.activeCount += 1;
    if (item.blocked) {
      existing.blockedCount += 1;
    }
    winningRouteMap.set(key, existing);
  }
  const winningRoutes = [...winningRouteMap.values()].sort((left, right) => {
    if (left.blockedCount !== right.blockedCount) {
      return left.blockedCount - right.blockedCount;
    }
    return right.activeCount - left.activeCount;
  }).slice(0, 4).map((item) => ({
    ...item,
    tone: item.blockedCount > 0 ? "warn" : "good",
    label: `${item.runtime} \xB7 ${item.provider} \xB7 ${item.model}`,
    detail: item.blockedCount > 0 ? `${item.activeCount} active \xB7 ${item.blockedCount} blocked` : `${item.activeCount} active and clear`
  }));
  const predictedCheckpoints = nextUp.map((item) => `${item.title}: ${item.checkpoint || item.summary}`).slice(0, 6);
  const changedWhileAway = whileAway.slice(0, 6).map((item) => `${item.missionTitle}: ${item.message}`);
  const summary = activeConversations.length > 0 ? `${activeConversations.length} active conversation${activeConversations.length === 1 ? "" : "s"} across ${Math.max(runtimeCount, 1)} runtime lane${Math.max(runtimeCount, 1) === 1 ? "" : "s"}. ${blockedCount > 0 ? `${blockedCount} need operator attention.` : "No operator block is active right now."} Top route: ${winningRoutes[0]?.label || "not resolved yet"}.` : "No active conversations. Builder stays ready for launch, runtime tuning, and review.";
  return {
    headline: activeConversations.length > 0 ? "Builder command deck" : "Builder readiness deck",
    summary,
    metrics: [
      {
        id: "active",
        label: "Active conversations",
        value: `${activeConversations.length}`,
        detail: activeConversations.length > 0 ? "Visible in the control board" : "Launch a mission to start the board",
        tone: activeConversations.length > 0 ? "good" : "neutral"
      },
      {
        id: "blocked",
        label: "Need attention",
        value: `${blockedCount}`,
        detail: blockedCount > 0 ? "Approvals, queue, or verification boundaries are open" : "No active blockers",
        tone: blockedCount > 0 ? "warn" : "good"
      },
      {
        id: "delegated",
        label: "Delegated lanes",
        value: `${delegatedLaneCount}`,
        detail: delegatedLaneCount > 0 ? "Hermes/OpenClaw sessions in flight" : "No live delegated lane right now",
        tone: delegatedLaneCount > 0 ? "neutral" : "warn"
      },
      {
        id: "harness",
        label: "Production harness",
        value: titleizeToken(productionHarness),
        detail: snapshot?.harnessLab?.recommendation || "Harness comparison is visible in Builder.",
        tone: blockedCount > 0 ? "warn" : "good"
      }
    ],
    activeConversations,
    roots,
    nexuses,
    whileAway,
    nextUp,
    stuckThreads,
    winningRoutes,
    changedWhileAway,
    predictedCheckpoints,
    selectedFocus: mission ? {
      missionId: mission.mission_id,
      title: mission.title || mission.objective || "Mission",
      current: deriveCurrentTask(mission),
      next: deriveNextCheckpoint(mission),
      lastMovement: deriveMissionLastMovement(mission),
      proof: deriveVerificationSummary(mission),
      updatedAt: deriveMissionLatestTimestamp(mission)
    } : null
  };
}
function priorityTone(priority) {
  const normalized = String(priority || "").toLowerCase();
  if (normalized === "high") {
    return "bad";
  }
  if (normalized === "medium") {
    return "warn";
  }
  if (normalized === "low") {
    return "good";
  }
  return "neutral";
}
function actionForGuidancePanel(panel) {
  const normalized = String(panel || "").toLowerCase();
  if (normalized === "auth") {
    return "open_auth";
  }
  if (normalized === "setup") {
    return "open_runtime";
  }
  if (normalized === "guidance") {
    return "open_profiles";
  }
  if (normalized === "projects") {
    return "open_workspace";
  }
  if (normalized === "missions") {
    return "open_mission";
  }
  if (normalized === "integrations") {
    return "open_escalation";
  }
  if (normalized === "builder_view" || normalized === "builder") {
    return "open_builder";
  }
  if (normalized === "skill_studio" || normalized === "skills") {
    return "open_skills";
  }
  return "open_builder";
}
function deriveTutorialStudio({
  mission,
  snapshot,
  setupHealth,
  profileId,
  workflowStudio
}) {
  const onboarding = snapshot?.onboarding || {};
  const guidance = snapshot?.guidance || {};
  const tutorial = onboarding?.tutorial || {};
  const completedSteps = asList(tutorial?.completedSteps);
  const steps = asList(tutorial?.steps).map((item, index) => {
    const status = String(
      item?.status || (completedSteps.includes(item?.step_id) ? "completed" : item?.step_id === tutorial?.currentStepId ? "current" : "pending")
    ).toLowerCase();
    return {
      id: item?.step_id || `step-${index}`,
      title: item?.title || `Step ${index + 1}`,
      description: item?.description || "",
      panel: item?.panel || "Builder",
      status: titleizeToken(status),
      done: status === "completed",
      current: status === "current" || status === "in_progress" || item?.step_id === tutorial?.currentStepId,
      tone: status === "completed" ? "good" : status === "pending" ? "neutral" : "warn",
      actionId: actionForGuidancePanel(item?.panel)
    };
  });
  const currentStep = steps.find((item) => item.current) || steps.find((item) => !item.done) || steps[steps.length - 1] || null;
  const motionMode = snapshot?.profiles?.details?.[profileId]?.ui?.motion || asList(guidance?.profileChoices).find((item) => item?.name === profileId)?.motion || "standard";
  const readiness = uniq([
    ...asList(onboarding?.nextActions),
    ...asList(setupHealth?.blockerExplanations)
  ]).slice(0, 4);
  const cards = asList(guidance?.guidanceCards).slice(0, 4).map((item) => ({
    id: item?.card_id || item?.title || "guide",
    title: item?.title || "Guidance",
    body: item?.body || "",
    panel: item?.panel || "Builder",
    kind: titleizeToken(item?.kind || "guide"),
    actionId: actionForGuidancePanel(item?.panel || item?.kind)
  }));
  const improvements = asList(guidance?.productImprovements).slice(0, 3).map((item) => ({
    id: item?.item_id || item?.title || "improvement",
    title: item?.title || "Improvement",
    reason: item?.reason || "",
    priority: titleizeToken(item?.priority || "medium"),
    category: titleizeToken(item?.category || "product"),
    tone: priorityTone(item?.priority)
  }));
  return {
    headline: tutorial?.isComplete ? "Tutorial complete" : currentStep?.title || "Finish guided setup",
    summary: tutorial?.isComplete ? "Builder is ready for real mission work. Keep the guide nearby for deliberate setup and escalation." : currentStep?.description || "Finish the guided path so Builder, runtime policy, and escalation all stay coherent.",
    progressLabel: `${completedSteps.length}/${Math.max(steps.length, 1)} complete`,
    currentStep,
    steps,
    cards,
    improvements,
    readiness,
    motionMode: titleizeToken(motionMode),
    recommendedWorkflow: workflowStudio?.recommended?.label || "Long-Run Agent Session",
    primaryActionId: currentStep?.actionId || "open_mission",
    primaryActionLabel: currentStep?.panel ? `Open ${currentStep.panel}` : mission ? "Keep building" : "Launch first mission"
  };
}
function deriveRecommendationStudio({
  mission,
  workspace,
  setupHealth,
  serviceStudio,
  skillStudio,
  workflowStudio,
  qualityRoadmap,
  builderBoard
}) {
  const struggleSignals = [];
  const approvalCount = asInt(asList(mission?.proof?.pending_approvals).length);
  const verificationCount = asInt(asList(mission?.state?.verification_failures).length);
  const serviceAttention = asInt(serviceStudio?.summary?.needsAttentionCount);
  const skillAttention = asInt(skillStudio?.summary?.needsTestCount);
  if (approvalCount > 0) {
    struggleSignals.push({
      id: "approval-friction",
      label: "Approval friction",
      detail: `${approvalCount} approval boundary is slowing the loop right now.`,
      tone: "warn",
      actionId: "open_queue"
    });
  }
  if (verificationCount > 0) {
    struggleSignals.push({
      id: "verification-friction",
      label: "Verification friction",
      detail: `${verificationCount} failed verification signal needs proof-first attention.`,
      tone: "bad",
      actionId: "open_proof"
    });
  }
  if (serviceAttention > 0) {
    struggleSignals.push({
      id: "runtime-drift",
      label: "Runtime drift",
      detail: `${serviceAttention} runtime or service item still needs repair or review.`,
      tone: "warn",
      actionId: "open_runtime"
    });
  }
  if (skillAttention > 0) {
    struggleSignals.push({
      id: "skill-gap",
      label: "Skill coverage gap",
      detail: `${skillAttention} skill pack(s) still need tests or promotion before they can be trusted.`,
      tone: "warn",
      actionId: "open_skills"
    });
  }
  if (struggleSignals.length === 0) {
    struggleSignals.push({
      id: "clear-lane",
      label: "No major blocker",
      detail: "Use the recommended workflow and keep Builder focused on the highest-value active conversation.",
      tone: "good",
      actionId: "open_mission"
    });
  }
  const skillRecommendations = uniq([
    ...asList(workspace?.skillRecommendations).map((item) => `${item?.label || "Skill"}||${item?.reason || ""}`),
    ...skillStudio.recommended.map((item) => `${item?.label || "Pack"}||${item?.description || ""}`)
  ]).slice(0, 4).map((item, index) => {
    const [label, reason] = String(item).split("||");
    return {
      id: `skill-recommendation-${index}-${label}`,
      label,
      reason
    };
  });
  const nextMoves = uniq([
    ...asList(qualityRoadmap?.tracks).filter((item) => item?.state !== "done").slice(0, 3).map((item) => `${item?.label || "Next move"}||${item?.suggestedAction || "Open"}||${item?.actionKind || ""}`),
    workflowStudio?.recommended?.label ? `${workflowStudio.recommended.label}||Recommended workflow for the current profile||workflow` : "",
    asList(setupHealth?.blockerExplanations)[0] ? `${asList(setupHealth?.blockerExplanations)[0]}||Resolve setup blocker before long unattended runs||runtime` : ""
  ]).slice(0, 4).map((item, index) => {
    const [label, detail, actionKind] = String(item).split("||");
    return {
      id: `recommendation-next-${index}`,
      label,
      detail,
      actionId: actionKind === "validate" ? "run_validation" : actionKind === "workflow" ? "open_workflow" : actionKind === "skill" ? "open_skills" : actionKind === "service" || actionKind === "runtime" ? "open_runtime" : "open_mission"
    };
  });
  return {
    headline: workflowStudio?.recommended?.label || "Builder recommendations",
    summary: builderBoard.activeConversations.length > 0 ? "Recommendations adapt to the active conversations, current blockers, and the packs that still need work." : "Recommendations are based on setup state, workflow readiness, and the gaps still blocking a strong first run.",
    struggleSignals: struggleSignals.slice(0, 4),
    skillRecommendations,
    nextMoves,
    learningQueue: asList(workflowStudio?.learningQueue).slice(0, 4).map((item, index) => ({
      id: `learning-${index}-${item?.title || item}`,
      title: item?.title || listLabel(item),
      priority: titleizeToken(item?.priority || "medium"),
      tone: priorityTone(item?.priority)
    })),
    activeConversationCount: builderBoard.activeConversations.length,
    blockedConversationCount: builderBoard.activeConversations.filter((item) => item.blocked).length,
    recommendedSurface: titleizeToken(workflowStudio?.recommended?.surface || "builder_view")
  };
}
function deriveLiveReviewStudio({
  mission,
  workspace,
  snapshot,
  previewMode,
  liveSyncSeconds,
  liveSyncSuspended,
  lastPushReason,
  isRefreshing,
  builderBoard
}) {
  const bridgeSessions = asList(snapshot?.bridgeLab?.connectedSessions);
  const missionFiles = deriveChanged(mission, workspace).slice(0, 3);
  const reviewTargets = [];
  reviewTargets.push({
    id: "review-preview",
    label: previewMode === "live" ? "Live surface" : "Fixture surface",
    title: previewMode === "live" ? "Live Builder review" : previewLabel(previewMode, snapshot?.previewMeta),
    detail: previewMode === "live" ? liveSyncSuspended ? "Live sync is paused while the surface is hidden." : lastPushReason ? `Latest backend push: ${lastPushReason}.` : "Live backend state is active for review." : "Fixture mode is active for repeatable review and screenshot work.",
    tone: previewMode === "live" ? liveSyncSuspended ? "warn" : "good" : "neutral",
    actionId: "open_builder",
    commentSeed: previewMode === "live" ? "Live UI review note for the current Builder surface:\nWhat feels wrong:\nWhat should change:\n" : "Fixture review note:\nThis scenario should read differently because \n"
  });
  if (mission) {
    reviewTargets.push({
      id: `review-mission-${mission?.mission_id || "current"}`,
      label: "Mission focus",
      title: mission?.title || mission?.objective || "Current mission",
      detail: `${deriveCurrentTask(mission)} \xB7 Next ${deriveNextCheckpoint(mission)}`,
      tone: missionNeedsAttention(mission) ? "warn" : missionStatusTone(mission?.state?.status),
      actionId: "focus_thread",
      commentSeed: `Mission UI review for ${mission?.title || "the current mission"}:
This decision point should look different because 
`
    });
  }
  if (builderBoard.activeConversations.length > 1) {
    reviewTargets.push({
      id: "review-conversations",
      label: "Conversation grid",
      title: `${builderBoard.activeConversations.length} active conversations`,
      detail: `${builderBoard.activeConversations.filter((item) => item.blocked).length} blocked \xB7 ${builderBoard.activeConversations.length - 1} secondary thread card(s) visible.`,
      tone: builderBoard.activeConversations.some((item) => item.blocked) ? "warn" : "good",
      actionId: "focus_conversations",
      commentSeed: "Conversation board review:\nWhich thread deserves more visual weight and why:\n"
    });
  }
  for (const [index, item] of bridgeSessions.slice(0, 2).entries()) {
    reviewTargets.push({
      id: item?.session_id || `review-bridge-${index}`,
      label: titleizeToken(item?.bridge_transport || "bridge"),
      title: item?.app_name || "Connected app",
      detail: asList(item?.context_preview).map((entry) => entry?.summary).find(Boolean) || item?.latest_task_result?.resultSummary || "Connected app review target is ready.",
      tone: item?.bridge_health === "healthy" ? "good" : "warn",
      actionId: "open_runtime",
      commentSeed: `Bridge review for ${item?.app_name || "this app"}:
This hand-off or preview block should change because 
`
    });
  }
  for (const [index, file] of missionFiles.entries()) {
    reviewTargets.push({
      id: `review-file-${index}-${file}`,
      label: "Changed file",
      title: file,
      detail: "Use this as a review anchor when pointing at what should change in the live UI flow.",
      tone: "neutral",
      actionId: "open_proof",
      commentSeed: `Review note for ${file}:
The visible UI behavior should change like this:
`
    });
  }
  return {
    headline: "Live UI review",
    summary: "Pick a visible block, annotate what feels wrong, and push the feedback back into the mission without leaving Builder.",
    statusLine: previewMode === "live" ? `${isRefreshing ? "Refreshing" : "Live"} \xB7 ${liveSyncSeconds === "off" ? "manual sync" : `${liveSyncSeconds}s sync`}` : `${previewLabel(previewMode, snapshot?.previewMeta)} \xB7 repeatable review`,
    targets: reviewTargets.slice(0, 6),
    compareHint: builderBoard.activeConversations.length > 0 ? "Use live review targets to steer the active mission, then jump back through nexuses if the direction changes." : "Use fixture review now, then launch the UI review loop once a real mission is active."
  };
}
function buildMissionControlModel({
  mission,
  workspace,
  setupHealth,
  snapshot,
  pendingQuestions,
  pendingApprovals,
  telegramReady,
  profileId,
  profileParams,
  inbox,
  previewMode = "live",
  uiMode = "agent",
  lastPushReason = "",
  isRefreshing = false,
  liveSyncSeconds = "off",
  liveSyncSuspended = false
}) {
  const queueItems = deriveQueueItems(mission, pendingQuestions, pendingApprovals);
  const primaryAction = derivePrimaryAction(mission, queueItems);
  const liveStatus = topBarLiveStatus(mission, pendingQuestions, pendingApprovals);
  const events = deriveEvents(mission, snapshot);
  const inboxPreview = asList(inbox)[0];
  const featureTruth = classifyFeatureTruth({ mission, snapshot, setupHealth, previewMode });
  const confidence = deriveConfidenceSurface({
    mission,
    snapshot,
    setupHealth,
    queueItems,
    pendingQuestions,
    pendingApprovals
  });
  const profileStudio = deriveProfileStudio(snapshot, workspace, profileId, profileParams);
  const serviceStudio = deriveServiceStudio(workspace, setupHealth);
  const skillStudio = deriveSkillStudio(snapshot, workspace);
  const workflowStudio = deriveWorkflowStudio(snapshot, profileId);
  const builderOps = deriveBuilderOps(workspace);
  const stateAudit = deriveStateAudit({ mission, setupHealth });
  const qualityRoadmap = deriveQualityRoadmap({
    confidence,
    mission,
    setupHealth,
    serviceStudio,
    skillStudio,
    workflowStudio,
    builderOps
  });
  const builderBoard = deriveBuilderBoard({ mission, workspace, snapshot, confidence, uiMode });
  const tutorialStudio = deriveTutorialStudio({
    mission,
    snapshot,
    setupHealth,
    profileId,
    workflowStudio
  });
  const recommendationStudio = deriveRecommendationStudio({
    mission,
    workspace,
    setupHealth,
    serviceStudio,
    skillStudio,
    workflowStudio,
    qualityRoadmap,
    builderBoard
  });
  const proofTone = asList(mission?.state?.verification_failures).length > 0 ? "bad" : asList(mission?.proof?.pending_approvals).length > 0 ? "warn" : mission?.state?.status === "completed" ? "good" : "neutral";
  const proofSections = [
    {
      title: "Files touched",
      items: deriveChanged(mission, workspace)
    },
    {
      title: "Checks and commands",
      items: deriveChecks(mission)
    },
    {
      title: "Artifacts",
      items: deriveArtifacts(mission, inboxPreview)
    }
  ];
  const contextGroups = [
    {
      title: "Guardrails",
      items: [
        {
          label: "Approval mode",
          value: titleizeToken(
            mission?.execution_policy?.approval_mode || profileParams?.approvalStrictness || "tiered"
          )
        },
        {
          label: "Run until",
          value: titleizeToken(
            mission?.missionLoop?.timeBudget?.runUntilBehavior || mission?.run_budget?.run_until_behavior || profileParams?.autoContinueBehavior || "pause_on_failure"
          ),
          note: resolveMissionPauseReason(mission) || "No active pause"
        },
        {
          label: "Setup blockers",
          value: `${asList(setupHealth?.blockerExplanations).length}`,
          note: asList(setupHealth?.blockerExplanations)[0] || "None"
        }
      ]
    },
    {
      title: "Runtime and scope",
      items: [
        {
          label: "Current lane",
          value: resolveCurrentRuntimeLane(mission)
        },
        {
          label: "Workspace root",
          value: workspace?.root_path || snapshot?.workspaceRoot || "Not selected"
        },
        {
          label: "Execution",
          value: mission?.execution_scope?.execution_root || "Not recorded",
          note: titleizeToken(mission?.execution_scope?.strategy || "direct")
        }
      ]
    },
    {
      title: "Context",
      items: [
        {
          label: "Profile",
          value: titleizeToken(profileId)
        },
        {
          label: "Known state",
          value: describeMissionKnownState(mission)
        },
        {
          label: "Escalation",
          value: telegramReady ? "Telegram ready" : "Not configured",
          note: inboxPreview?.previewMessage || ""
        }
      ]
    },
    {
      title: "Confidence",
      items: [
        {
          label: "1.0 progress",
          value: confidence.label,
          note: confidence.phase
        },
        {
          label: "Release status",
          value: confidence.releaseStatus,
          note: confidence.requiredGateSummary.label
        },
        {
          label: "Quality score",
          value: `${confidence.qualityScore}%`,
          note: confidence.nextActions[0] || "No blocker reported."
        }
      ]
    }
  ];
  const threadSections = deriveThreadSections({ mission, pendingQuestions, workspace });
  const emptyReadiness = uniq([
    ...asList(setupHealth?.blockerExplanations),
    asList(snapshot?.workspaces).length === 0 ? "Add at least one workspace" : "",
    previewMode !== "live" ? "Preview mode is active; actions are read-only." : ""
  ]);
  const activeAuditCount = stateAudit.filter((item) => item.state === "active").length;
  const requiredGateFailures = confidence.gates.filter(
    (item) => item.required && item.passed === false
  ).length;
  const builderReviewCount = featureTruth.notReady.length + activeAuditCount + asInt(serviceStudio.summary.needsAttentionCount) + asInt(skillStudio.summary.needsTestCount) + qualityRoadmap.nextCount + qualityRoadmap.blockedCount + requiredGateFailures;
  return {
    topBar: {
      liveStatus,
      environmentLabel: deriveEnvironmentLabel(setupHealth, mission, workspace),
      inboxCount: queueItems.filter((item) => item.tone === "warn" || item.tone === "bad").length + asList(inbox).length,
      primaryAction,
      confidence
    },
    shell: {
      isEmpty: !mission,
      missionLabel: mission ? mission.title || mission.objective : "No mission"
    },
    emptyState: {
      title: "Ready for a focused first mission",
      summary: emptyReadiness[0] || "Launch one real mission to replace scaffolding with a thread, proof, and review boundaries.",
      readiness: emptyReadiness.length > 0 ? emptyReadiness : ["Environment appears ready."],
      recommendedAction: primaryAction.label,
      confidenceLabel: confidence.label,
      confidencePhase: confidence.phase,
      qualityRoadmapHeadline: qualityRoadmap.headline,
      recommendedWorkflow: workflowStudio?.recommended?.label || "Long-Run Agent Session",
      launchEntryLabel: asList(snapshot?.workspaces).length > 0 ? "Launch mission" : "Add workspace"
    },
    thread: {
      title: mission ? mission.title || mission.objective : "Mission thread",
      objective: mission?.objective || "",
      summary: mission?.state?.last_plan_summary || mission?.proof?.summary || "The mission thread captures task, assumptions, operator needs, and proof deltas.",
      status: liveStatus,
      chips: mission ? [
        { label: runtimeLabel(mission?.runtime_id), tone: "neutral" },
        { label: titleizeToken(mission?.state?.status || "active"), tone: missionStatusTone(mission?.state?.status) },
        { label: `Elapsed ${deriveElapsed(mission)}`, tone: "neutral" },
        { label: `Remaining ${deriveRemaining(mission)}`, tone: "neutral" },
        {
          label: `${confidence.score}% confidence`,
          tone: confidence.tone
        }
      ] : [],
      sections: threadSections,
      events,
      proofItems: uniq([
        deriveVerificationSummary(mission),
        ...proofSections.flatMap((section) => section.items)
      ]).slice(0, 8),
      composerPlaceholder: "Write an operator note, scope clarification, or approval rationale for this mission thread."
    },
    drawers: {
      queue: {
        label: "Queue",
        urgent: queueItems.some((item) => item.tone === "warn" || item.tone === "bad"),
        count: queueItems.filter((item) => item.tone === "warn" || item.tone === "bad").length,
        items: queueItems,
        recommendation: {
          title: describeNextOperatorAction(mission, pendingQuestions),
          reason: queueItems[0]?.reason || ""
        }
      },
      proof: {
        label: "Proof",
        tone: proofTone,
        headline: deriveVerificationSummary(mission),
        diffSummary: deriveDiffSummary(workspace),
        sections: proofSections,
        itemsCount: proofSections.reduce((total, section) => total + section.items.length, 0)
      },
      context: {
        label: "Context",
        count: contextGroups.reduce((total, group) => total + group.items.length, 0),
        groups: contextGroups
      },
      builder: {
        label: "Builder review",
        reviewCount: builderReviewCount,
        confidence,
        liveSurface: {
          previewMode,
          liveSyncSeconds,
          liveSyncSuspended,
          lastPushReason,
          isRefreshing,
          note: previewMode === "live" ? liveSyncSuspended ? "Live sync paused while the window is hidden." : `Live backend${lastPushReason ? ` \xB7 last push ${lastPushReason}` : ""}` : "Fixture-backed review mode is active."
        },
        tutorialStudio,
        recommendationStudio,
        liveReviewStudio: deriveLiveReviewStudio({
          mission,
          workspace,
          snapshot,
          previewMode,
          liveSyncSeconds,
          liveSyncSuspended,
          lastPushReason,
          isRefreshing,
          builderBoard
        }),
        profileStudio,
        serviceStudio,
        skillStudio,
        workflowStudio,
        gitActions: builderOps.gitActions,
        validationActions: builderOps.validationActions,
        qualityRoadmap,
        featureTruth,
        stateAudit,
        events: events.slice(0, 10),
        board: builderBoard,
        mode: uiMode
      }
    }
  };
}

// t3code/apps/web/src/fluxio/FluxioShell.jsx
var import_jsx_runtime2 = require("react/jsx-runtime");
var STORAGE_KEYS = {
  uiMode: "fluxio.ui.mode",
  telegramChatId: "fluxio.telegram.chatId",
  previewMode: "fluxio.preview.mode",
  liveSyncSeconds: "fluxio.live_sync.seconds",
  codeExecutionEnabled: "fluxio.openai.code_execution.enabled",
  codeExecutionMemory: "fluxio.openai.code_execution.memory"
};
var FIXTURE_OPTIONS = [{ id: "live", name: "Live Backend" }, ...listFixtureOptions()];
var LIVE_SYNC_OPTIONS = [
  { value: "off", label: "Manual" },
  { value: "1", label: "1s" },
  { value: "5", label: "5s" },
  { value: "15", label: "15s" },
  { value: "30", label: "30s" }
];
var DEFAULT_OPENCLAW_GATEWAY_URL = "ws://127.0.0.1:8765";
var DEFAULT_WORKSPACE_FORM = {
  name: "",
  path: "",
  defaultRuntime: "openclaw",
  userProfile: "builder"
};
var DEFAULT_MISSION_FORM = {
  workspaceId: "",
  runtime: "openclaw",
  mode: "Autopilot",
  profile: "builder",
  budgetHours: 12,
  runUntil: "pause_on_failure",
  objective: "",
  successChecks: ""
};
var PREFERRED_HARNESS_OPTIONS = [
  { value: "fluxio_hybrid", label: "Fluxio Hybrid" },
  { value: "legacy_autonomous_engine", label: "Legacy Autonomous Engine" }
];
var ROUTING_STRATEGY_OPTIONS = [
  { value: "profile_default", label: "Profile Default" },
  { value: "planner_premium_executor_efficient", label: "Planner Premium / Executor Efficient" },
  { value: "uniform_quality", label: "Uniform Quality" },
  { value: "budget_first", label: "Budget First" }
];
var MINIMAX_AUTH_OPTIONS = [
  { value: "none", label: "Not Configured" },
  { value: "minimax-portal-oauth", label: "MiniMax Portal OAuth" },
  { value: "minimax-api", label: "MiniMax API Key" }
];
var OPENAI_CODEX_AUTH_OPTIONS = [
  { value: "none", label: "Not Configured" },
  { value: "chatgpt", label: "ChatGPT Portal" },
  { value: "api", label: "API Key" }
];
var COMMIT_STYLE_OPTIONS = [
  { value: "scoped", label: "Scoped" },
  { value: "concise", label: "Concise" },
  { value: "detailed", label: "Detailed" }
];
var EXECUTION_TARGET_OPTIONS = [
  { value: "profile_default", label: "Profile Default" },
  { value: "workspace_root", label: "Workspace Root" },
  { value: "isolated_worktree", label: "Isolated Worktree" }
];
var ROUTE_ROLE_OPTIONS = ["planner", "executor", "verifier"];
var MODEL_PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "openrouter", label: "OpenRouter" }
];
var MODEL_EFFORT_OPTIONS = [
  { value: "default", label: "Default" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" }
];
var CODE_EXECUTION_MEMORY_OPTIONS = [
  { value: "1g", label: "1 GB" },
  { value: "4g", label: "4 GB" },
  { value: "16g", label: "16 GB" },
  { value: "64g", label: "64 GB" }
];
var PROVIDER_SECRET_OPTIONS = [
  {
    id: "openai",
    label: "OpenAI / Codex",
    env: "OPENAI_API_KEY",
    note: "Used for GPT and Codex-family routes."
  },
  {
    id: "anthropic",
    label: "Anthropic",
    env: "ANTHROPIC_API_KEY",
    note: "Used when planner or verifier routes target Claude."
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    env: "OPENROUTER_API_KEY",
    note: "Used when a route is delegated through OpenRouter."
  }
];
var ROUTE_MODEL_OPTIONS = [
  "gpt-5.4",
  "gpt-5.4-mini",
  "codex",
  "claude-sonnet-4.5",
  "claude-opus-4.1"
];
var AGENT_BLOCKER_DRAWER_IDS = ["queue", "proof", "context"];
var AGENT_BUILDER_ONLY_DRAWERS = ["builder", "skills", "runtime", "profiles", "settings"];
var AGENT_BLOCKER_STATUSES = ["needs_approval", "blocked", "verification_failed"];
var AGENT_QUEUED_PAUSE_STATES = ["queued", "resume_available"];
function hasTauriBackend() {
  return Boolean(globalThis.window?.__TAURI__ || globalThis.window?.__TAURI_INTERNALS__);
}
async function callBackend(command, payload = void 0, options = {}) {
  try {
    return payload === void 0 ? await (0, import_core.invoke)(command) : await (0, import_core.invoke)(command, payload);
  } catch (error) {
    if (options.throwOnError) {
      throw error;
    }
    return null;
  }
}
function useToastQueue() {
  const [items, setItems] = (0, import_react.useState)([]);
  const push = (0, import_react.useCallback)((message, kind = "info") => {
    const item = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      kind,
      message
    };
    setItems((current) => [...current, item]);
    window.setTimeout(() => {
      setItems((current) => current.filter((entry) => entry.id !== item.id));
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
function timeValue2(value) {
  if (!value) {
    return Number.NaN;
  }
  const parsed = new Date(value);
  const ms = parsed.getTime();
  return Number.isNaN(ms) ? Number.NaN : ms;
}
function asList2(value) {
  return Array.isArray(value) ? value : [];
}
function isHeartbeatRuntimeKind(kind) {
  return String(kind || "").toLowerCase() === "session.heartbeat";
}
function isProcessRuntimeKind(kind) {
  return ["runtime.output", "runtime.stdout", "runtime.stderr"].includes(
    String(kind || "").toLowerCase()
  );
}
function isTraceRuntimeKind(kind) {
  const normalized = String(kind || "").toLowerCase();
  return isProcessRuntimeKind(normalized) || [
    "runtime.phase",
    "runtime.plan",
    "runtime.thinking",
    "runtime.reasoning",
    "runtime.route_contract"
  ].includes(normalized);
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
function ToastHost({ items }) {
  return /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { "aria-atomic": "true", "aria-live": "polite", className: "toast-host", children: items.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: `toast ${toneClass(item.kind === "error" ? "bad" : item.kind === "warn" ? "warn" : "neutral")}`, children: item.message }, item.id)) });
}
function NavItem({
  active = false,
  title,
  subtitle,
  context = "",
  stats = [],
  onClick,
  tone = "neutral",
  badge,
  icon = null
}) {
  return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
    "button",
    {
      className: `fluxio-nav-item ${active ? "active" : ""}`.trim(),
      onClick,
      type: "button",
      children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-nav-item-top", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-nav-item-title", children: [
            icon ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { "aria-hidden": "true", className: "nav-item-icon", children: icon }) : null,
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: title })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: toneClass(tone), children: badge || titleizeToken(tone) })
        ] }),
        subtitle ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: subtitle }) : null,
        context ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "fluxio-nav-context", children: context }) : null,
        stats.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "fluxio-nav-stats", children: stats.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: `fluxio-nav-stat ${toneClass(item.tone)}`, children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.value }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("em", { children: item.label })
        ] }, `${title}-${item.label}`)) }) : null
      ]
    }
  );
}
function TranscriptMessage({
  item,
  highlighted = false,
  pinned = false,
  showTrace = false,
  onPinNexus = () => {
  },
  onSteer = () => {
  },
  onMemory = () => {
  },
  onValidate = () => {
  }
}) {
  const role = item.role || "fluxio";
  const roleLabel = item.roleLabel || {
    fluxio: "Fluxio",
    operator: "Operator",
    runtime: "Runtime",
    bridge: "Bridge",
    queue: "Needs attention",
    system: "System"
  }[role] || "Fluxio";
  const roleIcon = item.roleIcon || {
    fluxio: "\u25CE",
    operator: "\u25C9",
    runtime: "\u25C7",
    bridge: "\u2301",
    queue: "!",
    system: "\xB7"
  }[role] || "\xB7";
  return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
    "article",
    {
      className: `agent-message role-${role} ${toneClass(item.tone || "neutral")} ${item.emphasis ? "emphasis" : ""} ${item.processMessage ? "process-message" : ""} ${highlighted ? "highlighted" : ""} ${pinned ? "pinned" : ""}`.trim(),
      id: item.id,
      children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "agent-message-top", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "agent-message-role", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { "aria-hidden": "true", className: "agent-message-avatar", children: roleIcon }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: roleLabel })
          ] }),
          item.meta ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.meta }) : null
        ] }),
        item.label ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "agent-message-label", children: item.label }) : null,
        item.title ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: item.title }) : null,
        item.detail ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.detail }) : null,
        item.technicalDetail ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { className: "agent-message-details", open: showTrace, children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: item.technicalSummary || "Technical detail" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.technicalDetail })
        ] }) : null,
        item.chips?.length ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "agent-message-chips", children: item.chips.map((chip) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: chip }, `${item.id}-${chip}`)) }) : null,
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "agent-message-actions", children: [
          item.role === "queue" || item.tone === "bad" || item.processMessage ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => onValidate(item), type: "button", children: "Validate" }) : null,
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => onSteer(item), type: "button", children: "Steer" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => onMemory(item), type: "button", children: "Memory" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => onPinNexus(item.id), type: "button", children: pinned ? "Unpin nexus" : "Pin nexus" })
        ] })
      ]
    }
  );
}
function TopbarShortcut({ active = false, label, onClick, tone = "neutral" }) {
  return /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
    "button",
    {
      className: `topbar-shortcut ${active ? "active" : ""} ${toneClass(tone)}`.trim(),
      onClick,
      type: "button",
      children: label
    }
  );
}
function MenuButton({ label, onClick }) {
  return /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("button", { className: "app-menu-button", onClick, type: "button", children: label });
}
function GlobalRailButton({ active = false, icon = null, label, onClick, subtle = false }) {
  return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
    "button",
    {
      className: `global-rail-button ${active ? "active" : ""} ${subtle ? "subtle" : ""}`.trim(),
      onClick,
      type: "button",
      children: [
        icon ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { "aria-hidden": "true", className: "global-rail-icon", children: icon }) : null,
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: label })
      ]
    }
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
    return mission.missionLoop?.continuityState === "resume_available" || ["queued", "blocked", "verification_failed", "needs_approval"].includes(
      mission.state?.status || ""
    );
  }
  return true;
}
function listLabel2(value) {
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
function saveableRouteOverrides(routeOverrides) {
  return asList2(routeOverrides).filter((item) => item?.model?.trim()).map((item) => ({
    role: item.role,
    provider: item.provider,
    model: item.model.trim(),
    ...item.effort && item.effort !== "default" ? { effort: item.effort } : {}
  }));
}
function updateRouteOverride(routeOverrides, role, patch) {
  return asList2(routeOverrides).map(
    (item) => item.role === role ? {
      ...item,
      ...patch
    } : item
  );
}
function profileFormFromWorkspace(workspace, fallbackProfile) {
  const overrides = Array.isArray(workspace?.route_overrides) ? workspace.route_overrides : [];
  const existingByRole = new Map(overrides.map((item) => [String(item.role || "").toLowerCase(), item]));
  return {
    userProfile: workspace?.user_profile || fallbackProfile || "builder",
    preferredHarness: workspace?.preferred_harness || "fluxio_hybrid",
    routingStrategy: workspace?.routing_strategy || "profile_default",
    autoOptimizeRouting: Boolean(workspace?.auto_optimize_routing),
    openaiCodexAuthMode: workspace?.openai_codex_auth_mode || "none",
    minimaxAuthMode: workspace?.minimax_auth_mode || "none",
    commitMessageStyle: workspace?.commit_message_style || "scoped",
    executionTargetPreference: workspace?.execution_target_preference || "profile_default",
    routeOverrides: ROUTE_ROLE_OPTIONS.map((role) => {
      const item = existingByRole.get(role) || {};
      return {
        role,
        provider: item.provider || "openai",
        model: item.model || "",
        effort: item.effort || "default"
      };
    })
  };
}
function createSessionEntry(entry) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    createdAt: (/* @__PURE__ */ new Date()).toISOString(),
    ...entry
  };
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
    row?.data?.request_id
  ];
  return detailSources.find((value) => value) || "";
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
    return {
      id: `mission-${row.mission_id}-${row.timestamp || payload.detectedAt}-${kind}-${row.message || "event"}`,
      kind,
      role: kind === "mission.follow_up" ? "operator" : kind === "mission.approval" ? "queue" : "system",
      runtimeId: row.metadata?.runtimeId || row.metadata?.runtime_id || "",
      roleLabel: kind === "mission.follow_up" ? "Operator" : kind === "mission.approval" ? "Needs attention" : "Fluxio",
      roleIcon: kind === "mission.follow_up" ? "\u25C9" : kind === "mission.approval" ? "!" : "\xB7",
      label: titleizeToken(kind),
      title: row.message || "Mission event",
      detail: deltaDetail(row),
      meta: timestampLabel(row.timestamp || payload.detectedAt),
      timestampRaw: row.timestamp || payload.detectedAt,
      tone: kind === "mission.approval" ? "warn" : /failed|error/i.test(`${kind} ${row.message || ""}`) ? "bad" : "neutral",
      chips: [
        row.metadata?.runtimeId ? runtimeLabel(row.metadata.runtimeId) : "",
        row.metadata?.queuedForRuntime ? "Queued for runtime" : ""
      ].filter(Boolean)
    };
  }
  if (source === "runtime_event") {
    const delegatedId = row.delegated_id || row.delegatedId || "";
    const delegatedIds = new Set(
      delegatedSessions.map((item) => item?.delegated_id).filter(Boolean)
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
    return {
      id: `runtime-${delegatedId || mission.mission_id}-${row.event_id || row.created_at || payload.detectedAt}-${kind}`,
      kind,
      role: kind === "operator.followup" ? "operator" : "runtime",
      runtimeId: row.runtime_id || mission.runtime_id,
      roleLabel: kind === "operator.followup" ? "Operator" : runtimeLabel(row.runtime_id || mission.runtime_id),
      roleIcon: kind === "operator.followup" ? "\u25C9" : row.runtime_id === "hermes" ? "\u2B22" : "\u25C7",
      label: phaseEntered ? "Phase entered" : routeSwitchReason ? "Route switch reason" : handoffEvent ? "Runtime handoff" : processMessage ? "Process message" : heartbeat ? "Runtime heartbeat" : titleizeToken(kind),
      title: row.message || "Runtime event",
      detail: (phaseEntered ? `${titleizeToken(row?.data?.phase || "execute")} phase via ${titleizeToken(
        row?.data?.role || "route"
      )}${row?.data?.provider ? ` \xB7 ${titleizeToken(row.data.provider)}` : ""}${row?.data?.model ? ` \xB7 ${row.data.model}` : ""}` : routeSwitchReason ? detail || row.message || "Route switch reason emitted by runtime supervision." : handoffEvent ? detail || row?.data?.reason || "Runtime handoff emitted by supervision." : routeSwitch ? `${titleizeToken(row?.data?.phase || "execute")} phase \xB7 ${titleizeToken(
        row?.data?.role || "route"
      )} route` : detail) || (processMessage ? `${runtimeLabel(row.runtime_id || mission.runtime_id)} emitted process output.` : heartbeat ? "Heartbeat telemetry from the delegated runtime lane." : ""),
      meta: timestampLabel(row.created_at || payload.detectedAt),
      timestampRaw: row.created_at || payload.detectedAt,
      tone: row.status === "failed" ? "bad" : /approval|waiting/i.test(`${kind} ${row.status || ""}`) ? "warn" : "neutral",
      technicalDetail: processMessage && detail && detail !== row.message ? detail : row?.metadata?.trace || row?.data?.trace || "",
      technicalSummary: processMessage ? "Thinking trace" : "",
      processMessage,
      heartbeat,
      emphasis: processMessage || phaseEntered || routeSwitchReason || handoffEvent || row.status === "failed" || /approval|blocked|error/i.test(`${kind} ${row.message || ""}`),
      chips: [
        row.runtime_id ? runtimeLabel(row.runtime_id) : "",
        routeSwitch && row?.data?.phase ? titleizeToken(row.data.phase) : "",
        routeSwitch && row?.data?.role ? titleizeToken(row.data.role) : "",
        phaseEntered && row?.data?.provider ? titleizeToken(row.data.provider) : "",
        phaseEntered && row?.data?.model ? row.data.model : "",
        routeSwitchReason && row?.data?.reason ? row.data.reason : "",
        row.status ? titleizeToken(row.status) : ""
      ].filter(Boolean)
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
  return "setup";
}
function FluxioShellApp({ reportUiAction = () => {
} }) {
  const searchParams = (0, import_react.useMemo)(() => new URLSearchParams(window.location.search), []);
  const storedUiMode = searchParams.get("mode") || localStorage.getItem(STORAGE_KEYS.uiMode) || "agent";
  const storedChatId = localStorage.getItem(STORAGE_KEYS.telegramChatId) || "";
  const storedPreviewMode = searchParams.get("fixture") || localStorage.getItem(STORAGE_KEYS.previewMode) || "live";
  const storedLiveSyncSeconds = localStorage.getItem(STORAGE_KEYS.liveSyncSeconds) || "off";
  const storedCodeExecutionEnabled = localStorage.getItem(STORAGE_KEYS.codeExecutionEnabled) === "true";
  const storedCodeExecutionMemory = localStorage.getItem(STORAGE_KEYS.codeExecutionMemory) || "4g";
  const [uiMode, setUiMode] = (0, import_react.useState)(
    ["agent", "builder"].includes(storedUiMode) ? storedUiMode : "agent"
  );
  const [previewMode, setPreviewMode] = (0, import_react.useState)(
    FIXTURE_OPTIONS.some((option) => option.id === storedPreviewMode) ? storedPreviewMode : "live"
  );
  const [liveSyncSeconds, setLiveSyncSeconds] = (0, import_react.useState)(
    LIVE_SYNC_OPTIONS.some((option) => option.value === storedLiveSyncSeconds) ? storedLiveSyncSeconds : "off"
  );
  const [selectedWorkspaceId, setSelectedWorkspaceId] = (0, import_react.useState)(null);
  const [selectedMissionId, setSelectedMissionId] = (0, import_react.useState)(null);
  const [showWorkspaceDialog, setShowWorkspaceDialog] = (0, import_react.useState)(false);
  const [showMissionDialog, setShowMissionDialog] = (0, import_react.useState)(false);
  const [showEscalationDialog, setShowEscalationDialog] = (0, import_react.useState)(false);
  const [workspaceForm, setWorkspaceForm] = (0, import_react.useState)(DEFAULT_WORKSPACE_FORM);
  const [missionForm, setMissionForm] = (0, import_react.useState)(DEFAULT_MISSION_FORM);
  const [workspaceProfileForm, setWorkspaceProfileForm] = (0, import_react.useState)(
    profileFormFromWorkspace(null, "builder")
  );
  const [skillStudioFilter, setSkillStudioFilter] = (0, import_react.useState)("all");
  const [skillStudioQuery, setSkillStudioQuery] = (0, import_react.useState)("");
  const [telegramChatId, setTelegramChatId] = (0, import_react.useState)(storedChatId);
  const [telegramBotToken, setTelegramBotToken] = (0, import_react.useState)("");
  const [openClawGatewayUrl, setOpenClawGatewayUrl] = (0, import_react.useState)(DEFAULT_OPENCLAW_GATEWAY_URL);
  const [openClawGatewayToken, setOpenClawGatewayToken] = (0, import_react.useState)("");
  const [providerSecretDrafts, setProviderSecretDrafts] = (0, import_react.useState)(
    Object.fromEntries(PROVIDER_SECRET_OPTIONS.map((item) => [item.id, ""]))
  );
  const [codeExecutionEnabled, setCodeExecutionEnabled] = (0, import_react.useState)(storedCodeExecutionEnabled);
  const [codeExecutionMemory, setCodeExecutionMemory] = (0, import_react.useState)(
    CODE_EXECUTION_MEMORY_OPTIONS.some((option) => option.value === storedCodeExecutionMemory) ? storedCodeExecutionMemory : "4g"
  );
  const [lastPushReason, setLastPushReason] = (0, import_react.useState)("");
  const [liveSyncSuspended, setLiveSyncSuspended] = (0, import_react.useState)(false);
  const [isRefreshing, setIsRefreshing] = (0, import_react.useState)(false);
  const [activeDrawer, setActiveDrawer] = (0, import_react.useState)(null);
  const [operatorDraft, setOperatorDraft] = (0, import_react.useState)("");
  const [operatorNotes, setOperatorNotes] = (0, import_react.useState)([]);
  const [liveControlEvents, setLiveControlEvents] = (0, import_react.useState)([]);
  const [agentRouteRole, setAgentRouteRole] = (0, import_react.useState)("executor");
  const [agentRuntimeFocus, setAgentRuntimeFocus] = (0, import_react.useState)("all");
  const [showThinkingTrace, setShowThinkingTrace] = (0, import_react.useState)(true);
  const [pinnedNexusIds, setPinnedNexusIds] = (0, import_react.useState)([]);
  const [highlightedTurnId, setHighlightedTurnId] = (0, import_react.useState)("");
  const [selectedReviewTargetId, setSelectedReviewTargetId] = (0, import_react.useState)("");
  const [data, setData] = (0, import_react.useState)({
    snapshot: null,
    onboarding: null,
    pendingApprovals: [],
    pendingQuestions: [],
    telegramReady: false,
    previewMeta: null,
    openClawStatus: null,
    openClawHasToken: false,
    openClawMessages: [],
    providerSecretPresence: {}
  });
  const mountedRef = (0, import_react.useRef)(true);
  const currentMissionRef = (0, import_react.useRef)(null);
  const currentDelegatedSessionsRef = (0, import_react.useRef)([]);
  const refreshPromiseRef = (0, import_react.useRef)(null);
  const queuedRefreshReasonRef = (0, import_react.useRef)("");
  const authPromptedRef = (0, import_react.useRef)(false);
  const { items: toasts, push: pushToast } = useToastQueue();
  const markAction = (0, import_react.useCallback)(
    (action) => {
      reportUiAction(action);
    },
    [reportUiAction]
  );
  (0, import_react.useEffect)(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);
  (0, import_react.useEffect)(() => {
    localStorage.setItem(STORAGE_KEYS.uiMode, uiMode);
  }, [uiMode]);
  (0, import_react.useEffect)(() => {
    localStorage.setItem(STORAGE_KEYS.previewMode, previewMode);
  }, [previewMode]);
  (0, import_react.useEffect)(() => {
    localStorage.setItem(STORAGE_KEYS.liveSyncSeconds, liveSyncSeconds);
  }, [liveSyncSeconds]);
  (0, import_react.useEffect)(() => {
    localStorage.setItem(STORAGE_KEYS.telegramChatId, telegramChatId);
  }, [telegramChatId]);
  (0, import_react.useEffect)(() => {
    localStorage.setItem(
      STORAGE_KEYS.codeExecutionEnabled,
      codeExecutionEnabled ? "true" : "false"
    );
  }, [codeExecutionEnabled]);
  (0, import_react.useEffect)(() => {
    localStorage.setItem(STORAGE_KEYS.codeExecutionMemory, codeExecutionMemory);
  }, [codeExecutionMemory]);
  (0, import_react.useEffect)(() => {
    setLiveControlEvents([]);
  }, [previewMode, selectedMissionId]);
  const performRefresh = (0, import_react.useCallback)(
    async (reason = "manual") => {
      markAction(`refresh:${reason}`);
      setIsRefreshing(true);
      try {
        if (previewMode !== "live") {
          const fixturePayload = buildFixtureSnapshot(previewMode);
          if (!fixturePayload) {
            setPreviewMode("live");
            return;
          }
          setData((current) => ({
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
            providerSecretPresence: {}
          }));
          return;
        }
        if (!hasTauriBackend()) {
          const fallbackPayload = buildFixtureSnapshot("live_review");
          setData((current) => ({
            ...current,
            snapshot: fallbackPayload.snapshot,
            onboarding: fallbackPayload.onboarding,
            pendingApprovals: fallbackPayload.pendingApprovals,
            pendingQuestions: fallbackPayload.pendingQuestions,
            telegramReady: fallbackPayload.telegramReady,
            previewMeta: {
              id: "fallback",
              name: "Local Fallback",
              description: "Tauri backend is unavailable, so Fluxio is showing a local supervision fixture."
            },
            openClawStatus: null,
            openClawHasToken: false,
            openClawMessages: []
          }));
          return;
        }
        const [
          snapshot2,
          pendingApprovals,
          pendingQuestions,
          telegramReady,
          openClawStatus2,
          openClawHasToken,
          providerSecretPresencePrimary
        ] = await Promise.all([
          callBackend(
            "get_control_room_snapshot_command",
            { payload: { root: null } },
            { throwOnError: true }
          ),
          callBackend("list_pending_approvals"),
          callBackend("list_pending_questions"),
          callBackend("has_telegram_bot_token_command"),
          callBackend("get_openclaw_status"),
          callBackend("has_openclaw_gateway_token"),
          callBackend("get_provider_secret_presence_command", {
            providerIds: PROVIDER_SECRET_OPTIONS.map((item) => item.id)
          })
        ]);
        if (!mountedRef.current) {
          return;
        }
        const providerSecretPresence2 = (snapshot2?.providerSecretPresence && typeof snapshot2.providerSecretPresence === "object" ? snapshot2.providerSecretPresence : null) || providerSecretPresencePrimary || await callBackend("get_provider_secret_presence_command", {
          provider_ids: PROVIDER_SECRET_OPTIONS.map((item) => item.id)
        }) || {};
        setData((current) => ({
          ...current,
          snapshot: snapshot2,
          onboarding: snapshot2?.onboarding || current.onboarding || null,
          pendingApprovals: Array.isArray(pendingApprovals) ? pendingApprovals : [],
          pendingQuestions: Array.isArray(pendingQuestions) ? pendingQuestions : [],
          telegramReady: Boolean(telegramReady),
          previewMeta: null,
          openClawStatus: openClawStatus2 || null,
          openClawHasToken: Boolean(openClawHasToken),
          providerSecretPresence: providerSecretPresence2 && typeof providerSecretPresence2 === "object" ? providerSecretPresence2 : {}
        }));
        if (reason !== "initialize") {
          setLastPushReason(reason);
        }
      } catch (error) {
        pushToast(`Refresh failed: ${error}`, "error");
      } finally {
        if (mountedRef.current) {
          setIsRefreshing(false);
        }
      }
    },
    [markAction, previewMode, pushToast]
  );
  const refreshAll = (0, import_react.useCallback)(
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
    [performRefresh]
  );
  (0, import_react.useEffect)(() => {
    void refreshAll("initialize");
  }, [refreshAll]);
  (0, import_react.useEffect)(() => {
    const workspaces2 = data.snapshot?.workspaces || [];
    setSelectedWorkspaceId(
      (current) => workspaces2.some((item) => item.workspace_id === current) ? current : workspaces2[0]?.workspace_id || null
    );
  }, [data.snapshot]);
  (0, import_react.useEffect)(() => {
    const missions2 = data.snapshot?.missions || [];
    setSelectedMissionId(
      (current) => missions2.some((item) => item.mission_id === current) ? current : missions2[missions2.length - 1]?.mission_id || null
    );
  }, [data.snapshot]);
  (0, import_react.useEffect)(() => {
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
  (0, import_react.useEffect)(() => {
    if (previewMode !== "live" || liveSyncSeconds === "off" || liveSyncSuspended) {
      return void 0;
    }
    const interval = window.setInterval(() => {
      void refreshAll("live-sync");
    }, Number(liveSyncSeconds) * 1e3);
    return () => {
      window.clearInterval(interval);
    };
  }, [liveSyncSeconds, liveSyncSuspended, previewMode, refreshAll]);
  (0, import_react.useEffect)(() => {
    if (previewMode !== "live" || !hasTauriBackend()) {
      return void 0;
    }
    let unlistenChanged = null;
    let unlistenDelta = null;
    let unlistenOpenClawStatus = null;
    let unlistenOpenClawMessage = null;
    void (0, import_event.listen)("control-room://changed", (event) => {
      const reason = event?.payload?.reason || "backend-event";
      setLastPushReason(reason);
      void refreshAll(reason);
    }).then((unlisten) => {
      unlistenChanged = unlisten;
    }).catch(() => void 0);
    void (0, import_event.listen)("control-room://delta", (event) => {
      const reason = event?.payload?.source || "backend-delta";
      setLastPushReason(reason);
      const liveItem = controlRoomDeltaToLiveItem(
        event?.payload,
        currentMissionRef.current,
        currentDelegatedSessionsRef.current
      );
      if (liveItem) {
        setLiveControlEvents(
          (current) => [liveItem, ...current.filter((entry) => entry.id !== liveItem.id)].slice(0, 24)
        );
      }
    }).then((unlisten) => {
      unlistenDelta = unlisten;
    }).catch(() => void 0);
    void (0, import_event.listen)("openclaw://status", (event) => {
      setData((current) => ({
        ...current,
        openClawStatus: event?.payload || current.openClawStatus
      }));
    }).then((unlisten) => {
      unlistenOpenClawStatus = unlisten;
    }).catch(() => void 0);
    void (0, import_event.listen)("openclaw://message", (event) => {
      const content = event?.payload?.content;
      if (!content) {
        return;
      }
      setData((current) => ({
        ...current,
        openClawMessages: [
          ...current.openClawMessages,
          createSessionEntry({
            title: "OpenClaw message",
            detail: String(content),
            meta: "Gateway message",
            tone: "neutral"
          })
        ].slice(-16)
      }));
    }).then((unlisten) => {
      unlistenOpenClawMessage = unlisten;
    }).catch(() => void 0);
    return () => {
      if (typeof unlistenChanged === "function") {
        unlistenChanged();
      }
      if (typeof unlistenDelta === "function") {
        unlistenDelta();
      }
      if (typeof unlistenOpenClawStatus === "function") {
        unlistenOpenClawStatus();
      }
      if (typeof unlistenOpenClawMessage === "function") {
        unlistenOpenClawMessage();
      }
    };
  }, [previewMode, refreshAll]);
  const snapshot = data.snapshot || {};
  const onboarding = data.onboarding || snapshot.onboarding || {};
  const setupHealth = snapshot.setupHealth || onboarding.setupHealth || {};
  const workspaces = snapshot.workspaces || [];
  const missions = snapshot.missions || [];
  const inboxItems = snapshot.inbox || [];
  const workspace = (0, import_react.useMemo)(
    () => selectedWorkspace(snapshot, selectedWorkspaceId),
    [selectedWorkspaceId, snapshot]
  );
  const mission = (0, import_react.useMemo)(
    () => selectedMission(snapshot, selectedMissionId),
    [selectedMissionId, snapshot]
  );
  const workspaceMissions = (0, import_react.useMemo)(
    () => missions.filter(
      (item) => selectedWorkspaceId ? item.workspace_id === selectedWorkspaceId : true
    ),
    [missions, selectedWorkspaceId]
  );
  const profileId = activeProfileId(snapshot, onboarding, workspace, mission);
  const profileParams = currentProfileParameters(snapshot, profileId, workspace);
  const viewModel = (0, import_react.useMemo)(
    () => buildMissionControlModel({
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
      liveSyncSuspended
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
      workspace
    ]
  );
  const missionOptions = workspaceMissions.length > 0 ? workspaceMissions : missions;
  const quickSetupActions = (0, import_react.useMemo)(
    () => [...setupHealth.repairActions || [], ...setupHealth.globalActions || []].slice(0, 3),
    [setupHealth.globalActions, setupHealth.repairActions]
  );
  const missionStatus = mission?.state?.status || "";
  const agentBlockedState = (0, import_react.useMemo)(() => {
    const approvalCount = asList2(mission?.proof?.pending_approvals).length + asList2(data.pendingApprovals).length;
    const questionCount = asList2(data.pendingQuestions).length;
    const verificationFailureCount = asList2(mission?.state?.verification_failures).length;
    const continuityState = mission?.missionLoop?.continuityState || mission?.missionLoop?.timeBudget?.status || mission?.missionLoop?.time_budget?.status || "";
    const hasApprovalBoundary = approvalCount > 0;
    const hasQuestionBoundary = questionCount > 0;
    const hasVerificationFailure = verificationFailureCount > 0 || missionStatus === "verification_failed";
    const hasBlockedMissionState = AGENT_BLOCKER_STATUSES.includes(missionStatus);
    const hasQueuedPauseState = AGENT_QUEUED_PAUSE_STATES.includes(missionStatus) || AGENT_QUEUED_PAUSE_STATES.includes(continuityState);
    const isBlocked = Boolean(
      mission && (hasApprovalBoundary || hasQuestionBoundary || hasVerificationFailure || hasBlockedMissionState || hasQueuedPauseState)
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
      defaultDrawer: hasApprovalBoundary || hasQuestionBoundary ? "queue" : hasVerificationFailure ? "proof" : "context"
    };
  }, [data.pendingApprovals, data.pendingQuestions, mission, missionStatus]);
  const agentVisibleDrawers = (0, import_react.useMemo)(
    () => AGENT_BLOCKER_DRAWER_IDS,
    []
  );
  const showPersistentDrawer = Boolean(activeDrawer) && (uiMode === "builder" || agentBlockedState.isBlocked);
  const focusedRuntimeServices = (0, import_react.useMemo)(() => {
    const services = viewModel.drawers.builder.serviceStudio.services || [];
    const byNeedle = (needle) => services.filter((item) => needle.test(`${item.serviceId} ${item.label} ${item.details}`));
    return {
      hermes: byNeedle(/hermes/i),
      openClaw: byNeedle(/openclaw|open claw|opencode/i),
      bridges: byNeedle(/telegram|bridge|message|imessage|sms/i)
    };
  }, [viewModel.drawers.builder.serviceStudio.services]);
  (0, import_react.useEffect)(() => {
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
    workspace?.workspace_id
  ]);
  (0, import_react.useEffect)(() => {
    setMissionForm((current) => ({
      ...current,
      workspaceId: workspace?.workspace_id || current.workspaceId || "",
      runtime: mission?.runtime_id || workspace?.default_runtime || current.runtime,
      profile: mission?.selected_profile || workspace?.user_profile || profileId
    }));
  }, [
    mission?.runtime_id,
    mission?.selected_profile,
    profileId,
    workspace?.default_runtime,
    workspace?.user_profile,
    workspace?.workspace_id
  ]);
  (0, import_react.useEffect)(() => {
    if (mission?.mission_id) {
      setAgentRuntimeFocus("all");
      return;
    }
    setAgentRuntimeFocus(missionForm.runtime || "openclaw");
  }, [mission?.mission_id, missionForm.runtime]);
  (0, import_react.useEffect)(() => {
    const gatewayUrl = data.openClawStatus?.gatewayUrl;
    if (gatewayUrl) {
      setOpenClawGatewayUrl(gatewayUrl);
    }
  }, [data.openClawStatus?.gatewayUrl]);
  (0, import_react.useEffect)(() => {
    if (!mission && uiMode === "agent") {
      setActiveDrawer(null);
    }
  }, [mission, uiMode]);
  (0, import_react.useEffect)(() => {
    if (uiMode === "agent" && AGENT_BUILDER_ONLY_DRAWERS.includes(activeDrawer)) {
      setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
    }
  }, [activeDrawer, agentBlockedState.defaultDrawer, agentBlockedState.isBlocked, uiMode]);
  (0, import_react.useEffect)(() => {
    if (uiMode === "agent" && agentBlockedState.isBlocked) {
      setActiveDrawer(agentBlockedState.defaultDrawer);
    }
  }, [agentBlockedState.defaultDrawer, agentBlockedState.isBlocked, uiMode]);
  const runMissionAction = (0, import_react.useCallback)(
    async (action, successMessage) => {
      markAction(`mission:${action}`);
      if (!mission) {
        return;
      }
      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast("Preview mode is read-only for mission actions.", "warn");
        return;
      }
      const backendAction = action === "pause" ? "stop" : action;
      try {
        await callBackend(
          "apply_control_room_mission_action_command",
          { payload: { missionId: mission.mission_id, action: backendAction, root: null } },
          { throwOnError: true }
        );
        pushToast(successMessage, "info");
        await refreshAll(`mission-${backendAction}`);
      } catch (error) {
        pushToast(`Mission action failed: ${error}`, "error");
      }
    },
    [markAction, mission, previewMode, pushToast, refreshAll]
  );
  const runWorkspaceAction = (0, import_react.useCallback)(
    async (surface, actionId, approved = false) => {
      markAction(`workspace:${surface}:${actionId}`);
      if (previewMode !== "live" || !hasTauriBackend()) {
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
              approved
            }
          },
          { throwOnError: true }
        );
        pushToast("Workspace action started.", "info");
        await refreshAll(`workspace-${actionId}`);
      } catch (error) {
        pushToast(`Workspace action failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, workspace?.workspace_id]
  );
  const runWorkspaceActionSpec = (0, import_react.useCallback)(
    async (action) => {
      if (!action?.actionId) {
        pushToast("Action is missing an action id.", "warn");
        return;
      }
      const surface = inferSurfaceFromAction(action);
      const requiresApproval = Boolean(action.requiresApproval);
      let approved = false;
      if (requiresApproval) {
        const confirmed = window.confirm(
          `Run "${action.label || action.actionId}" now?

This action is approval-gated and may mutate workspace state.`
        );
        if (!confirmed) {
          return;
        }
        approved = true;
      }
      await runWorkspaceAction(surface, action.actionId, approved);
    },
    [pushToast, runWorkspaceAction]
  );
  const saveWorkspacePolicy = (0, import_react.useCallback)(async () => {
    markAction("submit:workspace-policy");
    if (!workspace) {
      pushToast("Select a workspace first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot save workspace policy.", "warn");
      return;
    }
    try {
      await callBackend(
        "save_workspace_profile_command",
        {
          payload: {
            root: null,
            workspaceId: workspace.workspace_id,
            name: workspace.name,
            path: workspace.root_path,
            defaultRuntime: workspace.default_runtime,
            userProfile: workspaceProfileForm.userProfile,
            preferredHarness: workspaceProfileForm.preferredHarness,
            routingStrategy: workspaceProfileForm.routingStrategy,
            routeOverrides: saveableRouteOverrides(workspaceProfileForm.routeOverrides),
            autoOptimizeRouting: Boolean(workspaceProfileForm.autoOptimizeRouting),
            openaiCodexAuthMode: workspaceProfileForm.openaiCodexAuthMode,
            minimaxAuthMode: workspaceProfileForm.minimaxAuthMode,
            commitMessageStyle: workspaceProfileForm.commitMessageStyle,
            executionTargetPreference: workspaceProfileForm.executionTargetPreference
          }
        },
        { throwOnError: true }
      );
      pushToast("Workspace policy saved.", "info");
      await refreshAll("workspace-policy-save");
    } catch (error) {
      pushToast(`Workspace policy save failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll, workspace, workspaceProfileForm]);
  const applyPreferredHarness = (0, import_react.useCallback)(
    async (nextHarness) => {
      if (!nextHarness) {
        return;
      }
      markAction(`workspace:harness:${nextHarness}`);
      setWorkspaceProfileForm((current) => ({ ...current, preferredHarness: nextHarness }));
      if (!workspace) {
        pushToast("Select a workspace first.", "warn");
        return;
      }
      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast(`Harness preference staged as ${titleizeToken(nextHarness)} in preview mode.`, "info");
        return;
      }
      try {
        await callBackend(
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
              openaiCodexAuthMode: workspaceProfileForm.openaiCodexAuthMode,
              minimaxAuthMode: workspaceProfileForm.minimaxAuthMode,
              commitMessageStyle: workspaceProfileForm.commitMessageStyle,
              executionTargetPreference: workspaceProfileForm.executionTargetPreference
            }
          },
          { throwOnError: true }
        );
        pushToast(`Harness switched to ${titleizeToken(nextHarness)}.`, "info");
        await refreshAll(`workspace-harness-${nextHarness}`);
      } catch (error) {
        pushToast(`Harness switch failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, workspace, workspaceProfileForm]
  );
  const handleAgentRouteFieldChange = (0, import_react.useCallback)((field, value) => {
    setWorkspaceProfileForm((current) => ({
      ...current,
      routeOverrides: updateRouteOverride(current.routeOverrides, agentRouteRole, {
        [field]: value
      })
    }));
  }, [agentRouteRole]);
  const handleAgentRouteSave = (0, import_react.useCallback)(async () => {
    markAction(`agent:route-save:${agentRouteRole}`);
    if (!workspace) {
      pushToast("Select a workspace before saving route controls.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Route controls are staged in preview mode.", "info");
      return;
    }
    await saveWorkspacePolicy();
  }, [agentRouteRole, markAction, previewMode, pushToast, saveWorkspacePolicy, workspace]);
  const focusTranscriptTurn = (0, import_react.useCallback)((turnId) => {
    if (!turnId) {
      return;
    }
    setHighlightedTurnId(turnId);
    window.requestAnimationFrame(() => {
      document.getElementById(turnId)?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }, []);
  const togglePinnedNexus = (0, import_react.useCallback)((turnId) => {
    if (!turnId) {
      return;
    }
    setPinnedNexusIds(
      (current) => current.includes(turnId) ? current.filter((item) => item !== turnId) : [...current, turnId]
    );
  }, []);
  const handleAgentSteerFromTurn = (0, import_react.useCallback)((item) => {
    const prefix = item?.meta ? `From ${item.meta}` : "From this step";
    setHighlightedTurnId(item?.id || "");
    setOperatorDraft(
      `${prefix}: ${item?.title || "revisit this decision"}.
Do this differently: `
    );
    document.getElementById("thread-note")?.focus();
  }, []);
  const handleAgentMemoryFromTurn = (0, import_react.useCallback)((item) => {
    setHighlightedTurnId(item?.id || "");
    setOperatorDraft(
      `Memory correction for ${item?.title || "this step"}:
This was not okay because 
Next time do this instead: `
    );
    document.getElementById("thread-note")?.focus();
  }, []);
  const handleAgentValidateTurn = (0, import_react.useCallback)((item) => {
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
  const openMissionDialog = (0, import_react.useCallback)(() => {
    markAction("open:mission-dialog");
    setMissionForm((current) => ({
      ...current,
      workspaceId: workspace?.workspace_id || current.workspaceId || "",
      runtime: mission?.runtime_id || workspace?.default_runtime || current.runtime,
      profile: mission?.selected_profile || workspace?.user_profile || profileId,
      objective: !mission && operatorDraft.trim() && !current.objective.trim() ? operatorDraft.trim() : current.objective
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
    workspace?.workspace_id
  ]);
  const handleQualityRoadmapAction = (0, import_react.useCallback)(
    async (item) => {
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
        const serviceAction = viewModel.drawers.builder.serviceStudio.services.flatMap((service) => service.actions).find((action) => action);
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
    [markAction, openMissionDialog, pushToast, runWorkspaceActionSpec, viewModel]
  );
  const handleBuilderFeatureAction = (0, import_react.useCallback)(
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
              block: "start"
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
        case "open_builder":
          setUiMode("builder");
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
          const nextMissionId = payload?.missionId || builderPrimaryConversation?.missionId || mission?.mission_id;
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
      workspaces.length
    ]
  );
  const handleBuilderReviewTargetSeed = (0, import_react.useCallback)(
    (target) => {
      if (!target) {
        return;
      }
      setSelectedReviewTargetId(target.id || "");
      setOperatorDraft(target.commentSeed || `${target.title || "Review target"}:
`);
      window.requestAnimationFrame(() => {
        document.getElementById("builder-thread-note")?.focus();
      });
    },
    []
  );
  const handleWorkspaceSubmit = (0, import_react.useCallback)(
    async (event) => {
      event.preventDefault();
      markAction("submit:workspace");
      if (!workspaceForm.name.trim() || !workspaceForm.path.trim()) {
        pushToast("Workspace name and path are required.", "warn");
        return;
      }
      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast("Preview mode cannot save workspaces.", "warn");
        setShowWorkspaceDialog(false);
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
              userProfile: workspaceForm.userProfile
            }
          },
          { throwOnError: true }
        );
        pushToast("Workspace saved.", "info");
        setShowWorkspaceDialog(false);
        setWorkspaceForm(DEFAULT_WORKSPACE_FORM);
        await refreshAll("workspace-save");
      } catch (error) {
        pushToast(`Workspace save failed: ${error}`, "error");
      }
    },
    [markAction, previewMode, pushToast, refreshAll, workspaceForm]
  );
  const handleMissionSubmit = (0, import_react.useCallback)(
    async (event) => {
      event.preventDefault();
      markAction("submit:mission");
      if (!missionForm.workspaceId || !missionForm.objective.trim()) {
        pushToast("Choose a workspace and enter a mission objective.", "warn");
        return;
      }
      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast("Preview mode cannot launch missions.", "warn");
        setShowMissionDialog(false);
        return;
      }
      try {
        await callBackend(
          "start_control_room_mission_command",
          {
            payload: {
              root: null,
              workspaceId: missionForm.workspaceId,
              runtime: missionForm.runtime,
              objective: missionForm.objective.trim(),
              successChecks: missionForm.successChecks.split("\n").map((line) => line.trim()).filter(Boolean),
              mode: missionForm.mode,
              budgetHours: Number(missionForm.budgetHours || 12),
              runUntil: missionForm.runUntil,
              profile: missionForm.profile,
              escalationDestination: telegramChatId.trim() || null,
              codeExecution: codeExecutionEnabled,
              codeExecutionMemory,
              codeExecutionRequired: false
            }
          },
          { throwOnError: true }
        );
        pushToast("Mission launched.", "info");
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
      markAction,
      missionForm,
      previewMode,
      pushToast,
      refreshAll,
      telegramChatId
    ]
  );
  const handleSaveTelegram = (0, import_react.useCallback)(
    async (event) => {
      event.preventDefault();
      markAction("submit:telegram");
      if (previewMode !== "live" || !hasTauriBackend()) {
        pushToast("Preview mode cannot change escalation settings.", "warn");
        setShowEscalationDialog(false);
        return;
      }
      try {
        if (telegramBotToken.trim()) {
          await callBackend(
            "save_telegram_bot_token_command",
            { token: telegramBotToken.trim() },
            { throwOnError: true }
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
    [markAction, previewMode, pushToast, refreshAll, telegramBotToken]
  );
  const handleClearTelegram = (0, import_react.useCallback)(async () => {
    markAction("clear:telegram");
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot clear escalation settings.", "warn");
      return;
    }
    try {
      await callBackend("clear_telegram_bot_token_command", void 0, { throwOnError: true });
      setTelegramBotToken("");
      pushToast("Telegram token cleared.", "info");
      await refreshAll("telegram-clear");
    } catch (error) {
      pushToast(`Telegram clear failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);
  const handleSendTestPing = (0, import_react.useCallback)(async () => {
    markAction("send:telegram-test");
    if (!telegramChatId.trim()) {
      pushToast("Enter a Telegram chat ID first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot send escalation pings.", "warn");
      return;
    }
    try {
      await callBackend(
        "send_telegram_message_command",
        {
          payload: {
            chatId: telegramChatId.trim(),
            text: "Fluxio supervision test ping: approvals and mission escalations are reachable."
          }
        },
        { throwOnError: true }
      );
      pushToast("Telegram test ping sent.", "info");
    } catch (error) {
      pushToast(`Telegram message failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, telegramChatId]);
  const handlePrimaryAction = (0, import_react.useCallback)(() => {
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
  const appendOperatorEntry = (0, import_react.useCallback)(
    (entry) => {
      setOperatorNotes((current) => [createSessionEntry(entry), ...current]);
    },
    []
  );
  const handleOperatorNote = (0, import_react.useCallback)(
    (event) => {
      event.preventDefault();
      if (!operatorDraft.trim()) {
        return;
      }
      markAction("composer:add-note");
      appendOperatorEntry({
        title: "Operator note",
        detail: operatorDraft.trim(),
        meta: "Local note",
        tone: "neutral",
        channel: "note"
      });
      setOperatorDraft("");
      pushToast("Operator note added to this session.", "info");
    },
    [appendOperatorEntry, markAction, operatorDraft, pushToast]
  );
  const handleAgentFollowUp = (0, import_react.useCallback)(async () => {
    const followUp = operatorDraft.trim();
    if (!followUp) {
      pushToast("Write a follow-up first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot send runtime follow-ups.", "warn");
      return;
    }
    if (!mission?.mission_id) {
      pushToast("Select a mission before sending a follow-up.", "warn");
      return;
    }
    markAction("composer:send-follow-up");
    try {
      const steeringLines = [];
      const currentPhase = mission?.missionLoop?.currentCyclePhase || mission?.state?.current_cycle_phase || "execute";
      if (mission && agentRuntimeFocus !== "all") {
        steeringLines.push(`Runtime preference: ${runtimeLabel(agentRuntimeFocus)}.`);
      }
      steeringLines.push(
        `Current mission phase: ${titleizeToken(currentPhase)} via ${titleizeToken(
          phaseRouteRole(currentPhase)
        )}.`
      );
      const selectedRoute = workspaceProfileForm.routeOverrides.find((item) => item.role === agentRouteRole) || {};
      const effectiveRoute = asList2(mission?.effectiveRouteContract?.roles).find((item) => item.role === agentRouteRole) || {};
      const routeChanged = (selectedRoute.provider || "openai") !== (effectiveRoute.provider || "openai") || (selectedRoute.model || "").trim() !== (effectiveRoute.model || "").trim() || (selectedRoute.effort || "default") !== (effectiveRoute.effort || "default");
      if (routeChanged && selectedRoute.model?.trim()) {
        steeringLines.push(
          `Route preference for ${titleizeToken(agentRouteRole)}: ${titleizeToken(selectedRoute.provider)} / ${selectedRoute.model.trim()}${selectedRoute.effort && selectedRoute.effort !== "default" ? ` / ${selectedRoute.effort}` : ""}.`
        );
      }
      const activeProvider = String(
        selectedRoute.provider || effectiveRoute.provider || "openai"
      ).trim().toLowerCase();
      if (codeExecutionEnabled && ["openai", "openai-codex"].includes(activeProvider)) {
        steeringLines.push(
          `If the OpenAI route is active, use the python tool / code execution when it will ground the work. Prefer a ${codeExecutionMemory} container budget.`
        );
      }
      const composedFollowUp = steeringLines.length > 0 ? `${steeringLines.join(" ")}

${followUp}` : followUp;
      let sentLive = false;
      if (mission.runtime_id === "openclaw" && data.openClawStatus?.connected) {
        try {
          await callBackend(
            "send_openclaw_message",
            { payload: { message: composedFollowUp } },
            { throwOnError: true }
          );
          sentLive = true;
        } catch (error) {
          pushToast(`OpenClaw live send failed, keeping the follow-up in mission thread: ${error}`, "warn");
        }
      }
      await callBackend(
        "send_control_room_mission_follow_up_command",
        { payload: { missionId: mission.mission_id, message: composedFollowUp, root: null } },
        { throwOnError: true }
      );
      setOperatorDraft("");
      pushToast(sentLive ? "Follow-up sent live and recorded in the mission thread." : "Follow-up recorded in the mission thread.", "info");
    } catch (error) {
      pushToast(`Mission follow-up failed: ${error}`, "error");
    }
  }, [
    codeExecutionEnabled,
    codeExecutionMemory,
    agentRouteRole,
    agentRuntimeFocus,
    data.openClawStatus?.connected,
    markAction,
    mission,
    operatorDraft,
    previewMode,
    pushToast,
    workspaceProfileForm.routeOverrides,
    mission?.effectiveRouteContract?.roles
  ]);
  const handleOpenClawConnect = (0, import_react.useCallback)(async () => {
    markAction("runtime:openclaw-connect");
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend(
        "connect_openclaw_gateway",
        { payload: { gatewayUrl: openClawGatewayUrl.trim() || null } },
        { throwOnError: true }
      );
      pushToast("OpenClaw gateway connect requested.", "info");
      await refreshAll("openclaw-connect");
    } catch (error) {
      pushToast(`OpenClaw connect failed: ${error}`, "error");
    }
  }, [markAction, openClawGatewayUrl, previewMode, pushToast, refreshAll]);
  const handleOpenClawDisconnect = (0, import_react.useCallback)(async () => {
    markAction("runtime:openclaw-disconnect");
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend("disconnect_openclaw_gateway", void 0, { throwOnError: true });
      pushToast("OpenClaw gateway disconnected.", "info");
      await refreshAll("openclaw-disconnect");
    } catch (error) {
      pushToast(`OpenClaw disconnect failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);
  const handleOpenClawSaveToken = (0, import_react.useCallback)(async () => {
    markAction("runtime:openclaw-save-token");
    if (!openClawGatewayToken.trim()) {
      pushToast("Paste a gateway token first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend(
        "save_openclaw_gateway_token",
        { token: openClawGatewayToken.trim() },
        { throwOnError: true }
      );
      setOpenClawGatewayToken("");
      pushToast("OpenClaw gateway token saved.", "info");
      await refreshAll("openclaw-token-save");
    } catch (error) {
      pushToast(`OpenClaw token save failed: ${error}`, "error");
    }
  }, [markAction, openClawGatewayToken, previewMode, pushToast, refreshAll]);
  const handleOpenClawClearToken = (0, import_react.useCallback)(async () => {
    markAction("runtime:openclaw-clear-token");
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change OpenClaw gateway state.", "warn");
      return;
    }
    try {
      await callBackend("clear_openclaw_gateway_token", void 0, { throwOnError: true });
      pushToast("OpenClaw gateway token cleared.", "info");
      await refreshAll("openclaw-token-clear");
    } catch (error) {
      pushToast(`OpenClaw token clear failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);
  const handleProviderSecretSave = (0, import_react.useCallback)(async (providerId) => {
    markAction(`provider-secret:save:${providerId}`);
    const secret = String(providerSecretDrafts?.[providerId] || "").trim();
    if (!secret) {
      pushToast("Paste a provider API key first.", "warn");
      return;
    }
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change provider authentication.", "warn");
      return;
    }
    try {
      const payload = { providerId, secret };
      const saved = await callBackend("save_provider_secret_command", payload) ?? await callBackend("save_provider_secret_command", {
        provider_id: providerId,
        secret
      });
      if (!saved) {
        throw new Error("Provider secret save did not complete.");
      }
      setProviderSecretDrafts((current) => ({ ...current, [providerId]: "" }));
      pushToast(`${titleizeToken(providerId)} secret saved.`, "info");
      await refreshAll(`provider-secret-save-${providerId}`);
    } catch (error) {
      pushToast(`Provider secret save failed: ${error}`, "error");
    }
  }, [markAction, previewMode, providerSecretDrafts, pushToast, refreshAll]);
  const handleProviderSecretClear = (0, import_react.useCallback)(async (providerId) => {
    markAction(`provider-secret:clear:${providerId}`);
    if (previewMode !== "live" || !hasTauriBackend()) {
      pushToast("Preview mode cannot change provider authentication.", "warn");
      return;
    }
    try {
      const cleared = await callBackend("clear_provider_secret_command", { providerId }) ?? await callBackend("clear_provider_secret_command", {
        provider_id: providerId
      });
      if (!cleared) {
        throw new Error("Provider secret clear did not complete.");
      }
      setProviderSecretDrafts((current) => ({ ...current, [providerId]: "" }));
      pushToast(`${titleizeToken(providerId)} secret cleared.`, "info");
      await refreshAll(`provider-secret-clear-${providerId}`);
    } catch (error) {
      pushToast(`Provider secret clear failed: ${error}`, "error");
    }
  }, [markAction, previewMode, pushToast, refreshAll]);
  const openClawRuntimeActive = mission?.runtime_id === "openclaw";
  const openClawStatus = data.openClawStatus;
  const delegatedSessions = (0, import_react.useMemo)(
    () => Array.isArray(mission?.delegated_runtime_sessions) ? mission.delegated_runtime_sessions : [],
    [mission?.delegated_runtime_sessions]
  );
  const bridgeSessions = (0, import_react.useMemo)(
    () => Array.isArray(snapshot?.bridgeLab?.connectedSessions) ? snapshot.bridgeLab.connectedSessions : [],
    [snapshot?.bridgeLab?.connectedSessions]
  );
  const effectiveRouteRows = (0, import_react.useMemo)(
    () => Array.isArray(mission?.effectiveRouteContract?.roles) ? mission.effectiveRouteContract.roles : [],
    [mission?.effectiveRouteContract?.roles]
  );
  const missionRuntimeContract = (0, import_react.useMemo)(
    () => mission ? [
      {
        label: "Runtime",
        value: runtimeLabel(mission?.runtime_id)
      },
      {
        label: "Profile",
        value: titleizeToken(mission?.selected_profile || workspace?.user_profile || profileId)
      },
      {
        label: "Mode",
        value: titleizeToken(mission?.run_budget?.mode || mission?.missionLoop?.timeBudget?.mode || "autopilot")
      },
      {
        label: "Run until",
        value: titleizeToken(
          mission?.missionLoop?.timeBudget?.runUntilBehavior || mission?.run_budget?.run_until_behavior || "pause_on_failure"
        )
      },
      {
        label: "Harness",
        value: titleizeToken(mission?.harness_id || workspace?.preferred_harness || "fluxio_hybrid")
      },
      {
        label: "Active route",
        value: (() => {
          const truth = mission?.providerTruth || mission?.missionLoop?.providerTruth || mission?.state?.provider_runtime_truth || {};
          const active = truth?.activeRoute || {};
          if (!active?.provider && !active?.model) {
            return "Not resolved";
          }
          return `${titleizeToken(active.provider)} \xB7 ${active.model || "default"}`;
        })()
      },
      {
        label: "Blocker class",
        value: titleizeToken(
          mission?.state?.blocker_classification?.class || mission?.missionLoop?.blocker?.class || "none"
        )
      },
      {
        label: "Code execution",
        value: (() => {
          const codeState = mission?.state?.code_execution || mission?.missionLoop?.codeExecution || {};
          if (!codeState?.enabled) {
            return "Off";
          }
          return codeState?.container_id ? `On \xB7 ${codeState.container_id}` : "On \xB7 auto container";
        })()
      }
    ] : [],
    [
      mission,
      profileId,
      workspace?.preferred_harness,
      workspace?.user_profile
    ]
  );
  const builderBoard = viewModel.drawers.builder.board;
  const workspaceById = (0, import_react.useMemo)(
    () => new Map(workspaces.map((item) => [item.workspace_id, item])),
    [workspaces]
  );
  const workspaceNavItems = (0, import_react.useMemo)(
    () => workspaces.map((item) => {
      const workspaceMissionRows = missions.filter((entry) => entry?.workspace_id === item.workspace_id);
      const activeCount = workspaceMissionRows.filter(
        (entry) => !["completed", "failed"].includes(entry?.state?.status || "")
      ).length;
      const blockedCount = workspaceMissionRows.filter(
        (entry) => asList2(entry?.proof?.pending_approvals).length > 0 || asList2(entry?.state?.verification_failures).length > 0 || ["needs_approval", "blocked", "verification_failed", "queued"].includes(
          entry?.state?.status || ""
        )
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
          blockedCount > 0 ? { label: "blocked", value: blockedCount, tone: "warn" } : null
        ].filter(Boolean)
      };
    }),
    [missions, workspaces]
  );
  const missionNavItems = (0, import_react.useMemo)(
    () => missionOptions.map((item) => {
      const ownerWorkspace = workspaceById.get(item.workspace_id) || null;
      const executionPath = item?.delegated_runtime_sessions?.find((session) => session?.execution_root)?.execution_root || item?.execution_scope?.execution_root || item?.state?.execution_scope?.execution_root || ownerWorkspace?.root_path || "";
      const approvalCount = asList2(item?.proof?.pending_approvals).length;
      const verificationCount = asList2(item?.state?.verification_failures).length;
      const delegatedCount = asList2(item?.delegated_runtime_sessions).filter(
        (session) => !["completed", "failed", "stopped"].includes(session?.status || "")
      ).length;
      const queuedCount = ["queued", "needs_approval", "blocked"].includes(item?.state?.status || "") ? 1 : 0;
      const tone = verificationCount > 0 ? "bad" : approvalCount > 0 || queuedCount > 0 ? "warn" : delegatedCount > 0 || item?.state?.status === "running" ? "good" : "neutral";
      return {
        missionId: item.mission_id,
        title: item.title || item.objective,
        subtitle: `${runtimeLabel(item.runtime_id)} \xB7 ${titleizeToken(item.state?.status || "draft")}`,
        context: executionPath,
        tone,
        badge: pathLeaf(executionPath) || pathLeaf(ownerWorkspace?.root_path) || titleizeToken(item.state?.status || "draft"),
        stats: [
          approvalCount > 0 ? { label: "approvals", value: approvalCount, tone: "warn" } : null,
          verificationCount > 0 ? { label: "failures", value: verificationCount, tone: "bad" } : null,
          delegatedCount > 0 ? { label: "lanes", value: delegatedCount, tone: "good" } : null,
          queuedCount > 0 && approvalCount === 0 ? { label: "queued", value: queuedCount, tone: "warn" } : null
        ].filter(Boolean)
      };
    }),
    [missionOptions, workspaceById]
  );
  const builderRootItems = (0, import_react.useMemo)(() => builderBoard.roots || [], [builderBoard.roots]);
  const builderNexusItems = (0, import_react.useMemo)(() => builderBoard.nexuses || [], [builderBoard.nexuses]);
  const builderPrimaryConversation = (0, import_react.useMemo)(
    () => builderBoard.activeConversations.find((item) => item.selected) || builderBoard.activeConversations.find((item) => item.blocked) || builderBoard.activeConversations[0] || null,
    [builderBoard.activeConversations]
  );
  const builderSecondaryConversations = (0, import_react.useMemo)(
    () => builderBoard.activeConversations.filter(
      (item) => item.missionId !== builderPrimaryConversation?.missionId
    ),
    [builderBoard.activeConversations, builderPrimaryConversation?.missionId]
  );
  const tutorialStudio = viewModel.drawers.builder.tutorialStudio;
  const recommendationStudio = viewModel.drawers.builder.recommendationStudio;
  const liveReviewStudio = viewModel.drawers.builder.liveReviewStudio;
  const builderSelectedReviewTarget = (0, import_react.useMemo)(
    () => liveReviewStudio.targets.find((item) => item.id === selectedReviewTargetId) || liveReviewStudio.targets[0] || null,
    [liveReviewStudio.targets, selectedReviewTargetId]
  );
  const topbarStatus = (0, import_react.useMemo)(() => {
    if (uiMode === "builder") {
      return {
        label: "Builder focus",
        value: builderBoard.activeConversations.length > 0 ? `${builderBoard.activeConversations.length} active conversation${builderBoard.activeConversations.length === 1 ? "" : "s"}` : "No active conversations",
        tone: builderBoard.activeConversations.length > 0 ? builderBoard.activeConversations.some((item) => item.blocked) ? "warn" : "good" : "neutral"
      };
    }
    if (agentBlockedState.isBlocked) {
      return {
        label: "Blocker state",
        value: viewModel.topBar.liveStatus.label,
        tone: viewModel.topBar.liveStatus.tone
      };
    }
    return {
      label: mission ? "Mission state" : "Workspace state",
      value: mission ? viewModel.topBar.liveStatus.label : setupHealth.environmentReady ? "Environment ready" : "Needs setup",
      tone: mission ? viewModel.topBar.liveStatus.tone : setupHealth.environmentReady ? "good" : "warn"
    };
  }, [
    agentBlockedState.isBlocked,
    builderBoard.activeConversations,
    mission,
    setupHealth.environmentReady,
    uiMode,
    viewModel.topBar.liveStatus.label,
    viewModel.topBar.liveStatus.tone
  ]);
  const runtimeOptions = (0, import_react.useMemo)(
    () => asList2(snapshot?.runtimes).map((item) => ({
      value: item.runtime_id,
      label: item.label || runtimeLabel(item.runtime_id)
    })),
    [snapshot?.runtimes]
  );
  const bridgeSummary = (0, import_react.useMemo)(() => {
    const connected = bridgeSessions.filter((item) => item?.status === "connected").length;
    const callbackReady = bridgeSessions.filter((item) => item?.approval_callback).length;
    return {
      connected,
      callbackReady,
      totalApps: asList2(snapshot?.bridgeLab?.discoveredApps).length,
      recommendation: snapshot?.bridgeLab?.recommendation || "Bridge hand-offs between runtimes and connected apps will appear here."
    };
  }, [bridgeSessions, snapshot?.bridgeLab?.discoveredApps, snapshot?.bridgeLab?.recommendation]);
  const selectedAgentRoute = (0, import_react.useMemo)(
    () => {
      const explicit = workspaceProfileForm.routeOverrides.find((item) => item.role === agentRouteRole) || {};
      const effective = effectiveRouteRows.find((item) => item.role === agentRouteRole) || {};
      return {
        role: agentRouteRole,
        provider: explicit.provider || effective.provider || "openai",
        model: explicit.model || effective.model || "",
        effort: explicit.effort || effective.effort || "default"
      };
    },
    [agentRouteRole, effectiveRouteRows, workspaceProfileForm.routeOverrides]
  );
  const activeEffectiveRoute = (0, import_react.useMemo)(
    () => effectiveRouteRows.find((item) => item.role === agentRouteRole) || {
      role: agentRouteRole,
      provider: selectedAgentRoute.provider,
      model: selectedAgentRoute.model,
      effort: selectedAgentRoute.effort
    },
    [
      agentRouteRole,
      effectiveRouteRows,
      selectedAgentRoute.effort,
      selectedAgentRoute.model,
      selectedAgentRoute.provider
    ]
  );
  const builderStudioCards = (0, import_react.useMemo)(
    () => [
      {
        id: "runtime",
        eyebrow: "Runtime studio",
        title: "Hermes and OpenClaw",
        detail: "Update runtimes, inspect service drift, and repair failing bridges without leaving the shell.",
        meta: `${viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount} need attention \xB7 ${viewModel.drawers.builder.serviceStudio.availableActionCount} actions`,
        tone: viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount > 0 ? "warn" : "good"
      },
      {
        id: "skills",
        eyebrow: "Skill studio",
        title: "Reusable capability packs",
        detail: "Review skill coverage, tighten quality, and keep execution-ready packs visible.",
        meta: `${viewModel.drawers.builder.skillStudio.summary.executionReadyCount} ready \xB7 ${viewModel.drawers.builder.skillStudio.summary.needsTestCount} need tests`,
        tone: viewModel.drawers.builder.skillStudio.summary.needsTestCount > 0 ? "warn" : "neutral"
      },
      {
        id: "profiles",
        eyebrow: "Routing studio",
        title: "Profiles and model routes",
        detail: "Pin planner, executor, and verifier behavior when the default profile is not enough.",
        meta: `${viewModel.drawers.builder.profileStudio.profileRows.length} profiles \xB7 ${effectiveRouteRows.length} active route role${effectiveRouteRows.length === 1 ? "" : "s"}`,
        tone: "neutral"
      },
      {
        id: "proof",
        eyebrow: "Review studio",
        title: "Proof, queue, and release truth",
        detail: "Audit what is ready, what is secondary, and what still needs explicit operator review.",
        meta: `${viewModel.drawers.builder.reviewCount} review surface${viewModel.drawers.builder.reviewCount === 1 ? "" : "s"} \xB7 ${viewModel.drawers.builder.confidence.score}% confidence`,
        tone: viewModel.drawers.builder.confidence.tone
      }
    ],
    [
      effectiveRouteRows.length,
      viewModel.drawers.builder.confidence.score,
      viewModel.drawers.builder.confidence.tone,
      viewModel.drawers.builder.profileStudio.profileRows.length,
      viewModel.drawers.builder.reviewCount,
      viewModel.drawers.builder.serviceStudio.availableActionCount,
      viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount,
      viewModel.drawers.builder.skillStudio.summary.executionReadyCount,
      viewModel.drawers.builder.skillStudio.summary.needsTestCount
    ]
  );
  const workspaceGitSnapshot = workspace?.gitSnapshot || {};
  const branchInspectAction = (0, import_react.useMemo)(
    () => asList2(viewModel.drawers.builder.gitActions).find(
      (item) => item.actionId === "inspect_repo_state"
    ) || asList2(viewModel.drawers.builder.gitActions)[0] || null,
    [viewModel.drawers.builder.gitActions]
  );
  const branchPullAction = (0, import_react.useMemo)(
    () => asList2(viewModel.drawers.builder.gitActions).find(
      (item) => item.actionId === "pull_branch"
    ) || null,
    [viewModel.drawers.builder.gitActions]
  );
  const branchPushAction = (0, import_react.useMemo)(
    () => asList2(viewModel.drawers.builder.gitActions).find(
      (item) => item.actionId === "push_branch"
    ) || null,
    [viewModel.drawers.builder.gitActions]
  );
  const sidebarAccessLabel = previewMode === "live" ? "Full access" : "Read-only preview";
  const sidebarLocalPath = workspace?.root_path || snapshot?.workspaceRoot || "";
  const sidebarLocalLeaf = pathLeaf(sidebarLocalPath) || "workspace";
  const sidebarBranchName = String(workspaceGitSnapshot?.branch || "").trim() || "No branch";
  const sidebarBranchTone = !workspaceGitSnapshot?.repoDetected ? "warn" : workspaceGitSnapshot?.dirty || Number(workspaceGitSnapshot?.behind || 0) > 0 ? "warn" : "good";
  const sidebarBranchContext = !workspaceGitSnapshot?.repoDetected ? "Git repository not detected for selected workspace." : [
    workspaceGitSnapshot?.trackingBranch ? `tracking ${workspaceGitSnapshot.trackingBranch}` : "no tracking branch",
    `${workspaceGitSnapshot?.stagedCount || 0} staged`,
    `${workspaceGitSnapshot?.unstagedCount || 0} unstaged`,
    `${workspaceGitSnapshot?.untrackedCount || 0} untracked`
  ].join(" \xB7 ");
  const handleSidebarAccess = (0, import_react.useCallback)(() => {
    markAction("quick:access");
    setUiMode("builder");
    setActiveDrawer("settings");
  }, [markAction]);
  const handleSidebarLocal = (0, import_react.useCallback)(() => {
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
    workspaces
  ]);
  const handleSidebarFolders = (0, import_react.useCallback)(() => {
    markAction("quick:folders");
    setUiMode("builder");
    setActiveDrawer("builder");
  }, [markAction]);
  const handleSidebarBranch = (0, import_react.useCallback)(async () => {
    markAction("quick:branch");
    if (branchInspectAction) {
      await runWorkspaceActionSpec(branchInspectAction);
      return;
    }
    setUiMode("builder");
    setActiveDrawer("builder");
  }, [branchInspectAction, markAction, runWorkspaceActionSpec]);
  const handleSidebarBranchPull = (0, import_react.useCallback)(async () => {
    if (!branchPullAction) {
      return;
    }
    await runWorkspaceActionSpec(branchPullAction);
  }, [branchPullAction, runWorkspaceActionSpec]);
  const handleSidebarBranchPush = (0, import_react.useCallback)(async () => {
    if (!branchPushAction) {
      return;
    }
    await runWorkspaceActionSpec(branchPushAction);
  }, [branchPushAction, runWorkspaceActionSpec]);
  (0, import_react.useEffect)(() => {
    currentMissionRef.current = mission;
  }, [mission]);
  (0, import_react.useEffect)(() => {
    currentDelegatedSessionsRef.current = delegatedSessions;
  }, [delegatedSessions]);
  const agentTranscript = (0, import_react.useMemo)(() => {
    const timelineTurns = [];
    const seenTurnKeys = /* @__PURE__ */ new Set();
    const pushTurn = (item) => {
      if (!item || !item.title && !item.detail) {
        return;
      }
      const timestampRaw = item.timestampRaw || "";
      const dedupeKey = item.dedupeKey || [
        item.role || "",
        item.label || "",
        item.title || "",
        item.detail || "",
        timestampRaw
      ].join("|");
      if (seenTurnKeys.has(dedupeKey)) {
        return;
      }
      seenTurnKeys.add(dedupeKey);
      timelineTurns.push({
        ...item,
        timestampRaw,
        sortValue: Number.isFinite(item.sortValue) ? item.sortValue : timeValue2(timestampRaw),
        sortOrder: timelineTurns.length
      });
    };
    for (const note of operatorNotes) {
      pushTurn({
        id: `operator-${note.id}`,
        dedupeKey: `operator:${note.id}`,
        role: "operator",
        roleIcon: "\u25C9",
        label: note.channel === "followup" ? "Follow-up sent" : "Operator note",
        title: note.detail,
        detail: note.meta,
        meta: timestampLabel(note.createdAt),
        timestampRaw: note.createdAt,
        tone: note.tone || "neutral"
      });
    }
    const codeArtifacts = asList2(
      mission?.state?.code_execution?.artifacts || mission?.missionLoop?.codeExecution?.artifacts
    ).slice().reverse().slice(0, 4);
    for (const artifact of codeArtifacts) {
      pushTurn({
        id: `code-artifact-${artifact.artifact_id || artifact.created_at || artifact.action_id}`,
        dedupeKey: `code-artifact:${artifact.artifact_id || artifact.created_at || artifact.action_id}`,
        role: "runtime",
        runtimeId: mission?.runtime_id || "",
        roleLabel: "Code execution",
        roleIcon: "\u25C7",
        label: titleizeToken(artifact.kind || "artifact"),
        title: artifact.title || artifact.action_id || "Code execution artifact",
        detail: artifact.summary || "No summary captured.",
        meta: timestampLabel(artifact.created_at),
        timestampRaw: artifact.created_at,
        tone: artifact.ok ? "neutral" : "bad",
        processMessage: true,
        emphasis: true,
        chips: [
          artifact.container_id ? artifact.container_id : "",
          artifact.runtime ? titleizeToken(artifact.runtime) : ""
        ].filter(Boolean)
      });
    }
    for (const action of asList2(mission?.action_history).slice(-6)) {
      const actionKind = action?.proposal?.kind || action?.action_id || "action";
      const actionGatePending = action?.gate?.status === "pending";
      const actionStdout = action?.result?.stdout || "";
      const actionError = action?.result?.error || "";
      const actionRuntimeLike = action?.proposal?.sourceKind === "delegated" || /runtime|delegate|test|verify|command/i.test(actionKind);
      const actionResult = actionError || actionStdout;
      if (actionGatePending || !actionResult) {
        continue;
      }
      pushTurn({
        id: `action-${action?.action_id || actionKind}-${action?.executed_at || actionResult}`,
        dedupeKey: `action:${action?.action_id || actionKind}:${action?.executed_at || actionResult}`,
        role: actionRuntimeLike ? "runtime" : "system",
        runtimeId: actionRuntimeLike ? mission?.runtime_id : "",
        roleLabel: actionRuntimeLike ? runtimeLabel(mission?.runtime_id) : "Fluxio",
        roleIcon: actionRuntimeLike ? mission?.runtime_id === "hermes" ? "\u2B22" : "\u25C7" : "\xB7",
        label: actionRuntimeLike ? "Process message" : titleizeToken(actionKind),
        title: action?.proposal?.title || action?.action_id || "Mission action",
        detail: actionResult,
        technicalDetail: actionStdout && actionStdout !== actionResult ? actionStdout : "",
        technicalSummary: actionStdout && actionStdout !== actionResult ? "Thinking trace" : "",
        meta: timestampLabel(action?.executed_at),
        timestampRaw: action?.executed_at,
        tone: actionError ? "bad" : "neutral",
        processMessage: actionRuntimeLike,
        emphasis: Boolean(actionError || actionRuntimeLike)
      });
    }
    for (const event of liveControlEvents) {
      if (!event.processMessage && event.role !== "operator" && event.role !== "bridge") {
        continue;
      }
      pushTurn({
        ...event,
        dedupeKey: `live:${event.role || ""}:${event.kind || ""}:${event.title || ""}:${event.timestampRaw || ""}`
      });
    }
    for (const session of delegatedSessions) {
      const delegatedMessageId = session.delegated_id || `${session.runtime_id || "runtime"}-${session.updated_at || session.last_event || "session"}`;
      const latestEvents = asList2(session.latest_events);
      const meaningfulEvents = latestEvents.filter(
        (event) => isTraceRuntimeKind(event.kind) || ["runtime.phase_entered", "runtime.route_switch_reason", "runtime.handoff"].includes(
          String(event.kind || "").toLowerCase()
        ) || event.status === "failed"
      );
      if (meaningfulEvents.length === 0 && (session.status === "failed" || session.heartbeat_status === "stale")) {
        pushTurn({
          id: `delegated-${delegatedMessageId}`,
          dedupeKey: `delegated:${delegatedMessageId}`,
          role: "runtime",
          runtimeId: session.runtime_id,
          roleLabel: runtimeLabel(session.runtime_id),
          roleIcon: session.runtime_id === "hermes" ? "\u2B22" : "\u25C7",
          label: `${runtimeLabel(session.runtime_id)} lane`,
          title: session.detail || session.last_event || `${runtimeLabel(session.runtime_id)} session ${titleizeToken(session.status || "active")}`,
          detail: session.heartbeat_status === "stale" ? "Heartbeat is stale. Builder runtime view can inspect the lane in detail." : session.execution_target_detail || session.execution_root || "Delegated runtime lane is being supervised from Fluxio.",
          meta: timestampLabel(session.updated_at),
          timestampRaw: session.updated_at,
          tone: session.heartbeat_status === "stale" ? "warn" : session.status === "failed" ? "bad" : "neutral",
          emphasis: session.status === "failed" || session.heartbeat_status === "stale",
          chips: [
            titleizeToken(session.status || "unknown"),
            session.execution_target ? titleizeToken(session.execution_target) : ""
          ].filter(Boolean)
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
          roleIcon: session.runtime_id === "hermes" ? "\u2B22" : "\u25C7",
          label: phaseEntered ? "Phase entered" : routeSwitchReason ? "Route switch reason" : handoffEvent ? "Runtime handoff" : processMessage ? "Process message" : titleizeToken(event.kind || "runtime event"),
          title: event.message || "Runtime event",
          detail: (phaseEntered ? `${titleizeToken(event?.data?.phase || "execute")} phase via ${titleizeToken(
            event?.data?.role || "route"
          )}${event?.data?.provider ? ` \xB7 ${titleizeToken(event.data.provider)}` : ""}${event?.data?.model ? ` \xB7 ${event.data.model}` : ""}` : routeSwitchReason ? event?.data?.reason || event.message || "Route switch reason emitted by runtime supervision." : handoffEvent ? event?.data?.reason || event.message || "Runtime handoff emitted by supervision." : routeSwitch ? `${titleizeToken(event?.data?.phase || "execute")} phase \xB7 ${titleizeToken(
            event?.data?.role || "route"
          )} route` : event.detail) || (processMessage ? session.execution_target_detail || "Delegated runtime process output." : session.execution_target_detail || "Delegated runtime supervision is still flowing into the thread."),
          meta: timestampLabel(event.created_at || session.updated_at),
          timestampRaw: event.created_at || session.updated_at,
          tone: event.status === "failed" ? "bad" : /approval|blocked|stale/i.test(`${event.kind || ""} ${event.message || ""}`) ? "warn" : "neutral",
          technicalDetail: processMessage ? event.trace || session.detail || session.execution_target_detail || session.execution_root || "" : "",
          technicalSummary: processMessage ? "Thinking trace" : "",
          processMessage,
          emphasis: processMessage || phaseEntered || routeSwitchReason || handoffEvent || event.status === "failed" || /approval|blocked|error/i.test(`${event.kind || ""} ${event.message || ""}`),
          chips: [
            session.status ? titleizeToken(session.status) : "",
            session.execution_target ? titleizeToken(session.execution_target) : "",
            routeSwitch && event?.data?.phase ? titleizeToken(event.data.phase) : "",
            routeSwitch && event?.data?.role ? titleizeToken(event.data.role) : "",
            phaseEntered && event?.data?.provider ? titleizeToken(event.data.provider) : "",
            phaseEntered && event?.data?.model ? event.data.model : "",
            routeSwitchReason && event?.data?.reason ? event.data.reason : "",
            handoffEvent && event?.data?.source_delegated_id ? event.data.source_delegated_id : "",
            event.status ? titleizeToken(event.status) : ""
          ].filter(Boolean)
        });
      }
    }
    for (const activity of asList2(snapshot.activity).slice(0, 6)) {
      const kind = activity?.kind || "activity";
      const role = /bridge|app/i.test(kind) ? "bridge" : /approval|question/i.test(kind) ? "queue" : /runtime|delegate|verification|activity/i.test(kind) ? "runtime" : "system";
      if (role !== "bridge") {
        continue;
      }
      pushTurn({
        id: `activity-${kind}-${activity?.timestamp || activity?.message}`,
        dedupeKey: `activity:${kind}:${activity?.message || ""}:${activity?.timestamp || ""}`,
        role,
        roleLabel: role === "bridge" ? "Bridge" : role === "queue" ? "Needs attention" : role === "runtime" ? "Runtime" : "Fluxio",
        roleIcon: role === "bridge" ? "\u2301" : role === "queue" ? "!" : role === "runtime" ? "\u25C7" : "\xB7",
        label: titleizeToken(kind),
        title: activity?.message || "Activity update",
        detail: activity?.detail || "",
        meta: timestampLabel(activity?.timestamp),
        timestampRaw: activity?.timestamp,
        tone: role === "queue" ? "warn" : activity?.tone || "neutral"
      });
    }
    for (const message of data.openClawMessages) {
      pushTurn({
        id: `openclaw-${message.id}`,
        dedupeKey: `openclaw:${message.id || message.createdAt || message.detail}`,
        role: "runtime",
        runtimeId: "openclaw",
        roleLabel: "OpenClaw",
        roleIcon: "\u25C7",
        label: "Process message",
        title: message.detail,
        detail: message.meta || "Gateway message",
        meta: timestampLabel(message.createdAt),
        timestampRaw: message.createdAt,
        tone: message.tone || "neutral",
        processMessage: true,
        emphasis: true
      });
    }
    const sortedTurns = timelineTurns.filter((item) => item.title || item.detail).sort((left, right) => {
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
    return sortedTurns.filter((item) => !item.heartbeat).map(({ sortOrder, sortValue, ...item }) => item);
  }, [
    data.openClawMessages,
    data.pendingApprovals,
    data.pendingQuestions,
    delegatedSessions,
    liveControlEvents,
    mission,
    operatorNotes,
    snapshot.activity
  ]);
  const agentVisibleTranscript = (0, import_react.useMemo)(
    () => agentTranscript.filter((item) => {
      if (!mission || agentRuntimeFocus === "all") {
        return true;
      }
      if (item.role !== "runtime") {
        return true;
      }
      return !item.runtimeId || item.runtimeId === agentRuntimeFocus;
    }),
    [agentRuntimeFocus, agentTranscript, mission]
  );
  const agentThinkingTurns = (0, import_react.useMemo)(
    () => agentVisibleTranscript.filter((item) => item.processMessage || item.technicalDetail),
    [agentVisibleTranscript]
  );
  const agentNexusTurns = (0, import_react.useMemo)(() => {
    const direct = agentVisibleTranscript.filter((item) => {
      const text = `${item.label || ""} ${item.title || ""} ${item.detail || ""}`.toLowerCase();
      return pinnedNexusIds.includes(item.id) || item.role === "queue" || item.tone === "bad" || /approval|verification|blocked|replan|switch|route|review|deploy|patch/.test(text) || item.processMessage && /plan|patch|review|approval|verify|switch/.test(text);
    });
    return direct.slice(-6);
  }, [agentVisibleTranscript, pinnedNexusIds]);
  const agentHasTurns = agentVisibleTranscript.length > 0;
  const agentIdleState = !mission ? "no-mission" : agentHasTurns ? "active" : "no-turns";
  const agentCenterTitle = mission?.title || mission?.objective || workspace?.name || "Fluxio workspace";
  const agentComposerLabel = !mission ? "Mission prompt" : "Follow-up or note";
  const agentComposerPlaceholder = !mission ? workspaces.length > 0 ? "Describe the next mission you want Fluxio to run." : "Add a workspace, then describe the next mission you want Fluxio to run." : openClawRuntimeActive ? "Send a direct follow-up to the runtime, or keep a local operator note." : viewModel.thread.composerPlaceholder;
  const handleAgentIdlePrimaryAction = (0, import_react.useCallback)(() => {
    if (workspaces.length === 0) {
      setShowWorkspaceDialog(true);
      return;
    }
    openMissionDialog();
  }, [openMissionDialog, workspaces.length]);
  const agentRuntimeSelectValue = mission ? agentRuntimeFocus : missionForm.runtime;
  const agentRuntimeHint = !mission ? "Choose the runtime for the next mission launch." : agentRuntimeFocus === "all" ? `Showing every visible runtime trace. Active lane: ${runtimeLabel(mission?.runtime_id)}.` : `Filtering the transcript to ${runtimeLabel(agentRuntimeFocus)} turns while keeping operator and bridge context visible.`;
  const agentCyclePhase = mission?.missionLoop?.currentCyclePhase || mission?.state?.current_cycle_phase || "plan";
  const agentCycleRole = phaseRouteRole(agentCyclePhase);
  const agentRouteStatus = `${titleizeToken(activeEffectiveRoute.provider || selectedAgentRoute.provider)} \xB7 ${activeEffectiveRoute.model || selectedAgentRoute.model || "Profile default"} \xB7 ${activeEffectiveRoute.effort || selectedAgentRoute.effort || "default"}`;
  const providerSecretPresence = data.providerSecretPresence || {};
  const providerSetupStatus = snapshot?.providerSetupStatus || {};
  const openAIProviderStatus = (providerSetupStatus && typeof providerSetupStatus === "object" ? providerSetupStatus.openai : null) || {};
  const minimaxProviderStatus = (providerSetupStatus && typeof providerSetupStatus === "object" ? providerSetupStatus.minimax : null) || {};
  const missionProviderTruth = mission?.providerTruth || mission?.missionLoop?.providerTruth || mission?.state?.provider_runtime_truth || {};
  const missionCodeExecutionState = mission?.state?.code_execution || mission?.missionLoop?.codeExecution || {};
  const codeExecutionArtifacts = asList2(missionCodeExecutionState?.artifacts).slice().reverse().slice(0, 4);
  const openAISecretReady = Boolean(
    providerSecretPresence.openai || providerSecretPresence["openai-codex"]
  );
  const openAICodexAuthReady = Boolean(
    openAIProviderStatus?.authPresent || openAIProviderStatus?.configured || openAISecretReady
  );
  const openAICodexAuthPath = String(
    openAIProviderStatus?.authPath || (openAISecretReady ? "API key" : "not configured")
  );
  const minimaxAuthReady = Boolean(
    minimaxProviderStatus?.configured || minimaxProviderStatus?.authPresent
  );
  const modelAuthReady = openAICodexAuthReady || minimaxAuthReady;
  const latestThinkingTurn = agentThinkingTurns[agentThinkingTurns.length - 1] || null;
  const openAuthDrawer = (0, import_react.useCallback)(() => {
    setUiMode("builder");
    setActiveDrawer("runtime");
    window.setTimeout(() => {
      document.getElementById("provider-auth-panel")?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    }, 0);
  }, []);
  (0, import_react.useEffect)(() => {
    if (previewMode !== "live" || mission || workspaces.length === 0 || modelAuthReady || authPromptedRef.current) {
      return;
    }
    authPromptedRef.current = true;
    openAuthDrawer();
  }, [mission, modelAuthReady, openAuthDrawer, previewMode, workspaces.length]);
  const drawerItems = (0, import_react.useMemo)(() => {
    const items = [
      {
        id: "queue",
        label: "Queue",
        count: viewModel.drawers.queue.count,
        tone: viewModel.drawers.queue.urgent ? "warn" : "neutral"
      },
      {
        id: "proof",
        label: "Proof",
        count: viewModel.drawers.proof.itemsCount,
        tone: viewModel.drawers.proof.tone
      },
      {
        id: "context",
        label: "Context",
        count: viewModel.drawers.context.count,
        tone: "neutral"
      },
      {
        id: "skills",
        label: "Skills",
        count: viewModel.drawers.builder.skillStudio.summary.needsTestCount,
        tone: viewModel.drawers.builder.skillStudio.summary.needsTestCount > 0 ? "warn" : "neutral"
      },
      {
        id: "runtime",
        label: "Runtime",
        count: viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount,
        tone: viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount > 0 ? "warn" : "neutral"
      },
      {
        id: "settings",
        label: "Settings",
        count: 0,
        tone: "neutral"
      }
    ];
    if (uiMode === "builder") {
      items.push({
        id: "profiles",
        label: "Profiles",
        count: viewModel.drawers.builder.profileStudio.profileRows.length,
        tone: "neutral"
      });
      items.push({
        id: "builder",
        label: "Builder",
        count: viewModel.drawers.builder.reviewCount,
        tone: "neutral"
      });
    }
    return items;
  }, [uiMode, viewModel]);
  const visibleDrawerItems = (0, import_react.useMemo)(
    () => uiMode === "builder" ? drawerItems : drawerItems.filter((item) => agentVisibleDrawers.includes(item.id)),
    [agentVisibleDrawers, drawerItems, uiMode]
  );
  const activeDrawerMeta = (0, import_react.useMemo)(
    () => visibleDrawerItems.find((item) => item.id === activeDrawer) || drawerItems.find((item) => item.id === activeDrawer) || null,
    [activeDrawer, drawerItems, visibleDrawerItems]
  );
  const renderDrawerPanel = () => {
    if (activeDrawer === "queue") {
      return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-panel", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Urgency" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: viewModel.drawers.queue.label }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: viewModel.drawers.queue.recommendation.reason })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: viewModel.drawers.queue.items.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(item.tone)}`, children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.type }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.reason })
        ] }, `${item.type}-${item.title}`)) }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: handlePrimaryAction, variant: "primary", children: viewModel.topBar.primaryAction.label }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
            ActionButton,
            {
              disabled: !missionActionAvailable(mission, "resume"),
              onClick: () => void runMissionAction("resume", "Mission resume requested."),
              children: "Resume mission"
            }
          )
        ] })
      ] });
    }
    if (activeDrawer === "proof") {
      return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-panel", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Proof review" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: viewModel.drawers.proof.headline }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: viewModel.drawers.proof.diffSummary })
        ] }),
        viewModel.drawers.proof.sections.map((section) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: section.title }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("ul", { children: section.items.length > 0 ? section.items.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: listLabel2(item) }, `${section.title}-${item}`)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: "Nothing captured yet." }) })
        ] }, section.title))
      ] });
    }
    if (activeDrawer === "skills") {
      const filteredRecommendedSkills = viewModel.drawers.builder.skillStudio.recommended.filter(
        (item) => item.label.toLowerCase().includes(skillStudioQuery.trim().toLowerCase()) || item.description.toLowerCase().includes(skillStudioQuery.trim().toLowerCase())
      );
      const filteredCuratedSkills = viewModel.drawers.builder.skillStudio.curated.filter((item) => {
        const query = skillStudioQuery.trim().toLowerCase();
        const matchesQuery = !query || item.label.toLowerCase().includes(query) || (item.description || "").toLowerCase().includes(query);
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
      return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-panel", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: "Skills" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Install, review, and route the packs that actually support operator work." })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "skill-toolbar", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Filter", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("select", { onChange: (event) => setSkillStudioFilter(event.target.value), value: skillStudioFilter, children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "all", children: "All packs" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "recommended", children: "Installed" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "needs_attention", children: "Needs attention" })
            ] }) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Find skill pack", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "input",
              {
                onChange: (event) => setSkillStudioQuery(event.target.value),
                placeholder: "Search by label or note",
                value: skillStudioQuery
              }
            ) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "context-grid compact-metrics", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Reviewed reusable" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("strong", { children: [
                viewModel.drawers.builder.skillStudio.summary.reviewedReusableCount,
                "/",
                viewModel.drawers.builder.skillStudio.summary.totalSkills
              ] })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Execution ready" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: viewModel.drawers.builder.skillStudio.summary.executionReadyCount })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Need tests" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: viewModel.drawers.builder.skillStudio.summary.needsTestCount })
            ] })
          ] })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Recommended packs" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: filteredRecommendedSkills.length > 0 ? filteredRecommendedSkills.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(item.tone)}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.originType }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.description }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "pill-row", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill", children: item.status }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: item.installed ? "Installed" : "Not installed" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: item.executionCapable ? "Execution" : "Guidance only" })
            ] })
          ] }, `recommended-${item.id}`)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("article", { className: "drawer-card", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: "No recommended pack matches this filter." }) }) })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Curated library" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: filteredCuratedSkills.length > 0 ? filteredCuratedSkills.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(item.tone)}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.originType }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.status }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "pill-row", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill", children: item.testStatus }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                item.usageCount,
                " uses"
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                item.helpedCount,
                " helped"
              ] })
            ] })
          ] }, `curated-${item.id}`)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("article", { className: "drawer-card", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: "No curated pack matches this filter." }) }) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "drawer-footnote", children: viewModel.drawers.builder.skillStudio.capabilitiesNote })
        ] })
      ] });
    }
    if (activeDrawer === "runtime") {
      const primaryRuntimeServices = [
        ...focusedRuntimeServices.hermes,
        ...focusedRuntimeServices.openClaw.filter(
          (item) => !focusedRuntimeServices.hermes.some((existing) => existing.serviceId === item.serviceId)
        )
      ];
      const bridgeServices = focusedRuntimeServices.bridges.filter(
        (item) => !primaryRuntimeServices.some((existing) => existing.serviceId === item.serviceId)
      );
      return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-panel", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: "Runtime and integrations" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Keep Hermes, OpenClaw, and bridge surfaces manageable from one focused review panel." })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", id: "provider-auth-panel", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Provider auth and OpenAI tools" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "context-grid compact-metrics", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "OpenAI / Codex auth" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: `${openAICodexAuthPath} \xB7 ${openAICodexAuthReady ? "Ready" : "Missing"}` }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: openAICodexAuthPath.toLowerCase().includes("chatgpt") ? "Portal auth is configured for Codex sign-in." : "Saved API keys are injected into Fluxio runtime launches." })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Active provider route" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: missionProviderTruth?.activeRoute?.provider ? `${titleizeToken(missionProviderTruth.activeRoute.provider)} \xB7 ${missionProviderTruth.activeRoute.model || "default"}` : "Not resolved" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: missionProviderTruth?.activeRoute?.role ? `${titleizeToken(missionProviderTruth.activeRoute.role)} in ${titleizeToken(missionProviderTruth.currentPhase || agentCyclePhase)}` : "Route role will appear once the mission resolves planner/executor/verifier usage." })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Last successful model call" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: missionProviderTruth?.lastSuccessfulCall?.provider ? `${titleizeToken(missionProviderTruth.lastSuccessfulCall.provider)} \xB7 ${missionProviderTruth.lastSuccessfulCall.model || "default"}` : "None yet" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: missionProviderTruth?.lastSuccessfulCall?.at ? timestampLabel(missionProviderTruth.lastSuccessfulCall.at) : "Success timestamps appear after the first grounded action result." })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Last provider failure" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: missionProviderTruth?.lastFailure?.provider ? `${titleizeToken(missionProviderTruth.lastFailure.provider)} \xB7 ${missionProviderTruth.lastFailure.model || "default"}` : "No provider failure" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: missionProviderTruth?.lastFailure?.summary || "Failures are promoted into this surface when a provider route errors." })
            ] })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: PROVIDER_SECRET_OPTIONS.map((item) => {
            const hasSecret = Boolean(providerSecretPresence[item.id]);
            const providerTruthRow = (providerSetupStatus && typeof providerSetupStatus === "object" ? providerSetupStatus[item.id] : null) || {};
            return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(hasSecret ? "good" : "warn")}`, children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.env }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.note }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: providerTruthRow?.lastSuccessfulModelCall?.provider ? `Last success: ${titleizeToken(providerTruthRow.lastSuccessfulModelCall.provider)} \xB7 ${providerTruthRow.lastSuccessfulModelCall.model || "default"}` : "No successful call recorded yet." }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: providerTruthRow?.lastProviderFailure?.summary ? `Last failure: ${providerTruthRow.lastProviderFailure.summary}` : "No provider failure recorded." }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: `${item.label} API key`, children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "input",
                {
                  onChange: (event) => setProviderSecretDrafts((current) => ({
                    ...current,
                    [item.id]: event.target.value
                  })),
                  placeholder: hasSecret ? "Stored in secure keyring" : "Paste API key",
                  type: "password",
                  value: providerSecretDrafts[item.id] || ""
                }
              ) }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleProviderSecretSave(item.id), children: "Save key" }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleProviderSecretClear(item.id), children: "Clear" })
              ] })
            ] }, `provider-${item.id}`);
          }) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Code execution", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
              "select",
              {
                onChange: (event) => setCodeExecutionEnabled(event.target.value === "enabled"),
                value: codeExecutionEnabled ? "enabled" : "disabled",
                children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "disabled", children: "Disabled" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "enabled", children: "Enabled" })
                ]
              }
            ) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Container memory", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setCodeExecutionMemory(event.target.value),
                value: codeExecutionMemory,
                children: CODE_EXECUTION_MEMORY_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, `code-exec-memory-${option.value}`))
              }
            ) })
          ] }),
          mission ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-list compact runtime-event-mini-list", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Mission container" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: missionCodeExecutionState?.enabled ? missionCodeExecutionState?.container_id || "auto container" : "disabled" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: missionCodeExecutionState?.last_result || "Code execution results and errors are persisted per mission turn." }),
              missionCodeExecutionState?.last_error ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: missionCodeExecutionState.last_error }) : null
            ] }),
            codeExecutionArtifacts.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: titleizeToken(item.kind || "artifact") }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title || item.action_id || "Code execution artifact" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.summary || "No summary captured." }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.created_at ? timestampLabel(item.created_at) : "" })
            ] }, `code-artifact-${item.artifact_id || item.created_at || item.action_id}`))
          ] }) : null,
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "drawer-footnote", children: "Mission-level code execution state now persists container identity, failures, and artifacts so the runtime can reuse the same container across turns." })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "OpenClaw gateway" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "context-grid compact-metrics", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Gateway" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: openClawStatus?.connected ? "Connected" : "Disconnected" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: openClawStatus?.gatewayUrl || openClawGatewayUrl || DEFAULT_OPENCLAW_GATEWAY_URL })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Queued outbound" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: openClawStatus?.queuedOutbound ?? 0 }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: openClawStatus?.reconnectAttempt ? `Reconnect ${openClawStatus.reconnectAttempt}` : "No reconnect pressure" })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Gateway token" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: data.openClawHasToken ? "Stored" : "Missing" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: openClawStatus?.lastError || "No gateway error reported." })
            ] })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Gateway URL", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
            "input",
            {
              onChange: (event) => setOpenClawGatewayUrl(event.target.value),
              placeholder: DEFAULT_OPENCLAW_GATEWAY_URL,
              value: openClawGatewayUrl
            }
          ) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Gateway token", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
            "input",
            {
              onChange: (event) => setOpenClawGatewayToken(event.target.value),
              placeholder: data.openClawHasToken ? "Token stored in keyring" : "Paste a gateway token",
              type: "password",
              value: openClawGatewayToken
            }
          ) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleOpenClawConnect(), variant: "primary", children: "Connect gateway" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleOpenClawDisconnect(), children: "Disconnect" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleOpenClawSaveToken(), children: "Save token" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleOpenClawClearToken(), children: "Clear token" })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "drawer-footnote", children: "Gateway messaging is live in this app. Builder now surfaces install, repair, and update actions for Hermes and OpenClaw when the backend detects version drift." })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Core runtimes" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: primaryRuntimeServices.length > 0 ? primaryRuntimeServices.map((service) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(service.tone)}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: service.category }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: service.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
              service.status,
              service.version ? ` \xB7 ${service.version}` : "",
              service.latestVersion ? ` \u2192 ${service.latestVersion}` : ""
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: service.details || service.managementMode }),
            service.actions.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-actions", children: service.actions.slice(0, 3).map((action) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              ActionButton,
              {
                onClick: () => void runWorkspaceActionSpec(action),
                children: action.label
              },
              `${service.serviceId}-${action.actionId}`
            )) }) : null
          ] }, `runtime-${service.serviceId}`)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: "Hermes and OpenClaw are not surfaced by the backend yet." }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Once those services report through control-room service management, they will appear here." })
          ] }) })
        ] }),
        mission ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Mission execution contract" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "context-grid compact-metrics", children: missionRuntimeContract.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.value })
          ] }, `runtime-contract-${item.label}`)) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: effectiveRouteRows.length > 0 ? effectiveRouteRows.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: titleizeToken(item.role) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("strong", { children: [
              titleizeToken(item.provider),
              " \xB7 ",
              item.model
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
              titleizeToken(item.source || "profile_default"),
              item.effort ? ` \xB7 ${titleizeToken(item.effort)} effort` : "",
              item.budgetClass ? ` \xB7 ${titleizeToken(item.budgetClass)}` : ""
            ] }),
            item.reason ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.reason }) : null
          ] }, `route-contract-${item.role}`)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: "No effective route contract reported yet." }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Once the mission resolves planner, executor, and verifier routes, they will appear here." })
          ] }) })
        ] }) : null,
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Delegated runtime lanes" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: delegatedSessions.length > 0 ? delegatedSessions.map((session) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
            "article",
            {
              className: `drawer-card ${toneClass(session.heartbeat_status === "stale" ? "warn" : session.status === "failed" ? "bad" : "neutral")}`,
              children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: runtimeLabel(session.runtime_id) }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: titleizeToken(session.status || "unknown") }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: session.detail || session.last_event || "Delegated runtime lane is active." }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "pill-row", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill", children: session.heartbeat_status ? `Heartbeat ${titleizeToken(session.heartbeat_status)}` : "No heartbeat" }),
                  session.execution_target ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: titleizeToken(session.execution_target) }) : null,
                  typeof session.heartbeat_age_seconds === "number" ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                    session.heartbeat_age_seconds,
                    "s ago"
                  ] }) : null
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: session.execution_target_detail || session.execution_root || session.workspace_root || "Execution root not reported." }),
                Array.isArray(session.latest_events) && session.latest_events.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list compact runtime-event-mini-list", children: session.latest_events.slice(-3).reverse().map((event) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: titleizeToken(event.kind || "runtime") }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: event.message || "Runtime event" }),
                  event.status ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: titleizeToken(event.status) }) : null
                ] }, `runtime-event-${session.delegated_id}-${event.event_id || event.message}`)) }) : null
              ]
            },
            `delegated-session-${session.delegated_id}`
          )) : /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: "No delegated runtime lane is active." }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "When Hermes or OpenClaw is actively executing, heartbeat, last event, and execution target will show here." })
          ] }) })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Messaging and bridge surfaces" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: bridgeServices.length > 0 ? bridgeServices.map((service) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(service.tone)}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: service.category }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: service.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: service.status }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: service.details || "Bridge surface available." })
          ] }, `bridge-${service.serviceId}`)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: "Message bridge visibility is still partial." }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Telegram state is exposed today. iMessage and deeper mobile bridge specifics still need backend support before this shell can manage them honestly." })
          ] }) })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Connected apps and mobile bridges" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: bridgeSessions.length > 0 ? bridgeSessions.map((session) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(session.bridge_health === "healthy" ? "good" : "warn")}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: session.app_name || session.app_id }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("strong", { children: [
              titleizeToken(session.status || "unknown"),
              session.bridge_transport ? ` \xB7 ${titleizeToken(session.bridge_transport)}` : ""
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
              titleizeToken(session.bridge_health || "unknown"),
              " bridge health"
            ] }),
            Array.isArray(session.notes) && session.notes.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: session.notes[0] }) : null,
            Array.isArray(session.active_tasks) && session.active_tasks.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "pill-row", children: session.active_tasks.slice(0, 3).map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: item }, `bridge-task-${session.session_id}-${item}`)) }) : null
          ] }, `bridge-session-${session.session_id}`)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: "No connected app bridge is reporting yet." }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Bridge Lab data will appear here when connected apps expose live session or follow-on bridge state." })
          ] }) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "drawer-footnote", children: "OpenClaw still has the direct gateway, but Hermes supervision now lands in the same Agent conversation through control-room runtime events and delegated lane snapshots." })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Setup controls" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-actions", children: viewModel.drawers.builder.serviceStudio.services.flatMap(
            (service) => service.actions.slice(0, 1).map((action) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              ActionButton,
              {
                onClick: () => void runWorkspaceActionSpec(action),
                children: action.label
              },
              `${service.serviceId}-${action.actionId}-setup`
            ))
          ).slice(0, 4) })
        ] })
      ] });
    }
    if (activeDrawer === "profiles") {
      return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-panel", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: "Profiles and routing" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Shape workspace behavior, routing, and execution defaults from one profile surface." })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Workspace profile", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  userProfile: event.target.value
                })),
                value: workspaceProfileForm.userProfile,
                children: (snapshot.profiles?.availableProfiles || ["beginner", "builder", "advanced"]).map(
                  (option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option, children: titleizeToken(option) }, option)
                )
              }
            ) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Preferred harness", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  preferredHarness: event.target.value
                })),
                value: workspaceProfileForm.preferredHarness,
                children: PREFERRED_HARNESS_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value))
              }
            ) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Routing strategy", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  routingStrategy: event.target.value
                })),
                value: workspaceProfileForm.routingStrategy,
                children: ROUTING_STRATEGY_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value))
              }
            ) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Execution target", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  executionTargetPreference: event.target.value
                })),
                value: workspaceProfileForm.executionTargetPreference,
                children: EXECUTION_TARGET_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value))
              }
            ) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("label", { className: "check-field", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "input",
              {
                checked: workspaceProfileForm.autoOptimizeRouting,
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  autoOptimizeRouting: event.target.checked
                })),
                type: "checkbox"
              }
            ),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Enable deterministic routing auto-optimize when enough local runs exist." })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-actions", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void saveWorkspacePolicy(), variant: "primary", children: "Save profile policy" }) })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Current behavior" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list compact", children: viewModel.drawers.builder.profileStudio.behavior.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.value })
          ] }, `profile-surface-${item.label}`)) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "drawer-footnote", children: "Routing strategy is real and saved at workspace level. Builder now exposes per-role overrides for planner, executor, and verifier when you need to pin specific models." })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Per-role model routes" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "route-override-grid", children: workspaceProfileForm.routeOverrides.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card route-override-card", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: titleizeToken(item.role) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Provider", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "select",
                {
                  onChange: (event) => setWorkspaceProfileForm((current) => ({
                    ...current,
                    routeOverrides: current.routeOverrides.map(
                      (entry) => entry.role === item.role ? { ...entry, provider: event.target.value } : entry
                    )
                  })),
                  value: item.provider,
                  children: MODEL_PROVIDER_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, `${item.role}-${option.value}`))
                }
              ) }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Effort", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "select",
                {
                  onChange: (event) => setWorkspaceProfileForm((current) => ({
                    ...current,
                    routeOverrides: current.routeOverrides.map(
                      (entry) => entry.role === item.role ? { ...entry, effort: event.target.value } : entry
                    )
                  })),
                  value: item.effort,
                  children: MODEL_EFFORT_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, `${item.role}-${option.value}`))
                }
              ) })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Model", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "input",
              {
                list: `route-models-${item.role}`,
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  routeOverrides: current.routeOverrides.map(
                    (entry) => entry.role === item.role ? { ...entry, model: event.target.value } : entry
                  )
                })),
                placeholder: item.role === "executor" ? "gpt-5.4-mini" : "gpt-5.4",
                value: item.model
              }
            ) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("datalist", { id: `route-models-${item.role}`, children: ROUTE_MODEL_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option }, `${item.role}-${option}`)) })
          ] }, `route-override-${item.role}`)) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "drawer-footnote", children: "Leave a role blank to keep using the routing strategy default. Planner, executor, and verifier overrides are saved into workspace policy and forwarded to the harness." })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Available contracts" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: viewModel.drawers.builder.profileStudio.profileRows.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(item.tone)}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.description }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
              item.approval,
              " approvals \xB7 ",
              item.autonomy,
              " autonomy \xB7 ",
              item.visibility,
              " visibility"
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
              item.density,
              " density"
            ] })
          ] }, `profile-contract-${item.id}`)) })
        ] })
      ] });
    }
    if (activeDrawer === "settings") {
      return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-panel", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Settings" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: "Workspace and app controls" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Put operational settings here instead of scattering them across the shell." })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "App view" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Preview", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("select", { onChange: (event) => setPreviewMode(event.target.value), value: previewMode, children: FIXTURE_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.id, children: option.name }, option.id)) }) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Live sync", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("select", { onChange: (event) => setLiveSyncSeconds(event.target.value), value: liveSyncSeconds, children: LIVE_SYNC_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value)) }) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { className: "drawer-footnote", children: [
            previewLabel(previewMode, data.previewMeta),
            lastPushReason ? ` \xB7 Last push ${lastPushReason}` : ""
          ] })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Workspace defaults" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "context-grid", children: viewModel.drawers.builder.profileStudio.workspacePolicy.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.value })
          ] }, `settings-${item.label}`)) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-actions", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("builder"), variant: "primary", children: "Open builder controls" }) })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Escalation" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: data.telegramReady ? "Telegram ready" : "Telegram not configured" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setShowEscalationDialog(true), variant: "primary", children: "Configure" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleSendTestPing(), children: "Send test ping" })
          ] })
        ] })
      ] });
    }
    if (activeDrawer === "builder" && uiMode === "builder") {
      const skillQuery = skillStudioQuery.trim().toLowerCase();
      const skillMatchesQuery = (item) => !skillQuery || String(item?.label || "").toLowerCase().includes(skillQuery) || String(item?.description || "").toLowerCase().includes(skillQuery) || (item?.profileSuitability || []).some(
        (entry) => String(entry).toLowerCase().includes(skillQuery)
      );
      const matchesSkillFilter = (item) => {
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
        (item) => matchesSkillFilter(item) && skillMatchesQuery(item)
      );
      const filteredCuratedSkills = viewModel.drawers.builder.skillStudio.curated.filter(
        (item) => matchesSkillFilter(item) && skillMatchesQuery(item)
      );
      return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-panel", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: "Confidence and operations" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: viewModel.drawers.builder.liveSurface.note })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Confidence engine" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "confidence-headline", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { className: toneClass(viewModel.drawers.builder.confidence.tone), children: viewModel.drawers.builder.confidence.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: viewModel.drawers.builder.confidence.phase })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "confidence-meter", role: "presentation", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { style: { width: `${viewModel.drawers.builder.confidence.score}%` } }) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
            viewModel.drawers.builder.confidence.requiredGateSummary.label,
            ` \xB7 Quality ${viewModel.drawers.builder.confidence.qualityScore}%`,
            ` \xB7 Release ${viewModel.drawers.builder.confidence.releaseStatus}`
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "audit-list", children: viewModel.drawers.builder.confidence.milestones.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "audit-item", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
              item.percent,
              "% \xB7 ",
              item.detail
            ] })
          ] }, item.id)) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("ul", { children: viewModel.drawers.builder.confidence.nextActions.length > 0 ? viewModel.drawers.builder.confidence.nextActions.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: item }, `confidence-action-${item}`)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: "No blocking action reported." }) })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Road to 100%" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
            viewModel.drawers.builder.qualityRoadmap.headline,
            ` \xB7 Gap ${viewModel.drawers.builder.qualityRoadmap.gap}%`
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "roadmap-grid", children: viewModel.drawers.builder.qualityRoadmap.tracks.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `roadmap-item ${toneClass(item.tone)}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: titleizeToken(item.state) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.detail }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.hint }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-actions", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              ActionButton,
              {
                onClick: () => void handleQualityRoadmapAction(item),
                type: "button",
                children: item.suggestedAction || "Open"
              }
            ) })
          ] }, item.id)) })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Live surface" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Preview", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("select", { onChange: (event) => setPreviewMode(event.target.value), value: previewMode, children: FIXTURE_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.id, children: option.name }, option.id)) }) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Live sync", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
            "select",
            {
              onChange: (event) => setLiveSyncSeconds(event.target.value),
              value: liveSyncSeconds,
              children: LIVE_SYNC_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value))
            }
          ) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { className: "drawer-footnote", children: [
            previewLabel(previewMode, data.previewMeta),
            lastPushReason ? ` \xB7 Last push ${lastPushReason}` : ""
          ] })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Profile studio" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Workspace profile", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  userProfile: event.target.value
                })),
                value: workspaceProfileForm.userProfile,
                children: (snapshot.profiles?.availableProfiles || ["beginner", "builder", "advanced"]).map(
                  (option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option, children: titleizeToken(option) }, option)
                )
              }
            ) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Preferred harness", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  preferredHarness: event.target.value
                })),
                value: workspaceProfileForm.preferredHarness,
                children: PREFERRED_HARNESS_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value))
              }
            ) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Routing strategy", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  routingStrategy: event.target.value
                })),
                value: workspaceProfileForm.routingStrategy,
                children: ROUTING_STRATEGY_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value))
              }
            ) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Execution target", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  executionTargetPreference: event.target.value
                })),
                value: workspaceProfileForm.executionTargetPreference,
                children: EXECUTION_TARGET_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value))
              }
            ) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "OpenAI / Codex auth path", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  openaiCodexAuthMode: event.target.value
                })),
                value: workspaceProfileForm.openaiCodexAuthMode,
                children: OPENAI_CODEX_AUTH_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value))
              }
            ) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "MiniMax auth path", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "select",
              {
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  minimaxAuthMode: event.target.value
                })),
                value: workspaceProfileForm.minimaxAuthMode,
                children: MINIMAX_AUTH_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value))
              }
            ) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "field-row", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Commit message style", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
            "select",
            {
              onChange: (event) => setWorkspaceProfileForm((current) => ({
                ...current,
                commitMessageStyle: event.target.value
              })),
              value: workspaceProfileForm.commitMessageStyle,
              children: COMMIT_STYLE_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, option.value))
            }
          ) }) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("label", { className: "check-field", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "input",
              {
                checked: workspaceProfileForm.autoOptimizeRouting,
                onChange: (event) => setWorkspaceProfileForm((current) => ({
                  ...current,
                  autoOptimizeRouting: event.target.checked
                })),
                type: "checkbox"
              }
            ),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Enable deterministic routing auto-optimize when enough local runs exist." })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-actions", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void saveWorkspacePolicy(), variant: "primary", children: "Save workspace policy" }) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: viewModel.drawers.builder.profileStudio.behavior.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.value })
          ] }, `profile-behavior-${item.label}`)) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: "Available profile contracts" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: viewModel.drawers.builder.profileStudio.profileRows.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(item.tone)}`, children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.description }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
                item.approval,
                " approvals \xB7 ",
                item.autonomy,
                " autonomy \xB7 ",
                item.visibility,
                " visibility"
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
                item.density,
                " density"
              ] })
            ] }, item.id)) })
          ] })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Service management" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
            `${viewModel.drawers.builder.serviceStudio.summary.healthyCount}/${viewModel.drawers.builder.serviceStudio.summary.totalItems} healthy`,
            ` \xB7 ${viewModel.drawers.builder.serviceStudio.summary.needsAttentionCount} need attention`,
            ` \xB7 ${viewModel.drawers.builder.serviceStudio.availableActionCount} executable actions`
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: viewModel.drawers.builder.serviceStudio.services.map((service) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(service.tone)}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: service.category }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: service.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
              service.status,
              service.version ? ` \xB7 ${service.version}` : ""
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
              service.managementMode,
              service.required ? " \xB7 required" : " \xB7 optional"
            ] }),
            service.details ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: service.details }) : null,
            service.actions.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-actions", children: service.actions.slice(0, 3).map((action) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              ActionButton,
              {
                onClick: () => void runWorkspaceActionSpec(action),
                children: action.label
              },
              `${service.serviceId}-${action.actionId}`
            )) }) : null
          ] }, service.serviceId)) })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Skill studio" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
            `${viewModel.drawers.builder.skillStudio.summary.reviewedReusableCount}/${viewModel.drawers.builder.skillStudio.summary.totalSkills} reviewed reusable`,
            ` \xB7 ${viewModel.drawers.builder.skillStudio.summary.needsTestCount} need tests`,
            ` \xB7 ${viewModel.drawers.builder.skillStudio.summary.learnedCount} learned`
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
            `${viewModel.drawers.builder.skillStudio.summary.executionReadyCount} execution-ready`,
            ` \xB7 ${viewModel.drawers.builder.skillStudio.summary.installedCount} installed`,
            ` \xB7 ${viewModel.drawers.builder.skillStudio.summary.uniquePackCount} unique packs`
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "skill-toolbar", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Filter", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
              "select",
              {
                onChange: (event) => setSkillStudioFilter(event.target.value),
                value: skillStudioFilter,
                children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "all", children: "All packs" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "recommended", children: "Recommended only" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "installed", children: "Installed only" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "needs_attention", children: "Needs attention" })
                ]
              }
            ) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Search", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              "input",
              {
                onChange: (event) => setSkillStudioQuery(event.target.value),
                placeholder: "Search by pack or profile",
                value: skillStudioQuery
              }
            ) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "drawer-footnote", children: viewModel.drawers.builder.skillStudio.capabilitiesNote }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { open: true, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: "Recommended packs" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: filteredRecommendedSkills.length > 0 ? filteredRecommendedSkills.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(item.tone)}`, children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.originType }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.description }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
                item.status,
                item.installed ? " \xB7 installed" : " \xB7 not installed",
                item.executionCapable ? " \xB7 execution-capable" : " \xB7 guidance-only"
              ] }),
              item.profileSuitability?.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "pill-row", children: item.profileSuitability.map((entry) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill", children: entry }, `${item.id}-${entry}`)) }) : null,
              item.permissions?.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "pill-row", children: item.permissions.map((permission) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: permission }, `${item.id}-perm-${permission}`)) }) : null
            ] }, item.id)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("article", { className: "drawer-card", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: "No recommended pack matches this filter." }) }) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: "Curated inventory" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: filteredCuratedSkills.length > 0 ? filteredCuratedSkills.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(item.tone)}`, children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.originType }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
                item.status,
                item.installed ? " \xB7 installed" : " \xB7 not installed",
                item.executionCapable ? " \xB7 execution-capable" : " \xB7 guidance-only"
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
                "Used ",
                item.usageCount,
                " time(s) \xB7 Helped ",
                item.helpedCount,
                " run(s)"
              ] }),
              item.profileSuitability?.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "pill-row", children: item.profileSuitability.map((entry) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill", children: entry }, `${item.id}-${entry}`)) }) : null
            ] }, item.id)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("article", { className: "drawer-card", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: "No curated pack matches this filter." }) }) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: "Quality actions" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("ul", { children: viewModel.drawers.builder.skillStudio.nextQualityActions.length > 0 ? viewModel.drawers.builder.skillStudio.nextQualityActions.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: item }, `skill-next-${item}`)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: "Skill quality checklist is currently clear." }) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: "Profile coverage" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list compact", children: Object.entries(viewModel.drawers.builder.skillStudio.coverageByProfile).map(
              ([profile, count]) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "drawer-card", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: profile }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("strong", { children: [
                  count,
                  " suitable pack(s)"
                ] })
              ] }, `coverage-${profile}`)
            ) })
          ] })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Workflow studio" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
            `${viewModel.drawers.builder.workflowStudio.summary.reviewedCount}/${viewModel.drawers.builder.workflowStudio.summary.recipeCount} reviewed`,
            ` \xB7 ${viewModel.drawers.builder.workflowStudio.summary.blockedCount} blocked`,
            ` \xB7 Recommended mode ${viewModel.drawers.builder.workflowStudio.summary.recommendedMode}`
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: viewModel.drawers.builder.workflowStudio.recipes.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(item.tone)}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.surface }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.description }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { children: [
              item.status,
              " \xB7 ",
              item.audience,
              " \xB7 ",
              item.runtimeChoice
            ] }),
            item.verificationDefaults.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: `Default verification: ${item.verificationDefaults.join(" | ")}` }) : null
          ] }, item.workflowId)) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: "Learning queue" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("ul", { children: viewModel.drawers.builder.workflowStudio.learningQueue.length > 0 ? viewModel.drawers.builder.workflowStudio.learningQueue.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: listLabel2(item) }, `learning-${item}`)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: "No pending workflow learning item." }) })
          ] })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Repo operations" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: [...viewModel.drawers.builder.gitActions, ...viewModel.drawers.builder.validationActions].map(
            (action) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(action.tone)}`, children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: titleizeToken(action.surface) }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: action.label }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: action.detail }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-actions", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void runWorkspaceActionSpec(action), children: action.requiresApproval ? "Approve and run" : "Run action" }) })
            ] }, `${action.surface}-${action.actionId}`)
          ) })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Release gates" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-list", children: viewModel.drawers.builder.confidence.gates.length > 0 ? viewModel.drawers.builder.confidence.gates.map((gate) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `drawer-card ${toneClass(gate.tone)}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: gate.required ? "Required" : "Quality" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: gate.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: gate.details })
          ] }, gate.gateId)) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("article", { className: "drawer-card", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: "Release gates are not available yet." }) }) })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Feature truth" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { open: true, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: "Real and ready" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("ul", { children: viewModel.drawers.builder.featureTruth.realReady.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: item }, `ready-${item}`)) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: "Real but secondary" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("ul", { children: viewModel.drawers.builder.featureTruth.realSecondary.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: item }, `secondary-${item}`)) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: "Fixture and review only" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("ul", { children: viewModel.drawers.builder.featureTruth.fixtureOnly.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: item }, `fixture-${item}`)) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("details", { children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("summary", { children: "Not ready yet" }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("ul", { children: viewModel.drawers.builder.featureTruth.notReady.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: item }, `not-ready-${item}`)) })
          ] })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Core state audit" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "audit-list", children: viewModel.drawers.builder.stateAudit.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `audit-item state-${item.state}`, children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.nextAction })
          ] }, item.id)) })
        ] })
      ] });
    }
    return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-panel", children: [
      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Context" }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: "Operational context" }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Open only when you need runtime truth, guardrails, or escalation details." })
      ] }),
      viewModel.drawers.context.groups.map((group) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: group.title }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "context-grid", children: group.items.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "context-item", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.value }),
          item.note ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.note }) : null
        ] }, `${group.title}-${item.label}-${item.value}`)) })
      ] }, group.title)),
      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "drawer-block", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: "Escalation" }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: data.telegramReady ? "Telegram ready" : "Telegram not configured" }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setShowEscalationDialog(true), variant: "primary", children: "Configure" }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleSendTestPing(), children: "Send test ping" })
        ] })
      ] })
    ] });
  };
  return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
    "div",
    {
      className: "fluxio-shell",
      "data-drawer": showPersistentDrawer ? "open" : "collapsed",
      "data-mode": uiMode,
      "data-profile": profileId,
      children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { className: "fluxio-topbar", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "topbar-app", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "app-menu", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("button", { "aria-label": "Fluxio menu", className: "app-menu-glyph", type: "button", children: "+" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(MenuButton, { label: "File", onClick: () => setShowWorkspaceDialog(true) }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                MenuButton,
                {
                  label: "Edit",
                  onClick: () => {
                    if (workspaces.length === 0) {
                      setShowWorkspaceDialog(true);
                      return;
                    }
                    openMissionDialog();
                  }
                }
              ),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                MenuButton,
                {
                  label: "View",
                  onClick: () => {
                    setUiMode("builder");
                    setActiveDrawer("builder");
                  }
                }
              ),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                MenuButton,
                {
                  label: "Window",
                  onClick: () => {
                    setUiMode("builder");
                    setActiveDrawer("runtime");
                  }
                }
              ),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                MenuButton,
                {
                  label: "Help",
                  onClick: () => {
                    setUiMode("agent");
                    setActiveDrawer(agentBlockedState.defaultDrawer);
                  }
                }
              )
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "topbar-context", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: mission?.title || mission?.objective || workspace?.name || "Fluxio workspace" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: workspace?.name || "Select a workspace" })
            ] })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { "aria-label": "Fluxio mode", className: "fluxio-mode", role: "tablist", children: ["agent", "builder"].map((mode) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
            "button",
            {
              "aria-selected": uiMode === mode,
              className: uiMode === mode ? "active" : "",
              onClick: () => {
                markAction(`mode:${mode}`);
                setUiMode(mode);
                if (mode === "builder") {
                  setActiveDrawer(null);
                  return;
                }
                setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
              },
              role: "tab",
              type: "button",
              children: titleizeToken(mode)
            },
            mode
          )) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "topbar-shortcuts", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
            TopbarShortcut,
            {
              active: showPersistentDrawer,
              label: showPersistentDrawer && activeDrawerMeta ? `${activeDrawerMeta.label} panel` : "Open panel",
              onClick: () => {
                markAction("toggle:panel");
                if (uiMode === "builder") {
                  setActiveDrawer((current) => current ? null : "builder");
                  return;
                }
                if (agentBlockedState.isBlocked) {
                  setActiveDrawer(agentBlockedState.defaultDrawer);
                }
              },
              tone: "neutral"
            }
          ) }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "topbar-confidence", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: topbarStatus.label }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { className: toneClass(topbarStatus.tone), children: topbarStatus.value })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: handlePrimaryAction, variant: "primary", children: viewModel.topBar.primaryAction.label })
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-body", children: [
          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("aside", { className: "fluxio-sidebar", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-sidebar-scroll", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "sidebar-surface-list", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                  GlobalRailButton,
                  {
                    active: uiMode === "agent",
                    icon: "\u25CE",
                    label: "Agent",
                    onClick: () => {
                      markAction("rail:operator");
                      setUiMode("agent");
                      setActiveDrawer(agentBlockedState.isBlocked ? agentBlockedState.defaultDrawer : null);
                    }
                  }
                ),
                uiMode === "builder" ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(import_jsx_runtime2.Fragment, { children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    GlobalRailButton,
                    {
                      active: activeDrawer === "builder",
                      icon: "\u2318",
                      label: "Builder",
                      onClick: () => {
                        markAction("rail:builder");
                        setActiveDrawer((current) => current === "builder" ? null : "builder");
                      }
                    }
                  ),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    GlobalRailButton,
                    {
                      active: activeDrawer === "skills",
                      icon: "\u2726",
                      label: "Skills",
                      onClick: () => {
                        markAction("rail:skills");
                        setSkillStudioFilter("all");
                        setActiveDrawer((current) => current === "skills" ? null : "skills");
                      }
                    }
                  ),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    GlobalRailButton,
                    {
                      active: activeDrawer === "runtime",
                      icon: "\u25C7",
                      label: "Runtime",
                      onClick: () => {
                        markAction("rail:runtime");
                        setActiveDrawer((current) => current === "runtime" ? null : "runtime");
                      }
                    }
                  ),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    GlobalRailButton,
                    {
                      active: activeDrawer === "profiles",
                      icon: "\u25EB",
                      label: "Profiles",
                      onClick: () => {
                        markAction("rail:profiles");
                        setActiveDrawer((current) => current === "profiles" ? null : "profiles");
                      }
                    }
                  )
                ] }) : null
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "fluxio-nav-section", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "fluxio-nav-heading", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Quick controls" }) }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-nav-list", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    NavItem,
                    {
                      badge: previewMode === "live" ? "full" : "read-only",
                      context: previewMode === "live" ? "Live backend access is enabled." : "Fixture mode keeps actions read-only.",
                      icon: "\u26E8",
                      onClick: handleSidebarAccess,
                      subtitle: sidebarAccessLabel,
                      title: "Access",
                      tone: previewMode === "live" ? "good" : "warn"
                    }
                  ),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    NavItem,
                    {
                      badge: sidebarLocalLeaf,
                      context: sidebarLocalPath || "No workspace selected yet.",
                      icon: "\u2302",
                      onClick: handleSidebarLocal,
                      subtitle: workspace?.name || "Pick workspace",
                      title: "Local",
                      tone: workspace ? "good" : "warn"
                    }
                  ),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    NavItem,
                    {
                      badge: `${builderRootItems.length} root${builderRootItems.length === 1 ? "" : "s"}`,
                      context: builderPrimaryConversation?.executionPath || builderPrimaryConversation?.workspacePath || "Folder map appears once Builder has active conversations.",
                      icon: "\u{1F4C1}",
                      onClick: handleSidebarFolders,
                      subtitle: builderPrimaryConversation?.folderLabel || "Open folder map",
                      title: "Folders",
                      tone: builderRootItems.length > 0 ? "neutral" : "warn"
                    }
                  ),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    NavItem,
                    {
                      badge: sidebarBranchName,
                      context: sidebarBranchContext,
                      icon: "\u2442",
                      onClick: () => void handleSidebarBranch(),
                      subtitle: workspaceGitSnapshot?.repoDetected ? "Git branch controls" : "No git workspace",
                      title: "Branch",
                      tone: sidebarBranchTone
                    }
                  )
                ] }),
                workspaceGitSnapshot?.repoDetected ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-sidebar-branch-actions", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleSidebarBranch(), type: "button", children: "Inspect branch" }),
                  branchPullAction ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleSidebarBranchPull(), type: "button", children: "Pull" }) : null,
                  branchPushAction ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleSidebarBranchPush(), type: "button", children: "Push" }) : null
                ] }) : null
              ] }),
              uiMode === "builder" ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(import_jsx_runtime2.Fragment, { children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "fluxio-nav-section", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-nav-heading", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Board" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: openMissionDialog, children: "Launch" })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-sidebar-metrics", children: builderBoard.metrics.slice(0, 3).map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `builder-sidebar-card ${toneClass(item.tone)}`, children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.value }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.detail })
                  ] }, `builder-rail-${item.id}`)) })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "fluxio-nav-section", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "fluxio-nav-heading", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Roots" }) }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "fluxio-nav-list", children: builderRootItems.length > 0 ? builderRootItems.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    NavItem,
                    {
                      active: item.workspaceId === selectedWorkspaceId,
                      badge: item.folderLabel || "root",
                      context: item.path,
                      icon: "\u25A3",
                      onClick: () => setSelectedWorkspaceId(item.workspaceId),
                      stats: [
                        item.activeCount > 0 ? { label: "threads", value: item.activeCount, tone: "good" } : null,
                        item.blockedCount > 0 ? { label: "blocked", value: item.blockedCount, tone: "warn" } : null,
                        item.delegatedCount > 0 ? { label: "lanes", value: item.delegatedCount, tone: "good" } : null
                      ].filter(Boolean),
                      subtitle: item.activeCount > 0 ? "Conversation root" : "Workspace root",
                      title: item.title,
                      tone: item.tone
                    },
                    `builder-root-${item.workspaceId}`
                  )) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "fluxio-empty-copy", children: "Workspace roots will appear once Builder has projects to supervise." }) })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "fluxio-nav-section", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-nav-heading", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Nexuses" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("context"), children: "Open" })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-sidebar-nexus-list", children: builderNexusItems.length > 0 ? builderNexusItems.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                    "button",
                    {
                      className: `builder-sidebar-nexus ${toneClass(item.tone)}`.trim(),
                      onClick: () => {
                        if (item.missionId) {
                          setSelectedMissionId(item.missionId);
                        }
                        setActiveDrawer(item.tone === "bad" ? "proof" : "context");
                      },
                      type: "button",
                      children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.reason }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("em", { children: item.folderLabel || item.workspaceName })
                      ]
                    },
                    item.id
                  )) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "fluxio-empty-copy", children: "Important operator decisions will collect here." }) })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "fluxio-nav-section", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-nav-heading", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Bridge" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("runtime"), children: "Inspect" })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-sidebar-bridge", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Hermes \u2194 OpenClaw bridge" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("strong", { children: [
                      bridgeSummary.connected,
                      " live app bridge",
                      bridgeSummary.connected === 1 ? "" : "s"
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: bridgeSummary.recommendation }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-nav-stats", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "fluxio-nav-stat tone-good", children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: bridgeSummary.callbackReady }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("em", { children: "callbacks" })
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "fluxio-nav-stat tone-neutral", children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: bridgeSummary.totalApps }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("em", { children: "apps" })
                      ] })
                    ] })
                  ] })
                ] })
              ] }) : /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(import_jsx_runtime2.Fragment, { children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "fluxio-nav-section", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-nav-heading", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Workspaces" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setShowWorkspaceDialog(true), children: "Add" })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "fluxio-nav-list", children: workspaceNavItems.length > 0 ? workspaceNavItems.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    NavItem,
                    {
                      active: item.workspaceId === selectedWorkspaceId,
                      badge: item.badge,
                      context: item.context,
                      icon: "\u25A3",
                      onClick: () => setSelectedWorkspaceId(item.workspaceId),
                      stats: item.stats,
                      subtitle: item.subtitle,
                      title: item.title,
                      tone: item.tone
                    },
                    item.workspaceId
                  )) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "fluxio-empty-copy", children: "Add one workspace to begin." }) })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "fluxio-nav-section", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "fluxio-nav-heading", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Missions" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: openMissionDialog, children: "New" })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "fluxio-nav-list", children: missionOptions.length > 0 ? missionNavItems.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    NavItem,
                    {
                      active: item.missionId === selectedMissionId,
                      badge: item.badge,
                      context: item.context,
                      icon: "\u25C6",
                      onClick: () => setSelectedMissionId(item.missionId),
                      stats: item.stats,
                      subtitle: item.subtitle,
                      title: item.title,
                      tone: item.tone
                    },
                    item.missionId
                  )) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "fluxio-empty-copy", children: "Mission thread appears after first launch." }) })
                ] })
              ] })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "fluxio-sidebar-bottom", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
              GlobalRailButton,
              {
                active: activeDrawer === "settings",
                icon: "\u2699",
                label: "Settings",
                onClick: () => {
                  markAction("rail:settings");
                  setUiMode("builder");
                  setActiveDrawer("settings");
                },
                subtle: true
              }
            ) })
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("main", { className: "fluxio-main", children: !mission ? uiMode === "builder" ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "builder-shell builder-launch-shell", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { className: "builder-head builder-studio-head", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Builder workbench" }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h1", { children: viewModel.emptyState.title }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: viewModel.emptyState.summary })
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-head-actions", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                  ActionButton,
                  {
                    onClick: () => {
                      if (workspaces.length === 0) {
                        setShowWorkspaceDialog(true);
                        return;
                      }
                      openMissionDialog();
                    },
                    variant: "primary",
                    children: viewModel.emptyState.launchEntryLabel
                  }
                ),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => handleBuilderFeatureAction("open_builder"), children: "Open panel" })
              ] })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-workbench-grid", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "builder-primary-column", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-panel-hero builder-feature-card", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-head", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Guided tutorial" }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: tutorialStudio.headline })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-meta", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: tutorialStudio.progressLabel }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                        tutorialStudio.motionMode,
                        " motion"
                      ] })
                    ] })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: tutorialStudio.summary }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-step-grid", children: tutorialStudio.steps.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                    "button",
                    {
                      className: `builder-step-card ${toneClass(item.tone)} ${item.current ? "current" : ""}`.trim(),
                      onClick: () => void handleBuilderFeatureAction(item.actionId),
                      type: "button",
                      children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.panel }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.description }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("em", { children: item.status })
                      ]
                    },
                    item.id
                  )) }),
                  tutorialStudio.cards.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-inline-list builder-inline-list-actions", children: tutorialStudio.cards.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                    "button",
                    {
                      className: "builder-inline-action",
                      onClick: () => void handleBuilderFeatureAction(item.actionId),
                      type: "button",
                      children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.body })
                      ]
                    },
                    item.id
                  )) }) : null,
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                      ActionButton,
                      {
                        onClick: () => void handleBuilderFeatureAction(tutorialStudio.primaryActionId),
                        variant: "primary",
                        children: tutorialStudio.primaryActionLabel
                      }
                    ),
                    quickSetupActions.map((action) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                      ActionButton,
                      {
                        onClick: () => void runWorkspaceAction("setup", action.actionId),
                        children: action.label
                      },
                      `builder-empty-${action.actionId}`
                    ))
                  ] })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-grid", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-feature-card", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-head", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Recommendations" }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: recommendationStudio.headline })
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-feature-meta", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                        recommendationStudio.skillRecommendations.length,
                        " skill leads"
                      ] }) })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: recommendationStudio.summary }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-thread-list", children: recommendationStudio.struggleSignals.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                      "button",
                      {
                        className: `builder-thread-item ${toneClass(item.tone)}`.trim(),
                        onClick: () => void handleBuilderFeatureAction(item.actionId),
                        type: "button",
                        children: [
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.detail })
                        ]
                      },
                      item.id
                    )) }),
                    recommendationStudio.skillRecommendations.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-inline-list", children: recommendationStudio.skillRecommendations.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "builder-inline-pill", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.reason })
                    ] }, item.id)) }) : null,
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-actions", children: recommendationStudio.nextMoves.slice(0, 2).map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                      ActionButton,
                      {
                        onClick: () => void handleBuilderFeatureAction(item.actionId),
                        variant: item === recommendationStudio.nextMoves[0] ? "primary" : "secondary",
                        children: item.label
                      },
                      item.id
                    )) })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-feature-card", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-head", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Live UI review" }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: liveReviewStudio.statusLine })
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-feature-meta", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                        liveReviewStudio.targets.length,
                        " review blocks"
                      ] }) })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: liveReviewStudio.summary }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-review-grid", children: liveReviewStudio.targets.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                      "button",
                      {
                        className: `builder-review-target ${toneClass(item.tone)} ${builderSelectedReviewTarget?.id === item.id ? "active" : ""}`.trim(),
                        onClick: () => handleBuilderReviewTargetSeed(item),
                        type: "button",
                        children: [
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.detail })
                        ]
                      },
                      item.id
                    )) }),
                    builderSelectedReviewTarget ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `builder-review-focus ${toneClass(builderSelectedReviewTarget.tone)}`, children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: builderSelectedReviewTarget.label }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: builderSelectedReviewTarget.title }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: builderSelectedReviewTarget.detail })
                    ] }) : null,
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                        ActionButton,
                        {
                          onClick: () => builderSelectedReviewTarget && handleBuilderReviewTargetSeed(builderSelectedReviewTarget),
                          variant: "primary",
                          children: "Comment selected block"
                        }
                      ),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleBuilderFeatureAction("open_builder"), children: "Open preview controls" })
                    ] })
                  ] })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "section-header", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "section-title-block", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Road to 100%" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: viewModel.drawers.builder.qualityRoadmap.headline })
                  ] }) }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "roadmap-grid", children: viewModel.drawers.builder.qualityRoadmap.tracks.slice(0, 4).map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `roadmap-item ${toneClass(item.tone)}`, children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: titleizeToken(item.state) }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.detail }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleQualityRoadmapAction(item), children: item.suggestedAction || "Open" })
                  ] }, `empty-roadmap-${item.id}`)) })
                ] })
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("aside", { className: "builder-secondary-column", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-panel-focus", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Guided readiness" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: tutorialStudio.recommendedWorkflow }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: viewModel.emptyState.qualityRoadmapHeadline }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-inline-list", children: tutorialStudio.readiness.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item }, `readiness-${item}`)) })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-panel-focus", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Profiles" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: titleizeToken(workspaceProfileForm.userProfile) }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: viewModel.drawers.builder.profileStudio.behavior[0]?.value || "No profile selected." }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleBuilderFeatureAction("open_profiles"), children: "Open profiles" })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-panel-focus", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Feature backlog" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("h3", { children: [
                    tutorialStudio.improvements.length + recommendationStudio.learningQueue.length,
                    " queued improvement",
                    tutorialStudio.improvements.length + recommendationStudio.learningQueue.length === 1 ? "" : "s"
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-thread-list", children: [
                    tutorialStudio.improvements.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `builder-thread-item ${toneClass(item.tone)}`, children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.category }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.reason })
                    ] }, item.id)),
                    recommendationStudio.learningQueue.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `builder-thread-item ${toneClass(item.tone)}`, children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.priority }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Turn repeated friction into a reviewed skill or workflow." })
                    ] }, item.id))
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleBuilderFeatureAction("open_skills"), children: "Open improvement flow" })
                ] })
              ] })
            ] })
          ] }) : /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "thread-shell agent-shell agent-idle-shell", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("header", { className: "thread-head agent-thread-head agent-title-head", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h1", { children: agentCenterTitle }) }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
              "form",
              {
                className: "thread-composer agent-composer agent-chat-composer agent-idle-composer",
                onSubmit: (event) => event.preventDefault(),
                children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "agent-control-grid", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Launch runtime", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                      "select",
                      {
                        onChange: (event) => setMissionForm((current) => ({ ...current, runtime: event.target.value })),
                        value: missionForm.runtime,
                        children: runtimeOptions.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, `idle-runtime-${option.value}`))
                      }
                    ) }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Route role", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("select", { onChange: (event) => setAgentRouteRole(event.target.value), value: agentRouteRole, children: ROUTE_ROLE_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option, children: titleizeToken(option) }, `idle-role-${option}`)) }) }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Provider", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                      "select",
                      {
                        onChange: (event) => handleAgentRouteFieldChange("provider", event.target.value),
                        value: selectedAgentRoute.provider,
                        children: MODEL_PROVIDER_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, `idle-provider-${option.value}`))
                      }
                    ) }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(Field, { label: "Model", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                        "input",
                        {
                          list: "agent-route-models-idle",
                          onChange: (event) => handleAgentRouteFieldChange("model", event.target.value),
                          placeholder: "Profile default",
                          value: selectedAgentRoute.model
                        }
                      ),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("datalist", { id: "agent-route-models-idle", children: ROUTE_MODEL_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option }, `idle-model-${option}`)) })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Reasoning", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                      "select",
                      {
                        onChange: (event) => handleAgentRouteFieldChange("effort", event.target.value),
                        value: selectedAgentRoute.effort || "default",
                        children: MODEL_EFFORT_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, `idle-effort-${option.value}`))
                      }
                    ) })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "agent-control-strip", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: agentRuntimeHint }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "thread-chip-row", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: agentRouteStatus }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                        titleizeToken(agentRouteRole),
                        " route"
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                        "Code execution ",
                        codeExecutionEnabled ? "on" : "off"
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: openAICodexAuthReady ? "OpenAI auth ready" : "OpenAI auth missing" })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "thread-composer-actions", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleAgentRouteSave(), type: "button", children: "Apply route" }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                        ActionButton,
                        {
                          onClick: () => setCodeExecutionEnabled((current) => !current),
                          type: "button",
                          children: codeExecutionEnabled ? "Disable code execution" : "Enable code execution"
                        }
                      )
                    ] })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("label", { htmlFor: "thread-note-idle", children: agentComposerLabel }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    "textarea",
                    {
                      id: "thread-note-idle",
                      onChange: (event) => setOperatorDraft(event.target.value),
                      placeholder: agentComposerPlaceholder,
                      value: operatorDraft
                    }
                  ),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "thread-composer-actions", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: handleAgentIdlePrimaryAction, type: "button", variant: "primary", children: workspaces.length > 0 ? "Launch mission" : "Add workspace" }) })
                ]
              }
            )
          ] }) : uiMode === "builder" ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "builder-shell", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("header", { className: "builder-head builder-studio-head", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Conversation command board" }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h1", { children: viewModel.thread.title }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: builderBoard.summary })
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-head-actions", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("builder"), variant: "primary", children: "Open panel" }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: openMissionDialog, children: "Launch mission" })
              ] })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-workbench-grid", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "builder-primary-column", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-panel-hero builder-command-deck", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-command-head", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-command-copy", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: builderBoard.headline }),
                      builderPrimaryConversation ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(import_jsx_runtime2.Fragment, { children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "thread-chip-row", children: [
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(StatusPill, { tone: builderPrimaryConversation.blocked ? "warn" : builderPrimaryConversation.tone, children: builderPrimaryConversation.runtime }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(StatusPill, { tone: "neutral", children: builderPrimaryConversation.harnessLabel }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(StatusPill, { strong: true, tone: builderPrimaryConversation.blocked ? "warn" : builderPrimaryConversation.tone, children: builderPrimaryConversation.statusLabel })
                        ] }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: builderPrimaryConversation.title }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: builderPrimaryConversation.current }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { className: "builder-conversation-path", children: [
                          builderPrimaryConversation.workspaceName,
                          builderPrimaryConversation.executionPath ? ` \xB7 ${builderPrimaryConversation.executionPath}` : ""
                        ] }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-primary-summary", children: [
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-summary-card", children: [
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Current point" }),
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: builderPrimaryConversation.current }),
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: builderPrimaryConversation.lastMovement })
                          ] }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-summary-card", children: [
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Next step" }),
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: builderPrimaryConversation.next }),
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: builderPrimaryConversation.updatedAt ? `Updated ${timestampLabel(builderPrimaryConversation.updatedAt)}` : "Active now" })
                          ] })
                        ] })
                      ] }) : /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(import_jsx_runtime2.Fragment, { children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: viewModel.drawers.builder.confidence.label }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: builderBoard.summary })
                      ] })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-board-metrics", children: builderBoard.metrics.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `builder-metric-card ${toneClass(item.tone)}`, children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.value }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.detail })
                    ] }, item.id)) })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
                    builderPrimaryConversation ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setSelectedMissionId(builderPrimaryConversation.missionId), variant: "primary", children: "Focus thread" }) : null,
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("builder"), variant: "primary", children: "Command panel" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("queue"), children: "Queue review" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("proof"), children: "Proof review" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("context"), children: "Context" })
                  ] })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "section-header", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "section-title-block", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Other Active Conversations" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: "Smaller live threads around the main focus" })
                  ] }) }),
                  builderSecondaryConversations.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-conversation-grid", children: builderSecondaryConversations.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                    "button",
                    {
                      className: `builder-conversation-card ${toneClass(item.tone)} ${item.selected ? "active" : ""}`.trim(),
                      onClick: () => setSelectedMissionId(item.missionId),
                      type: "button",
                      children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-conversation-top", children: [
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { children: [
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { children: [
                              item.runtime,
                              " \xB7 ",
                              item.workspaceName
                            ] }),
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: item.title })
                          ] }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(StatusPill, { strong: true, tone: item.blocked ? "warn" : item.tone, children: item.statusLabel })
                        ] }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.current }),
                        item.executionPath ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { className: "builder-conversation-path", children: [
                          item.folderLabel ? `${item.folderLabel} \xB7 ` : "",
                          item.executionPath
                        ] }) : null,
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-conversation-meta", children: [
                          item.pendingApprovals > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { children: [
                            item.pendingApprovals,
                            " approval",
                            item.pendingApprovals === 1 ? "" : "s"
                          ] }) : null,
                          item.verificationFailures > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { children: [
                            item.verificationFailures,
                            " verification issue",
                            item.verificationFailures === 1 ? "" : "s"
                          ] }) : null,
                          item.delegatedSessions > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { children: [
                            item.delegatedSessions,
                            " delegated lane",
                            item.delegatedSessions === 1 ? "" : "s"
                          ] }) : null,
                          !item.pendingApprovals && !item.verificationFailures && !item.delegatedSessions ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "No active blocker" }) : null
                        ] }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-conversation-foot", children: [
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { children: [
                            "Next: ",
                            item.next
                          ] }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.updatedAt ? timestampLabel(item.updatedAt) : item.selected ? "Selected" : "Focus thread" })
                        ] })
                      ]
                    },
                    item.missionId
                  )) }) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "fluxio-empty-copy", children: builderPrimaryConversation ? "No secondary conversations are active right now." : "No active conversations yet. Launch a mission and Builder will track every live thread here." })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-grid", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-feature-card", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-head", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Guided tutorial" }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: tutorialStudio.headline })
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-meta", children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: tutorialStudio.progressLabel }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                          tutorialStudio.motionMode,
                          " motion"
                        ] })
                      ] })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: tutorialStudio.summary }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-step-grid compact", children: tutorialStudio.steps.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                      "button",
                      {
                        className: `builder-step-card ${toneClass(item.tone)} ${item.current ? "current" : ""}`.trim(),
                        onClick: () => void handleBuilderFeatureAction(item.actionId),
                        type: "button",
                        children: [
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.panel }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.description }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("em", { children: item.status })
                        ]
                      },
                      `builder-step-${item.id}`
                    )) }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                        ActionButton,
                        {
                          onClick: () => void handleBuilderFeatureAction(tutorialStudio.primaryActionId),
                          variant: "primary",
                          children: tutorialStudio.primaryActionLabel
                        }
                      ),
                      tutorialStudio.cards[0] ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                        ActionButton,
                        {
                          onClick: () => void handleBuilderFeatureAction(tutorialStudio.cards[0].actionId),
                          children: tutorialStudio.cards[0].title
                        }
                      ) : null
                    ] })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-feature-card", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-head", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Recommendations" }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: recommendationStudio.headline })
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-meta", children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                          recommendationStudio.blockedConversationCount,
                          " blocked"
                        ] }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                          recommendationStudio.skillRecommendations.length,
                          " skill leads"
                        ] })
                      ] })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: recommendationStudio.summary }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-thread-list", children: recommendationStudio.struggleSignals.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                      "button",
                      {
                        className: `builder-thread-item ${toneClass(item.tone)}`.trim(),
                        onClick: () => void handleBuilderFeatureAction(item.actionId),
                        type: "button",
                        children: [
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.detail })
                        ]
                      },
                      item.id
                    )) }),
                    recommendationStudio.skillRecommendations.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-inline-list", children: recommendationStudio.skillRecommendations.slice(0, 3).map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "builder-inline-pill", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.reason })
                    ] }, item.id)) }) : null,
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-actions", children: recommendationStudio.nextMoves.slice(0, 2).map((item, index) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                      ActionButton,
                      {
                        onClick: () => void handleBuilderFeatureAction(item.actionId),
                        variant: index === 0 ? "primary" : "ghost",
                        children: item.label
                      },
                      item.id
                    )) })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-feature-card builder-feature-card-wide", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-head", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Live UI review" }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: liveReviewStudio.statusLine })
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-feature-meta", children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                          liveReviewStudio.targets.length,
                          " review blocks"
                        ] }),
                        latestThinkingTurn ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                          latestThinkingTurn.roleLabel || "Runtime",
                          " trace live"
                        ] }) : null
                      ] })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: liveReviewStudio.summary }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-review-grid", children: liveReviewStudio.targets.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                      "button",
                      {
                        className: `builder-review-target ${toneClass(item.tone)} ${builderSelectedReviewTarget?.id === item.id ? "active" : ""}`.trim(),
                        onClick: () => handleBuilderReviewTargetSeed(item),
                        type: "button",
                        children: [
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.detail })
                        ]
                      },
                      item.id
                    )) }),
                    builderSelectedReviewTarget ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-review-lower", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `builder-review-focus ${toneClass(builderSelectedReviewTarget.tone)}`, children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: builderSelectedReviewTarget.label }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: builderSelectedReviewTarget.title }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: builderSelectedReviewTarget.detail })
                      ] }),
                      latestThinkingTurn ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-review-trace", children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { children: [
                          latestThinkingTurn.roleLabel || "Runtime",
                          " trace"
                        ] }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: latestThinkingTurn.title }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: latestThinkingTurn.detail })
                      ] }) : null
                    ] }) : null,
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "builder-review-hint", children: liveReviewStudio.compareHint }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                        ActionButton,
                        {
                          onClick: () => builderSelectedReviewTarget && handleBuilderReviewTargetSeed(builderSelectedReviewTarget),
                          variant: "primary",
                          children: "Comment selected block"
                        }
                      ),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleBuilderFeatureAction("open_builder"), children: "Open preview controls" }),
                      mission ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { disabled: !operatorDraft.trim(), onClick: () => void handleAgentFollowUp(), children: "Send to agent" }) : null
                    ] })
                  ] })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-board-grid", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "section-header", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "section-title-block", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "What Happens Next" }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: "Predicted checkpoints across live threads" })
                    ] }) }),
                    builderBoard.nextUp.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-digest-list", children: builderBoard.nextUp.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                      "button",
                      {
                        className: `builder-digest-item ${toneClass(item.tone)} ${item.selected ? "active" : ""}`.trim(),
                        onClick: () => setSelectedMissionId(item.missionId),
                        type: "button",
                        children: [
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-digest-top", children: [
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.runtime }),
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.updatedAt ? timestampLabel(item.updatedAt) : item.statusLabel })
                          ] }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.summary }),
                          item.checkpoint ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { className: "builder-digest-detail", children: [
                            "Checkpoint: ",
                            item.checkpoint
                          ] }) : null,
                          item.routeLabel ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { className: "builder-digest-detail", children: [
                            "Route: ",
                            item.routeLabel
                          ] }) : null,
                          item.detail ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "builder-digest-detail", children: item.detail }) : null,
                          /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-digest-meta", children: [
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.statusLabel }),
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.selected ? "Current thread" : "Open thread" })
                          ] })
                        ]
                      },
                      `next-${item.missionId}`
                    )) }) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "fluxio-empty-copy", children: "Launch a mission to see predicted checkpoints and queued follow-up work." })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "section-header", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "section-title-block", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "While You Were Away" }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: "Recent mission and runtime movement" })
                    ] }) }),
                    builderBoard.whileAway.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-digest-list", children: builderBoard.whileAway.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `builder-digest-item ${toneClass(item.tone)}`, children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-digest-top", children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.timestamp ? timestampLabel(item.timestamp) : "" })
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.missionTitle }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.message }),
                      item.detail ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "builder-digest-detail", children: item.detail }) : null
                    ] }, item.id)) }) : /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "fluxio-empty-copy", children: "Activity summaries will appear here as missions, approvals, and runtime events land." })
                  ] })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("form", { className: "builder-note-panel", onSubmit: handleOperatorNote, children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("label", { htmlFor: "builder-thread-note", children: builderSelectedReviewTarget ? `Review note for ${builderSelectedReviewTarget.title}` : "Builder note" }),
                  builderSelectedReviewTarget ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { className: "builder-note-context", children: [
                    builderSelectedReviewTarget.label,
                    " \xB7 ",
                    builderSelectedReviewTarget.detail
                  ] }) : null,
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                    "textarea",
                    {
                      id: "builder-thread-note",
                      onChange: (event) => setOperatorDraft(event.target.value),
                      placeholder: builderSelectedReviewTarget ? "Describe what is wrong with this block and what the model should change." : "Capture a technical observation, routing decision, or runtime intervention plan.",
                      value: operatorDraft
                    }
                  ),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "thread-composer-actions", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { type: "submit", variant: "primary", children: "Save note" }),
                    mission ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                      ActionButton,
                      {
                        disabled: !operatorDraft.trim(),
                        onClick: () => void handleAgentFollowUp(),
                        type: "button",
                        children: "Send to agent"
                      }
                    ) : null,
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("builder"), type: "button", children: "Open builder drawer" })
                  ] })
                ] })
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("aside", { className: "builder-secondary-column", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-panel-focus", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Nexuses" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("h3", { children: [
                    builderNexusItems.length,
                    " decision point",
                    builderNexusItems.length === 1 ? "" : "s"
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Jump back to the moments that most likely changed direction, risk, or final output." }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-thread-list", children: builderNexusItems.slice(0, 4).map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                    "button",
                    {
                      className: `builder-thread-item ${toneClass(item.tone)}`.trim(),
                      onClick: () => {
                        if (item.missionId) {
                          setSelectedMissionId(item.missionId);
                        }
                        setActiveDrawer(item.tone === "bad" ? "proof" : "context");
                      },
                      type: "button",
                      children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.reason })
                      ]
                    },
                    `nexus-${item.id}`
                  )) })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-panel-focus", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Runtime leaders" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("h3", { children: [
                    builderBoard.winningRoutes?.length || 0,
                    " active route pattern",
                    (builderBoard.winningRoutes?.length || 0) === 1 ? "" : "s"
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Builder tracks which runtime/provider/model combinations are clearing threads versus getting stuck." }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-thread-list", children: asList2(builderBoard.winningRoutes).slice(0, 3).map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `builder-thread-item ${toneClass(item.tone)}`, children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.runtime }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.label }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.detail })
                  ] }, `winning-route-${item.key || item.label}`)) }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "builder-thread-list", children: asList2(builderBoard.stuckThreads).slice(0, 3).map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                    "button",
                    {
                      className: `builder-thread-item ${toneClass(item.tone)}`.trim(),
                      onClick: () => item.missionId && setSelectedMissionId(item.missionId),
                      type: "button",
                      children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.blockerClass }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.reason })
                      ]
                    },
                    `stuck-${item.missionId || item.title}`
                  )) })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-panel-focus", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Harnesses" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h3", { children: titleizeToken(workspaceProfileForm.preferredHarness) }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-inline-list", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { children: [
                      "Production: ",
                      titleizeToken(snapshot.harnessLab?.productionHarness || workspaceProfileForm.preferredHarness)
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { children: [
                      "Shadow: ",
                      snapshot.harnessLab?.shadowCandidates?.length > 0 ? snapshot.harnessLab.shadowCandidates.map((item) => titleizeToken(item)).join(", ") : "None"
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: snapshot.harnessLab?.recommendation || "Builder keeps the production and shadow harnesses visible here." })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-actions", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void applyPreferredHarness("fluxio_hybrid"), variant: "primary", children: "Use Fluxio Hybrid" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void applyPreferredHarness("legacy_autonomous_engine"), children: "Use Legacy Harness" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("runtime"), type: "button", children: "Compare both" })
                  ] })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-panel-focus", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Runtime bridge" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("h3", { children: [
                    bridgeSummary.connected,
                    " live bridge",
                    bridgeSummary.connected === 1 ? "" : "s"
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: bridgeSummary.recommendation }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-inline-list", children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { children: [
                      bridgeSummary.callbackReady,
                      " approval callback",
                      bridgeSummary.callbackReady === 1 ? "" : "s",
                      " ready"
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { children: [
                      bridgeSummary.totalApps,
                      " connected app definition",
                      bridgeSummary.totalApps === 1 ? "" : "s"
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: "Use Builder to compare Hermes and OpenClaw bridge hand-offs." })
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer("runtime"), children: "Open runtime bridge" })
                ] }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: "builder-panel builder-panel-focus", children: [
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Feature backlog" }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("h3", { children: [
                    tutorialStudio.improvements.length + recommendationStudio.learningQueue.length,
                    " guided follow-up",
                    tutorialStudio.improvements.length + recommendationStudio.learningQueue.length === 1 ? "" : "s"
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Turn repeated friction into better defaults, stronger guidance, and reusable skill or workflow patterns." }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "builder-thread-list", children: [
                    tutorialStudio.improvements.slice(0, 2).map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `builder-thread-item ${toneClass(item.tone)}`, children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.category }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: item.reason })
                    ] }, item.id)),
                    recommendationStudio.learningQueue.slice(0, 2).map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("article", { className: `builder-thread-item ${toneClass(item.tone)}`, children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.priority }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: "Promote the pattern into Builder-visible guidance and reusable skill coverage." })
                    ] }, item.id))
                  ] }),
                  /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleBuilderFeatureAction("open_skills"), children: "Open skill studio" })
                ] })
              ] })
            ] })
          ] }) : /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "thread-shell agent-shell", children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("header", { className: "thread-head agent-thread-head agent-title-head", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h1", { children: agentCenterTitle }) }),
            agentNexusTurns.length > 0 ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "agent-nexus-strip", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "section-title-block", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: "Nexuses" }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { children: "Jump back to the decisions that changed the mission" })
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "agent-nexus-row", children: agentNexusTurns.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                "button",
                {
                  className: `agent-nexus-chip ${toneClass(item.tone || "neutral")} ${pinnedNexusIds.includes(item.id) ? "pinned" : ""}`.trim(),
                  onClick: () => focusTranscriptTurn(item.id),
                  type: "button",
                  children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: item.label || item.roleLabel || "Nexus" }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: item.title })
                  ]
                },
                `agent-nexus-${item.id}`
              )) })
            ] }) : null,
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: `agent-chat-stage ${agentIdleState === "no-turns" ? "agent-chat-stage-empty" : ""}`.trim(), children: [
              agentHasTurns ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("section", { className: "agent-transcript-shell", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "agent-transcript", children: agentVisibleTranscript.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                TranscriptMessage,
                {
                  highlighted: highlightedTurnId === item.id,
                  item,
                  onMemory: handleAgentMemoryFromTurn,
                  onPinNexus: togglePinnedNexus,
                  onSteer: handleAgentSteerFromTurn,
                  onValidate: handleAgentValidateTurn,
                  pinned: pinnedNexusIds.includes(item.id),
                  showTrace: showThinkingTrace
                },
                item.id
              )) }) }) : null,
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                "form",
                {
                  className: `thread-composer agent-composer agent-chat-composer ${agentIdleState === "no-turns" ? "agent-idle-composer" : ""}`.trim(),
                  onSubmit: (event) => event.preventDefault(),
                  children: [
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "agent-control-grid", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Runtime focus", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                        "select",
                        {
                          onChange: (event) => setAgentRuntimeFocus(event.target.value),
                          value: agentRuntimeSelectValue,
                          children: [
                            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "all", children: "All traces" }),
                            runtimeOptions.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, `agent-runtime-${option.value}`))
                          ]
                        }
                      ) }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Route role", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("select", { onChange: (event) => setAgentRouteRole(event.target.value), value: agentRouteRole, children: ROUTE_ROLE_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option, children: titleizeToken(option) }, `agent-role-${option}`)) }) }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Provider", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                        "select",
                        {
                          onChange: (event) => handleAgentRouteFieldChange("provider", event.target.value),
                          value: selectedAgentRoute.provider,
                          children: MODEL_PROVIDER_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, `agent-provider-${option.value}`))
                        }
                      ) }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(Field, { label: "Model", children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                          "input",
                          {
                            list: "agent-route-models-live",
                            onChange: (event) => handleAgentRouteFieldChange("model", event.target.value),
                            placeholder: "Profile default",
                            value: selectedAgentRoute.model
                          }
                        ),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("datalist", { id: "agent-route-models-live", children: ROUTE_MODEL_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option }, `agent-model-${option}`)) })
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Reasoning", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                        "select",
                        {
                          onChange: (event) => handleAgentRouteFieldChange("effort", event.target.value),
                          value: selectedAgentRoute.effort || "default",
                          children: MODEL_EFFORT_OPTIONS.map((option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option.value, children: option.label }, `agent-effort-${option.value}`))
                        }
                      ) })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "agent-control-strip", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { children: agentRuntimeHint }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "thread-chip-row", children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: agentRouteStatus }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                          titleizeToken(agentCyclePhase),
                          " phase via ",
                          titleizeToken(agentCycleRole)
                        ] }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: latestThinkingTurn ? `${latestThinkingTurn.roleLabel || "Runtime"} thinking` : mission?.state?.status === "running" ? "Awaiting the next runtime thought" : "No live thinking trace right now" }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                          agentThinkingTurns.length,
                          " trace moment",
                          agentThinkingTurns.length === 1 ? "" : "s"
                        ] }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "mini-pill muted", children: [
                          "Code execution ",
                          codeExecutionEnabled ? `on \xB7 ${codeExecutionMemory}` : "off"
                        ] }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "mini-pill muted", children: openAICodexAuthReady ? "OpenAI auth ready" : "OpenAI auth missing" })
                      ] }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "thread-composer-actions", children: [
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleAgentRouteSave(), type: "button", children: "Apply route" }),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                          ActionButton,
                          {
                            onClick: () => setCodeExecutionEnabled((current) => !current),
                            type: "button",
                            children: codeExecutionEnabled ? "Disable code execution" : "Enable code execution"
                          }
                        ),
                        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setShowThinkingTrace((current) => !current), type: "button", children: showThinkingTrace ? "Hide trace" : "Show trace" })
                      ] })
                    ] }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("label", { htmlFor: "thread-note", children: agentComposerLabel }),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                      "textarea",
                      {
                        id: "thread-note",
                        onChange: (event) => setOperatorDraft(event.target.value),
                        placeholder: agentComposerPlaceholder,
                        value: operatorDraft
                      }
                    ),
                    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "thread-composer-actions", children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => void handleAgentFollowUp(), type: "button", variant: "primary", children: "Send to agent" }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: handleOperatorNote, type: "button", children: "Save note" })
                    ] })
                  ]
                }
              )
            ] })
          ] }) }),
          showPersistentDrawer ? /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("aside", { className: `fluxio-drawer ${activeDrawer ? "open" : ""}`.trim(), children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "drawer-shell-head", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "eyebrow", children: uiMode === "builder" ? "Builder panel" : "Blocker panel" }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("strong", { children: activeDrawerMeta?.label || titleizeToken(activeDrawer || "panel") })
              ] }),
              uiMode === "builder" ? /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: () => setActiveDrawer(null), type: "button", children: "Close" }) : null
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "drawer-content", children: renderDrawerPanel() })
          ] }) : null
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
          Modal,
          {
            actions: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: handleWorkspaceSubmit, type: "submit", variant: "primary", children: "Save workspace" }),
            onClose: () => setShowWorkspaceDialog(false),
            open: showWorkspaceDialog,
            summary: "Workspace ownership stays in T3 shell state. Legacy shell no longer controls this flow.",
            title: "Add workspace",
            children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("form", { className: "dialog-form", onSubmit: handleWorkspaceSubmit, children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Workspace name", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "input",
                {
                  onChange: (event) => setWorkspaceForm((current) => ({ ...current, name: event.target.value })),
                  placeholder: "Fluxio Platform",
                  value: workspaceForm.name
                }
              ) }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Workspace path", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "input",
                {
                  onChange: (event) => setWorkspaceForm((current) => ({ ...current, path: event.target.value })),
                  placeholder: "C:/Users/paul/projects/vibe-coding-platform",
                  value: workspaceForm.path
                }
              ) }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Default runtime", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                  "select",
                  {
                    onChange: (event) => setWorkspaceForm((current) => ({
                      ...current,
                      defaultRuntime: event.target.value
                    })),
                    value: workspaceForm.defaultRuntime,
                    children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "openclaw", children: "OpenClaw" }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "hermes", children: "Hermes" })
                    ]
                  }
                ) }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Operator profile", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                  "select",
                  {
                    onChange: (event) => setWorkspaceForm((current) => ({ ...current, userProfile: event.target.value })),
                    value: workspaceForm.userProfile,
                    children: (snapshot.profiles?.availableProfiles || ["beginner", "builder", "advanced"]).map(
                      (option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option, children: titleizeToken(option) }, option)
                    )
                  }
                ) })
              ] })
            ] })
          }
        ),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
          Modal,
          {
            actions: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: handleMissionSubmit, type: "submit", variant: "primary", children: "Launch mission" }),
            onClose: () => setShowMissionDialog(false),
            open: showMissionDialog,
            summary: "Mission launch remains available, but operational clutter is removed from the top bar.",
            title: "Start mission",
            children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("form", { className: "dialog-form", onSubmit: handleMissionSubmit, children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Workspace", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                  "select",
                  {
                    onChange: (event) => setMissionForm((current) => ({ ...current, workspaceId: event.target.value })),
                    value: missionForm.workspaceId,
                    children: workspaces.map((item) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: item.workspace_id, children: item.name }, item.workspace_id))
                  }
                ) }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Runtime", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                  "select",
                  {
                    onChange: (event) => setMissionForm((current) => ({ ...current, runtime: event.target.value })),
                    value: missionForm.runtime,
                    children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "openclaw", children: "OpenClaw" }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "hermes", children: "Hermes" })
                    ]
                  }
                ) })
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Run mode", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                  "select",
                  {
                    onChange: (event) => setMissionForm((current) => ({ ...current, mode: event.target.value })),
                    value: missionForm.mode,
                    children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "Autopilot", children: "Autopilot" }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "Deep Run", children: "Deep Run" }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "Proof First", children: "Proof First" })
                    ]
                  }
                ) }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Profile", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                  "select",
                  {
                    onChange: (event) => setMissionForm((current) => ({ ...current, profile: event.target.value })),
                    value: missionForm.profile,
                    children: (snapshot.profiles?.availableProfiles || ["beginner", "builder", "advanced"]).map(
                      (option) => /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: option, children: titleizeToken(option) }, option)
                    )
                  }
                ) })
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "field-row", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Budget hours", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                  "input",
                  {
                    min: "1",
                    onChange: (event) => setMissionForm((current) => ({
                      ...current,
                      budgetHours: Number(event.target.value || 12)
                    })),
                    type: "number",
                    value: missionForm.budgetHours
                  }
                ) }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Run until", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
                  "select",
                  {
                    onChange: (event) => setMissionForm((current) => ({ ...current, runUntil: event.target.value })),
                    value: missionForm.runUntil,
                    children: [
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "pause_on_failure", children: "Pause on failure" }),
                      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("option", { value: "continue_until_blocked", children: "Continue until blocked" })
                    ]
                  }
                ) })
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Mission objective", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "textarea",
                {
                  onChange: (event) => setMissionForm((current) => ({ ...current, objective: event.target.value })),
                  placeholder: missionObjectivePlaceholder(missionForm.profile),
                  value: missionForm.objective
                }
              ) }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Success checks", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "textarea",
                {
                  onChange: (event) => setMissionForm((current) => ({ ...current, successChecks: event.target.value })),
                  placeholder: missionChecksPlaceholder(missionForm.profile),
                  value: missionForm.successChecks
                }
              ) })
            ] })
          }
        ),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
          Modal,
          {
            actions: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "inline-actions", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: handleClearTelegram, children: "Clear token" }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ActionButton, { onClick: handleSaveTelegram, type: "submit", variant: "primary", children: "Save escalation" })
            ] }),
            onClose: () => setShowEscalationDialog(false),
            open: showEscalationDialog,
            summary: "Escalation stays accessible, but only opens when the operator needs it.",
            title: "Configure Telegram escalation",
            children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("form", { className: "dialog-form", onSubmit: handleSaveTelegram, children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Telegram bot token", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "input",
                {
                  onChange: (event) => setTelegramBotToken(event.target.value),
                  placeholder: "123456:ABCDEF...",
                  type: "password",
                  value: telegramBotToken
                }
              ) }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(Field, { label: "Telegram chat ID", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "input",
                {
                  onChange: (event) => setTelegramChatId(event.target.value),
                  placeholder: "123456789",
                  value: telegramChatId
                }
              ) })
            ] })
          }
        ),
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(ToastHost, { items: toasts })
      ]
    }
  );
}
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  FluxioShellApp
});
