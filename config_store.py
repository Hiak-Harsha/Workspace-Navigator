"""Universal path resolution, configuration store, and Workspace initialization."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Canonical category definitions in deliberate display order
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
            "registration",
            "ads",
            "fcs",
            "envs",
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
        "sub_collections": ["Project_Backups", "Installers", "Desktop_Old_Backup", "_Redundant_Quarantine"],
    },
}

CATEGORY_DISPLAY_ORDER = [
    "Hackathons & SIH",
    "AI & Machine Learning",
    "Development",
    "Academics & Study",
    "Networking Labs",
    "Career & Documents",
    "Home & Standalone Projects",
    "Open Source Forks",
    "Desktop Active",
    "Archives & Backups",
]

QUARANTINE_SUBDIR = "_Redundant_Quarantine"


def resolve_windows_desktop() -> Path:
    """Resolve the active Desktop folder, supporting OneDrive Known Folder redirection."""
    if os.name == "nt":
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


def default_extra_scan_roots(workspace_dir: Path, desktop_dir: Path) -> list[dict[str, str]]:
    """
    Universal external project roots so Navigator never misses repos outside Workspace
    (e.g. ~/open-source, ~/my-repo, Desktop projects).
    """
    home = Path.home().resolve()
    roots: list[dict[str, str]] = []

    open_source_dir = home / "open-source"
    if open_source_dir.is_dir():
        roots.append({"path": str(open_source_dir), "category": "Open Source Forks", "icon": "🌿", "mode": "all_dirs"})

    if desktop_dir.is_dir() and desktop_dir.resolve() != workspace_dir.resolve():
        roots.append({"path": str(desktop_dir.resolve()), "category": "Desktop Active", "icon": "🖥️", "mode": "projects_and_files"})

    # Home directory: include git repos and genuine project folders (e.g. package.json / pyproject.toml / manifest.json)
    roots.append({"path": str(home), "category": "Home & Standalone Projects", "icon": "🏠", "mode": "project_markers_only"})
    return roots


def get_quarantine_dir(workspace_dir: Path) -> Path:
    return workspace_dir / "00_Archives_Storage" / QUARANTINE_SUBDIR


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

    extra_roots = raw.get("extra_scan_roots")
    if not isinstance(extra_roots, list):
        extra_roots = default_extra_scan_roots(workspace_dir, desktop_dir)

    return {
        "enabled": bool(raw.get("enabled", False)),
        "port": int(raw.get("port", 8585)),
        "workspace_dir": str(workspace_dir),
        "desktop_dir": str(desktop_dir),
        "duplicate_policy": raw.get("duplicate_policy", "recycle"),
        "min_age_seconds": int(raw.get("min_age_seconds", 20)),
        "scan_nested_git_depth": int(raw.get("scan_nested_git_depth", 2)),
        "ollama_enabled": bool(raw.get("ollama_enabled", True)),
        "ollama_url": str(raw.get("ollama_url", "http://127.0.0.1:11434")),
        "ollama_model": str(raw.get("ollama_model", "llama3.2:latest")),
        "extra_scan_roots": extra_roots,
        "categories": raw.get("categories") or DEFAULT_CATEGORIES,
    }


def save_config(config_file: Path, cfg: dict[str, Any]) -> None:
    """Persist user-editable config keys cleanly."""
    payload: dict[str, Any] = {
        "enabled": bool(cfg.get("enabled", False)),
        "port": int(cfg.get("port", 8585)),
        "workspace_dir": str(cfg["workspace_dir"]),
        "desktop_dir": str(cfg["desktop_dir"]),
        "duplicate_policy": cfg.get("duplicate_policy", "recycle"),
        "min_age_seconds": int(cfg.get("min_age_seconds", 20)),
        "scan_nested_git_depth": int(cfg.get("scan_nested_git_depth", 2)),
        "ollama_enabled": bool(cfg.get("ollama_enabled", True)),
        "ollama_url": str(cfg.get("ollama_url", "http://127.0.0.1:11434")),
        "ollama_model": str(cfg.get("ollama_model", "llama3.2:latest")),
        "extra_scan_roots": cfg.get("extra_scan_roots", []),
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
