"""plan: 分類結果 + 熱力学(相)から「どこへ動かすか」のプランを生成する。

  4タイプは TAXONOMY の標準ディレクトリ(agents/skills/projects/wiki)へ。
  junk は root/.trash/ へ。ambiguous は動かさない(人に任せる)。
  root 直下の type ディレクトリ自身は移動から除外する。

  熱力学木村モデル(rules.py)と統合:
    各 src の実パス mtime から温度相(vapor/liquid/solid)を出し、
    decide() の決定表で move/trash/leave/review を決める。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .buckets import BUCKET_DIR
from . import rules as rules_mod


class C:
    """dict を属性アクセス風に使う薄いラッパー。"""

    def __init__(self, d: dict):
        self.__dict__.update(d)

ROOT_TYPES = {d: True for d in BUCKET_DIR.values()}


@dataclass
class Move:
    src: str
    dst: str
    bucket: str
    prob: float
    reason: str = ""

    @property
    def action(self) -> str:
        """trash は .trash へ、他は move。rules との整合のため付ける。"""
        return "trash" if self.dst.startswith(".trash/") or "/.trash/" in self.dst else "move"


@dataclass
class Plan:
    moves: list[Move] = field(default_factory=list)
    stays: list[str] = field(default_factory=list)
    archives: list[str] = field(default_factory=list)

    @property
    def entropy_before(self) -> float:
        return _entropy(self._rel_paths())

    @property
    def entropy_after(self) -> float:
        # triggers は原始配置、dst はバケット/隠しディレクトリに集約後の配置
        return _entropy(self._final_paths())

    def _rel_paths(self) -> list[str]:
        # archives(→.trash) は moves と重複するため集計から外す
        return [m.src for m in self.moves] + self.stays

    def _final_paths(self) -> list[str]:
        finals = {m.src: m.dst for m in self.moves}
        return [finals.get(p, p) for p in self._rel_paths()]


def _entropy(paths: list[str]) -> float:
    """トップレベル分布のシャノン・エントロピー。1 = ばらばら、0 = 一点集中。"""
    from collections import Counter

    tops = Counter(p.split("/", 1)[0] for p in paths)
    total = sum(tops.values())
    if not total:
        return 0.0
    import math

    return -sum((c / total) * math.log2(c / total) for c in tops.values())


def from_classified(items, root: Path, *, trash: str = ".trash") -> Plan:
    root = Path(root).resolve()
    plan = Plan()
    seen = set()
    for c in items:
        rel = c.rel.rstrip("/")
        if rel in seen:
            continue
        seen.add(rel)
        if rel in ROOT_TYPES or rel.startswith("."):
            plan.stays.append(rel)
            continue
        if c.bucket == "ambiguous":
            plan.stays.append(rel)
            continue
        if c.bucket == "junk":
            plan.moves.append(Move(rel, f"{trash}/{rel}", "junk", c.prob, "junk (拡張子/命題)"))
            plan.archives.append(rel)
            continue
        # 実パスの相を測って rules に従う
        src_abs = root / rel
        thermo = rules_mod.thermo_of(str(src_abs)) if src_abs.exists() else rules_mod.Thermo(0.35, "liquid", 5.0)
        already_home = rel == BUCKET_DIR[c.bucket] or rel.startswith(BUCKET_DIR[c.bucket] + "/")
        action, reason = rules_mod.decide(c.bucket, thermo, already_home=already_home)
        if action in ("leave", "review"):
            plan.stays.append(rel)
            continue
        dst_dir = BUCKET_DIR[c.bucket]
        dst = dst_dir + "/" + rel
        plan.moves.append(Move(rel, dst, c.bucket, c.prob, f"{reason} [{thermo.phase}]"))
    return plan


def render_cli(plan: Plan) -> str:
    lines = []
    for m in plan.moves:
        tag = f"[{m.bucket} {m.prob:.2f}]"
        if m.reason:
            tag += f" {m.reason}"
        lines.append(f"{m.src}\t->\t{m.dst}\t{tag}")
    lines.append(f"[stays] {len(plan.stays)} items left in place")
    lines.append(f"[moves] {len(plan.moves)} items to move")
    lines.append(f"[archives->trash] {len(plan.archives)}")
    lines.append(
        f"[entropy] {plan.entropy_before:.3f} -> {plan.entropy_after:.3f}"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="furui plan")
    ap.add_argument("classified_json")
    ap.add_argument("--root", required=True)
    ap.add_argument("--trash", default=".trash")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    items = [type("C", (), vars(c)) for c in json.loads(Path(args.classified_json).read_text())]
    plan = from_classified(items, Path(args.root), trash=args.trash)
    text = render_cli(plan)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)