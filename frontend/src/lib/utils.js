import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let idx = 0;
  let val = bytes;
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx++;
  }
  return `${val.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export function naturalCompare(a, b) {
  return String(a || '').localeCompare(String(b || ''), undefined, {
    numeric: true,
    sensitivity: 'base',
  });
}

export function toWebRepoUrl(remoteUrl) {
  if (!remoteUrl) return '';
  let url = String(remoteUrl).trim();
  const sshMatch = url.match(/^git@([^:]+):(.+?)(?:\.git)?$/i);
  if (sshMatch) {
    return `https://${sshMatch[1]}/${sshMatch[2]}`;
  }
  const sshProtoMatch = url.match(/^ssh:\/\/(?:git@)?([^/]+)\/(.+?)(?:\.git)?$/i);
  if (sshProtoMatch) {
    return `https://${sshProtoMatch[1]}/${sshProtoMatch[2]}`;
  }
  if (/^https?:\/\//i.test(url)) {
    return url.replace(/\.git$/i, '');
  }
  return '';
}
