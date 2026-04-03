const now = '2026-04-02T21:15:00Z';

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
    },
    builder: {
      description: 'Balanced profile for autonomous delivery with guided control.',
      ui: { motion: 'standard' },
    },
    advanced: {
      description: 'Concise, higher-autonomy profile for experienced builders.',
      ui: { motion: 'standard' },
    },
    experimental: {
      description: 'Broad autonomy, wider experimentation, and faster iteration.',
      ui: { motion: 'standard' },
    },
  },
};

const baseSnapshot = {
  workspaceRoot: 'C:/Users/paul/Projects/vibe-coding-platform',
  workspaces: [
    {
      workspace_id: 'workspace_primary',
      name: 'Fluxio Platform',
      root_path: 'C:/Users/paul/Projects/vibe-coding-platform',
      default_runtime: 'openclaw',
      workspace_type: 'tauri-python',
      user_profile: 'builder',
      runtimeStatus: { detected: true },
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
        { step_id: 'detect_environment', title: 'Check local setup', description: 'Verify runtimes and tooling.', status: 'completed', panel: 'Setup' },
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
      openclaw: { installed: true, version: '2026.2.15' },
      hermes: { installed: true, version: '0.4.0' },
    },
    wsl: { installed: true, details: 'WSL2 detected and ready.' },
    nextActions: ['Launch a first mission', 'Enable Telegram escalation'],
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
  skillLibrary: {
    recommendedPacks: [{ label: 'Repo Scan', execution_capable: true }],
    curatedPacks: [{ label: 'Verification Suite', execution_capable: false }],
    userInstalledSkills: [],
    learnedSkills: [{ label: 'Approval Recovery Pattern', execution_capable: false }],
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
    recommendation: 'Bridge lab is mock-only until supervision and approvals are fully stable.',
    phases: [
      'Phase A: spec and mock registry only',
      'Phase B: one reference integration',
      'Phase C: developer kit and public docs',
    ],
    discoveredApps: [
      {
        name: 'Oratio Viva',
        description: 'Speech workflows exposed through a local bridge.',
        bridge: { transport: 'http' },
        permissions: ['task.run', 'context.read', 'action.invoke'],
      },
      {
        name: 'Solantir Terminal',
        description: 'Operator dashboard surfaces exposed through IPC.',
        bridge: { transport: 'ipc' },
        permissions: ['task.run', 'context.read', 'approval.request'],
      },
    ],
    connectedSessions: [
      {
        app_name: 'Oratio Viva',
        status: 'mock_connected',
        bridge_health: 'healthy',
        active_tasks: ['Render voice preview'],
        granted_capabilities: [
          { capability_key: 'task.run', status: 'granted' },
          { capability_key: 'context.read', status: 'granted' },
        ],
        last_seen_at: now,
      },
    ],
  },
};

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
      action_history: [
        {
          action_id: 'action_live_1',
          executed_at: now,
          proposal: {
            kind: 'runtime_delegate',
            title: 'Delegate deploy simulation to OpenClaw',
            policy_decision: 'auto_run',
            target_scope: 'worktree',
          },
          gate: { status: 'not_required' },
          result: { result_summary: 'Delegated runtime lane launched under Fluxio supervision.' },
        },
        {
          action_id: 'action_live_2',
          executed_at: now,
          proposal: {
            kind: 'file_patch',
            title: 'Patch mission review surface',
            policy_decision: 'requires_approval',
            target_scope: 'worktree',
          },
          gate: { status: 'pending' },
          result: { result_summary: 'Waiting for operator approval.' },
        },
      ],
      delegated_runtime_sessions: [
        {
          runtime_id: 'openclaw',
          status: 'waiting_for_approval',
          last_event: 'Approve delegated deploy simulation?',
          detail: 'Delegated runtime is waiting for approval.',
          updated_at: now,
          pending_approval: { prompt: 'Approve delegated deploy simulation?' },
          latest_events: [
            { kind: 'runtime.phase', message: 'Deploy simulation reached approval gate.' },
            { kind: 'approval.request', message: 'Approve delegated deploy simulation?' },
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

const fixtures = {
  live_review: liveReviewFixture,
  first_run: emptyStartFixture,
  verification_failure: verificationFailureFixture,
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
