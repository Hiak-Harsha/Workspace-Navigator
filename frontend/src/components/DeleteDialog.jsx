import React from 'react';
import { Trash2 } from 'lucide-react';
import { Button } from './ui/Button';

export function DeleteDialog({ item, onCancel, onConfirm }) {
  if (!item) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4 backdrop-blur-[4px]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-[460px] overflow-hidden rounded-2xl border bg-[var(--surface)] p-6 text-center shadow-2xl animate-fade-up">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-[color:var(--rose)]/35 bg-[var(--rose-soft)] text-[var(--rose)]">
          <Trash2 className="h-5 w-5" />
        </div>
        <h3 className="text-base font-semibold text-[var(--ink)]">Delete &ldquo;{item.name}&rdquo;?</h3>
        <p className="mt-2 break-all text-xs leading-relaxed text-[var(--ink-muted)]">
          This safely moves the item to your Windows Recycle Bin: {item.path}
        </p>
        <div className="mt-6 flex flex-wrap justify-end gap-2.5">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={() => onConfirm(item)}>
            Move to Recycle Bin
          </Button>
        </div>
      </div>
    </div>
  );
}
