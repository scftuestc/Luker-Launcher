#!/usr/bin/env python3
"""Validate the two-class docs layout: handbook, devlog, archive, IDs, links, tables."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
HANDBOOK = DOCS / "handbook"
DEVLOG = DOCS / "devlog"
ARCHIVE = DEVLOG / "archive"
STATUS = DEVLOG / "STATUS.md"
CURRENT = DEVLOG / "current.md"
INDEX = DEVLOG / "INDEX.md"

REQUIRED = [
    DOCS / "README.md",
    HANDBOOK / "README.md",
    *[
        HANDBOOK / name
        for name in [
            "01-baseline.md",
            "02-architecture.md",
            "03-decisions.md",
            "04-components.md",
            "05-lessons.md",
            "06-testing.md",
            "07-reference.md",
        ]
    ],
    DEVLOG / "README.md",
    STATUS,
    CURRENT,
    INDEX,
    ARCHIVE / "README.md",
    ARCHIVE / "00-detailed-handbook-2026-11-14.md",
    ARCHIVE / "01-v1.0-v3.3.md",
    ARCHIVE / "02-v3.4-v4.0.md",
]

ARCHIVE_COUNTS = {
    "01-v1.0-v3.3.md": 13,
    "02-v3.4-v4.0.md": 10,
}
DEV_RE = r"DEV-\d{8}-\d{2}"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_layout() -> list[str]:
    errors = [
        f"missing required file: {path.relative_to(ROOT)}" for path in REQUIRED if not path.exists()
    ]
    for old in [DOCS / "development-handbook.md", DOCS / "archive"]:
        if old.exists():
            errors.append(f"legacy path still exists: {old.relative_to(ROOT)}")
    return errors


def check_marker(text: str) -> str | None:
    last = next((line for line in reversed(text.splitlines()) if line.strip()), "")
    if "新开发日志追加点" not in last:
        return f"current.md append marker is not the last non-empty line: {last!r}"
    return None


def check_control(current: str, status: str) -> str | None:
    ids = re.findall(rf"^#### ({DEV_RE}) \|", current, re.M)
    if not ids:
        return "current.md has no DEV entries"
    if len(ids) != len(set(ids)):
        return "duplicate DEV IDs in current.md"
    latest = re.search(rf"\| 最新日志条目 \| `({DEV_RE})` \|", status)
    next_id = re.search(rf"\| 下一条日志 ID \| `({DEV_RE})` \|", status)
    if latest is None or next_id is None:
        return "STATUS.md control table latest/next missing"
    if ids[-1] != latest.group(1):
        return f"last DEV {ids[-1]} != STATUS latest {latest.group(1)}"
    last_date, last_nn = latest.group(1)[4:12], int(latest.group(1)[-2:])
    next_date, next_nn = next_id.group(1)[4:12], int(next_id.group(1)[-2:])
    if next_date == last_date:
        expected = last_nn + 1
        if next_nn != expected:
            return f"next DEV {next_id.group(1)} != {last_date}-{expected:02d}"
    elif next_nn != 1:
        return f"cross-day next DEV should end with 01, got {next_id.group(1)}"
    return None


def index_sections(index: str) -> tuple[str, str]:
    if "### 当前条目" not in index:
        raise ValueError("INDEX.md missing current-entry section")
    archived, live = index.split("### 当前条目", 1)
    live = live.split("## 2.", 1)[0]
    return archived, live


def table_dev_ids(block: str) -> list[str]:
    return re.findall(rf"^\| ({DEV_RE}) \|", block, re.M)


def check_index(current: str, index: str) -> str | None:
    current_ids = re.findall(rf"^#### ({DEV_RE}) \|", current, re.M)
    try:
        archived_block, live_block = index_sections(index)
    except ValueError as exc:
        return str(exc)
    live_ids = table_dev_ids(live_block)
    if live_ids != current_ids:
        return f"INDEX current rows {live_ids} != current.md {current_ids}"
    archived_ids = table_dev_ids(archived_block)
    if len(archived_ids) != 23:
        return f"INDEX archived rows {len(archived_ids)} != 23"
    return None


def check_archive() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    all_ids: list[str] = []
    for name, expected in ARCHIVE_COUNTS.items():
        path = ARCHIVE / name
        if not path.exists():
            continue
        matches = re.findall(
            rf'<a id="(dev-\d{{8}}-\d{{2}})"></a>\n### ({DEV_RE}) \|',
            read(path),
        )
        anchors = [anchor for anchor, _ in matches]
        entries = [entry for _, entry in matches]
        if len(entries) != expected:
            errors.append(f"{name}: {len(entries)} entries != {expected}")
        if anchors != [entry.lower() for entry in entries]:
            errors.append(f"{name}: anchor/entry mismatch")
        if len(entries) != len(set(entries)):
            errors.append(f"{name}: duplicate DEV entries")
        all_ids.extend(entries)
    if len(all_ids) != len(set(all_ids)):
        errors.append("duplicate DEV IDs across archive volumes")
    return errors, all_ids


def check_archive_index(index: str, archive_ids: list[str]) -> str | None:
    try:
        archived_block, _ = index_sections(index)
    except ValueError as exc:
        return str(exc)
    if table_dev_ids(archived_block) != archive_ids:
        return "INDEX archived rows != archive volume anchors"
    return None


def check_markdown(path: Path, text: str) -> str | None:
    lines = text.splitlines()
    if sum(1 for line in lines if line.startswith("```")) % 2:
        return f"{path.relative_to(ROOT)}: unbalanced code fences"
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if not in_fence and line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            if len({row.count("|") for row in block}) != 1:
                return f"{path.relative_to(ROOT)}: table mismatch at {block[0]!r}"
        else:
            i += 1
    return None


def check_links(path: Path, text: str) -> str | None:
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        file_part, _, anchor = target.partition("#")
        target_path = path if not file_part else (path.parent / file_part).resolve()
        if not target_path.exists():
            return f"{path.relative_to(ROOT)}: missing file {target}"
        if anchor and f'id="{anchor}"' not in read(target_path):
            relative = target_path.relative_to(ROOT)
            return f"{path.relative_to(ROOT)}: missing anchor #{anchor} in {relative}"
    return None


def main() -> int:
    errors = check_layout()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    current = read(CURRENT)
    status = read(STATUS)
    index = read(INDEX)

    checks = [
        check_marker(current),
        check_control(current, status),
        check_index(current, index),
    ]
    errors.extend(check_error for check_error in checks if check_error)

    archive_errors, archive_ids = check_archive()
    errors.extend(archive_errors)
    archive_error = check_archive_index(index, archive_ids)
    if archive_error:
        errors.append(archive_error)

    for path in sorted(DOCS.rglob("*.md")):
        text = read(path)
        for file_check in (check_markdown, check_links):
            file_error = file_check(path, text)
            if file_error:
                errors.append(file_error)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("docs structure: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
