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
    # agent と skill は「誰であるか(persona)」vs「何をするか(capability)」で
    # 差が出るよう命題を書いている(実測で『役割/ツール』の緩い表現だと混同する)。
    "agent": (
        "an AI AGENT PERSONA or CHARACTER: a named entity (a 'who') with an "
        "identity, name, role, responsibilities, personality, or character "
        "definition — organized as a being, NOT as an operating tool",
        "agents",
    ),
    "skill": (
        "a reusable CAPABILITY, TOOL, or OPERATION: a skill, plugin, MCP "
        "server, CLI utility, script, command, or pipeline that does "
        "something — software that performs an action, NOT a named persona",
        "skills",
    ),
    "project": (
        "a standalone software PRODUCT, application, service, or website "
        "deliverable: a git repository that runs as a deployable artifact, "
        "not a persona and not a one-off utility script",
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
    if name.endswith(":Zone.Identifier"):
        return "windows-zone-marker"
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


# ---- エージェント篩(人名ならエージェント) --------------------------------
# 「人名(persona)ならエージェント」が実測のファーストルール。
# Jev を呼ぶ前に、名前/説明から persona が確定できるものを振るい落とす。
AGENT_NAME_TOKEN = re.compile(
    r"(^|[_\-/])(agent|coordinator|orchestrator|composer|advisor|advisors"
    r"|council|persona|director|designer|helper)([_\-/]|$)",
    re.IGNORECASE,
)
# 「役割を持つ人名」の説明パターン。役職/担当/ペルソナ語が名前に付く
PERSON_MARK = re.compile(
    r"(persona|personality definition|character definition|ペルソナ"
    r"|(役割|担当)を?[（( ]?(持つ|担う)|役職として)"
    r"|\b(role|responsibilities|name)\b.{0,40}\b(persona|identity|person)\b",
    re.IGNORECASE,
)


# ---- スキル篩(CLI メイン) --------------------------------
# 「CLI メインでスキルがくっついてくる」がセカンドルール。
# 名前/説明に CLI エントリ(コマンド・スクリプト・macro・MCP サーバ)が見えるものを振るう。
CLI_TOKEN = re.compile(
    r"(^|[_\-/])(cli|cmd|bin|scripts|macros|plugin|mcp|pipeline)([_\-/]|$)",
    re.IGNORECASE,
)
# 英単語は境界付きのみ(「cli クイズ」「tests/cli」等の誤爆を避ける)。
# 日本語は「ツール・マクロ・スクリプト集」の語列だけに絞る。
CLI_DESC_MARK = re.compile(
    r"\bCLI\b|\bcommand[- ]line\b|\bterminal\b|\bconsole\b"
    r"|コマンドライン(ツール|化)|コンソール|マクロ(集|群)|スクリプト集",
    re.IGNORECASE,
)


def guess_agent(rel: str, desc: str = "") -> str | None:
    """人名(persona)ならエージェント。当てれば理由文字列、外れれば None。

    - 名前が agent/coordinator/advisor/persona 等のペルソナ tokens を持つ
      (例: mito-coordinator, garden-agent, strategic-advisors)
    - 説明に「役割を持つ人名」の表現(役割/担当/ペルソナ)が見える
    Jev より先に走らせる。1.0 確定で返すので、誤検知を嫌って意図的に狭い。
    """
    name = rel.rstrip("/").rsplit("/", 1)[-1]
    if AGENT_NAME_TOKEN.search(name):
        return f"name is persona ({name})"
    if desc and PERSON_MARK.search(desc):
        return "desc defines a persona/role (person name)"
    return None


def guess_skill(rel: str, desc: str = "") -> str | None:
    """CLI メインならスキル。当てれば理由文字列、外れれば None。

    - 名前が cli/scripts/macro/plugin/mcp/pipeline 等の操作系 tokens を持つ
    - 説明に CLI/コマンドライン/ターミナル/マクロ集 の実体が見える
    エージェント篩と同じく、Jev より前に忠実に切れるものだけ。
    """
    name = rel.rstrip("/").rsplit("/", 1)[-1]
    if CLI_TOKEN.search(name):
        return f"name is CLI/tool ({name})"
    # 「dir contains ...」の一覧は単なる中身の列挙で、名前の一部に "cli" が
    # あっても CLI ツールの証拠にならない。README 等の文面だけを見る。
    if desc and not desc.startswith("dir contains") and CLI_DESC_MARK.search(desc):
        return "desc shows a CLI command/script"
    return None