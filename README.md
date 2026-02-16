# growing_agent

最小構成のPythonプロジェクトです。エージェントの基本ループ **observe → plan → act → evaluate → update** を実装しています。

## できること

- **Orchestrator**: `observe -> plan -> act -> evaluate -> update` を指定回数ループ
- **Memory**: `data/state.json` に状態を読み書き
- **Runner**: 許可コマンド（allowlist）のみ実行し、`logs/runner.log` に実行ログを追記
- **Evaluator**: `pytest` の実行結果から \(0.0〜1.0\) のスコアを算出

## 実行方法

このリポジトリ直下で実行してください。

### 依存を増やさずに実行（おすすめ）

`src/` レイアウトなので、`PYTHONPATH=src` を付けて実行できます。

```bash
PYTHONPATH=src python -m growing_agent run --iterations 3 --dry-run
```

※ 環境によっては `python` が無いので、その場合は `python3` を使ってください。

### インストールして実行（任意）

ローカルソースを編集可能インストールして実行する場合:

```bash
python -m pip install -e .
python -m growing_agent run --iterations 3 --dry-run
```

## 生成されるファイル

- **状態**: `data/state.json`
- **実行ログ**: `logs/runner.log`（JSONL）

## 安全性について

- **ネットワークアクセスはしません**（Runnerは許可コマンドのみ実行します）
- **破壊的コマンドは実行しません**（allowlist方式・シェル実行なし）
