"""Workspace Navigator HTTP Server, Desktop Auto-Organizer, and Universal CLI."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import shutil
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

from navigator_core import (
    DEFAULT_CATEGORIES,
    IGNORED_FILE_NAMES,
    TEMP_SUFFIXES,
    analyze_workspace_redundancy,
    build_item_preview,
    classify_desktop_item,
    compare_folders,
    compute_file_sha256,
    ensure_workspace_structure,
    find_git_repos,
    get_git_summaries_parallel,
    get_unique_destination,
    load_config,
    save_config,
)

STATE_LOCK = threading.RLock()
RUNTIME_CFG: dict[str, Any] = load_config(ORGANIZER_CONFIG_FILE, NAVIGATOR_DIR)
RECENT_MOVES: list[dict[str, Any]] = []
DUPLICATES_CACHE: dict[str, Any] | None = None
PROJECTS_CACHE: tuple[float, list[dict[str, Any]]] | None = None
PROJECTS_CACHE_TTL_SECONDS = 15.0

FAVICON_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    b'<rect width="64" height="64" rx="14" fill="#0d1322"/>'
    b'<path d="M36 10L16 36h14l-4 18 22-28H34l2-16z" fill="#38bdf8"/>'
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
    """Avoid sweeping freshly created folders or in-progress downloads."""
    if min_age_seconds <= 0:
        return True
    try:
        age = time.time() - item.stat().st_mtime
        return age >= min_age_seconds
    except OSError:
        return False


def _handle_duplicate_collision(
    src: Path, dest: Path, policy: str
) -> tuple[str, Path | None]:
    """
    Resolve name collisions consistently using content verification:
    - If identical (or folder subset): apply duplicate_policy ('recycle' | 'skip' | 'rename').
    - If content genuinely differs: return ('rename', unique_dest).
    """
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
    # Default safe universal policy: 'recycle' redundant exact duplicate
    return "recycle_duplicate", dest


def organize_desktop_pass(dry_run: bool = False, respect_age: bool = True) -> list[dict[str, Any]]:
    """Classify and move Desktop items into Workspace with SHA-256 duplicate protection."""
    global DUPLICATES_CACHE
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

        # Skip empty folders on Desktop without silently deleting them if user just created one
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

        # Verify file is not write-locked
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
        with STATE_LOCK:
            DUPLICATES_CACHE = None

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


def get_item_info(
    path: Path,
    category_name: str,
    category_icon: str,
    favorites_set: set[str],
    nested_git_depth: int = 2,
) -> tuple[dict[str, Any], Path | None]:
    is_dir = path.is_dir()
    git_repos = find_git_repos(path, max_depth=nested_git_depth) if is_dir else []
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
            "last_modified": mtime,
            "size_bytes": size_bytes,
            "is_favorite": is_fav,
            "extension": path.suffix.lower() if not is_dir else "folder",
        },
        primary_repo,
    )


def invalidate_caches() -> None:
    global DUPLICATES_CACHE, PROJECTS_CACHE
    with STATE_LOCK:
        DUPLICATES_CACHE = None
        PROJECTS_CACHE = None


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

    favorites = set(load_favorites())
    items: list[dict[str, Any]] = []
    repo_links: list[tuple[int, Path]] = []

    if not workspace_dir.exists():
        return items

    for folder_name, meta in categories.items():
        cat_dir = workspace_dir / folder_name
        if not cat_dir.is_dir():
            continue
        cat_name = meta.get("label", folder_name)
        cat_icon = meta.get("icon", "📁")
        sub_collections = {s.lower() for s in meta.get("sub_collections", [])}

        try:
            children = list(cat_dir.iterdir())
        except OSError:
            continue

        for child in children:
            if child.name.startswith("."):
                continue
            item_dict, primary_repo = get_item_info(child, cat_name, cat_icon, favorites, git_depth)
            idx = len(items)
            items.append(item_dict)
            if primary_repo is not None:
                repo_links.append((idx, primary_repo))

            if child.is_dir() and child.name.lower() in sub_collections:
                try:
                    for sub_file in child.iterdir():
                        if sub_file.name.startswith("."):
                            continue
                        sub_dict, sub_repo = get_item_info(sub_file, cat_name, cat_icon, favorites, git_depth)
                        sub_idx = len(items)
                        items.append(sub_dict)
                        if sub_repo is not None:
                            repo_links.append((sub_idx, sub_repo))
                except OSError:
                    continue

    if repo_links:
        summaries = get_git_summaries_parallel([repo for _, repo in repo_links])
        for idx, repo in repo_links:
            items[idx]["git_info"] = summaries.get(str(repo))

    items.sort(key=lambda x: (x["category"], x["name"].lower()))
    with STATE_LOCK:
        PROJECTS_CACHE = (time.time(), items)
    return items


def find_vscode_exe() -> str | None:
    """Find Visual Studio Code dynamically across standard Windows/user install locations."""
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


def focus_window_by_hwnd(hwnd: int) -> None:
    if os.name != "nt":
        return
    try:
        user32 = ctypes.windll.user32
        user32.SystemParametersInfoW(0x2001, 0, 0, 0x0002 | 0x0001)
        user32.keybd_event(0x12, 0, 0, 0)
        user32.ShowWindow(hwnd, 9)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(0x12, 0, 2, 0)
    except Exception:
        pass


def open_in_explorer(target_path: str) -> tuple[bool, str]:
    p = Path(target_path).resolve()
    if os.name != "nt":
        return False, "Explorer is only available on Windows"

    is_dir = p.is_dir()
    target_uri = p.as_uri()
    navigated = False

    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            shell = win32com.client.Dispatch("Shell.Application")
            for w in shell.Windows():
                try:
                    if hasattr(w, "HWND") and w.HWND:
                        w.Navigate(target_uri if is_dir else p.parent.as_uri())
                        focus_window_by_hwnd(w.HWND)
                        navigated = True
                        break
                except Exception:
                    pass
        finally:
            pythoncom.CoUninitialize()
    except Exception:
        pass

    if not navigated:
        if is_dir:
            subprocess.Popen(["explorer.exe", str(p)])
        else:
            subprocess.Popen(["explorer.exe", f"/select,{str(p)}"])
    return True, "Opened in File Explorer"


def open_in_vscode(target_path: str) -> tuple[bool, str]:
    code_exe = find_vscode_exe()
    if not code_exe:
        return False, "VS Code executable not found on system"

    target = str(Path(target_path).resolve())
    cwd = os.path.dirname(code_exe) or None
    flags = (0x00000008 | 0x00000200) if os.name == "nt" else 0
    subprocess.Popen([code_exe, target], cwd=cwd, creationflags=flags)
    return True, "Opened in VS Code"


def open_in_terminal(target_path: str) -> tuple[bool, str]:
    p = Path(target_path)
    target_dir = str(p if p.is_dir() else p.parent)
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200
        cmd = ["powershell.exe", "-NoExit", "-Command", f"Set-Location -LiteralPath '{target_dir}'"]
        subprocess.Popen(cmd, creationflags=flags)
        return True, "Opened in PowerShell Terminal"
    return False, "Terminal launcher requires Windows PowerShell"


class NavigatorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(NAVIGATOR_DIR), **kwargs)

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
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

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
                    and (not i["git_info"].get("has_remote") or i["git_info"].get("unpushed_count", 0) > 0)
                )

                stats = {
                    "total": len(items),
                    "git_repos": sum(1 for i in items if i["is_git"]),
                    "unpushed_repos": unpushed_count,
                    "categories": len({i["category"] for i in items}),
                    "favorites": sum(1 for i in items if i["is_favorite"]),
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
                        "workspace_path": str(ws_dir),
                        "desktop_path": str(dt_dir),
                        "recent_moves": recent_moves,
                    },
                )
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

        if parsed.path == "/api/config":
            with STATE_LOCK:
                cfg_view = {
                    "workspace_dir": RUNTIME_CFG["workspace_dir"],
                    "desktop_dir": RUNTIME_CFG["desktop_dir"],
                    "enabled": bool(RUNTIME_CFG.get("enabled", False)),
                    "duplicate_policy": RUNTIME_CFG.get("duplicate_policy", "recycle"),
                    "min_age_seconds": int(RUNTIME_CFG.get("min_age_seconds", 20)),
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
            if not is_within_managed_roots(p):
                self._send_json(403, {"success": False, "error": "Preview restricted to managed Workspace/Desktop items"})
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
        global DUPLICATES_CACHE
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
                {
                    "success": len(errors) == 0,
                    "removed_count": len(removed),
                    "removed": removed,
                    "errors": errors,
                },
            )
            return

        if parsed.path == "/api/organize-desktop":
            dry_run = bool(payload.get("dry_run", False))
            moved = organize_desktop_pass(dry_run=dry_run, respect_age=False)
            self._send_json(
                200,
                {
                    "success": True,
                    "dry_run": dry_run,
                    "moved_count": len(moved),
                    "moved_items": moved,
                },
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

                    created = ensure_workspace_structure(
                        Path(RUNTIME_CFG["workspace_dir"]), RUNTIME_CFG.get("categories")
                    )
                    save_config(ORGANIZER_CONFIG_FILE, RUNTIME_CFG)
                    DUPLICATES_CACHE = None
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
            self._send_json(200, {"success": True, "is_favorite": is_fav})
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


def run_server() -> None:
    with STATE_LOCK:
        ensure_workspace_structure(Path(RUNTIME_CFG["workspace_dir"]), RUNTIME_CFG.get("categories"))
        if not ORGANIZER_CONFIG_FILE.exists():
            save_config(ORGANIZER_CONFIG_FILE, RUNTIME_CFG)
        port = int(RUNTIME_CFG.get("port", 8585))

    organizer_thread = threading.Thread(target=auto_organizer_worker, daemon=True)
    organizer_thread.start()
    threading.Timer(2.0, _warm_caches_background).start()
    print("⚡ Auto-Organizer background watcher active.")

    httpd = ThreadingHTTPServer(("127.0.0.1", port), NavigatorHandler)
    httpd.daemon_threads = True
    print(f"🚀 Workspace Navigator Server running at http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
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
        print(json.dumps({"workspace_dir": str(get_workspace_dir()), "desktop_dir": str(get_desktop_dir()), "created": created}, indent=2))
        return

    if args.migrate_dry_run or args.migrate_execute:
        items = organize_desktop_pass(dry_run=args.migrate_dry_run, respect_age=False)
        print(json.dumps({"dry_run": args.migrate_dry_run, "count": len(items), "items": items}, indent=2))
        return

    if args.scan_duplicates:
        report = analyze_workspace_redundancy(get_workspace_dir(), desktop_dir=get_desktop_dir(), include_desktop=True)
        print(json.dumps(report, indent=2))
        return

    run_server()


if __name__ == "__main__":
    main()
