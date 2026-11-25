import React from 'react';
import {
  Archive,
  FolderGit2,
  FolderKanban,
  Layers,
  Moon,
  Settings,
  ShieldAlert,
  Star,
  Sun,
  Zap,
} from 'lucide-react';
import { cn } from '../lib/utils';

export function Sidebar({
  workspacePath,
  categories,
  activeCategory,
  onSelectCategory,
  filterType,
  onSelectFilterType,
  stats,
  theme,
  onToggleTheme,
  onToggleOrganizer,
  onOpenQuarantine,
  onOpenSettings,
  onOpenWorkspaceRoot,
}) {
  const isAll = activeCategory === 'all' && filterType === 'all';
  const isPinned = activeCategory === 'favorites';
  const isAttention = filterType === 'unpushed';

  return (
    <aside className="flex w-full shrink-0 flex-col border-b bg-[var(--surface)] lg:sticky lg:top-0 lg:h-screen lg:w-[272px] lg:border-r lg:border-b-0">
      {/* Brand */}
      <div className="flex items-center gap-3 border-b px-5 py-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-[var(--accent-ink)]">
          <Zap className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14px] font-semibold tracking-tight text-[var(--ink)]">
            Workspace Navigator
          </div>
          <button
            type="button"
            onClick={onOpenWorkspaceRoot}
            title="Open Workspace folder in File Explorer"
            className="mt-0.5 block max-w-full truncate text-left font-mono text-[11px] text-[var(--ink-muted)] hover:text-[var(--accent-bright)] hover:underline cursor-pointer"
          >
            {workspacePath || 'Resolving...'}
          </button>
        </div>
      </div>

      {/* Primary Views */}
      <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Workspace Navigation">
        <div className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Views
        </div>
        <div className="space-y-1">
          <NavRow
            icon={Layers}
            label="All Workspace Items"
            count={stats.total ?? 0}
            active={isAll}
            onClick={() => {
              onSelectCategory('all');
              onSelectFilterType('all');
            }}
          />
          <NavRow
            icon={Star}
            label="Pinned"
            count={stats.favorites ?? 0}
            active={isPinned}
            onClick={() => {
              onSelectCategory('favorites');
              onSelectFilterType('all');
            }}
          />
          <NavRow
            icon={FolderGit2}
            label="Git Needs Attention"
            count={stats.unpushed_repos ?? 0}
            tone={stats.unpushed_repos > 0 ? 'amber' : 'neutral'}
            active={isAttention}
            onClick={() => {
              onSelectCategory('all');
              onSelectFilterType('unpushed');
            }}
          />
          <NavRow
            icon={Archive}
            label="Quarantine Vault"
            count={stats.quarantine_count ?? 0}
            tone={stats.quarantine_count > 0 ? 'violet' : 'neutral'}
            active={false}
            onClick={onOpenQuarantine}
          />
        </div>

        <div className="mt-6 px-2 pb-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Categories
        </div>
        <div className="space-y-1">
          {categories.map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => {
                onSelectCategory(cat.id);
                if (filterType === 'unpushed') onSelectFilterType('all');
              }}
              className={cn(
                'flex min-h-[40px] w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors cursor-pointer',
                activeCategory === cat.id && filterType !== 'unpushed'
                  ? 'bg-[var(--surface-elevated)] text-[var(--ink)] border border-[var(--border-strong)]'
                  : 'text-[var(--ink-secondary)] hover:bg-[var(--surface-elevated)] hover:text-[var(--ink)] border border-transparent'
              )}
            >
              <span className="flex min-w-0 items-center gap-2.5">
                <span className="text-[14px] leading-none">{cat.icon}</span>
                <span className="truncate">{cat.name}</span>
              </span>
              <span className="font-mono text-[11px] text-[var(--ink-muted)]">{cat.count}</span>
            </button>
          ))}
        </div>
      </nav>

      {/* Bottom Controls */}
      <div className="space-y-2 border-t p-3">
        <button
          type="button"
          onClick={onToggleOrganizer}
          className={cn(
            'flex min-h-[44px] w-full items-center justify-between rounded-lg border px-3 py-2 text-[12px] font-semibold transition-colors cursor-pointer',
            stats.organizer_enabled
              ? 'border-[color:var(--emerald)]/35 bg-[var(--emerald-soft)] text-[var(--emerald)]'
              : 'border-[var(--border-hairline)] bg-[var(--surface-elevated)] text-[var(--ink-secondary)] hover:border-[var(--border-strong)]'
          )}
        >
          <span className="flex items-center gap-2">
            <span
              className={cn(
                'h-2 w-2 rounded-full',
                stats.organizer_enabled ? 'bg-[var(--emerald)] shadow-[0_0_8px_var(--emerald)]' : 'bg-[var(--ink-muted)]'
              )}
            />
            Auto-Organizer
          </span>
          <span className="font-mono text-[11px]">
            {stats.organizer_enabled ? 'ACTIVE' : 'PAUSED'}
          </span>
        </button>

        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onToggleTheme}
            className="flex min-h-[44px] items-center justify-center gap-2 rounded-lg border bg-[var(--surface-elevated)] px-3 text-[12px] font-medium text-[var(--ink-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--ink)] cursor-pointer"
          >
            {theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
            <span>{theme === 'dark' ? 'Daylight' : 'Obsidian'}</span>
          </button>
          <button
            type="button"
            onClick={onOpenSettings}
            className="flex min-h-[44px] items-center justify-center gap-2 rounded-lg border bg-[var(--surface-elevated)] px-3 text-[12px] font-medium text-[var(--ink-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--ink)] cursor-pointer"
          >
            <Settings className="h-3.5 w-3.5" />
            <span>Settings</span>
          </button>
        </div>
      </div>
    </aside>
  );
}

function NavRow({ icon: Icon, label, count, active, tone = 'neutral', onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex min-h-[44px] w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-[13px] font-medium transition-colors cursor-pointer',
        active
          ? 'border-[var(--border-strong)] bg-[var(--surface-elevated)] text-[var(--ink)]'
          : 'border-transparent text-[var(--ink-secondary)] hover:bg-[var(--surface-elevated)] hover:text-[var(--ink)]'
      )}
    >
      <span className="flex min-w-0 items-center gap-2.5">
        <Icon className="h-4 w-4 shrink-0 text-[var(--ink-muted)]" />
        <span className="truncate">{label}</span>
      </span>
      <span
        className={cn(
          'rounded-md px-1.5 py-0.5 font-mono text-[11px]',
          tone === 'amber' && 'bg-[var(--amber-soft)] text-[var(--amber)]',
          tone === 'violet' && 'bg-[var(--violet-soft)] text-[var(--violet)]',
          tone === 'neutral' && 'text-[var(--ink-muted)]'
        )}
      >
        {count}
      </span>
    </button>
  );
}
