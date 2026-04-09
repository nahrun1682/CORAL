# CORAL 実行ログの読み方（初心者向け）

このメモは、次のような `uv run coral start ...` 実行時ログを読むためのガイドです。

---

## まず結論

あなたのログは **正常に起動できています**。

判断ポイントは次の3つです。

1. `Codex agent agent-1 started with PID ...` が出ている
2. `Agent running...` が出ている
3. `[agent-1] {"type":"thread.started"}` のようなイベントが流れている

この3つが揃っていれば、エージェント実行は開始済みです。

---

## ログを上から順に解説

### 1. 設定の表示

```text
[coral] Config:     examples/mnist/task.yaml
[coral] Task:       MNIST
[coral] Agents:     1
[coral] Model:      gpt-5.4
```

- どの設定ファイルを使ったか
- 何のタスクか
- エージェント数
- モデル

を確認する部分です。

ここで意図と違う値なら、起動オプション（`agents.count=...` など）を見直します。

### 2. 実行用ディレクトリの作成

```text
results/.../mnist/2026-04-09_145712
```

1回の実験ごとに専用フォルダを作ります。

- `run_dir`: その実験の作業場所
- `.coral/public`: ログや試行履歴
- `agents/agent-1`: エージェントのworktree

同じ実験を再現・比較しやすくするための仕組みです。

### 3. seed と grader の準備

```text
Copied eval/ to .coral/private/eval/
Seeded file: solution.py
Seeded directory: data/
```

- `eval/`（採点コード）をコピー
- `seed/`（初期コードとデータ）を作業リポジトリへ配置

つまり「採点環境と初期コードのセットアップ」が完了した状態です。

### 4. 依存関係のセットアップ

```text
Running setup command: uv venv .venv && uv pip install --python .venv/bin/python numpy scikit-learn
```

ここで各エージェント用のPython環境を作って、必要ライブラリを入れています。

この工程で失敗すると、後で `ModuleNotFoundError` が出ます。

### 5. Codexエージェント起動

```text
Starting Codex agent agent-1 ...
Command: codex exec Begin. --dangerously-bypass-approvals-and-sandbox --model gpt-5.4 --json
Codex agent agent-1 started with PID 67747
```

- CORALがCodex CLIをサブプロセスで起動
- `PID` が出ると、OS上でプロセスが動いている証拠

### 6. 実行中イベント

```text
[agent-1] {"type":"thread.started", ...}
[agent-1] {"type":"turn.started"}
```

CodexがJSONイベントを返しており、

- スレッド開始
- ターン開始

が確認できます。これは「実際に推論・作業が始まった」サインです。

---

## よく使う確認コマンド

別ターミナルで次を打つと状況確認しやすいです。

```bash
uv run coral status
uv run coral log
```

停止するとき:

```bash
uv run coral stop
```

---

## つまずきやすい点

1. APIキー未設定
- `OPENAI_API_KEY` がないと Codex がAPI呼び出しで失敗

2. 依存ライブラリ不足
- `numpy` などが入っていないと grader 実行で失敗

3. 設定ファイルのスキーマ不一致
- `task.files` のように、現行 `TaskConfig` にないキーでエラーになることがある

---

## このログの状態まとめ

- 起動: 成功
- エージェント: 起動済み（`agent-1`）
- 実験: 進行中

なので、今やることは「`status` / `log` で途中経過を見て、必要なら `stop`」です。
