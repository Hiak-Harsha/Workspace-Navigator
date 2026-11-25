"""Local Ollama AI integration for dynamic folder sorting and semantic navigation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from config_store import DEFAULT_CATEGORIES

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:latest"


def _http_json(url: str, payload: dict[str, Any] | None = None, timeout: float = 8.0) -> dict[str, Any]:
    """Perform a lightweight stdlib HTTP JSON request to the local Ollama server."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}


def get_ollama_status(ollama_url: str = DEFAULT_OLLAMA_URL, model: str = DEFAULT_OLLAMA_MODEL) -> dict[str, Any]:
    """Check whether local Ollama is reachable and list installed models."""
    base = (ollama_url or DEFAULT_OLLAMA_URL).rstrip("/")
    try:
        data = _http_json(f"{base}/api/tags", timeout=2.0)
        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
        active = model if model in models else (models[0] if models else model)
        return {
            "available": True,
            "url": base,
            "active_model": active,
            "models": models,
        }
    except Exception as exc:
        return {
            "available": False,
            "url": base,
            "active_model": model,
            "models": [],
            "error": str(exc),
        }


def _ollama_generate_json(
    prompt: str,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_OLLAMA_MODEL,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Call Ollama /api/generate with JSON output mode."""
    base = (ollama_url or DEFAULT_OLLAMA_URL).rstrip("/")
    res = _http_json(
        f"{base}/api/generate",
        payload={
            "model": model or DEFAULT_OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 700},
        },
        timeout=timeout,
    )
    text = (res.get("response") or "").strip()
    if not text:
        return {}
    return json.loads(text)


def _describe_item_for_prompt(item_path: Path) -> str:
    """Summarize a folder or file (name + top-level file hints) without reading large binaries."""
    if item_path.is_file():
        return f"FILE name='{item_path.name}' ext='{item_path.suffix.lower()}'"

    hints: list[str] = []
    try:
        for child in sorted(item_path.iterdir(), key=lambda p: p.name.lower())[:12]:
            if child.name.startswith(".") and child.name != ".git":
                continue
            hints.append(f"{child.name}/" if child.is_dir() else child.name)
    except OSError:
        pass
    return f"DIR name='{item_path.name}' contents=[{', '.join(hints)}]"


def classify_with_ollama(
    item_path: Path,
    categories: dict[str, Any] | None = None,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_OLLAMA_MODEL,
    timeout: float = 6.0,
) -> dict[str, str] | None:
    """Classify a single ambiguous file or folder using local Ollama."""
    cats = categories or DEFAULT_CATEGORIES
    cat_lines = "\n".join(f"- {k}: {v.get('label', k)}" for k, v in cats.items())
    item_desc = _describe_item_for_prompt(item_path)
    prompt = (
        "You are a local workspace file organizer. Pick the single best category key for this item.\n"
        f"Categories:\n{cat_lines}\n\n"
        f"Item: {item_desc}\n\n"
        'Respond ONLY with JSON: {"category": "<exact_category_key>", "reason": "<short 1-sentence reason>"}'
    )
    try:
        parsed = _ollama_generate_json(prompt, ollama_url=ollama_url, model=model, timeout=timeout)
        cat = str(parsed.get("category", "")).strip()
        if cat in cats:
            return {"category": cat, "reason": str(parsed.get("reason", "")).strip()}
    except Exception:
        return None
    return None


def suggest_dynamic_sort(
    candidates: list[dict[str, Any]],
    categories: dict[str, Any] | None = None,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_OLLAMA_MODEL,
    timeout: float = 25.0,
) -> list[dict[str, Any]]:
    """
    Ask local Ollama to dynamically classify a batch of folders/files and explain each placement.
    Each candidate has: {name, path, current_category, description}.
    """
    if not candidates:
        return []
    cats = categories or DEFAULT_CATEGORIES
    cat_lines = "\n".join(f"- {k}: {v.get('label', k)}" for k, v in cats.items())

    suggestions: list[dict[str, Any]] = []
    # Process in chunks of 15 so prompts stay fast and accurate for small local models
    for idx in range(0, len(candidates), 15):
        chunk = candidates[idx : idx + 15]
        items_block = "\n".join(
            f"{i}. current={c['current_category']} | {c['description']}" for i, c in enumerate(chunk)
        )
        prompt = (
            "You are a precise workspace organizer. For each numbered item below, choose the best category key.\n"
            "Only suggest moving an item if another category clearly fits better than its current category.\n"
            f"Valid category keys:\n{cat_lines}\n\n"
            f"Items:\n{items_block}\n\n"
            'Respond ONLY with JSON: {"items": [{"index": 0, "category": "<exact_key>", "reason": "<brief reason>"}]}'
        )
        parsed = _ollama_generate_json(prompt, ollama_url=ollama_url, model=model, timeout=timeout)
        for entry in parsed.get("items", []):
            try:
                i = int(entry.get("index", -1))
                cat = str(entry.get("category", "")).strip()
                if 0 <= i < len(chunk) and cat in cats:
                    cand = chunk[i]
                    suggestions.append(
                        {
                            "name": cand["name"],
                            "path": cand["path"],
                            "current_category": cand["current_category"],
                            "suggested_category": cat,
                            "suggested_label": cats[cat].get("label", cat),
                            "suggested_icon": cats[cat].get("icon", "📁"),
                            "reason": str(entry.get("reason", "")).strip() or "Matched by local Ollama model",
                            "changed": cat != cand["current_category"],
                        }
                    )
            except (TypeError, ValueError):
                continue
    return suggestions


def semantic_search_with_ollama(
    query: str,
    items: list[dict[str, Any]],
    ollama_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_OLLAMA_MODEL,
    limit: int = 8,
    timeout: float = 12.0,
) -> list[dict[str, Any]]:
    """Use local Ollama to rank workspace projects/folders for a natural-language navigation query."""
    if not query.strip() or not items:
        return []

    compact = items[:90]
    catalog = "\n".join(
        f"{i}. {it.get('name')} [{it.get('category')}]" for i, it in enumerate(compact)
    )
    prompt = (
        f'User wants to navigate to: "{query.strip()}"\n'
        f"Pick up to {limit} best matching items from this workspace catalog:\n{catalog}\n\n"
        'Respond ONLY with JSON: {"matches": [{"index": 0, "reason": "<short reason>"}]}'
    )
    parsed = _ollama_generate_json(prompt, ollama_url=ollama_url, model=model, timeout=timeout)
    results: list[dict[str, Any]] = []
    seen: set[int] = set()
    for m in parsed.get("matches", []):
        try:
            i = int(m.get("index", -1))
            if 0 <= i < len(compact) and i not in seen:
                seen.add(i)
                results.append(
                    {
                        "item": compact[i],
                        "reason": str(m.get("reason", "")).strip() or "Semantic match",
                    }
                )
        except (TypeError, ValueError):
            continue
    return results[:limit]
