"""Universal Workspace Navigator core: path resolution, config, classification, and duplicate/redundancy engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

# Directories skipped during deep file hashing / redundancy scans
IGNORED_DIR_NAMES = {
    ".git",
    "node_modules",
    "bower_components",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    ".tox",
    ".nox",
    ".cache",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".turbo",
    ".expo",
    ".dart_tool",
    "dist",
    "build",
    "out",
    "coverage",
    "htmlcov",
    ".gradle",
    "target",
    "android-sdk",
    "site-packages",
    ".idea",
    ".vs",
}

IGNORED_FILE_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
TEMP_SUFFIXES = {".tmp", ".crdownload", ".part", ".partial"}
NUMBERED_COPY_RE = re.compile(r"^(?P<base>.+?)\s*\((?P<num>\d+)\)(?P<ext>\.[^.]+)?$")

DEFAULT_CATEGORIES: dict[str, dict[str, Any]] = {
    "01_Hackathons_SIH": {
        "label": "Hackathons & SIH",
        "icon": "🚀",
        "dir_keywords": ["sih", "hackathon", "hack", "submission", "ctf", "competition"],
        "sub_collections": [],
    },
    "02_AI_MachineLearning": {
        "label": "AI & Machine Learning",
        "icon": "🤖",
        "dir_keywords": [
            "ai",
            "ml",
            "machine-learning",
            "machine learning",
            "deep-learning",
            "deep learning",
            "neural",
            "nlp",
            "vision",
            "llm",
            "rag",
            "model",
            "detector",
            "dataset",
            "datasets",
            "agent",
        ],
        "file_extensions": [".csv", ".parquet", ".tsv", ".jsonl", ".arrow", ".h5", ".onnx", ".pt", ".pkl"],
        "sub_collections": ["datasets"],
    },
    "03_Development_Projects": {
        "label": "Development",
        "icon": "💻",
        "dir_keywords": ["app", "web", "api", "backend", "frontend", "cli", "extension", "bot", "server", "studio"],
        "sub_collections": [],
        "is_default_dir_target": True,
    },
    "04_Academics_Study": {
        "label": "Academics & Study",
        "icon": "📚",
        "dir_keywords": [
            "note",
            "notes",
            "study",
            "course",
            "courses",
            "exam",
            "assignment",
            "assignments",
            "presentation",
            "class",
            "lecture",
            "chapter",
            "unit",
            "academics",
            "economics",
            "syllabus",
            "materials",
            "lab",
            "labs",
        ],
        "file_extensions": [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md", ".xlsx", ".xls", ".html"],
        "sub_collections": ["Course_PDFs"],
    },
    "05_Networking_Labs": {
        "label": "Networking Labs",
        "icon": "🌐",
        "dir_keywords": ["packet", "cisco", "nat", "dhcp", "router", "switch", "tracer", "networking", "network"],
        "file_extensions": [".pkt", ".pka", ".pkz"],
        "sub_collections": ["PacketTracer_Files"],
    },
    "06_Career_Personal": {
        "label": "Career & Documents",
        "icon": "📄",
        "dir_keywords": ["resume", "cv", "career", "job", "portfolio", "interview", "personal", "docs"],
        "file_keywords": ["resume", "cv", "fee", "slip", "id", "passport", "certificate", "offer"],
        "file_extensions": [".jpeg", ".jpg", ".png", ".webp", ".heic"],
        "sub_collections": ["Resume", "Personal_Docs"],
    },
    "00_Archives_Storage": {
        "label": "Archives & Backups",
        "icon": "📦",
        "dir_keywords": ["archive", "archives", "backup", "backups", "installer", "installers"],
        "archive_extensions": [".zip", ".rar", ".7z", ".tar", ".gz", ".xz"],
        "installer_extensions": [".exe", ".msi", ".msix", ".appx"],
        "sub_collections": ["Project_Backups", "Installers", "Desktop_Old_Backup"],
    },
}


def resolve_windows_desktop() -> Path:
    """Resolve the active Desktop folder, supporting OneDrive Known Folder redirection."""
    if os.name == "nt":
        # 1) Registry User Shell Folders handles OneDrive Desktop redirection reliably
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                raw_val, _ = winreg.QueryValueEx(key, "Desktop")
                expanded = Path(os.path.expandvars(raw_val))
                if expanded.exists():
                    return expanded.resolve()
        except Exception:
            pass

        # 2) Fallback: SHGetFolderPathW(CSIDL_DESKTOPDIRECTORY = 0x0010)
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf) == 0 and buf.value:
                p = Path(buf.value)
                if p.exists():
                    return p.resolve()
        except Exception:
            pass

    home = Path.home()
    for candidate in (home / "Desktop", home / "OneDrive" / "Desktop"):
        if candidate.exists():
            return candidate.resolve()
    return (home / "Desktop").resolve()


def resolve_default_workspace(navigator_dir: Path) -> Path:
    """Infer Workspace root dynamically relative to Navigator or user home."""
    parent = navigator_dir.resolve().parent
    if parent.name.lower() == "workspace" or any((parent / cat).is_dir() for cat in DEFAULT_CATEGORIES):
        return parent
    return (Path.home() / "Workspace").resolve()


def load_config(config_file: Path, navigator_dir: Path) -> dict[str, Any]:
    """Load configuration with universal auto-detected defaults."""
    raw: dict[str, Any] = {}
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    raw = loaded
        except Exception:
            raw = {}

    desktop_cfg = raw.get("desktop_dir")
    workspace_cfg = raw.get("workspace_dir")

    desktop_dir = (
        Path(os.path.expandvars(desktop_cfg)).expanduser().resolve()
        if desktop_cfg
        else resolve_windows_desktop()
    )
    workspace_dir = (
        Path(os.path.expandvars(workspace_cfg)).expanduser().resolve()
        if workspace_cfg
        else resolve_default_workspace(navigator_dir)
    )

    return {
        "enabled": bool(raw.get("enabled", False)),
        "port": int(raw.get("port", 8585)),
        "workspace_dir": str(workspace_dir),
        "desktop_dir": str(desktop_dir),
        "duplicate_policy": raw.get("duplicate_policy", "recycle"),  # recycle | skip | rename
        "min_age_seconds": int(raw.get("min_age_seconds", 20)),
        "scan_nested_git_depth": int(raw.get("scan_nested_git_depth", 2)),
        "categories": raw.get("categories") or DEFAULT_CATEGORIES,
    }


def save_config(config_file: Path, cfg: dict[str, Any]) -> None:
    """Persist user-editable config keys cleanly."""
    payload = {
        "enabled": bool(cfg.get("enabled", False)),
        "port": int(cfg.get("port", 8585)),
        "workspace_dir": str(cfg["workspace_dir"]),
        "desktop_dir": str(cfg["desktop_dir"]),
        "duplicate_policy": cfg.get("duplicate_policy", "recycle"),
        "min_age_seconds": int(cfg.get("min_age_seconds", 20)),
        "scan_nested_git_depth": int(cfg.get("scan_nested_git_depth", 2)),
    }
    if cfg.get("categories") and cfg["categories"] != DEFAULT_CATEGORIES:
        payload["categories"] = cfg["categories"]
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def ensure_workspace_structure(workspace_dir: Path, categories: dict[str, Any] | None = None) -> list[str]:
    """Create standard Workspace category & sub-collection directories if missing."""
    cats = categories or DEFAULT_CATEGORIES
    created: list[str] = []
    workspace_dir.mkdir(parents=True, exist_ok=True)
    for folder_name, meta in cats.items():
        cat_path = workspace_dir / folder_name
        if not cat_path.exists():
            cat_path.mkdir(parents=True, exist_ok=True)
            created.append(str(cat_path))
        for sub in meta.get("sub_collections", []):
            sub_path = cat_path / sub
            if not sub_path.exists():
                sub_path.mkdir(parents=True, exist_ok=True)
                created.append(str(sub_path))
    return created


def _tokenize_name(name: str) -> set[str]:
    """Split filename/folder name into lowercase word tokens (camelCase & separator aware)."""
    # Split camelCase before normalizing separators
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    tokens = re.findall(r"[a-z0-9]+", spaced.lower())
    return set(tokens)


def _matches_keywords(name_lower: str, tokens: set[str], keywords: list[str]) -> bool:
    """Match multi-word phrases cleanly and single keywords on word/token boundaries."""
    for kw in keywords:
        kw_l = kw.lower().strip()
        if not kw_l:
            continue
        if " " in kw_l or "-" in kw_l:
            if kw_l in name_lower or kw_l.replace("-", " ") in name_lower.replace("_", " ").replace("-", " "):
                return True
        elif kw_l in tokens:
            return True
    return False


def classify_desktop_item(
    item_path: Path,
    workspace_dir: Path,
    navigator_dir: Path | None = None,
    categories: dict[str, Any] | None = None,
) -> Path | None:
    """Deterministically classify a Desktop file or folder into Workspace using token-safe rules."""
    cats = categories or DEFAULT_CATEGORIES
    name = item_path.name
    name_lower = name.lower()
    suffix = item_path.suffix.lower()

    # Never touch shortcuts, system/hidden/temp files, or Navigator itself
    if name.startswith(".") or name.startswith("~$"):
        return None
    if name_lower in IGNORED_FILE_NAMES:
        return None
    if suffix in {".lnk", ".url", ".ini"} or suffix in TEMP_SUFFIXES:
        return None
    if navigator_dir is not None:
        try:
            if item_path.resolve() == navigator_dir.resolve():
                return None
        except Exception:
            pass

    tokens = _tokenize_name(item_path.stem if item_path.is_file() else name)

    if item_path.is_dir():
        # Priority order prevents generic dev keywords from shadowing hackathons/academics/ML
        priority = [
            "01_Hackathons_SIH",
            "05_Networking_Labs",
            "02_AI_MachineLearning",
            "04_Academics_Study",
            "06_Career_Personal",
            "00_Archives_Storage",
            "03_Development_Projects",
        ]
        for cat_key in priority:
            meta = cats.get(cat_key)
            if not meta:
                continue
            if _matches_keywords(name_lower, tokens, meta.get("dir_keywords", [])):
                return workspace_dir / cat_key / name

        # Default folder bucket
        for cat_key, meta in cats.items():
            if meta.get("is_default_dir_target"):
                return workspace_dir / cat_key / name
        return workspace_dir / "03_Development_Projects" / name

    # File classification
    # 1. Networking packet tracer files
    net_meta = cats.get("05_Networking_Labs", {})
    if suffix in net_meta.get("file_extensions", [".pkt", ".pka", ".pkz"]):
        return workspace_dir / "05_Networking_Labs" / "PacketTracer_Files" / name

    # 2. Datasets
    ml_meta = cats.get("02_AI_MachineLearning", {})
    if suffix in ml_meta.get("file_extensions", []):
        return workspace_dir / "02_AI_MachineLearning" / "datasets" / name

    # 3. Archives & Installers
    arch_meta = cats.get("00_Archives_Storage", {})
    if suffix in arch_meta.get("archive_extensions", [".zip", ".rar", ".7z", ".tar", ".gz"]):
        return workspace_dir / "00_Archives_Storage" / "Project_Backups" / name
    if suffix in arch_meta.get("installer_extensions", [".exe", ".msi"]):
        return workspace_dir / "00_Archives_Storage" / "Installers" / name

    # 4. Career / Resumes / Personal Docs
    career_meta = cats.get("06_Career_Personal", {})
    if _matches_keywords(name_lower, tokens, ["resume", "cv"]):
        return workspace_dir / "06_Career_Personal" / "Resume" / name
    if suffix in career_meta.get("file_extensions", []) or _matches_keywords(
        name_lower, tokens, career_meta.get("file_keywords", [])
    ):
        return workspace_dir / "06_Career_Personal" / "Personal_Docs" / name

    # 5. Study documents
    acad_meta = cats.get("04_Academics_Study", {})
    if suffix in acad_meta.get("file_extensions", []):
        return workspace_dir / "04_Academics_Study" / "Course_PDFs" / name

    return workspace_dir / "00_Archives_Storage" / "Project_Backups" / name


def compute_file_sha256(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 digest of a file using buffered reads."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_partial_signature(file_path: Path, sample_bytes: int = 65536) -> tuple[int, bytes]:
    """Fast pre-hash signature: file size + head/mid/tail slices before full SHA-256."""
    size = file_path.stat().st_size
    if size <= sample_bytes * 3:
        return size, file_path.read_bytes()
    with open(file_path, "rb") as f:
        head = f.read(sample_bytes)
        f.seek(size // 2)
        mid = f.read(sample_bytes)
        f.seek(max(0, size - sample_bytes))
        tail = f.read(sample_bytes)
    return size, hashlib.sha256(head + mid + tail).digest()


def _iter_folder_sizes(folder_path: Path) -> dict[str, int]:
    """Collect {relative_posix_path: size} for meaningful files inside a folder without hashing."""
    sizes: dict[str, int] = {}
    if not folder_path.is_dir():
        return sizes
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIR_NAMES)
        root_path = Path(root)
        for fname in sorted(files):
            fname_l = fname.lower()
            if fname_l in IGNORED_FILE_NAMES or fname.startswith("~$"):
                continue
            fpath = root_path / fname
            if fpath.suffix.lower() in TEMP_SUFFIXES:
                continue
            try:
                rel = fpath.relative_to(folder_path).as_posix()
                sizes[rel] = fpath.stat().st_size
            except OSError:
                continue
    return sizes


def compute_folder_manifest(folder_path: Path) -> dict[str, tuple[int, str]]:
    """Return {relative_posix_path: (size, sha256)} for meaningful files inside a folder."""
    sizes = _iter_folder_sizes(folder_path)
    manifest: dict[str, tuple[int, str]] = {}
    for rel, sz in sizes.items():
        try:
            manifest[rel] = (sz, compute_file_sha256(folder_path / rel))
        except OSError:
            continue
    return manifest


def compare_folders(src: Path, dest: Path) -> str:
    """Compare two folders fast (size-first): 'identical', 'src_subset_of_dest', or 'different'."""
    src_sizes = _iter_folder_sizes(src)
    dest_sizes = _iter_folder_sizes(dest)

    if not src_sizes and not dest_sizes:
        return "identical"
    if not src_sizes and dest_sizes:
        return "src_subset_of_dest"

    # Fast reject: if any file in src is missing or has a different size in dest, cannot be identical or subset
    for rel, sz in src_sizes.items():
        if dest_sizes.get(rel) != sz:
            return "different"

    # Only hash files that exist in src (dest already matches on key + size)
    for rel in src_sizes:
        try:
            if compute_file_sha256(src / rel) != compute_file_sha256(dest / rel):
                return "different"
        except OSError:
            return "different"

    return "identical" if len(src_sizes) == len(dest_sizes) else "src_subset_of_dest"


def get_unique_destination(dest_path: Path) -> Path:
    """Return a non-colliding path with (1), (2), ... suffix only when content genuinely differs."""
    if not dest_path.exists():
        return dest_path
    stem = dest_path.stem if dest_path.is_file() or dest_path.suffix else dest_path.name
    suffix = dest_path.suffix if dest_path.is_file() or dest_path.suffix else ""
    # Strip any existing trailing " (N)" so we don't produce "foo (1) (1)"
    m = NUMBERED_COPY_RE.match(dest_path.name)
    if m:
        stem = m.group("base")
        suffix = m.group("ext") or ""
    parent = dest_path.parent
    counter = 1
    while True:
        new_name = f"{stem} ({counter}){suffix}" if suffix else f"{stem} ({counter})"
        candidate = parent / new_name
        if not candidate.exists():
            return candidate
        counter += 1


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
                if not entry.is_dir() or entry.name.startswith(".") or entry.name in IGNORED_DIR_NAMES:
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
    """Return lightweight git status (branch, remote, dirty, unpushed) fast and safely."""
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


def _canonical_sort_key(path: Path, workspace_dir: Path) -> tuple[int, int, int, str]:
    """Prefer clean names without (N), outside 00_Archives_Storage, shorter paths."""
    in_archive = 1 if "00_Archives_Storage" in path.parts else 0
    is_numbered = 1 if NUMBERED_COPY_RE.match(path.name) else 0
    try:
        rel_depth = len(path.relative_to(workspace_dir).parts)
    except ValueError:
        rel_depth = len(path.parts)
    return (in_archive, is_numbered, rel_depth, path.name.lower())


def _dir_size_and_files(folder_path: Path) -> tuple[int, int]:
    """Compute non-ignored size (bytes) and file count for a folder."""
    total_size = 0
    total_files = 0
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIR_NAMES]
        for fname in files:
            fp = Path(root) / fname
            try:
                total_size += fp.stat().st_size
                total_files += 1
            except OSError:
                pass
    return total_size, total_files


def analyze_workspace_redundancy(
    workspace_dir: Path,
    desktop_dir: Path | None = None,
    include_desktop: bool = False,
) -> dict[str, Any]:
    """
    Consistently detect redundant files & folders across Workspace:
    1. Exact duplicate files (size-bucketed + SHA-256, excluding vendor/build dirs).
    2. Numbered collision folders like 'Foo (1)'..'Foo (17)' (identical/subset/diverged).
    3. Junk/stale items (empty folders, 0-byte non-marker files, ~$ lockfiles, .tmp).
    """
    scan_roots: list[Path] = []
    if workspace_dir.is_dir():
        scan_roots.append(workspace_dir)
    if include_desktop and desktop_dir and desktop_dir.is_dir():
        scan_roots.append(desktop_dir)

    size_buckets: dict[int, list[Path]] = {}
    junk_items: list[dict[str, Any]] = []
    numbered_folders: list[Path] = []
    scanned_files = 0

    for root_base in scan_roots:
        for root, dirs, files in os.walk(root_base):
            root_path = Path(root)
            # Automatically skip any Python venv or Conda environment regardless of folder name
            if (root_path / "pyvenv.cfg").is_file() or (root_path / "conda-meta").is_dir():
                dirs[:] = []
                continue
            # Prune heavy vendor/env/vcs directories consistently
            kept_dirs = []
            for d in sorted(dirs):
                if d in IGNORED_DIR_NAMES:
                    continue
                dpath = root_path / d
                if root_path.parent == workspace_dir and NUMBERED_COPY_RE.match(d):
                    numbered_folders.append(dpath)
                kept_dirs.append(d)
            dirs[:] = kept_dirs

            # Flag empty directories (excluding top-level Workspace category/sub-collection dirs)
            is_system_cat_dir = root_path == workspace_dir or root_path.parent == workspace_dir
            if not dirs and not files and not is_system_cat_dir:
                # Don't flag intentional sub-collections
                if not (root_path.parent.parent == workspace_dir):
                    junk_items.append(
                        {
                            "path": str(root_path),
                            "name": root_path.name,
                            "reason": "Empty directory",
                            "size": 0,
                            "is_dir": True,
                        }
                    )

            for fname in files:
                fpath = root_path / fname
                fname_l = fname.lower()
                suffix_l = fpath.suffix.lower()

                if fname_l in IGNORED_FILE_NAMES:
                    continue
                if root_base == desktop_dir and suffix_l in {".lnk", ".url", ".ini"}:
                    continue

                if fname.startswith("~$") or suffix_l in TEMP_SUFFIXES:
                    try:
                        sz = fpath.stat().st_size
                    except OSError:
                        sz = 0
                    junk_items.append(
                        {
                            "path": str(fpath),
                            "name": fname,
                            "reason": "Temporary / lock artifact",
                            "size": sz,
                            "is_dir": False,
                        }
                    )
                    continue

                try:
                    st = fpath.stat()
                except OSError:
                    continue

                scanned_files += 1
                if st.st_size == 0:
                    if fname_l not in {".gitkeep", "__init__.py", ".keep"}:
                        junk_items.append(
                            {
                                "path": str(fpath),
                                "name": fname,
                                "reason": "Empty 0-byte file",
                                "size": 0,
                                "is_dir": False,
                            }
                        )
                    continue

                size_buckets.setdefault(st.st_size, []).append(fpath)

    # Fast parallel pre-filter + full SHA-256 confirmation for same-size candidates
    duplicate_groups: list[dict[str, Any]] = []
    redundant_file_count = 0
    reclaimable_map: dict[Path, int] = {}

    multi_candidates = [c for cands in size_buckets.values() if len(cands) >= 2 for c in cands]

    def _safe_partial(p: Path) -> tuple[Path, tuple[int, bytes] | None]:
        try:
            return p, compute_partial_signature(p)
        except OSError:
            return p, None

    by_size_partial: dict[tuple[int, bytes], list[Path]] = {}
    if multi_candidates:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for p, sig in pool.map(_safe_partial, multi_candidates):
                if sig is not None:
                    by_size_partial.setdefault(sig, []).append(p)

    full_hash_targets = [p for grp in by_size_partial.values() if len(grp) >= 2 for p in grp]

    def _safe_full_hash(p: Path) -> tuple[Path, int, str | None]:
        try:
            return p, p.stat().st_size, compute_file_sha256(p)
        except OSError:
            return p, 0, None

    by_size_hash: dict[tuple[int, str], list[Path]] = {}
    if full_hash_targets:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for p, sz, digest in pool.map(_safe_full_hash, full_hash_targets):
                if digest is not None:
                    by_size_hash.setdefault((sz, digest), []).append(p)

    for (size, digest), group in by_size_hash.items():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda p: _canonical_sort_key(p, workspace_dir))
        keep = ordered[0]
        dups = ordered[1:]
        for d in dups:
            reclaimable_map[d] = size
        redundant_file_count += len(dups)
        duplicate_groups.append(
            {
                "hash": digest[:12],
                "size": size,
                "keep": {"path": str(keep), "name": keep.name},
                "duplicates": [
                    {
                        "path": str(d),
                        "name": d.name,
                        "size": size,
                        "reason": "Exact SHA-256 duplicate",
                    }
                    for d in dups
                ],
            }
        )

    duplicate_groups.sort(key=lambda g: g["size"] * len(g["duplicates"]), reverse=True)

    # Check numbered collision folders (e.g., "Engineering Economics (1..17)")
    folder_collisions: list[dict[str, Any]] = []
    safe_collision_roots: list[Path] = []
    for nf in sorted(numbered_folders):
        m = NUMBERED_COPY_RE.match(nf.name)
        if not m:
            continue
        base_name = m.group("base").strip()
        base_candidate = nf.parent / base_name
        sz, fcount = _dir_size_and_files(nf)
        relation = "numbered_copy"
        if base_candidate.is_dir():
            relation = compare_folders(nf, base_candidate)
        safe = relation in {"identical", "src_subset_of_dest"}
        folder_collisions.append(
            {
                "path": str(nf),
                "name": nf.name,
                "base_path": str(base_candidate) if base_candidate.is_dir() else None,
                "relation": relation,
                "size": sz,
                "file_count": fcount,
                "safe_to_recycle": safe,
            }
        )
        if safe:
            safe_collision_roots.append(nf)

    # Avoid double-counting duplicate files already accounted for inside safe collision folders
    reclaimable_bytes = sum(
        sz
        for p, sz in reclaimable_map.items()
        if not any(root in p.parents for root in safe_collision_roots)
    ) + sum(c["size"] for c in folder_collisions if c["safe_to_recycle"])

    return {
        "scanned_files": scanned_files,
        "duplicate_groups": duplicate_groups,
        "redundant_file_count": redundant_file_count,
        "folder_collisions": folder_collisions,
        "junk_items": junk_items,
        "reclaimable_bytes": reclaimable_bytes,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


TEXT_PREVIEW_EXTS = {
    ".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".html", ".css", ".ps1", ".bat", ".sh", ".sql", ".csv",
}


def build_item_preview(target_path: Path, max_bytes: int = 8192) -> dict[str, Any]:
    """Build a safe, fast preview payload (folder entries + README or file snippet)."""
    resolved = target_path.resolve()
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
            for child in children[:60]:
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
            "entries": entries,
            "entry_count": len(entries),
            "readme_name": readme_name,
            "readme_text": readme_text,
            "git_info": git_info,
        }

    # File preview
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
        "extension": resolved.suffix.lower(),
        "size": size,
        "last_modified": mtime,
        "snippet": snippet,
        "truncated": truncated,
    }
