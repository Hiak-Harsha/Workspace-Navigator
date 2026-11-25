// Workspace Navigator Client Logic
let allItems = [];
let activeCategory = 'all';
let searchQuery = '';
let currentFilterType = 'all';
let currentSortBy = 'name';
let currentViewMode = localStorage.getItem('wn_view_mode') || 'grid';
let pendingDeletePath = null;
let pendingDeleteName = null;
let workspaceRootPath = '';

// DOM Elements
const searchInput = document.getElementById('searchInput');
const clearSearchBtn = document.getElementById('clearSearch');
const categoryNav = document.getElementById('categoryNav');
const cardsGrid = document.getElementById('cardsGrid');
const resultsCount = document.getElementById('resultsCount');
const filterTypeSelect = document.getElementById('filterType');
const sortBySelect = document.getElementById('sortBy');
const refreshBtn = document.getElementById('refreshBtn');
const statTotal = document.getElementById('statTotal');
const statCategories = document.getElementById('statCategories');
const statGit = document.getElementById('statGit');
const statUnpushed = document.getElementById('statUnpushed');
const statPolicy = document.getElementById('statPolicy');
const statDesktop = document.getElementById('statDesktop');
const workspaceLocation = document.getElementById('workspaceLocation');
const workspaceLocationBtn = document.getElementById('workspaceLocationBtn');
const toastEl = document.getElementById('toast');
const organizerPill = document.getElementById('organizerPill');
const organizerText = document.getElementById('organizerText');
const cleanDesktopBtn = document.getElementById('cleanDesktopBtn');
const themeSelect = document.getElementById('themeSelect');
const viewGridBtn = document.getElementById('viewGridBtn');
const viewListBtn = document.getElementById('viewListBtn');

// KPI Cards
const kpiAll = document.getElementById('kpiAll');
const kpiGit = document.getElementById('kpiGit');
const kpiUnpushed = document.getElementById('kpiUnpushed');
const kpiAudit = document.getElementById('kpiAudit');

// Preview Drawer
const previewDrawer = document.getElementById('previewDrawer');
const previewTypeLabel = document.getElementById('previewTypeLabel');
const previewTitle = document.getElementById('previewTitle');
const previewPath = document.getElementById('previewPath');
const previewActions = document.getElementById('previewActions');
const previewBody = document.getElementById('previewBody');
const previewCloseBtn = document.getElementById('previewCloseBtn');

// Clean Modal
const cleanModal = document.getElementById('cleanModal');
const cleanSummary = document.getElementById('cleanSummary');
const cleanResultsBody = document.getElementById('cleanResultsBody');
const cleanCloseBtn = document.getElementById('cleanCloseBtn');
const cleanCancelBtn = document.getElementById('cleanCancelBtn');
const cleanExecuteBtn = document.getElementById('cleanExecuteBtn');

// Delete Modal
const confirmModal = document.getElementById('confirmModal');
const modalTitle = document.getElementById('modalTitle');
const modalMessage = document.getElementById('modalMessage');
const modalCancelBtn = document.getElementById('modalCancelBtn');
const modalConfirmBtn = document.getElementById('modalConfirmBtn');

// Audit Modal
const auditDuplicatesBtn = document.getElementById('auditDuplicatesBtn');
const auditModal = document.getElementById('auditModal');
const auditCloseBtn = document.getElementById('auditCloseBtn');
const auditSummary = document.getElementById('auditSummary');
const auditIncludeDesktop = document.getElementById('auditIncludeDesktop');
const auditRescanBtn = document.getElementById('auditRescanBtn');
const auditSelectSafeBtn = document.getElementById('auditSelectSafeBtn');
const auditCleanupBtn = document.getElementById('auditCleanupBtn');
const auditResultsBody = document.getElementById('auditResultsBody');

// Settings Modal
const settingsBtn = document.getElementById('settingsBtn');
const settingsModal = document.getElementById('settingsModal');
const settingsCloseBtn = document.getElementById('settingsCloseBtn');
const settingsCancelBtn = document.getElementById('settingsCancelBtn');
const settingsForm = document.getElementById('settingsForm');
const cfgWorkspaceDir = document.getElementById('cfgWorkspaceDir');
const cfgDesktopDir = document.getElementById('cfgDesktopDir');
const cfgDupPolicy = document.getElementById('cfgDupPolicy');
const cfgMinAge = document.getElementById('cfgMinAge');

document.addEventListener('DOMContentLoaded', () => {
  initThemeAndView();
  fetchData();
  setupEventListeners();
});

function initThemeAndView() {
  const savedTheme = localStorage.getItem('wn_theme') || 'obsidian-cyan';
  document.documentElement.setAttribute('data-theme', savedTheme);
  themeSelect.value = savedTheme;
  applyViewMode(currentViewMode);
}

function applyViewMode(mode) {
  currentViewMode = mode === 'list' ? 'list' : 'grid';
  localStorage.setItem('wn_view_mode', currentViewMode);
  cardsGrid.classList.toggle('list-view', currentViewMode === 'list');
  viewGridBtn.classList.toggle('active', currentViewMode === 'grid');
  viewListBtn.classList.toggle('active', currentViewMode === 'list');
}

function showToast(message, isError = false) {
  toastEl.textContent = message;
  toastEl.style.borderColor = isError ? 'var(--rose-border)' : 'var(--accent-border)';
  toastEl.classList.add('show');
  setTimeout(() => {
    toastEl.classList.remove('show');
  }, 2800);
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let idx = 0;
  let val = bytes;
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx++;
  }
  return `${val.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

async function fetchData(forceRefresh = false) {
  cardsGrid.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Scanning workspace projects...</p>
    </div>
  `;

  try {
    const res = await fetch(forceRefresh ? '/api/projects?refresh=1' : '/api/projects');
    if (!res.ok) throw new Error('Failed to load data');
    const data = await res.json();
    allItems = data.items || [];
    workspaceRootPath = data.workspace_path || '';

    statTotal.textContent = data.stats.total ?? allItems.length;
    statCategories.textContent = `${data.stats.categories ?? 0} categories`;
    statGit.textContent = data.stats.git_repos ?? 0;
    const attentionCount = allItems.filter(isUnpushedOrLocalGit).length;
    statUnpushed.textContent = attentionCount;
    statPolicy.textContent = String(data.stats.duplicate_policy || 'recycle').toUpperCase();
    statDesktop.textContent = data.desktop_path || 'Desktop auto-detected';

    if (workspaceRootPath) {
      workspaceLocation.textContent = workspaceRootPath;
    }

    updateOrganizerUI(data.stats.organizer_enabled);
    renderCategories();
    applyFilterAndSort();
  } catch (err) {
    console.error(err);
    cardsGrid.innerHTML = `
      <div class="empty-state">
        <p style="color: var(--rose); font-size: 16px;">Unable to connect to Navigator server.</p>
        <p style="margin-top: 8px;">Ensure server.py is running on port 8585.</p>
        <button onclick="fetchData(true)" class="btn" style="margin: 16px auto;">Retry Connection</button>
      </div>
    `;
  }
}

function updateOrganizerUI(isEnabled) {
  if (isEnabled) {
    organizerPill.classList.add('active');
    organizerText.textContent = 'Auto-Organizer: ON';
    organizerPill.title = 'Desktop Auto-Organizer is ACTIVE. Click to pause.';
  } else {
    organizerPill.classList.remove('active');
    organizerText.textContent = 'Auto-Organizer: PAUSED';
    organizerPill.title = 'Desktop Auto-Organizer is PAUSED. Click to enable.';
  }
}

function renderCategories() {
  const categoryCounts = {};
  let favoriteCount = 0;

  allItems.forEach(item => {
    categoryCounts[item.category] = (categoryCounts[item.category] || 0) + 1;
    if (item.is_favorite) favoriteCount++;
  });

  const categories = [
    { id: 'all', name: 'All Items', icon: '◆', count: allItems.length },
    { id: 'favorites', name: 'Pinned', icon: '★', count: favoriteCount },
    ...Object.keys(categoryCounts).map(cat => ({
      id: cat,
      name: cat,
      icon: allItems.find(i => i.category === cat)?.category_icon || '📁',
      count: categoryCounts[cat]
    }))
  ];

  categoryNav.innerHTML = categories.map(cat => `
    <button class="cat-tab ${activeCategory === cat.id ? 'active' : ''}" data-cat="${escapeHtml(cat.id)}">
      <span>${cat.icon}</span>
      <span>${escapeHtml(cat.name)}</span>
      <span class="cat-badge">${cat.count}</span>
    </button>
  `).join('');

  categoryNav.querySelectorAll('.cat-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      categoryNav.querySelectorAll('.cat-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeCategory = tab.dataset.cat;
      applyFilterAndSort();
    });
  });
}

function isUnpushedOrLocalGit(item) {
  if (!item.is_git || !item.git_info) return false;
  return !item.git_info.has_remote || (item.git_info.unpushed_count || 0) > 0 || (item.git_info.dirty_count || 0) > 0;
}

function applyFilterAndSort() {
  let filtered = [...allItems];

  if (activeCategory === 'favorites') {
    filtered = filtered.filter(i => i.is_favorite);
  } else if (activeCategory !== 'all') {
    filtered = filtered.filter(i => i.category === activeCategory);
  }

  if (currentFilterType === 'git') {
    filtered = filtered.filter(i => i.is_git);
  } else if (currentFilterType === 'unpushed') {
    filtered = filtered.filter(isUnpushedOrLocalGit);
  } else if (currentFilterType === 'folders') {
    filtered = filtered.filter(i => i.is_dir);
  } else if (currentFilterType === 'files') {
    filtered = filtered.filter(i => !i.is_dir);
  }

  if (searchQuery.trim()) {
    const q = searchQuery.toLowerCase().trim();
    filtered = filtered.filter(i =>
      i.name.toLowerCase().includes(q) ||
      i.category.toLowerCase().includes(q) ||
      i.path.toLowerCase().includes(q)
    );
  }

  if (currentSortBy === 'name') {
    filtered.sort((a, b) => a.name.localeCompare(b.name));
  } else if (currentSortBy === 'category') {
    filtered.sort((a, b) => a.category.localeCompare(b.category) || a.name.localeCompare(b.name));
  } else if (currentSortBy === 'date') {
    filtered.sort((a, b) => b.last_modified.localeCompare(a.last_modified));
  }

  renderCards(filtered);
}

function renderGitBadge(item) {
  if (!item.is_git) return '';
  const g = item.git_info;
  if (!g) return '<span class="git-badge">GIT</span>';

  const branch = g.branch ? escapeHtml(g.branch) : 'git';
  if (!g.has_remote) {
    return `<span class="git-badge git-local" title="Local Git repo with no GitHub remote">${branch} · no remote</span>`;
  }
  if (g.unpushed_count > 0) {
    return `<span class="git-badge git-unpushed" title="${g.unpushed_count} unpushed commit(s)">${branch} · ↑${g.unpushed_count}</span>`;
  }
  if (g.dirty_count > 0) {
    return `<span class="git-badge git-dirty" title="${g.dirty_count} uncommitted change(s)">${branch} · *${g.dirty_count}</span>`;
  }
  return `<span class="git-badge" title="Synced with remote">${branch}</span>`;
}

function getTypeSvg(isDir) {
  if (isDir) {
    return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';
  }
  return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>';
}

function renderCards(items) {
  resultsCount.textContent = `Showing ${items.length} of ${allItems.length} items`;

  if (items.length === 0) {
    cardsGrid.innerHTML = `
      <div class="empty-state">
        <p style="font-size: 16px;">No matching items found</p>
        <p style="margin-top: 6px;">Try adjusting your search query or filters.</p>
      </div>
    `;
    return;
  }

  cardsGrid.innerHTML = items.map(item => `
    <article class="project-card" data-id="${escapeHtml(item.id)}" data-path="${escapeHtml(item.path)}">
      <div class="card-head-block">
        <div class="card-top">
          <span class="card-cat-badge">
            <span>${item.category_icon}</span>
            <span>${escapeHtml(item.category)}</span>
          </span>
          <div class="card-top-right">
            <button class="card-icon-btn card-fav-btn ${item.is_favorite ? 'is-fav' : ''}" data-path="${escapeHtml(item.path)}" data-name="${escapeHtml(item.name)}" title="${item.is_favorite ? 'Unpin' : 'Pin to favorites'}">
              ${item.is_favorite ? '★' : '☆'}
            </button>
            <button class="card-icon-btn del card-delete-btn" data-name="${escapeHtml(item.name)}" data-path="${escapeHtml(item.path)}" title="Delete to Windows Recycle Bin">
              ✕
            </button>
          </div>
        </div>

        <div class="card-title-row">
          <span class="type-icon">${getTypeSvg(item.is_dir)}</span>
          <h3 class="card-title" data-preview="${escapeHtml(item.path)}" title="Click to preview">${escapeHtml(item.name)}</h3>
          ${renderGitBadge(item)}
        </div>

        <div class="card-path" data-copy="${escapeHtml(item.path)}" title="Click to copy path: ${escapeHtml(item.path)}">
          ${escapeHtml(item.path)}
        </div>
      </div>

      <div class="card-foot-block">
        <div class="card-meta">
          <span>${escapeHtml(item.last_modified)}</span>
          <span>${item.is_dir ? 'Directory' : escapeHtml(item.extension.toUpperCase() + (item.size_bytes ? ` · ${formatBytes(item.size_bytes)}` : ''))}</span>
        </div>

        <div class="card-actions">
          <button class="btn btn-card btn-preview" data-preview="${escapeHtml(item.path)}" title="Quick Preview">Preview</button>
          <button class="btn btn-card" data-action="explorer" data-path="${escapeHtml(item.path)}" title="Open in File Explorer">Explorer</button>
          <button class="btn btn-card" data-action="vscode" data-path="${escapeHtml(item.path)}" title="Open in VS Code">VS Code</button>
          <button class="btn btn-card" data-action="terminal" data-path="${escapeHtml(item.path)}" title="Open PowerShell Terminal">Terminal</button>
        </div>
      </div>
    </article>
  `).join('');

  cardsGrid.querySelectorAll('[data-preview]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      openPreviewDrawer(el.dataset.preview);
    });
  });

  cardsGrid.querySelectorAll('[data-copy]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      if (navigator.clipboard) {
        navigator.clipboard.writeText(el.dataset.copy).then(() => {
          showToast('Path copied to clipboard');
        }).catch(() => {});
      }
    });
  });

  cardsGrid.querySelectorAll('.btn-card[data-action]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      triggerAction(btn.dataset.action, btn.dataset.path, btn);
    });
  });

  cardsGrid.querySelectorAll('.card-fav-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleFavorite(btn.dataset.path, btn.dataset.name);
    });
  });

  cardsGrid.querySelectorAll('.card-delete-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openDeleteModal(btn.dataset.name, btn.dataset.path);
    });
  });
}

// --- Quick Preview Drawer ---
async function openPreviewDrawer(targetPath) {
  previewDrawer.classList.add('show');
  previewDrawer.setAttribute('aria-hidden', 'false');
  previewTitle.textContent = 'Loading...';
  previewPath.textContent = targetPath;
  previewActions.innerHTML = '';
  previewBody.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Loading preview...</p></div>`;

  try {
    const res = await fetch(`/api/preview?path=${encodeURIComponent(targetPath)}`);
    const data = await res.json();
    if (!res.ok || !data.success) {
      previewBody.innerHTML = `<div class="empty-state"><p style="color:var(--rose);">${escapeHtml(data.error || 'Preview unavailable')}</p></div>`;
      return;
    }

    previewTypeLabel.textContent = data.kind === 'directory' ? 'DIRECTORY PREVIEW' : 'FILE PREVIEW';
    previewTitle.textContent = data.name;
    previewPath.textContent = data.path;

    previewActions.innerHTML = `
      <button class="btn btn-primary" data-daction="explorer">Open in Explorer</button>
      <button class="btn" data-daction="vscode">Open in VS Code</button>
      <button class="btn" data-daction="terminal">Open Terminal</button>
      ${data.kind === 'file' ? '<button class="btn" data-daction="default">Open Default App</button>' : ''}
    `;
    previewActions.querySelectorAll('[data-daction]').forEach(b => {
      b.addEventListener('click', () => triggerAction(b.dataset.daction, data.path, b));
    });

    let bodyHtml = '';
    if (data.git_info) {
      const g = data.git_info;
      bodyHtml += `
        <div class="preview-block">
          <h4>Git Repository Status</h4>
          <div class="preview-code">Branch: ${escapeHtml(g.branch || 'unknown')}
Remote: ${escapeHtml(g.remote_url || 'None (not pushed to GitHub)')}
Dirty files: ${g.dirty_count} | Unpushed commits: ${g.unpushed_count}</div>
        </div>
      `;
    }

    if (data.kind === 'directory') {
      const entries = data.entries || [];
      bodyHtml += `
        <div class="preview-block">
          <h4>Contents (${entries.length}${entries.length >= 60 ? '+' : ''} items)</h4>
          <div class="entry-list">
            ${entries.map(e => `
              <div class="entry-item">
                <span>${e.is_dir ? '📁' : '📄'} ${escapeHtml(e.name)}</span>
                <span>${e.is_dir ? 'DIR' : formatBytes(e.size)}</span>
              </div>
            `).join('') || '<span style="color:var(--text-muted);font-size:12px;">Empty directory</span>'}
          </div>
        </div>
      `;
      if (data.readme_text) {
        bodyHtml += `
          <div class="preview-block">
            <h4>${escapeHtml(data.readme_name || 'README')}</h4>
            <pre class="preview-code">${escapeHtml(data.readme_text)}</pre>
          </div>
        `;
      }
    } else {
      bodyHtml += `
        <div class="preview-block">
          <h4>Metadata</h4>
          <div class="preview-code">Size: ${formatBytes(data.size)} (${data.size} bytes)
Modified: ${escapeHtml(data.last_modified)}
Extension: ${escapeHtml(data.extension || 'none')}</div>
        </div>
      `;
      if (data.snippet !== null && data.snippet !== undefined) {
        bodyHtml += `
          <div class="preview-block">
            <h4>File Content ${data.truncated ? '(First 8 KB)' : ''}</h4>
            <pre class="preview-code">${escapeHtml(data.snippet)}</pre>
          </div>
        `;
      }
    }
    previewBody.innerHTML = bodyHtml;
  } catch (err) {
    previewBody.innerHTML = `<div class="empty-state"><p style="color:var(--rose);">Failed to load preview.</p></div>`;
  }
}

function closePreviewDrawer() {
  previewDrawer.classList.remove('show');
  previewDrawer.setAttribute('aria-hidden', 'true');
}

async function triggerAction(action, path, btnEl = null) {
  const originalHtml = btnEl ? btnEl.innerHTML : null;
  const actionNames = {
    explorer: 'File Explorer',
    vscode: 'VS Code',
    terminal: 'PowerShell Terminal',
    default: 'Default Application'
  };

  if (btnEl) {
    btnEl.innerHTML = 'Opening...';
    btnEl.disabled = true;
  }

  try {
    const res = await fetch('/api/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, path })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Opened in ${actionNames[action] || action}`);
      if (btnEl) btnEl.innerHTML = 'Opened';
    } else {
      showToast(`Error: ${data.message || data.error}`, true);
    }
  } catch (err) {
    showToast('Failed to communicate with server', true);
  } finally {
    if (btnEl) {
      setTimeout(() => {
        btnEl.innerHTML = originalHtml;
        btnEl.disabled = false;
      }, 1300);
    }
  }
}

function openDeleteModal(name, path) {
  pendingDeleteName = name;
  pendingDeletePath = path;
  modalTitle.textContent = `Delete "${name}"?`;
  modalMessage.textContent = `This will safely move "${name}" to your Windows Recycle Bin.`;
  confirmModal.classList.add('show');
}

function closeDeleteModal() {
  confirmModal.classList.remove('show');
  pendingDeleteName = null;
  pendingDeletePath = null;
}

async function executeDelete() {
  if (!pendingDeletePath) return;

  const targetPath = pendingDeletePath;
  const targetName = pendingDeleteName;
  closeDeleteModal();

  try {
    const res = await fetch('/api/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: targetPath })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Moved "${targetName}" to Recycle Bin`);
      allItems = allItems.filter(i => i.path !== targetPath);
      statTotal.textContent = allItems.length;
      renderCategories();
      applyFilterAndSort();
    } else {
      showToast(`Error: ${data.error || 'Failed to delete'}`, true);
    }
  } catch (err) {
    showToast('Failed to execute delete request', true);
  }
}

async function toggleFavorite(path, name) {
  try {
    const res = await fetch('/api/toggle-favorite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, name })
    });
    const data = await res.json();
    if (data.success) {
      const item = allItems.find(i => i.path === path);
      if (item) item.is_favorite = data.is_favorite;
      renderCategories();
      applyFilterAndSort();
    }
  } catch (err) {
    console.error(err);
  }
}

// --- Clean Desktop Dry-Run Preview & Execution ---
async function openCleanDesktopPreview() {
  cleanModal.classList.add('show');
  cleanSummary.textContent = 'Scanning Desktop items (dry-run)...';
  cleanResultsBody.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Checking classification and SHA-256 duplicates...</p></div>`;
  cleanExecuteBtn.disabled = true;

  try {
    const [dryRes, statusRes] = await Promise.all([
      fetch('/api/organize-desktop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dry_run: true })
      }),
      fetch('/api/organizer-status')
    ]);
    const dryData = await dryRes.json();
    const statusData = await statusRes.json();
    const planned = dryData.moved_items || [];
    const recent = statusData.recent_moves || [];

    cleanSummary.textContent = planned.length > 0
      ? `${planned.length} Desktop item(s) ready to organize or deduplicate.`
      : 'Desktop is already clean — no loose items need moving.';
    cleanExecuteBtn.disabled = planned.length === 0;

    let html = '';
    if (planned.length > 0) {
      html += `<div class="audit-section"><h4>Planned Actions</h4>`;
      html += planned.map(p => `
        <div class="audit-row">
          <div class="audit-check-label">
            <span>${p.Type === 'Folder' ? '📁' : '📄'}</span>
            <strong>${escapeHtml(p.Item)}</strong>
            <span class="audit-tag ${String(p.Status).includes('Recycle') ? 'tag-warn' : 'tag-safe'}">${escapeHtml(p.Status)}</span>
          </div>
          <div class="audit-meta"><code>${escapeHtml(p.From)}</code> → <code>${escapeHtml(p.To)}</code></div>
        </div>
      `).join('');
      html += `</div>`;
    } else {
      html += `<div class="empty-state" style="padding:28px;"><p>Desktop has no unorganized files or folders.</p></div>`;
    }

    if (recent.length > 0) {
      html += `<div class="audit-section"><h4>Recent Auto-Organizer Activity</h4>`;
      html += recent.slice(0, 8).map(r => `
        <div class="audit-row">
          <div class="audit-check-label"><strong>${escapeHtml(r.Item)}</strong> <span class="audit-tag tag-safe">${escapeHtml(r.Status)}</span></div>
          <div class="audit-meta">${escapeHtml(r.Timestamp || '')} · <code>${escapeHtml(r.To)}</code></div>
        </div>
      `).join('');
      html += `</div>`;
    }
    cleanResultsBody.innerHTML = html;
  } catch (err) {
    cleanResultsBody.innerHTML = `<div class="empty-state"><p style="color:var(--rose);">Failed to scan Desktop.</p></div>`;
  }
}

async function executeCleanDesktop() {
  cleanExecuteBtn.disabled = true;
  cleanExecuteBtn.textContent = 'Organizing...';
  try {
    const res = await fetch('/api/organize-desktop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dry_run: false })
    });
    const data = await res.json();
    cleanModal.classList.remove('show');
    showToast(`Organized / deduplicated ${data.moved_count || 0} item(s)`);
    fetchData(true);
  } catch (err) {
    showToast('Error organizing desktop', true);
  } finally {
    cleanExecuteBtn.textContent = 'Confirm & Organize';
  }
}

async function toggleAutoOrganizer() {
  try {
    const res = await fetch('/api/toggle-organizer', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      updateOrganizerUI(data.enabled);
      showToast(`Auto-Organizer ${data.enabled ? 'Enabled' : 'Paused'}`);
    }
  } catch (err) {
    showToast('Error toggling organizer', true);
  }
}

// --- Redundant & Duplicate Audit ---
async function openAuditModal(forceRefresh = false) {
  auditModal.classList.add('show');
  auditResultsBody.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Scanning SHA-256 hashes and numbered copies...</p></div>`;
  auditCleanupBtn.disabled = true;
  auditCleanupBtn.textContent = 'Recycle Selected (0)';

  try {
    const includeDt = auditIncludeDesktop.checked ? '1' : '0';
    const ref = forceRefresh ? '1' : '0';
    const res = await fetch(`/api/duplicates?refresh=${ref}&include_desktop=${includeDt}`);
    const report = await res.json();
    renderAuditReport(report);
  } catch (err) {
    auditResultsBody.innerHTML = `<div class="empty-state"><p style="color:var(--rose);">Failed to run redundancy scan.</p></div>`;
  }
}

function updateAuditSelectionCount() {
  const checked = auditResultsBody.querySelectorAll('.audit-check:checked');
  auditCleanupBtn.textContent = `Recycle Selected (${checked.length})`;
  auditCleanupBtn.disabled = checked.length === 0;
}

function renderAuditReport(report) {
  const dupGroups = report.duplicate_groups || [];
  const collisions = report.folder_collisions || [];
  const junk = report.junk_items || [];

  auditSummary.textContent =
    `Scanned ${report.scanned_files} files · ${report.redundant_file_count} exact duplicates · ` +
    `${collisions.length} numbered folders · ${junk.length} junk/empty items · ` +
    `Reclaimable: ${formatBytes(report.reclaimable_bytes)}`;

  if (dupGroups.length === 0 && collisions.length === 0 && junk.length === 0) {
    auditResultsBody.innerHTML = `<div class="empty-state"><p style="font-size:16px;">Workspace is clean — no redundant files detected.</p></div>`;
    return;
  }

  let html = '';

  if (collisions.length > 0) {
    html += `<div class="audit-section"><h4>Numbered Collision Folders (${collisions.length})</h4>`;
    html += collisions.map(c => `
      <div class="audit-row">
        <label class="audit-check-label">
          <input type="checkbox" class="audit-check" data-safe="${c.safe_to_recycle ? '1' : '0'}" value="${escapeHtml(c.path)}">
          <span><strong>${escapeHtml(c.name)}</strong></span>
          <span class="audit-tag ${c.safe_to_recycle ? 'tag-safe' : 'tag-warn'}">${escapeHtml(c.relation)}</span>
        </label>
        <div class="audit-meta">${c.file_count} files · ${formatBytes(c.size)} · <code>${escapeHtml(c.path)}</code></div>
      </div>
    `).join('');
    html += `</div>`;
  }

  if (dupGroups.length > 0) {
    html += `<div class="audit-section"><h4>Exact SHA-256 File Duplicates (${dupGroups.length} groups)</h4>`;
    html += dupGroups.slice(0, 80).map(g => `
      <div class="audit-group">
        <div class="audit-keep">KEEP (${formatBytes(g.size)}): <code>${escapeHtml(g.keep.path)}</code></div>
        ${g.duplicates.map(d => `
          <label class="audit-check-label audit-dup-item">
            <input type="checkbox" class="audit-check" data-safe="1" value="${escapeHtml(d.path)}">
            <span>REDUNDANT: <code>${escapeHtml(d.path)}</code></span>
          </label>
        `).join('')}
      </div>
    `).join('');
    html += `</div>`;
  }

  if (junk.length > 0) {
    html += `<div class="audit-section"><h4>Empty / Temporary Artifacts (${junk.length})</h4>`;
    html += junk.slice(0, 100).map(j => `
      <div class="audit-row">
        <label class="audit-check-label">
          <input type="checkbox" class="audit-check" data-safe="1" value="${escapeHtml(j.path)}">
          <span><strong>${escapeHtml(j.name)}</strong></span>
          <span class="audit-tag tag-safe">${escapeHtml(j.reason)}</span>
        </label>
        <div class="audit-meta"><code>${escapeHtml(j.path)}</code></div>
      </div>
    `).join('');
    html += `</div>`;
  }

  auditResultsBody.innerHTML = html;
  auditResultsBody.querySelectorAll('.audit-check').forEach(cb => {
    cb.addEventListener('change', updateAuditSelectionCount);
  });
}

async function cleanupSelectedDuplicates() {
  const paths = Array.from(auditResultsBody.querySelectorAll('.audit-check:checked')).map(cb => cb.value);
  if (paths.length === 0) return;

  auditCleanupBtn.disabled = true;
  auditCleanupBtn.textContent = 'Recycling...';
  try {
    const res = await fetch('/api/cleanup-duplicates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths })
    });
    const data = await res.json();
    showToast(`Moved ${data.removed_count || 0} redundant item(s) to Recycle Bin`);
    await openAuditModal(true);
    fetchData(true);
  } catch (err) {
    showToast('Cleanup failed', true);
    updateAuditSelectionCount();
  }
}

// --- Settings Modal ---
async function openSettingsModal() {
  settingsModal.classList.add('show');
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();
    cfgWorkspaceDir.value = cfg.workspace_dir || '';
    cfgDesktopDir.value = cfg.desktop_dir || '';
    cfgDupPolicy.value = cfg.duplicate_policy || 'recycle';
    cfgMinAge.value = cfg.min_age_seconds ?? 20;
  } catch (err) {
    showToast('Failed to load settings', true);
  }
}

async function saveSettings(e) {
  e.preventDefault();
  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_dir: cfgWorkspaceDir.value,
        desktop_dir: cfgDesktopDir.value,
        duplicate_policy: cfgDupPolicy.value,
        min_age_seconds: Number(cfgMinAge.value || 20)
      })
    });
    const data = await res.json();
    if (data.success) {
      settingsModal.classList.remove('show');
      showToast('Settings saved & Workspace initialized');
      fetchData(true);
    } else {
      showToast(`Error: ${data.error}`, true);
    }
  } catch (err) {
    showToast('Failed to save settings', true);
  }
}

function setupEventListeners() {
  workspaceLocationBtn.addEventListener('click', () => {
    if (workspaceRootPath) triggerAction('explorer', workspaceRootPath);
  });

  themeSelect.addEventListener('change', (e) => {
    const t = e.target.value;
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('wn_theme', t);
  });

  viewGridBtn.addEventListener('click', () => applyViewMode('grid'));
  viewListBtn.addEventListener('click', () => applyViewMode('list'));

  kpiAll.addEventListener('click', () => {
    activeCategory = 'all';
    currentFilterType = 'all';
    filterTypeSelect.value = 'all';
    renderCategories();
    applyFilterAndSort();
  });
  kpiGit.addEventListener('click', () => {
    activeCategory = 'all';
    currentFilterType = 'git';
    filterTypeSelect.value = 'git';
    renderCategories();
    applyFilterAndSort();
  });
  kpiUnpushed.addEventListener('click', () => {
    activeCategory = 'all';
    currentFilterType = 'unpushed';
    filterTypeSelect.value = 'unpushed';
    renderCategories();
    applyFilterAndSort();
  });
  kpiAudit.addEventListener('click', () => openAuditModal(false));

  searchInput.addEventListener('input', (e) => {
    searchQuery = e.target.value;
    clearSearchBtn.style.display = searchQuery ? 'block' : 'none';
    applyFilterAndSort();
  });

  clearSearchBtn.addEventListener('click', () => {
    searchInput.value = '';
    searchQuery = '';
    clearSearchBtn.style.display = 'none';
    searchInput.focus();
    applyFilterAndSort();
  });

  filterTypeSelect.addEventListener('change', (e) => {
    currentFilterType = e.target.value;
    applyFilterAndSort();
  });

  sortBySelect.addEventListener('change', (e) => {
    currentSortBy = e.target.value;
    applyFilterAndSort();
  });

  refreshBtn.addEventListener('click', () => {
    fetchData(true);
    showToast('Workspace rescanned');
  });

  cleanDesktopBtn.addEventListener('click', openCleanDesktopPreview);
  cleanCloseBtn.addEventListener('click', () => cleanModal.classList.remove('show'));
  cleanCancelBtn.addEventListener('click', () => cleanModal.classList.remove('show'));
  cleanExecuteBtn.addEventListener('click', executeCleanDesktop);
  cleanModal.addEventListener('click', (e) => {
    if (e.target === cleanModal) cleanModal.classList.remove('show');
  });

  organizerPill.addEventListener('click', toggleAutoOrganizer);

  previewCloseBtn.addEventListener('click', closePreviewDrawer);
  previewDrawer.addEventListener('click', (e) => {
    if (e.target === previewDrawer) closePreviewDrawer();
  });

  modalCancelBtn.addEventListener('click', closeDeleteModal);
  modalConfirmBtn.addEventListener('click', executeDelete);
  confirmModal.addEventListener('click', (e) => {
    if (e.target === confirmModal) closeDeleteModal();
  });

  auditDuplicatesBtn.addEventListener('click', () => openAuditModal(false));
  auditCloseBtn.addEventListener('click', () => auditModal.classList.remove('show'));
  auditRescanBtn.addEventListener('click', () => openAuditModal(true));
  auditIncludeDesktop.addEventListener('change', () => openAuditModal(true));
  auditSelectSafeBtn.addEventListener('click', () => {
    auditResultsBody.querySelectorAll('.audit-check[data-safe="1"]').forEach(cb => {
      cb.checked = true;
    });
    updateAuditSelectionCount();
  });
  auditCleanupBtn.addEventListener('click', cleanupSelectedDuplicates);
  auditModal.addEventListener('click', (e) => {
    if (e.target === auditModal) auditModal.classList.remove('show');
  });

  settingsBtn.addEventListener('click', openSettingsModal);
  settingsCloseBtn.addEventListener('click', () => settingsModal.classList.remove('show'));
  settingsCancelBtn.addEventListener('click', () => settingsModal.classList.remove('show'));
  settingsForm.addEventListener('submit', saveSettings);
  settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) settingsModal.classList.remove('show');
  });

  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey && e.key.toLowerCase() === 'k') || (e.key === '/' && document.activeElement.tagName !== 'INPUT')) {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
    if (e.key === 'Escape') {
      closePreviewDrawer();
      cleanModal.classList.remove('show');
      confirmModal.classList.remove('show');
      auditModal.classList.remove('show');
      settingsModal.classList.remove('show');
      if (document.activeElement === searchInput) {
        searchInput.value = '';
        searchQuery = '';
        clearSearchBtn.style.display = 'none';
        searchInput.blur();
        applyFilterAndSort();
      }
    }
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
