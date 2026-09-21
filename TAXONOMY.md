# TAXONOMY — furui の4つの篩目

furui はファイル/ディレクトリを意味ごとに選り分ける。選り分けの「目」(criteria)は以下。
`py/furui/buckets.py` の `TAXONOMY` と同期している(変更時の正はコード側)。

| key | 判定命題 (Jev choice criteria) | 標準ディレクトリ |
|---|---|---|
| `agent` | An AI agent persona or character: a named entity with a role, responsibilities, and a personality definition | `agents/` |
| `skill` | An AI agent skill, tool, plugin, MCP server, or CLI utility: a capability that does or operates something | `skills/` |
| `project` | A software project, application, service, or website: a git repository, app, or deployable artifact | `projects/` |
| `wiki` | Knowledge, documentation, notes, records, plans, references, or any archive material | `wiki/` |
| `junk` | A temporary or stray artifact: log file, backup, executable, cache, leftover, or otherwise disposable junk | `.trash/` |

## 分類の実際 (実測ノート)

### Jev の絶対尤度 (noul) は使わない

5命題を同時に「このどれに当てはまりそうか」で聞くと、全カテゴリが同時に高くなる
(実測: どれも0.6〜0.8で差ゼロ/低confidence。`agents/mito` が project 0.80 等)。
→ **choice(択一)** 質問に切り替えた。単一カテゴリが confidence 0.9+ で返る
(`agents/mito` → agent 1.00, `skills/Cycle.md` → wiki 0.99 等)。

### 拡張子で先行除外するゴミ (Jev は呼ばない)

- `.log .bak .tmp .swp .pyc .pyo .DS_Store .exe .dll .db-wal .db-shm`
- `無題*` / `untitled` / `new document*`(括弧付き `(無題__104720).txt` も)
- `.~xxx` / `~$xxx`(Office ロック)
- URL 名のままの `.txt`

### ambiguous

Jev choice の confidence が 0.4 未満 → `ambiguous`。動かさない。
あいまいなものは情報量が多いことが多い(判断が人に委ねるのが正しい)。

### 二重化防止

既に正しいバケット配下にある項目(例: `agents/mito` → agent)は移動しない。
plan が `agents/agents/mito` のような二重化を作らないためのガード。

## 判断のコツ

- ディレクトリは中身の一覧(最初の8要素)を説明に載せる。空は "empty dir"
- 説明はファイルの先頭数行から生成(コードは metadata/front-matter を除去)
- バイナリは "binary file, N bytes" で判定(中身は読まない)

## 将来の拡張

- provider 判定後の embed クラスタから、命名規則(例: 全部 `furui` 関連ノート)を
  キャッチしてバケット候補を提案する
- `--dry-run` 相当の差分表示は apply の dry run で提供中