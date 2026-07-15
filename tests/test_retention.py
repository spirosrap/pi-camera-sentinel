import os

import pytest

from pi_camera_sentinel.retention import (
    RetentionPolicy,
    apply_retention,
    archive_files,
    plan_retention,
)


def archive_file(directory, name: str, *, size: int, modified_at: float):
    path = directory / name
    path.write_bytes(b"x" * size)
    os.utime(path, (modified_at, modified_at))
    return path


def test_retention_plans_age_count_and_size_in_order(tmp_path):
    now = 2_000_000.0
    newest = archive_file(tmp_path, "motion-new.jpg", size=6, modified_at=now - 10)
    second = archive_file(tmp_path, "motion-second.mp4", size=6, modified_at=now - 20)
    third = archive_file(tmp_path, "motion-third.png", size=1, modified_at=now - 30)
    count_limited = archive_file(tmp_path, "motion-fourth.jpeg", size=1, modified_at=now - 40)
    expired = archive_file(tmp_path, "motion-old.jpg", size=1, modified_at=now - 172_800)

    plan = plan_retention(
        tmp_path,
        RetentionPolicy(max_files=3, max_age_days=1, max_bytes=7),
        now=now,
    )

    assert [removal.file.path for removal in plan.removals] == [
        second,
        third,
        count_limited,
        expired,
    ]
    assert {removal.file.path: removal.reason for removal in plan.removals} == {
        second: "size",
        third: "size",
        count_limited: "count",
        expired: "age",
    }
    assert plan.kept_files == (plan.files[0],)
    assert plan.kept_files[0].path == newest
    assert plan.to_dict()["cleanup"]["reasons"] == {"age": 1, "count": 1, "size": 2}


def test_archive_scan_includes_capture_media_and_ignores_other_files(tmp_path):
    archive_file(tmp_path, "motion-photo.jpg", size=1, modified_at=100)
    archive_file(tmp_path, "motion-video.mp4", size=1, modified_at=200)
    archive_file(tmp_path, "motion-notes.txt", size=1, modified_at=300)
    archive_file(tmp_path, "unrelated.jpg", size=1, modified_at=400)

    assert [file.path.name for file in archive_files(tmp_path)] == [
        "motion-video.mp4",
        "motion-photo.jpg",
    ]


def test_retention_dry_run_reports_without_deleting(tmp_path):
    newest = archive_file(tmp_path, "motion-new.jpg", size=4, modified_at=200)
    oldest = archive_file(tmp_path, "motion-old.jpg", size=4, modified_at=100)
    plan = plan_retention(tmp_path, RetentionPolicy(max_files=1), now=300)

    preview = apply_retention(plan, dry_run=True)

    assert preview.to_dict()["candidates"] == [{"name": oldest.name, "reason": "count"}]
    assert preview.to_dict()["result"]["removed_files"] == 0
    assert newest.exists() and oldest.exists()

    result = apply_retention(plan)
    assert [removal.file.path for removal in result.removed] == [oldest]
    assert newest.exists() and not oldest.exists()


@pytest.mark.parametrize(
    "policy",
    [
        RetentionPolicy(max_files=0),
        RetentionPolicy(max_age_days=0),
        RetentionPolicy(max_bytes=0),
    ],
)
def test_zero_limits_are_valid_and_disabled(policy):
    assert policy.enabled is False


def test_negative_limit_is_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        RetentionPolicy(max_files=-1)
