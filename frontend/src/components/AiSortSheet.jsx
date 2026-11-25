import React, { useEffect, useState } from 'react';
import { ArrowRight, Bot, CheckCircle2, RefreshCw, Sparkles } from 'lucide-react';
import { api } from '../lib/api';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import { Sheet } from './ui/Sheet';

export function AiSortSheet({ open, onClose, onCompleted, showToast }) {
  const [status, setStatus] = useState(null);
  const [scope, setScope] = useState('workspace');
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setError('');
    api
      .getAiStatus()
      .then((res) => setStatus(res))
      .catch(() => setStatus({ available: false }));
  }, [open]);

  const runSmartSort = async (targetScope = scope) => {
    setScope(targetScope);
    setLoading(true);
    setError('');
    try {
      const res = await api.aiSmartSort(targetScope);
      const list = res.suggestions || [];
      setSuggestions(list);
      const initial = new Set(list.filter((s) => s.changed).map((s) => s.path));
      setSelected(initial);
    } catch (err) {
      setError(err.message || 'Failed to run Ollama smart sort');
    } finally {
      setLoading(false);
    }
  };

  const toggleItem = (path) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const applySelected = async () => {
    const moves = suggestions
      .filter((s) => selected.has(s.path) && s.changed)
      .map((s) => ({ path: s.path, target_category: s.suggested_category }));
    if (moves.length === 0) return;

    setApplying(true);
    try {
      const res = await api.aiApplySort(moves);
      const movedCount = (res.moved || []).length;
      showToast(`Ollama AI moved ${movedCount} item(s) to their suggested categories`);
      onCompleted();
      await runSmartSort(scope);
    } catch (err) {
      showToast(err.message || 'Failed to apply moves', true);
    } finally {
      setApplying(false);
    }
  };

  const actionable = suggestions.filter((s) => s.changed);
  const aligned = suggestions.filter((s) => !s.changed);

  return (
    <Sheet
      open={open}
      onClose={onClose}
      eyebrow="Local Ollama AI"
      title="Dynamic Folder Sorter"
      subtitle="Uses your local Ollama model to classify ambiguous folders & files by their actual contents."
    >
      <div className="space-y-4">
        {/* Ollama Model Status */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-xl border bg-[var(--input-bg)] p-3.5">
          <div className="flex items-center gap-2.5">
            <Bot className="h-4 w-4 text-[var(--accent-bright)]" />
            <div>
              <div className="text-[13px] font-semibold text-[var(--ink)]">
                {status?.available ? `Ollama Connected · ${status.active_model}` : 'Ollama Offline'}
              </div>
              <div className="text-[11px] text-[var(--ink-muted)]">
                {status?.available
                  ? `Running locally at ${status.url} (100% private)`
                  : 'Start Ollama locally (ollama serve) to enable dynamic AI sorting.'}
              </div>
            </div>
          </div>
          <Badge tone={status?.available ? 'emerald' : 'amber'}>
            {status?.available ? 'Online' : 'Offline'}
          </Badge>
        </div>

        {/* Scan Actions */}
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="primary"
            disabled={loading || !status?.available}
            onClick={() => runSmartSort('workspace')}
          >
            <Sparkles className="h-4 w-4" />
            <span>{loading && scope === 'workspace' ? 'Analyzing Workspace...' : 'Analyze Workspace Folders'}</span>
          </Button>
          <Button
            variant="secondary"
            disabled={loading || !status?.available}
            onClick={() => runSmartSort('desktop')}
          >
            <RefreshCw className={loading && scope === 'desktop' ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
            <span>{loading && scope === 'desktop' ? 'Analyzing Desktop...' : 'Analyze Desktop'}</span>
          </Button>
        </div>

        {error && (
          <div className="rounded-lg border border-[color:var(--rose)]/35 bg-[var(--rose-soft)] p-3.5 text-xs text-[var(--rose)]">
            {error}
          </div>
        )}

        {/* Actionable Suggestions */}
        {actionable.length > 0 && (
          <div className="space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs font-semibold text-[var(--ink)]">
                Suggested Re-Categorizations ({actionable.length})
              </div>
              <Button
                size="sm"
                variant="emerald"
                disabled={applying || selected.size === 0}
                onClick={applySelected}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>{applying ? 'Moving...' : `Apply Selected (${selected.size})`}</span>
              </Button>
            </div>

            {actionable.map((item) => (
              <label
                key={item.path}
                className="flex cursor-pointer items-start gap-3 rounded-xl border bg-[var(--surface-elevated)] p-3 transition hover:border-[var(--border-strong)]"
              >
                <input
                  type="checkbox"
                  checked={selected.has(item.path)}
                  onChange={() => toggleItem(item.path)}
                  className="mt-1 h-4 w-4 accent-[var(--accent)]"
                />
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[13px] font-semibold text-[var(--ink)]">{item.name}</span>
                    <span className="font-mono text-[11px] text-[var(--ink-muted)]">{item.current_category}</span>
                    <ArrowRight className="h-3.5 w-3.5 text-[var(--accent-bright)]" />
                    <Badge tone="accent">
                      {item.suggested_icon} {item.suggested_label}
                    </Badge>
                  </div>
                  <div className="text-[11.5px] text-[var(--ink-secondary)]">{item.reason}</div>
                </div>
              </label>
            ))}
          </div>
        )}

        {/* Already Well-Placed Summary */}
        {suggestions.length > 0 && actionable.length === 0 && !loading && (
          <div className="rounded-xl border border-[color:var(--emerald)]/30 bg-[var(--emerald-soft)] p-4 text-xs text-[var(--emerald)]">
            All {aligned.length} scanned items are already in their optimal categories according to {status?.active_model || 'Ollama'}.
          </div>
        )}
      </div>
    </Sheet>
  );
}
