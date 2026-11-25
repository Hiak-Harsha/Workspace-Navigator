"""Consistent duplicate/redundancy detection and one-place Quarantine Vault."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Callable

from classifier import IGNORED_FILE_NAMES, NUMBERED_COPY_RE, TEMP_SUFFIXES
from config_store import QUARANTINE_SUBDIR, get_quarantine_dir

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
    QUARANTINE_SUBDIR,
}

QUARANTINE_MANIFEST_NAME = "quarantine_manifest.json"


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
    sizes: dict[str, int] = {}
    if not folder_path.is_dir():
        return sizes
    for root, dirs, files in os.walk(folder_path):
        root_p = Path(root)
        if (root_p / "pyvenv.cfg").is_file() or (root_p / "conda-meta").is_dir():
            dirs[:] = []
            continue
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIR_NAMES)
        for fname in sorted(files):
            fname_l = fname.lower()
            if fname_l in IGNORED_FILE_NAMES or fname.startswith("~$"):
                continue
            fpath = root_p / fname
            if fpath.suffix.lower() in TEMP_SUFFIXES:
                continue
            try:
                rel = fpath.relative_to(folder_path).as_posix()
                sizes[rel] = fpath.stat().st_size
            except OSError:
                continue
    return sizes


def compare_folders(src: Path, dest: Path) -> str:
    """Compare two folders fast (size-first): 'identical', 'src_subset_of_dest', or 'different'."""
    src_sizes = _iter_folder_sizes(src)
    dest_sizes = _iter_folder_sizes(dest)

    if not src_sizes and not dest_sizes:
        return "identical"
    if not src_sizes and dest_sizes:
        return "src_subset_of_dest"

    for rel, sz in src_sizes.items():
        if dest_sizes.get(rel) != sz:
            return "different"

    for rel in src_sizes:
        try:
            if compute_file_sha256(src / rel) != compute_file_sha256(dest / rel):
                return "different"
        except OSError:
            return "different"

    return "identical" if len(src_sizes) == len(dest_sizes) else "src_subset_of_dest"


def _dir_size_and_files(folder_path: Path) -> tuple[int, int]:
    total_size = 0
    total_files = 0
    for root, dirs, files in os.walk(folder_path):
        root_p = Path(root)
        if (root_p / "pyvenv.cfg").is_file() or (root_p / "conda-meta").is_dir():
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in IGNORED_DIR_NAMES]
        for fname in files:
            fp = root_p / fname
            try:
                total_size += fp.stat().st_size
                total_files += 1
            except OSError:
                pass
    return total_size, total_files


def _canonical_sort_key(path: Path, workspace_dir: Path) -> tuple[int, int, int, str]:
    """Prefer clean names without (N), outside 00_Archives_Storage, shorter paths."""
    in_archive = 1 if "00_Archives_Storage" in path.parts else 0
    is_numbered = 1 if NUMBERED_COPY_RE.match(path.name) else 0
    try:
        rel_depth = len(path.relative_to(workspace_dir).parts)
    except ValueError:
        rel_depth = len(path.parts)
    return (in_archive, is_numbered, rel_depth, path.name.lower())


def _enclosing_git_repo(path: Path, stop_at: Path) -> Path | None:
    """Return nearest ancestor folder containing .git before stop_at."""
    curr = path.parent
    while curr != stop_at and curr != curr.parent:
        if (curr / ".git").exists():
            return curr
        curr = curr.parent
    return None


def analyze_workspace_redundancy(
    workspace_dir: Path,
    desktop_dir: Path | None = None,
    include_desktop: bool = False,
) -> dict[str, Any]:
    """
    Consistently detect redundant files & folders across Workspace:
    - Separates safe redundant items (numbered collision copies, archive duplicates, cross-folder duplicates, junk)
      from intra-repo duplicates (files duplicated inside the same .git repository's test/run folders).
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
            if (root_path / "pyvenv.cfg").is_file() or (root_path / "conda-meta").is_dir():
                dirs[:] = []
                continue

            kept_dirs = []
            for d in sorted(dirs):
                if d in IGNORED_DIR_NAMES:
                    continue
                dpath = root_path / d
                if root_path.parent == workspace_dir and NUMBERED_COPY_RE.match(d):
                    numbered_folders.append(dpath)
                kept_dirs.append(d)
            dirs[:] = kept_dirs

            is_system_cat_dir = root_path == workspace_dir or root_path.parent == workspace_dir
            in_git_repo = _enclosing_git_repo(root_path, root_base) is not None
            if not dirs and not files and not is_system_cat_dir and not in_git_repo:
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
                    if (
                        fname_l not in {".gitkeep", "__init__.py", ".keep"}
                        and not fname_l.endswith((".db-wal", ".db-shm"))
                    ):
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

    duplicate_groups: list[dict[str, Any]] = []
    intra_repo_groups: list[dict[str, Any]] = []
    redundant_file_count = 0
    safe_redundant_file_count = 0
    reclaimable_map: dict[Path, int] = {}

    for (size, digest), group in by_size_hash.items():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda p: _canonical_sort_key(p, workspace_dir))
        keep = ordered[0]
        dups = ordered[1:]

        keep_repo = _enclosing_git_repo(keep, workspace_dir)
        safe_dups = []
        repo_dups = []
        for d in dups:
            dup_repo = _enclosing_git_repo(d, workspace_dir)
            # Only classify as intra-repo fixture if both keep & dup live inside the same active Git repo
            # and neither has a numbered "(N)" duplicate filename
            if keep_repo is not None and dup_repo == keep_repo and not NUMBERED_COPY_RE.match(d.name):
                repo_dups.append(d)
            else:
                safe_dups.append(d)

        redundant_file_count += len(dups)
        if safe_dups:
            for d in safe_dups:
                reclaimable_map[d] = size
            safe_redundant_file_count += len(safe_dups)
            duplicate_groups.append(
                {
                    "hash": digest[:12],
                    "size": size,
                    "keep": {"path": str(keep), "name": keep.name},
                    "duplicates": [
                        {"path": str(d), "name": d.name, "size": size, "reason": "Exact SHA-256 duplicate"}
                        for d in safe_dups
                    ],
                }
            )
        if repo_dups:
            intra_repo_groups.append(
                {
                    "hash": digest[:12],
                    "size": size,
                    "keep": {"path": str(keep), "name": keep.name},
                    "duplicates": [
                        {"path": str(d), "name": d.name, "size": size, "reason": "Same-repo file copy"}
                        for d in repo_dups
                    ],
                }
            )

    duplicate_groups.sort(key=lambda g: g["size"] * len(g["duplicates"]), reverse=True)
    intra_repo_groups.sort(key=lambda g: g["size"] * len(g["duplicates"]), reverse=True)

    # Check numbered collision folders (including sibling duplicates & .venv-only leftovers)
    folder_collisions: list[dict[str, Any]] = []
    safe_collision_roots: list[Path] = []
    seen_sibling_sigs: dict[tuple[str, tuple[tuple[str, int], ...]], Path] = {}

    for nf in sorted(numbered_folders, key=lambda p: _canonical_sort_key(p, workspace_dir)):
        m = NUMBERED_COPY_RE.match(nf.name)
        if not m:
            continue
        base_name = m.group("base").strip()
        base_candidate = nf.parent / base_name
        sz, fcount = _dir_size_and_files(nf)

        relation = "numbered_copy"
        if fcount == 0 and (nf / ".venv" / "pyvenv.cfg").is_file():
            relation = "venv_only_copy"
        elif base_candidate.is_dir():
            relation = compare_folders(nf, base_candidate)

        # Also catch identical numbered siblings like Foo (12) == Foo (13) == Foo (16) == Foo (17)
        if relation == "different":
            sizes_sig = tuple(sorted(_iter_folder_sizes(nf).items()))
            sib_key = (base_name.lower(), sizes_sig)
            if sib_key in seen_sibling_sigs:
                if compare_folders(nf, seen_sibling_sigs[sib_key]) == "identical":
                    relation = "duplicate_of_sibling"
            else:
                seen_sibling_sigs[sib_key] = nf

        safe = relation in {"identical", "src_subset_of_dest", "duplicate_of_sibling", "venv_only_copy"}
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

    reclaimable_bytes = sum(
        sz
        for p, sz in reclaimable_map.items()
        if not any(root in p.parents for root in safe_collision_roots)
    ) + sum(c["size"] for c in folder_collisions if c["safe_to_recycle"])

    return {
        "scanned_files": scanned_files,
        "duplicate_groups": duplicate_groups,
        "intra_repo_groups": intra_repo_groups,
        "redundant_file_count": safe_redundant_file_count,
        "total_duplicate_count": redundant_file_count,
        "folder_collisions": folder_collisions,
        "junk_items": junk_items,
        "reclaimable_bytes": reclaimable_bytes,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


# --- One-Place Quarantine Vault ---

def _load_quarantine_manifest(q_dir: Path) -> list[dict[str, Any]]:
    mf = q_dir / QUARANTINE_MANIFEST_NAME
    if not mf.exists():
        return []
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_quarantine_manifest(q_dir: Path, entries: list[dict[str, Any]]) -> None:
    q_dir.mkdir(parents=True, exist_ok=True)
    mf = q_dir / QUARANTINE_MANIFEST_NAME
    mf.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _unique_quarantine_dest(q_dir: Path, name: str) -> Path:
    dest = q_dir / name
    if not dest.exists():
        return dest
    p = Path(name)
    stem = p.stem if p.suffix else p.name
    suffix = p.suffix if p.suffix else ""
    counter = 1
    while True:
        cand = q_dir / (f"{stem} ({counter}){suffix}" if suffix else f"{stem} ({counter})")
        if not cand.exists():
            return cand
        counter += 1


def quarantine_items(
    paths: list[Path],
    workspace_dir: Path,
    reason: str = "Redundant copy",
) -> dict[str, Any]:
    """Consolidate selected redundant files/folders into one Quarantine directory with a restore manifest."""
    q_dir = get_quarantine_dir(workspace_dir)
    q_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_quarantine_manifest(q_dir)

    moved: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for src in paths:
        try:
            src_resolved = src.resolve()
            if not src_resolved.exists():
                continue
            if q_dir.resolve() in src_resolved.parents or src_resolved == q_dir.resolve():
                continue
            dest = _unique_quarantine_dest(q_dir, src_resolved.name)
            sz = _dir_size_and_files(src_resolved)[0] if src_resolved.is_dir() else src_resolved.stat().st_size
            shutil.move(str(src_resolved), str(dest))
            rec = {
                "name": src_resolved.name,
                "original_path": str(src_resolved),
                "quarantine_path": str(dest.resolve()),
                "is_dir": dest.is_dir(),
                "size": sz,
                "reason": reason,
                "quarantined_at": datetime.now().isoformat(timespec="seconds"),
            }
            manifest.append(rec)
            moved.append(rec)
        except Exception as exc:
            errors.append({"path": str(src), "error": str(exc)})

    _save_quarantine_manifest(q_dir, manifest)
    return {
        "quarantine_dir": str(q_dir),
        "moved_count": len(moved),
        "moved": moved,
        "errors": errors,
    }


def list_quarantine(workspace_dir: Path) -> dict[str, Any]:
    """Return all items currently staged in the Quarantine Vault."""
    q_dir = get_quarantine_dir(workspace_dir)
    manifest = _load_quarantine_manifest(q_dir)
    live_entries: list[dict[str, Any]] = []
    tracked_paths: set[str] = set()

    for entry in manifest:
        qp = Path(entry.get("quarantine_path", ""))
        if qp.exists():
            live_entries.append(entry)
            tracked_paths.add(str(qp.resolve()))

    # Include any manually placed items in Quarantine folder
    if q_dir.is_dir():
        for child in sorted(q_dir.iterdir(), key=lambda p: p.name.lower()):
            if child.name == QUARANTINE_MANIFEST_NAME:
                continue
            res_str = str(child.resolve())
            if res_str not in tracked_paths:
                sz = _dir_size_and_files(child)[0] if child.is_dir() else child.stat().st_size
                live_entries.append(
                    {
                        "name": child.name,
                        "original_path": None,
                        "quarantine_path": res_str,
                        "is_dir": child.is_dir(),
                        "size": sz,
                        "reason": "Staged in Quarantine",
                        "quarantined_at": "",
                    }
                )

    if len(live_entries) != len(manifest):
        _save_quarantine_manifest(q_dir, [e for e in live_entries if e.get("original_path")])

    total_bytes = sum(int(e.get("size", 0)) for e in live_entries)
    return {
        "quarantine_dir": str(q_dir),
        "count": len(live_entries),
        "total_bytes": total_bytes,
        "items": live_entries,
    }


def restore_quarantine_items(quarantine_paths: list[Path], workspace_dir: Path) -> dict[str, Any]:
    """Restore quarantined items back to their recorded original paths."""
    q_dir = get_quarantine_dir(workspace_dir)
    manifest = _load_quarantine_manifest(q_dir)
    by_qpath = {str(Path(e["quarantine_path"]).resolve()): e for e in manifest if e.get("quarantine_path")}

    restored: list[str] = []
    errors: list[dict[str, str]] = []

    for qp in quarantine_paths:
        qp_res = qp.resolve()
        key = str(qp_res)
        rec = by_qpath.get(key)
        if not qp_res.exists() or not rec or not rec.get("original_path"):
            errors.append({"path": key, "error": "Missing original path metadata"})
            continue
        orig = Path(rec["original_path"])
        if orig.exists():
            errors.append({"path": key, "error": f"Destination already exists: {orig}"})
            continue
        try:
            orig.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(qp_res), str(orig))
            by_qpath.pop(key, None)
            restored.append(str(orig))
        except Exception as exc:
            errors.append({"path": key, "error": str(exc)})

    _save_quarantine_manifest(q_dir, list(by_qpath.values()))
    return {"restored_count": len(restored), "restored": restored, "errors": errors}


def purge_quarantine(
    quarantine_paths: list[Path] | None,
    workspace_dir: Path,
    recycler_fn: Callable[[str], bool],
) -> dict[str, Any]:
    """Remove selected (or all) items from Quarantine into the Windows Recycle Bin."""
    q_dir = get_quarantine_dir(workspace_dir)
    manifest = _load_quarantine_manifest(q_dir)
    current = list_quarantine(workspace_dir)

    targets = (
        [p.resolve() for p in quarantine_paths]
        if quarantine_paths is not None
        else [Path(item["quarantine_path"]).resolve() for item in current["items"]]
    )

    removed: list[str] = []
    errors: list[dict[str, str]] = []
    for t in targets:
        if not t.exists():
            continue
        if q_dir.resolve() not in t.parents:
            errors.append({"path": str(t), "error": "Not inside Quarantine Vault"})
            continue
        try:
            recycler_fn(str(t))
            removed.append(str(t))
        except Exception as exc:
            errors.append({"path": str(t), "error": str(exc)})

    removed_set = set(removed)
    remaining_manifest = [
        e for e in manifest if str(Path(e.get("quarantine_path", "")).resolve()) not in removed_set
    ]
    _save_quarantine_manifest(q_dir, remaining_manifest)
    return {"removed_count": len(removed), "removed": removed, "errors": errors}
