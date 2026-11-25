import React from 'react';
import {
  Archive,
  FolderGit2,
  Layers,
  Moon,
  PanelLeftClose,
  Settings,
  Star,
  Sun,
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
  onCollapse,
}) {
  const isAll = activeCategory === 'all' && filterType === 'all';
  const isPinned = activeCategory === 'favorites';
  const isAttention = filterType === 'unpushed';

  return (
    <aside className="flex w-full shrink-0 flex-col border-b bg-[var(--surface-glass)] backdrop-blur-xl lg:sticky lg:top-0 lg:h-screen lg:w-[252px] lg:border-r lg:border-b-0">
      {/* Apple × Microsoft Brand Header */}
      <div className="flex items-center gap-2.5 border-b px-4 py-3.5">
        <div
          className="grid h-8 w-8 shrink-0 grid-cols-2 gap-0.5 rounded-lg border bg-[var(--surface)] p-1.5 shadow-apple"
          aria-hidden="true"
        >
          <span className="rounded-[2px] bg-[#D13438]" />
          <span className="rounded-[2px] bg-[#107C10]" />
          <span className="rounded-[2px] bg-[#0067B8]" />
          <span className="rounded-[2px] bg-[#FFB900]" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13.5px] font-semibold tracking-tight text-[var(--ink)]">
            Workspace Navigator
          </div>
          <button
            type="button"
            onClick={onOpenWorkspaceRoot}
            title="Open Workspace folder in File Explorer"
            className="block max-w-full truncate text-left font-mono text-[10.5px] text-[var(--ink-muted)] hover:text-[var(--accent-bright)] hover:underline cursor-pointer"
          >
            {workspacePath || 'Resolving...'}
          </button>
        </div>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            title="Close sidebar"
            aria-label="Close sidebar"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border bg-[var(--surface-elevated)] text-[var(--ink-muted)] transition hover:border-[var(--border-strong)] hover:text-[var(--ink)] cursor-pointer"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="thin-scroll flex-1 overflow-y-auto px-2.5 py-3" aria-label="Workspace Navigation">
        <div className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Overview
        </div>
        <div className="space-y-0.5">
          <NavRow
            icon={Layers}
            label="All Workspace"
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
            tone={stats.favorites > 0 ? 'amber' : 'neutral'}
            active={isPinned}
            onClick={() => {
              onSelectCategory('favorites');
              onSelectFilterType('all');
            }}
          />
          <NavRow
            icon={FolderGit2}
            label="Git Attention"
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

        <div className="mt-4 px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
          Domains
        </div>
        <div className="space-y-0.5">
          {categories.map((cat) => {
            const isActive = activeCategory === cat.id && filterType !== 'unpushed';
            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => {
                  onSelectCategory(cat.id);
                  if (filterType === 'unpushed') onSelectFilterType('all');
                }}
                className={cn(
                  'relative flex min-h-[34px] w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-[12.5px] font-medium transition-colors cursor-pointer',
                  isActive
                    ? 'bg-[var(--surface)] text-[var(--ink)] shadow-apple border border-[var(--border-hairline)]'
                    : 'text-[var(--ink-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)] border border-transparent'
                )}
              >
                {isActive && (
                  <span
                    aria-hidden="true"
                    className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-[var(--accent)]"
                  />
                )}
                <span className="flex min-w-0 items-center gap-2 pl-0.5">
                  <span className="text-[13px] leading-none">{cat.icon}</span>
                  <span className="truncate">{cat.name}</span>
                </span>
                <span className="font-mono text-[11px] text-[var(--ink-muted)]">{cat.count}</span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* Compact Footer Controls */}
      <div className="space-y-2 border-t p-2.5">
        <button
          type="button"
          onClick={onToggleOrganizer}
          className={cn(
            'flex min-h-[40px] w-full items-center justify-between rounded-lg border px-3 text-[12px] font-semibold transition-colors cursor-pointer',
            stats.organizer_enabled
              ? 'border-[color:var(--emerald)]/35 bg-[var(--emerald-soft)] text-[var(--emerald)]'
              : 'border-[var(--border-hairline)] bg-[var(--surface)] text-[var(--ink-secondary)] hover:border-[var(--border-strong)]'
          )}
        >
          <span className="flex items-center gap-2">
            <span
              className={cn(
                'h-2 w-2 rounded-full',
                stats.organizer_enabled
                  ? 'bg-[var(--emerald)] shadow-[0_0_8px_var(--emerald)]'
                  : 'bg-[var(--ink-muted)]'
              )}
            />
            Auto-Organizer
          </span>
          <span className="font-mono text-[10.5px]">
            {stats.organizer_enabled ? 'ACTIVE' : 'PAUSED'}
          </span>
        </button>

        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            onClick={onToggleTheme}
            className="flex min-h-[40px] items-center justify-center gap-1.5 rounded-lg border bg-[var(--surface)] px-2 text-[12px] font-medium text-[var(--ink-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--ink)] cursor-pointer"
          >
            {theme === 'light' ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
            <span>{theme === 'light' ? 'Space Gray' : 'Light Gray'}</span>
          </button>
          <button
            type="button"
            onClick={onOpenSettings}
            className="flex min-h-[40px] items-center justify-center gap-1.5 rounded-lg border bg-[var(--surface)] px-2 text-[12px] font-medium text-[var(--ink-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--ink)] cursor-pointer"
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
        'relative flex min-h-[36px] w-full items-center justify-between gap-2 rounded-lg border px-2.5 py-1.5 text-[12.5px] font-medium transition-colors cursor-pointer',
        active
          ? 'border-[var(--border-hairline)] bg-[var(--surface)] text-[var(--ink)] shadow-apple'
          : 'border-transparent text-[var(--ink-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]'
      )}
    >
      {active && (
        <span
          aria-hidden="true"
          className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-[var(--accent)]"
        />
      )}
      <span className="flex min-w-0 items-center gap-2 pl-0.5">
        <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--ink-muted)]" />
        <span className="truncate">{label}</span>
      </span>
      <span
        className={cn(
          'rounded-md px-1.5 py-0.5 font-mono text-[10.5px]',
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
