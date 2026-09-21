"""furui — エラトステネスの篩。意味でフォルダを振るう整理の槍。

BUCKETS は furui の4つの篩目。TAXONOMY.md / SKILL.md と同期している。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

BUCKETS = ["agent", "skill", "project", "wiki"]

TAXONOMY = {
    # 型名: (jevの判定命題, 基準ディレクトリ名)
    "agent": (
        "an AI agent persona or character: a named entity with a role, "
        "responsibilities, and a personality definition",
        "agents",
    ),
    "skill": (
        "an AI agent skill, tool, plugin, MCP server, or CLI utility: "
        "a capability that does or operates something",
        "skills",
    ),
    "project": (
        "a software project, application, service, or website: "
        "a git repository, app, or deployable artifact",
        "projects",
    ),
    "wiki": (
        "knowledge, documentation, notes, records, plans, references, "
        "or any archive material",
        "wiki",
    ),
}

BUCKET_DIR = {b: t[1] for b, t in TAXONOMY.items()}

# 拡張子で即判定できる「明らかゴミ」
JUNK_EXT = {
    ".log": "log",
    ".bak": "backup",
    ".tmp": "temp",
    ".swp": "swap",
    ".pyc": "cache",
    ".pyo": "cache",
    ".DS_Store": "mac-metadata",
    ".exe": "executable",
    ".dll": "binary",
    ".db-wal": "db-cache",
    ".db-shm": "db-cache",
}


def load_manifest(path: Path | str) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        rel, desc = line.split("\t", 1)
        rows.append({"rel": rel, "desc": desc.strip()})
    return rows


def guess_junk(rel: str) -> str | None:
    """拡張子ベースのゴミ判定。当てれば理由文字列、外れれば None。"""
    name = rel.rsplit("/", 1)[-1]
    suffix = Path(name).suffix.lower()
    if suffix in JUNK_EXT:
        return JUNK_EXT[suffix]
    if re.fullmatch(r"[(\[]?(無題|untitled|new document)[-_)\] ]?\S*", name, re.IGNORECASE):
        return "untitled"
    if name.startswith(".~") or name.startswith("~$"):
        return "office-lock"
    if name.endswith(".txt") and re.match(r"^https?://", name):
        return "pasted-url"
    return None