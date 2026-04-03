export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function runtimeLabel(runtimeId) {
  if (runtimeId === 'openclaw') return 'OpenClaw';
  if (runtimeId === 'hermes') return 'Hermes';
  return runtimeId;
}

export function missionStatusTone(status) {
  switch (status) {
    case 'completed':
      return 'good';
    case 'blocked':
    case 'verification_failed':
      return 'bad';
    case 'needs_approval':
    case 'waiting_for_approval':
      return 'warn';
    default:
      return 'neutral';
  }
}

export function renderMetricCard(label, value, note = '') {
  return `
    <article>
      <p class="eyebrow">${escapeHtml(label)}</p>
      <strong>${escapeHtml(value)}</strong>
      ${note ? `<p class="muted">${escapeHtml(note)}</p>` : ''}
    </article>
  `;
}

export function describeMissionLocus(mission) {
  const delegated = mission.delegated_runtime_sessions || [];
  if (delegated.some(item => item.status === 'waiting_for_approval')) {
    return 'Delegated / approval-blocked';
  }
  if (delegated.some(item => ['launching', 'running'].includes(item.status))) {
    return 'Delegated / active';
  }
  if ((mission.proof?.pending_approvals || []).length) {
    return 'Local / approval-blocked';
  }
  return 'Local / direct';
}
