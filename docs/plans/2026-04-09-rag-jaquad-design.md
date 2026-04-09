# JaQuADベース日本語RAG研究自動化 PoC 設計

## 1. 目的と成功条件
本PoCの目的は、CORAL上で日本語RAGタスクの自動改善ループを成立させること。対象はJaQuADを用いたQAで、単なる回答精度ではなく、検索品質と速度を含めた総合最適化を行う。成功条件は、ベースラインに対して総合スコアが改善し、かつ内訳指標（Answer F1 / Recall@5 / Latency）が極端に悪化しないこと。1回の評価は約1,000クエリで固定し、比較は複数run平均で行う。生成モデルはOpenAI APIの固定モデル名を使い、評価の再現性を確保する。

総合スコアは次式を採用する。

```
score = 0.55 * AnswerF1 + 0.35 * Recall@5 + 0.10 * LatencyScore
LatencyScore = max(0, 1 - latency_sec / 15)
```

この重みは「回答品質を主軸にしつつ、検索品質を明確に評価し、遅すぎる手法を抑制する」ためのPoC向け初期設定である。

## 2. タスク構成
新規タスクを `examples/rag_jaquad/` に追加する。構成はCORAL標準に合わせる。

- `task.yaml`: 目的・制約・評価方針・実行設定
- `seed/`: 初期RAG実装
- `eval/grader.py`: 評価ロジック（スコア統合）

`seed/` は改善対象を分離しやすいように以下を推奨。

- `solution.py`: 推論パイプライン制御（retrieve -> context assemble -> generate）
- `retrievers/bm25_retriever.py`
- `retrievers/dense_retriever.py`
- `prompts/`（任意）
- `data/`（評価対象クエリ・文書コーパス）

エージェントはこの初期実装を基に、検索方式、k値、プロンプト、後処理などを段階的に最適化する。

## 3. データ設計
JaQuADをPoC用に整形し、評価で使うスプリットを固定する。最低限の項目は以下。

- `query_id`
- `query`
- `gold_answer`（複数可）
- `gold_doc_id`（Recall評価用）
- `doc_id -> document text`（検索対象）

評価データの漏洩防止のため、必要に応じて `grader.private` を使って隠しデータを `.coral/private` 側へ配置する。PoC段階では運用負荷を下げるため、まず公開整形データで開始し、のちに本番用分割へ移行する。

## 4. 評価ロジック
`eval/grader.py` は以下を計測し、最後に単一スコアへ統合する。

- `AnswerF1`: 生成回答 vs gold回答のトークンF1
- `Recall@5`: top-5検索結果にgold文書が含まれる割合
- `latency_sec`: 1クエリ平均推論時間
- `score`: 重み付き統合スコア

加えて診断用メトリクスを返す。

- 空回答率
- 取得失敗率
- APIリトライ回数
- 実評価件数（除外後）

失敗時は全体停止を避け、可能な限り評価継続する。例えば空回答はF1=0として扱い、API一時障害はリトライ後に失敗率へ反映する。

## 5. 実行環境
依存関係は `workspace.setup` で固定する。Anaconda混入を避けるため、worktree内Pythonを明示してインストールする。

例:

```yaml
workspace:
  setup:
    - "uv venv .venv && uv pip install --python .venv/bin/python rank-bm25 sentence-transformers openai"
```

APIキーは実行前に設定。

```bash
export OPENAI_API_KEY="..."
```

## 6. 実験プロトコル
1. `coral validate` でgrader健全性確認
2. スモーク実行（`agents.count=1`, `max_turns=3~5`）
3. 本実行（約1,000クエリ）
4. 3run以上で平均比較

初期は `research=false` で開始し、改善幅が頭打ちになった段階でwarm-start調査を導入する。

## 7. リスクと対策
- コスト超過: クエリ数・ターン数・モデル固定で制御
- 再現性欠如: データ分割・seed・モデル名を固定
- 指標ハック: 総合スコアに内訳下限チェックを追加
- 実行停止: graderでフォールトトレラント設計（部分失敗許容）

## 8. スコープ外（PoC段階）
- 高度再ランキング（Cross-Encoder等）
- マルチホップRAG
- 大規模多ドメイン評価
- 論文投稿向け統計検定パッケージング

PoC完了後、最も効いた改善軸に絞って次段階（研究基盤化）へ進む。
