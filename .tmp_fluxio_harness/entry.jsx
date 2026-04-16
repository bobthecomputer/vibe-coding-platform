
import React from 'react';
import { createRoot } from 'react-dom/client';
import { FluxioShellApp } from '../t3code/apps/web/src/fluxio/FluxioShell.jsx';
import snapshot from './control-room.json';

const providerPresence = { openai: false, anthropic: false, openrouter: false };
const backend = {
  get_control_room_snapshot_command: snapshot,
  list_pending_approvals: [],
  list_pending_questions: [],
  has_telegram_bot_token_command: false,
  get_openclaw_status: null,
  has_openclaw_gateway_token: false,
  get_provider_secret_presence_command: providerPresence,
};

globalThis.__fluxioTestInvoke = async (command) => {
  if (Object.prototype.hasOwnProperty.call(backend, command)) {
    return backend[command];
  }
  return null;
};

const storage = new Map([
  ['fluxio.ui.mode', 'agent'],
  ['fluxio.preview.mode', 'live'],
  ['fluxio.live_sync.seconds', 'off'],
]);
const localStorage = {
  getItem(key) { return storage.has(key) ? storage.get(key) : null; },
  setItem(key, value) { storage.set(key, String(value)); },
  removeItem(key) { storage.delete(key); },
};
Object.defineProperty(globalThis, 'localStorage', { value: localStorage, configurable: true });
Object.defineProperty(window, 'localStorage', { value: localStorage, configurable: true });
window.__TAURI__ = {};
window.requestAnimationFrame = cb => setTimeout(cb, 0);

createRoot(document.getElementById('root')).render(React.createElement(FluxioShellApp, { reportUiAction() {} }));
