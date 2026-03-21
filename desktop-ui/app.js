// Fluxio Desktop UI - Comprehensive App Controller
// =================================================

const STORAGE_KEYS = {
  CONVERSATIONS: 'vibe_conversations',
  FOLDERS: 'vibe_folders',
  ACTIVE_CONVERSATION: 'vibe_active_conversation',
  SETTINGS: 'vibe_settings',
  TUTORIAL_COMPLETE: 'vibe_tutorial_complete',
  PROVIDERS: 'vibe_providers',
  ACTIVE_PROVIDER: 'vibe_active_provider',
  SHORTCUTS: 'vibe_shortcuts'
};

const TASK_ROUTE_TYPES = [
  { id: 'frontend', label: 'Frontend' },
  { id: 'backend', label: 'Backend' },
  { id: 'verification', label: 'Verification' },
  { id: 'research', label: 'Research' },
  { id: 'general', label: 'General' }
];

const DEFAULT_TASK_MODEL_ROUTING = {
  frontend: { providerId: 'minimax', model: 'abab6.5s-chat' },
  backend: { providerId: 'codex', model: 'gpt-5-codex' },
  verification: { providerId: 'codex', model: 'gpt-5-codex' },
  research: { providerId: 'anthropic', model: 'claude-3-5-sonnet-20241022' },
  general: { providerId: 'openai', model: 'gpt-4o' }
};

const PERMISSION_CAPABILITIES = [
  { id: 'node.command', label: 'Node Command' },
  { id: 'shell.exec', label: 'Shell Exec' },
  { id: 'git.commit', label: 'Git Commit' },
  { id: 'git.push', label: 'Git Push' },
  { id: 'fs.delete', label: 'Delete Files' },
  { id: 'message.send', label: 'Message Send' },
  { id: 'context.capture', label: 'Context Capture' }
];

const DEFAULT_PERMISSION_MATRIX = {
  'node.command': 'ask',
  'shell.exec': 'ask',
  'git.commit': 'ask',
  'git.push': 'ask',
  'fs.delete': 'deny',
  'message.send': 'allow',
  'context.capture': 'allow'
};

const DEFAULT_PLUGINS = [
  { id: 'proof-panel', name: 'Proof Panel', enabled: true },
  { id: 'audit-timeline', name: 'Audit Timeline', enabled: true }
];

const DEFAULT_SKILLS = [
  { id: 'repo-scan', name: 'Repo Scan', enabled: true },
  { id: 'release-checklist', name: 'Release Checklist', enabled: false }
];

const DEFAULT_SETTINGS = {
  theme: 'default',
  font: 'default',
  pinned: true,
  soundEnabled: true,
  notificationsEnabled: true,
  voiceEnabled: true,
  voiceMode: 'push',
  showAllNotifications: true,
  notifyOnQuestion: true,
  notifyOnMessage: true,
  notifyOnCompletion: true,
  notifyOnError: true,
  autoImportConversations: true,
  profilePreset: 'hands_free_builder',
  agentMode: 'profile',
  parallelAgents: 3,
  mergePolicy: 'consensus',
  pauseOnVerificationFailure: true,
  openclawGatewayUrl: 'ws://127.0.0.1:8765',
  taskModelRouting: DEFAULT_TASK_MODEL_ROUTING,
  permissionMatrix: DEFAULT_PERMISSION_MATRIX,
  mcpServers: [],
  plugins: DEFAULT_PLUGINS,
  skills: DEFAULT_SKILLS,
  runLiveCommand: 'npm run dev:live',
  runLiveCwd: ''
};

const PROFILE_PRESETS = {
  minimal_focus: {
    theme: 'default',
    font: 'compact',
    pinned: true,
    voiceMode: 'push',
    notificationsEnabled: false,
    showAllNotifications: false,
    agentMode: 'fast',
    parallelAgents: 1,
    mergePolicy: 'risk_averse',
    pauseOnVerificationFailure: true
  },
  hands_free_builder: {
    theme: 'default',
    font: 'default',
    pinned: true,
    voiceMode: 'always',
    notificationsEnabled: true,
    showAllNotifications: true,
    agentMode: 'autopilot',
    parallelAgents: 3,
    mergePolicy: 'consensus',
    pauseOnVerificationFailure: true
  },
  research_sprint: {
    theme: 'midnight',
    font: 'default',
    pinned: true,
    voiceMode: 'push',
    notificationsEnabled: true,
    showAllNotifications: true,
    agentMode: 'swarms',
    parallelAgents: 5,
    mergePolicy: 'best_score',
    pauseOnVerificationFailure: false
  },
  safety_gate: {
    theme: 'forest',
    font: 'compact',
    pinned: true,
    voiceMode: 'push',
    notificationsEnabled: true,
    showAllNotifications: true,
    agentMode: 'careful',
    parallelAgents: 1,
    mergePolicy: 'risk_averse',
    pauseOnVerificationFailure: true
  }
};

const DEFAULT_PROVIDERS = [
  // Major AI Labs (Quality Tested)
  { id: 'openai', name: 'OpenAI GPT-4o', icon: '🤖', baseUrl: 'https://api.openai.com/v1', authType: 'api_key', defaultModel: 'gpt-4o' },
  { id: 'anthropic', name: 'Anthropic Claude 3.5', icon: '🧠', baseUrl: 'https://api.anthropic.com/v1', authType: 'api_key', defaultModel: 'claude-3-5-sonnet-20241022' },
  { id: 'google', name: 'Google Gemini 1.5', icon: '🔵', baseUrl: 'https://generativelanguage.googleapis.com/v1', authType: 'api_key', defaultModel: 'gemini-1.5-pro' },
  { id: 'xai', name: 'xAI Grok 2', icon: '✨', baseUrl: 'https://api.x.ai/v1', authType: 'api_key', defaultModel: 'grok-2-1212' },
  
  // Open Source Alternatives
  { id: 'meta-llama', name: 'Meta Llama 3.1', icon: '🦙', baseUrl: 'https://api.together.xyz/v1', authType: 'api_key', defaultModel: 'meta-llama/Llama-3.1-70B-Instruct-Turbo' },
  { id: 'mistral', name: 'Mistral Large', icon: '🌫️', baseUrl: 'https://api.mistral.ai/v1', authType: 'api_key', defaultModel: 'mistral-large-latest' },
  { id: 'cohere', name: 'Cohere Command R+', icon: '🌊', baseUrl: 'https://api.cohere.ai/v1', authType: 'api_key', defaultModel: 'command-r-plus' },
  { id: 'deepseek', name: 'DeepSeek Chat', icon: '🔍', baseUrl: 'https://api.deepseek.com/v1', authType: 'api_key', defaultModel: 'deepseek-chat' },
  { id: 'minimax', name: 'MiniMax', icon: '🔮', baseUrl: 'https://api.minimax.chat/v1', authType: 'bearer', defaultModel: 'abab6.5s-chat' },
  
  // Code Specialization
  { id: 'codex', name: 'OpenAI Codex', icon: '💻', baseUrl: 'https://api.openai.com/v1', authType: 'api_key', defaultModel: 'gpt-5-codex' },
  
  // Cloud & Enterprise
  { id: 'azure', name: 'Azure OpenAI', icon: '☁️', baseUrl: 'https://YOUR_RESOURCE.openai.azure.com/openai/v1', authType: 'api_key', defaultModel: 'gpt-4' },
  { id: 'bedrock', name: 'AWS Bedrock', icon: '🗻', baseUrl: 'https://bedrock-runtime.REGION.amazonaws.com', authType: 'aws', defaultModel: 'anthropic.claude-3-sonnet-20240229' },
  
  // Local (Optional)
  { id: 'ollama', name: 'Ollama (Local)', icon: '💻', baseUrl: 'http://localhost:11434/v1', authType: 'none', defaultModel: 'llama3.1' },
];

const DEFAULT_SHORTCUTS = [
  { id: 'new_chat', name: 'New Chat', desc: 'Start a new conversation', keys: 'Ctrl+Shift+N', action: 'newChat' },
  { id: 'toggle_pin', name: 'Toggle Pin', desc: 'Pin/unpin overlay', keys: 'Ctrl+Shift+P', action: 'togglePin' },
  { id: 'settings', name: 'Settings', desc: 'Open settings', keys: 'Ctrl+,', action: 'openSettings' },
  { id: 'command_palette', name: 'Command Palette', desc: 'Quick actions', keys: 'Ctrl+K', action: 'openCommandPalette' },
  { id: 'voice', name: 'Voice Input', desc: 'Start voice recording', keys: 'Ctrl+Shift+V', action: 'voiceRecord' },
  { id: 'toggle_sidebar', name: 'Toggle Sidebar', desc: 'Show/hide sidebar', keys: 'Ctrl+B', action: 'toggleSidebar' },
  { id: 'vibe_status', name: 'Vibe Status', desc: 'Fetch latest autonomous status', keys: '', action: 'vibeStatus' },
  { id: 'vibe_continue', name: 'Vibe Continue', desc: 'Continue autonomous run cycle', keys: '', action: 'continueAutonomy' },
  { id: 'run_soak', name: 'Run Soak', desc: 'Start a soak validation cycle', keys: '', action: 'runSoak' }
];

const DEFAULT_MODES = ['coding', 'youtube', 'writing'];
const MODE_ICONS = {
  coding: '⌨️',
  youtube: '📺',
  writing: '✍️'
};

const FOLDER_COLORS = ['red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink'];

// State
const appState = {
  conversations: [],
  folders: [],
  activeConversationId: null,
  settings: normalizeSettings(DEFAULT_SETTINGS),
  providers: [...DEFAULT_PROVIDERS],
  activeProvider: null,
  providerSecretPresence: {},
  openclawStatus: {
    connected: false,
    gatewayUrl: null,
    lastError: null,
    lastEventAt: null,
    lastConnectedAt: null,
    reconnectAttempt: 0,
    queuedOutbound: 0,
    pendingAckCount: 0
  },
  autonomySnapshot: null,
  lastAutonomyOutput: 'Run output will appear here.',
  shortcuts: [...DEFAULT_SHORTCUTS],
  isRecording: false,
  tutorialComplete: false,
  editingProviderId: null,
  selectedProviderTemplateId: null,
  conversationSearchQuery: '',
  activeInsightPanel: 'lineage',
  runLiveInFlight: false
};

// DOM Elements
const elements = {
  splashScreen: document.getElementById('splashScreen'),
  appContainer: document.getElementById('appContainer'),
  sidebar: document.getElementById('sidebar'),
  conversationList: document.getElementById('conversationList'),
  folderList: document.getElementById('folderList'),
  messagesContainer: document.getElementById('messagesContainer'),
  promptInput: document.getElementById('promptInput'),
  sendBtn: document.getElementById('sendBtn'),
  voiceBtn: document.getElementById('voiceBtn'),
  conversationTitle: document.getElementById('conversationTitle'),
  modeBadge: document.getElementById('modeBadge'),
  settingsOverlay: document.getElementById('settingsOverlay'),
  tutorialOverlay: document.getElementById('tutorialOverlay'),
  providerModal: document.getElementById('providerModal'),
  commandPalette: document.getElementById('commandPalette'),
  newChatBtn: document.getElementById('newChatBtn'),
  settingsBtn: document.getElementById('settingsBtn'),
  menuBtn: document.getElementById('menuBtn'),
  settingsCloseBtn: document.getElementById('settingsCloseBtn'),
  toggleSidebarBtn: document.getElementById('toggleSidebarBtn'),
  themeSelector: document.getElementById('themeSelector'),
  fontSelector: document.getElementById('fontSelector'),
  pinToggle: document.getElementById('pinToggle'),
  soundToggle: document.getElementById('soundToggle'),
  notificationToggle: document.getElementById('notificationToggle'),
  voiceToggle: document.getElementById('voiceToggle'),
  voiceModeSelector: document.getElementById('voiceModeSelector'),
  providersList: document.getElementById('providersList'),
  addProviderBtn: document.getElementById('addProviderBtn'),
  providerModalTitle: document.getElementById('providerModalTitle'),
  providerModalClose: document.getElementById('providerModalClose'),
  providerTypeGrid: document.getElementById('providerTypeGrid'),
  providerConfig: document.getElementById('providerConfig'),
  providerCancelBtn: document.getElementById('providerCancelBtn'),
  providerSaveBtn: document.getElementById('providerSaveBtn'),
  modelSelector: document.getElementById('modelSelector'),
  commandInput: document.getElementById('commandInput'),
  commandList: document.getElementById('commandList'),
  autonomyUpdatedValue: document.getElementById('autonomyUpdatedValue'),
  autonomySessionValue: document.getElementById('autonomySessionValue'),
  autonomyStatusValue: document.getElementById('autonomyStatusValue'),
  autonomyMergeValue: document.getElementById('autonomyMergeValue'),
  autonomyCheckpointsValue: document.getElementById('autonomyCheckpointsValue'),
  autonomyRemainingValue: document.getElementById('autonomyRemainingValue'),
  autonomyApprovalsValue: document.getElementById('autonomyApprovalsValue'),
  autonomyRefreshBtn: document.getElementById('autonomyRefreshBtn'),
  autonomyVibeStatusBtn: document.getElementById('autonomyVibeStatusBtn'),
  autonomyCyclesInput: document.getElementById('autonomyCyclesInput'),
  autonomyIterationsInput: document.getElementById('autonomyIterationsInput'),
  autonomyContinueBtn: document.getElementById('autonomyContinueBtn'),
  autonomySoakBtn: document.getElementById('autonomySoakBtn'),
  autonomyOutput: document.getElementById('autonomyOutput'),
  tutorialTitle: document.getElementById('tutorialTitle'),
  tutorialText: document.getElementById('tutorialText'),
  tutorialBtn: document.getElementById('tutorialBtn'),
  showAllNotificationsToggle: document.getElementById('showAllNotificationsToggle'),
  notifyQuestionToggle: document.getElementById('notifyQuestionToggle'),
  notifyMessageToggle: document.getElementById('notifyMessageToggle'),
  notifyCompletionToggle: document.getElementById('notifyCompletionToggle'),
  notifyErrorToggle: document.getElementById('notifyErrorToggle'),
  autoImportToggle: document.getElementById('autoImportToggle'),
  profilePresetSelector: document.getElementById('profilePresetSelector'),
  applyProfilePresetBtn: document.getElementById('applyProfilePresetBtn'),
  agentModeSelector: document.getElementById('agentModeSelector'),
  parallelAgentsInput: document.getElementById('parallelAgentsInput'),
  mergePolicySelector: document.getElementById('mergePolicySelector'),
  agentPauseOnFailToggle: document.getElementById('agentPauseOnFailToggle'),
  modelRoutingGrid: document.getElementById('modelRoutingGrid'),
  openclawStatusBadge: document.getElementById('openclawStatusBadge'),
  openclawStatusText: document.getElementById('openclawStatusText'),
  openclawToggleBtn: document.getElementById('openclawToggleBtn'),
  openclawGatewayUrlInput: document.getElementById('openclawGatewayUrlInput'),
  conversationSearchInput: document.getElementById('conversationSearchInput'),
  forkConversationBtn: document.getElementById('forkConversationBtn'),
  runLiveBtn: document.getElementById('runLiveBtn'),
  autonomyRunLiveBtn: document.getElementById('autonomyRunLiveBtn'),
  runLiveFromSettingsBtn: document.getElementById('runLiveFromSettingsBtn'),
  runLiveCommandInput: document.getElementById('runLiveCommandInput'),
  runLiveCwdInput: document.getElementById('runLiveCwdInput'),
  permissionGrid: document.getElementById('permissionGrid'),
  addMcpServerBtn: document.getElementById('addMcpServerBtn'),
  mcpServersList: document.getElementById('mcpServersList'),
  pluginsList: document.getElementById('pluginsList'),
  skillsList: document.getElementById('skillsList'),
  insightTabs: document.getElementById('insightTabs'),
  insightLineagePanel: document.getElementById('insightLineagePanel'),
  insightRiskPanel: document.getElementById('insightRiskPanel'),
  insightIntegrationsPanel: document.getElementById('insightIntegrationsPanel'),
  lineageOutput: document.getElementById('lineageOutput'),
  riskOutput: document.getElementById('riskOutput'),
  integrationOutput: document.getElementById('integrationOutput'),
  importChatGPTBtn: document.getElementById('importChatGPTBtn'),
  importClaudeBtn: document.getElementById('importClaudeBtn'),
  importJsonBtn: document.getElementById('importJsonBtn'),
  importFileInput: document.getElementById('importFileInput'),
  providerQuickKey: document.getElementById('providerQuickKey'),
  providerAuthHelp: document.getElementById('providerAuthHelp')
};

// Tauri API
const invoke = window.__TAURI__?.core?.invoke;
const listen = window.__TAURI__?.event?.listen;

// ====================
// Storage Functions
// ====================

function loadFromStorage(key, defaultValue) {
  try {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : defaultValue;
  } catch {
    return defaultValue;
  }
}

function saveToStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.error('Storage error:', e);
  }
}

function cloneTaskModelRouting(source = DEFAULT_TASK_MODEL_ROUTING) {
  const output = {};
  TASK_ROUTE_TYPES.forEach(route => {
    const fallback = DEFAULT_TASK_MODEL_ROUTING[route.id] || { providerId: 'openai', model: '' };
    const current = source?.[route.id] || fallback;
    output[route.id] = {
      providerId: typeof current.providerId === 'string' ? current.providerId : fallback.providerId,
      model: typeof current.model === 'string' ? current.model : fallback.model
    };
  });
  return output;
}

function normalizeTaskModelRouting(rawRouting) {
  return cloneTaskModelRouting(rawRouting || DEFAULT_TASK_MODEL_ROUTING);
}

function normalizePermissionMatrix(rawMatrix) {
  const matrix = { ...DEFAULT_PERMISSION_MATRIX };
  const source = rawMatrix && typeof rawMatrix === 'object' ? rawMatrix : {};
  PERMISSION_CAPABILITIES.forEach(capability => {
    const value = source[capability.id];
    matrix[capability.id] = ['allow', 'ask', 'deny'].includes(value) ? value : matrix[capability.id];
  });
  return matrix;
}

function normalizeIntegrationList(rawList, fallbackList) {
  const list = Array.isArray(rawList) ? rawList : fallbackList;
  return list
    .map((item, index) => {
      const id = String(item?.id || item?.name || `item_${index + 1}`).trim().toLowerCase().replace(/\s+/g, '-');
      const name = String(item?.name || item?.id || `Item ${index + 1}`).trim();
      if (!name) {
        return null;
      }
      return {
        id,
        name,
        enabled: item?.enabled !== false
      };
    })
    .filter(Boolean);
}

function normalizeMcpServers(rawList) {
  const list = Array.isArray(rawList) ? rawList : [];
  return list
    .map((item, index) => {
      const name = String(item?.name || `MCP Server ${index + 1}`).trim();
      const command = String(item?.command || '').trim();
      const args = Array.isArray(item?.args)
        ? item.args.map(value => String(value || '').trim()).filter(Boolean)
        : [];
      if (!name) {
        return null;
      }
      return {
        id: String(item?.id || `${name.toLowerCase().replace(/\s+/g, '-')}-${index + 1}`),
        name,
        command,
        args,
        enabled: item?.enabled !== false
      };
    })
    .filter(Boolean);
}

function normalizeProviderRecord(provider, index) {
  const normalized = {
    id: provider?.id || `provider_${index + 1}`,
    name: provider?.name || `Provider ${index + 1}`,
    icon: provider?.icon || '🔑',
    baseUrl: provider?.baseUrl || '',
    authType: provider?.authType || 'api_key',
    defaultModel: provider?.defaultModel || '',
    secretStored: !!provider?.secretStored
  };

  if (normalized.id === 'codex') {
    normalized.authType = 'api_key';
    if (!normalized.baseUrl || normalized.baseUrl.includes('YOUR_RESOURCE')) {
      normalized.baseUrl = 'https://api.openai.com/v1';
    }
    if (!normalized.defaultModel || normalized.defaultModel === 'code-davinci-002') {
      normalized.defaultModel = 'gpt-5-codex';
    }
  }

  if (normalized.id === 'minimax') {
    normalized.authType = 'bearer';
    if (!normalized.baseUrl || normalized.baseUrl.includes('YOUR_RESOURCE')) {
      normalized.baseUrl = 'https://api.minimax.chat/v1';
    }
    if (!normalized.defaultModel) {
      normalized.defaultModel = 'abab6.5s-chat';
    }
  }

  return normalized;
}

function ensureCoreProviders(providers) {
  const output = [...providers];
  ['minimax', 'codex'].forEach(coreId => {
    if (output.some(provider => provider.id === coreId)) {
      return;
    }
    const template = DEFAULT_PROVIDERS.find(provider => provider.id === coreId);
    if (template) {
      output.push(normalizeProviderRecord(template, output.length));
    }
  });
  return output;
}

function normalizeSettings(rawSettings) {
  const merged = {
    ...DEFAULT_SETTINGS,
    ...(rawSettings || {})
  };
  merged.taskModelRouting = normalizeTaskModelRouting(rawSettings?.taskModelRouting || merged.taskModelRouting);
  merged.permissionMatrix = normalizePermissionMatrix(rawSettings?.permissionMatrix || merged.permissionMatrix);
  merged.mcpServers = normalizeMcpServers(rawSettings?.mcpServers || merged.mcpServers);
  merged.plugins = normalizeIntegrationList(rawSettings?.plugins, DEFAULT_PLUGINS);
  merged.skills = normalizeIntegrationList(rawSettings?.skills, DEFAULT_SKILLS);
  merged.runLiveCommand = typeof merged.runLiveCommand === 'string' && merged.runLiveCommand.trim()
    ? merged.runLiveCommand.trim()
    : DEFAULT_SETTINGS.runLiveCommand;
  merged.runLiveCwd = typeof merged.runLiveCwd === 'string' ? merged.runLiveCwd.trim() : '';
  return merged;
}

function loadConversations() {
  return loadFromStorage(STORAGE_KEYS.CONVERSATIONS, []);
}

function saveConversations() {
  saveToStorage(STORAGE_KEYS.CONVERSATIONS, appState.conversations);
}

function loadFolders() {
  return loadFromStorage(STORAGE_KEYS.FOLDERS, [
    { id: 'default', name: 'General', count: 0, color: 'blue' },
    { id: 'work', name: 'Work', count: 0, color: 'green' },
    { id: 'personal', name: 'Personal', count: 0, color: 'purple' },
    { id: 'projects', name: 'Projects', count: 0, color: 'orange' }
  ]);
}

function saveFolders() {
  saveToStorage(STORAGE_KEYS.FOLDERS, appState.folders);
}

function loadSettings() {
  const stored = loadFromStorage(STORAGE_KEYS.SETTINGS, {});
  return normalizeSettings(stored || {});
}

function saveSettings() {
  saveToStorage(STORAGE_KEYS.SETTINGS, appState.settings);
}

function loadProviders() {
  const stored = loadFromStorage(STORAGE_KEYS.PROVIDERS, null);
  if (stored && stored.length > 0) {
    return ensureCoreProviders(
      stored.map((provider, index) => normalizeProviderRecord(provider, index))
    );
  }
  return ensureCoreProviders(
    DEFAULT_PROVIDERS.map((provider, index) => normalizeProviderRecord(provider, index))
  );
}

function saveProviders() {
  saveToStorage(STORAGE_KEYS.PROVIDERS, appState.providers);
}

function loadActiveProvider() {
  return loadFromStorage(STORAGE_KEYS.ACTIVE_PROVIDER, 'openai');
}

function saveActiveProvider(id) {
  saveToStorage(STORAGE_KEYS.ACTIVE_PROVIDER, id);
}

function loadShortcuts() {
  return loadFromStorage(STORAGE_KEYS.SHORTCUTS, DEFAULT_SHORTCUTS);
}

function saveShortcuts() {
  saveToStorage(STORAGE_KEYS.SHORTCUTS, appState.shortcuts);
}

function loadActiveConversation() {
  return loadFromStorage(STORAGE_KEYS.ACTIVE_CONVERSATION, null);
}

function saveActiveConversation(id) {
  saveToStorage(STORAGE_KEYS.ACTIVE_CONVERSATION, id);
}

// ====================
// Conversation Management
// ====================

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

function createConversation(title = 'New Conversation') {
  const conversation = {
    id: generateId(),
    title,
    mode: 'coding',
    folderId: 'default',
    providerId: appState.activeProvider,
    parentId: null,
    messages: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
  
  appState.conversations.unshift(conversation);
  saveConversations();
  
  return conversation;
}

function updateConversation(id, updates) {
  const index = appState.conversations.findIndex(c => c.id === id);
  if (index !== -1) {
    appState.conversations[index] = {
      ...appState.conversations[index],
      ...updates,
      updatedAt: new Date().toISOString()
    };
    saveConversations();
  }
}

function deleteConversation(id) {
  appState.conversations = appState.conversations.filter(c => c.id !== id);
  saveConversations();
  
  if (appState.activeConversationId === id) {
    appState.activeConversationId = appState.conversations[0]?.id || null;
    saveActiveConversation(appState.activeConversationId);
    renderActiveConversation();
  }
  
  renderConversationList();
}

function setActiveConversation(id) {
  appState.activeConversationId = id;
  saveActiveConversation(id);
  renderActiveConversation();
  renderConversationList();
  void refreshMissionControl();
}

function addMessage(content, role = 'user') {
  if (!appState.activeConversationId) {
    const conv = createConversation();
    setActiveConversation(conv.id);
  }
  
  const conversation = appState.conversations.find(c => c.id === appState.activeConversationId);
  if (!conversation) return;
  
  const message = {
    id: generateId(),
    content,
    role,
    timestamp: new Date().toISOString()
  };
  
  conversation.messages.push(message);
  updateConversation(conversation.id, { messages: conversation.messages });
  void refreshMissionControl();
  
  return message;
}

// ====================
// Folder Management
// ====================

function createFolder(name, color = 'blue') {
  const folder = {
    id: generateId(),
    name,
    color,
    count: 0
  };
  
  appState.folders.push(folder);
  saveFolders();
  renderFolderList();
  
  return folder;
}

function moveToFolder(conversationId, folderId) {
  const conv = appState.conversations.find(c => c.id === conversationId);
  if (conv) {
    updateConversation(conversationId, { folderId });
    updateFolderCounts();
  }
}

function updateFolderCounts() {
  appState.folders.forEach(folder => {
    folder.count = appState.conversations.filter(c => c.folderId === folder.id).length;
  });
  saveFolders();
  renderFolderList();
}

// ====================
// Provider Management
// ====================

function renderProvidersList() {
  const list = elements.providersList;
  list.innerHTML = '';
  
  appState.providers.forEach(provider => {
    const item = document.createElement('div');
    item.className = `provider-item ${provider.id === appState.activeProvider ? 'active' : ''}`;
    item.dataset.id = provider.id;
    
    const hasSecret = appState.providerSecretPresence[provider.id] ?? provider.secretStored ?? false;
    const isConnected = provider.authType === 'none' || hasSecret;
    provider.secretStored = isConnected;
    const authHint = provider.authType === 'bearer'
      ? 'Bearer token'
      : provider.authType === 'api_key'
        ? 'API key'
        : provider.authType;
    const connectionText = isConnected ? `Connected (${authHint})` : `Add ${authHint}`;
    
    item.innerHTML = `
      <div class="provider-icon">${provider.icon}</div>
      <div class="provider-info">
        <div class="provider-name">${escapeHtml(provider.name)}</div>
        <div class="provider-status ${isConnected ? 'connected' : ''}">${escapeHtml(connectionText)}</div>
      </div>
      <div class="provider-actions">
        <button class="icon-btn provider-edit-btn" title="Edit">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </button>
        <button class="icon-btn provider-delete-btn" title="Delete">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      </div>
    `;
    
    item.addEventListener('click', (e) => {
      if (!e.target.closest('.provider-actions')) {
        setActiveProvider(provider.id);
      }
    });
    
    item.querySelector('.provider-edit-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      editProvider(provider.id);
    });
    
    item.querySelector('.provider-delete-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      deleteProvider(provider.id);
    });
    
    list.appendChild(item);
  });
  
  updateModelSelector();
  renderTaskModelRoutingControls();
}

function setActiveProvider(providerId) {
  appState.activeProvider = providerId;
  saveActiveProvider(providerId);
  renderProvidersList();
  
  const conversation = appState.conversations.find(c => c.id === appState.activeConversationId);
  if (conversation) {
    updateConversation(conversation.id, { providerId });
  }
}

function editProvider(providerId) {
  const provider = appState.providers.find(p => p.id === providerId);
  if (!provider) return;
  
  appState.editingProviderId = providerId;
  appState.selectedProviderTemplateId = null;
  elements.providerModalTitle.textContent = `Edit ${provider.name}`;
  
  document.getElementById('providerName').value = provider.name;
  document.getElementById('providerBaseUrl').value = provider.baseUrl || '';
  document.getElementById('providerAuthType').value = provider.authType || 'api_key';
  document.getElementById('providerDefaultModel').value = provider.defaultModel || '';
  document.getElementById('providerQuickKey').value = '';
  
  updateAuthFieldsVisibility();
  openProviderModal();
}

async function deleteProvider(providerId) {
  if (confirm('Are you sure you want to delete this provider?')) {
    await callBackend('clear_provider_secret_command', { provider_id: providerId });
    delete appState.providerSecretPresence[providerId];
    appState.providers = appState.providers.filter(p => p.id !== providerId);
    saveProviders();
    
    if (appState.activeProvider === providerId) {
      appState.activeProvider = appState.providers[0]?.id || null;
      saveActiveProvider(appState.activeProvider);
    }
    
    renderProvidersList();
  }
}

async function saveProviderConfig() {
  const name = document.getElementById('providerName').value.trim();
  const baseUrl = document.getElementById('providerBaseUrl').value.trim();
  const authType = document.getElementById('providerAuthType').value;
  const defaultModel = document.getElementById('providerDefaultModel').value.trim();

  if (!name) {
    alert('Provider name is required.');
    return;
  }

  let providerId = appState.editingProviderId || appState.selectedProviderTemplateId || generateId();
  if (!appState.editingProviderId && appState.providers.some(provider => provider.id === providerId)) {
    providerId = generateId();
  }

  let secret = document.getElementById('providerQuickKey').value.trim();
  if (!secret) {
    if (authType === 'api_key') {
      secret = document.getElementById('providerApiKey').value.trim();
    } else if (authType === 'bearer') {
      secret = document.getElementById('providerBearerToken').value.trim();
    } else if (authType === 'basic') {
      const username = document.getElementById('providerUsername').value.trim();
      const password = document.getElementById('providerPassword').value.trim();
      if (username || password) {
        secret = JSON.stringify({ username, password });
      }
    } else if (authType === 'oauth') {
      const oauthBundle = {
        clientId: document.getElementById('providerOauthClientId').value.trim(),
        clientSecret: document.getElementById('providerOauthClientSecret').value.trim(),
        authUrl: document.getElementById('providerOauthAuthUrl').value.trim(),
        tokenUrl: document.getElementById('providerOauthTokenUrl').value.trim()
      };
      if (oauthBundle.clientId || oauthBundle.clientSecret || oauthBundle.authUrl || oauthBundle.tokenUrl) {
        secret = JSON.stringify(oauthBundle);
      }
    }
  }

  let secretStored = authType === 'none';
  if (!secretStored) {
    secretStored = !!appState.providerSecretPresence[providerId];
    if (secret) {
      const stored = await callBackend('save_provider_secret_command', {
        provider_id: providerId,
        secret
      });
      if (stored) {
        secretStored = true;
      } else {
        alert('Failed to store provider secret securely. Please retry.');
      }
    }
  }

  if (appState.editingProviderId) {
    const provider = appState.providers.find(p => p.id === appState.editingProviderId);
    if (provider) {
      const normalized = normalizeProviderRecord(
        {
          ...provider,
          name,
          baseUrl,
          authType,
          defaultModel,
          secretStored
        },
        0
      );
      provider.name = normalized.name;
      provider.baseUrl = normalized.baseUrl;
      provider.authType = normalized.authType;
      provider.defaultModel = normalized.defaultModel;
      provider.secretStored = secretStored;
    }
  } else {
    const newProvider = normalizeProviderRecord({
      id: providerId,
      name,
      icon: '🔑',
      baseUrl,
      authType,
      defaultModel,
      secretStored
    }, appState.providers.length);
    appState.providers.push(newProvider);

    if (!appState.activeProvider) {
      appState.activeProvider = newProvider.id;
      saveActiveProvider(newProvider.id);
    }
  }

  appState.providerSecretPresence[providerId] = secretStored;
  saveProviders();
  await syncProviderSecretPresence();
  renderProvidersList();
  closeProviderModal();
}

function openProviderModal() {
  elements.providerModal.classList.add('open');
  updateProviderAuthHelp();
}

function closeProviderModal() {
  elements.providerModal.classList.remove('open');
  appState.editingProviderId = null;
  appState.selectedProviderTemplateId = null;
  document.getElementById('providerName').value = '';
  document.getElementById('providerBaseUrl').value = '';
  document.getElementById('providerAuthType').value = 'api_key';
  document.getElementById('providerDefaultModel').value = '';
  document.getElementById('providerApiKey').value = '';
  document.getElementById('providerBearerToken').value = '';
  document.getElementById('providerUsername').value = '';
  document.getElementById('providerPassword').value = '';
  document.getElementById('providerOauthClientId').value = '';
  document.getElementById('providerOauthClientSecret').value = '';
  document.getElementById('providerOauthAuthUrl').value = '';
  document.getElementById('providerOauthTokenUrl').value = '';
  document.getElementById('providerQuickKey').value = '';
  updateProviderAuthHelp();
}

function updateAuthFieldsVisibility() {
  const authType = document.getElementById('providerAuthType').value;
  
  document.getElementById('apiKeyGroup').classList.toggle('hidden', authType !== 'api_key');
  document.getElementById('bearerGroup').classList.toggle('hidden', authType !== 'bearer');
  document.getElementById('basicGroup').classList.toggle('hidden', authType !== 'basic');
  document.getElementById('oauthGroup').classList.toggle('hidden', authType !== 'oauth');
  updateProviderAuthHelp();
}

function updateProviderAuthHelp() {
  if (!elements.providerAuthHelp) {
    return;
  }

  const authType = document.getElementById('providerAuthType').value;
  const providerName = (document.getElementById('providerName').value || '').toLowerCase();
  const baseHelp = 'Stored securely in your OS keychain. Not saved in plain app storage.';

  if (providerName.includes('codex') || providerName.includes('openai')) {
    elements.providerAuthHelp.textContent = `Codex/OpenAI should use API key auth. ${baseHelp}`;
    return;
  }

  if (providerName.includes('minimax')) {
    elements.providerAuthHelp.textContent = `MiniMax should use bearer token auth. ${baseHelp}`;
    return;
  }

  if (authType === 'bearer') {
    elements.providerAuthHelp.textContent = `Use bearer token format for this provider. ${baseHelp}`;
    return;
  }
  if (authType === 'api_key') {
    elements.providerAuthHelp.textContent = `Use API key format for this provider. ${baseHelp}`;
    return;
  }

  elements.providerAuthHelp.textContent = baseHelp;
}

function updateModelSelector() {
  const selector = elements.modelSelector;
  selector.innerHTML = '';
  
  appState.providers.forEach(provider => {
    const option = document.createElement('option');
    option.value = provider.id;
    option.textContent = `${provider.name} (${provider.defaultModel || 'default'})`;
    option.selected = provider.id === appState.activeProvider;
    selector.appendChild(option);
  });
}

function getProviderById(providerId) {
  return appState.providers.find(provider => provider.id === providerId) || null;
}

function providerHasCredential(providerId) {
  const provider = getProviderById(providerId);
  if (!provider) {
    return false;
  }
  if (provider.authType === 'none') {
    return true;
  }
  return !!(appState.providerSecretPresence[provider.id] ?? provider.secretStored);
}

function getTaskRouteConfig(taskType) {
  const fallback = DEFAULT_TASK_MODEL_ROUTING[taskType] || DEFAULT_TASK_MODEL_ROUTING.general;
  const current = appState.settings.taskModelRouting?.[taskType] || fallback;
  return {
    providerId: typeof current.providerId === 'string' ? current.providerId : fallback.providerId,
    model: typeof current.model === 'string' ? current.model : fallback.model
  };
}

function resolveTaskRoute(taskType) {
  const config = getTaskRouteConfig(taskType);
  const fallback = DEFAULT_TASK_MODEL_ROUTING[taskType] || DEFAULT_TASK_MODEL_ROUTING.general;
  const provider = getProviderById(config.providerId)
    || getProviderById(fallback.providerId)
    || getProviderById(appState.activeProvider)
    || appState.providers[0]
    || null;

  const model = (config.model || '').trim() || provider?.defaultModel || '';
  return {
    taskType,
    providerId: provider?.id || config.providerId || fallback.providerId,
    providerName: provider?.name || config.providerId || 'Unknown provider',
    authType: provider?.authType || 'api_key',
    model
  };
}

function buildResolvedTaskRoutingMap() {
  const output = {};
  TASK_ROUTE_TYPES.forEach(route => {
    const resolved = resolveTaskRoute(route.id);
    output[route.id] = {
      providerId: resolved.providerId,
      model: resolved.model
    };
  });
  return output;
}

function inferTaskTypeFromPrompt(text, mode) {
  const source = `${mode || ''} ${text || ''}`.toLowerCase();

  const verificationHints = [
    'verify', 'verification', 'review', 'test', 'tests', 'lint', 'qa', 'regression', 'assert', 'failing test'
  ];
  if (verificationHints.some(hint => source.includes(hint))) {
    return 'verification';
  }

  const frontendHints = [
    'frontend', 'ui', 'ux', 'css', 'html', 'react', 'vue', 'svelte', 'tailwind', 'component', 'responsive', 'layout'
  ];
  if (frontendHints.some(hint => source.includes(hint))) {
    return 'frontend';
  }

  const backendHints = [
    'backend', 'api', 'server', 'database', 'endpoint', 'service', 'migration', 'schema', 'auth', 'jwt', 'orm'
  ];
  if (backendHints.some(hint => source.includes(hint))) {
    return 'backend';
  }

  const researchHints = [
    'research', 'investigate', 'explore', 'compare', 'benchmark', 'analyze', 'spike', 'read docs'
  ];
  if (researchHints.some(hint => source.includes(hint))) {
    return 'research';
  }

  if ((mode || '').toLowerCase() === 'writing') {
    return 'research';
  }

  return 'general';
}

function computePromptRouting(text) {
  const conversation = appState.conversations.find(conv => conv.id === appState.activeConversationId);
  const taskType = inferTaskTypeFromPrompt(text, conversation?.mode);
  const primaryRoute = resolveTaskRoute(taskType);
  const verificationRoute = resolveTaskRoute('verification');
  const routingMap = buildResolvedTaskRoutingMap();

  return {
    taskType,
    primaryRoute,
    verificationRoute,
    routingMap
  };
}

function renderTaskModelRoutingControls() {
  const container = elements.modelRoutingGrid;
  if (!container) {
    return;
  }

  container.innerHTML = '';
  TASK_ROUTE_TYPES.forEach(route => {
    const config = getTaskRouteConfig(route.id);
    const resolved = resolveTaskRoute(route.id);

    const row = document.createElement('div');
    row.className = 'model-route-row';
    row.innerHTML = `
      <div class="model-route-header">
        <span class="model-route-label">${escapeHtml(route.label)}</span>
        <span class="model-route-status ${providerHasCredential(resolved.providerId) ? 'ready' : 'needs-key'}">
          ${providerHasCredential(resolved.providerId) ? 'Credential ready' : 'Credential missing'}
        </span>
      </div>
      <div class="model-route-controls">
        <select class="select-dropdown model-route-provider"></select>
        <input class="settings-input model-route-model" type="text" placeholder="Model name" />
      </div>
      <p class="model-route-hint">${escapeHtml(resolved.providerName)} via ${escapeHtml(resolved.authType)} auth</p>
    `;

    const providerSelect = row.querySelector('.model-route-provider');
    appState.providers.forEach(provider => {
      const option = document.createElement('option');
      option.value = provider.id;
      option.textContent = provider.name;
      providerSelect.appendChild(option);
    });

    if (!getProviderById(config.providerId) && config.providerId) {
      const customOption = document.createElement('option');
      customOption.value = config.providerId;
      customOption.textContent = `${config.providerId} (missing provider)`;
      providerSelect.appendChild(customOption);
    }
    providerSelect.value = config.providerId;

    const modelInput = row.querySelector('.model-route-model');
    modelInput.value = config.model || resolved.model || '';

    providerSelect.addEventListener('change', () => {
      const selectedProvider = getProviderById(providerSelect.value);
      const nextRouting = normalizeTaskModelRouting(appState.settings.taskModelRouting);
      const previousProviderId = nextRouting[route.id]?.providerId;
      nextRouting[route.id] = {
        providerId: providerSelect.value,
        model: nextRouting[route.id]?.model || ''
      };

      if (!nextRouting[route.id].model || previousProviderId !== providerSelect.value) {
        nextRouting[route.id].model = selectedProvider?.defaultModel || '';
      }

      appState.settings.taskModelRouting = nextRouting;
      appState.settings.profilePreset = 'custom';
      saveSettings();
      applySettings();
    });

    modelInput.addEventListener('change', () => {
      const nextRouting = normalizeTaskModelRouting(appState.settings.taskModelRouting);
      nextRouting[route.id] = {
        providerId: providerSelect.value,
        model: modelInput.value.trim()
      };
      appState.settings.taskModelRouting = nextRouting;
      appState.settings.profilePreset = 'custom';
      saveSettings();
      applySettings();
    });

    container.appendChild(row);
  });
}

async function syncProviderSecretPresence() {
  const providerIds = appState.providers.map(provider => provider.id);
  if (providerIds.length === 0) {
    appState.providerSecretPresence = {};
    return;
  }

  const result = await callBackend('get_provider_secret_presence_command', {
    provider_ids: providerIds
  });
  if (!result || typeof result !== 'object') {
    return;
  }

  appState.providerSecretPresence = result;
  appState.providers.forEach(provider => {
    provider.secretStored = provider.authType === 'none' || !!result[provider.id];
  });
  saveProviders();
  renderTaskModelRoutingControls();
}

function renderProviderTypes() {
  const grid = elements.providerTypeGrid;
  grid.innerHTML = '';
  
  DEFAULT_PROVIDERS.forEach(type => {
    const btn = document.createElement('div');
    btn.className = 'provider-type-btn';
    btn.dataset.type = type.id;
    btn.innerHTML = `
      <span class="provider-type-icon">${type.icon}</span>
      <span class="provider-type-name">${type.name}</span>
    `;
    
    btn.addEventListener('click', () => {
      document.querySelectorAll('.provider-type-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      appState.selectedProviderTemplateId = type.id;
      
      document.getElementById('providerName').value = type.name;
      document.getElementById('providerBaseUrl').value = type.baseUrl;
      document.getElementById('providerAuthType').value = type.authType;
      document.getElementById('providerDefaultModel').value = type.defaultModel;
      
      updateAuthFieldsVisibility();
    });
    
    grid.appendChild(btn);
  });
}

// ====================
// Command Palette
// ====================

function renderCommandList(filter = '') {
  const list = elements.commandList;
  list.innerHTML = '';
  
  const filtered = appState.shortcuts.filter(s => 
    s.name.toLowerCase().includes(filter.toLowerCase()) ||
    s.desc.toLowerCase().includes(filter.toLowerCase())
  );
  
  filtered.forEach((cmd, index) => {
    const item = document.createElement('div');
    item.className = `command-item ${index === 0 ? 'selected' : ''}`;
    item.dataset.action = cmd.action;
    
    item.innerHTML = `
      <div class="command-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </div>
      <div class="command-info">
        <div class="command-name">${escapeHtml(cmd.name)}</div>
        <div class="command-desc">${escapeHtml(cmd.desc)}</div>
      </div>
      <span class="command-shortcut">${cmd.keys}</span>
    `;
    
    item.addEventListener('click', () => executeCommand(cmd.action));
    list.appendChild(item);
  });
}

function openCommandPalette() {
  elements.commandPalette.classList.remove('hidden');
  elements.commandInput.value = '';
  elements.commandInput.focus();
  renderCommandList();
}

function closeCommandPalette() {
  elements.commandPalette.classList.add('hidden');
}

function executeCommand(action) {
  switch (action) {
    case 'newChat':
      const conv = createConversation();
      setActiveConversation(conv.id);
      break;
    case 'togglePin':
      appState.settings.pinned = !appState.settings.pinned;
      saveSettings();
      applySettings();
      break;
    case 'openSettings':
      openSettings();
      break;
    case 'openCommandPalette':
      openCommandPalette();
      break;
    case 'voiceRecord':
      startVoiceRecording();
      break;
    case 'toggleSidebar':
      elements.sidebar.classList.toggle('collapsed');
      break;
    case 'vibeStatus':
      void runVibeStatusFromDashboard();
      break;
    case 'continueAutonomy':
      void runVibeContinueFromDashboard();
      break;
    case 'runSoak':
      void runSoakFromDashboard();
      break;
  }
  closeCommandPalette();
}

// ====================
// Rendering Functions
// ====================

function renderConversationList() {
  const list = elements.conversationList;
  list.innerHTML = '';

  const searchQuery = (appState.conversationSearchQuery || '').trim().toLowerCase();
  const visibleConversations = searchQuery
    ? appState.conversations.filter(conv => {
      const latestMessage = conv.messages[conv.messages.length - 1]?.content || '';
      return conv.title.toLowerCase().includes(searchQuery)
        || latestMessage.toLowerCase().includes(searchQuery)
        || String(conv.mode || '').toLowerCase().includes(searchQuery);
    })
    : appState.conversations;
  
  visibleConversations.forEach(conv => {
    const item = document.createElement('div');
    item.className = `conversation-item ${conv.id === appState.activeConversationId ? 'active' : ''}`;
    item.dataset.id = conv.id;
    
    const lastMessage = conv.messages[conv.messages.length - 1];
    const preview = lastMessage ? lastMessage.content.substring(0, 40) : 'No messages yet';
    const time = formatTime(conv.updatedAt);
    
    const provider = appState.providers.find(p => p.id === (conv.providerId || appState.activeProvider));
    
    item.innerHTML = `
      <div class="conversation-icon">${provider?.icon || '💬'}</div>
      <div class="conversation-info">
        <div class="conversation-title">${escapeHtml(conv.title)}</div>
        <div class="conversation-preview">${escapeHtml(preview)}</div>
      </div>
      <div class="conversation-time">${time}</div>
    `;
    
    item.addEventListener('click', () => setActiveConversation(conv.id));
    item.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      showConversationMenu(conv.id, e.clientX, e.clientY);
    });
    
    list.appendChild(item);
  });
  
  updateFolderCounts();
}

function renderFolderList() {
  const list = elements.folderList;
  list.innerHTML = '';
  
  appState.folders.forEach(folder => {
    const item = document.createElement('div');
    item.className = 'folder-item';
    item.dataset.color = folder.color;
    item.innerHTML = `
      <svg class="folder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      <span class="folder-name">${escapeHtml(folder.name)}</span>
      <span class="folder-count">${folder.count}</span>
    `;
    
    item.addEventListener('click', () => filterByFolder(folder.id));
    item.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      showFolderMenu(folder.id, e.clientX, e.clientY);
    });
    
    list.appendChild(item);
  });
}

function renderActiveConversation() {
  const container = elements.messagesContainer;
  container.innerHTML = '';
  
  const conversation = appState.conversations.find(c => c.id === appState.activeConversationId);
  
  if (!conversation) {
    container.innerHTML = `
      <div class="empty-state">
        <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <h3 class="empty-state-title">No conversation selected</h3>
        <p class="empty-state-desc">Start a new conversation by typing below or clicking the + button</p>
      </div>
    `;
    elements.conversationTitle.value = '';
    elements.modeBadge.textContent = 'coding';
    return;
  }
  
  elements.conversationTitle.value = conversation.title;
  elements.modeBadge.textContent = conversation.mode;
  
  conversation.messages.forEach(msg => {
    renderMessage(msg, container);
  });
  
  container.scrollTop = container.scrollHeight;
}

function renderMessage(message, container = elements.messagesContainer) {
  const div = document.createElement('div');
  div.className = `message ${message.role}`;
  div.dataset.id = message.id;
  
  const avatarContent = message.role === 'user' ? 'U' : 'V';
  
  div.innerHTML = `
    <div class="message-avatar">${avatarContent}</div>
    <div class="message-content">${formatMessageContent(message.content)}</div>
  `;
  
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function renderQuestionBubble(question, container = elements.messagesContainer) {
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.innerHTML = `
    <div class="message-avatar">V</div>
    <div class="question-bubble" data-question-id="${question.question_id}">
      <p class="question-text">${escapeHtml(question.question)}</p>
      <div class="question-choices">
        ${question.choices.map(choice => `
          <button class="choice-btn" data-choice-id="${choice.choice_id}">${escapeHtml(choice.label)}</button>
        `).join('')}
      </div>
      <div class="question-custom">
        <input type="text" placeholder="Or type your answer..." />
        <button class="custom-submit">Send</button>
      </div>
    </div>
  `;
  
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  
  const choiceBtns = div.querySelectorAll('.choice-btn');
  choiceBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      choiceBtns.forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      answerQuestion(question.question_id, btn.dataset.choiceId);
    });
  });
  
  const customInput = div.querySelector('.question-custom input');
  const customSubmit = div.querySelector('.custom-submit');
  
  customSubmit.addEventListener('click', () => {
    const value = customInput.value.trim();
    if (value) {
      answerQuestion(question.question_id, 'custom', value);
      customInput.value = '';
    }
  });
  
  customInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const value = customInput.value.trim();
      if (value) {
        answerQuestion(question.question_id, 'custom', value);
        customInput.value = '';
      }
    }
  });
}

// ====================
// UI Helpers
// ====================

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatMessageContent(content) {
  // Basic markdown-like formatting
  let html = escapeHtml(content);
  
  // Code blocks
  html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
  
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  
  // Bold
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  
  // Italic
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  
  // Line breaks
  html = html.replace(/\n/g, '<br>');
  
  return html;
}

function formatTime(dateStr) {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now - date;
  
  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function showConversationMenu(conversationId, x, y) {
  const existing = document.querySelector('.context-menu');
  if (existing) existing.remove();
  
  const menu = document.createElement('div');
  menu.className = 'context-menu';
  menu.style.cssText = `position: fixed; left: ${x}px; top: ${y}px; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-md); padding: 4px; z-index: 1000; box-shadow: var(--shadow-medium);`;
  
  const options = [
    { label: 'Rename', action: () => renameConversation(conversationId) },
    { label: 'Move to folder', action: () => showFolderPicker(conversationId) },
    { label: 'Delete', action: () => deleteConversation(conversationId) }
  ];
  
  options.forEach(opt => {
    const btn = document.createElement('button');
    btn.textContent = opt.label;
    btn.style.cssText = 'display: block; width: 100%; padding: 8px 16px; border: none; background: transparent; color: var(--ink); text-align: left; cursor: pointer; border-radius: var(--radius-sm);';
    btn.addEventListener('mouseenter', () => btn.style.background = 'var(--chip)');
    btn.addEventListener('mouseleave', () => btn.style.background = 'transparent');
    btn.addEventListener('click', () => { opt.action(); menu.remove(); });
    menu.appendChild(btn);
  });
  
  document.body.appendChild(menu);
  setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 0);
}

function showFolderMenu(folderId, x, y) {
  const existing = document.querySelector('.context-menu');
  if (existing) existing.remove();
  
  const menu = document.createElement('div');
  menu.className = 'context-menu';
  menu.style.cssText = `position: fixed; left: ${x}px; top: ${y}px; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-md); padding: 4px; z-index: 1000; box-shadow: var(--shadow-medium);`;
  
  const colors = FOLDER_COLORS.map(c => ({
    label: c.charAt(0).toUpperCase() + c.slice(1),
    action: () => setFolderColor(folderId, c)
  }));
  
  colors.forEach(opt => {
    const btn = document.createElement('button');
    btn.textContent = opt.label;
    btn.style.cssText = 'display: block; width: 100%; padding: 8px 16px; border: none; background: transparent; color: var(--ink); text-align: left; cursor: pointer; border-radius: var(--radius-sm);';
    btn.addEventListener('mouseenter', () => btn.style.background = 'var(--chip)');
    btn.addEventListener('mouseleave', () => btn.style.background = 'transparent');
    btn.addEventListener('click', () => { opt.action(); menu.remove(); });
    menu.appendChild(btn);
  });
  
  document.body.appendChild(menu);
  setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 0);
}

function setFolderColor(folderId, color) {
  const folder = appState.folders.find(f => f.id === folderId);
  if (folder) {
    folder.color = color;
    saveFolders();
    renderFolderList();
  }
}

function renameConversation(id) {
  const conv = appState.conversations.find(c => c.id === id);
  if (!conv) return;
  
  const newTitle = prompt('Enter new title:', conv.title);
  if (newTitle && newTitle.trim()) {
    updateConversation(id, { title: newTitle.trim() });
    renderConversationList();
    if (id === appState.activeConversationId) {
      elements.conversationTitle.value = newTitle.trim();
    }
  }
}

function showFolderPicker(conversationId) {
  const folderNames = appState.folders.map(f => f.name).join(', ');
  const folder = prompt(`Move to folder (${folderNames}):`, 'General');
  if (folder) {
    const target = appState.folders.find(f => f.name.toLowerCase() === folder.toLowerCase());
    if (target) {
      moveToFolder(conversationId, target.id);
    }
  }
}

function filterByFolder(folderId) {
  console.log('Filter by folder:', folderId);
}

function splitCommandArgs(rawCommand) {
  const input = String(rawCommand || '').trim();
  if (!input) {
    return [];
  }

  const tokens = [];
  let current = '';
  let quote = null;

  for (let i = 0; i < input.length; i += 1) {
    const char = input[i];
    const prev = input[i - 1];

    if ((char === '"' || char === "'") && prev !== '\\') {
      if (!quote) {
        quote = char;
        continue;
      }
      if (quote === char) {
        quote = null;
        continue;
      }
    }

    if (!quote && /\s/.test(char)) {
      if (current) {
        tokens.push(current);
        current = '';
      }
      continue;
    }

    current += char;
  }

  if (current) {
    tokens.push(current);
  }
  return tokens;
}

function setInsightPanel(panelId) {
  appState.activeInsightPanel = panelId;
  document.querySelectorAll('.insight-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.panel === panelId);
  });
  document.querySelectorAll('.insight-panel').forEach(panel => {
    panel.classList.remove('active');
  });

  const panelMap = {
    lineage: elements.insightLineagePanel,
    risk: elements.insightRiskPanel,
    integrations: elements.insightIntegrationsPanel
  };
  panelMap[panelId]?.classList.add('active');
}

function getConversationChildren(parentId) {
  return appState.conversations.filter(conv => conv.parentId === parentId);
}

function renderLineageInsight() {
  if (!elements.lineageOutput) {
    return;
  }

  const active = appState.conversations.find(conv => conv.id === appState.activeConversationId);
  if (!active) {
    elements.lineageOutput.innerHTML = '<div class="insight-row"><span class="insight-label">Status</span><span class="insight-value">No active conversation</span></div>';
    return;
  }

  const chain = [];
  let cursor = active;
  while (cursor) {
    chain.unshift(cursor);
    cursor = cursor.parentId ? appState.conversations.find(conv => conv.id === cursor.parentId) : null;
  }

  const activeChildren = getConversationChildren(active.id);
  const branchCount = appState.conversations.filter(conv => conv.parentId).length;
  const chainText = chain.map(conv => conv.title).join(' → ');
  const childText = activeChildren.length > 0
    ? activeChildren.map(conv => conv.title).join(', ')
    : 'None';

  elements.lineageOutput.innerHTML = `
    <div class="insight-row"><span class="insight-label">Active Chain</span><span class="insight-value">${escapeHtml(chainText)}</span></div>
    <div class="insight-row"><span class="insight-label">Depth</span><span class="insight-value">${Math.max(chain.length - 1, 0)} hops</span></div>
    <div class="insight-row"><span class="insight-label">Child Branches</span><span class="insight-value">${activeChildren.length}</span></div>
    <div class="insight-row"><span class="insight-label">Children</span><span class="insight-value">${escapeHtml(childText)}</span></div>
    <div class="insight-row"><span class="insight-label">Forked Sessions</span><span class="insight-value">${branchCount}</span></div>
  `;
}

async function renderRiskInsight() {
  if (!elements.riskOutput) {
    return;
  }

  const [pendingApprovals, pendingQuestions] = await Promise.all([
    callBackend('list_pending_approvals'),
    callBackend('list_pending_questions')
  ]);

  const approvals = Array.isArray(pendingApprovals) ? pendingApprovals : [];
  const questions = Array.isArray(pendingQuestions) ? pendingQuestions : [];
  const openclaw = appState.openclawStatus || {};
  const queueSize = Number(openclaw.queuedOutbound || openclaw.queued_outbound || 0);
  const waitingAcks = Number(openclaw.pendingAckCount || openclaw.pending_ack_count || 0);

  const approvalTools = approvals.length > 0
    ? approvals.map(item => item.toolId || item.tool_id || 'unknown').join(', ')
    : 'None';

  const hasRisk = approvals.length > 0 || questions.length > 0 || queueSize > 0 || waitingAcks > 0;

  elements.riskOutput.innerHTML = `
    <div class="insight-row"><span class="insight-label">Pending Approvals</span><span class="insight-value ${approvals.length > 0 ? 'highlight' : ''}">${approvals.length}</span></div>
    <div class="insight-row"><span class="insight-label">Pending Questions</span><span class="insight-value ${questions.length > 0 ? 'highlight' : ''}">${questions.length}</span></div>
    <div class="insight-row"><span class="insight-label">Tools Awaiting</span><span class="insight-value">${escapeHtml(approvalTools)}</span></div>
    <div class="insight-row"><span class="insight-label">Queue Outbound</span><span class="insight-value ${queueSize > 0 ? 'highlight' : ''}">${queueSize}</span></div>
    <div class="insight-row"><span class="insight-label">Waiting Acks</span><span class="insight-value ${waitingAcks > 0 ? 'highlight' : ''}">${waitingAcks}</span></div>
  `;
}

function renderIntegrationsInsight() {
  if (!elements.integrationOutput) {
    return;
  }

  const mcpEnabled = appState.settings.mcpServers.filter(server => server.enabled !== false).length;
  const pluginEnabled = appState.settings.plugins.filter(plugin => plugin.enabled !== false).length;
  const skillEnabled = appState.settings.skills.filter(skill => skill.enabled !== false).length;
  const permissionAskCount = Object.values(appState.settings.permissionMatrix).filter(value => value === 'ask').length;

  const runLiveCmd = appState.settings.runLiveCommand || 'npm run dev:live';

  elements.integrationOutput.innerHTML = `
    <div class="insight-row"><span class="insight-label">MCP Servers</span><span class="insight-value">${mcpEnabled}/${appState.settings.mcpServers.length}</span></div>
    <div class="insight-row"><span class="insight-label">Plugins</span><span class="insight-value">${pluginEnabled}/${appState.settings.plugins.length}</span></div>
    <div class="insight-row"><span class="insight-label">Skills</span><span class="insight-value">${skillEnabled}/${appState.settings.skills.length}</span></div>
    <div class="insight-row"><span class="insight-label">Ask Permissions</span><span class="insight-value">${permissionAskCount}</span></div>
    <div class="insight-row"><span class="insight-label">Run Live</span><span class="insight-value highlight">${escapeHtml(runLiveCmd)}</span></div>
  `;
}

async function refreshMissionControl() {
  renderLineageInsight();
  await renderRiskInsight();
  renderIntegrationsInsight();
}

function renderPermissionMatrix() {
  if (!elements.permissionGrid) {
    return;
  }

  elements.permissionGrid.innerHTML = '';
  PERMISSION_CAPABILITIES.forEach(capability => {
    const row = document.createElement('div');
    row.className = 'permission-row';
    row.innerHTML = `
      <span class="permission-label">${escapeHtml(capability.label)}</span>
      <select class="select-dropdown permission-select" data-capability="${escapeHtml(capability.id)}">
        <option value="allow">Allow</option>
        <option value="ask">Ask</option>
        <option value="deny">Deny</option>
      </select>
    `;

    const select = row.querySelector('.permission-select');
    select.value = appState.settings.permissionMatrix[capability.id] || 'ask';
    select.addEventListener('change', () => {
      appState.settings.permissionMatrix = normalizePermissionMatrix(appState.settings.permissionMatrix);
      appState.settings.permissionMatrix[capability.id] = select.value;
      saveSettings();
      void refreshMissionControl();
    });

    elements.permissionGrid.appendChild(row);
  });
}

function renderIntegrationList(container, list, kind) {
  if (!container) {
    return;
  }

  container.innerHTML = '';
  if (!Array.isArray(list) || list.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'setting-desc';
    empty.textContent = `No ${kind} configured.`;
    container.appendChild(empty);
    return;
  }

  list.forEach(item => {
    const row = document.createElement('div');
    row.className = 'integration-item';
    const meta = kind === 'MCP servers' && item.command
      ? `${item.command}${Array.isArray(item.args) && item.args.length ? ` ${item.args.join(' ')}` : ''}`
      : item.enabled === false ? 'Disabled' : 'Enabled';

    row.innerHTML = `
      <div class="integration-meta">
        <div class="integration-name">${escapeHtml(item.name)}</div>
        <div class="integration-desc">${escapeHtml(meta)}</div>
      </div>
      <div class="integration-actions">
        <button class="inline-btn integration-toggle" type="button">${item.enabled === false ? 'Enable' : 'Disable'}</button>
        <button class="inline-btn integration-remove" type="button">Remove</button>
      </div>
    `;

    row.querySelector('.integration-toggle')?.addEventListener('click', () => {
      item.enabled = item.enabled === false;
      saveSettings();
      renderIntegrationsSettings();
      void refreshMissionControl();
    });

    row.querySelector('.integration-remove')?.addEventListener('click', () => {
      if (kind === 'MCP servers') {
        appState.settings.mcpServers = appState.settings.mcpServers.filter(server => server.id !== item.id);
      } else if (kind === 'plugins') {
        appState.settings.plugins = appState.settings.plugins.filter(plugin => plugin.id !== item.id);
      } else {
        appState.settings.skills = appState.settings.skills.filter(skill => skill.id !== item.id);
      }
      saveSettings();
      renderIntegrationsSettings();
      void refreshMissionControl();
    });

    container.appendChild(row);
  });
}

function renderIntegrationsSettings() {
  renderIntegrationList(elements.mcpServersList, appState.settings.mcpServers, 'MCP servers');
  renderIntegrationList(elements.pluginsList, appState.settings.plugins, 'plugins');
  renderIntegrationList(elements.skillsList, appState.settings.skills, 'skills');
}

function forkActiveConversation() {
  const active = appState.conversations.find(conv => conv.id === appState.activeConversationId);
  if (!active) {
    return;
  }

  const fork = {
    ...active,
    id: generateId(),
    title: `${active.title} (Fork)`,
    parentId: active.id,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messages: active.messages.map(message => ({ ...message, id: generateId() }))
  };

  appState.conversations.unshift(fork);
  saveConversations();
  setActiveConversation(fork.id);
  void refreshMissionControl();
}

async function runLiveCommand(source = 'desktop_ui') {
  if (appState.runLiveInFlight) {
    return;
  }

  const rawCommand = (elements.runLiveCommandInput?.value || appState.settings.runLiveCommand || '').trim();
  const cwd = (elements.runLiveCwdInput?.value || appState.settings.runLiveCwd || '').trim();
  const tokens = splitCommandArgs(rawCommand);
  if (tokens.length === 0) {
    addMessage('Run Live command is empty. Set it in Settings > Run Live.', 'assistant');
    renderActiveConversation();
    return;
  }

  const [command, ...args] = tokens;
  appState.settings.runLiveCommand = rawCommand;
  appState.settings.runLiveCwd = cwd;
  saveSettings();
  applySettings();

  appState.runLiveInFlight = true;
  const runButtons = [elements.runLiveBtn, elements.autonomyRunLiveBtn, elements.runLiveFromSettingsBtn].filter(Boolean);
  runButtons.forEach(button => {
    button.disabled = true;
  });

  try {
    const outcome = await callBackend('action_request', {
      payload: {
        toolId: 'node.command',
        source,
        args: {
          command,
          args,
          cwd: cwd || null,
          timeoutSeconds: 180
        }
      }
    }, { throwOnError: true });

    const status = outcome?.status;
    if (status === 'pending') {
      addMessage('Run Live is waiting for approval. Check the approval question and approve to execute.', 'assistant');
      setAutonomyOutput('Run Live requested and waiting for approval.');
      return;
    }

    if (status === 'denied' || status === 'rejected') {
      const reason = outcome?.reason || 'Run Live request was denied.';
      addMessage(`Run Live denied: ${reason}`, 'assistant');
      setAutonomyOutput(`Run Live denied: ${reason}`);
      return;
    }

    const output = outcome?.output || {};
    const stdout = (output.stdout || '').trim();
    const stderr = (output.stderr || '').trim();
    const success = !!output.success;
    const parts = [];
    parts.push(`Run Live ${success ? 'completed' : 'finished with errors'} (${command} ${args.join(' ')})`);
    if (stdout) {
      parts.push(`stdout:\n${stdout}`);
    }
    if (stderr) {
      parts.push(`stderr:\n${stderr}`);
    }

    const outputText = parts.join('\n\n');
    addMessage(outputText, 'assistant');
    renderActiveConversation();
    setAutonomyOutput(outputText);
  } catch (error) {
    const reason = error?.message || String(error);
    addMessage(`Run Live failed: ${reason}`, 'assistant');
    renderActiveConversation();
    setAutonomyOutput(`Run Live failed: ${reason}`);
  } finally {
    appState.runLiveInFlight = false;
    runButtons.forEach(button => {
      button.disabled = false;
    });
    await refreshMissionControl();
  }
}

// ====================
// Settings
// ====================

function applySettings() {
  appState.settings = normalizeSettings(appState.settings);
  const { settings } = appState;
  
  document.documentElement.setAttribute('data-theme', settings.theme);
  document.documentElement.setAttribute('data-font', settings.font);
  
  document.querySelectorAll('.theme-option').forEach(opt => {
    opt.classList.toggle('active', opt.dataset.theme === settings.theme);
  });
  
  elements.fontSelector.value = settings.font;
  if (elements.pinToggle) {
    elements.pinToggle.classList.toggle('active', settings.pinned);
  }
  if (elements.soundToggle) {
    elements.soundToggle.classList.toggle('active', settings.soundEnabled);
  }
  if (elements.notificationToggle) {
    elements.notificationToggle.classList.toggle('active', settings.notificationsEnabled);
  }
  if (elements.voiceToggle) {
    elements.voiceToggle.classList.toggle('active', settings.voiceEnabled);
  }
  if (elements.voiceModeSelector) {
    elements.voiceModeSelector.value = settings.voiceMode;
  }
  
  // New notification settings
  if (elements.showAllNotificationsToggle) {
    elements.showAllNotificationsToggle.classList.toggle('active', settings.showAllNotifications);
  }
  if (elements.notifyQuestionToggle) {
    elements.notifyQuestionToggle.classList.toggle('active', settings.notifyOnQuestion);
  }
  if (elements.notifyMessageToggle) {
    elements.notifyMessageToggle.classList.toggle('active', settings.notifyOnMessage);
  }
  if (elements.notifyCompletionToggle) {
    elements.notifyCompletionToggle.classList.toggle('active', settings.notifyOnCompletion);
  }
  if (elements.notifyErrorToggle) {
    elements.notifyErrorToggle.classList.toggle('active', settings.notifyOnError);
  }
  if (elements.autoImportToggle) {
    elements.autoImportToggle.classList.toggle('active', settings.autoImportConversations);
  }
  if (elements.profilePresetSelector) {
    elements.profilePresetSelector.value = settings.profilePreset || 'custom';
  }
  if (elements.agentModeSelector) {
    elements.agentModeSelector.value = settings.agentMode || 'profile';
  }
  if (elements.parallelAgentsInput) {
    elements.parallelAgentsInput.value = String(settings.parallelAgents || 1);
  }
  if (elements.mergePolicySelector) {
    elements.mergePolicySelector.value = settings.mergePolicy || 'best_score';
  }
  if (elements.agentPauseOnFailToggle) {
    elements.agentPauseOnFailToggle.classList.toggle('active', !!settings.pauseOnVerificationFailure);
  }
  if (elements.openclawGatewayUrlInput) {
    elements.openclawGatewayUrlInput.value = settings.openclawGatewayUrl || 'ws://127.0.0.1:8765';
  }
  if (elements.runLiveCommandInput) {
    elements.runLiveCommandInput.value = settings.runLiveCommand || DEFAULT_SETTINGS.runLiveCommand;
  }
  if (elements.runLiveCwdInput) {
    elements.runLiveCwdInput.value = settings.runLiveCwd || '';
  }
  renderTaskModelRoutingControls();
  renderPermissionMatrix();
  renderIntegrationsSettings();
  renderOpenclawStatus();
  renderAutonomyDashboard();
  void refreshMissionControl();
}

function openSettings() {
  elements.settingsOverlay.classList.add('open');
}

function closeSettings() {
  elements.settingsOverlay.classList.remove('open');
}

async function applyProfilePreset(presetName) {
  if (!presetName || presetName === 'custom') {
    appState.settings.profilePreset = 'custom';
    saveSettings();
    applySettings();
    return;
  }

  const preset = PROFILE_PRESETS[presetName];
  if (!preset) {
    return;
  }

  appState.settings = {
    ...appState.settings,
    ...preset,
    profilePreset: presetName
  };
  saveSettings();
  applySettings();

  await callBackend('set_overlay_pinned', { pinned: appState.settings.pinned });
  await syncOpenclawForMode();
  if (appState.settings.notificationsEnabled) {
    showNotification('Fluxio', `Applied profile preset: ${presetName}`);
  }
}

// ====================
// Tutorial
// ====================

function checkTutorial() {
  appState.tutorialComplete = loadFromStorage(STORAGE_KEYS.TUTORIAL_COMPLETE, false);
  
  if (!appState.tutorialComplete) {
    showTutorial();
  }
}

function showTutorial() {
  const tutorials = [
    { title: 'Welcome to Fluxio!', text: 'Your AI assistant is ready. Type a message or use the voice button to start.', btn: "Let's Go" },
    { title: 'Hold to Open', text: 'Press and hold Space to open the overlay from anywhere. Release to close.', btn: 'Next' },
    { title: 'Voice Input', text: 'Click and hold the microphone button to dictate your message hands-free.', btn: 'Next' },
    { title: 'Organize Conversations', text: 'Create folders to organize your conversations. Right-click any conversation to move it.', btn: 'Got It!' },
    { title: 'AI Providers', text: 'Configure multiple AI providers in Settings. Each can have different authentication methods.', btn: 'Next' },
    { title: 'Command Palette', text: 'Press Ctrl+K to open the command palette for quick actions!', btn: 'Start Chatting' }
  ];
  
  let step = 0;
  
  function showStep() {
    if (step >= tutorials.length) {
      elements.tutorialOverlay.classList.add('hidden');
      appState.tutorialComplete = true;
      localStorage.setItem(STORAGE_KEYS.TUTORIAL_COMPLETE, 'true');
      return;
    }
    
    const t = tutorials[step];
    elements.tutorialTitle.textContent = t.title;
    elements.tutorialText.textContent = t.text;
    elements.tutorialBtn.textContent = t.btn;
    elements.tutorialOverlay.classList.remove('hidden');
  }
  
  showStep();
  
  elements.tutorialBtn.addEventListener('click', () => {
    step++;
    showStep();
  });
}

// ====================
// Tauri Backend Integration
// ====================

async function callBackend(command, payload = {}, options = {}) {
  const { throwOnError = false } = options;
  if (!invoke) {
    console.warn('Tauri invoke not available');
    if (throwOnError) {
      throw new Error('Tauri invoke not available');
    }
    return null;
  }
  
  try {
    return await invoke(command, payload);
  } catch (error) {
    console.error(`Backend error (${command}):`, error);
    if (throwOnError) {
      throw error;
    }
    return null;
  }
}

function resolveEffectiveAgentMode() {
  if (appState.settings.agentMode && appState.settings.agentMode !== 'profile') {
    return appState.settings.agentMode;
  }

  const preset = PROFILE_PRESETS[appState.settings.profilePreset || ''];
  if (preset?.agentMode) {
    return preset.agentMode;
  }

  return 'balanced';
}

function isAutonomousModeEnabled() {
  const mode = resolveEffectiveAgentMode();
  return ['autopilot', 'deep_run', 'swarms', 'swarm_mega'].includes(mode);
}

function renderOpenclawStatus() {
  if (!elements.openclawStatusBadge || !elements.openclawStatusText) {
    return;
  }

  const autonomousMode = isAutonomousModeEnabled();
  const status = appState.openclawStatus || {};
  const connected = !!status.connected;
  const lastError = status.lastError || status.last_error || null;
  const gatewayUrl = status.gatewayUrl || appState.settings.openclawGatewayUrl || 'ws://127.0.0.1:8765';
  const queuedOutbound = Number.isFinite(status.queuedOutbound)
    ? status.queuedOutbound
    : Number.isFinite(status.queued_outbound)
      ? status.queued_outbound
      : 0;
  const pendingAckCount = Number.isFinite(status.pendingAckCount)
    ? status.pendingAckCount
    : Number.isFinite(status.pending_ack_count)
      ? status.pending_ack_count
      : 0;
  const reconnectAttempt = Number.isFinite(status.reconnectAttempt)
    ? status.reconnectAttempt
    : Number.isFinite(status.reconnect_attempt)
      ? status.reconnect_attempt
      : 0;

  if (!autonomousMode) {
    elements.openclawStatusBadge.textContent = 'Inactive';
    elements.openclawStatusBadge.classList.remove('online');
    elements.openclawStatusText.textContent = 'OpenClaw is only active in autonomous modes.';
    if (elements.openclawToggleBtn) {
      elements.openclawToggleBtn.textContent = 'Connect';
      elements.openclawToggleBtn.disabled = true;
    }
    return;
  }

  elements.openclawStatusBadge.textContent = connected ? 'Connected' : 'Offline';
  elements.openclawStatusBadge.classList.toggle('online', connected);

  if (connected) {
    elements.openclawStatusText.textContent = `OpenClaw connected (${gatewayUrl}).`;
  } else if (lastError) {
    elements.openclawStatusText.textContent = reconnectAttempt > 0
      ? `OpenClaw offline: ${lastError} (retry #${reconnectAttempt})`
      : `OpenClaw offline: ${lastError}`;
  } else {
    elements.openclawStatusText.textContent = `OpenClaw offline (${gatewayUrl}).`;
  }

  if (queuedOutbound > 0) {
    elements.openclawStatusText.textContent += ` ${queuedOutbound} message(s) queued for replay.`;
  }
  if (pendingAckCount > 0) {
    elements.openclawStatusText.textContent += ` Waiting ack for ${pendingAckCount} message(s).`;
  }

  if (elements.openclawToggleBtn) {
    elements.openclawToggleBtn.textContent = connected ? 'Disconnect' : 'Connect';
    elements.openclawToggleBtn.disabled = false;
  }
}

async function refreshOpenclawStatus() {
  const status = await callBackend('get_openclaw_status');
  if (status && typeof status === 'object') {
    appState.openclawStatus = status;
  }
  renderOpenclawStatus();
}

async function connectOpenclawGateway() {
  const gatewayUrl = (elements.openclawGatewayUrlInput?.value || appState.settings.openclawGatewayUrl || '').trim();
  if (gatewayUrl) {
    appState.settings.openclawGatewayUrl = gatewayUrl;
    saveSettings();
  }

  const status = await callBackend('connect_openclaw_gateway', {
    payload: {
      gatewayUrl: gatewayUrl || undefined
    }
  });
  if (status && typeof status === 'object') {
    appState.openclawStatus = status;
    renderOpenclawStatus();
    return true;
  }
  return false;
}

async function disconnectOpenclawGateway() {
  const status = await callBackend('disconnect_openclaw_gateway');
  if (status && typeof status === 'object') {
    appState.openclawStatus = status;
  }
  renderOpenclawStatus();
}

async function syncOpenclawForMode() {
  if (!isAutonomousModeEnabled()) {
    if (appState.openclawStatus?.connected) {
      await disconnectOpenclawGateway();
    }
    renderOpenclawStatus();
    return;
  }

  if (!appState.openclawStatus?.connected) {
    await connectOpenclawGateway();
    await refreshOpenclawStatus();
    return;
  }

  renderOpenclawStatus();
}

function pickValue(payload, camelKey, snakeKey, fallback = null) {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  if (payload[camelKey] !== undefined && payload[camelKey] !== null) {
    return payload[camelKey];
  }
  if (payload[snakeKey] !== undefined && payload[snakeKey] !== null) {
    return payload[snakeKey];
  }
  return fallback;
}

function formatDashboardTimestamp(value) {
  if (!value) {
    return 'No run data yet';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return `Updated ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
}

function setAutonomyOutput(text) {
  const content = typeof text === 'string' ? text : JSON.stringify(text, null, 2);
  appState.lastAutonomyOutput = content;
  if (elements.autonomyOutput) {
    elements.autonomyOutput.textContent = content;
  }
}

function renderAutonomyDashboard() {
  const snapshot = appState.autonomySnapshot || {};

  if (elements.autonomySessionValue) {
    elements.autonomySessionValue.textContent = pickValue(snapshot, 'latestSessionId', 'latest_session_id', '—') || '—';
  }

  const autopilotStatus = pickValue(snapshot, 'autopilotStatus', 'autopilot_status', '—') || '—';
  const pauseReason = pickValue(snapshot, 'autopilotPauseReason', 'autopilot_pause_reason', '');
  if (elements.autonomyStatusValue) {
    elements.autonomyStatusValue.textContent = pauseReason ? `${autopilotStatus} (${pauseReason})` : autopilotStatus;
  }

  const mergePolicy = pickValue(snapshot, 'mergePolicy', 'merge_policy', '—') || '—';
  const parallelAgents = pickValue(snapshot, 'parallelAgents', 'parallel_agents', null);
  if (elements.autonomyMergeValue) {
    elements.autonomyMergeValue.textContent = Number.isFinite(parallelAgents)
      ? `${mergePolicy} • ${parallelAgents} workers`
      : mergePolicy;
  }

  if (elements.autonomyCheckpointsValue) {
    elements.autonomyCheckpointsValue.textContent = String(pickValue(snapshot, 'checkpointCount', 'checkpoint_count', 0));
  }
  if (elements.autonomyRemainingValue) {
    elements.autonomyRemainingValue.textContent = String(pickValue(snapshot, 'remainingSteps', 'remaining_steps', 0));
  }

  const pendingApprovals = pickValue(snapshot, 'pendingApprovals', 'pending_approvals', 0);
  const pendingQuestions = pickValue(snapshot, 'pendingQuestions', 'pending_questions', 0);
  if (elements.autonomyApprovalsValue) {
    elements.autonomyApprovalsValue.textContent = `${pendingApprovals} approvals • ${pendingQuestions} questions`;
  }

  if (elements.autonomyUpdatedValue) {
    elements.autonomyUpdatedValue.textContent = formatDashboardTimestamp(
      pickValue(snapshot, 'updatedAt', 'updated_at', null)
    );
  }

  if (elements.autonomyOutput && !elements.autonomyOutput.textContent?.trim()) {
    elements.autonomyOutput.textContent = appState.lastAutonomyOutput;
  }
}

function clampNumberInput(rawValue, min, max, fallback) {
  const parsed = Number.parseInt(rawValue, 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, parsed));
}

function getAutonomyRunOptions() {
  const mode = appState.settings.agentMode || 'profile';
  const profile = mode === 'profile' && appState.settings.profilePreset !== 'custom'
    ? appState.settings.profilePreset
    : null;
  return {
    mode,
    profile,
    mergePolicy: appState.settings.mergePolicy || null,
    cycles: clampNumberInput(elements.autonomyCyclesInput?.value, 1, 20, 2),
    iterations: clampNumberInput(elements.autonomyIterationsInput?.value, 1, 24, 4)
  };
}

function inferSoakObjective() {
  const prompt = elements.promptInput?.value?.trim();
  if (prompt) {
    return prompt;
  }

  const active = appState.conversations.find(conv => conv.id === appState.activeConversationId);
  if (active) {
    const latestUserMessage = [...active.messages].reverse().find(msg => msg.role === 'user' && msg.content?.trim());
    if (latestUserMessage) {
      return latestUserMessage.content.trim();
    }
    if (active.title?.trim()) {
      return `Soak: ${active.title.trim()}`;
    }
  }

  return 'Desktop-triggered autonomous soak validation';
}

async function refreshAutonomyDashboard() {
  const snapshot = await callBackend('get_autonomy_dashboard_snapshot', {
    payload: { root: null }
  });

  if (snapshot && typeof snapshot === 'object') {
    appState.autonomySnapshot = snapshot;
    if (snapshot.openclawStatus && typeof snapshot.openclawStatus === 'object') {
      appState.openclawStatus = snapshot.openclawStatus;
      renderOpenclawStatus();
    } else if (snapshot.openclaw_status && typeof snapshot.openclaw_status === 'object') {
      appState.openclawStatus = snapshot.openclaw_status;
      renderOpenclawStatus();
    }
  }
  renderAutonomyDashboard();
}

function stringifyResult(result) {
  try {
    return JSON.stringify(result, null, 2);
  } catch {
    return String(result);
  }
}

async function runDashboardAction(actionLabel, action) {
  const buttons = [
    elements.autonomyRefreshBtn,
    elements.autonomyVibeStatusBtn,
    elements.autonomyContinueBtn,
    elements.autonomySoakBtn,
    elements.autonomyRunLiveBtn
  ].filter(Boolean);

  buttons.forEach(btn => {
    btn.disabled = true;
  });
  setAutonomyOutput(`${actionLabel}...`);

  try {
    const result = await action();
    setAutonomyOutput(stringifyResult(result));
    await refreshAutonomyDashboard();
    return result;
  } catch (error) {
    const message = error?.message || String(error);
    setAutonomyOutput(`${actionLabel} failed: ${message}`);
    throw error;
  } finally {
    buttons.forEach(btn => {
      btn.disabled = false;
    });
  }
}

async function runVibeStatusFromDashboard() {
  await runDashboardAction('Running vibe-status', () => callBackend(
    'run_agent_vibe_status_command',
    { payload: { root: null } },
    { throwOnError: true }
  ));
}

async function runVibeContinueFromDashboard() {
  const options = getAutonomyRunOptions();
  await runDashboardAction('Running vibe-continue', () => callBackend(
    'run_agent_vibe_continue_command',
    {
      payload: {
        root: null,
        cycles: options.cycles,
        iterations: options.iterations,
        mode: options.mode,
        profile: options.profile,
        mergePolicy: options.mergePolicy
      }
    },
    { throwOnError: true }
  ));
}

async function runSoakFromDashboard() {
  const options = getAutonomyRunOptions();
  await runDashboardAction('Running soak', () => callBackend(
    'run_agent_soak_command',
    {
      payload: {
        root: null,
        objective: inferSoakObjective(),
        docs: [],
        cycles: options.cycles,
        iterations: options.iterations,
        mode: options.mode,
        profile: options.profile,
        mergePolicy: options.mergePolicy
      }
    },
    { throwOnError: true }
  ));
}

async function submitPrompt(text) {
  addMessage(text, 'user');
  renderActiveConversation();

  const autonomousMode = isAutonomousModeEnabled();
  const routing = computePromptRouting(text);
  const primaryProvider = getProviderById(routing.primaryRoute.providerId);

  if (appState.activeConversationId && routing.primaryRoute.providerId) {
    updateConversation(appState.activeConversationId, {
      providerId: routing.primaryRoute.providerId
    });
    renderConversationList();
  }

  if (autonomousMode && !appState.openclawStatus?.connected) {
    await syncOpenclawForMode();
  }

  if (autonomousMode && !appState.openclawStatus?.connected) {
    addMessage('Autonomous mode is active, but OpenClaw gateway is offline. Connect the gateway in Settings > Agent Studio.', 'assistant');
    renderActiveConversation();
    return;
  }

  if (autonomousMode) {
    const missingAuth = [];
    const routeChecks = [
      { route: routing.primaryRoute, label: routing.taskType },
      { route: routing.verificationRoute, label: 'verification' }
    ];

    routeChecks.forEach(item => {
      const provider = getProviderById(item.route.providerId);
      if (!provider) {
        missingAuth.push(`${item.label}: provider '${item.route.providerId}' is missing`);
        return;
      }
      if (provider.authType !== 'none' && !providerHasCredential(provider.id)) {
        const authLabel = provider.authType === 'bearer' ? 'bearer token' : 'API key';
        missingAuth.push(`${item.label}: ${provider.name} requires a ${authLabel}`);
      }
    });

    if (missingAuth.length > 0) {
      addMessage(
        `Model routing is configured but missing credentials: ${missingAuth.join('; ')}. Configure keys in Settings > AI Providers. Codex uses API key auth, MiniMax uses bearer token auth.`,
        'assistant'
      );
      renderActiveConversation();
      return;
    }
  }
  
  try {
    await callBackend('submit_prompt', {
      prompt: text,
      provider: routing.primaryRoute.providerId,
      model: routing.primaryRoute.model,
      autonomous_mode: autonomousMode,
      task_type: routing.taskType,
      task_routing: routing.routingMap,
      verification_provider: routing.verificationRoute.providerId,
      verification_model: routing.verificationRoute.model
    }, { throwOnError: true });
  } catch {
    addMessage('Failed to submit prompt to backend. Check gateway/backend status and retry.', 'assistant');
    renderActiveConversation();
    return;
  }

  if (!autonomousMode) {
    const routeLabel = primaryProvider
      ? `${routing.taskType} -> ${primaryProvider.name} (${routing.primaryRoute.model || 'default model'})`
      : `${routing.taskType} -> ${routing.primaryRoute.providerId}`;
    addMessage(`Prompt captured. Routed with task profile: ${routeLabel}. OpenClaw execution activates in autonomous modes.`, 'assistant');
    renderActiveConversation();
  }
}

async function answerQuestion(questionId, choiceId, customAnswer = null) {
  await callBackend('ui_answer', {
    question_id: questionId,
    choice_id: choiceId,
    custom_answer: customAnswer
  });
}

async function startDictation() {
  await callBackend('start_dictation');
}

async function stopDictation() {
  await callBackend('stop_dictation');
}

function startVoiceRecording() {
  if (!appState.settings.voiceEnabled) return;
  
  appState.isRecording = true;
  elements.voiceBtn.classList.add('recording');
  startDictation();
}

function stopVoiceRecording() {
  if (!appState.isRecording) return;
  
  appState.isRecording = false;
  elements.voiceBtn.classList.remove('recording');
  stopDictation();
}

function showNotification(title, body) {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification(title, { body });
  }
}

// ====================
// Import Functions
// ====================

function importFromChatGPT() {
  alert('To import from ChatGPT:\n\n1. Go to ChatGPT\n2. Click on your conversation\n3. Click the share button\n4. Select "Export"\n5. Upload the JSON file using the "Import JSON" button\n\nOr paste the conversation text directly into the chat.');
}

function importFromClaude() {
  alert('To import from Claude:\n\n1. Go to Claude.ai\n2. Open your conversation\n3. Click the settings gear\n4. Select "Export conversation"\n5. Upload the JSON file using the "Import JSON" button');
}

function importFromJsonFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target.result);
      const imported = parseImportedConversation(data);
      
      if (imported) {
        const conv = createConversation(imported.title || 'Imported Chat');
        imported.messages.forEach(msg => {
          conv.messages.push({
            id: generateId(),
            content: msg.content,
            role: msg.role || 'user',
            timestamp: msg.timestamp || new Date().toISOString()
          });
        });
        updateConversation(conv.id, { messages: conv.messages });
        setActiveConversation(conv.id);
        renderConversationList();
        renderActiveConversation();
        showNotification('Fluxio', 'Conversation imported successfully!');
      } else {
        alert('Could not parse the imported file. Please ensure it\'s a valid chat export.');
      }
    } catch (err) {
      console.error('Import error:', err);
      alert('Error importing file: ' + err.message);
    }
  };
  reader.readAsText(file);
}

function parseImportedConversation(data) {
  // Handle various export formats
  if (Array.isArray(data)) {
    // Direct array of messages
    return {
      title: 'Imported Conversation',
      messages: data.map(m => ({
        content: m.content || m.text || m.message || JSON.stringify(m),
        role: m.role || m.author || 'user'
      }))
    };
  }
  
  if (data.conversation || data.chat || data.messages) {
    const conv = data.conversation || data.chat || data;
    return {
      title: conv.title || conv.name || 'Imported Chat',
      messages: (conv.messages || conv.nodes || []).map(m => ({
        content: m.content || m.text || m.message || m.value || JSON.stringify(m),
        role: m.role || m.author || m.sender || 'user'
      }))
    };
  }
  
  if (data.title && data.mapping) {
    // ChatGPT export format
    const messages = [];
    Object.values(data.mapping).forEach(node => {
      if (node.message) {
        messages.push({
          content: node.message.content?.parts?.join('\n') || node.message.content?.text || '',
          role: node.message.author?.role || 'user'
        });
      }
    });
    return { title: data.title, messages };
  }
  
  if (data.export_date || data.id) {
    // Generic export
    return {
      title: data.title || data.name || 'Imported Chat',
      messages: []
    };
  }
  
  return null;
}

function exportConversation(conversationId) {
  const conv = appState.conversations.find(c => c.id === conversationId);
  if (!conv) return;
  
  const exportData = {
    title: conv.title,
    created: conv.createdAt,
    exported: new Date().toISOString(),
    messages: conv.messages.map(m => ({
      role: m.role,
      content: m.content,
      timestamp: m.timestamp
    }))
  };
  
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${conv.title.replace(/[^a-z0-9]/gi, '_')}.json`;
  a.click();
  URL.revokeObjectURL(url);
  
  showNotification('Fluxio', 'Conversation exported!');
}

// ====================
// Event Handlers
// ====================

function setupEventListeners() {
  // New Chat
  elements.newChatBtn.addEventListener('click', () => {
    const conv = createConversation();
    setActiveConversation(conv.id);
  });

  if (elements.conversationSearchInput) {
    elements.conversationSearchInput.addEventListener('input', (e) => {
      appState.conversationSearchQuery = e.target.value || '';
      renderConversationList();
    });
  }

  if (elements.forkConversationBtn) {
    elements.forkConversationBtn.addEventListener('click', forkActiveConversation);
  }

  if (elements.runLiveBtn) {
    elements.runLiveBtn.addEventListener('click', async () => {
      await runLiveCommand('header_run_live');
    });
  }
  
  // Settings
  elements.settingsBtn.addEventListener('click', openSettings);
  elements.settingsCloseBtn.addEventListener('click', closeSettings);
  elements.settingsOverlay.addEventListener('click', (e) => {
    if (e.target === elements.settingsOverlay) closeSettings();
  });
  
  // Theme
  elements.themeSelector.addEventListener('click', (e) => {
    const option = e.target.closest('.theme-option');
    if (option) {
      appState.settings.theme = option.dataset.theme;
      saveSettings();
      applySettings();
    }
  });
  
  // Font
  elements.fontSelector.addEventListener('change', (e) => {
    appState.settings.font = e.target.value;
    saveSettings();
    applySettings();
  });
  
  // Toggles
  elements.pinToggle.addEventListener('click', async () => {
    appState.settings.pinned = !appState.settings.pinned;
    saveSettings();
    applySettings();
    await callBackend('set_overlay_pinned', { pinned: appState.settings.pinned });
  });
  
  elements.soundToggle.addEventListener('click', () => {
    appState.settings.soundEnabled = !appState.settings.soundEnabled;
    saveSettings();
    applySettings();
  });
  
  if (elements.notificationToggle) {
    elements.notificationToggle.addEventListener('click', () => {
      appState.settings.notificationsEnabled = !appState.settings.notificationsEnabled;
      saveSettings();
      applySettings();
      if (appState.settings.notificationsEnabled && 'Notification' in window) {
        Notification.requestPermission();
      }
    });
  }
  
  elements.voiceToggle.addEventListener('click', () => {
    appState.settings.voiceEnabled = !appState.settings.voiceEnabled;
    saveSettings();
    applySettings();
  });
  
  elements.voiceModeSelector.addEventListener('change', (e) => {
    appState.settings.voiceMode = e.target.value;
    saveSettings();
    applySettings();
  });

  if (elements.profilePresetSelector) {
    elements.profilePresetSelector.addEventListener('change', async () => {
      appState.settings.profilePreset = elements.profilePresetSelector.value;
      saveSettings();
      applySettings();
      await syncOpenclawForMode();
    });
  }

  if (elements.applyProfilePresetBtn) {
    elements.applyProfilePresetBtn.addEventListener('click', async () => {
      const selectedPreset = elements.profilePresetSelector?.value || 'custom';
      await applyProfilePreset(selectedPreset);
    });
  }

  if (elements.agentModeSelector) {
    elements.agentModeSelector.addEventListener('change', async (e) => {
      appState.settings.agentMode = e.target.value;
      appState.settings.profilePreset = 'custom';
      saveSettings();
      applySettings();
      await syncOpenclawForMode();
    });
  }

  if (elements.parallelAgentsInput) {
    elements.parallelAgentsInput.addEventListener('change', (e) => {
      const parsed = Number.parseInt(e.target.value, 10);
      appState.settings.parallelAgents = Number.isFinite(parsed) ? Math.max(1, Math.min(8, parsed)) : 1;
      appState.settings.profilePreset = 'custom';
      saveSettings();
      applySettings();
    });
  }

  if (elements.mergePolicySelector) {
    elements.mergePolicySelector.addEventListener('change', (e) => {
      appState.settings.mergePolicy = e.target.value;
      appState.settings.profilePreset = 'custom';
      saveSettings();
      applySettings();
    });
  }

  if (elements.agentPauseOnFailToggle) {
    elements.agentPauseOnFailToggle.addEventListener('click', () => {
      appState.settings.pauseOnVerificationFailure = !appState.settings.pauseOnVerificationFailure;
      appState.settings.profilePreset = 'custom';
      saveSettings();
      applySettings();
    });
  }

  if (elements.openclawGatewayUrlInput) {
    elements.openclawGatewayUrlInput.addEventListener('change', async (e) => {
      appState.settings.openclawGatewayUrl = e.target.value.trim() || 'ws://127.0.0.1:8765';
      saveSettings();
      applySettings();
      if (appState.openclawStatus?.connected) {
        await disconnectOpenclawGateway();
        await connectOpenclawGateway();
      }
    });
  }

  if (elements.openclawToggleBtn) {
    elements.openclawToggleBtn.addEventListener('click', async () => {
      if (!isAutonomousModeEnabled()) {
        addMessage('OpenClaw only runs in autonomous modes (Autopilot, Deep Run, Swarms, Swarm Mega).', 'assistant');
        renderActiveConversation();
        return;
      }

      if (appState.openclawStatus?.connected) {
        await disconnectOpenclawGateway();
      } else {
        await connectOpenclawGateway();
      }
      await refreshOpenclawStatus();
    });
  }

  if (elements.autonomyRefreshBtn) {
    elements.autonomyRefreshBtn.addEventListener('click', async () => {
      await runDashboardAction('Refreshing dashboard', async () => {
        await refreshAutonomyDashboard();
        return appState.autonomySnapshot || {};
      });
    });
  }

  if (elements.autonomyVibeStatusBtn) {
    elements.autonomyVibeStatusBtn.addEventListener('click', async () => {
      await runVibeStatusFromDashboard();
    });
  }

  if (elements.autonomyContinueBtn) {
    elements.autonomyContinueBtn.addEventListener('click', async () => {
      await runVibeContinueFromDashboard();
    });
  }

  if (elements.autonomySoakBtn) {
    elements.autonomySoakBtn.addEventListener('click', async () => {
      await runSoakFromDashboard();
    });
  }

  if (elements.autonomyRunLiveBtn) {
    elements.autonomyRunLiveBtn.addEventListener('click', async () => {
      await runLiveCommand('dashboard_run_live');
    });
  }

  if (elements.runLiveFromSettingsBtn) {
    elements.runLiveFromSettingsBtn.addEventListener('click', async () => {
      await runLiveCommand('settings_run_live');
    });
  }

  if (elements.runLiveCommandInput) {
    elements.runLiveCommandInput.addEventListener('change', (e) => {
      appState.settings.runLiveCommand = e.target.value.trim() || DEFAULT_SETTINGS.runLiveCommand;
      saveSettings();
      void refreshMissionControl();
    });
  }

  if (elements.runLiveCwdInput) {
    elements.runLiveCwdInput.addEventListener('change', (e) => {
      appState.settings.runLiveCwd = e.target.value.trim();
      saveSettings();
    });
  }

  if (elements.addMcpServerBtn) {
    elements.addMcpServerBtn.addEventListener('click', () => {
      const name = prompt('MCP server name:');
      if (!name || !name.trim()) {
        return;
      }
      const command = prompt('Command (for example: npx):', 'npx') || 'npx';
      const argsRaw = prompt('Args (space-separated):', '') || '';
      const args = splitCommandArgs(argsRaw);
      appState.settings.mcpServers.push({
        id: generateId(),
        name: name.trim(),
        command: command.trim(),
        args,
        enabled: true
      });
      saveSettings();
      renderIntegrationsSettings();
      void refreshMissionControl();
    });
  }

  if (elements.insightTabs) {
    elements.insightTabs.addEventListener('click', (e) => {
      const tab = e.target.closest('.insight-tab');
      if (!tab) {
        return;
      }
      const panel = tab.dataset.panel || 'lineage';
      setInsightPanel(panel);
    });
  }

  if (elements.autonomyCyclesInput) {
    elements.autonomyCyclesInput.addEventListener('change', () => {
      elements.autonomyCyclesInput.value = String(
        clampNumberInput(elements.autonomyCyclesInput.value, 1, 20, 2)
      );
    });
  }

  if (elements.autonomyIterationsInput) {
    elements.autonomyIterationsInput.addEventListener('change', () => {
      elements.autonomyIterationsInput.value = String(
        clampNumberInput(elements.autonomyIterationsInput.value, 1, 24, 4)
      );
    });
  }
  
  // New notification toggles
  if (elements.showAllNotificationsToggle) {
    elements.showAllNotificationsToggle.addEventListener('click', () => {
      appState.settings.showAllNotifications = !appState.settings.showAllNotifications;
      saveSettings();
      applySettings();
    });
  }
  
  if (elements.notifyQuestionToggle) {
    elements.notifyQuestionToggle.addEventListener('click', () => {
      appState.settings.notifyOnQuestion = !appState.settings.notifyOnQuestion;
      saveSettings();
      applySettings();
    });
  }
  
  if (elements.notifyMessageToggle) {
    elements.notifyMessageToggle.addEventListener('click', () => {
      appState.settings.notifyOnMessage = !appState.settings.notifyOnMessage;
      saveSettings();
      applySettings();
    });
  }
  
  if (elements.notifyCompletionToggle) {
    elements.notifyCompletionToggle.addEventListener('click', () => {
      appState.settings.notifyOnCompletion = !appState.settings.notifyOnCompletion;
      saveSettings();
      applySettings();
    });
  }
  
  if (elements.notifyErrorToggle) {
    elements.notifyErrorToggle.addEventListener('click', () => {
      appState.settings.notifyOnError = !appState.settings.notifyOnError;
      saveSettings();
      applySettings();
    });
  }
  
  if (elements.autoImportToggle) {
    elements.autoImportToggle.addEventListener('click', () => {
      appState.settings.autoImportConversations = !appState.settings.autoImportConversations;
      saveSettings();
      applySettings();
    });
  }
  
  // Import buttons
  if (elements.importChatGPTBtn) {
    elements.importChatGPTBtn.addEventListener('click', () => {
      importFromChatGPT();
    });
  }
  
  if (elements.importClaudeBtn) {
    elements.importClaudeBtn.addEventListener('click', () => {
      importFromClaude();
    });
  }
  
  if (elements.importJsonBtn) {
    elements.importJsonBtn.addEventListener('click', () => {
      elements.importFileInput.click();
    });
  }
  
  if (elements.importFileInput) {
    elements.importFileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) {
        importFromJsonFile(file);
      }
    });
  }
  
  // Sidebar
  elements.toggleSidebarBtn.addEventListener('click', () => {
    elements.sidebar.classList.toggle('collapsed');
  });
  
  // Prompt
  elements.promptInput.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const text = elements.promptInput.value.trim();
      if (text) {
        elements.promptInput.value = '';
        await submitPrompt(text);
      }
    }
  });
  
  elements.promptInput.addEventListener('input', () => {
    elements.promptInput.style.height = 'auto';
    elements.promptInput.style.height = Math.min(elements.promptInput.scrollHeight, 150) + 'px';
  });
  
  elements.sendBtn.addEventListener('click', async () => {
    const text = elements.promptInput.value.trim();
    if (text) {
      elements.promptInput.value = '';
      await submitPrompt(text);
    }
  });
  
  // Voice
  elements.voiceBtn.addEventListener('mousedown', startVoiceRecording);
  elements.voiceBtn.addEventListener('mouseup', stopVoiceRecording);
  elements.voiceBtn.addEventListener('mouseleave', stopVoiceRecording);
  
  // Conversation Title
  elements.conversationTitle.addEventListener('change', (e) => {
    const title = e.target.value.trim() || 'New Conversation';
    if (appState.activeConversationId) {
      updateConversation(appState.activeConversationId, { title });
      renderConversationList();
    }
  });
  
  // New Folder
  document.getElementById('newFolderBtn')?.addEventListener('click', () => {
    const name = prompt('Enter folder name:');
    if (name && name.trim()) {
      createFolder(name.trim());
    }
  });
  
  // Menu
  if (elements.menuBtn) {
    elements.menuBtn.addEventListener('click', (e) => {
      showConversationMenu(appState.activeConversationId || 'new', e.clientX, e.clientY);
    });
  }
  
  // Providers
  elements.addProviderBtn.addEventListener('click', () => {
    appState.editingProviderId = null;
    appState.selectedProviderTemplateId = null;
    elements.providerModalTitle.textContent = 'Add AI Provider';
    renderProviderTypes();
    openProviderModal();
  });
  
  elements.providerModalClose.addEventListener('click', closeProviderModal);
  elements.providerCancelBtn.addEventListener('click', closeProviderModal);
  elements.providerModal.addEventListener('click', (e) => {
    if (e.target === elements.providerModal) closeProviderModal();
  });
  
  document.getElementById('providerAuthType').addEventListener('change', updateAuthFieldsVisibility);
  document.getElementById('providerName').addEventListener('input', updateProviderAuthHelp);
  
  elements.providerSaveBtn.addEventListener('click', saveProviderConfig);
  
  elements.modelSelector.addEventListener('change', (e) => {
    setActiveProvider(e.target.value);
  });
  
  // Command Palette
  elements.commandPalette.addEventListener('click', (e) => {
    if (e.target === elements.commandPalette) closeCommandPalette();
  });
  
  elements.commandInput.addEventListener('input', (e) => {
    renderCommandList(e.target.value);
  });
  
  elements.commandInput.addEventListener('keydown', (e) => {
    const selected = elements.commandList.querySelector('.command-item.selected');
    
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (selected && selected.nextElementSibling) {
        selected.classList.remove('selected');
        selected.nextElementSibling.classList.add('selected');
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (selected && selected.previousElementSibling) {
        selected.classList.remove('selected');
        selected.previousElementSibling.classList.add('selected');
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selected) {
        executeCommand(selected.dataset.action);
      }
    } else if (e.key === 'Escape') {
      closeCommandPalette();
    }
  });
  
  // Global shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
      if (e.key === 'k') {
        e.preventDefault();
        openCommandPalette();
      } else if (e.key === ',') {
        e.preventDefault();
        openSettings();
      } else if (e.shiftKey && e.key === 'N') {
        e.preventDefault();
        const conv = createConversation();
        setActiveConversation(conv.id);
      }
    }
  });
}

// ====================
// Backend Event Listeners
// ====================

async function setupBackendListeners() {
  if (!listen) return;
  
  await listen('overlay://settings', (event) => console.log('Settings:', event.payload));
  await listen('overlay://visibility', (event) => {
    if (event.payload?.visible) elements.promptInput.focus();
  });
  await listen('overlay://question', (event) => {
    renderQuestionBubble(event.payload);
    void refreshMissionControl();
  });
  await listen('overlay://question_answered', (event) => {
    console.log('Answered:', event.payload);
    void refreshMissionControl();
  });
  await listen('dictation://started', () => console.log('Dictation started'));
  await listen('dictation://stopped', (event) => {
    console.log('Dictation stopped:', event.payload);
    if (event.payload?.transcript) {
      elements.promptInput.value = event.payload.transcript;
    }
  });
  await listen('overlay://mode', (event) => {
    if (appState.activeConversationId) {
      updateConversation(appState.activeConversationId, { mode: event.payload.id });
      elements.modeBadge.textContent = event.payload.id;
      renderConversationList();
    }
  });

  await listen('openclaw://status', (event) => {
    if (event.payload && typeof event.payload === 'object') {
      appState.openclawStatus = event.payload;
      renderOpenclawStatus();
      renderAutonomyDashboard();
    }
  });

  await listen('openclaw://message', (event) => {
    const content = event.payload?.content;
    if (typeof content === 'string' && content.trim()) {
      addMessage(content, 'assistant');
      renderActiveConversation();
      if (appState.settings.notificationsEnabled && !document.hasFocus()) {
        showNotification('Fluxio', content.substring(0, 100));
      }
    }
  });

  await listen('openclaw://rejected', (event) => {
    const reason = event.payload?.error || 'Gateway event was rejected by validation.';
    addMessage(`OpenClaw event rejected: ${reason}`, 'assistant');
    renderActiveConversation();
  });

  await listen('openclaw://action_result', (event) => {
    const status = event.payload?.result?.status;
    if (!status) {
      return;
    }
    const reason = event.payload?.result?.reason;
    const text = reason
      ? `OpenClaw action result: ${status} (${reason})`
      : `OpenClaw action result: ${status}`;
    addMessage(text, 'assistant');
    renderActiveConversation();
    void refreshMissionControl();
  });

  await listen('openclaw://ack', (event) => {
    if (event.payload?.acknowledged) {
      renderOpenclawStatus();
      renderAutonomyDashboard();
    }
  });
}

// ====================
// Initialization
// ====================

async function initialize() {
  // Load data
  appState.conversations = loadConversations();
  appState.folders = loadFolders();
  appState.settings = loadSettings();
  appState.providers = ensureCoreProviders(loadProviders().map((provider, index) => normalizeProviderRecord(provider, index)));
  appState.activeProvider = loadActiveProvider();
  appState.shortcuts = loadShortcuts();
  appState.activeConversationId = loadActiveConversation();

  saveSettings();
  saveProviders();
  
  // Ensure defaults
  if (appState.conversations.length === 0) {
    createConversation('Welcome Chat');
  }
  
  if (!appState.activeProvider && appState.providers.length > 0) {
    appState.activeProvider = appState.providers[0].id;
    saveActiveProvider(appState.activeProvider);
  }

  if (
    appState.activeProvider
    && !appState.providers.some(provider => provider.id === appState.activeProvider)
  ) {
    appState.activeProvider = appState.providers[0]?.id || null;
    saveActiveProvider(appState.activeProvider);
  }
  
  if (!appState.activeConversationId || !appState.conversations.find(c => c.id === appState.activeConversationId)) {
    appState.activeConversationId = appState.conversations[0]?.id || null;
  }
  
  await syncProviderSecretPresence();
  await refreshOpenclawStatus();
  await refreshAutonomyDashboard();
  setAutonomyOutput(appState.lastAutonomyOutput);

  // Render
  applySettings();
  renderProvidersList();
  renderConversationList();
  renderFolderList();
  renderActiveConversation();
  renderAutonomyDashboard();
  setInsightPanel(appState.activeInsightPanel);
  await refreshMissionControl();
  
  // Events
  setupEventListeners();
  await setupBackendListeners();

  setInterval(() => {
    void refreshAutonomyDashboard();
    void refreshMissionControl();
  }, 15000);
  
  // Tutorial
  setTimeout(() => checkTutorial(), 500);
  
  // Splash
  setTimeout(() => elements.splashScreen.classList.add('hidden'), 700);
  
  // Notifications
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }
  
  // Backend sync
  const snapshot = await callBackend('get_overlay_state');
  if (snapshot?.openclawStatus) {
    appState.openclawStatus = snapshot.openclawStatus;
  } else if (snapshot?.openclaw_status) {
    appState.openclawStatus = snapshot.openclaw_status;
  }
  renderOpenclawStatus();
  renderAutonomyDashboard();
  await syncOpenclawForMode();
}

document.addEventListener('DOMContentLoaded', initialize);
