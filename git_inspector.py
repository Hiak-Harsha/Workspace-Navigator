"""Git repository discovery and parallel lightweight status inspection."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import re
import subprocess
from pathlib import Path
from typing import Any

SKIP_GIT_WALK_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    ".next",
    "dist",
    "build",
    ".gradle",
    "target",
    "android-sdk",
    "SOURCE_REPO",
    "ZIP1_REF",
}


def find_git_repos(root_dir: Path, max_depth: int = 2) -> list[Path]:
    """Find .git directories up to max_depth levels below root_dir."""
    repos: list[Path] = []
    if not root_dir.is_dir():
        return repos
    if (root_dir / ".git").exists():
        repos.append(root_dir)
        return repos
    if max_depth <= 0:
        return repos

    def _walk(curr: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            for entry in curr.iterdir():
                if not entry.is_dir() or entry.name.startswith(".") or entry.name in SKIP_GIT_WALK_DIRS:
                    continue
                if (entry / ".git").exists():
                    repos.append(entry)
                elif depth < max_depth:
                    _walk(entry, depth + 1)
        except OSError:
            pass

    _walk(root_dir, 1)
    return repos


def get_git_summary(repo_dir: Path) -> dict[str, Any]:
    """Return lightweight git status (branch, remote, remote_url, dirty, unpushed) fast and safely."""
    info: dict[str, Any] = {
        "path": str(repo_dir),
        "name": repo_dir.name,
        "branch": None,
        "has_remote": False,
        "remote_url": None,
        "dirty_count": 0,
        "unpushed_count": 0,
    }
    git_dir = repo_dir / ".git"
    if git_dir.is_dir():
        try:
            head_text = (git_dir / "HEAD").read_text(encoding="utf-8", errors="ignore").strip()
            if head_text.startswith("ref: refs/heads/"):
                info["branch"] = head_text[len("ref: refs/heads/") :]
            elif head_text:
                info["branch"] = head_text[:7]
        except OSError:
            pass
        try:
            cfg_text = (git_dir / "config").read_text(encoding="utf-8", errors="ignore")
            info["has_remote"] = '[remote "' in cfg_text
            m_url = re.search(r'\[remote\s+"origin"\][^\[]*?url\s*=\s*(.+)', cfg_text)
            if not m_url:
                m_url = re.search(r'\[remote\s+"[^"]+"\][^\[]*?url\s*=\s*(.+)', cfg_text)
            if m_url:
                info["remote_url"] = m_url.group(1).strip()
        except OSError:
            pass

    no_window = 0x08000000 if os.name == "nt" else 0
    base_cmd = ["git", "-c", "safe.directory=*", "-C", str(repo_dir)]
    try:
        st = subprocess.run(
            base_cmd + ["status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=1.5,
            creationflags=no_window,
        )
        if st.returncode == 0:
            info["dirty_count"] = sum(1 for ln in st.stdout.splitlines() if ln.strip())
    except Exception:
        pass

    if info["has_remote"]:
        try:
            unp = subprocess.run(
                base_cmd + ["log", "--branches", "--not", "--remotes", "--oneline"],
                capture_output=True,
                text=True,
                timeout=1.5,
                creationflags=no_window,
            )
            if unp.returncode == 0:
                info["unpushed_count"] = sum(1 for ln in unp.stdout.splitlines() if ln.strip())
        except Exception:
            pass
    return info


def get_git_summaries_parallel(repo_dirs: list[Path], max_workers: int = 8) -> dict[str, dict[str, Any]]:
    """Fetch git summaries in parallel across all detected repositories."""
    if not repo_dirs:
        return {}
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(repo_dirs))) as pool:
        for repo, summary in zip(repo_dirs, pool.map(get_git_summary, repo_dirs)):
            results[str(repo)] = summary
    return results
