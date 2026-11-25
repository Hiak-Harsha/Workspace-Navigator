"""Workspace Navigator HTTP Server, Desktop Auto-Organizer, and Universal CLI."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

NAVIGATOR_DIR = Path(__file__).resolve().parent
LOG_FILE = NAVIGATOR_DIR / "server.log"
ORGANIZER_LOG = NAVIGATOR_DIR / "auto_organizer.log"
FAVORITES_FILE = NAVIGATOR_DIR / "favorites.json"
ORGANIZER_CONFIG_FILE = NAVIGATOR_DIR / "organizer_config.json"

# Fix for pythonw.exe on Windows where stdout/stderr are None
if sys.stdout is None:
    try:
        sys.stdout = open(LOG_FILE, "a", encoding="utf-8")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open(LOG_FILE, "a", encoding="utf-8")
    except Exception:
        pass

if str(NAVIGATOR_DIR) not in sys.path:
    sys.path.insert(0, str(NAVIGATOR_DIR))

from classifier import CODE_MARKERS, IGNORED_FILE_NAMES, TEMP_SUFFIXES
from navigator_core import (
    CATEGORY_DISPLAY_ORDER,
    DEFAULT_CATEGORIES,
    QUARANTINE_SUBDIR,
    analyze_workspace_redundancy,
    build_item_preview,
    classify_desktop_item,
    compare_folders,
    compute_file_sha256,
    ensure_workspace_structure,
    find_git_repos,
    get_git_summaries_parallel,
    get_quarantine_dir,
    get_unique_destination,
    list_quarantine,
    load_config,
    purge_quarantine,
    quarantine_items,
    restore_quarantine_items,
    save_config,
)

STATE_LOCK = threading.RLock()
RUNTIME_CFG: dict[str, Any] = load_config(ORGANIZER_CONFIG_FILE, NAVIGATOR_DIR)
RECENT_MOVES: list[dict[str, Any]] = []
DUPLICATES_CACHE: dict[str, Any] | None = None
PROJECTS_CACHE: tuple[float, list[dict[str, Any]]] | None = None
PROJECTS_CACHE_TTL_SECONDS = 15.0

HOME_SKIP_DIRS = {
    "appdata", "anaconda3", "miniforge3", "node_modules", "onedrive",
    "searches", "contacts", "favorites", "links", "saved games", "videos",
    "music", "pictures", "downloads", "documents", "workspace", "desktop",
    "virtualbox vms", "pycharmprojects", "scikit_learn_data", "open-source",
}

FAVICON_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    b'<rect width="64" height="64" rx="14" fill="#090b10"/>'
    b'<path d="M36 10L16 36h14l-4 18 22-28H34l2-16z" fill="#22d3ee"/>'
    b"</svg>"
)


def get_workspace_dir() -> Path:
    with STATE_LOCK:
        return Path(RUNTIME_CFG["workspace_dir"])


def get_desktop_dir() -> Path:
    with STATE_LOCK:
        return Path(RUNTIME_CFG["desktop_dir"])


def get_manifest_file() -> Path:
    return get_workspace_dir() / "migration_manifest.json"


def invalidate_caches() -> None:
    global DUPLICATES_CACHE, PROJECTS_CACHE
    with STATE_LOCK:
        DUPLICATES_CACHE = None
        PROJECTS_CACHE = None


def normalize_path(p: str) -> str:
    """Clean and normalize Windows/POSIX path, removing trailing slashes and quotes."""
    if not p:
        return ""
    clean = p.strip().strip('"').strip("'")
    norm = os.path.normpath(clean)
    if len(norm) > 3 and norm.endswith(("\\", "/")):
        norm = norm.rstrip(r"\/")
    return norm


def is_within_managed_roots(target_path: Path) -> bool:
    """Verify target_path is strictly inside Workspace or Desktop (never the roots themselves)."""
    try:
        resolved = target_path.resolve()
        for root in (get_workspace_dir().resolve(), get_desktop_dir().resolve()):
            if resolved != root and root in resolved.parents:
                return True
    except Exception:
        return False
    return False


def is_within_preview_roots(target_path: Path) -> bool:
    """Allow safe read-only preview inside Workspace, Desktop, or valid extra project roots."""
    if is_within_managed_roots(target_path):
        return True
    try:
        resolved = target_path.resolve()
        if resolved in (get_workspace_dir().resolve(), get_desktop_dir().resolve()):
            return True
        with STATE_LOCK:
            extra_roots = list(RUNTIME_CFG.get("extra_scan_roots", []))
        for entry in extra_roots:
            rp = Path(entry.get("path", "")).resolve()
            if resolved == rp or rp not in resolved.parents:
                continue
            mode = entry.get("mode", "project_markers_only")
            if mode == "project_markers_only":
                rel = resolved.relative_to(rp)
                top_dir = rp / rel.parts[0]
                if top_dir.name.startswith(".") or top_dir.name.lower() in HOME_SKIP_DIRS:
                    continue
                if not top_dir.is_dir() or not _has_project_marker(top_dir):
                    continue
            return True
    except Exception:
        return False
    return False


def send_to_recycle_bin(path_str: str) -> bool:
    """Safely move a file or folder to the Windows Recycle Bin (with fallback)."""
    target = normalize_path(path_str)
    if os.name == "nt":

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", wintypes.WORD),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", wintypes.LPVOID),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        FO_DELETE = 0x0003
        FOF_ALLOWUNDO = 0x0040
        FOF_NOCONFIRMATION = 0x0010
        FOF_SILENT = 0x0004

        file_op = SHFILEOPSTRUCTW()
        file_op.hwnd = None
        file_op.wFunc = FO_DELETE
        file_op.pFrom = target + "\0\0"
        file_op.pTo = None
        file_op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
        file_op.fAnyOperationsAborted = False
        file_op.hNameMappings = None
        file_op.lpszProgressTitle = None

        res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(file_op))
        if res == 0 and not file_op.fAnyOperationsAborted:
            return True

    if os.path.isdir(target):
        shutil.rmtree(target)
    elif os.path.exists(target):
        os.remove(target)
    return True


def load_favorites() -> list[str]:
    if FAVORITES_FILE.exists():
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def save_favorites(favs: list[str]) -> None:
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(favs, f, indent=2)
    except Exception as e:
        print(f"Error saving favorites: {e}")


def append_manifest_entries(entries: list[dict[str, Any]]) -> None:
    if not entries:
        return
    manifest_file = get_manifest_file()
    try:
        manifest: list[dict[str, Any]] = []
        if manifest_file.exists():
            with open(manifest_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    manifest = loaded
        manifest.extend(entries)
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"Error appending to manifest: {e}")


def log_organizer_action(line: str) -> None:
    try:
        with open(ORGANIZER_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")
    except Exception:
        pass


def _is_item_settled(item: Path, min_age_seconds: int) -> bool:
    if min_age_seconds <= 0:
        return True
    try:
        return (time.time() - item.stat().st_mtime) >= min_age_seconds
    except OSError:
        return False


def _handle_duplicate_collision(src: Path, dest: Path, policy: str) -> tuple[str, Path | None]:
    is_redundant = False
    if src.is_file() and dest.is_file():
        try:
            if src.stat().st_size == dest.stat().st_size and compute_file_sha256(src) == compute_file_sha256(dest):
                is_redundant = True
        except OSError:
            is_redundant = False
    elif src.is_dir() and dest.is_dir():
        relation = compare_folders(src, dest)
        is_redundant = relation in {"identical", "src_subset_of_dest"}

    if not is_redundant:
        return "move", get_unique_destination(dest)
    if policy == "skip":
        return "skip_duplicate", None
    if policy == "rename":
        return "move", get_unique_destination(dest)
    return "recycle_duplicate", dest


def organize_desktop_pass(dry_run: bool = False, respect_age: bool = True) -> list[dict[str, Any]]:
    """Classify and move Desktop items into Workspace with SHA-256 duplicate protection."""
    with STATE_LOCK:
        desktop_dir = Path(RUNTIME_CFG["desktop_dir"])
        workspace_dir = Path(RUNTIME_CFG["workspace_dir"])
        dup_policy = RUNTIME_CFG.get("duplicate_policy", "recycle")
        min_age = int(RUNTIME_CFG.get("min_age_seconds", 20)) if respect_age else 0
        categories = RUNTIME_CFG.get("categories") or DEFAULT_CATEGORIES

    if not desktop_dir.exists():
        return []
    if not dry_run:
        ensure_workspace_structure(workspace_dir, categories)

    results: list[dict[str, Any]] = []
    manifest_batch: list[dict[str, Any]] = []

    try:
        desktop_items = sorted(desktop_dir.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []

    for item in desktop_items:
        if item.name.startswith((".", "~$")) or item.name.lower() in IGNORED_FILE_NAMES:
            continue
        if item.suffix.lower() in {".lnk", ".url", ".ini"} or item.suffix.lower() in TEMP_SUFFIXES:
            continue
        if not _is_item_settled(item, min_age):
            continue
        if item.is_dir():
            try:
                if not any(item.iterdir()):
                    continue
            except OSError:
                continue

        dest = classify_desktop_item(
            item, workspace_dir=workspace_dir, navigator_dir=NAVIGATOR_DIR, categories=categories
        )
        if dest is None:
            continue

        if item.is_file():
            try:
                with open(item, "a"):
                    pass
            except OSError:
                continue

        action_kind = "move"
        target_dest = dest
        if dest.exists():
            action_kind, resolved_dest = _handle_duplicate_collision(item, dest, dup_policy)
            if action_kind == "skip_duplicate":
                results.append(
                    {
                        "Item": item.name,
                        "Type": "Folder" if item.is_dir() else "File",
                        "From": str(item),
                        "To": str(dest),
                        "Status": "Skipped (Exact Duplicate)",
                        "Timestamp": datetime.now().isoformat(timespec="seconds"),
                    }
                )
                continue
            if resolved_dest is not None:
                target_dest = resolved_dest

        if dry_run:
            status = (
                "Plan: Recycle Duplicate"
                if action_kind == "recycle_duplicate"
                else f"Plan -> {target_dest.relative_to(workspace_dir)}"
            )
            results.append(
                {
                    "Item": item.name,
                    "Type": "Folder" if item.is_dir() else "File",
                    "From": str(item),
                    "To": str(target_dest),
                    "Status": status,
                }
            )
            continue

        try:
            if action_kind == "recycle_duplicate":
                send_to_recycle_bin(str(item))
                entry = {
                    "Item": item.name,
                    "Type": "Folder" if item.is_dir() else "File",
                    "From": str(item),
                    "To": f"Recycle Bin (duplicate of {target_dest})",
                    "Status": "Deduplicated",
                    "Timestamp": datetime.now().isoformat(timespec="seconds"),
                }
                log_organizer_action(f"DEDUP (Recycle Bin): {item.name} == {target_dest}")
                results.append(entry)
                with STATE_LOCK:
                    RECENT_MOVES.insert(0, entry)
                    del RECENT_MOVES[20:]
                continue

            target_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(target_dest))
            if item.exists():
                continue

            entry = {
                "Item": item.name,
                "Type": "Folder" if target_dest.is_dir() else "File",
                "From": str(item),
                "To": str(target_dest),
                "Status": "Auto-Moved",
                "Timestamp": datetime.now().isoformat(timespec="seconds"),
            }
            manifest_batch.append(entry)
            results.append(entry)
            log_organizer_action(f"{item.name} -> {target_dest}")
            with STATE_LOCK:
                RECENT_MOVES.insert(0, entry)
                del RECENT_MOVES[20:]
        except Exception as exc:
            log_organizer_action(f"ERROR moving {item.name}: {exc}")

    if manifest_batch and not dry_run:
        append_manifest_entries(manifest_batch)
        invalidate_caches()

    return results


def auto_organizer_worker() -> None:
    while True:
        try:
            with STATE_LOCK:
                enabled = bool(RUNTIME_CFG.get("enabled", False))
            if enabled:
                organize_desktop_pass(dry_run=False, respect_age=True)
        except Exception:
            pass
        time.sleep(5)


def _has_project_marker(dir_path: Path) -> bool:
    if (dir_path / ".git").exists():
        return True
    try:
        for entry in dir_path.iterdir():
            if entry.is_file() and entry.name.lower() in CODE_MARKERS:
                return True
    except OSError:
        return False
    return False


def get_item_info(
    path: Path,
    category_name: str,
    category_icon: str,
    favorites_set: set[str],
    nested_git_depth: int = 2,
    source_scope: str = "workspace",
    check_git: bool = True,
) -> tuple[dict[str, Any], Path | None]:
    is_dir = path.is_dir()
    git_repos = find_git_repos(path, max_depth=nested_git_depth) if (is_dir and check_git) else []
    primary_repo = git_repos[0] if git_repos else None

    try:
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        size_bytes = 0 if is_dir else stat.st_size
    except OSError:
        mtime = "Unknown"
        size_bytes = 0

    resolved_str = str(path.resolve())
    is_fav = resolved_str in favorites_set or path.name in favorites_set

    return (
        {
            "id": f"{path.parent.name}_{path.name}".replace(" ", "_"),
            "name": path.name,
            "path": resolved_str,
            "parent": str(path.parent.resolve()),
            "is_dir": is_dir,
            "is_git": primary_repo is not None,
            "git_info": None,
            "category": category_name,
            "category_icon": category_icon,
            "source_scope": source_scope,
            "last_modified": mtime,
            "size_bytes": size_bytes,
            "is_favorite": is_fav,
            "extension": path.suffix.lower() if not is_dir else "folder",
        },
        primary_repo,
    )


def scan_items(force_refresh: bool = False) -> list[dict[str, Any]]:
    global PROJECTS_CACHE
    with STATE_LOCK:
        if not force_refresh and PROJECTS_CACHE is not None:
            ts, cached_items = PROJECTS_CACHE
            if (time.time() - ts) < PROJECTS_CACHE_TTL_SECONDS:
                return cached_items
        workspace_dir = Path(RUNTIME_CFG["workspace_dir"])
        categories = RUNTIME_CFG.get("categories") or DEFAULT_CATEGORIES
        git_depth = int(RUNTIME_CFG.get("scan_nested_git_depth", 2))
        extra_roots = list(RUNTIME_CFG.get("extra_scan_roots", []))

    favorites = set(load_favorites())
    items: list[dict[str, Any]] = []
    repo_links: list[tuple[int, Path]] = []
    seen_paths: set[str] = set()

    def _add_item(p: Path, cat_name: str, cat_icon: str, scope: str, check_git: bool = True) -> None:
        try:
            res_key = str(p.resolve()).lower()
        except OSError:
            return
        if res_key in seen_paths:
            return
        seen_paths.add(res_key)
        item_dict, primary_repo = get_item_info(
            p, cat_name, cat_icon, favorites, git_depth, scope, check_git=check_git
        )
        idx = len(items)
        items.append(item_dict)
        if primary_repo is not None:
            repo_links.append((idx, primary_repo))

    # 1. Scan structured Workspace categories + sub-collections
    if workspace_dir.exists():
        for folder_name, meta in categories.items():
            cat_dir = workspace_dir / folder_name
            if not cat_dir.is_dir():
                continue
            cat_name = meta.get("label", folder_name)
            cat_icon = meta.get("icon", "📁")
            sub_collections = {s.lower() for s in meta.get("sub_collections", [])}
            is_archive_cat = folder_name == "00_Archives_Storage"

            try:
                children = list(cat_dir.iterdir())
            except OSError:
                continue

            for child in children:
                if child.name.startswith(".") or child.name == QUARANTINE_SUBDIR:
                    continue
                _add_item(child, cat_name, cat_icon, "workspace", check_git=not is_archive_cat)
                if child.is_dir() and child.name.lower() in sub_collections:
                    try:
                        for sub_file in child.iterdir():
                            if sub_file.name.startswith(".") or sub_file.name == QUARANTINE_SUBDIR:
                                continue
                            _add_item(sub_file, cat_name, cat_icon, "workspace", check_git=not is_archive_cat)
                    except OSError:
                        continue

        # Also index Navigator itself if inside Workspace
        if NAVIGATOR_DIR.parent.resolve() == workspace_dir.resolve():
            _add_item(NAVIGATOR_DIR, "Development", "💻", "workspace")

    # 2. Scan extra project roots (Home repos, ~/open-source, Desktop projects/files)
    for root_cfg in extra_roots:
        rp = Path(os.path.expandvars(str(root_cfg.get("path", "")))).expanduser()
        if not rp.is_dir():
            continue
        cat_name = root_cfg.get("category", "External Projects")
        cat_icon = root_cfg.get("icon", "📁")
        mode = root_cfg.get("mode", "project_markers_only")

        try:
            entries = list(rp.iterdir())
        except OSError:
            continue

        for entry in entries:
            name_l = entry.name.lower()
            if entry.name.startswith(".") or name_l in IGNORED_FILE_NAMES:
                continue
            if mode == "project_markers_only":
                if not entry.is_dir() or name_l in HOME_SKIP_DIRS:
                    continue
                if not _has_project_marker(entry):
                    continue
                _add_item(entry, cat_name, cat_icon, "external")
            elif mode == "all_dirs":
                if entry.is_dir():
                    _add_item(entry, cat_name, cat_icon, "external")
            elif mode == "projects_and_files":
                if entry.suffix.lower() in {".lnk", ".url", ".ini"} or entry.suffix.lower() in TEMP_SUFFIXES:
                    continue
                if entry.is_dir() or entry.is_file():
                    _add_item(entry, cat_name, cat_icon, "desktop")

    if repo_links:
        summaries = get_git_summaries_parallel([repo for _, repo in repo_links])
        for idx, repo in repo_links:
            items[idx]["git_info"] = summaries.get(str(repo))

    items.sort(key=lambda x: (x["category"], x["name"].lower()))
    with STATE_LOCK:
        PROJECTS_CACHE = (time.time(), items)
    return items


def find_vscode_exe() -> str | None:
    env_candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft VS Code" / "Code.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft VS Code" / "Code.exe",
        Path.home() / "Downloads" / "Microsoft VS Code" / "Code.exe",
    ]
    for c in env_candidates:
        if str(c) and c.is_file():
            return str(c.resolve())

    for cmd in ("code.cmd", "code.exe", "code"):
        found = shutil.which(cmd)
        if found:
            return found
    return None


def _visible_startupinfo() -> Any:
    """Ensure child GUI/console windows open visibly even when server.py was launched hidden."""
    if os.name != "nt":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 1  # SW_SHOWNORMAL
    return si


def _allow_foreground_window() -> None:
    """Permit newly launched Explorer/VS Code/Terminal windows to come to the foreground on Windows."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
    except Exception:
        pass


def open_in_explorer(target_path: str) -> tuple[bool, str]:
    """Deterministically open the exact folder or highlight the exact file in Windows Explorer."""
    p = Path(target_path).resolve()
    if os.name != "nt":
        return False, "Explorer is only available on Windows"
    _allow_foreground_window()
    si = _visible_startupinfo()
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    if p.is_dir():
        subprocess.Popen(["explorer.exe", str(p)], startupinfo=si, creationflags=flags)
    else:
        # Pass unquoted /select, with quoted path so paths containing spaces select properly
        subprocess.Popen(f'explorer.exe /select,"{str(p)}"', startupinfo=si, creationflags=flags)
    return True, "Opened in File Explorer"


def open_in_vscode(target_path: str) -> tuple[bool, str]:
    code_exe = find_vscode_exe()
    if not code_exe:
        return False, "VS Code executable not found on system"

    _allow_foreground_window()
    p = Path(target_path).resolve()
    target = str(p if p.is_dir() else p.parent)
    cwd = os.path.dirname(code_exe) or None
    si = _visible_startupinfo()
    if os.name == "nt":
        if code_exe.lower().endswith((".cmd", ".bat")):
            subprocess.Popen(
                ["cmd.exe", "/c", code_exe, "--new-window", target],
                cwd=cwd,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            subprocess.Popen(
                [code_exe, "--new-window", target],
                cwd=cwd,
                startupinfo=si,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
    else:
        subprocess.Popen([code_exe, "--new-window", target], cwd=cwd)
    return True, "Opened in VS Code"


def open_in_terminal(target_path: str) -> tuple[bool, str]:
    p = Path(target_path).resolve()
    target_dir = str(p if p.is_dir() else p.parent)
    if os.name == "nt":
        # CREATE_NEW_CONSOLE (0x00000010) allocates a visible window; DETACHED_PROCESS hides it.
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        escaped_dir = target_dir.replace("'", "''")
        cmd = ["powershell.exe", "-NoExit", "-Command", f"Set-Location -LiteralPath '{escaped_dir}'"]
        subprocess.Popen(cmd, cwd=target_dir, startupinfo=_visible_startupinfo(), creationflags=flags)
        return True, "Opened in PowerShell Terminal"
    return False, "Terminal launcher requires Windows PowerShell"


class NavigatorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        dist_dir = NAVIGATOR_DIR / "frontend" / "dist"
        serve_dir = dist_dir if (dist_dir / "index.html").is_file() else NAVIGATOR_DIR
        super().__init__(*args, directory=str(serve_dir), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        try:
            if sys.stderr and not sys.stderr.closed:
                sys.stderr.write(
                    "%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args)
                )
                sys.stderr.flush()
        except Exception:
            pass

    def _send_json(self, status_code: int, payload: Any) -> None:
        raw = json.dumps(payload).encode("utf-8")
        try:
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.end_headers()

    def do_GET(self) -> None:
        global DUPLICATES_CACHE
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/favicon.ico":
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(FAVICON_SVG)))
            self.end_headers()
            self.wfile.write(FAVICON_SVG)
            return

        if parsed.path == "/api/projects":
            try:
                force_refresh = query.get("refresh", ["0"])[0] == "1"
                items = scan_items(force_refresh=force_refresh)
                with STATE_LOCK:
                    ws_dir = Path(RUNTIME_CFG["workspace_dir"])
                    dt_dir = Path(RUNTIME_CFG["desktop_dir"])
                    enabled = bool(RUNTIME_CFG.get("enabled", False))
                    recent_moves = list(RECENT_MOVES)
                    dup_policy = RUNTIME_CFG.get("duplicate_policy", "recycle")

                unpushed_count = sum(
                    1
                    for i in items
                    if i.get("git_info")
                    and (
                        not i["git_info"].get("has_remote")
                        or i["git_info"].get("unpushed_count", 0) > 0
                        or i["git_info"].get("dirty_count", 0) > 0
                    )
                )

                q_info = list_quarantine(ws_dir)
                stats = {
                    "total": len(items),
                    "git_repos": sum(1 for i in items if i["is_git"]),
                    "unpushed_repos": unpushed_count,
                    "categories": len({i["category"] for i in items}),
                    "favorites": sum(1 for i in items if i["is_favorite"]),
                    "quarantine_count": q_info["count"],
                    "quarantine_bytes": q_info["total_bytes"],
                    "workspace_ready": ws_dir.exists(),
                    "desktop_ready": dt_dir.exists(),
                    "organizer_enabled": enabled,
                    "duplicate_policy": dup_policy,
                    "recent_moves_count": len(recent_moves),
                }
                self._send_json(
                    200,
                    {
                        "items": items,
                        "stats": stats,
                        "category_order": CATEGORY_DISPLAY_ORDER,
                        "workspace_path": str(ws_dir),
                        "desktop_path": str(dt_dir),
                        "recent_moves": recent_moves,
                    },
                )
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                pass
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/duplicates":
            force_refresh = query.get("refresh", ["0"])[0] == "1"
            include_desktop = query.get("include_desktop", ["0"])[0] == "1"
            with STATE_LOCK:
                cached = DUPLICATES_CACHE
                ws_dir = Path(RUNTIME_CFG["workspace_dir"])
                dt_dir = Path(RUNTIME_CFG["desktop_dir"])

            if cached is None or force_refresh or include_desktop:
                report = analyze_workspace_redundancy(
                    ws_dir, desktop_dir=dt_dir, include_desktop=include_desktop
                )
                if not include_desktop:
                    with STATE_LOCK:
                        DUPLICATES_CACHE = report
            else:
                report = cached
            self._send_json(200, report)
            return

        if parsed.path == "/api/quarantine":
            self._send_json(200, list_quarantine(get_workspace_dir()))
            return

        if parsed.path == "/api/config":
            with STATE_LOCK:
                cfg_view = {
                    "workspace_dir": RUNTIME_CFG["workspace_dir"],
                    "desktop_dir": RUNTIME_CFG["desktop_dir"],
                    "enabled": bool(RUNTIME_CFG.get("enabled", False)),
                    "duplicate_policy": RUNTIME_CFG.get("duplicate_policy", "recycle"),
                    "min_age_seconds": int(RUNTIME_CFG.get("min_age_seconds", 20)),
                    "extra_scan_roots": RUNTIME_CFG.get("extra_scan_roots", []),
                }
            self._send_json(200, cfg_view)
            return

        if parsed.path == "/api/preview":
            raw_path = query.get("path", [""])[0]
            target_path = normalize_path(raw_path)
            p = Path(target_path) if target_path else None
            if not p or not p.exists():
                self._send_json(404, {"success": False, "error": f"Path not found: {raw_path}"})
                return
            if not is_within_preview_roots(p):
                self._send_json(403, {"success": False, "error": "Preview restricted to managed roots"})
                return
            self._send_json(200, {"success": True, **build_item_preview(p)})
            return

        if parsed.path == "/api/organizer-status":
            with STATE_LOCK:
                self._send_json(
                    200,
                    {
                        "enabled": bool(RUNTIME_CFG.get("enabled", False)),
                        "recent_moves": list(RECENT_MOVES),
                    },
                )
            return

        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            payload = json.loads(post_data)
        except Exception:
            payload = {}

        if parsed.path == "/api/open":
            action = payload.get("action", "explorer")
            raw_path = payload.get("path", "")
            target_path = normalize_path(raw_path)
            if not target_path or not os.path.exists(target_path):
                self._send_json(404, {"success": False, "error": f"Path not found: {raw_path}"})
                return

            try:
                if action == "explorer":
                    success, msg = open_in_explorer(target_path)
                elif action == "vscode":
                    success, msg = open_in_vscode(target_path)
                elif action == "terminal":
                    success, msg = open_in_terminal(target_path)
                elif action == "default":
                    os.startfile(target_path)
                    success, msg = True, "Opened default application"
                else:
                    success, msg = False, f"Unknown action: {action}"
            except Exception as e:
                success, msg = False, str(e)

            print(f"[ACTION] {action} -> {target_path} | success={success} | msg={msg}", flush=True)
            self._send_json(200 if success else 500, {"success": success, "message": msg})
            return

        if parsed.path == "/api/delete":
            raw_path = payload.get("path", "")
            target_path = normalize_path(raw_path)
            p = Path(target_path) if target_path else None
            if not p or not p.exists():
                self._send_json(404, {"success": False, "error": f"Path not found: {raw_path}"})
                return
            if not is_within_managed_roots(p):
                self._send_json(403, {"success": False, "error": "Refusing to delete path outside Workspace/Desktop"})
                return
            try:
                send_to_recycle_bin(str(p))
                log_organizer_action(f"DELETED (Recycle Bin): {p}")
                invalidate_caches()
                self._send_json(200, {"success": True, "message": "Moved to Windows Recycle Bin"})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if parsed.path == "/api/cleanup-duplicates":
            raw_paths = payload.get("paths", [])
            if not isinstance(raw_paths, list):
                self._send_json(400, {"success": False, "error": "paths must be a list"})
                return
            removed: list[str] = []
            errors: list[dict[str, str]] = []
            for raw_p in raw_paths:
                norm_p = normalize_path(str(raw_p))
                p = Path(norm_p) if norm_p else None
                if not p or not p.exists():
                    continue
                if not is_within_managed_roots(p):
                    errors.append({"path": norm_p, "error": "Outside managed roots"})
                    continue
                try:
                    send_to_recycle_bin(str(p))
                    log_organizer_action(f"CLEANUP DUPLICATE (Recycle Bin): {p}")
                    removed.append(str(p))
                except Exception as exc:
                    errors.append({"path": str(p), "error": str(exc)})
            invalidate_caches()
            self._send_json(
                200,
                {"success": len(errors) == 0, "removed_count": len(removed), "removed": removed, "errors": errors},
            )
            return

        if parsed.path == "/api/quarantine":
            raw_paths = payload.get("paths", [])
            reason = str(payload.get("reason", "Redundant copy"))
            if not isinstance(raw_paths, list):
                self._send_json(400, {"success": False, "error": "paths must be a list"})
                return
            valid_paths: list[Path] = []
            errors: list[dict[str, str]] = []
            for raw_p in raw_paths:
                norm_p = normalize_path(str(raw_p))
                p = Path(norm_p) if norm_p else None
                if not p or not p.exists():
                    continue
                if not is_within_managed_roots(p):
                    errors.append({"path": norm_p, "error": "Outside managed roots"})
                    continue
                valid_paths.append(p)
            res = quarantine_items(valid_paths, get_workspace_dir(), reason=reason)
            res["errors"].extend(errors)
            for m in res["moved"]:
                log_organizer_action(f"QUARANTINED: {m['original_path']} -> {m['quarantine_path']}")
            invalidate_caches()
            self._send_json(200, {"success": len(res["errors"]) == 0, **res})
            return

        if parsed.path == "/api/quarantine/restore":
            raw_paths = payload.get("paths", [])
            if not isinstance(raw_paths, list):
                self._send_json(400, {"success": False, "error": "paths must be a list"})
                return
            q_paths = [Path(normalize_path(str(p))) for p in raw_paths if str(p).strip()]
            res = restore_quarantine_items(q_paths, get_workspace_dir())
            for r in res["restored"]:
                log_organizer_action(f"RESTORED FROM QUARANTINE: {r}")
            invalidate_caches()
            self._send_json(200, {"success": len(res["errors"]) == 0, **res})
            return

        if parsed.path == "/api/quarantine/purge":
            raw_paths = payload.get("paths")
            q_paths = (
                [Path(normalize_path(str(p))) for p in raw_paths if str(p).strip()]
                if isinstance(raw_paths, list)
                else None
            )
            res = purge_quarantine(q_paths, get_workspace_dir(), send_to_recycle_bin)
            for r in res["removed"]:
                log_organizer_action(f"PURGED QUARANTINE (Recycle Bin): {r}")
            invalidate_caches()
            self._send_json(200, {"success": len(res["errors"]) == 0, **res})
            return

        if parsed.path == "/api/organize-desktop":
            dry_run = bool(payload.get("dry_run", False))
            moved = organize_desktop_pass(dry_run=dry_run, respect_age=False)
            self._send_json(
                200,
                {"success": True, "dry_run": dry_run, "moved_count": len(moved), "moved_items": moved},
            )
            return

        if parsed.path == "/api/toggle-organizer":
            with STATE_LOCK:
                RUNTIME_CFG["enabled"] = not bool(RUNTIME_CFG.get("enabled", False))
                save_config(ORGANIZER_CONFIG_FILE, RUNTIME_CFG)
                enabled = bool(RUNTIME_CFG["enabled"])
            self._send_json(200, {"success": True, "enabled": enabled})
            return

        if parsed.path == "/api/config":
            try:
                with STATE_LOCK:
                    if "workspace_dir" in payload and str(payload["workspace_dir"]).strip():
                        RUNTIME_CFG["workspace_dir"] = str(
                            Path(os.path.expandvars(str(payload["workspace_dir"]))).expanduser().resolve()
                        )
                    if "desktop_dir" in payload and str(payload["desktop_dir"]).strip():
                        RUNTIME_CFG["desktop_dir"] = str(
                            Path(os.path.expandvars(str(payload["desktop_dir"]))).expanduser().resolve()
                        )
                    if payload.get("duplicate_policy") in {"recycle", "skip", "rename"}:
                        RUNTIME_CFG["duplicate_policy"] = payload["duplicate_policy"]
                    if "min_age_seconds" in payload:
                        RUNTIME_CFG["min_age_seconds"] = max(0, int(payload["min_age_seconds"]))
                    if isinstance(payload.get("extra_scan_roots"), list):
                        RUNTIME_CFG["extra_scan_roots"] = payload["extra_scan_roots"]

                    created = ensure_workspace_structure(
                        Path(RUNTIME_CFG["workspace_dir"]), RUNTIME_CFG.get("categories")
                    )
                    save_config(ORGANIZER_CONFIG_FILE, RUNTIME_CFG)
                    invalidate_caches()
                    snapshot = {
                        "workspace_dir": RUNTIME_CFG["workspace_dir"],
                        "desktop_dir": RUNTIME_CFG["desktop_dir"],
                        "duplicate_policy": RUNTIME_CFG["duplicate_policy"],
                        "min_age_seconds": RUNTIME_CFG["min_age_seconds"],
                        "created_dirs": created,
                    }
                self._send_json(200, {"success": True, **snapshot})
            except Exception as e:
                self._send_json(400, {"success": False, "error": str(e)})
            return

        if parsed.path == "/api/init-workspace":
            with STATE_LOCK:
                created = ensure_workspace_structure(
                    Path(RUNTIME_CFG["workspace_dir"]), RUNTIME_CFG.get("categories")
                )
            self._send_json(200, {"success": True, "created": created})
            return

        if parsed.path == "/api/toggle-favorite":
            item_key = str(payload.get("path") or payload.get("name") or "").strip()
            item_name = str(payload.get("name") or "").strip()
            favs = load_favorites()
            if item_key in favs:
                favs.remove(item_key)
                if item_name and item_name in favs:
                    favs.remove(item_name)
                is_fav = False
            elif item_name and item_name in favs:
                favs.remove(item_name)
                is_fav = False
            else:
                if item_key:
                    favs.append(item_key)
                is_fav = True
            save_favorites(favs)
            invalidate_caches()
            self._send_json(200, {"success": True, "is_favorite": is_fav})
            return

        if parsed.path == "/api/shutdown":
            self._send_json(200, {"success": True, "message": "Workspace Navigator server shutting down"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self.send_response(404)
        self.end_headers()


def _warm_caches_background() -> None:
    global DUPLICATES_CACHE
    try:
        scan_items()
        with STATE_LOCK:
            if DUPLICATES_CACHE is not None:
                return
            ws_dir = Path(RUNTIME_CFG["workspace_dir"])
        report = analyze_workspace_redundancy(ws_dir)
        with STATE_LOCK:
            if DUPLICATES_CACHE is None:
                DUPLICATES_CACHE = report
    except Exception:
        pass


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    """Prevent multiple server instances from binding to the same port on Windows."""

    allow_reuse_address = False

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def run_server() -> None:
    with STATE_LOCK:
        ensure_workspace_structure(Path(RUNTIME_CFG["workspace_dir"]), RUNTIME_CFG.get("categories"))
        if not ORGANIZER_CONFIG_FILE.exists():
            save_config(ORGANIZER_CONFIG_FILE, RUNTIME_CFG)
        port = int(RUNTIME_CFG.get("port", 8585))

    try:
        httpd = ExclusiveThreadingHTTPServer(("127.0.0.1", port), NavigatorHandler)
    except OSError as e:
        print(f"Workspace Navigator Server could not bind to http://127.0.0.1:{port} ({e}).")
        return

    organizer_thread = threading.Thread(target=auto_organizer_worker, daemon=True)
    organizer_thread.start()
    threading.Timer(2.0, _warm_caches_background).start()
    print("⚡ Auto-Organizer background watcher active.")

    httpd.daemon_threads = True
    print(f"🚀 Workspace Navigator Server running at http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Workspace Navigator server and universal CLI.")
    parser.add_argument("--init", action="store_true", help="Initialize Workspace folders & config and exit.")
    parser.add_argument("--migrate-dry-run", action="store_true", help="Preview Desktop organization without moving.")
    parser.add_argument("--migrate-execute", action="store_true", help="Organize Desktop into Workspace now.")
    parser.add_argument("--scan-duplicates", action="store_true", help="Print redundant/duplicate report as JSON.")
    args = parser.parse_args()

    if args.init:
        created = ensure_workspace_structure(get_workspace_dir(), RUNTIME_CFG.get("categories"))
        save_config(ORGANIZER_CONFIG_FILE, RUNTIME_CFG)
        print(
            json.dumps(
                {
                    "workspace_dir": str(get_workspace_dir()),
                    "desktop_dir": str(get_desktop_dir()),
                    "created": created,
                },
                indent=2,
            )
        )
        return

    if args.migrate_dry_run or args.migrate_execute:
        items = organize_desktop_pass(dry_run=args.migrate_dry_run, respect_age=False)
        print(json.dumps({"dry_run": args.migrate_dry_run, "count": len(items), "items": items}, indent=2))
        return

    if args.scan_duplicates:
        report = analyze_workspace_redundancy(
            get_workspace_dir(), desktop_dir=get_desktop_dir(), include_desktop=True
        )
        print(json.dumps(report, indent=2))
        return

    run_server()


if __name__ == "__main__":
    main()
