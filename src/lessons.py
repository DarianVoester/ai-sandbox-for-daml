"""Lektionen und Startercode verwalten."""
import shutil
from pathlib import Path

import settings


def list_lessons() -> list[str]:
    """Dateinamen aller Lektionen (curriculum/*.md), sortiert."""
    if not settings.CURRICULUM_DIR.exists():
        return []
    return sorted(p.name for p in settings.CURRICULUM_DIR.glob("*.md"))


def lesson_path(name: str) -> Path:
    return settings.CURRICULUM_DIR / name


def lesson_title(name: str) -> str:
    try:
        first = lesson_path(name).read_text(encoding="utf-8").splitlines()[0]
        return first.lstrip("# ").strip() or name
    except (OSError, IndexError):
        return name


def starter_for(name: str) -> Path | None:
    candidate = settings.STARTERS_DIR / f"{Path(name).stem}.daml"
    return candidate if candidate.exists() else None


def load_starter(name: str, target: Path | None = None) -> Path | None:
    """Kopiert den Startercode nach `target`. Gibt den Pfad der Sicherung zurück (falls es eine gab)."""
    target = target or settings.DAML_FILE
    starter = starter_for(name)
    if starter is None:
        raise FileNotFoundError(f"No starter code for lesson {name}.")
    backup = None
    if target.exists():
        backup = target.with_name(target.name + ".bak")
        shutil.copy2(target, backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(starter, target)
    return backup
