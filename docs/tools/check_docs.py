#!/usr/bin/env python3
"""Validate the structure of docs/: append marker, IDs, links, tables, archive counts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
HANDBOOK = DOCS / "development-handbook.md"
ARCHIVE = DOCS / "archive"
INDEX = ARCHIVE / "INDEX.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_marker(text: str) -> str | None:
    last = next((line for line in reversed(text.splitlines()) if line.strip()), "")
    if "新开发日志追加点" not in last:
        return f"append marker is not the last non-empty line: {last!r}"
    return None


def check_dev_ids(text: str) -> str | None:
    ids = re.findall(r"^#### (DEV-\d{8}-\d{2}) \|", text, re.M)
    if not ids:
        return "no DEV entries"
    if len(ids) != len(set(ids)):
        return "duplicate DEV IDs in handbook"
    latest = re.search(r"\| 最新日志条目 \| `(DEV-\d{8}-\d{2})`", text)
    next_id = re.search(r"\| 下一条日志 ID \| `(DEV-\d{8}-\d{2})`", text)
    if latest is None or next_id is None:
        return "control table latest/next missing"
    if ids[-1] != latest.group(1):
        return f"last DEV {ids[-1]} != latest {latest.group(1)}"
    last_date, last_nn = latest.group(1)[4:12], int(latest.group(1)[-2:])
    next_date, next_nn = next_id.group(1)[4:12], int(next_id.group(1)[-2:])
    if next_date == last_date:
        if next_nn != last_nn + 1:
            return f"next DEV {next_id.group(1)} != {last_date}-{last_nn + 1:02d}"
    elif next_nn != 1:
        return f"cross-day next DEV should end with 01, got {next_id.group(1)}"
    return None


def check_toc_anchors(text: str) -> str | None:
    for anchor in ["handoff", *(f"sec-{index}" for index in range(11))]:
        if f'<a id="{anchor}"></a>' not in text:
            return f"missing TOC anchor {anchor}"
    if "[交接摘要](#handoff)" not in text:
        return "TOC handoff link missing"
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
        if anchor and f'<a id="{anchor}"></a>' not in read(target_path):
            relative = target_path.relative_to(ROOT)
            return f"{path.relative_to(ROOT)}: missing anchor #{anchor} in {relative}"
    return None


def check_archive_counts(handbook: str) -> str | None:
    expected = {"01": 5, "02": 8, "03": 3, "04": 7}
    actual = {}
    for part in sorted(ARCHIVE.glob("0[1-4]-*.md")):
        ids = re.findall(
            r'<a id="dev-\d{8}-\d{2}"></a>\n### (DEV-\d{8}-\d{2}) \|',
            read(part),
        )
        actual[part.name[:2]] = len(ids)
    if actual != expected:
        return f"archive counts {actual} != {expected}"

    index = read(INDEX)
    if "### 当前条目" not in index:
        return "INDEX.md missing current-entry section"
    archived_block, live_block = index.split("### 当前条目", 1)
    archived_rows = len(re.findall(r"^\| DEV-\d{8}-\d{2} \|", archived_block, re.M))
    live_rows = len(re.findall(r"^\| DEV-\d{8}-\d{2} \|", live_block, re.M))
    if archived_rows != 23:
        return f"INDEX archived rows {archived_rows} != 23"

    handbook_live = handbook.split("**当前条目（未归档，详情见 §10.3）**：", 1)[-1]
    handbook_live = handbook_live.split("### 10.3", 1)[0]
    handbook_live_rows = len(re.findall(r"^\| DEV-\d{8}-\d{2} \|", handbook_live, re.M))
    if live_rows != handbook_live_rows:
        return f"INDEX live rows {live_rows} != handbook live rows {handbook_live_rows}"
    return None


def main() -> int:
    handbook = read(HANDBOOK)
    errors: list[str] = []
    for check in (check_marker, check_dev_ids, check_toc_anchors):
        error = check(handbook)
        if error:
            errors.append(error)

    files = [
        DOCS / "README.md",
        HANDBOOK,
        ARCHIVE / "README.md",
        INDEX,
        *sorted(ARCHIVE.glob("*.md")),
    ]
    for path in files:
        text = read(path)
        for file_check in (check_markdown, check_links):
            error = file_check(path, text)
            if error:
                errors.append(error)

    error = check_archive_counts(handbook)
    if error:
        errors.append(error)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("docs structure: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
