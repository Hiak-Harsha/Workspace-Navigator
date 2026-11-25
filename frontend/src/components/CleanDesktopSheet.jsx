import React, { useEffect, useState } from 'react';
import { Folder, FileText, Sparkles } from 'lucide-react';
import { api } from '../lib/api';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import { Sheet } from './ui/Sheet';
import { StepProgress } from './ui/StepProgress';
import { ShimmerButton } from './magic/ShimmerButton';

export function CleanDesktopSheet({ open, onClose, onCompleted, showToast }) {
  const [step, setStep] = useState(0); // 0: scanning, 1: review, 2: done
  const [planned, setPlanned] = useState([]);
  const [recent, setRecent] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStep(0);
    setBusy(true);
    Promise.all([api.organizeDesktop(true), api.getOrganizerStatus()])
      .then(([dryRes, stRes]) => {
        setPlanned(dryRes.moved_items || []);
        setRecent(stRes.recent_moves || []);
        setStep(1);
      })
      .catch((err) => {
        showToast(err.message || 'Failed to scan Desktop', true);
      })
      .finally(() => setBusy(false));
  }, [open]);

  const handleExecute = async () => {
    setBusy(true);
    try {
      const res = await api.organizeDesktop(false);
      setStep(2);
      showToast(`Organized / deduplicated ${res.moved_count || 0} item(s)`);
      onCompleted?.();
    } catch (err) {
      showToast(err.message || 'Failed to organize Desktop', true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      eyebrow="Desktop Organizer Flow"
      title="Clean & Deduplicate Desktop"
      subtitle="Token-safe + content-aware classification with SHA-256 duplicate protection"
    >
      <StepProgress steps={['Scan Desktop', 'Review Plan', 'Organized']} currentStep={step} />

      {step === 0 && (
        <div className="py-12 text-center text-sm text-[var(--ink-muted)]">
          Scanning Desktop items and verifying SHA-256 hashes...
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4">
          {planned.length === 0 ? (
            <div className="rounded-xl border bg-[var(--input-bg)] p-6 text-center text-sm text-[var(--ink-secondary)]">
              Desktop is already clean — no loose items need moving.
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                Planned Moves ({planned.length})
              </div>
              {planned.map((p) => (
                <div key={p.From} className="rounded-lg border bg-[var(--input-bg)] p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {p.Type === 'Folder' ? (
                      <Folder className="h-4 w-4 text-[var(--accent-bright)]" />
                    ) : (
                      <FileText className="h-4 w-4 text-[var(--ink-muted)]" />
                    )}
                    <span className="text-sm font-semibold text-[var(--ink)]">{p.Item}</span>
                    <Badge tone={String(p.Status).includes('Recycle') ? 'amber' : 'emerald'}>
                      {p.Status}
                    </Badge>
                  </div>
                  <div className="mt-1.5 break-all font-mono text-[11px] text-[var(--ink-muted)]">
                    {p.From} → {p.To}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <ShimmerButton disabled={busy || planned.length === 0} onClick={handleExecute}>
              <Sparkles className="h-4 w-4" />
              <span>{busy ? 'Organizing...' : `Confirm & Organize (${planned.length})`}</span>
            </ShimmerButton>
          </div>

          {recent.length > 0 && (
            <div className="space-y-2 border-t pt-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                Recent Auto-Organizer Activity
              </div>
              {recent.slice(0, 6).map((r, i) => (
                <div key={`${r.Item}-${i}`} className="rounded-lg border bg-[var(--input-bg)] px-3 py-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-[var(--ink)]">{r.Item}</span>
                    <Badge tone="emerald">{r.Status}</Badge>
                  </div>
                  <div className="mt-1 truncate font-mono text-[10px] text-[var(--ink-muted)]">
                    {r.Timestamp} · {r.To}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4 py-8 text-center">
          <div className="text-base font-semibold text-[var(--emerald)]">
            Desktop organized cleanly into Workspace.
          </div>
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        </div>
      )}
    </Sheet>
  );
}
