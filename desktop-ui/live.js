import { listen } from '@tauri-apps/api/event';

export function createLiveRefreshController({
  state,
  refresh,
  isPreviewMode,
  setRefreshStatus,
  setDevLoopStatus,
  setFeedStatus,
  applyDelta,
  onError,
}) {
  function stopLiveSync() {
    if (state.liveSyncHandle) {
      window.clearInterval(state.liveSyncHandle);
      state.liveSyncHandle = null;
    }
  }

  function syncDevLoopStatus() {
    if (import.meta.hot) {
      setDevLoopStatus('Vite HMR', 'good');
      return;
    }
    setDevLoopStatus('Packaged build', 'idle');
  }

  function syncFeedStatus() {
    if (isPreviewMode()) {
      setFeedStatus('Fixture review', 'paused');
      return;
    }
    if (state.lastPushReason) {
      setFeedStatus(`Push: ${state.lastPushReason}`, 'good');
      return;
    }
    if (state.liveSyncSeconds !== 'off') {
      setFeedStatus(`Polling: ${state.liveSyncSeconds}s`, 'idle');
      return;
    }
    setFeedStatus('Manual refresh', 'idle');
  }

  function syncRefreshStatus() {
    if (state.previewMode !== 'live') {
      setRefreshStatus(`Preview: ${state.previewMeta?.name || state.previewMode}`, 'good');
      syncFeedStatus();
      return;
    }
    if (state.liveSyncSuspended && state.liveSyncSeconds !== 'off') {
      setRefreshStatus('Live sync paused in background', 'paused');
      syncFeedStatus();
      return;
    }
    setRefreshStatus('Up to date', 'good');
    syncFeedStatus();
  }

  function queueRefresh(reason = 'queued') {
    state.lastRefreshReason = reason;
    state.queuedRefreshReason = reason;
    if (state.refreshInFlight) {
      state.refreshQueued = true;
      return;
    }
    refresh(reason).catch(error => {
      onError(reason, error);
    });
  }

  function liveSyncAllowed() {
    return state.previewMode === 'live' && document.visibilityState === 'visible';
  }

  function applyLiveSync() {
    stopLiveSync();
    const seconds = Number(state.liveSyncSeconds);
    if (!Number.isFinite(seconds) || seconds <= 0) {
      state.liveSyncSuspended = false;
      syncFeedStatus();
      return;
    }
    if (!liveSyncAllowed()) {
      state.liveSyncSuspended = state.previewMode === 'live';
      syncFeedStatus();
      return;
    }
    state.liveSyncSuspended = false;
    state.liveSyncHandle = window.setInterval(() => {
      queueRefresh('live-sync');
    }, seconds * 1000);
    syncFeedStatus();
  }

  function handleVisibilityChange() {
    if (document.visibilityState === 'hidden') {
      if (state.previewMode === 'live' && state.liveSyncSeconds !== 'off') {
        stopLiveSync();
        state.liveSyncSuspended = true;
        syncRefreshStatus();
      }
      return;
    }

    if (state.liveSyncSeconds !== 'off' && state.previewMode === 'live') {
      queueRefresh('visibility-resume');
      return;
    }
    applyLiveSync();
    syncRefreshStatus();
  }

  async function bindControlRoomEvents() {
    if ((state.controlRoomUnlisten && state.controlRoomDeltaUnlisten) || typeof listen !== 'function') {
      return;
    }

    try {
      state.controlRoomUnlisten = await listen('control-room://changed', event => {
        const reason = event?.payload?.reason || 'backend-event';
        state.lastPushReason = reason;
        syncFeedStatus();
        if (isPreviewMode()) {
          return;
        }
        queueRefresh(reason);
      });
      state.controlRoomDeltaUnlisten = await listen('control-room://delta', event => {
        const source = event?.payload?.source || 'delta';
        state.lastPushReason = source;
        syncFeedStatus();
        if (isPreviewMode()) {
          return;
        }
        applyDelta?.(event.payload);
      });
    } catch (error) {
      console.warn('control-room event listener unavailable', error);
    }
  }

  function teardown() {
    stopLiveSync();
    if (typeof state.controlRoomUnlisten === 'function') {
      state.controlRoomUnlisten();
      state.controlRoomUnlisten = null;
    }
    if (typeof state.controlRoomDeltaUnlisten === 'function') {
      state.controlRoomDeltaUnlisten();
      state.controlRoomDeltaUnlisten = null;
    }
  }

  function bindWindowLifecycle() {
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('beforeunload', teardown);
  }

  return {
    applyLiveSync,
    bindControlRoomEvents,
    bindWindowLifecycle,
    queueRefresh,
    syncDevLoopStatus,
    syncFeedStatus,
    syncRefreshStatus,
    teardown,
  };
}
