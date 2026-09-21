"""Jev (System One) 分類 API。プロバイダを zen / openrouter / typesafe から選ぶ。

furui は **OpenCode Zen を最優先**する。OpenRouter は zen が使えない(レート制限・
残高不足・接続不可)場合のフォールバックにしか使わない。

provider 選択:
  - env FURUI_PROVIDER=zen|openrouter|typesafe|auto  (default auto)
  - auto: OPENCODE_ZEN_API_KEY があれば zen。無ければ openrouter、次いで typesafe。
  - SEMGREP_API_BASE / SEMGREP_MODEL で endpoint/モデルを強制上書きできる。

分類方式 (choice):
  Jev の絶対尤度 (noul) は全カテゴリが同時に高くなり差が出にくいため、
  択一の choice 質問に切り替えた(confidence 0.9+)。1リクエストに
  複数行 × 複数質問を詰めて呼ぶ。

wire format:
  POST {model, state:{L000:line,...}, questions:{"q0":{type:'choice',instructions,criteria}}}
  -> {answers:{"q0":{choice:str, confidence:float}}}
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ZEN_DEFAULTS = {
    "api_base": "https://opencode.ai/zen/v1/systemone",
    "model": "jev-1.13-free",  # 無料(期間限定)。有償なら jev-1.13
}
OPENROUTER_DEFAULTS = {
    "api_base": "https://openrouter.ai/api/alpha/decisions",
    "model": "~typesafe/jev-latest",
}
TYPESAFE_DEFAULTS = {
    "api_base": "https://api.typesafe.ai/v1/systemone",
    "model": "jev-latest",
}

ENV_CANDIDATES = [
    "SEMGREP_ENV",
    ".env",
    str(Path.home() / ".config/semgrep" / ".env"),
]

PROVIDER = {
    "zen": ("OPENCODE_ZEN_API_KEY", ZEN_DEFAULTS),
    "openrouter": ("OPENROUTER_API_KEY", OPENROUTER_DEFAULTS),
    "typesafe": ("TYPESAFE_API_KEY", TYPESAFE_DEFAULTS),
}


def _load_env_file(path: str) -> dict[str, str]:
    env: dict[str, str] = {}
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip("'\"")
    except OSError:
        pass
    return env


def _key_for(provider: str) -> str:
    env_name = PROVIDER[provider][0]
    value = (os.environ.get(env_name) or "").strip()
    if value:
        return value
    for cand in ENV_CANDIDATES:
        if not cand:
            continue
        env = _load_env_file(cand)
        value = env.get(env_name, "").strip()
        if value:
            return value
    return ""


def _settings(force: str | None = None) -> tuple[str, str, str, str]:
    """(api_base, model, provider, key)。provider は zen / openrouter / typesafe。"""
    want = (force or os.environ.get("FURUI_PROVIDER") or "auto").lower()
    if want == "auto":
        order = ["zen", "openrouter", "typesafe"]
    elif want in PROVIDER:
        order = [want]
    else:
        raise RuntimeError(f"FURUI_PROVIDER must be one of auto/{'/'.join(PROVIDER)}")

    for provider in order:
        key = _key_for(provider)
        if not key:
            continue
        defaults = PROVIDER[provider][1]
        api_base = os.environ.get("SEMGREP_API_BASE", defaults["api_base"])
        model = os.environ.get("SEMGREP_MODEL", defaults["model"])
        return api_base, model, provider, key

    raise RuntimeError(
        "No API key. Set OPENCODE_ZEN_API_KEY, OPENROUTER_API_KEY or "
        "TYPESAFE_API_KEY, or put them in SEMGREP_ENV / ./.env / "
        "~/.config/semgrep/.env"
    )


def classify_lines(
    lines: list[str],
    criteria: dict[str, str],
    *,
    chunk: int = 30,
    concurrency: int = 8,
    retries: int = 6,
    timeout: float = 60.0,
    force_provider: str | None = None,
) -> list[tuple[str, float]]:
    """lines を Jev choice で単一カテゴリに振るう。

    返り値は (line数) の (choice, confidence)。
    """
    api_base, model, provider, key = _settings(force_provider)

    chunks: list[list[str]] = []
    for line in lines:
        if not chunks or len(chunks[-1]) >= chunk:
            chunks.append([])
        chunks[-1].append(line)

    def build_body(lines_chunk: list[str], model: str) -> bytes:
        state = {f"L{i:03d}": text[:2000] for i, text in enumerate(lines_chunk)}
        questions = {
            f"q{i}": {
                "type": "choice",
                "instructions": f"Which category fits the item on L{i:03d} best?",
                "criteria": criteria,
            }
            for i in range(len(lines_chunk))
        }
        return json.dumps({"model": model, "state": state, "questions": questions}).encode()

    def headers(key: str, provider: str) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "furui/0.1 (https://github.com/bonsai/furui)",
        }
        if provider == "openrouter":
            h["HTTP-Referer"] = "https://github.com/bonsai/furui"
            h["X-Title"] = "furui"
        return h

    # --- 単一 chunk の評価(リトライ + フォールバック込み) ---
    def evaluate(ci: int, lines_chunk: list[str], out: list) -> None:
        # zen を優先しつつ、後続 provider(openrouter → typesafe)へフォールバック可能
        order = ["zen", "openrouter", "typesafe"]
        try:
            start = order.index(provider)
        except ValueError:
            start = 0
        attempts = order[start:] + [p for p in order[:start] if _key_for(p)]
        errors: list[str] = []
        tried: set[str] = set()
        for provider_try in attempts:
            if provider_try in tried:
                continue
            tried.add(provider_try)
            key_try = _key_for(provider_try)
            if not key_try:
                continue
            try:
                api_try, model_try, _, _ = _settings(force=provider_try)
            except RuntimeError:
                continue
            body = build_body(lines_chunk, model_try)
            for attempt in range(retries + 1):
                try:
                    req = urllib.request.Request(
                        api_try,
                        data=body,
                        headers=headers(key_try, provider_try),
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        raw = json.loads(resp.read().decode("utf-8"))
                    payload = raw.get("data") or raw
                    answers = payload["answers"]
                    out[ci] = [
                        (
                            str(a.get("choice", "")),
                            float(a.get("confidence", 0.0) or 0.0),
                        )
                        for a in (answers[f"q{i}"] for i in range(len(lines_chunk)))
                    ]
                    return
                except urllib.error.HTTPError as e:
                    err = e.read().decode("utf-8", "replace")[:300]
                    # zen の無料枠制限(429)・残高不足(402)・Cloudflare(403)は
                    # フォールバック対象。一時的 5xx は同じ provider で再試行する。
                    if e.code in (429, 402, 403, 529) or e.code >= 500:
                        if provider_try == "zen" and e.code in (429, 402, 403):
                            errors.append(f"{provider_try} {e.code}: {err}")
                            break  # zen は諦めて次の provider へ
                        if attempt < retries:
                            time.sleep(0.5 * (2**attempt))
                            continue
                    errors.append(f"{provider_try} {e.code}: {err}")
                    break  # この provider を諦める
                except (urllib.error.URLError, TimeoutError) as e:
                    errors.append(f"{provider_try}: {e}")
                    break
        if out[ci] is None:
            raise RuntimeError("; ".join(errors) if errors else "no provider available")

    results: list = [None] * len(chunks)
    threads = [
        threading.Thread(target=evaluate, args=(i, c, results), daemon=True)
        for i, c in enumerate(chunks)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    flat = [row for chunk in results for row in chunk]
    if None in flat:  # どこかの chunk が白紙のまま
        raise RuntimeError("furui: some chunks failed to classify")
    return flat