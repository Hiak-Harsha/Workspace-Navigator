"""Facade module re-exporting Navigator's modular core components."""

from classifier import (
    IGNORED_FILE_NAMES,
    NUMBERED_COPY_RE,
    TEMP_SUFFIXES,
    classify_desktop_item,
    get_unique_destination,
)
from config_store import (
    CATEGORY_DISPLAY_ORDER,
    DEFAULT_CATEGORIES,
    QUARANTINE_SUBDIR,
    default_extra_scan_roots,
    ensure_workspace_structure,
    get_quarantine_dir,
    load_config,
    resolve_default_workspace,
    resolve_windows_desktop,
    save_config,
)
from git_inspector import find_git_repos, get_git_summaries_parallel, get_git_summary
from ollama_ai import (
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
    classify_with_ollama,
    get_ollama_status,
    semantic_search_with_ollama,
    suggest_dynamic_sort,
)
from previewer import build_item_preview
from redundancy import (
    IGNORED_DIR_NAMES,
    analyze_workspace_redundancy,
    compare_folders,
    compute_file_sha256,
    compute_partial_signature,
    list_quarantine,
    purge_quarantine,
    quarantine_items,
    restore_quarantine_items,
)

__all__ = [
    "CATEGORY_DISPLAY_ORDER",
    "DEFAULT_CATEGORIES",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OLLAMA_URL",
    "IGNORED_DIR_NAMES",
    "IGNORED_FILE_NAMES",
    "NUMBERED_COPY_RE",
    "QUARANTINE_SUBDIR",
    "TEMP_SUFFIXES",
    "analyze_workspace_redundancy",
    "build_item_preview",
    "classify_desktop_item",
    "classify_with_ollama",
    "compare_folders",
    "compute_file_sha256",
    "compute_partial_signature",
    "default_extra_scan_roots",
    "ensure_workspace_structure",
    "find_git_repos",
    "get_git_summaries_parallel",
    "get_git_summary",
    "get_ollama_status",
    "get_quarantine_dir",
    "get_unique_destination",
    "list_quarantine",
    "load_config",
    "purge_quarantine",
    "quarantine_items",
    "resolve_default_workspace",
    "resolve_windows_desktop",
    "restore_quarantine_items",
    "save_config",
    "semantic_search_with_ollama",
    "suggest_dynamic_sort",
]
