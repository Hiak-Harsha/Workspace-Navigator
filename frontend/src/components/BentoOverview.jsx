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

  const syncedCount = Math.max(0, (stats.git_repos || 0) - attentionRepos.length);
  const totalSafe = Math.max(1, stats.total || 1);
  const syncedPct = Math.round((syncedCount / Math.max(1, stats.git_repos || 1)) * 100);
  const attnPct = 100 - syncedPct;

  return (
    <section
      aria-label="Workspace Bento Overview"
      className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-12"
    >
      {/* Hero Bento Card: Apple Clean Surface + Ambient Hybrid Pulse + Repo Marquee */}
      <BentoCard className="md:col-span-2 xl:col-span-6 flex flex-col justify-between overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-16 -top-16 h-44 w-44 rounded-full opacity-20 blur-3xl"
          style={{
            background: 'linear-gradient(135deg, #0067B8 0%, #107C10 55%, #FFB900 100%)',
          }}
        />
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
              <Layers className="h-3.5 w-3.5 text-[var(--accent-bright)]" />
              <span>Workspace Command</span>
            </div>
            <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-3xl font-bold tracking-tight text-[var(--ink)]">
                <NumberTicker value={stats.total ?? 0} />
              </span>
              <span className="text-[12.5px] text-[var(--ink-muted)]">
                items indexed across {stats.categories ?? 0} domains
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onFilterAll}
            className="min-h-[36px] shrink-0 rounded-lg border bg-[var(--surface-elevated)] px-3 text-[12px] font-semibold text-[var(--ink-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--ink)] cursor-pointer"
          >
            View All
          </button>
        </div>

        {/* Niche Touch: Live Microsoft 4-Color Workspace Health Segment Bar */}
        <div className="mt-3.5 space-y-1.5">
          <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-[var(--input-bg)]">
            <div
              className="h-full bg-[#0067B8]"
              style={{ width: `${Math.min(100, Math.round(((stats.git_repos || 0) / totalSafe) * 100))}%` }}
              title={`Git Repositories: ${stats.git_repos || 0}`}
            />
            <div
              className="h-full bg-[#107C10]"
              style={{ width: `${Math.min(100, Math.round((syncedCount / totalSafe) * 100))}%` }}
              title={`Synced Repos: ${syncedCount}`}
            />
            <div
              className="h-full bg-[#FFB900]"
              style={{ width: `${Math.min(100, Math.round((attentionRepos.length / totalSafe) * 100))}%` }}
              title={`Attention Needed: ${attentionRepos.length}`}
            />
            <div
              className="h-full bg-[#D13438]"
              style={{ width: `${Math.min(100, Math.round(((stats.quarantine_count || 0) / totalSafe) * 100))}%` }}
              title={`Quarantined Redundant: ${stats.quarantine_count || 0}`}
            />
          </div>
        </div>

        {/* Live Repo Marquee */}
        {gitRepos.length > 0 && (
          <div className="mt-3 overflow-hidden rounded-lg border bg-[var(--input-bg)] py-1.5">
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

      {/* Bento Tile 2: Git Repositories */}
      <BentoCard className="xl:col-span-3 flex flex-col justify-between" onClick={onFilterGit}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Git Repositories
          </span>
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--emerald-soft)] text-[var(--emerald)]">
            <FolderGit2 className="h-4 w-4" />
          </span>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
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
              {attentionRepos.length} attention
            </Badge>
          )}
        </div>

        <div className="mt-3 space-y-1">
          <div className="flex h-1 w-full overflow-hidden rounded-full bg-[var(--input-bg)]">
            <div className="h-full bg-[var(--emerald)]" style={{ width: `${syncedPct}%` }} />
            <div className="h-full bg-[var(--amber)]" style={{ width: `${attnPct}%` }} />
          </div>
          <div className="text-[11px] text-[var(--ink-muted)]">
            {syncedCount} synced · {attentionRepos.length} unpushed/dirty
          </div>
        </div>
      </BentoCard>

      {/* Bento Tile 3: Quarantine Vault */}
      <BentoCard className="xl:col-span-3 flex flex-col justify-between" onClick={onOpenQuarantine}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-[var(--ink-muted)]">
            Quarantine Vault
          </span>
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--violet-soft)] text-[var(--violet)]">
            <Archive className="h-4 w-4" />
          </span>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-3xl font-bold tracking-tight text-[var(--ink)]">
            <NumberTicker value={stats.quarantine_count ?? 0} />
          </span>
          <Badge tone={stats.quarantine_count > 0 ? 'violet' : 'neutral'}>
            {formatBytes(stats.quarantine_bytes || 0)}
          </Badge>
        </div>

        <div className="mt-3 text-[11px] text-[var(--ink-muted)]">
          Redundant files staged in one place
        </div>
      </BentoCard>
    </section>
  );
}
