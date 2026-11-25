"""Safe directory/file preview builder with breadcrumb navigation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from classifier import IGNORED_FILE_NAMES
from git_inspector import find_git_repos, get_git_summary

TEXT_PREVIEW_EXTS = {
    ".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".html", ".css", ".ps1", ".bat", ".sh", ".sql", ".csv",
}


def build_item_preview(target_path: Path, max_bytes: int = 8192) -> dict[str, Any]:
    """Build a safe, fast preview payload (folder entries + README + parent link + Git info)."""
    resolved = target_path.resolve()
    parent_dir = resolved.parent if resolved.parent != resolved else None

    if resolved.is_dir():
        entries: list[dict[str, Any]] = []
        readme_text: str | None = None
        readme_name: str | None = None
        git_repos = find_git_repos(resolved, max_depth=2)
        git_info = get_git_summary(git_repos[0]) if git_repos else None

        try:
            children = sorted(
                resolved.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
            for child in children[:80]:
                if child.name in IGNORED_FILE_NAMES:
                    continue
                try:
                    st = child.stat()
                    sz = 0 if child.is_dir() else st.st_size
                except OSError:
                    sz = 0
                entries.append(
                    {
                        "name": child.name,
                        "path": str(child.resolve()),
                        "is_dir": child.is_dir(),
                        "size": sz,
                    }
                )
                if readme_text is None and child.is_file() and child.name.lower() in {"readme.md", "readme.txt", "progress.md"}:
                    try:
                        raw = child.read_bytes()[:max_bytes]
                        readme_text = raw.decode("utf-8", errors="replace")
                        readme_name = child.name
                    except OSError:
                        pass
        except OSError:
            pass

        return {
            "kind": "directory",
            "name": resolved.name,
            "path": str(resolved),
            "parent_path": str(parent_dir) if parent_dir else None,
            "entries": entries,
            "entry_count": len(entries),
            "readme_name": readme_name,
            "readme_text": readme_text,
            "git_info": git_info,
        }

    try:
        st = resolved.stat()
        size = st.st_size
        mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        size = 0
        mtime = "Unknown"

    snippet: str | None = None
    truncated = False
    if resolved.suffix.lower() in TEXT_PREVIEW_EXTS or size <= max_bytes:
        try:
            raw = resolved.read_bytes()
            truncated = len(raw) > max_bytes
            if b"\x00" not in raw[:1024]:
                snippet = raw[:max_bytes].decode("utf-8", errors="replace")
        except OSError:
            snippet = None

    return {
        "kind": "file",
        "name": resolved.name,
        "path": str(resolved),
        "parent_path": str(parent_dir) if parent_dir else None,
        "extension": resolved.suffix.lower(),
        "size": size,
        "last_modified": mtime,
        "snippet": snippet,
        "truncated": truncated,
    }
