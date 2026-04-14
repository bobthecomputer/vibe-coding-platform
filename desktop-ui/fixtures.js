const now = '2026-04-14T10:30:00Z';

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

const profiles = {
  defaultProfile: 'builder',
  availableProfiles: ['beginner', 'builder', 'advanced', 'experimental'],
  details: {
    beginner: {
      description: 'Safer approvals, stronger explanations, and slower autonomy.',
      ui: { motion: 'reduced' },
      parameters: { profileName: 'beginner', autonomyLevel: 'guided', approvalStrictness: 'strict', verificationCadence: 'each_cycle', explanationLevel: 'high', explorationBreadth: 'bounded', autoContinueBehavior: 'pause_on_failure', gitActionPolicy: 'approval_gated', setupAutomationPolicy: 'installer_guided', learningAggressiveness: 'guarded', uiDensity: 'comfortable', visibilityLevel: 'guided' },
    },
    builder: {
      description: 'Balanced profile for autonomous delivery with guided control.',
      ui: { motion: 'standard' },
      parameters: { profileName: 'builder', autonomyLevel: 'balanced', approvalStrictness: 'tiered', verificationCadence: 'each_cycle', explanationLevel: 'medium', explorationBreadth: 'bounded', autoContinueBehavior: 'pause_on_failure', gitActionPolicy: 'approval_gated', setupAutomationPolicy: 'repair_and_verify', learningAggressiveness: 'bounded', uiDensity: 'comfortable', visibilityLevel: 'balanced' },
    },
    advanced: {
      description: 'Concise, higher-autonomy profile for experienced builders.',
      ui: { motion: 'standard' },
      parameters: { profileName: 'advanced', autonomyLevel: 'high', approvalStrictness: 'tiered', verificationCadence: 'continuous_until_blocked', explanationLevel: 'low', explorationBreadth: 'wide', autoContinueBehavior: 'continue_until_blocked', gitActionPolicy: 'approval_gated', setupAutomationPolicy: 'repair_and_verify', learningAggressiveness: 'bounded', uiDensity: 'comfortable', visibilityLevel: 'detailed' },
    },
    experimental: {
      description: 'Broad autonomy, wider experimentation, and faster iteration.',
      ui: { motion: 'standard' },
      parameters: { profileName: 'experimental', autonomyLevel: 'maximum', approvalStrictness: 'hands_free', verificationCadence: 'continuous_until_blocked', explanationLevel: 'low', explorationBreadth: 'wide', autoContinueBehavior: 'continue_until_blocked', gitActionPolicy: 'profile_resolved', setupAutomationPolicy: 'repair_and_verify', learningAggressiveness: 'aggressive', uiDensity: 'comfortable', visibilityLevel: 'expert' },
    },
  },
};

const baseSnapshot = {
  workspaceRoot: 'C:/Users/paul/Projects/vibe-coding-platform',
  ui: {
    uiMode: 'agent',
    defaultMode: 'agent',
    availableModes: ['agent', 'builder'],
    layout: 't3_workbench',
    sharedMissionState: true,
  },
  workspaces: [
    {
      workspace_id: 'workspace_primary',
      name: 'Fluxio Platform',
      root_path: 'C:/Users/paul/Projects/vibe-coding-platform',
      default_runtime: 'openclaw',
      workspace_type: 'tauri-python',
      user_profile: 'builder',
      runtimeStatus: { detected: true },
      gitSnapshot: {
        repoDetected: true,
        branch: 'main',
        trackingBranch: 'origin/main',
        dirty: true,
        stagedCount: 2,
        unstagedCount: 1,
        untrackedCount: 0,
        ahead: 1,
        behind: 0,
        remotes: [{ name: 'origin', url: 'git@github.com:paul/vibe-coding-platform.git' }],
        deployTarget: {
          provider: 'github_pages',
          available: true,
          configured: false,
          requiresApproval: true,
          detail: 'GitHub remote detected. Pages can be scaffolded after explicit approval.',
        },
        detail: 'main · dirty · 1 remote(s)',
      },
      gitActions: [
        { actionId: 'inspect_repo_state', label: 'Inspect repository state', command: 'git status --short --branch', commandSurface: 'git.inspect', requiresApproval: false, detail: 'Review branch, changes, and ahead/behind before mutating actions.' },
        { actionId: 'push_branch', label: 'Push current branch', command: 'git push', commandSurface: 'git.push', requiresApproval: true, detail: 'Policy-resolved push action. Approval stays on by default.' },
        { actionId: 'deploy_pages', label: 'Publish deploy target', command: 'git push origin HEAD', commandSurface: 'deploy.pages', requiresApproval: true, detail: 'GitHub remote detected. Pages can be scaffolded after explicit approval.' },
      ],
      workspaceActionHistory: [],
      profileParameters: {
        profileName: 'builder',
        autonomyLevel: 'balanced',
        approvalStrictness: 'tiered',
        verificationCadence: 'each_cycle',
        explanationLevel: 'medium',
        explorationBreadth: 'bounded',
        autoContinueBehavior: 'pause_on_failure',
        gitActionPolicy: 'approval_gated',
        setupAutomationPolicy: 'repair_and_verify',
        learningAggressiveness: 'bounded',
        uiDensity: 'comfortable',
        visibilityLevel: 'balanced',
      },
      skillRecommendations: [
        { label: 'Repo Scan', reason: 'Ground planning in the actual repo.' },
        { label: 'Frontend Proof', reason: 'Track UI regressions and screenshots.' },
      ],
      integrationRecommendations: [
        { label: 'Filesystem MCP', reason: 'Safe workspace inspection.', command: 'npx @modelcontextprotocol/server-filesystem .' },
        { label: 'Playwright MCP', reason: 'Visual proof and smoke tests.', command: 'npx @playwright/mcp@latest' },
      ],
    },
  ],
  missions: [],
  runtimes: [
    {
      runtime_id: 'openclaw',
      label: 'OpenClaw',
      detected: true,
      doctor_summary: 'Ready for delegated execution.',
      install_hint: '',
      capabilities: [{ label: 'Remote approvals' }, { label: 'Skills' }],
    },
    {
      runtime_id: 'hermes',
      label: 'Hermes',
      detected: true,
      doctor_summary: 'Ready for long-horizon delegated work.',
      install_hint: '',
      capabilities: [{ label: 'Delegation' }, { label: 'Skills and memory' }],
    },
  ],
  activity: [
    { kind: 'mission.runtime_cycle', message: 'OpenClaw control cycle finished with status running.', timestamp: now },
    { kind: 'approval.request', message: 'Delegated runtime requested approval for deploy simulation.', timestamp: now },
  ],
  inbox: [],
  onboarding: {
    tutorial: {
      selectedProfile: 'builder',
      completedSteps: ['detect_environment', 'choose_profile', 'add_workspace'],
      currentStepId: 'launch_mission',
      isComplete: false,
      steps: [
        { step_id: 'detect_environment', title: 'Check local setup', description: 'Verify runtimes and tooling.', status: 'pending', panel: 'Setup' },
        { step_id: 'choose_profile', title: 'Choose a guided profile', description: 'Set safe defaults.', status: 'completed', panel: 'Guidance' },
        { step_id: 'add_workspace', title: 'Add a workspace', description: 'Register a project.', status: 'completed', panel: 'Projects' },
        { step_id: 'launch_mission', title: 'Launch a mission', description: 'Start a real loop.', status: 'pending', panel: 'Missions' },
      ],
    },
    profileChoices: [],
    checks: {
      node: { installed: true, version: 'v24.2.0' },
      python: { installed: true, version: '3.13.2' },
      uv: { installed: true, version: '0.7.20' },
      openclaw: { installed: true, version: '2026.4.14' },
      hermes: { installed: true, version: 'v0.9.0' },
    },
    wsl: { installed: true, details: 'WSL2 detected and ready.' },
    nextActions: ['Launch a first mission to unlock the planner timeline and proof surfaces.', 'Configure Telegram escalation before long unattended runs.', 'Review runtime lanes and connected app bridges in Builder after launch.'],
  },
  guidance: {
    profileChoices: [
      { name: 'beginner', description: 'Safer approvals and richer teaching.', executionScope: 'isolated', approvalMode: 'strict', motion: 'reduced' },
      { name: 'builder', description: 'Balanced autonomy and clarity.', executionScope: 'isolated', approvalMode: 'tiered', motion: 'standard' },
      { name: 'advanced', description: 'Faster autonomy with less guidance.', executionScope: 'isolated', approvalMode: 'tiered', motion: 'standard' },
      { name: 'experimental', description: 'Broader experimentation and autonomy.', executionScope: 'isolated', approvalMode: 'hands_free', motion: 'standard' },
    ],
    guidanceCards: [
      { card_id: 'guide_launch', title: 'Run a first mission', body: 'The planner and proof feed become much clearer after one real mission cycle.', kind: 'mission', panel: 'Missions' },
      { card_id: 'guide_phone', title: 'Enable phone escalation', body: 'Configure Telegram before long unattended runs.', kind: 'integration', panel: 'Integrations' },
    ],
    productImprovements: [
      { item_id: 'pi_1', title: 'Improve approval handoff language', reason: 'Operators still hesitate on delegated approvals.', priority: 'high', category: 'ux' },
      { item_id: 'pi_2', title: 'Add screenshot proof lane', reason: 'UI review still lacks a native visual check surface.', priority: 'medium', category: 'proof' },
    ],
  },
  profiles,
  setupHealth: {
    installState: 'missing',
    environmentReady: true,
    installerReady: true,
    firstMissionLaunched: false,
    telegramReady: false,
    missingDependencies: ['First guided mission'],
    dependencies: [
      { dependencyId: 'wsl2', label: 'WSL2', category: 'platform', required: true, installed: true, version: 'WSL2', details: 'WSL2 detected and ready.', repairActions: [], latestAction: {}, stage: 'healthy', blocked: false },
      { dependencyId: 'node', label: 'Node', category: 'runtime', required: true, installed: true, version: 'v24.2.0', details: 'Installed and reachable.', repairActions: [], latestAction: {}, stage: 'healthy', blocked: false },
      { dependencyId: 'python', label: 'Python', category: 'runtime', required: true, installed: true, version: '3.13.2', details: 'Installed and reachable.', repairActions: [], latestAction: {}, stage: 'healthy', blocked: false },
      { dependencyId: 'uv', label: 'uv', category: 'tooling', required: true, installed: true, version: '0.7.20', details: 'Installed and reachable.', repairActions: [], latestAction: {}, stage: 'healthy', blocked: false },
      { dependencyId: 'openclaw', label: 'OpenClaw', category: 'agent_runtime', required: true, installed: true, version: '2026.4.14', details: 'Installed and verified against the latest npm release.', repairActions: [], latestAction: {}, stage: 'healthy', blocked: false },
      { dependencyId: 'hermes', label: 'Hermes', category: 'agent_runtime', required: true, installed: true, version: 'v0.9.0', details: 'Installed in WSL2 and verified against the latest upstream release.', repairActions: [], latestAction: {}, stage: 'healthy', blocked: false },
      { dependencyId: 'tauri_prereqs', label: 'Tauri prerequisites', category: 'desktop', required: false, installed: true, version: 'stable', details: 'Rust and Cargo are available for Tauri builds.', repairActions: [], latestAction: {}, stage: 'healthy', blocked: false },
      { dependencyId: 'telegram_ready', label: 'Telegram escalation', category: 'readiness', required: false, installed: false, version: '', details: 'Add a Telegram destination so long unattended runs can escalate approvals.', repairActions: [], latestAction: {}, stage: 'missing', blocked: false },
      { dependencyId: 'guided_mission', label: 'First guided mission', category: 'readiness', required: true, installed: false, version: '', details: 'Finish setup by launching one real guided mission from Fluxio.', repairActions: [], latestAction: {}, stage: 'missing', blocked: true },
    ],
    repairActions: [],
    globalActions: [
      {
        actionId: 'verify_setup_health',
        label: 'Verify setup health',
        description: 'Re-check local dependencies, runtimes, and blockers after a repair.',
        commandSurface: 'setup.verify',
      },
    ],
    actionHistory: [],
    actionHistoryByDependency: {},
    blockerExplanations: ['Launch one real guided mission from Fluxio.'],
  },
  skillLibrary: {
    recommendedPacks: [{ label: 'Repo Scan', execution_capable: true }],
    curatedPacks: [{ label: 'Verification Suite', execution_capable: false }],
    userInstalledSkills: [],
    learnedSkills: [{ label: 'Approval Recovery Pattern', execution_capable: false }],
  },
  workflowStudio: {
    recommendedMode: 'agent',
    recipes: [
      { workflowId: 'agent_long_run', label: 'Long-Run Agent Session', description: 'Leave Fluxio to plan, execute, verify, and replan over many hours with approvals and proof kept visible.', status: 'ready', audience: 'all', surface: 'agent_view' },
      { workflowId: 'ui_review_loop', label: 'Live UI Review Loop', description: 'Use HMR, fixtures, proof, and replay-ready states while refining the desktop workbench.', status: 'ready', audience: 'builder', surface: 'builder_view' },
      { workflowId: 'safe_git_push', label: 'Safe Push Or Deploy', description: 'Inspect repo truth first, then offer profile-resolved push and GitHub Pages actions with approvals.', status: 'ready', audience: 'advanced', surface: 'builder_view' },
      { workflowId: 'skill_authoring', label: 'Skill And Workflow Authoring', description: 'Create a new skill or workflow recipe, test it locally, and keep it reviewable inside Fluxio.', status: 'ready', audience: 'builder', surface: 'skill_studio' },
    ],
    learningQueue: [{ title: 'Promote approval recovery pattern', priority: 'medium' }],
  },
  harnessLab: {
    productionHarness: 'fluxio_hybrid',
    shadowCandidates: ['legacy_autonomous_engine'],
    recentRuns: [
      { sessionId: 'session_aa12', harnessId: 'fluxio_hybrid', runtimeId: 'openclaw', autopilotStatus: 'running', pauseReason: '' },
      { sessionId: 'session_bb34', harnessId: 'legacy_autonomous_engine', runtimeId: 'openclaw', autopilotStatus: 'completed', pauseReason: '' },
    ],
    recommendation: 'Fluxio hybrid harness is active; keep shadow comparisons visible.',
  },
  bridgeLab: {
    schemaVersion: 'fluxio.app-capability/v0-draft',
    recommendation: 'OratioViva and Mind Tower are live reference integrations. Solantir remains in manifest-only follow-on review.',
    phases: [
      'Phase A: manifest and policy contract',
      'Phase B: live reference integrations for OratioViva and Mind Tower',
      'Phase C: Solantir follow-on after the bridge standard is proven',
    ],
    discoveredApps: [
      {
        name: 'Oratio Viva',
        description: 'Speech workflows exposed through a local bridge.',
        bridge: { transport: 'http' },
        permissions: ['task.run', 'context.read', 'action.invoke'],
        tasks: [{ label: 'Render voice preview' }],
      },
      {
        name: 'Mind Tower',
        description: 'Monitoring and digest workflows exposed through a local bridge.',
        bridge: { transport: 'http' },
        permissions: ['task.run', 'context.read', 'approval.callback'],
        tasks: [{ label: 'Run monitoring digest' }],
      },
      {
        name: 'Solantir Terminal',
        description: 'Operator dashboard surfaces exposed through IPC.',
        bridge: { transport: 'ipc' },
        permissions: ['task.run', 'context.read', 'approval.request'],
        tasks: [{ label: 'Refresh watchlist' }],
      },
    ],
    connectedSessions: [
      {
        session_id: 'bridge_oratio_viva',
        app_id: 'oratio-viva',
        app_name: 'Oratio Viva',
        status: 'connected',
        bridge_health: 'healthy',
        handshake_status: 'connected',
        bridge_transport: 'http',
        active_tasks: [],
        context_preview: [{ summary: '3 voice engines detected in oratio-viva-ui 0.1.0' }],
        latest_task_result: {
          label: 'Render voice preview',
          resultSummary: 'Queued and completed a local preview bridge task for the dia2 voice engine.',
        },
        granted_capabilities: [
          { capability_key: 'task.run', status: 'granted' },
          { capability_key: 'context.read', status: 'granted' },
        ],
        notes: ['Bridge session is live and available for follow-on orchestration.'],
        last_seen_at: now,
      },
      {
        session_id: 'bridge_mind_tower',
        app_id: 'mind-tower',
        app_name: 'Mind Tower',
        status: 'connected',
        bridge_health: 'healthy',
        handshake_status: 'connected',
        bridge_transport: 'http',
        active_tasks: [],
        context_preview: [{ summary: '42 admin files and 2 service modules detected.' }],
        latest_task_result: {
          label: 'Run monitoring digest',
          resultSummary: 'Ran the local monitoring digest bridge task and captured session proof.',
        },
        approval_callback: {
          detail: 'Telegram listener detected for escalation-aware callback handling.',
        },
        granted_capabilities: [
          { capability_key: 'task.run', status: 'granted' },
          { capability_key: 'context.read', status: 'granted' },
          { capability_key: 'approval.callback', status: 'review' },
        ],
        notes: ['Bridge session is healthy and can push approval-aware follow-ups.'],
        last_seen_at: now,
      },
      {
        session_id: 'bridge_solantir_terminal',
        app_id: 'solantir-terminal',
        app_name: 'Solantir Terminal',
        status: 'follow_on_manifest',
        bridge_health: 'manifest_only',
        handshake_status: 'manifest_loaded',
        bridge_transport: 'ipc',
        active_tasks: [],
        latest_task_result: {
          label: 'Refresh watchlist',
          resultSummary: 'Solantir stays in follow-on review for the first post-1.0 bridge activation.',
        },
        granted_capabilities: [
          { capability_key: 'task.run', status: 'granted' },
          { capability_key: 'context.read', status: 'granted' },
          { capability_key: 'approval.request', status: 'review' },
        ],
        notes: ['Still held in manifest-only follow-on review.'],
        last_seen_at: now,
      },
    ],
  },
};

baseSnapshot.workspaces[0].serviceManagement = [
  {
    serviceId: 'wsl2',
    label: 'WSL2',
    serviceCategory: 'runtime_substrate',
    installSource: 'windows_feature',
    currentHealthStatus: 'healthy',
    lastVerificationResult: 'passed',
    lastRepairAction: {},
    managementMode: 'fluxio_managed',
    version: 'WSL2',
    details: 'WSL2 detected and ready.',
  },
  {
    serviceId: 'openclaw',
    label: 'OpenClaw',
    serviceCategory: 'runtime',
    installSource: 'npm',
    currentHealthStatus: 'healthy',
    lastVerificationResult: 'passed',
    lastRepairAction: {},
    managementMode: 'fluxio_managed',
    version: '2026.4.14',
    details: 'Installed and aligned with the latest npm release.',
  },
  {
    serviceId: 'hermes',
    label: 'Hermes',
    serviceCategory: 'runtime',
    installSource: 'wsl_script',
    currentHealthStatus: 'healthy',
    lastVerificationResult: 'passed',
    lastRepairAction: {},
    managementMode: 'fluxio_managed',
    version: 'v0.9.0',
    details: 'Installed in WSL2 and aligned with the latest upstream release.',
  },
  {
    serviceId: 'filesystem_mcp',
    label: 'Filesystem MCP',
    serviceCategory: 'mcp_tool_server',
    installSource: 'npx @modelcontextprotocol/server-filesystem .',
    currentHealthStatus: 'recommended',
    lastVerificationResult: 'not_run',
    lastRepairAction: {},
    managementMode: 'fluxio_managed',
    version: '',
    details: 'Safe workspace inspection.',
  },
  {
    serviceId: 'mind-tower',
    label: 'Mind Tower',
    serviceCategory: 'connected_app_bridge',
    installSource: 'http',
    currentHealthStatus: 'healthy',
    lastVerificationResult: 'passed',
    lastRepairAction: {},
    managementMode: 'externally_managed',
    version: '',
    details: 'Monitoring bridge connected and verified.',
  },
];
baseSnapshot.workspaces[0].serviceManagementSummary = {
  totalItems: 5,
  healthyCount: 4,
  needsAttentionCount: 1,
  runtimeCount: 2,
  toolServerCount: 1,
  bridgeCount: 1,
};
baseSnapshot.setupHealth.serviceManagement = [
  {
    serviceId: 'wsl2',
    label: 'WSL2',
    serviceCategory: 'runtime_substrate',
    installSource: 'windows_feature',
    currentHealthStatus: 'healthy',
    lastVerificationResult: 'passed',
    lastRepairAction: {},
    managementMode: 'fluxio_managed',
    version: 'WSL2',
    details: 'WSL2 detected and ready.',
    required: true,
  },
  {
    serviceId: 'uv',
    label: 'uv',
    serviceCategory: 'tooling',
    installSource: 'winget',
    currentHealthStatus: 'healthy',
    lastVerificationResult: 'passed',
    lastRepairAction: {},
    managementMode: 'fluxio_managed',
    version: '0.7.20',
    details: 'Installed and reachable.',
    required: true,
  },
  {
    serviceId: 'openclaw',
    label: 'OpenClaw',
    serviceCategory: 'runtime',
    installSource: 'npm',
    currentHealthStatus: 'healthy',
    lastVerificationResult: 'passed',
    lastRepairAction: {},
    managementMode: 'fluxio_managed',
    version: '2026.4.14',
    details: 'Installed and aligned with the latest npm release.',
    required: true,
  },
  {
    serviceId: 'hermes',
    label: 'Hermes',
    serviceCategory: 'runtime',
    installSource: 'wsl_script',
    currentHealthStatus: 'healthy',
    lastVerificationResult: 'passed',
    lastRepairAction: {},
    managementMode: 'fluxio_managed',
    version: 'v0.9.0',
    details: 'Installed in WSL2 and aligned with the latest upstream release.',
    required: true,
  },
  {
    serviceId: 'telegram_ready',
    label: 'Telegram escalation',
    serviceCategory: 'connected_app_bridge',
    installSource: 'telegram_destination',
    currentHealthStatus: 'missing',
    lastVerificationResult: 'blocked',
    lastRepairAction: {},
    managementMode: 'fluxio_managed',
    version: '',
    details: 'Add a Telegram destination so long unattended runs can escalate approvals.',
    required: false,
  },
];
baseSnapshot.setupHealth.serviceManagementSummary = {
  totalItems: 5,
  healthyCount: 4,
  needsAttentionCount: 1,
  fluxioManagedCount: 5,
  externalCount: 0,
};
baseSnapshot.skillLibrary.managementSummary = {
  totalSkills: 4,
  needsTestCount: 2,
  reviewedReusableCount: 1,
  learnedCount: 1,
  disabledCount: 0,
};
baseSnapshot.skillLibrary.recommendedPacks = [
  {
    label: 'Repo Scan',
    execution_capable: true,
    originType: 'curated',
    editableStatus: 'available',
    testStatus: 'recommended',
    promotionState: 'recommended',
    lastUsedAt: null,
    lastHelpedAt: null,
  },
];
baseSnapshot.skillLibrary.curatedPacks = [
  {
    label: 'Verification Suite',
    execution_capable: false,
    originType: 'curated',
    editableStatus: 'active',
    testStatus: 'reviewed',
    promotionState: 'reviewed',
    lastUsedAt: '2026-04-01T12:00:00Z',
    lastHelpedAt: '2026-04-01T12:00:00Z',
    description: 'Reusable verification defaults for Python and frontend missions.',
  },
];
baseSnapshot.skillLibrary.userInstalledSkills = [
  {
    label: 'Local Builder Notes',
    executionCapable: true,
    originType: 'user_authored',
    editableStatus: 'active',
    testStatus: 'sample_ready',
    promotionState: 'reviewed',
    lastUsedAt: '2026-04-02T18:00:00Z',
    lastHelpedAt: '2026-04-02T18:00:00Z',
    description: 'A locally authored builder helper under review inside Skill Studio.',
  },
];
baseSnapshot.skillLibrary.learnedSkills = [
  {
    label: 'Approval Recovery Pattern',
    execution_capable: false,
    originType: 'learned',
    editableStatus: 'active',
    testStatus: 'untested',
    promotionState: 'learning',
    lastUsedAt: '2026-04-02T21:15:00Z',
    lastHelpedAt: '2026-04-02T21:15:00Z',
    description: 'Promote approval recovery into a reusable reviewed skill after a successful test run.',
  },
];
baseSnapshot.workflowStudio.managementSummary = {
  recipeCount: 4,
  reviewedCount: 4,
  blockedCount: 0,
};
baseSnapshot.workflowStudio.recipes = baseSnapshot.workflowStudio.recipes.map(item => ({
  ...item,
  reviewStatus: 'reviewed',
  runtimeChoice: item.workflowId === 'agent_long_run' ? 'openclaw_or_hermes' : 'openclaw',
  skillIds: item.workflowId === 'skill_authoring' ? ['Local Builder Notes', 'Approval Recovery Pattern'] : ['Repo Scan'],
  serviceIds: item.workflowId === 'skill_authoring' ? ['uv', 'hermes'] : ['wsl2', 'filesystem_mcp'],
  verificationDefaults: ['python -m pytest tests -q', 'npm run frontend:build'],
}));

const liveReviewFixture = (() => {
  const snapshot = clone(baseSnapshot);
  snapshot.missions = [
    {
      mission_id: 'mission_live_review',
      workspace_id: 'workspace_primary',
      runtime_id: 'openclaw',
      selected_profile: 'builder',
      title: 'Redesign delegated approval workbench',
      objective: 'Tighten the mission control UI, add fixture preview mode, and keep delegated approvals obvious.',
      run_budget: { mode: 'Autopilot' },
      state: {
        status: 'needs_approval',
        current_cycle_phase: 'execute',
        cycle_count: 2,
        last_verification_result: 'pending',
        last_replan_reason: 'delegated_approval',
        remaining_steps: ['Review new approval surface', 'Patch delegated-lane stack', 'Run fixture-backed UI check'],
        verification_failures: [],
        active_step_id: 'step_review',
        pending_mutating_actions: 1,
        execution_scope: { execution_root: 'C:/Users/paul/Projects/vibe-coding-platform' },
        planner_loop_status: 'paused',
        last_plan_summary: 'Planner paused after a delegated lane asked for approval on a high-risk action.',
      },
      proof: {
        summary: 'Approve delegated deploy simulation before Fluxio continues.',
        pending_approvals: ['Approve delegated deploy simulation?'],
        failed_checks: [],
      },
      missionLoop: {
        currentCyclePhase: 'execute',
        cycleCount: 2,
        lastVerificationResult: 'pending',
        lastVerificationSummary: 'Verification is still pending.',
        lastReplanReason: 'delegated_approval',
        lastReplanTrigger: 'delegated_approval',
        improvementQueue: [{ title: 'Split planner panel into approval rail and execution rail', priority: 'high' }],
        resumeReady: true,
        continuityState: 'approval_waiting',
        continuityDetail: 'Approve delegated deploy simulation?',
        currentRuntimeLane: 'openclaw delegated approval lane',
        timeBudget: {
          budgetHours: 12,
          elapsedSeconds: 18720,
          remainingSeconds: 24480,
          status: 'approval_waiting',
          runUntilBehavior: 'pause_on_failure',
          lastPauseReason: 'Approve delegated deploy simulation?',
        },
      },
      changed_files: ['desktop-ui/FluxioDesktop.jsx', 'desktop-ui/styles.css', 'tests/test_desktop_ui_contract.py'],
      proof_artifacts: ['Approval screenshot pending', 'Mission diff review queued', 'Desktop verification pass required'],
      execution_scope: { strategy: 'git_worktree', execution_root: 'C:/Users/paul/Projects/.fluxio-worktrees-vibe/live-review' },
      execution_policy: { approval_mode: 'tiered' },
      plan_revisions: [
        {
          revision_id: 'rev_live_2',
          trigger: 'delegated_approval',
          summary: 'Planner paused to request approval for a delegated deploy simulation.',
          created_at: now,
          steps: [
            { title: 'Review current delegated lane output', status: 'completed' },
            { title: 'Approve delegated deploy simulation', status: 'in_progress' },
            { title: 'Continue UI refinement after approval', status: 'pending' },
          ],
        },
      ],
      route_configs: [
        { role: 'planner', provider: 'openai', model: 'gpt-5.4', budget_class: 'premium', explanation: 'Better planning quality.' },
        { role: 'executor', provider: 'openai', model: 'gpt-5.4-mini', budget_class: 'efficient', explanation: 'Cheaper execution.' },
      ],
      effectiveRouteContract: {
        roles: [
          { role: 'planner', provider: 'openai', model: 'gpt-5.4', budgetClass: 'premium', effort: 'high', source: 'workspace_override', reason: 'Keep approval planning explicit.' },
          { role: 'executor', provider: 'openai', model: 'gpt-5.4-mini', budgetClass: 'efficient', effort: 'medium', source: 'workspace_override', reason: 'Execution stays cheaper during UI iteration.' },
          { role: 'verifier', provider: 'openai', model: 'gpt-5.4', budgetClass: 'premium', effort: 'high', source: 'profile_default', reason: 'Verification still uses the stronger route.' },
        ],
      },
      action_history: [
        {
          action_id: 'action_live_1',
          executed_at: now,
          proposal: {
            kind: 'runtime_delegate',
            title: 'Delegate deploy simulation to OpenClaw',
            policy_decision: 'auto_run',
            target_scope: 'worktree',
            sourceKind: 'delegated',
          },
          gate: { status: 'not_required' },
          result: { result_summary: 'Delegated runtime lane launched under Fluxio supervision.', sourceKind: 'delegated' },
        },
        {
          action_id: 'action_live_2',
          executed_at: now,
          proposal: {
            kind: 'file_patch',
            title: 'Patch mission review surface',
            policy_decision: 'requires_approval',
            target_scope: 'worktree',
            sourceKind: 'local',
          },
          gate: { status: 'pending' },
          result: { result_summary: 'Waiting for operator approval.', sourceKind: 'local' },
        },
      ],
      delegated_runtime_sessions: [
        {
          delegated_id: 'delegated_live_review',
          runtime_id: 'openclaw',
          status: 'waiting_for_approval',
          last_event: 'Approve delegated deploy simulation?',
          detail: 'Delegated runtime is waiting for approval.',
          heartbeat_status: 'healthy',
          heartbeat_age_seconds: 18,
          execution_target: 'isolated_worktree',
          execution_root: 'C:/Users/paul/Projects/.fluxio-worktrees-vibe/live-review',
          execution_target_detail: 'Isolated worktree review lane for desktop UI changes.',
          updated_at: now,
          pending_approval: { prompt: 'Approve delegated deploy simulation?' },
          approval_history: [],
          latest_events: [
            { event_id: 'evt_live_review_1', kind: 'runtime.phase', message: 'Deploy simulation reached approval gate.', status: 'running' },
            { event_id: 'evt_live_review_2', kind: 'approval.request', message: 'Approve delegated deploy simulation?', status: 'waiting' },
          ],
        },
      ],
      improvement_queue: [
        { title: 'Split planner panel into approval rail and execution rail', reason: 'The current planner stack is too dense.', priority: 'high' },
      ],
      derived_tasks: [
        { title: 'Add fixture-backed review mode', reason: 'UI work needs fast scenario switching.', status: 'pending' },
      ],
    },
  ];
  snapshot.inbox = [
    {
      missionId: 'mission_live_review',
      channel: 'telegram',
      destination: '123456789',
      ready: true,
      pendingCount: 1,
      previewMessage: 'Approve delegated deploy simulation before Fluxio continues.',
    },
  ];
  return {
    name: 'Live Review',
    description: 'Shows the delegated approval state while refining the operator workbench.',
    snapshot,
  };
})();

const emptyStartFixture = (() => {
  const snapshot = clone(baseSnapshot);
  snapshot.workspaces = [];
  snapshot.missions = [];
  snapshot.activity = [];
  snapshot.inbox = [];
  snapshot.guidance.guidanceCards = [
    { card_id: 'guide_add_workspace', title: 'Add your first workspace', body: 'Register a project to unlock missions and recommendations.', kind: 'setup', panel: 'Projects' },
  ];
  snapshot.guidance.productImprovements = [
    { item_id: 'pi_empty', title: 'Improve first-run empty states', reason: 'The shell should feel guided even before the first mission exists.', priority: 'high', category: 'tutorial' },
  ];
  snapshot.onboarding.tutorial.currentStepId = 'add_workspace';
  snapshot.onboarding.tutorial.isComplete = false;
  snapshot.onboarding.tutorial.completedSteps = ['detect_environment', 'choose_profile'];
  return {
    name: 'First Run',
    description: 'Shows the no-workspace, no-mission onboarding state.',
    snapshot,
  };
})();

const verificationFailureFixture = (() => {
  const snapshot = clone(baseSnapshot);
  snapshot.missions = [
    {
      mission_id: 'mission_verification_failure',
      workspace_id: 'workspace_primary',
      runtime_id: 'hermes',
      selected_profile: 'advanced',
      title: 'Repair verification failure and broaden diagnosis',
      objective: 'Hermes widened the search after repeated failures.',
      run_budget: { mode: 'Deep Run' },
      state: {
        status: 'verification_failed',
        current_cycle_phase: 'replan',
        cycle_count: 3,
        last_verification_result: 'failed',
        last_replan_reason: 'verification_failed',
        remaining_steps: ['Inspect failing environment assumptions', 'Retry focused fix'],
        verification_failures: ['python -m pytest tests -q'],
        active_step_id: 'step_diag',
        pending_mutating_actions: 0,
        execution_scope: { execution_root: 'C:/Users/paul/Projects/vibe-coding-platform' },
        planner_loop_status: 'paused',
        last_plan_summary: 'Verification failed twice, so Fluxio broadened diagnosis into environment and tooling.',
      },
      proof: {
        summary: 'Verification failed after execution. Review the widened diagnosis lane.',
        pending_approvals: [],
        failed_checks: ['python -m pytest tests -q'],
      },
      missionLoop: {
        currentCyclePhase: 'replan',
        cycleCount: 3,
        lastVerificationResult: 'failed',
        lastVerificationSummary: 'Failed: python -m pytest tests -q',
        lastReplanReason: 'verification_failed',
        lastReplanTrigger: 'verification_failed',
        improvementQueue: [{ title: 'Add automatic screenshot proof for failing UIs', priority: 'medium' }],
        resumeReady: true,
        continuityState: 'resume_available',
        continuityDetail: 'Mission can resume safely from the last recorded session.',
        currentRuntimeLane: 'hermes verification lane',
        timeBudget: {
          budgetHours: 10,
          elapsedSeconds: 13200,
          remainingSeconds: 22800,
          status: 'paused_after_failure',
          runUntilBehavior: 'pause_on_failure',
          lastPauseReason: 'Verification failed: python -m pytest tests -q',
        },
      },
      changed_files: ['src/grant_agent/runtime_worker.py', 'desktop-ui/FluxioDesktop.jsx'],
      proof_artifacts: ['pytest failure log captured', 'Environment diagnosis note drafted', 'Retry plan waiting for review'],
      execution_scope: { strategy: 'direct', execution_root: 'C:/Users/paul/Projects/vibe-coding-platform' },
      execution_policy: { approval_mode: 'tiered' },
      plan_revisions: [
        {
          revision_id: 'rev_fail_3',
          trigger: 'verification_failed',
          summary: 'Planner broadened root-cause search after repeated failure.',
          created_at: now,
          steps: [
            { title: 'Inspect dependency graph', status: 'completed' },
            { title: 'Check environment assumptions', status: 'in_progress' },
            { title: 'Retry focused fix', status: 'pending' },
          ],
        },
      ],
      route_configs: [
        { role: 'planner', provider: 'openai', model: 'gpt-5.4', budget_class: 'premium', explanation: 'Broader diagnosis benefits from stronger planning.' },
        { role: 'verifier', provider: 'openai', model: 'gpt-5.4', budget_class: 'premium', explanation: 'Verification quality matters here.' },
      ],
      effectiveRouteContract: {
        roles: [
          { role: 'planner', provider: 'openai', model: 'gpt-5.4', budgetClass: 'premium', effort: 'high', source: 'profile_default', reason: 'Broader diagnosis benefits from stronger planning.' },
          { role: 'executor', provider: 'openai', model: 'gpt-5.4-mini', budgetClass: 'efficient', effort: 'medium', source: 'profile_default', reason: 'Execution stays efficient during diagnosis.' },
          { role: 'verifier', provider: 'openai', model: 'gpt-5.4', budgetClass: 'premium', effort: 'high', source: 'workspace_override', reason: 'Verification quality matters here.' },
        ],
      },
      action_history: [
        {
          action_id: 'action_fail_1',
          executed_at: now,
          proposal: {
            kind: 'test_run',
            title: 'Run verification for environment diagnosis',
            policy_decision: 'auto_run',
            target_scope: 'workspace',
          },
          gate: { status: 'not_required' },
          result: { result_summary: 'test_run completed with exit code 1.' },
        },
      ],
      delegated_runtime_sessions: [],
      improvement_queue: [
        { title: 'Add automatic screenshot proof for failing UIs', reason: 'Verification failures need faster visual evidence.', priority: 'medium' },
      ],
      derived_tasks: [
        { title: 'Inspect environment assumptions', reason: 'Repeated failure triggered broader diagnosis.', status: 'in_progress' },
      ],
    },
  ];
  snapshot.inbox = [
    {
      missionId: 'mission_verification_failure',
      channel: 'telegram',
      destination: '123456789',
      ready: true,
      pendingCount: 1,
      previewMessage: 'Verification failed after execution. Review the widened diagnosis lane.',
    },
  ];
  return {
    name: 'Verification Failure',
    description: 'Shows a widened-diagnosis state after repeated verification failures.',
    snapshot,
  };
})();

const approvalResumedFixture = (() => {
  const snapshot = clone(baseSnapshot);
  snapshot.missions = [
    {
      mission_id: 'mission_approval_resumed',
      workspace_id: 'workspace_primary',
      runtime_id: 'hermes',
      selected_profile: 'builder',
      title: 'Resume after delegated approval',
      objective: 'Hermes resumed after operator approval and is finishing the remaining lane.',
      run_budget: { mode: 'Autopilot' },
      state: {
        status: 'queued',
        current_cycle_phase: 'execute',
        cycle_count: 4,
        last_verification_result: 'pending',
        last_verification_summary: 'Verification is still pending.',
        last_replan_reason: 'delegated_approval',
        last_replan_trigger: 'delegated_approval',
        continuity_state: 'resume_available',
        continuity_detail: 'Mission can resume safely from the last recorded session.',
        remaining_steps: ['Resume delegated lane', 'Collect proof', 'Run verification'],
        verification_failures: [],
        active_step_id: 'step_resume',
        pending_mutating_actions: 0,
        execution_scope: { execution_root: 'C:/Users/paul/Projects/vibe-coding-platform' },
        planner_loop_status: 'paused',
        last_plan_summary: 'Approval was granted while the operator was away. Fluxio is ready to resume from the same mission state.',
      },
      proof: {
        summary: 'Latest approval requirement approved. Resume mission to continue.',
        pending_approvals: [],
        failed_checks: [],
      },
      missionLoop: {
        currentCyclePhase: 'execute',
        cycleCount: 4,
        lastVerificationResult: 'pending',
        lastVerificationSummary: 'Verification is still pending.',
        lastReplanReason: 'delegated_approval',
        lastReplanTrigger: 'delegated_approval',
        improvementQueue: [{ title: 'Persist clearer resume banners after approval', priority: 'medium' }],
        resumeReady: true,
        continuityState: 'resume_available',
        continuityDetail: 'Mission can resume safely from the last recorded session.',
        currentRuntimeLane: 'hermes resumed verification lane',
        timeBudget: {
          budgetHours: 12,
          elapsedSeconds: 21540,
          remainingSeconds: 21660,
          status: 'resume_available',
          runUntilBehavior: 'continue_until_blocked',
          lastPauseReason: 'Waiting for operator to resume from the last recorded checkpoint.',
        },
      },
      changed_files: ['src/grant_agent/mission_control.py', 'docs/FLUXIO_1_0_RELEASE.md'],
      proof_artifacts: ['Approval resolution recorded', 'Delegated lane completion report ready'],
      execution_scope: { strategy: 'direct', execution_root: 'C:/Users/paul/Projects/vibe-coding-platform' },
      route_configs: [
        { role: 'planner', provider: 'openai', model: 'gpt-5.4', budget_class: 'premium', explanation: 'Planner keeps the resumed mission coherent.' },
      ],
      effectiveRouteContract: {
        roles: [
          { role: 'planner', provider: 'openai', model: 'gpt-5.4', budgetClass: 'premium', effort: 'high', source: 'profile_default', reason: 'Planner keeps the resumed mission coherent.' },
          { role: 'executor', provider: 'openai', model: 'gpt-5.4-mini', budgetClass: 'efficient', effort: 'medium', source: 'workspace_override', reason: 'Execution stays lighter for resumed follow-through.' },
          { role: 'verifier', provider: 'openai', model: 'gpt-5.4', budgetClass: 'premium', effort: 'high', source: 'profile_default', reason: 'Verification still uses the premium route.' },
        ],
      },
      action_history: [
        {
          action_id: 'action_resume_1',
          executed_at: now,
          proposal: { kind: 'runtime_delegate', title: 'Delegate verification follow-up to Hermes', policy_decision: 'auto_run', target_scope: 'workspace', sourceKind: 'delegated' },
          gate: { status: 'not_required' },
          result: { result_summary: 'Delegated runtime lane resumed under Fluxio supervision.', sourceKind: 'delegated' },
        },
      ],
      delegated_runtime_sessions: [
        {
          delegated_id: 'delegated_approval_resumed',
          runtime_id: 'hermes',
          status: 'completed',
          last_event: 'Delegated lane resumed after approval and finished cleanly.',
          detail: 'Delegated lane completed while the desktop was away.',
          heartbeat_status: 'healthy',
          heartbeat_age_seconds: 7,
          execution_target: 'workspace_root',
          execution_root: 'C:/Users/paul/Projects/vibe-coding-platform',
          execution_target_detail: 'Workspace-root resume lane under Hermes supervision.',
          updated_at: now,
          pending_approval: {},
          approval_history: [
            { status: 'approved', resolved_by: 'operator', resolved_at: now },
          ],
          latest_events: [
            { event_id: 'evt_resume_1', kind: 'approval.resolved', message: 'Delegated approval approved by operator.', status: 'approved' },
            { event_id: 'evt_resume_2', kind: 'session.completed', message: 'Delegated lane resumed after approval and finished cleanly.', status: 'completed' },
          ],
        },
      ],
      improvement_queue: [
        { title: 'Persist clearer resume banners after approval', reason: 'Operators need immediate clarity after returning to the app.', priority: 'medium' },
      ],
      derived_tasks: [],
    },
  ];
  return {
    name: 'Approval Resumed',
    description: 'Shows the restart-safe state after approval was granted and the mission can resume.',
    snapshot,
  };
})();

const longRunResumedFixture = (() => {
  const snapshot = clone(baseSnapshot);
  snapshot.missions = [
    {
      mission_id: 'mission_long_run',
      workspace_id: 'workspace_primary',
      runtime_id: 'openclaw',
      selected_profile: 'advanced',
      title: 'Long-run mission resumed after several hours',
      objective: 'OpenClaw planned, executed, verified, and left a clear continuity trail.',
      run_budget: { mode: 'Deep Run' },
      state: {
        status: 'running',
        current_cycle_phase: 'verify',
        cycle_count: 7,
        last_verification_result: 'passed',
        last_verification_summary: 'Passed 2 verification check(s).',
        last_replan_reason: 'action_completed',
        last_replan_trigger: 'action_completed',
        continuity_state: 'delegated_active',
        continuity_detail: 'openclaw lane is still active and restart-safe.',
        remaining_steps: ['Summarize proof bundle', 'Prepare final review'],
        verification_failures: [],
        active_step_id: 'step_summary',
        pending_mutating_actions: 0,
        execution_scope: { execution_root: 'C:/Users/paul/Projects/vibe-coding-platform' },
        planner_loop_status: 'running',
        last_plan_summary: 'Fluxio completed the main execution and is waiting for the final proof summary before closing the mission.',
      },
      proof: {
        summary: 'Delegated runtime lane is active. Fluxio will continue when it finishes.',
        passed_checks: ['python -m pytest tests -q', 'npm run frontend:build'],
        pending_approvals: [],
        failed_checks: [],
      },
      missionLoop: {
        currentCyclePhase: 'verify',
        cycleCount: 7,
        lastVerificationResult: 'passed',
        lastVerificationSummary: 'Passed 2 verification check(s).',
        lastReplanReason: 'action_completed',
        lastReplanTrigger: 'action_completed',
        improvementQueue: [{ title: 'Add a calmer post-run state for long unattended missions', priority: 'medium' }],
        resumeReady: true,
        continuityState: 'delegated_active',
        continuityDetail: 'openclaw lane is still active and restart-safe.',
        currentRuntimeLane: 'openclaw long-run summary lane',
        timeBudget: {
          budgetHours: 16,
          elapsedSeconds: 36120,
          remainingSeconds: 21480,
          status: 'delegated_active',
          runUntilBehavior: 'continue_until_blocked',
          lastPauseReason: 'Delegated runtime lane is still active and restart-safe.',
        },
      },
      changed_files: ['desktop-ui/FluxioDesktop.jsx', 'desktop-ui/styles.css', 'artifacts/ui-audit/long-run-proof.png'],
      proof_artifacts: ['Completion report draft', 'Verification proof bundle assembled', 'Return summary pending operator review'],
      route_configs: [
        { role: 'planner', provider: 'openai', model: 'gpt-5.4', budget_class: 'premium', explanation: 'Stronger planner for long unattended loops.' },
      ],
      effectiveRouteContract: {
        roles: [
          { role: 'planner', provider: 'openai', model: 'gpt-5.4', budgetClass: 'premium', effort: 'high', source: 'profile_default', reason: 'Long unattended loops benefit from stronger planning.' },
          { role: 'executor', provider: 'openai', model: 'gpt-5.4-mini', budgetClass: 'efficient', effort: 'medium', source: 'workspace_override', reason: 'Execution can stay efficient over long runs.' },
          { role: 'verifier', provider: 'openai', model: 'gpt-5.4', budgetClass: 'premium', effort: 'high', source: 'profile_default', reason: 'Verification remains premium for unattended completion.' },
        ],
      },
      action_history: [
        {
          action_id: 'action_long_1',
          executed_at: now,
          proposal: { kind: 'runtime_delegate', title: 'Delegate long-run verification sweep', policy_decision: 'auto_run', target_scope: 'workspace', sourceKind: 'delegated' },
          gate: { status: 'not_required' },
          result: { result_summary: 'Delegated long-run verification sweep is still active.', sourceKind: 'delegated' },
        },
      ],
      delegated_runtime_sessions: [
        {
          delegated_id: 'delegated_long_run',
          runtime_id: 'openclaw',
          status: 'running',
          last_event: 'Preparing the final proof summary and completion report.',
          detail: 'Delegated lane is still running.',
          heartbeat_status: 'healthy',
          heartbeat_age_seconds: 23,
          execution_target: 'isolated_worktree',
          execution_root: 'C:/Users/paul/Projects/vibe-coding-platform',
          execution_target_detail: 'Long-run summary lane in an isolated worktree.',
          updated_at: now,
          pending_approval: {},
          approval_history: [],
          latest_events: [
            { event_id: 'evt_long_run_1', kind: 'runtime.phase', message: 'Verification passed and the lane moved into summary mode.', status: 'running' },
            { event_id: 'evt_long_run_2', kind: 'runtime.output', message: 'Preparing the final proof summary and completion report.', status: 'running' },
          ],
        },
      ],
      improvement_queue: [
        { title: 'Add a calmer post-run state for long unattended missions', reason: 'Returning operators need faster long-run orientation.', priority: 'medium' },
      ],
      derived_tasks: [],
    },
  ];
  return {
    name: 'Long-Run Resumed',
    description: 'Shows a long unattended mission with clear continuity, proof, and active delegated state.',
    snapshot,
  };
})();

const fixtures = {
  live_review: liveReviewFixture,
  first_run: emptyStartFixture,
  verification_failure: verificationFailureFixture,
  approval_resumed: approvalResumedFixture,
  long_run_resumed: longRunResumedFixture,
};

export function listFixtureOptions() {
  return Object.entries(fixtures).map(([id, item]) => ({
    id,
    name: item.name,
    description: item.description,
  }));
}

export function buildFixtureSnapshot(id) {
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
      description: fixture.description,
    },
  };
}
