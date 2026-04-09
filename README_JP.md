<div align="center">

<img src="assets/logo.png" alt="Coral" width="360">


#### 自動研究（AutoResearch）のために構築された、堅牢かつ軽量なマルチエージェント自己進化インフラ。

## 🚀 AutoResearch を加速しよう



[![Paper](https://img.shields.io/badge/Paper-arXiv%3A2604.01658-B31B1B.svg?logo=arxiv&logoColor=white)](https://arxiv.org/abs/2604.01658v1)
[![Blog](https://img.shields.io/badge/Blog-CORAL-FF6B6B.svg?logo=hashnode&logoColor=white)](https://human-agent-society.github.io/CORAL/)
[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-package%20manager-5C4EE5.svg)](https://docs.astral.sh/uv/)

[English](README.md) | [中文](README_CN.md)

</div>

<p align="center">
<a href="#installation">インストール</a> · <a href="#supported-agents">対応エージェント</a> · <a href="#usage">使い方</a> · <a href="#how-it-works">仕組み</a> · <a href="#quick-start">クイックスタート</a> · <a href="#cli-reference">CLI リファレンス</a> · <a href="#using-opencode">OpenCode の利用</a> · <a href="#using-the-gateway-for-custom-models">Gateway</a> · <a href="#examples">例</a> · <a href="#license">ライセンス</a>
</p>


**CORAL** は、実験を実行し、知識を共有し、継続的に解法を改善する **自律型 AI エージェント** の組織を構築するためのインフラです。コードベースと採点スクリプトを渡せば、Coral が残りを処理します。分離されたワークスペース、安全な評価、永続的な共有知識、そして堅牢な進化を可能にするマルチエージェント協調までを提供します。Coral は Claude Code、OpenCode、Codex など主要なコーディングエージェントとネイティブ統合されています。

設定オーバーヘッドなしで自己改善する AI を使いたいですか？ Coral を試してください。



### 🔥 ニュース！

- **[2026-04-03]** 私たちの論文「CORAL: Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery」が公開されました！ [Arxiv](https://arxiv.org/pdf/2604.01658) をご覧ください。
- **[2026-03-18]** CORAL をリリースしました！ [ブログ記事](https://human-agent-society.github.io/CORAL/) をご覧ください。

![Demo](assets/demo.gif)

### Installation

```bash
git clone https://github.com/Human-Agent-Society/CORAL.git
cd CORAL
# uv を https://github.com/astral-sh/uv からインストール
uv sync                   # （必要に応じて --extra ui を付けるとダッシュボード依存関係も追加）
```

### Supported Agents

Coral は、サブプロセスとして実行でき、ターミナル経由で対話できる任意のコーディングエージェントで動作します。現在の対応は以下です。

| Agent | Description |
|-------|-------------|
| [**Claude Code**](https://github.com/anthropics/claude-code) | Anthropic のエージェント型コーディングツール。デフォルトかつ最も検証されているランタイム |
| [**Codex**](https://github.com/openai/codex) | OpenAI のオープンソースコーディングエージェント |
| [**OpenCode**](https://github.com/opencode-ai/opencode) | オープンソースのターミナルベース AI コーディングエージェント |

> [!TIP]
> Coral を使う前に、利用予定のエージェントを必ず完全にセットアップしてください。
>
> - **エージェントのインストール:** 対象エージェント（Claude Code、Codex、OpenCode など）の公式インストール手順に従ってください。パッケージの導入、実行ファイルの配置、スクリプト設定が必要な場合があります。
> - **認証:** 先にコーディングエージェントへログインして認証を済ませ、CLI モードで認証情報入力を求められないようにしてください。エージェントのドキュメントに従って必要な環境変数、設定ファイル、シークレットを設定してください。
> - **権限設定:** エージェントの設定ファイル（例: Claude Code の `~/.claude/settings.json`）で権限を設定し、使用可能なツール、ファイルパス、実行可能な操作を制御してください。
>
> *Coral はエージェントのインストールや認証を代行しません。基盤エージェントが起動できない、または正しく認証されていない場合、インフラは機能しません。*

タスク設定でエージェントを指定します（<a href="#3-configure-the-task">タスク設定</a> を参照）。

```yaml
agents:
  runtime: claude_code   # または "codex" / "opencode"
  count: 3  # 起動するエージェント数。予算に注意 :)
  model: opus   # 使用したいモデル名
```

### Usage

```bash
# 実行を開始
uv run coral start -c examples/kernel_builder/task.yaml

# dotlist 構文で任意の設定値を上書き
uv run coral start -c task.yaml agents.count=4 agents.model=opus
uv run coral start -c task.yaml run.verbose=true        # エージェント出力をストリーム表示
uv run coral start -c task.yaml run.ui=true              # Web ダッシュボードも起動
uv run coral start -c task.yaml run.session=local         # tmux を使わずインライン実行
uv run coral start -c task.yaml run.session=docker        # Docker コンテナ内で実行

# ウォームスタート: コーディング前にリサーチ段階を実行（先に文献調査）
uv run coral start -c task.yaml agents.warmstart.enabled=true agents.research=true

# 停止と再開
uv run coral stop                                        # いつでも停止
uv run coral resume                                      # 中断地点から再開
uv run coral resume agents.model=opus run.verbose=true   # 上書き付きで再開

# 進捗監視
uv run coral ui                                          # Web ダッシュボードを開く
```

### How It Works

<p align="center">
  <img src="assets/coral_diagram_trans.jpg" alt="Coral Architecture Diagram" width="800">
</p>

各エージェントはそれぞれ独立した git worktree ブランチで動作します。共有状態（attempt、notes、skills）は `.coral/public/` に保存され、すべての worktree にシンボリックリンクされるため、同期オーバーヘッドなしでエージェント同士がリアルタイムに作業を参照できます。マネージャーは新しい attempt を監視し、ハートビートトリガーのプロンプト（例: "reflect"、"consolidate skills"）でエージェントに割り込みをかけられます。

| Concept | Description |
|---------|-------------|
| **Agents as optimizers** | Claude Code / Codex / OpenCode のサブプロセス。各エージェントは独自の git worktree で実行 |
| **Shared state** | attempt・notes・skills を持つ `.coral/` ディレクトリ。各 worktree にシンボリックリンク |
| **Eval loop** | エージェントは `uv run coral eval -m "..."` を呼び出し、ステージング・コミット・評価を一括実行 |
| **CLI orchestration** | `start`、`stop`、`status`、`eval`、`log`、`ui` など 17 以上のコマンド |
| **Web dashboard** | `uv run coral ui`。リアルタイムのリーダーボード、attempt diff、エージェント監視 |

**ウォームスタート（任意）:** エージェントはコーディング前に Web 検索で文献調査を行い、結果を共有ノートへ書き込みます。`agents.warmstart.enabled=true` で有効化できます。

### Quick Start

完全な例を見てみましょう。エージェントが **100 都市巡回セールスマン問題** を継続的に最適化します。

#### 1. シードコードベースを書く

シードは、エージェントが反復改善を始める初期コードです。作業ディレクトリを作成します。

```bash
mkdir -p examples/tsp/{seed,eval}
```

次に、単純な初期解を作成します（空から始めることも可能ですが、エージェントにとっては難しくなる可能性があります）。

```python
# examples/tsp/seed/solution.py
import random

# エージェントは `grader.py` の内容を読めないため、ここで問題を再掲する
random.seed(42)
CITIES = [(random.random(), random.random()) for _ in range(100)]

# 単純解: 都市をインデックス順（0, 1, 2, ..., 99）に訪問
for i in range(len(CITIES)):
    print(i)
```

#### 2. グレーダーを書く

`TaskGrader` を継承し、`evaluate()` を実装します。基底クラスは 2 つのヘルパーを提供します。`self.run_program(filename)` はエージェントのコードベース内のファイルをサブプロセスで実行し `CompletedProcess`（`.stdout`、`.stderr`、`.returncode` を含む）を返します。`self.fail(reason)` は失敗を記録し、ヌルスコアを返します。

```python
# examples/tsp/eval/grader.py
import math
import random
from coral.grader import TaskGrader, ScoreBundle

# `solution.py` の問題設定と一致させる
random.seed(42)
CITIES = [(random.random(), random.random()) for _ in range(100)]

class Grader(TaskGrader):
    def evaluate(self) -> float | ScoreBundle:
        try:
            result = self.run_program("solution.py")  # solution.py を実行し CompletedProcess を返す
            order = [int(x) for x in result.stdout.strip().split("\n")]
            assert sorted(order) == list(range(len(CITIES)))
            dist = sum(
                math.dist(CITIES[order[i]], CITIES[order[(i + 1) % len(order)]])
                for i in range(len(order))
            )
            return -dist  # 経路が短いほど高スコア
        except Exception as e:
            return self.fail(str(e))  # 失敗を記録してヌルスコアを返す
```

この単純なシード経路のスコアは約 `-58.02` です。エージェントは最短近傍法、2-opt、焼きなまし法などを試して、より短い経路を探します。100 都市では全探索は完全に非現実的（99! 通り）なので、実用的な最適化ヒューリスティックを発見して適用する必要があります。

#### 3. タスクを設定する

設定ファイルでシードコードベースとグレーダーを指定します。

```yaml
# examples/tsp/task.yaml
task:
  name: tsp
  description: |
    100 都市を巡回する最短の往復ツアーを見つけてください。座標は
    `solution.py` 内で固定シードを使って numpy により生成されます。
    シードや CITIES 生成を変更してはいけません。

    solution.py は標準出力に 100 個の整数（0-99）を 1 行 1 つで出力し、
    訪問順を表す必要があります。各都市はちょうど 1 回ずつ登場しなければなりません。

    グレーダーはユークリッド距離で往復総距離を計算し、
    スコアとして -distance を返します（短いほど高い）。

grader:
  type: function
  module: eval.grader

agents:
  count: 1
  runtime: claude_code  # または opencode, codex
  model: claude-sonnet-4-6
  max_turns: 200  # エージェント再起動までのターン数。Coral は stop するまで動き続けるので心配不要

workspace:
  results_dir: "./results"  # $PWD からの相対パス
  repo_path: "./examples/tsp/seed"  # $PWD からの相対パス
```

#### 4. 実行

```bash
uv run coral start -c examples/tsp/task.yaml             # tmux セッション `coral-tsp` で起動
uv run coral start -c examples/tsp/task.yaml agents.count=4  # エージェント数を上書き
uv sync --extra ui && uv run coral ui                     # Web ダッシュボードを開く（port 8420）
uv run coral status      # CLI リーダーボード
uv run coral log         # attempt を表示
uv run coral stop        # 全エージェント停止
```

### CLI Reference

<details>
<summary>17+ コマンドをすべて表示</summary>

| Command                              | Description                         |
| ------------------------------------ | ----------------------------------- |
| `uv run coral init <name>`           | 新しいタスクをひな形作成            |
| `uv run coral validate <name>`       | グレーダーをテスト                  |
| `uv run coral start -c task.yaml [overrides...]` | エージェントを起動（例: `agents.count=4 run.verbose=true`） |
| `uv run coral resume [overrides...]` | 前回実行を再開（例: `agents.model=opus`） |
| `uv run coral stop`                  | 全エージェント停止                  |
| `uv run coral status`                | エージェント健全性 + リーダーボード |
| `uv run coral log`                   | リーダーボード（上位 20）           |
| `uv run coral log -n 5 --recent`     | 最近の attempt                      |
| `uv run coral log --search "query"`  | attempt を検索                      |
| `uv run coral show <hash>`           | attempt 詳細 + diff                 |
| `uv run coral notes`                 | 共有ノートを閲覧                    |
| `uv run coral skills`                | 共有スキルを閲覧                    |
| `uv run coral runs`                  | すべての実行を一覧表示              |
| `uv run coral ui`                    | Web ダッシュボード                  |
| `uv run coral eval -m "description"` | ステージング・コミット・評価（エージェント用） |
| `uv run coral diff`                  | 未コミット変更を表示                |
| `uv run coral revert`                | 直前コミットを取り消し              |
| `uv run coral checkout <hash>`       | 過去の attempt にリセット           |
| `uv run coral heartbeat`             | ハートビートアクションを表示・変更  |

</details>


### Architecture

<details>
<summary>展開して表示</summary>

```
coral/
├── types.py             # Task, Score, ScoreBundle, Attempt
├── config.py            # YAML ベースの CoralConfig
├── agent/
│   ├── manager.py       # マルチエージェントのライフサイクル
│   └── runtime.py       # Claude Code / Codex / OpenCode サブプロセス
├── workspace/
│   └── setup.py         # Worktree 作成、hooks、symlink
├── grader/
│   ├── protocol.py      # GraderInterface プロトコル
│   ├── base.py          # BaseGrader（ヘルパー: _make_score, _make_bundle）
│   ├── task_grader.py   # タスク固有グレーダー向け TaskGrader
│   ├── loader.py        # グレーダー探索とロード
│   └── builtin/
│       └── function_grader.py
├── hub/
│   ├── attempts.py      # Attempt CRUD + リーダーボード + 検索
│   ├── notes.py         # YAML frontmatter 付き Markdown ノート
│   └── skills.py        # SKILL.md を持つスキルディレクトリ
├── hooks/
│   └── post_commit.py   # コミット時評価（Eval-on-commit）実装
├── template/
│   └── coral_md.py      # CORAL.md 生成器
├── web/                 # Starlette + React ダッシュボード
└── cli/                 # 5 モジュールにまたがる 17 コマンド
```

</details>

### Using OpenCode

エージェントランタイムとして [OpenCode](https://github.com/opencode-ai/opencode) を使うには、シードディレクトリに `opencode.json` 設定ファイルを置く必要があります。このファイルで OpenCode の権限とプロバイダー設定を行います。

以下は `examples/circle_packing/seed/opencode.json` の例です。

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "external_directory": "allow",
    "question": "deny",
    "doom_loop": "allow",
    "bash": "allow",
    "edit": "allow",
    "read": "allow",
    "write": "allow",
    "webfetch": "deny",
    "websearch": "deny",
    "codesearch": "allow",
    "lsp": "allow",
    "skill": "allow"
  },
  "provider": {
    "claude": {
      "npm": "@ai-sdk/anthropic",
      "name": "claude",
      "options": {
        "baseURL": "http://localhost:4000/v1",
        "apiKey": "xxx"
      },
      "models": {
        "claude-opus-4-6": {
          "name": "claude-opus-4-6"
        }
      }
    }
  }
}
```

重要ポイント:
- エージェントを対話プロンプトなしで自律実行させるため、すべての権限を `"allow"` に設定してください（ただし `question`、`webfetch`、`websearch` は `"deny"`）。
- `provider` セクションで使用モデルを設定します。gateway（下記参照）を使う場合は、`baseURL` を `http://localhost:<gateway_port>/v1` に向け、`apiKey` は任意のプレースホルダー値を設定してください。認証は gateway 側で処理されます。
- `opencode.json` はシードディレクトリに置いてください。各エージェントの worktree にコピーされます。

次に、タスク設定で OpenCode を使うよう指定します。

```yaml
agents:
  runtime: opencode
  model: claude/claude-opus-4-6  # opencode.json で定義したモデル名と一致させる必要あり
```

### Using the Gateway for Custom Models

CORAL には、エージェントとモデルプロバイダーの間でプロキシとして動作する組み込み **LiteLLM gateway** が含まれています。次のような場合に有用です。

- 統一された API キー管理で、単一プロキシ経由にエージェントリクエストを集約したい
- カスタムモデルやセルフホストモデルを使いたい
- リクエストログやエージェント単位の追跡を追加したい
- 非標準の認証を必要とするプロバイダーを使いたい

#### Setting up the gateway

**1. LiteLLM 設定ファイル**（例: `litellm_config.yaml`）を `task.yaml` と同じ場所に作成します。

```yaml
# examples/circle_packing/litellm_config.yaml
model_list:
  - model_name: "claude-opus-4-6"
    litellm_params:
      model: "anthropic/claude-opus-4-6"
      api_key: "YOUR_ANTHROPIC_API_KEY"

litellm_settings:
  drop_params: true
```

`model_list` の各エントリは、gateway が提供するモデルを定義します。`model_name` はエージェントが要求する名前、`litellm_params.model` は上流プロバイダーのモデル名です。設定オプションの全体（複数プロバイダー、ロードバランシング、フォールバック等）は [LiteLLM docs](https://docs.litellm.ai/docs/proxy/configs) を参照してください。

**2. タスク設定で gateway を有効化します。**

```yaml
agents:
  runtime: opencode           # または claude_code, codex
  model: claude/claude-opus-4-6
  gateway:
    enabled: true
    port: 4000                # gateway の待ち受けポート
    config: "./litellm_config.yaml"  # task.yaml からの相対パス
```

**3. エージェントを gateway に向けます。** OpenCode の場合は `opencode.json` の `baseURL` を `http://localhost:<port>/v1` に設定します。Claude Code の場合は gateway URL が自動注入されます。

`coral start` を実行すると、エージェント起動前に gateway が起動し、すべてのエージェント API リクエストがそこを経由します。gateway は各エージェントに一意のプロキシキーを自動で割り当て、エージェント単位のリクエスト追跡を可能にします。

gateway を使った OpenCode の完全動作例は `examples/circle_packing/` を参照してください。

### Examples

`examples/` には、そのまま実行できるタスク設定が含まれています。


| Task                       | Domain       | Description                                                 |
| -------------------------- | ------------ | ----------------------------------------------------------- |
| **circle_packing**         | Optimization | 半径和を最大化するように、26 個の円を単位正方形内に詰める |
| **erdos**                  | Mathematics  | 数学予想を解く                                               |
| **kernel_builder**         | Systems      | VLIW SIMD カーネル最適化                                     |
| **kernel_engineering**     | Systems      | GPU カーネル最適化                                           |
| **mnist**                  | ML           | 手書き数字分類                                                |
| **spaceship_titanic**      | ML           | Kaggle コンペティション                                      |
| **stanford_covid_vaccine** | Bio/ML       | mRNA 分解予測                                                |


### Development

```bash
# 開発用依存関係をインストール
uv sync --extra dev

# テストを実行
uv run pytest tests/ -v

# Lint と format
uv run ruff check .
uv run ruff format .
```

このプロジェクトは MIT [LICENSE](LICENSE) で公開されています。

### Citation

⭐ CORAL が役立った場合は、Star や論文での引用をご検討ください。

```bibtex
@article{coral2026,
  title  = {CORAL: Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery},
  author = {Qu, Ao and Zheng, Han and Zhou, Zijian and Yan, Yihao and Tang, Yihong and Ong, Shao Yong and Hong, Fenglu and Zhou, Kaichen and Jiang, Chonghe and Kong, Minwei and Zhu, Jiacheng and Jiang, Xuan and Li, Sirui and Wu, Cathy and Low, Bryan Kian Hsiang and Zhao, Jinhua and Liang, Paul Pu},
  journal = {arXiv preprint arXiv:2604.01658},
  year   = {2026},
  url    = {https://arxiv.org/pdf/2604.01658}
}
```

### Acknowledgement

Coral の開発期間中に多様な API クレジットを惜しみなく提供してくださった [TNT Accelerator](https://www.tnt.so/) に感謝します。さらに、[OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve)、[autoresearch](https://github.com/karpathy/autoresearch)、[TTT Discover](https://arxiv.org/abs/2601.16175) など、多くの先行研究に触発され Coral の着想に至りました。ここに感謝します。
