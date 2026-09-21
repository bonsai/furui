"""manifest 生成: ディレクトリを走査して relpath+desc の2列を吐く。"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".ssh", ".aws", ".gnupg", "__pycache__", ".venv"}
SKIP_FILE = re.compile(
    r"(^\.env(\..*)?$|\.(pem|key|p12|pfx)$|^id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$)"
)
# Windows の「ブロックの由来」マーカー。見えたら二度と目録に載せない(URL化の温床)
ZONE_MARKER = ":Zone.Identifier"
MAX_BINARY_SCAN = 8192
MAX_DESC_CHARS = 240
MAX_DESC_LINES = 6


def _is_binary(buf: bytes) -> bool:
    return b"\x00" in buf[:MAX_BINARY_SCAN]


def _describe(root: Path, path: Path) -> str:
    """最初の数行から、jev が判定できる程度の desc を作る。

    ディレクトリは「README/SKILL 等の導入文」を最優先で使い、
    無ければ中身の一覧(最初の8要素)に頼る。CLI メインか・persona かといった
    分類シグネチャ(junk/agent/skill 篩)が dir 名だけでは見えないため。
    """
    if path.is_dir():
        probe = _probe_readme(path)
        if probe:
            return probe
        subs = [
            n for n in sorted(os.listdir(path) or []) if not n.startswith(".")
        ][:8]
        if subs:
            return "dir contains " + ", ".join(subs)
        return "empty dir"
    return _describe_file(path)


README_NAMES = [
    "README.md",
    "README",
    "README.ja.md",
    "GUIDE.md",
    "AGENTS.md",
    "SKILL.md",
]


def _probe_readme(path: Path) -> str | None:
    """ディレクトリ内の導入文(README/SKILL/GUIDE)を拾う。無ければ None。"""
    for name in README_NAMES:
        f = path / name
        if f.is_file():
            return _describe_file(f)
    f = path / "package.json"
    if f.is_file():
        try:
            import json

            meta = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        bits = []
        for key in ("name", "description"):
            v = (meta.get(key) or "").strip()
            if v:
                bits.append(v)
        return ("package.json: " + " | ".join(bits))[:MAX_DESC_CHARS] if bits else None
    return None


def _describe_file(path: Path) -> str:
    """ファイルの先頭数行から desc を作る(バイナリ/巨大判定込み)。"""
    if _is_binary(path.read_bytes()):
        return f"binary file, {path.stat().st_size} bytes"
    lines = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if not line.strip() or line.strip() == "---":
                    continue
                if line.startswith(("#", "//", "<!DOCTYPE", "<?xml")):
                    line = line.lstrip("#/ \t")
                lines.append(line.strip())
                if len(lines) >= MAX_DESC_LINES:
                    break
    except OSError:
        return "unreadable file"
    if not lines:
        return "empty file"
    return " | ".join(lines)[:MAX_DESC_CHARS]


def scan(root: Path, *, max_depth: int = 6) -> list[tuple[str, str]]:
    root = root.resolve()
    out: list[tuple[str, str]] = []

    def walk(path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: p.name)
        except OSError:
            return
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.name in SKIP_DIRS:
                continue
            if entry.is_file() and (SKIP_FILE.match(entry.name) or ZONE_MARKER in entry.name):
                continue
            rel = os.path.relpath(entry, root)
            if entry.is_dir():
                out.append((f"{rel}/", _describe(root, entry)))
                walk(entry, depth + 1)
            else:
                out.append((rel, _describe(root, entry)))

    walk(root, 0)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="furui manifest")
    ap.add_argument("dir")
    ap.add_argument("-o", "--out", default=None, help="output file (default stdout)")
    ap.add_argument("--max-depth", type=int, default=6)
    args = ap.parse_args()
    rows = scan(Path(args.dir), max_depth=args.max_depth)
    text = "\n".join(f"{rel}\t{desc}" for rel, desc in rows) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()