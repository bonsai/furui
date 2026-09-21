"""furui CLI — エラトステネスの篩。

  furui manifest <dir>                   走査して目録 (relpath<TAB>desc) を作る
  furui classify <manifest> [--out X]    Jev で 4タイプ+junk に振るう
  furui plan <classified> --root R       move プラン + エントロピー変化を出す
  furui apply <plan> --root R [--yes]    実際に移動する
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from . import manifest as manifest_mod
from . import classify as classify_mod
from . import plan as plan_mod
from . import embed as embed_mod
from . import rules as rules_mod


def _cmd_manifest(args) -> int:
    rows = manifest_mod.scan(Path(args.dir), max_depth=args.max_depth)
    text = "\n".join(f"{rel}\t{desc}" for rel, desc in rows) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    print(f"# {len(rows)} items", file=sys.stderr)
    return 0


def _cmd_classify(args) -> int:
    items = classify_mod.run(args.manifest, min_conf=args.min_conf)
    payload = [vars(c) for c in items]
    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    # サマリ
    from collections import Counter

    cnt = Counter(c["bucket"] for c in payload)
    print(
        "# " + " ".join(f"{k}={v}" for k, v in sorted(cnt.items())), file=sys.stderr
    )
    return 0


def _cmd_embed(args) -> int:
    rows = embed_mod.cluster(
        embed_mod.load_rows(args.manifest),
        args.k,
        args.min_sim,
    )
    if args.out:
        Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        for r in rows:
            print(f"{r['rel']}\tcluster={r.get('cluster','-')}")
    return 0


def _cmd_plan(args) -> int:
    raw = json.loads(Path(args.classified).read_text(encoding="utf-8"))
    items = [plan_mod.C(n) for n in raw]
    plan = plan_mod.from_classified(items, Path(args.root), trash=args.trash)
    text = plan_mod.render_cli(plan)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


def _cmd_rules(args) -> int:
    table = [
        (b, ph, t)
        for b in ["agents", "skill", "project", "wiki", "junk", "ambiguous"]
        for ph, t in [("vapor", 0.7), ("liquid", 0.35), ("solid", 0.1)]
    ]
    for bucket, ph, t in table:
        action, reason = rules_mod.decide(bucket, rules_mod.Thermo(t, ph, 5.0))
        print(f"{bucket:10} {ph:7} -> {action:8} {reason}")
    if args.path:
        th = rules_mod.thermo_of(args.path)
        print(f"\n{args.path}: {th} ({th.age_days:.0f}日 mtime)")
    return 0


def _cmd_apply(args) -> int:
    # apply は plan の出力(TSV)を食って実際に動かす
    root = Path(args.root).resolve()
    plan = Path(args.plan).read_text(encoding="utf-8")
    moves = []
    for line in plan.splitlines():
        if "\t->\t" not in line:
            continue
        src = line.split("\t->\t", 1)[0]
        rest = line.split("\t->\t", 1)[1]
        dst = rest.split("\t[")[0]
        moves.append((src, dst))
    if not args.yes:
        print(f"{len(moves)} moves (dry run). Re-run with --yes to move.")
        for src, dst in moves[: args.limit] or moves:
            print(f"  {src} -> {dst}")
        return 0
    log_path = Path(args.log)
    done = 0
    for src, dst in moves[: args.limit] or moves:
        s, d = root / src, root / dst
        if not s.exists() or s.is_symlink():
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.exists():
            continue
        shutil.move(str(s), str(d))
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{src}\t{dst}\n")
        done += 1
    print(f"moved {done} items (log: {log_path})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="furui", description=__doc__)
    ap.add_argument("--version", action="version", version=f"furui {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("manifest", help="走査して目録を作る")
    p.add_argument("dir")
    p.add_argument("-o", "--out")
    p.add_argument("--max-depth", type=int, default=6)
    p.set_defaults(func=_cmd_manifest)

    p = sub.add_parser("classify", help="Jev で4タイプ+junkに振るう")
    p.add_argument("manifest")
    p.add_argument("--min-conf", type=float, default=0.4)
    p.add_argument("-o", "--out")
    p.set_defaults(func=_cmd_classify)

    p = sub.add_parser("embed", help="ML埋め込みで近い塊(cluster)を付与")
    p.add_argument("manifest")
    p.add_argument("--k", type=int, default=6)
    p.add_argument("--min-sim", type=float, default=0.6)
    p.add_argument("-o", "--out")
    p.set_defaults(func=_cmd_embed)

    p = sub.add_parser("plan", help="移動プラン+エントロピー変化")
    p.add_argument("classified")
    p.add_argument("--root", required=True)
    p.add_argument("--trash", default=".trash")
    p.add_argument("-o", "--out")
    p.set_defaults(func=_cmd_plan)

    p = sub.add_parser("apply", help="プラン通りに移動")
    p.add_argument("plan")
    p.add_argument("--root", required=True)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--log", default="furui-move.log")
    p.set_defaults(func=_cmd_apply)

    p = sub.add_parser("rules", help="熱力学決定表デモ（bucket×相）")
    p.add_argument("path", nargs="?", help="相を測る実パス（省略で表のみ）")
    p.set_defaults(func=_cmd_rules)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())