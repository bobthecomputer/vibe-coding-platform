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
  openclawGatewayUrl: 'ws://127.0.0.1:8765'
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
  { id: 'minimax', name: 'MiniMax', icon: '🔮', baseUrl: 'https://api.minimax.chat/v1', authType: 'api_key', defaultModel: 'abab6.5s-chat' },
  
  // Code Specialization
  { id: 'codex', name: 'OpenAI Codex', icon: '💻', baseUrl: 'https://api.openai.com/v1', authType: 'api_key', defaultModel: 'code-davinci-002' },
  
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
  { id: 'toggle_sidebar', name: 'Toggle Sidebar', desc: 'Show/hide sidebar', keys: 'Ctrl+B', action: 'toggleSidebar' }
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
  settings: { ...DEFAULT_SETTINGS },
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
    queuedOutbound: 0
  },
  shortcuts: [...DEFAULT_SHORTCUTS],
  isRecording: false,
  tutorialComplete: false,
  editingProviderId: null
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
  openclawStatusBadge: document.getElementById('openclawStatusBadge'),
  openclawStatusText: document.getElementById('openclawStatusText'),
  openclawToggleBtn: document.getElementById('openclawToggleBtn'),
  openclawGatewayUrlInput: document.getElementById('openclawGatewayUrlInput'),
  importChatGPTBtn: document.getElementById('importChatGPTBtn'),
  importClaudeBtn: document.getElementById('importClaudeBtn'),
  importJsonBtn: document.getElementById('importJsonBtn'),
  importFileInput: document.getElementById('importFileInput'),
  providerQuickKey: document.getElementById('providerQuickKey')
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
  return {
    ...DEFAULT_SETTINGS,
    ...(stored || {})
  };
}

function saveSettings() {
  saveToStorage(STORAGE_KEYS.SETTINGS, appState.settings);
}

function loadProviders() {
  const stored = loadFromStorage(STORAGE_KEYS.PROVIDERS, null);
  if (stored && stored.length > 0) {
    return stored.map((provider, index) => ({
      id: provider.id || `provider_${index + 1}`,
      name: provider.name || `Provider ${index + 1}`,
      icon: provider.icon || '🔑',
      baseUrl: provider.baseUrl || '',
      authType: provider.authType || 'api_key',
      defaultModel: provider.defaultModel || '',
      secretStored: !!provider.secretStored
    }));
  }
  return [...DEFAULT_PROVIDERS];
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
    
    item.innerHTML = `
      <div class="provider-icon">${provider.icon}</div>
      <div class="provider-info">
        <div class="provider-name">${escapeHtml(provider.name)}</div>
        <div class="provider-status ${isConnected ? 'connected' : ''}">${isConnected ? 'Connected' : 'Paste key to connect'}</div>
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

  const providerId = appState.editingProviderId || generateId();

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
      provider.name = name;
      provider.baseUrl = baseUrl;
      provider.authType = authType;
      provider.defaultModel = defaultModel;
      provider.secretStored = secretStored;
    }
  } else {
    const newProvider = {
      id: providerId,
      name,
      icon: '🔑',
      baseUrl,
      authType,
      defaultModel,
      secretStored
    };
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
}

function closeProviderModal() {
  elements.providerModal.classList.remove('open');
  appState.editingProviderId = null;
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
}

function updateAuthFieldsVisibility() {
  const authType = document.getElementById('providerAuthType').value;
  
  document.getElementById('apiKeyGroup').classList.toggle('hidden', authType !== 'api_key');
  document.getElementById('bearerGroup').classList.toggle('hidden', authType !== 'bearer');
  document.getElementById('basicGroup').classList.toggle('hidden', authType !== 'basic');
  document.getElementById('oauthGroup').classList.toggle('hidden', authType !== 'oauth');
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
  }
  closeCommandPalette();
}

// ====================
// Rendering Functions
// ====================

function renderConversationList() {
  const list = elements.conversationList;
  list.innerHTML = '';
  
  appState.conversations.forEach(conv => {
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

// ====================
// Settings
// ====================

function applySettings() {
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
  renderOpenclawStatus();
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

async function submitPrompt(text) {
  addMessage(text, 'user');
  renderActiveConversation();
  
  const provider = appState.providers.find(p => p.id === appState.activeProvider);
  const autonomousMode = isAutonomousModeEnabled();

  if (autonomousMode && !appState.openclawStatus?.connected) {
    await syncOpenclawForMode();
  }

  if (autonomousMode && !appState.openclawStatus?.connected) {
    addMessage('Autonomous mode is active, but OpenClaw gateway is offline. Connect the gateway in Settings > Agent Studio.', 'assistant');
    renderActiveConversation();
    return;
  }
  
  try {
    await callBackend('submit_prompt', {
      prompt: text,
      provider: provider?.id,
      model: provider?.defaultModel,
      autonomous_mode: autonomousMode
    }, { throwOnError: true });
  } catch {
    addMessage('Failed to submit prompt to backend. Check gateway/backend status and retry.', 'assistant');
    renderActiveConversation();
    return;
  }

  if (!autonomousMode) {
    addMessage('Prompt captured. OpenClaw routing is active only in autonomous modes.', 'assistant');
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
  await listen('overlay://question', (event) => renderQuestionBubble(event.payload));
  await listen('overlay://question_answered', (event) => console.log('Answered:', event.payload));
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
  appState.providers = loadProviders();
  appState.activeProvider = loadActiveProvider();
  appState.shortcuts = loadShortcuts();
  appState.activeConversationId = loadActiveConversation();
  
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

  // Render
  applySettings();
  renderProvidersList();
  renderConversationList();
  renderFolderList();
  renderActiveConversation();
  
  // Events
  setupEventListeners();
  await setupBackendListeners();
  
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
  await syncOpenclawForMode();
}

document.addEventListener('DOMContentLoaded', initialize);
