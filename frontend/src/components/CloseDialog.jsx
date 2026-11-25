import React from 'react';
import { Power, X } from 'lucide-react';
import { Button } from './ui/Button';

export function CloseDialog({ open, busy, onCancel, onCloseWindowOnly, onStopServerAndClose }) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4 backdrop-blur-[4px]"
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-[540px] overflow-hidden rounded-2xl border bg-[var(--surface)] p-6 shadow-2xl animate-fade-up">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-[var(--ink)]">Close Workspace Navigator</h3>
            <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--ink-muted)]">
              Close just this window (keeping Auto-Organizer running in the background) or stop the local server completely.
            </p>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            aria-label="Cancel"
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border bg-[var(--surface-elevated)] text-[var(--ink-muted)] transition hover:border-[var(--border-strong)] hover:text-[var(--ink)] cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-end gap-2.5">
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            Stay Open
          </Button>
          <Button variant="outline" onClick={onCloseWindowOnly} disabled={busy}>
            Close Window Only
          </Button>
          <Button variant="destructive" onClick={onStopServerAndClose} disabled={busy}>
            <Power className="h-4 w-4" />
            <span>{busy ? 'Stopping...' : 'Stop Server & Close'}</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
