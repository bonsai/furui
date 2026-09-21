"""rules — 熱力学木村モデル × furui の統合整理ルール。

三箇条（分ける・置く・登録する）+ 7禁忌(seiri-seiton/theory.md) と
furui の篩（agent/skill/project/wiki）を、木村モデルの温度相で
1つの決定表に束ねる。

  T(f) = exp(-Δdays/30)       温度（mtime）
  phase: vapor(T≥0.5) / liquid(0.2≤T<0.5) / solid(T<0.2)
  S    = 散らかり度（本モジュールでは判定のみ。測定は measure.py）

基本方針:
  - 篩の目（意味）と 温度（相）は直交する。
  - 温度は「動かすか・アーカイブか・触るな」の判断に使い、
    意味は「どこへ置くか」の判断に使う。
  - vapor（作業中）のものは余計な手出しをしない（原稿・にわかファイル）。
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import os

HALF_LIFE_DAYS = 30.0
SOLID_T = 0.2
VAPOR_T = 0.5

# 木村モデルの cache ディレクトリ（縮退状態。触るな）
CACHE_DIRS = {
    "node_modules", ".git", "venv", ".venv", "deps",
    "__pycache__", ".cache", ".next", "target", "dist", "build",
    ".takt", ".hermes", ".local", ".opencode", ".npm", ".config", ".git",
}


@dataclass
class Thermo:
    temp: float
    phase: str  # vapor | liquid | solid
    age_days: float

    @property
    def is_cache(self) -> bool:
        return False

    def __str__(self) -> str:
        return f"{self.phase}(T={self.temp:.2f})"


def file_temp(path: str) -> float:
    """mtime から温度 T = exp(-Δdays/30)。measure.py と同一基準。"""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return 0.0
    days = (dt.datetime.now() - dt.datetime.fromtimestamp(mtime)).total_seconds() / 86400.0
    return math_exp(-max(days, 0.0) / HALF_LIFE_DAYS)


def math_exp(x: float) -> float:
    import math

    return math.exp(x)


def phase_of(t: float) -> str:
    if t >= VAPOR_T:
        return "vapor"
    if t >= SOLID_T:
        return "liquid"
    return "solid"


def thermo_of(path: str) -> Thermo:
    temp = file_temp(path)
    return Thermo(temp=temp, phase=phase_of(temp), age_days=_age_days(path))


def _age_days(path: str) -> float:
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return 1e9
    return (dt.datetime.now() - dt.datetime.fromtimestamp(mtime)).total_seconds() / 86400.0


# ---------------------------------------------------------------------------
# 決定表（bucket x phase -> action）
# ---------------------------------------------------------------------------
# action: move=棚へ / trash=.trashへ / leave=触るな / archive=アーカイブ検討
# reason: ルールの理由（人が追えるように）

def decide(bucket: str, thermo: Thermo | None, *, already_home: bool = False) -> tuple[str, str]:
    """bucket（agent/skill/project/wiki/junk/ambiguous）× 相 -> (action, reason)。"""
    phase = thermo.phase if thermo else "liquid"
    temp = thermo.temp if thermo else 0.35

    # 1) ゴミは温度に関係なく.trashへ（三箇条の1: 分ける）
    if bucket == "junk":
        return "trash", "junk（拡張子/命題）→ .trash"

    # 2) 意味が確定しないものは動かさない（人に委ねる）
    if bucket == "ambiguous":
        if phase == "vapor":
            return "leave", "ambiguous + vapor（作業中: 手出し禁止）"
        if phase == "solid":
            return "review", "ambiguous + solid（冷えている: アーカイブ検討）"
        return "leave", "ambiguous（判定弱い: 動かさない）"

    # 3) 既に正しい棚にある（二重化防止）
    if already_home:
        return "leave", f"既に正しい棚内（{bucket}）"

    # 4) 意味が確定しているものは棚へ。相は扱いを決める
    if phase == "solid":
        return "move", f"{bucket} + solid（冷え: アーカイブ候補として棚へ）"
    if phase == "vapor":
        return "move", f"{bucket} + vapor（作業中: 棚へ出して整理）"
    return "move", f"{bucket} + liquid（棚へ）"


def bucket_dir(bucket: str) -> str:
    """bucket -> 標準ディレクトリ名（buckets.py と同期）。"""
    return {
        "agent": "agents",
        "skill": "skills",
        "project": "projects",
        "wiki": "wiki",
    }.get(bucket, bucket)


def is_cache_rel(rel: str) -> bool:
    parts = set(rel.replace(os.sep, "/").split("/"))
    return bool(parts & CACHE_DIRS)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="furui rules — 決定表デモ")
    ap.add_argument("path", nargs="?", help="temperature を測る実パス")
    args = ap.parse_args()
    print("木村モデル × furui 統合決定表")
    print("-" * 46)
    for bucket in ["agents", "skill", "project", "wiki", "junk", "ambiguous"]:
        for ph, t in [("vapor", 0.7), ("liquid", 0.35), ("solid", 0.1)]:
            action, reason = decide(bucket, Thermo(t, ph, 5.0))
            print(f"  {bucket:10} {ph:7} -> {action:8} {reason}")
    if args.path:
        b = args.path.lstrip("/")
        th = thermo_of(args.path)
        print(f"\n実測: {args.path}")
        print(f"  {th}（{th.age_days:.0f}日前 mtime）")