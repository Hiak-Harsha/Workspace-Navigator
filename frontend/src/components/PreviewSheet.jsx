import React, { useEffect, useState } from 'react';
import { ArrowUp, Code2, ExternalLink, FileText, Folder, FolderOpen, GitBranch, Terminal } from 'lucide-react';
import { api } from '../lib/api';
import { formatBytes, toWebRepoUrl } from '../lib/utils';
import { Button } from './ui/Button';
import { Sheet } from './ui/Sheet';

export function PreviewSheet({ targetPath, onClose, onNavigate, onOpenAction }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!targetPath) return;
    let active = true;
    setLoading(true);
    setError('');
    api
      .getPreview(targetPath)
      .then((res) => {
        if (active) setData(res);
      })
      .catch((err) => {
        if (active) setError(err.message || 'Failed to load preview');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [targetPath]);

  const currentTarget = data?.path || targetPath;
  const dirTarget = data?.kind === 'file' ? (data?.parent_path || currentTarget) : currentTarget;
  const githubUrl = toWebRepoUrl(data?.git_info?.remote_url);

  return (
    <Sheet
      open={Boolean(targetPath)}
      onClose={onClose}
      eyebrow={data?.kind === 'directory' ? 'Directory Inspector' : 'File Inspector'}
      title={data?.name || 'Loading...'}
      subtitle={data?.path || targetPath}
      headerActions={
        data && (
          <>
            {data.parent_path && (
              <Button size="sm" variant="secondary" onClick={() => onNavigate(data.parent_path)}>
                <ArrowUp className="h-3.5 w-3.5" /> Up
              </Button>
            )}
            <Button size="sm" variant="primary" onClick={() => onOpenAction('explorer', currentTarget)}>
              <FolderOpen className="h-3.5 w-3.5" /> Explorer
            </Button>
            <Button size="sm" variant="secondary" onClick={() => onOpenAction('vscode', dirTarget)}>
              <Code2 className="h-3.5 w-3.5" /> VS Code
            </Button>
            <Button size="sm" variant="secondary" onClick={() => onOpenAction('terminal', dirTarget)}>
              <Terminal className="h-3.5 w-3.5" /> Terminal
            </Button>
            {githubUrl && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => window.open(githubUrl, '_blank', 'noopener,noreferrer')}
              >
                <ExternalLink className="h-3.5 w-3.5" /> GitHub
              </Button>
            )}
            {data.kind === 'file' && (
              <Button size="sm" variant="outline" onClick={() => onOpenAction('default', currentTarget)}>
                <ExternalLink className="h-3.5 w-3.5" /> Default App
              </Button>
            )}
          </>
        )
      }
    >
      {loading && <div className="py-16 text-center text-sm text-[var(--ink-muted)]">Loading preview...</div>}
      {error && <div className="rounded-lg border border-[color:var(--rose)]/35 bg-[var(--rose-soft)] p-4 text-sm text-[var(--rose)]">{error}</div>}

      {!loading && !error && data && (
        <div className="space-y-4">
          {data.git_info && (
            <div className="rounded-xl border bg-[var(--input-bg)] p-4">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-[var(--emerald)]">
                <GitBranch className="h-3.5 w-3.5" />
                <span>Git Repository Status</span>
              </div>
              <pre className="whitespace-pre-wrap break-all font-mono text-[11.5px] leading-relaxed text-[var(--ink-secondary)]">
                {`Root: ${data.git_info.path}\nBranch: ${data.git_info.branch || 'unknown'}\nRemote: ${data.git_info.remote_url || 'None (not pushed to GitHub)'}\nDirty files: ${data.git_info.dirty_count} | Unpushed commits: ${data.git_info.unpushed_count}`}
              </pre>
            </div>
          )}

          {data.kind === 'directory' ? (
            <>
              <div className="rounded-xl border bg-[var(--input-bg)] p-4">
                <div className="mb-3 text-xs font-semibold text-[var(--accent-bright)]">
                  Contents — click to navigate ({data.entries?.length || 0} items)
                </div>
                <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                  {(data.entries || []).map((entry) => (
                    <div
                      key={entry.path}
                      className="flex items-center justify-between gap-1.5 rounded-lg border bg-[var(--surface)] px-2.5 py-1.5 font-mono text-[11px] text-[var(--ink-secondary)] transition hover:border-[var(--accent-bright)]"
                    >
                      <button
                        type="button"
                        onClick={() => onNavigate(entry.path)}
                        className="flex min-w-0 flex-1 items-center gap-2 py-0.5 text-left hover:text-[var(--ink)] cursor-pointer"
                        title={entry.is_dir ? `Open folder: ${entry.name}` : `Inspect file: ${entry.name}`}
                      >
                        {entry.is_dir ? (
                          <Folder className="h-3.5 w-3.5 shrink-0 text-[var(--accent-bright)]" />
                        ) : (
                          <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--ink-muted)]" />
                        )}
                        <span className="truncate">{entry.name}</span>
                      </button>
                      <div className="flex shrink-0 items-center gap-1">
                        <span className="text-[10px] text-[var(--ink-muted)] mr-0.5">
                          {entry.is_dir ? 'DIR' : formatBytes(entry.size)}
                        </span>
                        {!entry.is_dir && (
                          <button
                            type="button"
                            onClick={() => onOpenAction('default', entry.path)}
                            title={`Open ${entry.name} in Default App`}
                            className="inline-flex h-6 w-6 items-center justify-center rounded border bg-[var(--surface-elevated)] text-[var(--ink-secondary)] hover:border-[var(--accent-bright)] hover:text-[var(--accent-bright)] cursor-pointer"
                          >
                            <ExternalLink className="h-3 w-3" />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => onOpenAction('explorer', entry.path)}
                          title={entry.is_dir ? `Open ${entry.name} in Explorer` : `Reveal ${entry.name} in Explorer`}
                          className="inline-flex h-6 w-6 items-center justify-center rounded border bg-[var(--surface-elevated)] text-[var(--ink-secondary)] hover:border-[var(--accent-bright)] hover:text-[var(--accent-bright)] cursor-pointer"
                        >
                          <FolderOpen className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {data.readme_text && (
                <div className="rounded-xl border bg-[var(--input-bg)] p-4">
                  <div className="mb-2 text-xs font-semibold text-[var(--ink)]">
                    {data.readme_name || 'README'}
                  </div>
                  <pre className="max-h-[340px] overflow-y-auto whitespace-pre-wrap break-words font-mono text-[11.5px] leading-relaxed text-[var(--ink-secondary)]">
                    {data.readme_text}
                  </pre>
                </div>
              )}
            </>
          ) : (
            <>
              <div className="rounded-xl border bg-[var(--input-bg)] p-4">
                <div className="mb-2 text-xs font-semibold text-[var(--ink)]">File Metadata</div>
                <pre className="font-mono text-[11.5px] leading-relaxed text-[var(--ink-secondary)]">
                  {`Size: ${formatBytes(data.size)} (${data.size} bytes)\nModified: ${data.last_modified}\nExtension: ${data.extension || 'none'}`}
                </pre>
              </div>
              {data.snippet !== null && data.snippet !== undefined && (
                <div className="rounded-xl border bg-[var(--input-bg)] p-4">
                  <div className="mb-2 text-xs font-semibold text-[var(--ink)]">
                    Content Preview {data.truncated ? '(First 8 KB)' : ''}
                  </div>
                  <pre className="max-h-[380px] overflow-y-auto whitespace-pre-wrap break-words font-mono text-[11.5px] leading-relaxed text-[var(--ink-secondary)]">
                    {data.snippet}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </Sheet>
  );
}
