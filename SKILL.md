---
name: furui
description: エラトステネスの篩 — Jev (System One) + ML埋め込みでフォルダを意味ごとに振るう整理の槍。4タイプ(agent/skill/project/wiki)+junkに分類し、移動プランとエントロピー変化を出して実際に移動する。トリガー: 「ふるい」「furui」「フォルダ整理」「ファイル整理」「整理の槍」「意味で分ける」「エントロピー下げて」「reorganize」
---

# furui — エラトステネスの篩

Jev(System One)でファイル/ディレクトリを意味ごとに4タイプ+ゴミへ選り分け、
移動プランを生成・適用する**フォルダ整理の槍**。木村拓哉(kimura)エージェントの掃除に
使えるよう設計している。

## 前提

- Git リポジトリ: `~/repo/projects/furui`(= bonsai/furui)
- 実装は `py/`(Python・依存なし)
- Jev は **OpenCode Zen 優先**、OpenRouter はフォールバック(キーは `~/.config/semgrep/.env`)
- ML 埋め込みは LM Studio ローカル (`127.0.0.1:1234`)。無ければハッシュ埋め込みに自動フォールバック

## 使い方

```
cd ~/repo/projects/furui/py

# 1. 目録を作る (rel + 一行説明)
python3 -m furui.cli manifest <dir> -o manifest.txt

# 2. Jev で分類
python3 -m furui.cli classify manifest.txt -o classified.json

# 3. 移動プラン (何がどこへ行くか・エントロピー変化)
python3 -m furui.cli plan classified.json --root <dir> -o plan.tsv

# 4. ドライラン確認 → 実際に移動
python3 -m furui.cli apply plan.tsv --root <dir>            # dry-run
python3 -m furui.cli apply plan.tsv --root <dir> --yes      # 実行（ログ: furui-move.log）
```

補助: `furui embed manifest.txt` で近い意味の塊(cluster)付与。

## 分類の設計 (実測ベース)

- **拡張子で明らかゴミは Jev を呼ばない**:
  `.log/.bak/.tmp/.swp/.pyc/.pyo/.DS_Store/.exe/.dll/.db-wal/.db-shm`、
  `無題*/untitled`、`.~`/`~$` ロック、URL名の .txt、
  `:Zone.Identifier`(Windows 由来マーカー。manifest 生成時にも読み飛ばす)
- **エージェント篩は Jev より先** — 「**人名ならエージェント**」。
  `mito-coordinator` / `garden-agent` / `architecture-agent` / `strategic-advisors` 等の
  ペルソナ命名、または説明に「役割を持つ人名」が見える項目は Jev を呼ばず agent 1.00
- **スキル篩** — 「**CLI メインでスキルがくっついてくる**」。
  名前が `cli/scripts/macro/plugin/mcp/pipeline` 等、文面に CLI/コマンドライン/
  ターミナル/マクロ集 が見える項目は skill 1.00(「dir contains ...」の一覧には
  マッチさせない — `tests/cli` で誤爆した実測あり)
- **Jev には choice(択一)質問を使う**。`noul`(絶対尤度)は全カテゴリが同時に高くなるため
  差が出ない(実測で全項目0.6-0.8に並ぶ問題が確認された)。choice にすると confidence 0.9+ で単一カテゴリが返る
- 判定が confidence 0.4 未満は `ambiguous` — **動かさない**(人に任せる)
- 既に正しいバケット配下(例: `agents/mito` → agent)の項目は移動しない(二重化防止)

## provider フォールバック

`FURUI_PROVIDER=auto` で `zen → openrouter → typesafe` の順に最初のキーを持つ provider を使う。
zen が 429(無料枠制限)/402(残高不足)/403 のとき自動で次へ。強制は
`FURUI_PROVIDER=zen|openrouter|typesafe`、endpoint/model は `SEMGREP_API_BASE`/`SEMGREP_MODEL` で上書き。

## 他のスキルとの関係

- `lms-manager` — LM Studio の起動・モデル導入・embed モデル管理(furui embed の下回り)
- `seiri-seiton` — 整理整頓理論(3ルール/7禁忌/熱力学モデル)。furui はその「実行器」側
- `asset-manager` — GitHub-centric のアセットライフサイクル。furui は分類の道具

## ファイル

- `py/furui/{manifest,classify,plan,apply}(cli)`, `jev`, `embed`, `buckets`.py
- `buckets.py` — TAXONOMY(4タイプ)、junk拡張子、guess_junk
- `tests/data/small_manifest.txt` ほか — スモークテスト

## 注意

- 移動は `--yes` で実行される。最初は必ず dry-run でプラン確認を
- `apply` はログ(`furui-move.log`)を追記する。元に戻す材料として git diff かログを見る
- バケット配下へ移動中の相対パスは「既に正しい位置」ならスキップされる