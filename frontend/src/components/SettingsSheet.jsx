import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Button } from './ui/Button';
import { Sheet } from './ui/Sheet';

export function SettingsSheet({ open, onClose, onSaved, showToast }) {
  const [workspaceDir, setWorkspaceDir] = useState('');
  const [desktopDir, setDesktopDir] = useState('');
  const [duplicatePolicy, setDuplicatePolicy] = useState('recycle');
  const [minAgeSeconds, setMinAgeSeconds] = useState(20);
  const [extraRoots, setExtraRoots] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    api
      .getConfig()
      .then((cfg) => {
        setWorkspaceDir(cfg.workspace_dir || '');
        setDesktopDir(cfg.desktop_dir || '');
        setDuplicatePolicy(cfg.duplicate_policy || 'recycle');
        setMinAgeSeconds(cfg.min_age_seconds ?? 20);
        setExtraRoots(cfg.extra_scan_roots || []);
      })
      .catch((err) => showToast(err.message || 'Failed to load settings', true));
  }, [open]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.saveConfig({
        workspace_dir: workspaceDir,
        desktop_dir: desktopDir,
        duplicate_policy: duplicatePolicy,
        min_age_seconds: Number(minAgeSeconds || 20),
      });
      showToast('Settings saved & Workspace initialized');
      onSaved?.();
      onClose?.();
    } catch (err) {
      showToast(err.message || 'Failed to save settings', true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      eyebrow="Universal Machine Config"
      title="Workspace & Path Settings"
      subtitle="Auto-resolves OneDrive Desktops, Workspace categories, and external Git roots"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block space-y-1.5 text-xs font-medium text-[var(--ink-secondary)]">
          <span>Workspace Directory</span>
          <input
            type="text"
            required
            value={workspaceDir}
            onChange={(e) => setWorkspaceDir(e.target.value)}
            className="min-h-[44px] w-full rounded-lg border bg-[var(--input-bg)] px-3 font-mono text-xs text-[var(--ink)] outline-none focus:border-[var(--accent-bright)]"
          />
        </label>

        <label className="block space-y-1.5 text-xs font-medium text-[var(--ink-secondary)]">
          <span>Desktop Directory (Windows Shell / OneDrive auto-detected)</span>
          <input
            type="text"
            required
            value={desktopDir}
            onChange={(e) => setDesktopDir(e.target.value)}
            className="min-h-[44px] w-full rounded-lg border bg-[var(--input-bg)] px-3 font-mono text-xs text-[var(--ink)] outline-none focus:border-[var(--accent-bright)]"
          />
        </label>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block space-y-1.5 text-xs font-medium text-[var(--ink-secondary)]">
            <span>Duplicate Collision Policy</span>
            <select
              value={duplicatePolicy}
              onChange={(e) => setDuplicatePolicy(e.target.value)}
              className="min-h-[44px] w-full rounded-lg border bg-[var(--input-bg)] px-3 text-xs text-[var(--ink)] outline-none focus:border-[var(--accent-bright)]"
            >
              <option value="recycle">Recycle exact duplicates (Recommended)</option>
              <option value="skip">Skip exact duplicates on Desktop</option>
              <option value="rename">Keep &amp; rename with (1)</option>
            </select>
          </label>

          <label className="block space-y-1.5 text-xs font-medium text-[var(--ink-secondary)]">
            <span>Settle Delay (seconds)</span>
            <input
              type="number"
              min={0}
              max={3600}
              value={minAgeSeconds}
              onChange={(e) => setMinAgeSeconds(e.target.value)}
              className="min-h-[44px] w-full rounded-lg border bg-[var(--input-bg)] px-3 font-mono text-xs text-[var(--ink)] outline-none focus:border-[var(--accent-bright)]"
            />
          </label>
        </div>

        <div className="rounded-xl border bg-[var(--input-bg)] p-3.5">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
            Indexed Project Roots ({extraRoots.length + 1})
          </div>
          <div className="space-y-1.5 font-mono text-[11px] text-[var(--ink-secondary)]">
            <div>• {workspaceDir} (Primary Workspace)</div>
            {extraRoots.map((r) => (
              <div key={r.path}>
                • {r.path} ({r.category})
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap justify-end gap-2.5 pt-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={saving}>
            {saving ? 'Saving...' : 'Save & Initialize Folders'}
          </Button>
        </div>
      </form>
    </Sheet>
  );
}
