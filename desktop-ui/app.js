import { buildFixtureSnapshot, listFixtureOptions } from './fixtures.js';
import {
  describeMissionLocus,
  escapeHtml,
  missionStatusTone,
  renderMetricCard,
  runtimeLabel,
} from './helpers.js';
import { createLiveRefreshController } from './live.js';

const invoke = window.__TAURI__?.core?.invoke;

const STORAGE_KEYS = {
  telegramChatId: 'fluxio.telegram.chatId',
  previewMode: 'fluxio.preview.mode',
  liveSyncSeconds: 'fluxio.live_sync.seconds',
};

const state = {
  snapshot: null,
  onboarding: null,
  pendingApprovals: [],
  pendingQuestions: [],
  telegramReady: false,
  selectedWorkspaceId: null,
  selectedMissionId: null,
  previewMode: 'live',
  previewMeta: null,
  liveSyncSeconds: 'off',
  liveSyncHandle: null,
  liveSyncSuspended: false,
  refreshInFlight: false,
  refreshQueued: false,
  queuedRefreshReason: '',
  controlRoomUnlisten: null,
  controlRoomDeltaUnlisten: null,
  lastPushReason: '',
  lastRefreshReason: '',
  liveActivity: [],
};

const elements = {
  refreshBtn: document.getElementById('refreshBtn'),
  refreshStatus: document.getElementById('refreshStatus'),
  devLoopStatus: document.getElementById('devLoopStatus'),
  liveFeedStatus: document.getElementById('liveFeedStatus'),
  previewModeSelect: document.getElementById('previewModeSelect'),
  liveSyncSelect: document.getElementById('liveSyncSelect'),
  heroGrid: document.getElementById('heroGrid'),
  guidanceStrip: document.getElementById('guidanceStrip'),
  guidanceSummary: document.getElementById('guidanceSummary'),
  tutorialStepList: document.getElementById('tutorialStepList'),
  profileChoiceList: document.getElementById('profileChoiceList'),
  guidanceCardList: document.getElementById('guidanceCardList'),
  workspaceList: document.getElementById('workspaceList'),
  workspaceForm: document.getElementById('workspaceForm'),
  missionWorkspace: document.getElementById('missionWorkspace'),
  missionRuntime: document.getElementById('missionRuntime'),
  missionProfile: document.getElementById('missionProfile'),
  missionForm: document.getElementById('missionForm'),
  missionList: document.getElementById('missionList'),
  inboxSummary: document.getElementById('inboxSummary'),
  inboxList: document.getElementById('inboxList'),
  activityList: document.getElementById('activityList'),
  plannerSummary: document.getElementById('plannerSummary'),
  proofArtifactList: document.getElementById('proofArtifactList'),
  routingList: document.getElementById('routingList'),
  planRevisionList: document.getElementById('planRevisionList'),
  actionHistoryList: document.getElementById('actionHistoryList'),
  delegatedLaneList: document.getElementById('delegatedLaneList'),
  improvementQueueList: document.getElementById('improvementQueueList'),
  setupGrid: document.getElementById('setupGrid'),
  runtimeList: document.getElementById('runtimeList'),
  telegramBotToken: document.getElementById('telegramBotToken'),
  telegramChatId: document.getElementById('telegramChatId'),
  telegramStatus: document.getElementById('telegramStatus'),
  saveTelegramTokenBtn: document.getElementById('saveTelegramTokenBtn'),
  clearTelegramTokenBtn: document.getElementById('clearTelegramTokenBtn'),
  sendTelegramTestBtn: document.getElementById('sendTelegramTestBtn'),
  skillRecommendations: document.getElementById('skillRecommendations'),
  integrationRecommendations: document.getElementById('integrationRecommendations'),
  skillCatalog: document.getElementById('skillCatalog'),
  harnessLab: document.getElementById('harnessLab'),
  productLab: document.getElementById('productLab'),
  bridgeLabSummary: document.getElementById('bridgeLabSummary'),
  bridgeLabApps: document.getElementById('bridgeLabApps'),
  bridgeLabSessions: document.getElementById('bridgeLabSessions'),
  toastHost: document.getElementById('toastHost'),
};

function toast(message, kind = 'info') {
  const node = document.createElement('div');
  node.className = `toast ${kind}`;
  node.textContent = message;
  elements.toastHost.appendChild(node);
  window.setTimeout(() => node.remove(), 3200);
}

async function callBackend(command, payload = undefined, options = {}) {
  if (!invoke) {
    if (options.throwOnError) {
      throw new Error('Tauri backend is unavailable.');
    }
    return null;
  }

  try {
    return payload === undefined ? await invoke(command) : await invoke(command, payload);
  } catch (error) {
    if (options.throwOnError) {
      throw error;
    }
    console.error(command, error);
    return null;
  }
}

function setRefreshStatus(text, kind = 'idle') {
  elements.refreshStatus.textContent = text;
  elements.refreshStatus.dataset.kind = kind;
}

function setDevLoopStatus(text, kind = 'idle') {
  if (!elements.devLoopStatus) {
    return;
  }
  elements.devLoopStatus.textContent = text;
  elements.devLoopStatus.dataset.kind = kind;
}

function setFeedStatus(text, kind = 'idle') {
  if (!elements.liveFeedStatus) {
    return;
  }
  elements.liveFeedStatus.textContent = text;
  elements.liveFeedStatus.dataset.kind = kind;
}

const liveRefresh = createLiveRefreshController({
  state,
  refresh: reason => refreshAll(reason),
  isPreviewMode,
  setRefreshStatus,
  setDevLoopStatus,
  setFeedStatus,
  applyDelta: payload => applyLiveDelta(payload),
  onError: (reason, error) => {
    console.error(`refresh failed: ${reason}`, error);
    toast(`Refresh failed: ${error}`, 'error');
  },
});

function getSelectedWorkspace() {
  const workspaces = state.snapshot?.workspaces || [];
  return workspaces.find(item => item.workspace_id === state.selectedWorkspaceId) || workspaces[0] || null;
}

function getSelectedMission() {
  const missions = state.snapshot?.missions || [];
  return missions.find(item => item.mission_id === state.selectedMissionId) || missions[missions.length - 1] || null;
}

function previewLabel() {
  return state.previewMode === 'live'
    ? 'Live backend'
    : `${state.previewMeta?.name || 'Fixture'} preview`;
}

function isPreviewMode() {
  return state.previewMode !== 'live';
}

function currentProfileDetails() {
  const workspace = getSelectedWorkspace();
  const selectedProfile = workspace?.user_profile || getSelectedMission()?.selected_profile || 'builder';
  return state.snapshot?.profiles?.details?.[selectedProfile] || null;
}

function renderHero() {
  const snapshot = state.snapshot || {};
  const missions = snapshot.missions || [];
  const runtimes = snapshot.runtimes || [];
  const inboxCount =
    (snapshot.inbox || []).length +
    (state.pendingApprovals?.length || 0) +
    (state.pendingQuestions?.length || 0);
  const readyRuntimeCount = runtimes.filter(item => item.detected).length;

  const cards = [
    { label: 'Projects', value: (snapshot.workspaces || []).length, note: 'Managed workspaces' },
    { label: 'Missions', value: missions.length, note: 'Daily goals and autonomous loops' },
    { label: 'Ready Runtimes', value: readyRuntimeCount, note: 'OpenClaw and Hermes detection' },
    { label: 'Inbox', value: inboxCount, note: 'Approvals, questions, and phone escalations' },
    { label: 'Preview', value: previewLabel(), note: state.previewMode === 'live' ? 'Reading real control-room state' : (state.previewMeta?.description || 'Fixture-backed UI review') },
  ];

  elements.heroGrid.innerHTML = cards
    .map(card => `
      <article class="hero-card">
        <p class="hero-label">${escapeHtml(card.label)}</p>
        <strong class="hero-value">${escapeHtml(card.value)}</strong>
        <p class="hero-note">${escapeHtml(card.note)}</p>
      </article>
    `)
    .join('');
}

function renderGuidance() {
  const guidance = state.snapshot?.guidance || {};
  const onboarding = state.onboarding || state.snapshot?.onboarding || {};
  const tutorial = onboarding.tutorial || {};
  const profileChoices = guidance.profileChoices || onboarding.profileChoices || [];
  const cards = guidance.guidanceCards || [];
  const improvements = guidance.productImprovements || [];
  const completedSteps = tutorial.completedSteps || [];
  const totalSteps = (tutorial.steps || []).length;
  const activeProfile = tutorial.selectedProfile || getSelectedWorkspace()?.user_profile || 'builder';
  const profileDetails = state.snapshot?.profiles?.details?.[activeProfile] || {};
  const motion = profileDetails.ui?.motion || 'standard';

  document.body.dataset.motion = motion;

  elements.guidanceStrip.innerHTML = `
    <article class="guidance-banner">
      <div>
        <p class="eyebrow">Progressive Guide</p>
        <strong>${escapeHtml(activeProfile)}</strong>
        <p class="muted">${escapeHtml(profileDetails.description || 'Fluxio adapts approvals, explanation depth, and motion from the selected profile.')}</p>
      </div>
      <div class="guidance-metrics">
        <span class="mini-chip">${escapeHtml(`${completedSteps.length}/${totalSteps || 0} tutorial steps complete`)}</span>
        <span class="mini-chip">${escapeHtml(`Motion: ${motion}`)}</span>
      </div>
    </article>
  `;

  elements.guidanceSummary.innerHTML = `
    <strong>${escapeHtml(tutorial.isComplete ? 'Guided setup complete' : 'Guided setup in progress')}</strong>
    <p>${escapeHtml(
      tutorial.isComplete
        ? 'Fluxio has enough setup context to guide new missions with profile-aware approvals and explanations.'
        : 'Fluxio keeps the next setup step visible so non-technical users can recover context quickly.'
    )}</p>
    <p class="muted">Current step: ${escapeHtml(tutorial.currentStepId || 'All steps complete')} · Product ideas: ${escapeHtml(improvements.length)}</p>
  `;

  elements.tutorialStepList.innerHTML = (tutorial.steps || []).length
    ? (tutorial.steps || [])
        .map(
          step => `
            <article class="activity-row ${step.status === 'completed' ? 'is-complete' : 'is-pending'}">
              <div>
                <p class="eyebrow">${escapeHtml(step.panel || 'Guidance')}</p>
                <strong>${escapeHtml(step.title)}</strong>
                <p class="muted">${escapeHtml(step.description)}</p>
              </div>
              <span class="runtime-chip ${step.status === 'completed' ? 'good' : 'warn'}">${escapeHtml(step.status)}</span>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No tutorial steps available yet.</p>';

  elements.profileChoiceList.innerHTML = profileChoices.length
    ? profileChoices
        .map(
          profile => `
            <article class="recommendation-card compact ${profile.name === activeProfile ? 'selected-guide' : ''}">
              <strong>${escapeHtml(profile.name)}</strong>
              <p>${escapeHtml(profile.description)}</p>
              <p class="muted">${escapeHtml(`${profile.executionScope} · ${profile.approvalMode} approvals · ${profile.motion} motion`)}</p>
            </article>
          `
        )
        .join('')
    : '<p class="muted">Profile guidance will appear after onboarding status loads.</p>';

  elements.guidanceCardList.innerHTML = cards.length
    ? cards
        .map(
          card => `
            <article class="recommendation-card compact">
              <p class="eyebrow">${escapeHtml(card.kind)}</p>
              <strong>${escapeHtml(card.title)}</strong>
              <p>${escapeHtml(card.body)}</p>
              <p class="muted">${escapeHtml(card.panel || '')} ${card.cta_label ? `· ${card.cta_label}` : ''}</p>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No additional guidance cards right now.</p>';

  elements.productLab.innerHTML = improvements.length
    ? improvements
        .map(
          item => `
            <article class="activity-row">
              <div>
                <p class="eyebrow">${escapeHtml(item.category || 'product')}</p>
                <strong>${escapeHtml(item.title)}</strong>
                <p class="muted">${escapeHtml(item.reason)}</p>
              </div>
              <span class="runtime-chip neutral">${escapeHtml(item.priority || 'medium')}</span>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No queued product improvements yet.</p>';
}

function renderWorkspaces() {
  const workspaces = state.snapshot?.workspaces || [];
  const selected = getSelectedWorkspace();

  elements.workspaceList.innerHTML = workspaces.length
    ? workspaces
        .map(
          workspace => `
            <button class="workspace-card ${selected?.workspace_id === workspace.workspace_id ? 'selected' : ''}" data-workspace-id="${escapeHtml(workspace.workspace_id)}" type="button">
                <div>
                  <h3>${escapeHtml(workspace.name)}</h3>
                  <p>${escapeHtml(workspace.workspace_type)} · ${escapeHtml(runtimeLabel(workspace.default_runtime))} · ${escapeHtml(workspace.user_profile || 'builder')}</p>
                </div>
              <span class="runtime-chip ${workspace.runtimeStatus?.detected ? 'good' : 'bad'}">
                ${workspace.runtimeStatus?.detected ? 'Runtime ready' : 'Needs setup'}
              </span>
            </button>
          `
        )
        .join('')
    : '<p class="muted">No managed workspaces yet.</p>';

  elements.workspaceList.querySelectorAll('[data-workspace-id]').forEach(button => {
    button.addEventListener('click', () => {
      state.selectedWorkspaceId = button.dataset.workspaceId;
      renderWorkspaces();
      renderMissionFormOptions();
      renderRecommendations();
    });
  });
}

function renderMissionFormOptions() {
  const workspaces = state.snapshot?.workspaces || [];
  const selected = getSelectedWorkspace();
  const profiles = state.snapshot?.profiles?.availableProfiles || [];

  elements.missionWorkspace.innerHTML = workspaces
    .map(
      workspace => `
        <option value="${escapeHtml(workspace.workspace_id)}" ${selected?.workspace_id === workspace.workspace_id ? 'selected' : ''}>
          ${escapeHtml(workspace.name)}
        </option>
      `
    )
    .join('');

  if (selected) {
    elements.missionRuntime.value = selected.default_runtime || 'openclaw';
  }

  elements.missionProfile.innerHTML = profiles
    .map(
      profile => `
        <option value="${escapeHtml(profile)}" ${selected?.user_profile === profile ? 'selected' : ''}>
          ${escapeHtml(profile)}
        </option>
      `
    )
    .join('');

  const savedChatId = localStorage.getItem(STORAGE_KEYS.telegramChatId) || '';
  elements.telegramChatId.value = savedChatId;
}

function renderMissions() {
  const missions = state.snapshot?.missions || [];
  const selectedMission = getSelectedMission();
  elements.missionList.innerHTML = missions.length
    ? missions
        .slice()
        .reverse()
        .map(
          mission => `
            <article class="mission-card ${selectedMission?.mission_id === mission.mission_id ? 'selected-mission' : ''}" data-select-mission="${escapeHtml(mission.mission_id)}">
              <div class="mission-head">
                <div>
                  <p class="eyebrow">${escapeHtml(runtimeLabel(mission.runtime_id))} · ${escapeHtml(mission.run_budget?.mode || 'Autopilot')} · ${escapeHtml(mission.selected_profile || 'builder')}</p>
                  <h3>${escapeHtml(mission.title || mission.objective)}</h3>
                </div>
                <span class="runtime-chip ${missionStatusTone(mission.state?.status)}">${escapeHtml(mission.state?.status || 'draft')}</span>
              </div>
              <p class="mission-objective">${escapeHtml(mission.objective)}</p>
              <div class="mission-proof">
                <strong>Proof</strong>
                <p>${escapeHtml(mission.proof?.summary || 'No proof yet.')}</p>
                <p class="muted">Remaining steps: ${(mission.state?.remaining_steps || []).length} · Verification failures: ${(mission.state?.verification_failures || []).length} · Improvements: ${(mission.improvement_queue || []).length}</p>
                <p class="muted">Harness: ${escapeHtml(mission.harness_id || 'fluxio_hybrid')} · Active step: ${escapeHtml(mission.state?.active_step_id || 'none')}</p>
                <p class="muted">Scope: ${escapeHtml(mission.execution_scope?.strategy || mission.state?.execution_scope?.strategy || 'direct')} · Policy: ${escapeHtml(mission.execution_policy?.approval_mode || 'tiered')} · Delegated lanes: ${(mission.delegated_runtime_sessions || []).length}</p>
                <p class="muted">Work locus: ${escapeHtml(describeMissionLocus(mission))}</p>
              </div>
              <div class="inline-actions">
                <button class="ghost-btn" type="button" data-mission-action="resume" data-mission-id="${escapeHtml(mission.mission_id)}">Resume</button>
                <button class="ghost-btn" type="button" data-mission-action="need-approval" data-mission-id="${escapeHtml(mission.mission_id)}">Need Approval</button>
                ${
                  (mission.proof?.pending_approvals || []).length
                    ? `<button class="ghost-btn" type="button" data-mission-action="approve-latest" data-mission-id="${escapeHtml(mission.mission_id)}">Approve</button>
                       <button class="ghost-btn" type="button" data-mission-action="reject-latest" data-mission-id="${escapeHtml(mission.mission_id)}">Reject</button>`
                    : ''
                }
                <button class="ghost-btn" type="button" data-mission-action="stop" data-mission-id="${escapeHtml(mission.mission_id)}">Stop</button>
              </div>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No missions launched yet.</p>';

  elements.missionList.querySelectorAll('[data-select-mission]').forEach(card => {
    card.addEventListener('click', event => {
      if (event.target.closest('[data-mission-action]')) return;
      state.selectedMissionId = card.dataset.selectMission;
      renderMissions();
      renderPlanner();
    });
  });

  elements.missionList.querySelectorAll('[data-mission-action]').forEach(button => {
    button.addEventListener('click', async () => {
      if (isPreviewMode()) {
        toast('Preview mode is read-only. Switch back to Live Backend to apply mission actions.', 'info');
        return;
      }
      const missionId = button.dataset.missionId;
      const action = button.dataset.missionAction;
      await callBackend(
        'apply_control_room_mission_action_command',
        {
          payload: {
            missionId,
            action,
            root: null,
          },
        },
        { throwOnError: true }
      );
      toast(`Mission action applied: ${action}`);
      await refreshAll();
    });
  });
}

function renderInbox() {
  const inboxItems = state.snapshot?.inbox || [];
  const pendingApprovals = state.pendingApprovals || [];
  const pendingQuestions = state.pendingQuestions || [];

  elements.inboxSummary.innerHTML = `
    <div class="summary-tile">
      <span>Mission escalations</span>
      <strong>${escapeHtml(inboxItems.length)}</strong>
    </div>
    <div class="summary-tile">
      <span>Pending approvals</span>
      <strong>${escapeHtml(pendingApprovals.length)}</strong>
    </div>
    <div class="summary-tile">
      <span>Pending questions</span>
      <strong>${escapeHtml(pendingQuestions.length)}</strong>
    </div>
  `;

  const missionRows = inboxItems.map(
    item => `
      <article class="inbox-card">
        <div>
          <strong>${escapeHtml(item.missionId)}</strong>
          <p>${escapeHtml(item.previewMessage || 'Mission update ready for phone delivery.')}</p>
          <p class="muted">${escapeHtml(item.channel)} · ${escapeHtml(item.destination || 'No destination set')}</p>
        </div>
        <button class="ghost-btn" type="button" data-escalate-message="${escapeHtml(item.previewMessage || '')}">Send To Phone</button>
      </article>
    `
  );

  const approvalRows = pendingApprovals.map(
    item => `
      <article class="inbox-card compact">
        <div>
          <strong>${escapeHtml(item.toolId || item.tool_id || 'Approval')}</strong>
          <p>${escapeHtml(item.reason || item.source || 'Operator approval required.')}</p>
        </div>
      </article>
    `
  );

  const questionRows = pendingQuestions.map(
    item => `
      <article class="inbox-card compact">
        <div>
          <strong>Question</strong>
          <p>${escapeHtml(item.question || 'Agent is waiting for clarification.')}</p>
        </div>
      </article>
    `
  );

  const html = [...missionRows, ...approvalRows, ...questionRows].join('');
  elements.inboxList.innerHTML = html || '<p class="muted">Inbox is clear.</p>';

  elements.inboxList.querySelectorAll('[data-escalate-message]').forEach(button => {
    button.addEventListener('click', async () => {
      const text = button.dataset.escalateMessage || 'Mission update from Fluxio.';
      await sendTelegram(text);
    });
  });
}

function appendLiveActivity(item) {
  const key = JSON.stringify([item.kind, item.message, item.timestamp || '', item.source || '']);
  const existingKeys = new Set(
    state.liveActivity.map(entry => JSON.stringify([entry.kind, entry.message, entry.timestamp || '', entry.source || '']))
  );
  if (existingKeys.has(key)) {
    return;
  }
  state.liveActivity = [{ ...item }, ...state.liveActivity].slice(0, 16);
}

function patchDelegatedMissionSession(row) {
  const missions = state.snapshot?.missions || [];
  let changed = false;

  for (const mission of missions) {
    const sessions = mission.delegated_runtime_sessions || [];
    const session = sessions.find(item => item.delegated_id === row.delegated_id);
    if (!session) {
      continue;
    }

    session.last_event = row.message || session.last_event;
    session.last_event_kind = row.kind || session.last_event_kind;
    session.updated_at = row.created_at || session.updated_at;
    session.status = row.status || session.status;
    const latestEvents = Array.isArray(session.latest_events) ? session.latest_events.slice() : [];
    latestEvents.push(row);
    session.latest_events = latestEvents.slice(-5);

    if (row.kind === 'approval.request') {
      session.pending_approval = {
        request_id: row.data?.request_id || `approval_${row.delegated_id}`,
        delegated_id: row.delegated_id,
        runtime_id: row.runtime_id,
        prompt: row.message,
        risk_level: row.data?.risk_level || 'medium',
        status: 'pending',
        metadata: row.data || {},
      };
      mission.state.status = 'needs_approval';
      mission.proof.summary = row.message || mission.proof.summary;
      mission.proof.pending_approvals = [row.message].filter(Boolean);
    } else if (row.kind === 'approval.decision' || row.kind === 'approval.resolved') {
      if (row.data?.decision === 'approved') {
        session.pending_approval = {};
        mission.proof.pending_approvals = [];
      }
    } else if (row.status) {
      if (row.status === 'waiting_for_approval') {
        mission.state.status = 'needs_approval';
      } else if (['running', 'launching'].includes(row.status)) {
        mission.state.status = 'running';
      }
    }

    mission.state.last_runtime_event = row.message || mission.state.last_runtime_event;
    changed = true;
  }

  return changed;
}

function applyLiveDelta(payload) {
  if (!payload?.row) {
    return;
  }

  if (payload.source === 'mission_event') {
    appendLiveActivity({
      kind: payload.row.kind || 'mission.event',
      message: payload.row.message || 'Mission event',
      timestamp: payload.row.timestamp || payload.detectedAt || '',
      source: 'mission_event',
    });
    renderActivity();
    return;
  }

  if (payload.source === 'runtime_event') {
    appendLiveActivity({
      kind: payload.row.kind || 'runtime.event',
      message: `${runtimeLabel(payload.row.runtime_id || 'runtime')} · ${payload.row.message || 'Runtime event'}`,
      timestamp: payload.row.created_at || payload.detectedAt || '',
      source: 'runtime_event',
    });
    const changed = patchDelegatedMissionSession(payload.row);
    renderActivity();
    if (changed) {
      renderMissions();
      renderPlanner();
    }
  }
}

function renderActivity() {
  const seen = new Set();
  const activity = [...state.liveActivity, ...(state.snapshot?.activity || [])]
    .filter(item => {
      const key = JSON.stringify([item.kind, item.message, item.timestamp || '', item.source || '']);
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    })
    .slice(0, 40);
  elements.activityList.innerHTML = activity.length
    ? activity
        .map(
          item => `
            <article class="activity-row">
              <div>
                <p class="eyebrow">${escapeHtml(item.kind)}</p>
                <strong>${escapeHtml(item.message)}</strong>
              </div>
              <span class="muted">${escapeHtml(item.timestamp || '')}</span>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No mission events yet.</p>';
}

function renderPlanner() {
  const mission = getSelectedMission();
  if (!mission) {
    elements.plannerSummary.innerHTML = '<p class="muted">Launch or select a mission to inspect the planner loop.</p>';
    elements.proofArtifactList.innerHTML = '';
    elements.routingList.innerHTML = '';
    elements.planRevisionList.innerHTML = '';
    elements.actionHistoryList.innerHTML = '';
    elements.delegatedLaneList.innerHTML = '';
    elements.improvementQueueList.innerHTML = '';
    return;
  }

  elements.plannerSummary.innerHTML = `
    <strong>${escapeHtml(mission.title || mission.objective)}</strong>
    <p>${escapeHtml(mission.state?.last_plan_summary || mission.proof?.summary || 'No planner summary yet.')}</p>
    <p class="muted">Profile: ${escapeHtml(mission.selected_profile || 'builder')} · Loop: ${escapeHtml(mission.planner_loop_status || mission.state?.planner_loop_status || 'idle')} · Current revision: ${escapeHtml(mission.current_plan_revision_id || 'n/a')}</p>
    <p class="muted">Execution root: ${escapeHtml(mission.execution_scope?.execution_root || mission.state?.execution_scope?.execution_root || 'n/a')} · Pending mutating actions: ${escapeHtml(mission.state?.pending_mutating_actions || 0)}</p>
  `;

  elements.proofArtifactList.innerHTML = [
    renderMetricCard('Mission State', mission.state?.status || 'draft', describeMissionLocus(mission)),
    renderMetricCard('Runtime', runtimeLabel(mission.runtime_id), mission.execution_scope?.strategy || mission.state?.execution_scope?.strategy || 'direct'),
    renderMetricCard('Approvals', (mission.proof?.pending_approvals || []).length, mission.proof?.pending_approvals?.[0] || 'No pending approvals'),
    renderMetricCard('Checks', `${(mission.proof?.passed_checks || []).length} pass / ${(mission.proof?.failed_checks || []).length} fail`, mission.proof?.failed_checks?.[0] || 'Verification healthy'),
  ].join('');

  elements.routingList.innerHTML = (mission.route_configs || []).length
    ? (mission.route_configs || [])
        .map(
          route => `
            <article class="recommendation-card compact">
              <strong>${escapeHtml(route.role)}</strong>
              <p>${escapeHtml(route.provider)} / ${escapeHtml(route.model)} · ${escapeHtml(route.budget_class)}</p>
              <p class="muted">${escapeHtml(route.explanation || '')}</p>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No model routing data recorded yet.</p>';

  elements.planRevisionList.innerHTML = (mission.plan_revisions || []).length
    ? mission.plan_revisions
        .slice()
        .reverse()
        .slice(0, 4)
        .map(
          revision => `
            <article class="activity-row">
              <div>
                <p class="eyebrow">${escapeHtml(revision.trigger)}</p>
                <strong>${escapeHtml(revision.summary || revision.revision_id)}</strong>
                <p class="muted">${escapeHtml((revision.steps || []).map(step => `${step.title} [${step.status}]`).join(' · '))}</p>
              </div>
              <span class="muted">${escapeHtml(revision.created_at || '')}</span>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No plan revisions yet.</p>';

  elements.actionHistoryList.innerHTML = (mission.action_history || []).length
    ? mission.action_history
        .slice()
        .reverse()
        .slice(0, 5)
        .map(
          action => `
            <article class="activity-row">
              <div>
                <p class="eyebrow">${escapeHtml(action.proposal?.kind || 'action')}</p>
                <strong>${escapeHtml(action.proposal?.title || action.action_id)}</strong>
                <p class="muted">${escapeHtml(action.gate?.status || 'not_required')} · ${escapeHtml(action.proposal?.policy_decision || 'auto_run')} · ${escapeHtml(action.proposal?.target_scope || 'workspace')}</p>
                <p class="muted">${escapeHtml(action.result?.result_summary || action.result?.error || action.result?.stdout || '')}</p>
              </div>
              <span class="muted">${escapeHtml(action.executed_at || '')}</span>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No action history yet.</p>';

  elements.delegatedLaneList.innerHTML = (mission.delegated_runtime_sessions || []).length
    ? mission.delegated_runtime_sessions
        .slice()
        .reverse()
        .map(
          session => `
            <article class="activity-row">
              <div>
                <p class="eyebrow">delegated lane</p>
                <strong>${escapeHtml(session.runtime_id)} · ${escapeHtml(session.status || 'queued')}</strong>
                <p class="muted">${escapeHtml(session.last_event || session.detail || 'No runtime event yet.')}</p>
                ${
                  session.pending_approval?.prompt
                    ? `<p class="muted">Approval: ${escapeHtml(session.pending_approval.prompt)}</p>`
                    : ''
                }
                <p class="muted">${escapeHtml((session.latest_events || []).map(item => `${item.kind}: ${item.message}`).slice(-2).join(' · ') || session.log_path || '')}</p>
              </div>
              <span class="muted">${escapeHtml(session.updated_at || session.created_at || '')}</span>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No delegated runtime lanes.</p>';

  elements.improvementQueueList.innerHTML = (mission.improvement_queue || []).length || (mission.derived_tasks || []).length
    ? [
        ...(mission.derived_tasks || []).map(
          item => `
            <article class="activity-row">
              <div>
                <p class="eyebrow">derived task</p>
                <strong>${escapeHtml(item.title)}</strong>
                <p class="muted">${escapeHtml(item.reason)}</p>
              </div>
              <span class="muted">${escapeHtml(item.status || 'pending')}</span>
            </article>
          `
        ),
        ...(mission.improvement_queue || []).map(
          item => `
            <article class="activity-row">
              <div>
                <p class="eyebrow">improvement</p>
                <strong>${escapeHtml(item.title)}</strong>
                <p class="muted">${escapeHtml(item.reason)}</p>
              </div>
              <span class="muted">${escapeHtml(item.priority || 'medium')}</span>
            </article>
          `
        ),
      ].join('')
    : '<p class="muted">No derived tasks or queued improvements.</p>';
}

function renderSetup() {
  const onboarding = state.onboarding || state.snapshot?.onboarding || {};
  const checks = onboarding.checks || {};
  const wsl = onboarding.wsl || {};
  const nextActions = onboarding.nextActions || [];

  elements.setupGrid.innerHTML = `
    <article class="setup-card">
      <h3>WSL2</h3>
      <p>${escapeHtml(wsl.installed ? 'Installed' : 'Missing')}</p>
      <p class="muted">${escapeHtml(wsl.details || '')}</p>
    </article>
    ${Object.entries(checks)
      .map(
        ([key, value]) => `
          <article class="setup-card">
            <h3>${escapeHtml(key)}</h3>
            <p>${escapeHtml(value.installed ? 'Installed' : 'Missing')}</p>
            <p class="muted">${escapeHtml(value.version || value.details || '')}</p>
          </article>
        `
      )
      .join('')}
    <article class="setup-card wide">
      <h3>Next Actions</h3>
      <ul>
        ${nextActions.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
      </ul>
    </article>
  `;

  const runtimes = state.snapshot?.runtimes || [];
  elements.runtimeList.innerHTML = runtimes
    .map(
      runtime => `
        <article class="runtime-card">
          <div class="mission-head">
            <div>
              <p class="eyebrow">${escapeHtml(runtime.runtime_id)}</p>
              <h3>${escapeHtml(runtime.label)}</h3>
            </div>
            <span class="runtime-chip ${runtime.detected ? 'good' : 'bad'}">${runtime.detected ? 'Detected' : 'Missing'}</span>
          </div>
          <p>${escapeHtml(runtime.doctor_summary || '')}</p>
          <p class="muted">${escapeHtml(runtime.install_hint || '')}</p>
          ${(runtime.capabilities || [])
            .map(capability => `<span class="mini-chip">${escapeHtml(capability.label)}</span>`)
            .join('')}
        </article>
      `
    )
    .join('');
}

function renderRecommendations() {
  const workspace = getSelectedWorkspace();
  const skills = workspace?.skillRecommendations || [];
  const integrations = workspace?.integrationRecommendations || [];

  elements.skillRecommendations.innerHTML = skills.length
    ? skills
        .map(
          item => `
            <article class="recommendation-card">
              <strong>${escapeHtml(item.label)}</strong>
              <p>${escapeHtml(item.reason)}</p>
            </article>
          `
        )
        .join('')
    : '<p class="muted">Select a workspace to see skill packs.</p>';

  elements.integrationRecommendations.innerHTML = integrations.length
    ? integrations
        .map(
          item => `
            <article class="recommendation-card">
              <strong>${escapeHtml(item.label)}</strong>
              <p>${escapeHtml(item.reason)}</p>
              <code>${escapeHtml(item.command)}</code>
            </article>
          `
        )
        .join('')
    : '<p class="muted">Select a workspace to see integration recommendations.</p>';
}

function renderSkillLibrary() {
  const library = state.snapshot?.skillLibrary || {};
  const sections = [
    ['Recommended Packs', library.recommendedPacks || []],
    ['Curated Packs', library.curatedPacks || []],
    ['User Installed', library.userInstalledSkills || []],
    ['Learned Skills', library.learnedSkills || []],
  ];
  elements.skillCatalog.innerHTML = sections
    .map(([label, items]) => `
      <article class="recommendation-card">
        <strong>${escapeHtml(label)}</strong>
        <p class="muted">${items.length} item(s)</p>
        <p>${escapeHtml(items.slice(0, 3).map(item => item.label || item.name || item.skill_id).join(' · ') || 'None yet')}</p>
        <p class="muted">${escapeHtml(items.slice(0, 1).map(item => (item.executionCapable || item.execution_capable) ? 'execution-capable' : 'guidance-first').join('') || '')}</p>
      </article>
    `)
    .join('');

  const harnessLab = state.snapshot?.harnessLab || {};
  elements.harnessLab.innerHTML = `
    <article class="recommendation-card">
      <strong>${escapeHtml(harnessLab.productionHarness || 'fluxio_hybrid')}</strong>
      <p>${escapeHtml(harnessLab.recommendation || 'No harness recommendation yet.')}</p>
      <p class="muted">Shadow: ${escapeHtml((harnessLab.shadowCandidates || []).join(', ') || 'none')}</p>
    </article>
    ${(harnessLab.recentRuns || [])
      .map(
        run => `
          <article class="recommendation-card compact">
            <strong>${escapeHtml(run.sessionId)}</strong>
            <p>${escapeHtml(run.harnessId)} · ${escapeHtml(run.runtimeId)}</p>
            <p class="muted">${escapeHtml(run.autopilotStatus)} ${escapeHtml(run.pauseReason || '')}</p>
          </article>
        `
      )
      .join('')}
  `;

  renderBridgeLab();
}

function renderBridgeLab() {
  const bridgeLab = state.snapshot?.bridgeLab || {};
  elements.bridgeLabSummary.innerHTML = `
    <strong>${escapeHtml(bridgeLab.schemaVersion || 'fluxio.app-capability/v0-draft')}</strong>
    <p>${escapeHtml(bridgeLab.recommendation || 'Bridge lab is loading.')}</p>
    <p class="muted">${escapeHtml((bridgeLab.phases || []).join(' · '))}</p>
  `;

  elements.bridgeLabApps.innerHTML = (bridgeLab.discoveredApps || []).length
    ? (bridgeLab.discoveredApps || [])
        .map(
          app => `
            <article class="recommendation-card compact">
              <strong>${escapeHtml(app.name)}</strong>
              <p>${escapeHtml(app.description)}</p>
              <p class="muted">${escapeHtml(app.bridge?.transport || 'bridge')} · ${escapeHtml((app.permissions || []).join(', '))}</p>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No connected-app manifests loaded yet.</p>';

  elements.bridgeLabSessions.innerHTML = (bridgeLab.connectedSessions || []).length
    ? (bridgeLab.connectedSessions || [])
        .map(
          session => `
            <article class="activity-row">
              <div>
                <p class="eyebrow">${escapeHtml(session.bridge_health || 'healthy')}</p>
                <strong>${escapeHtml(session.app_name)} · ${escapeHtml(session.status)}</strong>
                <p class="muted">${escapeHtml((session.active_tasks || []).join(' · ') || 'No active tasks')}</p>
                <p class="muted">${escapeHtml((session.granted_capabilities || []).map(item => `${item.capability_key} [${item.status}]`).join(' · '))}</p>
              </div>
              <span class="muted">${escapeHtml(session.last_seen_at || '')}</span>
            </article>
          `
        )
        .join('')
    : '<p class="muted">No bridge sessions yet.</p>';
}

function syncLiveControls() {
  const previewActive = isPreviewMode();
  elements.liveSyncSelect.disabled = previewActive;
  if (previewActive) {
    elements.liveSyncSelect.value = 'off';
  } else {
    elements.liveSyncSelect.value = state.liveSyncSeconds;
  }
}

async function refreshAll(reason = 'manual') {
  if (state.refreshInFlight) {
    state.refreshQueued = true;
    state.queuedRefreshReason = reason;
    return;
  }

  state.refreshInFlight = true;
  setRefreshStatus('Refreshing', 'busy');
  try {
    if (state.previewMode !== 'live') {
      const fixturePayload = buildFixtureSnapshot(state.previewMode);
      if (!fixturePayload) {
        state.previewMode = 'live';
        localStorage.setItem(STORAGE_KEYS.previewMode, 'live');
        state.refreshInFlight = false;
        return refreshAll('fallback-live');
      }
      state.snapshot = fixturePayload.snapshot;
      state.onboarding = fixturePayload.onboarding;
      state.pendingApprovals = fixturePayload.pendingApprovals;
      state.pendingQuestions = fixturePayload.pendingQuestions;
      state.telegramReady = fixturePayload.telegramReady;
      state.previewMeta = fixturePayload.meta;
    } else {
      const [snapshot, onboarding, pendingApprovals, pendingQuestions, telegramReady] = await Promise.all([
        callBackend('get_control_room_snapshot_command', { payload: { root: null } }, { throwOnError: true }),
        callBackend('get_onboarding_status_command', { payload: { root: null } }, { throwOnError: true }),
        callBackend('list_pending_approvals'),
        callBackend('list_pending_questions'),
        callBackend('has_telegram_bot_token_command'),
      ]);

      state.snapshot = snapshot;
      state.onboarding = onboarding;
      state.pendingApprovals = Array.isArray(pendingApprovals) ? pendingApprovals : [];
      state.pendingQuestions = Array.isArray(pendingQuestions) ? pendingQuestions : [];
      state.telegramReady = !!telegramReady;
      state.previewMeta = null;
    }

    const selectedWorkspaceExists = (state.snapshot?.workspaces || []).some(
      workspace => workspace.workspace_id === state.selectedWorkspaceId
    );
    if (!selectedWorkspaceExists) {
      state.selectedWorkspaceId = state.snapshot?.workspaces?.[0]?.workspace_id || null;
    }
    const selectedMissionExists = (state.snapshot?.missions || []).some(
      mission => mission.mission_id === state.selectedMissionId
    );
    if (!selectedMissionExists) {
      state.selectedMissionId = state.snapshot?.missions?.[state.snapshot?.missions?.length - 1]?.mission_id || null;
    }

    renderHero();
    renderGuidance();
    renderWorkspaces();
    renderMissionFormOptions();
    renderMissions();
    renderInbox();
    renderActivity();
    renderPlanner();
    renderSetup();
    renderRecommendations();
    renderSkillLibrary();
    syncLiveControls();
    liveRefresh.syncDevLoopStatus();
    liveRefresh.applyLiveSync();
    elements.telegramStatus.textContent = state.telegramReady
      ? 'Telegram bot token is stored securely. Test messages can be sent.'
      : 'Telegram bot token is not configured.';
    liveRefresh.syncRefreshStatus();
  } finally {
    state.refreshInFlight = false;
    if (state.refreshQueued) {
      state.refreshQueued = false;
      const queuedReason = state.queuedRefreshReason || 'queued';
      state.queuedRefreshReason = '';
      window.setTimeout(() => {
        liveRefresh.queueRefresh(queuedReason);
      }, 0);
    }
  }
}

async function sendTelegram(text) {
  const chatId = elements.telegramChatId.value.trim();
  if (!chatId) {
    toast('Set a Telegram chat id first.', 'error');
    return;
  }

  localStorage.setItem(STORAGE_KEYS.telegramChatId, chatId);
  try {
    await callBackend(
      'send_telegram_message_command',
      { payload: { chatId, text } },
      { throwOnError: true }
    );
    toast('Telegram message sent.', 'ok');
  } catch (error) {
    toast(`Telegram send failed: ${error}`, 'error');
  }
}

function setupEventListeners() {
  elements.refreshBtn.addEventListener('click', async () => {
    await refreshAll('manual');
  });

  elements.previewModeSelect.addEventListener('change', async event => {
    state.previewMode = event.target.value || 'live';
    localStorage.setItem(STORAGE_KEYS.previewMode, state.previewMode);
    await refreshAll('preview-mode-change');
  });

  elements.liveSyncSelect.addEventListener('change', event => {
    state.liveSyncSeconds = event.target.value || 'off';
    localStorage.setItem(STORAGE_KEYS.liveSyncSeconds, state.liveSyncSeconds);
    liveRefresh.applyLiveSync();
    toast(
      state.liveSyncSeconds === 'off'
        ? 'Live sync disabled.'
        : `Live sync set to every ${state.liveSyncSeconds}s.`,
      'ok'
    );
  });

  elements.workspaceForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (isPreviewMode()) {
      toast('Preview mode is read-only. Switch back to Live Backend to save workspaces.', 'info');
      return;
    }
    const name = document.getElementById('workspaceName').value.trim();
    const path = document.getElementById('workspacePath').value.trim();
    const defaultRuntime = document.getElementById('workspaceRuntime').value;
    const userProfile = document.getElementById('workspaceProfile').value;
    if (!name || !path) {
      toast('Workspace name and path are required.', 'error');
      return;
    }

    await callBackend(
      'save_workspace_profile_command',
      {
        payload: {
          root: null,
          workspaceId: null,
          name,
          path,
          defaultRuntime,
          userProfile,
        },
      },
      { throwOnError: true }
    );
    event.target.reset();
    toast('Workspace saved.', 'ok');
    await refreshAll('workspace-saved');
  });

  elements.missionForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (isPreviewMode()) {
      toast('Preview mode is read-only. Switch back to Live Backend to launch missions.', 'info');
      return;
    }
    const workspaceId = elements.missionWorkspace.value;
    const runtime = elements.missionRuntime.value;
    const mode = document.getElementById('missionMode').value;
    const profile = elements.missionProfile.value;
    const objective = document.getElementById('missionObjective').value.trim();
    const successChecks = document
      .getElementById('missionChecks')
      .value.split('\n')
      .map(line => line.trim())
      .filter(Boolean);
    const escalationDestination = elements.telegramChatId.value.trim();

    if (!objective) {
      toast('Mission objective is required.', 'error');
      return;
    }

    if (escalationDestination) {
      localStorage.setItem(STORAGE_KEYS.telegramChatId, escalationDestination);
    }

    await callBackend(
      'start_control_room_mission_command',
      {
        payload: {
          root: null,
          workspaceId,
          runtime,
          objective,
          successChecks,
          mode,
          profile,
          budgetHours: 12,
          escalationDestination,
        },
      },
      { throwOnError: true }
    );
    event.target.reset();
    elements.telegramChatId.value = localStorage.getItem(STORAGE_KEYS.telegramChatId) || '';
    toast('Mission launched.', 'ok');
    await refreshAll('mission-started');
  });

  elements.saveTelegramTokenBtn.addEventListener('click', async () => {
    if (isPreviewMode()) {
      toast('Preview mode is read-only. Switch back to Live Backend to update integrations.', 'info');
      return;
    }
    const token = elements.telegramBotToken.value.trim();
    if (!token) {
      toast('Enter a Telegram bot token first.', 'error');
      return;
    }
    await callBackend(
      'save_telegram_bot_token_command',
      { token },
      { throwOnError: true }
    );
    elements.telegramBotToken.value = '';
    state.telegramReady = true;
    elements.telegramStatus.textContent = 'Telegram bot token is stored securely.';
    toast('Telegram token saved.', 'ok');
  });

  elements.clearTelegramTokenBtn.addEventListener('click', async () => {
    if (isPreviewMode()) {
      toast('Preview mode is read-only. Switch back to Live Backend to update integrations.', 'info');
      return;
    }
    await callBackend('clear_telegram_bot_token_command', undefined, { throwOnError: true });
    state.telegramReady = false;
    elements.telegramStatus.textContent = 'Telegram bot token cleared.';
    toast('Telegram token cleared.', 'ok');
  });

  elements.sendTelegramTestBtn.addEventListener('click', async () => {
    if (isPreviewMode()) {
      toast('Preview mode is read-only. Switch back to Live Backend to send test messages.', 'info');
      return;
    }
    await sendTelegram('Fluxio test: phone escalation is configured and reachable.');
  });
}

async function initialize() {
  const storedChatId = localStorage.getItem(STORAGE_KEYS.telegramChatId) || '';
  const searchParams = new URLSearchParams(window.location.search);
  const fixtureParam = searchParams.get('fixture');
  const storedPreviewMode = localStorage.getItem(STORAGE_KEYS.previewMode) || 'live';
  const storedLiveSyncSeconds = localStorage.getItem(STORAGE_KEYS.liveSyncSeconds) || 'off';
  const availableModes = [{ id: 'live', name: 'Live Backend' }, ...listFixtureOptions()];
  elements.previewModeSelect.innerHTML = availableModes
    .map(option => `<option value="${escapeHtml(option.id)}">${escapeHtml(option.name)}</option>`)
    .join('');
  state.previewMode = fixtureParam || storedPreviewMode;
  if (!availableModes.some(option => option.id === state.previewMode)) {
    state.previewMode = 'live';
  }
  elements.previewModeSelect.value = state.previewMode;
  state.liveSyncSeconds = ['off', '1', '5', '15', '30'].includes(storedLiveSyncSeconds) ? storedLiveSyncSeconds : 'off';
  elements.liveSyncSelect.value = state.liveSyncSeconds;
  elements.telegramChatId.value = storedChatId;
  liveRefresh.syncDevLoopStatus();
  setupEventListeners();
  liveRefresh.bindWindowLifecycle();
  await liveRefresh.bindControlRoomEvents();
  await refreshAll('initialize');
}

document.addEventListener('DOMContentLoaded', initialize);
