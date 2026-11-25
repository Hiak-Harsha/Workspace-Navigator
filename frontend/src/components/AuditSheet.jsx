import React, { useEffect, useState } from 'react';
import { Archive, CheckSquare, Folder, FileText, RefreshCw, RotateCcw, Trash2 } from 'lucide-react';
import { api } from '../lib/api';
import { formatBytes } from '../lib/utils';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import { Sheet } from './ui/Sheet';
import { StepProgress } from './ui/StepProgress';

export function AuditSheet({ open, initialTab = 'scan', onClose, onChanged, showToast }) {
  const [tab, setTab] = useState(initialTab);
  const [includeDesktop, setIncludeDesktop] = useState(false);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [quarantine, setQuarantine] = useState(null);
  const [selectedScan, setSelectedScan] = useState(new Set());
  const [selectedQ, setSelectedQ] = useState(new Set());

  useEffect(() => {
    if (!open) return;
    setTab(initialTab);
    loadAll(false, includeDesktop);
  }, [open, initialTab]);

  const loadAll = async (forceRefresh = false, incDesktop = includeDesktop) => {
    setLoading(true);
    try {
      const [dupRes, qRes] = await Promise.all([
        api.getDuplicates(forceRefresh, incDesktop),
        api.getQuarantine(),
      ]);
      setReport(dupRes);
      setQuarantine(qRes);
      setSelectedScan(new Set());
      setSelectedQ(new Set());
    } catch (err) {
      showToast(err.message || 'Audit failed', true);
    } finally {
      setLoading(false);
    }
  };

  const toggleScanPath = (path) => {
    setSelectedScan((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const toggleQPath = (path) => {
    setSelectedQ((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const selectAllSafe = () => {
    if (!report) return;
    const safe = new Set();
    (report.folder_collisions || []).forEach((c) => {
      if (c.safe_to_recycle) safe.add(c.path);
    });
    (report.duplicate_groups || []).forEach((g) => {
      (g.duplicates || []).forEach((d) => safe.add(d.path));
    });
    (report.junk_items || []).forEach((j) => safe.add(j.path));
    setSelectedScan(safe);
  };

  const handleQuarantine = async () => {
    if (selectedScan.size === 0) return;
    setLoading(true);
    try {
      const res = await api.quarantineItems(Array.from(selectedScan), 'Redundant copy');
      showToast(`Moved ${res.moved_count || 0} item(s) to Quarantine Vault`);
      await loadAll(true);
      setTab('quarantine');
      onChanged?.();
    } catch (err) {
      showToast(err.message || 'Failed to quarantine items', true);
      setLoading(false);
    }
  };

  const handleRecycleDirect = async () => {
    if (selectedScan.size === 0) return;
    setLoading(true);
    try {
      const res = await api.cleanupDuplicates(Array.from(selectedScan));
      showToast(`Recycled ${res.removed_count || 0} item(s)`);
      await loadAll(true);
      onChanged?.();
    } catch (err) {
      showToast(err.message || 'Recycle failed', true);
      setLoading(false);
    }
  };

  const handleRestore = async () => {
    if (selectedQ.size === 0) return;
    setLoading(true);
    try {
      const res = await api.restoreQuarantine(Array.from(selectedQ));
      showToast(`Restored ${res.restored_count || 0} item(s)`);
      await loadAll(true);
      onChanged?.();
    } catch (err) {
      showToast(err.message || 'Restore failed', true);
      setLoading(false);
    }
  };

  const handlePurge = async (all = false) => {
    setLoading(true);
    try {
      const res = await api.purgeQuarantine(all ? null : Array.from(selectedQ));
      showToast(`Removed ${res.removed_count || 0} item(s) to Windows Recycle Bin`);
      await loadAll(true);
      onChanged?.();
    } catch (err) {
      showToast(err.message || 'Remove failed', true);
      setLoading(false);
    }
  };

  const currentStep = tab === 'quarantine' ? ((quarantine?.count || 0) > 0 ? 1 : 2) : 0;

  return (
    <Sheet
      open={open}
      onClose={onClose}
      widthClass="max-w-[820px]"
      eyebrow="Redundancy & Quarantine Engine"
      title="Redundant Files & One-Place Vault"
      subtitle={
        report
          ? `Scanned ${report.scanned_files} files · ${report.redundant_file_count} safe duplicates · ${report.folder_collisions?.length || 0} numbered folders · Reclaimable: ${formatBytes(report.reclaimable_bytes)}`
          : 'Analyzing hashes and folder structures...'
      }
    >
      <StepProgress steps={['1. Scan Workspace', '2. Stage in Quarantine', '3. Remove Safely']} currentStep={currentStep} />

      {/* Tabs */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b pb-3">
        <div className="flex gap-2">
          <Button
            size="sm"
            variant={tab === 'scan' ? 'primary' : 'secondary'}
            onClick={() => setTab('scan')}
          >
            Scan Results
          </Button>
          <Button
            size="sm"
            variant={tab === 'quarantine' ? 'primary' : 'secondary'}
            onClick={() => setTab('quarantine')}
          >
            <Archive className="h-3.5 w-3.5" />
            Quarantine Vault ({quarantine?.count || 0})
          </Button>
        </div>

        {tab === 'scan' && (
          <label className="inline-flex items-center gap-2 text-xs text-[var(--ink-secondary)] cursor-pointer">
            <input
              type="checkbox"
              checked={includeDesktop}
              onChange={(e) => {
                const next = e.target.checked;
                setIncludeDesktop(next);
                loadAll(true, next);
              }}
            />
            <span>Include Desktop in scan</span>
          </label>
        )}
      </div>

      {/* Action Toolbar */}
      {tab === 'scan' ? (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="secondary" onClick={() => loadAll(true)} disabled={loading}>
            <RefreshCw className="h-3.5 w-3.5" /> Rescan
          </Button>
          <Button size="sm" variant="secondary" onClick={selectAllSafe} disabled={loading || !report}>
            <CheckSquare className="h-3.5 w-3.5" /> Select Safe Redundant
          </Button>
          <Button size="sm" variant="primary" onClick={handleQuarantine} disabled={loading || selectedScan.size === 0}>
            <Archive className="h-3.5 w-3.5" /> Move to Quarantine ({selectedScan.size})
          </Button>
          <Button size="sm" variant="destructive" onClick={handleRecycleDirect} disabled={loading || selectedScan.size === 0}>
            <Trash2 className="h-3.5 w-3.5" /> Recycle ({selectedScan.size})
          </Button>
        </div>
      ) : (
        <div className="mb-4 flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1 truncate font-mono text-[11px] text-[var(--ink-muted)]" title={quarantine?.quarantine_dir}>
            {quarantine?.quarantine_dir} ({formatBytes(quarantine?.total_bytes || 0)})
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={handleRestore} disabled={loading || selectedQ.size === 0}>
              <RotateCcw className="h-3.5 w-3.5" /> Restore ({selectedQ.size})
            </Button>
            <Button size="sm" variant="destructive" onClick={() => handlePurge(false)} disabled={loading || selectedQ.size === 0}>
              <Trash2 className="h-3.5 w-3.5" /> Remove Selected
            </Button>
            <Button size="sm" variant="destructive" onClick={() => handlePurge(true)} disabled={loading || !(quarantine?.count > 0)}>
              Empty Quarantine
            </Button>
          </div>
        </div>
      )}

      {/* Body */}
      {loading && <div className="py-16 text-center text-sm text-[var(--ink-muted)]">Processing...</div>}

      {!loading && tab === 'scan' && report && (
        <div className="space-y-5">
          {(report.folder_collisions || []).length > 0 && (
            <Section title={`Numbered Collision Folders (${report.folder_collisions.length})`}>
              {report.folder_collisions.map((c) => (
                <CheckRow
                  key={c.path}
                  checked={selectedScan.has(c.path)}
                  onChange={() => toggleScanPath(c.path)}
                  title={c.name}
                  badge={{ text: c.relation, tone: c.safe_to_recycle ? 'emerald' : 'amber' }}
                  meta={`${c.file_count} files · ${formatBytes(c.size)} · ${c.path}`}
                />
              ))}
            </Section>
          )}

          {(report.duplicate_groups || []).length > 0 && (
            <Section title={`Safe Exact SHA-256 Duplicates (${report.duplicate_groups.length} groups)`}>
              {report.duplicate_groups.slice(0, 60).map((g) => (
                <div key={`${g.hash}-${g.keep.path}`} className="rounded-lg border bg-[var(--input-bg)] p-3 space-y-2">
                  <div className="break-all font-mono text-[11px] text-[var(--emerald)]">
                    KEEP ({formatBytes(g.size)}): {g.keep.path}
                  </div>
                  {g.duplicates.map((d) => (
                    <label key={d.path} className="flex items-start gap-2.5 pl-2 font-mono text-[11px] text-[var(--ink-secondary)] cursor-pointer">
                      <input
                        type="checkbox"
                        className="mt-0.5"
                        checked={selectedScan.has(d.path)}
                        onChange={() => toggleScanPath(d.path)}
                      />
                      <span className="break-all">REDUNDANT: {d.path}</span>
                    </label>
                  ))}
                </div>
              ))}
            </Section>
          )}

          {(report.junk_items || []).length > 0 && (
            <Section title={`Empty & Temp Artifacts (${report.junk_items.length})`}>
              {report.junk_items.slice(0, 60).map((j) => (
                <CheckRow
                  key={j.path}
                  checked={selectedScan.has(j.path)}
                  onChange={() => toggleScanPath(j.path)}
                  title={j.name}
                  badge={{ text: j.reason, tone: 'neutral' }}
                  meta={j.path}
                />
              ))}
            </Section>
          )}

          {(report.intra_repo_groups || []).length > 0 && (
            <Section title={`Same-Repo Test / Run Data (${report.intra_repo_groups.length} groups — excluded from auto-select)`}>
              {report.intra_repo_groups.slice(0, 20).map((g) => (
                <div key={`${g.hash}-${g.keep.path}`} className="rounded-lg border bg-[var(--input-bg)] p-3 space-y-1.5 opacity-80">
                  <div className="break-all font-mono text-[11px] text-[var(--ink-secondary)]">
                    PRIMARY ({formatBytes(g.size)}): {g.keep.path}
                  </div>
                  {g.duplicates.slice(0, 3).map((d) => (
                    <label key={d.path} className="flex items-start gap-2.5 pl-2 font-mono text-[11px] text-[var(--ink-muted)] cursor-pointer">
                      <input
                        type="checkbox"
                        className="mt-0.5"
                        checked={selectedScan.has(d.path)}
                        onChange={() => toggleScanPath(d.path)}
                      />
                      <span className="break-all">COPY: {d.path}</span>
                    </label>
                  ))}
                </div>
              ))}
            </Section>
          )}
        </div>
      )}

      {!loading && tab === 'quarantine' && quarantine && (
        <div className="space-y-2">
          {(quarantine.items || []).length === 0 ? (
            <div className="rounded-xl border bg-[var(--input-bg)] p-8 text-center text-sm text-[var(--ink-muted)]">
              Quarantine Vault is empty. Stage redundant items from Scan Results to inspect and remove them in one place.
            </div>
          ) : (
            quarantine.items.map((item) => (
              <div key={item.quarantine_path} className="rounded-lg border bg-[var(--input-bg)] p-3">
                <label className="flex items-center gap-2.5 text-sm font-medium text-[var(--ink)] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedQ.has(item.quarantine_path)}
                    onChange={() => toggleQPath(item.quarantine_path)}
                  />
                  {item.is_dir ? (
                    <Folder className="h-4 w-4 text-[var(--accent-bright)]" />
                  ) : (
                    <FileText className="h-4 w-4 text-[var(--ink-muted)]" />
                  )}
                  <span className="truncate">{item.name}</span>
                  <Badge tone="violet">{formatBytes(item.size)}</Badge>
                  {item.reason && <Badge tone="neutral">{item.reason}</Badge>}
                </label>
                <div className="mt-1 pl-6 break-all font-mono text-[11px] text-[var(--ink-muted)]">
                  Original: {item.original_path || 'Manual'}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </Sheet>
  );
}

function Section({ title, children }) {
  return (
    <div className="space-y-2">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent-bright)]">
        {title}
      </div>
      {children}
    </div>
  );
}

function CheckRow({ checked, onChange, title, badge, meta }) {
  return (
    <div className="rounded-lg border bg-[var(--input-bg)] p-3">
      <label className="flex flex-wrap items-center gap-2 text-sm font-medium text-[var(--ink)] cursor-pointer">
        <input type="checkbox" checked={checked} onChange={onChange} />
        <span>{title}</span>
        {badge && <Badge tone={badge.tone}>{badge.text}</Badge>}
      </label>
      <div className="mt-1 pl-6 break-all font-mono text-[11px] text-[var(--ink-muted)]">{meta}</div>
    </div>
  );
}
