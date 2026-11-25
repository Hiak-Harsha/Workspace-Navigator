import React from 'react';
import { Check } from 'lucide-react';
import { cn } from '../../lib/utils';

export function StepProgress({ steps, currentStep }) {
  return (
    <div className="mb-5 flex flex-wrap items-center gap-2 sm:flex-nowrap">
      {steps.map((label, idx) => {
        const done = idx < currentStep;
        const active = idx === currentStep;
        return (
          <React.Fragment key={label}>
            <div className="flex min-w-0 items-center gap-2">
              <div
                className={cn(
                  'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold transition-colors',
                  done && 'border-[var(--emerald)] bg-[var(--emerald)] text-white',
                  active && 'border-[var(--accent-bright)] bg-[var(--accent-soft)] text-[var(--accent-bright)]',
                  !done && !active && 'border-[var(--border-strong)] text-[var(--ink-muted)]'
                )}
              >
                {done ? <Check className="h-3.5 w-3.5" /> : idx + 1}
              </div>
              <span
                className={cn(
                  'truncate text-[12px] font-medium',
                  active || done ? 'text-[var(--ink)]' : 'text-[var(--ink-muted)]'
                )}
              >
                {label}
              </span>
            </div>
            {idx < steps.length - 1 && (
              <div
                className={cn(
                  'hidden h-px flex-1 transition-colors sm:block',
                  done ? 'bg-[var(--emerald)]' : 'bg-[var(--border-hairline)]'
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
