import React from 'react';
import { cn } from '../../lib/utils';

/** Magic UI-inspired Shimmer CTA button with accessible 44px tap target and 16px padding. */
export function ShimmerButton({ className, children, ...props }) {
  return (
    <button
      type="button"
      className={cn(
        'group relative inline-flex min-h-[44px] items-center justify-center gap-2 overflow-hidden rounded-lg border border-transparent bg-[var(--accent)] px-4 py-2 text-[13px] font-semibold text-[var(--accent-ink)] shadow-sm transition hover:opacity-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-bright)] disabled:opacity-45 disabled:cursor-not-allowed cursor-pointer whitespace-nowrap',
        className
      )}
      {...props}
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer-sweep"
      />
      <span className="relative z-10 inline-flex items-center gap-2">{children}</span>
    </button>
  );
}
