from __future__ import annotations

from pathlib import Path


EXCLUDED_DIRS = {".git", ".madcli", "node_modules", "__pycache__", ".pytest_cache"}


def list_project_tree(root: Path, *, max_depth: int = 4) -> list[dict[str, object]]:
    resolved_root = root.resolve()
    items: list[dict[str, object]] = []
    _collect_tree(resolved_root, resolved_root, items, depth=0, max_depth=max_depth)
    return items


def read_project_file(root: Path, relative_path: str) -> str:
    resolved_root = root.resolve()
    target = (resolved_root / relative_path).resolve()
    if not _is_relative_to(target, resolved_root):
        raise ValueError(f"file is outside project root: {relative_path}")
    if not target.is_file():
        raise ValueError(f"file not found: {relative_path}")
    return target.read_text(encoding="utf-8")


def _collect_tree(
    root: Path,
    current: Path,
    items: list[dict[str, object]],
    *,
    depth: int,
    max_depth: int,
) -> None:
    if depth >= max_depth:
        return
    for child in sorted(current.iterdir(), key=lambda path: (path.is_file(), path.name.lower())):
        if child.is_dir() and child.name in EXCLUDED_DIRS:
            continue
        relative = child.relative_to(root).as_posix()
        items.append(
            {
                "path": relative,
                "name": child.name,
                "type": "directory" if child.is_dir() else "file",
            }
        )
        if child.is_dir():
            _collect_tree(root, child, items, depth=depth + 1, max_depth=max_depth)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
