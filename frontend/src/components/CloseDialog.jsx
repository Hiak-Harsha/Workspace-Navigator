import React from 'react';
import { Power, XCircle } from 'lucide-react';
import { Button } from './ui/Button';

export function CloseDialog({ open, busy, onCancel, onCloseWindowOnly, onStopServerAndClose }) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-[3px]"
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div className="w-[92%] max-w-[460px] rounded-xl border bg-[var(--surface)] p-6 shadow-2xl animate-fade-up">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-[var(--ink)]">Close Workspace Navigator</h3>
            <p className="mt-1 text-xs text-[var(--ink-muted)]">
              Close just this window (keeping Auto-Organizer running) or stop the local server completely.
            </p>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            aria-label="Cancel"
            className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg border bg-[var(--surface-elevated)] text-[var(--ink-muted)] hover:text-[var(--ink)] cursor-pointer"
          >
            <XCircle className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 flex flex-col gap-2.5 sm:flex-row sm:justify-end">
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
