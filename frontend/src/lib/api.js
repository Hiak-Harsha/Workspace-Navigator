async function requestJson(url, options = {}) {
  const res = await fetch(url, options);
  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }
  if (!res.ok) {
    throw new Error(data.error || data.message || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  getProjects: (refresh = false) =>
    requestJson(refresh ? '/api/projects?refresh=1' : '/api/projects'),

  getPreview: (path) =>
    requestJson(`/api/preview?path=${encodeURIComponent(path)}`),

  openTarget: (action, path) =>
    requestJson('/api/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, path }),
    }),

  deleteTarget: (path) =>
    requestJson('/api/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    }),

  toggleFavorite: (path, name) =>
    requestJson('/api/toggle-favorite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, name }),
    }),

  toggleOrganizer: () =>
    requestJson('/api/toggle-organizer', { method: 'POST' }),

  getOrganizerStatus: () =>
    requestJson('/api/organizer-status'),

  organizeDesktop: (dryRun = false) =>
    requestJson('/api/organize-desktop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dry_run: dryRun }),
    }),

  getDuplicates: (refresh = false, includeDesktop = false) =>
    requestJson(
      `/api/duplicates?refresh=${refresh ? '1' : '0'}&include_desktop=${includeDesktop ? '1' : '0'}`
    ),

  cleanupDuplicates: (paths) =>
    requestJson('/api/cleanup-duplicates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths }),
    }),

  getQuarantine: () =>
    requestJson('/api/quarantine'),

  quarantineItems: (paths, reason = 'Redundant copy') =>
    requestJson('/api/quarantine', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths, reason }),
    }),

  restoreQuarantine: (paths) =>
    requestJson('/api/quarantine/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths }),
    }),

  purgeQuarantine: (paths = null) =>
    requestJson('/api/quarantine/purge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths }),
    }),

  getConfig: () =>
    requestJson('/api/config'),

  saveConfig: (payload) =>
    requestJson('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
};
