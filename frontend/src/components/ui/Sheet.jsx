import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

export function Sheet({ open, onClose, title, eyebrow, subtitle, headerActions, children, widthClass = 'max-w-[600px]' }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-[3px]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        className={cn(
          'flex h-full w-full flex-col border-l bg-[var(--surface)] shadow-2xl animate-fade-up',
          widthClass
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b px-6 py-4">
          <div className="min-w-0">
            {eyebrow && (
              <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--accent-bright)]">
                {eyebrow}
              </div>
            )}
            <h2 className="mt-0.5 truncate text-lg font-semibold text-[var(--ink)]">{title}</h2>
            {subtitle && (
              <p className="mt-0.5 break-all font-mono text-[11px] text-[var(--ink-muted)]">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg border bg-[var(--surface-elevated)] text-[var(--ink-muted)] transition hover:text-[var(--ink)] cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {headerActions && (
          <div className="flex flex-wrap items-center gap-2 border-b bg-[var(--surface-elevated)] px-6 py-3">
            {headerActions}
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  );
}
