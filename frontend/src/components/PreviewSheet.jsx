import React, { useEffect, useState } from 'react';
import { ArrowUp, Code2, ExternalLink, FileText, Folder, FolderOpen, GitBranch, Terminal } from 'lucide-react';
import { api } from '../lib/api';
import { formatBytes } from '../lib/utils';
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

  const repoTarget = data?.git_info?.path || data?.path || targetPath;

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
            <Button size="sm" variant="primary" onClick={() => onOpenAction('explorer', data.path)}>
              <FolderOpen className="h-3.5 w-3.5" /> Explorer
            </Button>
            <Button size="sm" variant="secondary" onClick={() => onOpenAction('vscode', repoTarget)}>
              <Code2 className="h-3.5 w-3.5" /> VS Code
            </Button>
            <Button size="sm" variant="secondary" onClick={() => onOpenAction('terminal', repoTarget)}>
              <Terminal className="h-3.5 w-3.5" /> Terminal
            </Button>
            {data.kind === 'file' && (
              <Button size="sm" variant="outline" onClick={() => onOpenAction('default', data.path)}>
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
                    <button
                      key={entry.path}
                      type="button"
                      onClick={() => onNavigate(entry.path)}
                      className="flex items-center justify-between gap-2 rounded-lg border bg-[var(--surface)] px-3 py-2 text-left font-mono text-[11px] text-[var(--ink-secondary)] transition hover:border-[var(--accent-bright)] hover:text-[var(--ink)] cursor-pointer"
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        {entry.is_dir ? (
                          <Folder className="h-3.5 w-3.5 shrink-0 text-[var(--accent-bright)]" />
                        ) : (
                          <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--ink-muted)]" />
                        )}
                        <span className="truncate">{entry.name}</span>
                      </span>
                      <span className="shrink-0 text-[10px] text-[var(--ink-muted)]">
                        {entry.is_dir ? 'DIR' : formatBytes(entry.size)}
                      </span>
                    </button>
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
