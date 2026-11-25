import React, { useEffect, useState } from 'react';
import { Code2, ExternalLink, Eye, FolderOpen, Search, Sparkles, Terminal } from 'lucide-react';
import { api } from '../lib/api';
import { naturalCompare, toWebRepoUrl } from '../lib/utils';

export function CommandPalette({ open, onClose, items, onPreview, onOpenAction }) {
  const [query, setQuery] = useState('');
  const [aiResults, setAiResults] = useState([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState('');

  useEffect(() => {
    if (open) {
      setQuery('');
      setAiResults([]);
      setAiError('');
    }
  }, [open]);

  if (!open) return null;

  const q = query.trim().toLowerCase();
  const matches = items
    .filter(
      (i) =>
        !q ||
        i.name.toLowerCase().includes(q) ||
        i.category.toLowerCase().includes(q) ||
        i.path.toLowerCase().includes(q)
    )
    .sort((a, b) => naturalCompare(a.name, b.name))
    .slice(0, 12);

  const runAiSearch = async () => {
    if (!query.trim()) return;
    setAiLoading(true);
    setAiError('');
    try {
      const res = await api.aiSearch(query.trim());
      setAiResults(res.results || []);
    } catch (err) {
      setAiError(err.message || 'Ollama search unavailable');
    } finally {
      setAiLoading(false);
    }
  };

  const displayList = aiResults.length > 0
    ? aiResults.map((r) => ({ ...r.item, _aiReason: r.reason }))
    : matches;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/65 pt-[12vh] backdrop-blur-[3px]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div className="w-[92%] max-w-[640px] overflow-hidden rounded-xl border bg-[var(--surface)] shadow-2xl animate-fade-up">
        <div className="flex items-center gap-2.5 border-b px-4 py-3">
          <Search className="h-4 w-4 text-[var(--ink-muted)]" />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (aiResults.length > 0) setAiResults([]);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && matches.length === 0 && query.trim()) {
                runAiSearch();
              }
            }}
            placeholder="Jump to any project, or ask Ollama (e.g. 'packet tracer labs')..."
            className="flex-1 bg-transparent text-sm text-[var(--ink)] outline-none placeholder:text-[var(--ink-muted)]"
          />
          {query.trim() && (
            <button
              type="button"
              onClick={runAiSearch}
              disabled={aiLoading}
              className="inline-flex items-center gap-1 rounded-md border bg-[var(--accent-soft)] px-2.5 py-1 text-[11px] font-semibold text-[var(--accent-bright)] hover:opacity-85 cursor-pointer"
            >
              <Sparkles className="h-3 w-3" />
              <span>{aiLoading ? 'Thinking...' : 'Ask Ollama'}</span>
            </button>
          )}
          <kbd className="rounded border bg-[var(--surface-elevated)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--ink-muted)]">
            ESC
          </kbd>
        </div>

        {aiError && (
          <div className="border-b bg-[var(--rose-soft)] px-4 py-2 text-[11px] text-[var(--rose)]">
            {aiError}
          </div>
        )}

        <div className="max-h-[400px] overflow-y-auto p-2">
          {displayList.length === 0 ? (
            <div className="py-10 text-center text-sm text-[var(--ink-muted)]">
              No exact matches. Press Enter or click <strong>Ask Ollama</strong> for AI semantic navigation.
            </div>
          ) : (
            displayList.map((item) => {
              const actionTarget = item.path;
              const githubUrl = toWebRepoUrl(item.git_info?.remote_url);
              return (
                <div
                  key={item.path}
                  className="flex items-center justify-between gap-3 rounded-lg px-3 py-2.5 hover:bg-[var(--surface-elevated)]"
                >
                  <button
                    type="button"
                    onClick={() => {
                      onPreview(item.path);
                      onClose();
                    }}
                    className="min-w-0 flex-1 text-left cursor-pointer"
                  >
                    <div className="truncate text-[13px] font-medium text-[var(--ink)]">
                      {item.category_icon} {item.name}
                    </div>
                    <div className="truncate font-mono text-[10px] text-[var(--ink-muted)]">
                      {item._aiReason ? `AI: ${item._aiReason} · ${item.path}` : `${item.category} · ${item.path}`}
                    </div>
                  </button>
                  <div className="flex items-center gap-1 shrink-0">
                    <IconCmdBtn
                      title="Preview"
                      onClick={() => {
                        onPreview(item.path);
                        onClose();
                      }}
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </IconCmdBtn>
                    <IconCmdBtn
                      title="Explorer"
                      onClick={() => {
                        onOpenAction('explorer', actionTarget);
                        onClose();
                      }}
                    >
                      <FolderOpen className="h-3.5 w-3.5" />
                    </IconCmdBtn>
                    <IconCmdBtn
                      title="VS Code"
                      onClick={() => {
                        onOpenAction('vscode', actionTarget);
                        onClose();
                      }}
                    >
                      <Code2 className="h-3.5 w-3.5" />
                    </IconCmdBtn>
                    <IconCmdBtn
                      title="Terminal"
                      onClick={() => {
                        onOpenAction('terminal', actionTarget);
                        onClose();
                      }}
                    >
                      <Terminal className="h-3.5 w-3.5" />
                    </IconCmdBtn>
                    {githubUrl && (
                      <IconCmdBtn
                        title={`GitHub: ${githubUrl}`}
                        onClick={() => {
                          window.open(githubUrl, '_blank', 'noopener,noreferrer');
                          onClose();
                        }}
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </IconCmdBtn>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

function IconCmdBtn({ title, onClick, children }) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="inline-flex h-8 w-8 items-center justify-center rounded-md border bg-[var(--surface)] text-[var(--ink-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--ink)] cursor-pointer"
    >
      {children}
    </button>
  );
}
