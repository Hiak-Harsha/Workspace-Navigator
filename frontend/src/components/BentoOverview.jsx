import React from 'react';
import { Archive, FolderGit2, GitBranch, Layers, ShieldAlert } from 'lucide-react';
import { BentoCard } from './magic/BentoCard';
import { NumberTicker } from './magic/NumberTicker';
import { Badge } from './ui/Badge';
import { formatBytes } from '../lib/utils';

export function BentoOverview({
  stats,
  gitRepos,
  onFilterAll,
  onFilterGit,
  onFilterAttention,
  onOpenQuarantine,
  onPreviewPath,
}) {
  const attentionRepos = gitRepos.filter(
    (r) =>
      !r.git_info?.has_remote ||
      (r.git_info?.unpushed_count || 0) > 0 ||
      (r.git_info?.dirty_count || 0) > 0
  );

  return (
    <section aria-label="Workspace Bento Overview" className="grid grid-cols-1 gap-3 md:grid-cols-12">
      {/* Primary Bento Tile: Workspace Pulse + Live Repo Marquee */}
      <BentoCard className="md:col-span-6 flex flex-col justify-between">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              <Layers className="h-3.5 w-3.5 text-[var(--accent-bright)]" />
              <span>Workspace Index</span>
            </div>
            <div className="mt-2 flex items-baseline gap-3">
              <span className="text-3xl font-bold tracking-tight text-[var(--ink)]">
                <NumberTicker value={stats.total ?? 0} />
              </span>
              <span className="text-[12px] text-[var(--ink-muted)]">
                across {stats.categories ?? 0} organized categories
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onFilterAll}
            className="min-h-[36px] rounded-lg border bg-[var(--surface-elevated)] px-3 text-[12px] font-medium text-[var(--ink-secondary)] hover:text-[var(--ink)] cursor-pointer"
          >
            View All
          </button>
        </div>

        {/* Magic UI-inspired Marquee strip of Git Repos */}
        {gitRepos.length > 0 && (
          <div className="mt-4 overflow-hidden rounded-lg border bg-[var(--input-bg)] py-1.5">
            <div className="animate-marquee gap-2 px-2">
              {[...gitRepos, ...gitRepos].map((repo, idx) => (
                <button
                  key={`${repo.path}-${idx}`}
                  type="button"
                  onClick={() => onPreviewPath(repo.path)}
                  className="inline-flex items-center gap-1.5 rounded-md border bg-[var(--surface)] px-2.5 py-1 text-[11px] text-[var(--ink-secondary)] hover:border-[var(--accent-bright)] hover:text-[var(--ink)] cursor-pointer whitespace-nowrap"
                >
                  <GitBranch className="h-3 w-3 text-[var(--emerald)]" />
                  <span className="font-medium">{repo.name}</span>
                  <span className="font-mono text-[10px] text-[var(--ink-muted)]">
                    {repo.git_info?.branch || 'git'}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </BentoCard>

      {/* Bento Tile 2: Active Git Repositories & Attention */}
      <BentoCard className="md:col-span-3 flex flex-col justify-between" onClick={onFilterGit}>
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Git Repositories
          </span>
          <FolderGit2 className="h-4 w-4 text-[var(--emerald)]" />
        </div>
        <div className="mt-2 flex items-baseline gap-2.5">
          <span className="text-3xl font-bold tracking-tight text-[var(--ink)]">
            <NumberTicker value={stats.git_repos ?? 0} />
          </span>
          {attentionRepos.length > 0 && (
            <Badge
              tone="amber"
              onClick={(e) => {
                e.stopPropagation();
                onFilterAttention();
              }}
              className="cursor-pointer"
            >
              <ShieldAlert className="h-3 w-3" />
              {attentionRepos.length} need attention
            </Badge>
          )}
        </div>
        <div className="mt-3 text-[11px] text-[var(--ink-muted)]">
          Workspace, Home, Desktop &amp; Open-Source forks
        </div>
      </BentoCard>

      {/* Bento Tile 3: Quarantine Vault (One-Place Redundant Staging) */}
      <BentoCard className="md:col-span-3 flex flex-col justify-between" onClick={onOpenQuarantine}>
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Quarantine Vault
          </span>
          <Archive className="h-4 w-4 text-[var(--violet)]" />
        </div>
        <div className="mt-2 flex items-baseline gap-2.5">
          <span className="text-3xl font-bold tracking-tight text-[var(--ink)]">
            <NumberTicker value={stats.quarantine_count ?? 0} />
          </span>
          <Badge tone={stats.quarantine_count > 0 ? 'violet' : 'neutral'}>
            {formatBytes(stats.quarantine_bytes || 0)}
          </Badge>
        </div>
        <div className="mt-3 text-[11px] text-[var(--ink-muted)]">
          Redundant items staged for 1-click removal
        </div>
      </BentoCard>
    </section>
  );
}
