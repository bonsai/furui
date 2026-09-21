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
MAX_BINARY_SCAN = 8192
MAX_DESC_CHARS = 240
MAX_DESC_LINES = 6


def _is_binary(buf: bytes) -> bool:
    return b"\x00" in buf[:MAX_BINARY_SCAN]


def _describe(root: Path, path: Path) -> str:
    """最初の数行から、jev が判定できる程度の desc を作る。"""
    try:
        names = os.listdir(path) if path.is_dir() else []
    except OSError:
        names = []
    if path.is_dir():
        subs = [n for n in sorted(names) if not n.startswith(".")][:8]
        if subs:
            return "dir contains " + ", ".join(subs)
        return "empty dir"
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
            if entry.is_file() and SKIP_FILE.match(entry.name):
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