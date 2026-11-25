import React from 'react';
import {
  Code2,
  Copy,
  Eye,
  FileText,
  Folder,
  FolderOpen,
  GitBranch,
  Star,
  Terminal,
  Trash2,
} from 'lucide-react';
import { Badge } from './ui/Badge';
import { cn, formatBytes } from '../lib/utils';

function GitStatusBadge({ item }) {
  if (!item.is_git) return null;
  const g = item.git_info;
  if (!g) return <Badge tone="emerald">GIT</Badge>;

  const branch = g.branch || 'git';
  if (!g.has_remote) {
    return (
      <Badge tone="amber" title="Local Git repo without GitHub remote">
        <GitBranch className="h-3 w-3" />
        {branch} · local
      </Badge>
    );
  }
  if (g.unpushed_count > 0) {
    return (
      <Badge tone="violet" title={`${g.unpushed_count} unpushed commit(s)`}>
        <GitBranch className="h-3 w-3" />
        {branch} · ↑{g.unpushed_count}
      </Badge>
    );
  }
  if (g.dirty_count > 0) {
    return (
      <Badge tone="accent" title={`${g.dirty_count} uncommitted change(s)`}>
        <GitBranch className="h-3 w-3" />
        {branch} · *{g.dirty_count}
      </Badge>
    );
  }
  return (
    <Badge tone="emerald" title="Synced with remote">
      <GitBranch className="h-3 w-3" />
      {branch}
    </Badge>
  );
}

export function ProjectCard({
  item,
  viewMode,
  onPreview,
  onOpenAction,
  onToggleFavorite,
  onDelete,
  onCopyPath,
}) {
  const codeTarget = item.git_info?.path || item.path;
  const isList = viewMode === 'list';

  return (
    <article
      className={cn(
        'group rounded-2xl border bg-[var(--surface)] shadow-apple transition-all duration-150 hover:border-[var(--border-strong)] hover:bg-[var(--surface-elevated)] animate-fade-up',
        isList
          ? 'flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between'
          : 'flex min-w-0 flex-col justify-between p-4'
      )}
    >
      <div className={cn('min-w-0', isList && 'flex flex-1 flex-wrap items-center gap-3')}>
        {/* Top Row: Category + Pin/Delete */}
        <div className={cn('flex items-center justify-between gap-2', !isList && 'mb-2.5')}>
          <Badge tone="neutral" className="max-w-[75%] truncate">
            <span>{item.category_icon}</span>
            <span className="truncate">{item.category}</span>
          </Badge>
          {!isList && (
            <div className="flex shrink-0 items-center gap-0.5">
              <button
                type="button"
                onClick={() => onToggleFavorite(item)}
                title={item.is_favorite ? 'Unpin' : 'Pin to favorites'}
                className={cn(
                  'inline-flex h-8 w-8 items-center justify-center rounded-lg transition cursor-pointer',
                  item.is_favorite
                    ? 'text-[var(--amber)]'
                    : 'text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]'
                )}
              >
                <Star className="h-4 w-4" fill={item.is_favorite ? 'currentColor' : 'none'} />
              </button>
              <button
                type="button"
                onClick={() => onDelete(item)}
                title="Move to Windows Recycle Bin"
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[var(--ink-muted)] transition hover:bg-[var(--rose-soft)] hover:text-[var(--rose)] cursor-pointer"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>

        {/* Title + Git Badge */}
        <div className={cn('flex min-w-0 flex-wrap items-center gap-2', !isList && 'mb-1.5')}>
          {item.is_dir ? (
            <Folder className="h-4 w-4 shrink-0 text-[var(--accent-bright)]" />
          ) : (
            <FileText className="h-4 w-4 shrink-0 text-[var(--ink-muted)]" />
          )}
          <button
            type="button"
            onClick={() => onPreview(item.path)}
            className="min-w-0 truncate text-left text-[15px] font-semibold text-[var(--ink)] hover:text-[var(--accent-bright)] cursor-pointer"
          >
            {item.name}
          </button>
          <GitStatusBadge item={item} />
        </div>

        {/* Copyable Path */}
        <button
          type="button"
          onClick={() => onCopyPath(item.path)}
          title={`Click to copy path: ${item.path}`}
          className={cn(
            'flex items-center gap-1.5 truncate font-mono text-[11px] text-[var(--ink-muted)] hover:text-[var(--ink-secondary)] cursor-pointer',
            !isList ? 'mb-3 w-full' : 'max-w-[280px]'
          )}
        >
          <Copy className="h-3 w-3 shrink-0 opacity-60" />
          <span className="truncate">{item.path}</span>
        </button>
      </div>

      {/* Footer / Actions */}
      <div className={cn('min-w-0', isList && 'flex flex-wrap items-center gap-2 shrink-0')}>
        {!isList && (
          <div className="mb-2.5 flex items-center justify-between border-t pt-2.5 text-[11px] text-[var(--ink-muted)]">
            <span>{item.last_modified}</span>
            <span className="font-mono">
              {item.is_dir
                ? 'DIR'
                : `${(item.extension || 'FILE').toUpperCase()}${item.size_bytes ? ` · ${formatBytes(item.size_bytes)}` : ''}`}
            </span>
          </div>
        )}

        <div className="grid grid-cols-4 gap-1.5">
          <CardActionBtn icon={Eye} label="Preview" onClick={() => onPreview(item.path)} />
          <CardActionBtn icon={FolderOpen} label="Files" onClick={() => onOpenAction('explorer', item.path)} />
          <CardActionBtn icon={Code2} label="Code" onClick={() => onOpenAction('vscode', codeTarget)} />
          <CardActionBtn icon={Terminal} label="Term" onClick={() => onOpenAction('terminal', codeTarget)} />
        </div>
      </div>
    </article>
  );
}

function CardActionBtn({ icon: Icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex min-h-[38px] min-w-0 items-center justify-center gap-1 rounded-lg border bg-[var(--surface-elevated)] px-2 text-[11.5px] font-semibold text-[var(--ink-secondary)] transition hover:border-[var(--border-strong)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)] cursor-pointer"
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="truncate">{label}</span>
    </button>
  );
}
