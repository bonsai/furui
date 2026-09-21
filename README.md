# furui — エラトステネスの篩

> 「ふるい」、エラトステネスの篩にちなむ。意味でフォルダを振るう整理の槍。

`furui` は **Jev (System One)** でファイルやディレクトリを意味ごとに選り分け、
`agent / skill / project / wiki` の4タイプ(+ ゴミ)に再編成するツールです。
さらに ML 埋め込みで「近い意味の塊(cluster)」を検出して、分類では拾いきれない
まとまりも見えるようにします。

- **Jev** (zen / openrouter / typesafe) が主役 — 意味判定の篩
- **embed** (LM Studio ローカル) が補助 — 近傍クラスタの情
- **entropy** で整理前後の散らばり度を比較

## 思想

エラトステネスの篩は「素数だけを残す」ための手続きです。
`furui` は同じ構造で「意味あるものだけを正しい棚に入れる」手続きを提供します。

```
全ファイル ── 拡張子で明らかゴミを除外 (.log/.bak/.tmp/.exe/無題*...)
    │
    ├─ Jev: これは agent? skill? project? wiki?  (choice 質問・択一)
    ├─ embed: 似た言葉の塊 (cluster)
    └─ 判定が弱ければ ambiguous (動かさない・人に任せる)
```

| bucket | 意味 | 標準ディレクトリ |
|---|---|---|
| `agent` | AIエージェント・ペルソナ | `agents/` |
| `skill` | AIスキル・ツール・MCP・CLI | `skills/` |
| `project` | ソフトウェア・アプリ・サービス | `projects/` |
| `wiki` | 知識・資料・記録・計画 | `wiki/` |
| `junk` | ログ・バックアップ等の廃棄物 | `.trash/` |

## 使い方 (python)

```sh
pip install -e py/          # 依存はなし。stdlib + ネットのみ

furui manifest ~/repo -o manifest.txt        # 1. 目録 (rel + one-line desc)
furui classify manifest.txt -o classified.json   # 2. Jev で4タイプ+junkに振るう
furui plan classified.json --root ~/repo -o plan.tsv   # 3. 移動プラン+エントロピー
furui apply plan.tsv --root ~/repo --yes     # 4. 実際に動かす (ログ furui-move.log)
```

補助コマンド:

```sh
furui embed manifest.txt --k 6 --min-sim 0.6   # 近い意味の塊(cluster)を付与
```

## provider 切り替え (Jev)

`furui` は **OpenCode Zen を最優先**し、OpenRouter はフォールバックにしか使いません。
キーは `~/.config/semgrep/.env` (`OPENCODE_ZEN_API_KEY` / `OPENROUTER_API_KEY`) か
環境変数で持ちます(`_key_for` が env → SEMGREP_ENV → ./.env → ~/.config/semgrep/.env の順に探索)。

| 環境変数 | 効果 |
|---|---|
| `FURUI_PROVIDER` | `auto`(既定) / `zen` / `openrouter` / `typesafe` |
| `SEMGREP_API_BASE` | endpoint 強制上書き |
| `SEMGREP_MODEL` | model 強制上書き |

auto は `zen` → `openrouter` → `typesafe` の順で最初にキーのある provider を使い、
zen が 429(無料枠制限)・402(残高不足)・403 で落ちたら次の provider に自動フォールバックします。

## embed (ML 埋め込み)

`furui embed` は LM Studio (`http://127.0.0.1:1234/v1/embeddings`) を使い、
単語頻度ベクトル(hash)にフォールバックします。LM Studio で embed モデルを
導入していない間は近似のクラスタリング品質になります。

## 構成

| 言語 | 場所 | 状態 |
|---|---|---|
| Python | `py/` | 実装済み |
| TypeScript | (未着手) | - |
| Rust | (未着手) | - |

## テスト

スモークテスト用データが `tests/data/` にあります。

```sh
python3 -m furui.cli classify tests/data/small_manifest.txt -o /tmp/out.json
python3 -m furui.cli plan /tmp/out.json --root ~/repo
```

## 関連

- `docs/ERATOSTHENES.md` — 篩と furui のエッセイ
- `~/.agents/skills/lms-manager/` — LM Studio (lms) 管理スキル(embed モデル導入・ヘルスチェック)
- [bonsai/jevalin](https://github.com/bonsai/jevalin) — 意思決定エンジン(分離プロジェクト)

## License

MIT