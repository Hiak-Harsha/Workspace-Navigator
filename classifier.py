"""Token-safe and content-aware classification for Workspace & Desktop items."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config_store import DEFAULT_CATEGORIES

IGNORED_FILE_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
TEMP_SUFFIXES = {".tmp", ".crdownload", ".part", ".partial"}
NUMBERED_COPY_RE = re.compile(r"^(?P<base>.+?)\s*\((?P<num>\d+)\)(?P<ext>\.[^.]+)?$")

CODE_MARKERS = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "manifest.json",
    "dockerfile",
    "docker-compose.yml",
}
STUDY_FILE_EXTS = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".xlsx", ".md"}
ML_CONTENT_HINTS = ("torch", "tensorflow", "scikit-learn", "sklearn", "transformers", "keras", "xgboost", "onnx")


def tokenize_name(name: str) -> set[str]:
    """Split filename/folder name into lowercase word tokens (camelCase & separator aware)."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return set(re.findall(r"[a-z0-9]+", spaced.lower()))


def matches_keywords(name_lower: str, tokens: set[str], keywords: list[str]) -> bool:
    """Match multi-word phrases cleanly and single keywords on word/token boundaries."""
    for kw in keywords:
        kw_l = kw.lower().strip()
        if not kw_l:
            continue
        if " " in kw_l or "-" in kw_l:
            norm_name = name_lower.replace("_", " ").replace("-", " ")
            if kw_l in name_lower or kw_l.replace("-", " ") in norm_name:
                return True
        elif kw_l in tokens:
            return True
    return False


def _inspect_folder_content_hint(folder_path: Path) -> str | None:
    """
    Inspect top-level / depth-1 files inside a folder so study folders aren't dumped into Development,
    and ML/networking folders are categorized accurately even when folder names are generic.
    """
    try:
        entries = list(folder_path.iterdir())
    except OSError:
        return None

    names_lower = {e.name.lower() for e in entries}
    if any(e.is_file() and e.suffix.lower() in {".pkt", ".pka", ".pkz"} for e in entries):
        return "05_Networking_Labs"

    has_code_marker = bool(names_lower & CODE_MARKERS) or (folder_path / ".git").exists() or (folder_path / "src").is_dir()
    if has_code_marker:
        # Check if requirements/pyproject points strongly to ML
        for req_name in ("requirements.txt", "pyproject.toml"):
            req = folder_path / req_name
            if req.is_file():
                try:
                    txt = req.read_text(encoding="utf-8", errors="ignore")[:4096].lower()
                    if any(h in txt for h in ML_CONTENT_HINTS):
                        return "02_AI_MachineLearning"
                except OSError:
                    pass
        if any(e.is_file() and e.suffix.lower() in {".ipynb", ".h5", ".onnx", ".pt", ".pkl"} for e in entries):
            return "02_AI_MachineLearning"
        return "03_Development_Projects"

    file_exts = [e.suffix.lower() for e in entries if e.is_file()]
    if file_exts and all(ext in STUDY_FILE_EXTS | {".txt", ".csv"} for ext in file_exts):
        if any(ext in {".pdf", ".pptx", ".ppt", ".docx", ".doc"} for ext in file_exts):
            return "04_Academics_Study"

    return None


def classify_desktop_item(
    item_path: Path,
    workspace_dir: Path,
    navigator_dir: Path | None = None,
    categories: dict[str, Any] | None = None,
) -> Path | None:
    """Deterministically classify a Desktop file or folder into Workspace using token-safe + content-aware rules."""
    cats = categories or DEFAULT_CATEGORIES
    name = item_path.name
    name_lower = name.lower()
    suffix = item_path.suffix.lower()

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

    tokens = tokenize_name(item_path.stem if item_path.is_file() else name)

    if item_path.is_dir():
        priority = [
            "01_Hackathons_SIH",
            "05_Networking_Labs",
            "02_AI_MachineLearning",
            "04_Academics_Study",
            "06_Career_Personal",
            "00_Archives_Storage",
        ]
        for cat_key in priority:
            meta = cats.get(cat_key)
            if meta and matches_keywords(name_lower, tokens, meta.get("dir_keywords", [])):
                return workspace_dir / cat_key / name

        # Content-aware fallback before defaulting to Development
        content_cat = _inspect_folder_content_hint(item_path)
        if content_cat and content_cat in cats:
            return workspace_dir / content_cat / name

        dev_meta = cats.get("03_Development_Projects")
        if dev_meta and matches_keywords(name_lower, tokens, dev_meta.get("dir_keywords", [])):
            return workspace_dir / "03_Development_Projects" / name

        for cat_key, meta in cats.items():
            if meta.get("is_default_dir_target"):
                return workspace_dir / cat_key / name
        return workspace_dir / "03_Development_Projects" / name

    # File classification
    net_meta = cats.get("05_Networking_Labs", {})
    if suffix in net_meta.get("file_extensions", [".pkt", ".pka", ".pkz"]):
        return workspace_dir / "05_Networking_Labs" / "PacketTracer_Files" / name

    ml_meta = cats.get("02_AI_MachineLearning", {})
    if suffix in ml_meta.get("file_extensions", []):
        return workspace_dir / "02_AI_MachineLearning" / "datasets" / name

    arch_meta = cats.get("00_Archives_Storage", {})
    if suffix in arch_meta.get("archive_extensions", [".zip", ".rar", ".7z", ".tar", ".gz"]):
        return workspace_dir / "00_Archives_Storage" / "Project_Backups" / name
    if suffix in arch_meta.get("installer_extensions", [".exe", ".msi"]):
        return workspace_dir / "00_Archives_Storage" / "Installers" / name

    career_meta = cats.get("06_Career_Personal", {})
    if matches_keywords(name_lower, tokens, ["resume", "cv"]):
        return workspace_dir / "06_Career_Personal" / "Resume" / name
    if suffix in career_meta.get("file_extensions", []) or matches_keywords(
        name_lower, tokens, career_meta.get("file_keywords", [])
    ):
        return workspace_dir / "06_Career_Personal" / "Personal_Docs" / name

    acad_meta = cats.get("04_Academics_Study", {})
    if suffix in acad_meta.get("file_extensions", []):
        return workspace_dir / "04_Academics_Study" / "Course_PDFs" / name

    return workspace_dir / "00_Archives_Storage" / "Project_Backups" / name


def get_unique_destination(dest_path: Path) -> Path:
    """Return a non-colliding path with (1), (2), ... suffix only when content genuinely differs."""
    if not dest_path.exists():
        return dest_path
    stem = dest_path.stem if dest_path.is_file() or dest_path.suffix else dest_path.name
    suffix = dest_path.suffix if dest_path.is_file() or dest_path.suffix else ""
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
