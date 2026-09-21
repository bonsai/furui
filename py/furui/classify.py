"""classify: マニフェストの各アイテムを 4タイプ(agent/skill/project/wiki) + junk に振るう。

実測済み(normal threshold)の設計:
  - 拡張子で決まる明らかゴミ(.log/.bak/.tmp/.exe/...)は Jev を呼ばず先に除外
  - それ以外は Jev に choice 質問(択一)で単一カテゴリを選ばせる
    (noul の同時判定は全カテゴリが高くなり差が出にくいため使わない)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .buckets import TAXONOMY, guess_junk, load_manifest
from . import jev as jevapi

LABELS = list(TAXONOMY.keys()) + ["junk"]

# choice 質問の criteria。answer は criteria の key で返ってくる。
CRITERIA = {
    "agent": TAXONOMY["agent"][0],
    "skill": TAXONOMY["skill"][0],
    "project": TAXONOMY["project"][0],
    "wiki": TAXONOMY["wiki"][0],
    "junk": (
        "a temporary or stray artifact: log file, backup, executable, cache, "
        "leftover, or otherwise disposable junk"
    ),
}


@dataclass
class Classified:
    rel: str
    desc: str
    bucket: str  # agent | skill | project | wiki | junk | ambiguous
    prob: float = 0.0
    confidence: float = 0.0
    probs: list[float] = field(default_factory=list)


def run(manifest: str, *, min_conf: float = 0.4) -> list[Classified]:
    rows = load_manifest(manifest)
    out: list[Classified] = []

    pending: list[tuple[int, str]] = []  # (row_index, label)
    for i, row in enumerate(rows):
        reason = guess_junk(row["rel"])
        if reason:
            out.append(Classified(row["rel"], row["desc"], "junk", 1.0, 1.0))
            continue
        pending.append((i, row["rel"] + " | " + row["desc"]))

    if pending:
        lines = [label for _, label in pending]
        results = jevapi.classify_lines(lines, CRITERIA)
        for (i, _), (choice, conf) in zip(pending, results):
            r = rows[i]
            bucket = choice if choice in LABELS else "ambiguous"
            if bucket != "ambiguous" and conf < min_conf:
                bucket = "ambiguous"
            out.append(Classified(r["rel"], r["desc"], bucket, conf, conf))

    # original order preserved
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="furui classify")
    ap.add_argument("manifest")
    ap.add_argument("--min-conf", type=float, default=0.4)
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    items = run(args.manifest, min_conf=args.min_conf)
    import json

    if args.out:
        Path(args.out).write_text(
            json.dumps([vars(c) for c in items], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    else:
        for c in items:
            print(f"{c.rel}\t{c.bucket}\t{c.confidence:.2f}")