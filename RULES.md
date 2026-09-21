# furui 整理ルール — 熱力学木村モデル × ふるいの統合

> `~/.skills/seiri-seiton/theory.md`（三箇条 + 7禁忌 + 熱力学モデル）と
> furui（4タイプ分類 + junk 判別）の決定表。実装: `py/furui/rules.py`。

## 0. 基本に立ち返る

- **篩の目（意味）**は「どこへ置くか」を決める。
- **温度（相）**は「動かすか・触るか」の扱いを決める。
- この2つは直交する。どちらかだけで全部を決めてはいけない。

## 1. 温度相（vapor / liquid / solid）

| 記号 | 式 | 意味 | 扱い |
|---|---|---|---|
| T | `exp(-Δdays/30)`（mtime） | 温度 | 相の判断のみ |
| 相 | vapor: T≥0.5 / liquid: 0.2≤T<0.5 / solid: T<0.2 | 状態 | 決定表へ |

- **vapor（作業中・ホット）**: 余計な手出しをしない。ただし意味が確定して
  いるものは棚へ「出す」（留置きは軌道修正しにくい）。
- **liquid（常駐・アクティブ）**: 温存。棚の移動なら問題なし。
- **solid（冷え・アーカイブ候補）**: 棚へ移す際はアーカイブの検討もする。

## 2. 決定表（bucket × 相 -> action）

| bucket | 相 | action | 理由 |
|---|---|---|---|
| junk | 任意 | **trash** | 要らない（三箇条1: 分ける）。`root/.trash/` へ |
| ambiguous | vapor | **leave** | 判定弱い + 作業中 → 手出し禁止 |
| ambiguous | liquid | **leave** | 判定弱い → 動かさない（人に任せる） |
| ambiguous | solid | **review** | 冷えている → アーカイブを人に検討させる |
| agent/skill/project/wiki | vapor | **move** | 作業中でも意味が確定 → 棚へ出して整理 |
| agent/skill/project/wiki | liquid | **move** | 棚へ |
| agent/skill/project/wiki | solid | **move** | アーカイブ候補として棚へ |
| （既に正しい棚内） | 任意 | **leave** | 二重化を避ける（`agents/agents/...`） |

## 3. 三箇条との対応

1. **分ける** → junk 判定と trash。不要は捨てるかアーカイブへ。
2. **置く** → 分類結果の棚（agents/skills/projects/wiki）へ1つだけ。
3. **登録する** → 頼んだ後に index / リポジトリへ。`furui-move.log` が移動の記録。

## 4. 7禁忌（機械検出は measure.py --taboo）

| # | 禁忌 | furui 側の役割 |
|---|---|---|
| 1 | ホーム直下に置くな | plan がバケットへ移動 |
| 2 | 「とりあえず」で置くな | 分類で「ambiguous」を残す判定 |
| 3 | 一時ファイル放置 | junk（`.tmp`/`.bak`/`~` 等）を trash へ |
| 4 | 複数箇所に写すな | 既に正しい棚内はスキップ（leave） |
| 5 | 抽象フォルダ新設 | 標準 4 バケット + .trash のみ |
| 6 | 掃除しないで帰るな | apply が実行器 |
| 7 | 索引に載せずに置くな | apply 前後の measure / log |

## 5. 実運用フロー

```bash
# 1) 散らかりを測る（木村: まず測れ）
python3 ~/.skills/seiri-seiton/measure.py <root> --taboo

# 2) ふるいに掛ける
furui manifest <root> -o manifest.txt
furui classify manifest.txt -o classified.json

# 3) プラン（決定表 + エントロピー変化）
furui plan classified.json --root <root>

# 4) 実行
furui apply <plan.tsv> --root <root> --yes

# 5) 検証（移動で散らかりが下がったか）
python3 ~/.skills/seiri-seiton/measure.py <root>
```

## 6. エントロピーの読み方

- furui の plan が出す entropy は**位置分布**の一様性（0=一点集中）。
- 木村の S（散らかり度）は**状態の質**（scatter/naming/dup/obs）。
- 両者は次元が違う。**両方を下げる**のが完成形。
  plan が position entropy を下げ、その後の命名・重複・陳腐化整理が
  kimura S を下げる。