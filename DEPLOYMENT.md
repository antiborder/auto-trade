# デプロイメントガイド

## 前提条件

- AWS CLI設定済み
- Terraform 1.5以上
- Python 3.11以上
- Node.js 18以上

## セットアップ手順

### 1. 環境変数の設定

```bash
export AWS_REGION=ap-northeast-1
export PROJECT_NAME=auto-trade
```

### 2. DynamoDBテーブルの作成（Terraform）

```bash
cd infra
terraform init
terraform plan
terraform apply
```

### 3. Lambda関数のデプロイ

#### 方法1: スクリプトを使用

```bash
chmod +x scripts/deploy_lambda.sh
./scripts/deploy_lambda.sh
```

その後、各Lambda関数の`deployment.zip`をAWSにアップロード:

```bash
# price_fetcher
aws lambda update-function-code \
  --function-name auto-trade-price-fetcher \
  --zip-file fileb://lambda/price_fetcher/deployment.zip

# trading_agent
aws lambda update-function-code \
  --function-name auto-trade-trading-agent \
  --zip-file fileb://lambda/trading_agent/deployment.zip
```

#### 方法2: Terraformで自動デプロイ

Terraformの`lambda.tf`で`source_code_hash`を使用しているため、`deployment.zip`を作成後、`terraform apply`を実行。

### 4. 設定の適用

`trading_agent` Lambda関数に環境変数として設定を追加:

```bash
aws lambda update-function-configuration \
  --function-name auto-trade-trading-agent \
  --environment Variables="{TRADING_CONFIG=$(cat lambda/trading_agent/config.example.json | jq -c)}"
```

または、AWS Secrets Managerを使用（推奨）:

```bash
aws secretsmanager create-secret \
  --name auto-trade/config \
  --secret-string file://lambda/trading_agent/config.example.json
```

### 5. EventBridgeルールの有効化

Terraformで作成されたEventBridgeルールは自動的に有効化されます。

手動で確認:

```bash
aws events list-rules --name-prefix auto-trade
```

### 6. 機械学習モデルのアップロード

```bash
# モデルを学習
cd ml/train
python train_lstm.py --data ../../data/btc_prices.csv --output ../../ml/models/lstm_model.h5

# S3にアップロード
aws s3 cp ml/models/lstm_model.h5 s3://your-bucket/models/lstm_model.h5
```

### 7. フロントエンドのデプロイ

```bash
cd frontend
npm install
npm run build

# Vercel、AWS Amplify、または他のホスティングサービスにデプロイ
```

## ローカル開発

### Lambda関数のローカルテスト

```bash
# 依存関係をインストール
cd lambda
pip install -r requirements.txt -t .

# テスト実行
python -m pytest tests/
```

### フロントエンドのローカル実行

```bash
cd frontend
npm install
npm run dev
```

## トラブルシューティング

### Lambda関数がタイムアウトする

- メモリサイズを増やす（`lambda_memory_size`変数を調整）
- タイムアウト時間を増やす（`lambda_timeout`変数を調整）

### DynamoDBアクセスエラー

- IAMロールのポリシーを確認
- テーブル名が環境変数と一致しているか確認

### モデル読み込みエラー

- S3バケットへのアクセス権限を確認
- モデルパスが正しいか確認
- Lambda Layerを使用する場合は、モデルサイズを確認

## モニタリング

### CloudWatch Logs

```bash
# Lambda関数のログを確認
aws logs tail /aws/lambda/auto-trade-price-fetcher --follow
aws logs tail /aws/lambda/auto-trade-trading-agent --follow
```

### CloudWatch Metrics

AWSコンソールで以下を確認:
- Lambda実行回数
- エラー率
- 実行時間
- DynamoDB読み書きスループット

