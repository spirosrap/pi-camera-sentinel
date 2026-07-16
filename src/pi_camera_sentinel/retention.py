from __future__ import annotations

import datetime as dt
import math
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Settings


ARCHIVE_SUFFIXES = {".jpeg", ".jpg", ".mp4", ".png"}


@dataclass(frozen=True)
class ArchiveFile:
    path: Path
    modified_at: float
    size_bytes: int


@dataclass(frozen=True)
class RetentionPolicy:
    max_files: int = 0
    max_age_days: float = 0
    max_bytes: int = 0

    def __post_init__(self) -> None:
        if self.max_files < 0:
            raise ValueError("retention file limit cannot be negative")
        if not math.isfinite(self.max_age_days) or self.max_age_days < 0:
            raise ValueError("retention age limit must be a non-negative number")
        if self.max_bytes < 0:
            raise ValueError("retention byte limit cannot be negative")

    @property
    def enabled(self) -> bool:
        return self.max_files > 0 or self.max_age_days > 0 or self.max_bytes > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "max_files": self.max_files,
            "max_age_days": self.max_age_days,
            "max_bytes": self.max_bytes,
        }


@dataclass(frozen=True)
class ArchiveRemoval:
    file: ArchiveFile
    reason: str


@dataclass(frozen=True)
class RetentionPlan:
    policy: RetentionPolicy
    files: tuple[ArchiveFile, ...]
    removals: tuple[ArchiveRemoval, ...]

    @property
    def kept_files(self) -> tuple[ArchiveFile, ...]:
        removed = {removal.file.path for removal in self.removals}
        return tuple(file for file in self.files if file.path not in removed)

    def to_dict(self, *, include_candidates: bool = False) -> dict[str, object]:
        kept = self.kept_files
        reason_counts = {
            reason: sum(1 for removal in self.removals if removal.reason == reason)
            for reason in ("age", "count", "size")
        }
        reason_counts = {reason: count for reason, count in reason_counts.items() if count}
        payload: dict[str, object] = {
            "policy": self.policy.to_dict(),
            "archive": {
                "file_count": len(self.files),
                "size_bytes": sum(file.size_bytes for file in self.files),
                "oldest_at": _file_time(self.files[-1]) if self.files else None,
            },
            "cleanup": {
                "pending": bool(self.removals),
                "file_count": len(self.removals),
                "size_bytes": sum(removal.file.size_bytes for removal in self.removals),
                "reasons": reason_counts,
            },
            "projected_archive": {
                "file_count": len(kept),
                "size_bytes": sum(file.size_bytes for file in kept),
                "oldest_at": _file_time(kept[-1]) if kept else None,
            },
        }
        if include_candidates:
            payload["candidates"] = [
                {"name": removal.file.path.name, "reason": removal.reason}
                for removal in self.removals
            ]
        return payload


@dataclass(frozen=True)
class RetentionResult:
    plan: RetentionPlan
    dry_run: bool
    removed: tuple[ArchiveRemoval, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = self.plan.to_dict(include_candidates=True)
        payload["result"] = {
            "dry_run": self.dry_run,
            "removed_files": len(self.removed),
            "removed_bytes": sum(removal.file.size_bytes for removal in self.removed),
            "errors": list(self.errors),
        }
        return payload


def _file_time(file: ArchiveFile) -> str:
    return dt.datetime.fromtimestamp(file.modified_at, dt.timezone.utc).isoformat()


def archive_files(directory: Path) -> tuple[ArchiveFile, ...]:
    if not directory.exists():
        return ()
    files: list[ArchiveFile] = []
    for path in directory.glob("motion-*"):
        if not path.is_file() or path.suffix.lower() not in ARCHIVE_SUFFIXES:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(ArchiveFile(path, stat.st_mtime, stat.st_size))
    return tuple(sorted(files, key=lambda file: (file.modified_at, file.path.name), reverse=True))


def policy_from_settings(settings: Settings) -> RetentionPolicy:
    return RetentionPolicy(
        max_files=settings.retention_files,
        max_age_days=settings.retention_days,
        max_bytes=settings.retention_mb * 1024 * 1024,
    )


def plan_retention(
    directory: Path,
    policy: RetentionPolicy,
    *,
    now: float | None = None,
    files: tuple[ArchiveFile, ...] | None = None,
) -> RetentionPlan:
    current_time = time.time() if now is None else now
    if not math.isfinite(current_time) or current_time <= 0:
        raise ValueError("retention timestamp must be positive")
    archive = archive_files(directory) if files is None else files
    removals: dict[Path, ArchiveRemoval] = {}

    if policy.max_age_days > 0:
        cutoff = current_time - (policy.max_age_days * 86400)
        for file in archive:
            if file.modified_at < cutoff:
                removals[file.path] = ArchiveRemoval(file, "age")

    remaining = [file for file in archive if file.path not in removals]
    if policy.max_files > 0:
        for file in remaining[policy.max_files :]:
            removals[file.path] = ArchiveRemoval(file, "count")

    remaining = [file for file in remaining if file.path not in removals]
    if policy.max_bytes > 0:
        retained_bytes = 0
        size_limit_reached = False
        for file in remaining:
            if size_limit_reached or retained_bytes + file.size_bytes > policy.max_bytes:
                size_limit_reached = True
                removals[file.path] = ArchiveRemoval(file, "size")
            else:
                retained_bytes += file.size_bytes

    ordered_removals = tuple(
        removals[file.path] for file in archive if file.path in removals
    )
    return RetentionPlan(policy, archive, ordered_removals)


def apply_retention(plan: RetentionPlan, *, dry_run: bool = False) -> RetentionResult:
    if dry_run:
        return RetentionResult(plan, True, (), ())
    removed: list[ArchiveRemoval] = []
    errors: list[str] = []
    for removal in plan.removals:
        try:
            removal.file.path.unlink()
        except OSError:
            errors.append(removal.file.path.name)
        else:
            removed.append(removal)
    return RetentionResult(plan, False, tuple(removed), tuple(errors))


def enforce_retention(
    directory: Path,
    policy: RetentionPolicy,
    *,
    dry_run: bool = False,
    now: float | None = None,
) -> RetentionResult:
    return apply_retention(plan_retention(directory, policy, now=now), dry_run=dry_run)
