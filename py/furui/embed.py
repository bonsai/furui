"""embed: ML 埋め込みで「近い意味のまとまり」を検出する。

Jev は1アイテム1カテゴリの択一に強い。embed は4タイプでは拾いきれない
「同じ主題の塊」(例: 全部 furui 関連ノート、全部 MEGA バックアップ)を
コサイン類似度でグルーピングする補助として使う。

バックエンド:
  1. ローカル LM Studio /v1/embeddings (http://127.0.0.1:1234)
  2. SQLite/sqlite3 等は不要。フォールバックは単語頻度ベクトル(純 python)

使い方:
  furui embed <manifest> --model <mm_model|local> --k 6
  -> 各アイテムに cluster id を付与
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

EMBED_ENDPOINT = "http://127.0.0.1:1234/v1/embeddings"


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_\u3040-\u30ff\u4e00-\u9fff]{2,}", text.lower())


class HashingEmbedder:
    """特許の丸儲けはしない。語の文字列ハッシュ袋で次元を作る簡易埋め込み。"""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _tokens(text):
            h = int(hashlib.blake2b(tok.encode(), digest_size=4).hexdigest(), 16)
            idx = h >> 8  # 上位 bit で次元 index を決める
            sign = 1.0 if (h & 0x80) else -1.0
            vec[idx % self.dim] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class LmsEmbedder:
    """LM Studio (OpenAI 互換) 埋め込み。応答不能なら HashingEmbedder に落ちる。"""

    def __init__(self, endpoint: str = EMBED_ENDPOINT, model: str = ""):
        self.endpoint = endpoint
        self.model = model
        self._fallback = HashingEmbedder()

    def embed_many(self, texts: list[str], *, timeout: float = 30.0) -> list[list[float]]:
        import urllib.error
        import urllib.request

        body = json.dumps({"model": self.model or "text-embedding", "input": texts}).encode()
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            data = raw.get("data") or raw
            return [d["embedding"] for d in data]
        except Exception:  # noqa: BLE001 - LM Studio が落ちてたら何でも hash に落とす
            return [self._fallback.embed(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) / (
        (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))) or 1.0
    )


def load_rows(manifest: str) -> list[dict]:
    from .buckets import load_manifest

    return load_manifest(manifest)


def cluster(
    rows: list[dict],
    k: int = 6,
    min_sim: float = 0.6,
) -> list[dict]:
    """テキスト類似度で簡単な凝集クラスタリング。rows に cluster を付けて返す。"""
    texts = [r["rel"] + " | " + r["desc"] for r in rows]
    embedder = LmsEmbedder()
    vecs = embedder.embed_many(texts)
    n = len(vecs)
    assignments: list[list[int]] = []  # 埋め込みでなく、cluster全体の代表との類似でassign
    labels: list[list[float]] = []
    for i in range(n):
        if not labels:
            labels.append(vecs[i])
            assignments.append([i])
            continue
        sims = [cosine(vecs[i], l) for l in labels]
        best = max(range(len(sims)), key=lambda m: sims[m])
        if sims[best] >= min_sim and len(assignments[best]) < k:
            assignments[best].append(i)
            # 代表ベクトルを更新
            cluster_vecs = [vecs[j] for j in assignments[best]]
            labels[best] = [sum(c[d] for c in cluster_vecs) / len(cluster_vecs) for d in range(len(cluster_vecs))]
        else:
            labels.append(vecs[i])
            assignments.append([i])
    for i, member_list in enumerate(assignments):
        for j in member_list:
            rows[j] = {**rows[j], **({"cluster": i} if rows[j].get("cluster") is None else {})}
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="furui embed")
    ap.add_argument("manifest")
    ap.add_argument("--backend", default="local", choices=["local"])
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--min-sim", type=float, default=0.6)
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    rows = load_rows(args.manifest)
    rows = cluster(rows, k=args.k, min_sim=args.min_sim)
    if args.out:
        Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        for r in rows:
            print(f"{r['rel']}\tcluster={r.get('cluster','-')}")


if __name__ == "__main__":
    main()