import React, { useEffect, useMemo, useState } from 'react';
import { LayoutGrid, List, PanelLeftOpen, Power, RefreshCw, Search, ShieldCheck, Sparkles } from 'lucide-react';
import { api } from './lib/api';
import { cn, naturalCompare } from './lib/utils';
import { Sidebar } from './components/Sidebar';
import { BentoOverview } from './components/BentoOverview';
import { ProjectCard } from './components/ProjectCard';
import { PreviewSheet } from './components/PreviewSheet';
import { CleanDesktopSheet } from './components/CleanDesktopSheet';
import { AuditSheet } from './components/AuditSheet';
import { SettingsSheet } from './components/SettingsSheet';
import { CommandPalette } from './components/CommandPalette';
import { DeleteDialog } from './components/DeleteDialog';
import { CloseDialog } from './components/CloseDialog';
import { Button } from './components/ui/Button';
import { ShimmerButton } from './components/magic/ShimmerButton';

function isGitAttention(item) {
  if (!item.is_git || !item.git_info) return false;
  const g = item.git_info;
  return !g.has_remote || (g.unpushed_count || 0) > 0 || (g.dirty_count || 0) > 0;
}

function gitAttentionScore(item) {
  if (!item.is_git || !item.git_info) return 3;
  const g = item.git_info;
  if (!g.has_remote || (g.unpushed_count || 0) > 0) return 0;
  if ((g.dirty_count || 0) > 0) return 1;
  return 2;
}

export default function App() {
  const [items, setItems] = useState([]);
  const [categoryOrder, setCategoryOrder] = useState([]);
  const [stats, setStats] = useState({});
  const [workspacePath, setWorkspacePath] = useState('');
  const [loading, setLoading] = useState(true);

  const [activeCategory, setActiveCategory] = useState('all');
  const [filterType, setFilterType] = useState('all');
  const [sortBy, setSortBy] = useState('name');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('wn_view_mode') || 'grid');
  const [theme, setTheme] = useState(() => localStorage.getItem('wn_theme_v2') || 'light');
  const [sidebarOpen, setSidebarOpen] = useState(() => localStorage.getItem('wn_sidebar_open') !== 'false');

  const [previewPath, setPreviewPath] = useState(null);
  const [cleanOpen, setCleanOpen] = useState(false);
  const [auditState, setAuditState] = useState({ open: false, tab: 'scan' });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [closingBusy, setClosingBusy] = useState(false);
  const [closedNotice, setClosedNotice] = useState(null);
  const [toast, setToast] = useState({ msg: '', error: false, visible: false });

  useEffect(() => {
    const html = document.documentElement;
    html.classList.remove('dark', 'light');
    html.classList.add(theme === 'dark' ? 'dark' : 'light');
    localStorage.setItem('wn_theme_v2', theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem('wn_view_mode', viewMode);
  }, [viewMode]);

  useEffect(() => {
    localStorage.setItem('wn_sidebar_open', String(sidebarOpen));
  }, [sidebarOpen]);

  const showToast = (msg, error = false) => {
    setToast({ msg, error, visible: true });
    setTimeout(() => setToast((t) => ({ ...t, visible: false })), 2800);
  };

  const loadWorkspace = async (refresh = false) => {
    setLoading(true);
    try {
      const data = await api.getProjects(refresh);
      setItems(data.items || []);
      setCategoryOrder(data.category_order || []);
      setStats(data.stats || {});
      setWorkspacePath(data.workspace_path || '');
    } catch (err) {
      showToast(err.message || 'Failed to connect to Workspace Navigator server', true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkspace(false);
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey && e.key.toLowerCase() === 'k') || (e.key === '/' && document.activeElement?.tagName !== 'INPUT')) {
        e.preventDefault();
        setCmdOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const categories = useMemo(() => {
    const counts = {};
    const icons = {};
    items.forEach((item) => {
      counts[item.category] = (counts[item.category] || 0) + 1;
      if (!icons[item.category]) icons[item.category] = item.category_icon || '📁';
    });
    return Object.keys(counts)
      .sort((a, b) => {
        const ra = categoryOrder.indexOf(a);
        const rb = categoryOrder.indexOf(b);
        const na = ra === -1 ? 999 : ra;
        const nb = rb === -1 ? 999 : rb;
        return na !== nb ? na - nb : naturalCompare(a, b);
      })
      .map((name) => ({ id: name, name, icon: icons[name], count: counts[name] }));
  }, [items, categoryOrder]);

  const gitRepos = useMemo(() => items.filter((i) => i.is_git), [items]);

  const filteredItems = useMemo(() => {
    let list = [...items];
    if (activeCategory === 'favorites') {
      list = list.filter((i) => i.is_favorite);
    } else if (activeCategory !== 'all') {
      list = list.filter((i) => i.category === activeCategory);
    }

    if (filterType === 'git') list = list.filter((i) => i.is_git);
    else if (filterType === 'unpushed') list = list.filter(isGitAttention);
    else if (filterType === 'folders') list = list.filter((i) => i.is_dir);
    else if (filterType === 'files') list = list.filter((i) => !i.is_dir);

    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter(
        (i) =>
          i.name.toLowerCase().includes(q) ||
          i.category.toLowerCase().includes(q) ||
          i.path.toLowerCase().includes(q) ||
          (i.git_info?.branch || '').toLowerCase().includes(q)
      );
    }

    if (sortBy === 'name') {
      list.sort((a, b) => naturalCompare(a.name, b.name));
    } else if (sortBy === 'category') {
      list.sort((a, b) => {
        const ra = categoryOrder.indexOf(a.category);
        const rb = categoryOrder.indexOf(b.category);
        const na = ra === -1 ? 999 : ra;
        const nb = rb === -1 ? 999 : rb;
        if (na !== nb) return na - nb;
        const c = naturalCompare(a.category, b.category);
        return c !== 0 ? c : naturalCompare(a.name, b.name);
      });
    } else if (sortBy === 'git_attention') {
      list.sort((a, b) => {
        const s = gitAttentionScore(a) - gitAttentionScore(b);
        return s !== 0 ? s : naturalCompare(a.name, b.name);
      });
    } else if (sortBy === 'date') {
      list.sort((a, b) => String(b.last_modified).localeCompare(String(a.last_modified)));
    }
    return list;
  }, [items, activeCategory, filterType, searchQuery, sortBy, categoryOrder]);

  const handleOpenAction = async (action, targetPath) => {
    try {
      const res = await api.openTarget(action, targetPath);
      showToast(res.message || `Opened (${action})`);
    } catch (err) {
      showToast(err.message || `Failed to open (${action})`, true);
    }
  };

  const handleToggleFavorite = async (item) => {
    try {
      const res = await api.toggleFavorite(item.path, item.name);
      setItems((prev) =>
        prev.map((p) => (p.path === item.path ? { ...p, is_favorite: res.is_favorite } : p))
      );
    } catch (err) {
      showToast(err.message || 'Failed to update favorite', true);
    }
  };

  const handleDeleteConfirm = async (item) => {
    setPendingDelete(null);
    try {
      await api.deleteTarget(item.path);
      showToast(`Moved "${item.name}" to Windows Recycle Bin`);
      loadWorkspace(true);
    } catch (err) {
      showToast(err.message || 'Delete failed', true);
    }
  };

  const handleToggleOrganizer = async () => {
    try {
      const res = await api.toggleOrganizer();
      setStats((s) => ({ ...s, organizer_enabled: res.enabled }));
      showToast(`Auto-Organizer ${res.enabled ? 'Activated' : 'Paused'}`);
    } catch (err) {
      showToast(err.message || 'Toggle failed', true);
    }
  };

  const handleCopyPath = (p) => {
    navigator.clipboard?.writeText(p).then(() => showToast('Path copied to clipboard')).catch(() => {});
  };

  const handleCloseWindowOnly = () => {
    setCloseDialogOpen(false);
    window.close();
    setClosedNotice('window');
  };

  const handleStopServerAndClose = async () => {
    setClosingBusy(true);
    try {
      await api.shutdownServer();
    } catch {
      // Server may drop connection while shutting down
    } finally {
      setClosingBusy(false);
      setCloseDialogOpen(false);
      window.close();
      setClosedNotice('server');
    }
  };

  if (closedNotice) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--canvas)] p-6 text-[var(--ink)]">
        <div className="max-w-md rounded-xl border bg-[var(--surface)] p-8 text-center shadow-xl">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--surface-elevated)] text-[var(--accent-bright)]">
            <Power className="h-5 w-5" />
          </div>
          <h1 className="text-lg font-semibold">
            {closedNotice === 'server' ? 'Workspace Navigator Server Stopped' : 'Dashboard Closed'}
          </h1>
          <p className="mt-2 text-xs text-[var(--ink-muted)]">
            {closedNotice === 'server'
              ? 'The local server on port 8585 has stopped cleanly. You can close this browser tab.'
              : 'The background watcher is still running. You can close this browser tab or reopen the dashboard.'}
          </p>
          {closedNotice === 'window' && (
            <div className="mt-5 flex justify-center">
              <Button variant="primary" onClick={() => setClosedNotice(null)}>
                Reopen Dashboard
              </Button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-[var(--canvas)] text-[var(--ink)] lg:flex-row">
      {sidebarOpen && (
        <Sidebar
          workspacePath={workspacePath}
          categories={categories}
          activeCategory={activeCategory}
          onSelectCategory={setActiveCategory}
          filterType={filterType}
          onSelectFilterType={setFilterType}
          stats={stats}
          theme={theme}
          onToggleTheme={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
          onToggleOrganizer={handleToggleOrganizer}
          onOpenQuarantine={() => setAuditState({ open: true, tab: 'quarantine' })}
          onOpenSettings={() => setSettingsOpen(true)}
          onOpenWorkspaceRoot={() => workspacePath && handleOpenAction('explorer', workspacePath)}
          onCollapse={() => setSidebarOpen(false)}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Command Header */}
        <header className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-3 border-b bg-[var(--surface)]/95 px-6 py-3 backdrop-blur-md">
          <div className="flex min-w-[240px] flex-1 items-center gap-2.5 max-w-[520px]">
            {!sidebarOpen && (
              <Button
                variant="secondary"
                size="icon"
                title="Open Sidebar"
                aria-label="Open Sidebar"
                onClick={() => setSidebarOpen(true)}
              >
                <PanelLeftOpen className="h-4 w-4" />
              </Button>
            )}
            <div className="flex min-h-[44px] w-full items-center gap-2.5 rounded-lg border bg-[var(--input-bg)] px-3 focus-within:border-[var(--accent-bright)]">
              <Search className="h-4 w-4 text-[var(--ink-muted)]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter workspace or press Ctrl+K..."
                className="w-full bg-transparent text-[13px] text-[var(--ink)] outline-none placeholder:text-[var(--ink-muted)]"
              />
              <button
                type="button"
                onClick={() => setCmdOpen(true)}
                className="rounded border bg-[var(--surface-elevated)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--ink-muted)] hover:text-[var(--ink)] cursor-pointer"
              >
                Ctrl K
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <ShimmerButton onClick={() => setCleanOpen(true)}>
              <Sparkles className="h-4 w-4" />
              <span>Clean Desktop</span>
            </ShimmerButton>

            <Button
              variant="emerald"
              onClick={() => setAuditState({ open: true, tab: 'scan' })}
            >
              <ShieldCheck className="h-4 w-4" />
              <span>
                Redundant Audit{stats.quarantine_count ? ` (${stats.quarantine_count})` : ''}
              </span>
            </Button>

            <Button
              variant="secondary"
              size="icon"
              title="Force Rescan Workspace"
              onClick={() => {
                loadWorkspace(true);
                showToast('Rescanning Workspace...');
              }}
            >
              <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            </Button>

            <Button
              variant="outline"
              title="Close Dashboard or Stop Server"
              onClick={() => setCloseDialogOpen(true)}
            >
              <Power className="h-4 w-4" />
              <span>Close</span>
            </Button>
          </div>
        </header>

        {/* Main Content */}
        <main className="mx-auto w-full max-w-[1440px] flex-1 space-y-6 p-6">
          <BentoOverview
            stats={stats}
            gitRepos={gitRepos}
            onFilterAll={() => {
              setActiveCategory('all');
              setFilterType('all');
            }}
            onFilterGit={() => {
              setActiveCategory('all');
              setFilterType('git');
            }}
            onFilterAttention={() => {
              setActiveCategory('all');
              setFilterType('unpushed');
            }}
            onOpenQuarantine={() => setAuditState({ open: true, tab: 'quarantine' })}
            onPreviewPath={(p) => setPreviewPath(p)}
          />

          {/* Controls Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-[13px] font-medium text-[var(--ink-muted)]">
              Showing <span className="font-semibold text-[var(--ink)]">{filteredItems.length}</span> of{' '}
              {items.length} items
              {activeCategory !== 'all' && ` · ${activeCategory}`}
              {filterType !== 'all' && ` · ${filterType}`}
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              <div className="inline-flex rounded-lg border bg-[var(--surface)] p-1">
                <button
                  type="button"
                  onClick={() => setViewMode('grid')}
                  title="Grid view"
                  className={cn(
                    'inline-flex h-8 w-8 items-center justify-center rounded-md cursor-pointer',
                    viewMode === 'grid'
                      ? 'bg-[var(--accent)] text-[var(--accent-ink)]'
                      : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                  )}
                >
                  <LayoutGrid className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('list')}
                  title="List view"
                  className={cn(
                    'inline-flex h-8 w-8 items-center justify-center rounded-md cursor-pointer',
                    viewMode === 'list'
                      ? 'bg-[var(--accent)] text-[var(--accent-ink)]'
                      : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                  )}
                >
                  <List className="h-4 w-4" />
                </button>
              </div>

              <select
                aria-label="Filter type"
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="min-h-[40px] rounded-lg border bg-[var(--surface)] px-3 text-[12px] font-medium text-[var(--ink)] outline-none focus:border-[var(--accent-bright)]"
              >
                <option value="all">All Types</option>
                <option value="git">Git Repos Only</option>
                <option value="unpushed">Git Needs Attention</option>
                <option value="folders">Folders Only</option>
                <option value="files">Files Only</option>
              </select>

              <select
                aria-label="Sort by"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="min-h-[40px] rounded-lg border bg-[var(--surface)] px-3 text-[12px] font-medium text-[var(--ink)] outline-none focus:border-[var(--accent-bright)]"
              >
                <option value="name">Name (A–Z)</option>
                <option value="category">Category + Name</option>
                <option value="git_attention">Git Attention First</option>
                <option value="date">Recently Modified</option>
              </select>
            </div>
          </div>

          {/* Items Grid / List */}
          {loading ? (
            <div className="rounded-xl border bg-[var(--surface)] py-20 text-center text-sm text-[var(--ink-muted)]">
              Scanning workspace &amp; external project roots...
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="rounded-xl border bg-[var(--surface)] py-20 text-center">
              <div className="text-base font-medium text-[var(--ink)]">No matching items found</div>
              <div className="mt-1 text-xs text-[var(--ink-muted)]">
                Try clearing your search or selecting All Workspace Items.
              </div>
            </div>
          ) : (
            <section
              className={cn(
                viewMode === 'grid'
                  ? 'grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-3'
                  : 'flex flex-col gap-2'
              )}
            >
              {filteredItems.map((item) => (
                <ProjectCard
                  key={item.path}
                  item={item}
                  viewMode={viewMode}
                  onPreview={(p) => setPreviewPath(p)}
                  onOpenAction={handleOpenAction}
                  onToggleFavorite={handleToggleFavorite}
                  onDelete={(it) => setPendingDelete(it)}
                  onCopyPath={handleCopyPath}
                />
              ))}
            </section>
          )}
        </main>
      </div>

      {/* Slide-Over Drawers & Modals */}
      <PreviewSheet
        targetPath={previewPath}
        onClose={() => setPreviewPath(null)}
        onNavigate={(p) => setPreviewPath(p)}
        onOpenAction={handleOpenAction}
      />

      <CleanDesktopSheet
        open={cleanOpen}
        onClose={() => setCleanOpen(false)}
        onCompleted={() => loadWorkspace(true)}
        showToast={showToast}
      />

      <AuditSheet
        open={auditState.open}
        initialTab={auditState.tab}
        onClose={() => setAuditState((s) => ({ ...s, open: false }))}
        onChanged={() => loadWorkspace(true)}
        showToast={showToast}
      />

      <SettingsSheet
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={() => loadWorkspace(true)}
        showToast={showToast}
      />

      <CommandPalette
        open={cmdOpen}
        onClose={() => setCmdOpen(false)}
        items={items}
        onPreview={(p) => setPreviewPath(p)}
        onOpenAction={handleOpenAction}
      />

      <DeleteDialog
        item={pendingDelete}
        onCancel={() => setPendingDelete(null)}
        onConfirm={handleDeleteConfirm}
      />

      <CloseDialog
        open={closeDialogOpen}
        busy={closingBusy}
        onCancel={() => setCloseDialogOpen(false)}
        onCloseWindowOnly={handleCloseWindowOnly}
        onStopServerAndClose={handleStopServerAndClose}
      />

      {/* Toast */}
      <div
        role="status"
        aria-live="polite"
        className={cn(
          'fixed bottom-5 right-5 z-[110] rounded-lg border bg-[var(--surface-elevated)] px-4 py-2.5 text-[13px] font-medium shadow-xl transition-all duration-200',
          toast.error ? 'border-[var(--rose)] text-[var(--rose)]' : 'border-[var(--accent-bright)] text-[var(--ink)]',
          toast.visible ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-6 opacity-0'
        )}
      >
        {toast.msg}
      </div>
    </div>
  );
}
