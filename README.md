# Bitcoin Auto Trading System

Bitcoinの自動取引システム。AWS Lambda、DynamoDB、Reactを使用したコスト効率的な設計。

## アーキテクチャ概要

- **AWS Lambda**: 価格チェックと取引判断（コスト削減）
- **DynamoDB**: 価格データ、取引履歴、エージェント判断の保存
- **Amazon EventBridge**: 定期的なLambdaトリガー
- **React + Server Actions**: フロントエンドとデータアクセス
- **LSTM**: 機械学習モデル（ローカル学習、Lambdaで推論）

## プロジェクト構造

```
auto-trade/
├── lambda/                    # Lambda関数
│   ├── price_fetcher/        # 価格取得関数
│   ├── trading_agent/        # 取引エージェント関数
│   ├── trader/               # 注文実行関数
│   └── shared/               # 共通モジュール
├── infra/                     # Terraform定義
│   ├── lambda.tf
│   ├── dynamodb.tf
│   ├── eventbridge.tf
│   └── iam.tf
├── ml/                        # 機械学習
│   ├── train/                # 学習スクリプト
│   ├── models/               # 学習済みモデル
│   └── inference/            # 推論用コード
├── frontend/                  # Reactアプリ
│   ├── app/                  # Next.js App Router
│   ├── components/
│   └── server-actions/       # DynamoDBアクセス
├── shared/                    # 共通コード
│   ├── agents/               # エージェントロジック
│   ├── traders/              # トレーダー実装
│   └── models/               # データモデル
└── simulation/                # シミュレーション
    ├── engine/               # シミュレーションエンジン
    └── api/                  # シミュレーションAPI
```

## セットアップ

### 前提条件

- Python 3.11+
- Node.js 18+
- Terraform 1.5+
- AWS CLI設定済み

### インストール

```bash
# Lambda依存関係
cd lambda && pip install -r requirements.txt -t .

# フロントエンド依存関係
cd frontend && npm install

# Terraform初期化
cd infra && terraform init
```

## デプロイ

```bash
# インフラデプロイ
cd infra && terraform apply

# Lambdaデプロイ（各関数）
# AWS CLIまたはTerraformで自動デプロイ
```

## 使用方法

1. 機械学習モデルの学習（ローカル）
2. 学習済みモデルをS3にアップロード
3. Lambda関数をデプロイ
4. EventBridgeルールを有効化
5. Reactアプリでモニタリング

## ライセンス

MIT


