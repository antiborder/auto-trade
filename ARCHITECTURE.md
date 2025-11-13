# アーキテクチャ設計ドキュメント

## システム概要

Bitcoin自動取引システムは、AWS Lambda、DynamoDB、Reactを使用したコスト効率的な設計です。

## 主要コンポーネント

### 1. Lambda関数

#### price_fetcher
- **役割**: 定期的にBitcoin価格を取得し、DynamoDBに保存
- **トリガー**: EventBridge（5分ごと）
- **処理**:
  1. CoinGecko APIなどから価格取得
  2. DynamoDBに価格データを保存

#### trading_agent
- **役割**: 複数の取引エージェントを並列実行し、取引判断と注文実行
- **トリガー**: EventBridge（5分ごと）
- **処理**:
  1. DynamoDBから最新の価格データを取得
  2. 各エージェントで取引判断
  3. 必要に応じてTrader経由で注文実行
  4. 判断結果と注文結果をDynamoDBに保存

### 2. エージェント設計

#### BaseAgent（基底クラス）
- `decide()`: 取引判断メソッド（抽象メソッド）
- `get_agent_type()`: エージェントタイプを返す

#### 実装エージェント
- **SimpleAgent**: 移動平均クロスオーバー戦略
- **LSTMAgent**: LSTMモデルを使用した予測ベース戦略

#### エージェントの拡張
新しいエージェントを追加する場合:
1. `BaseAgent`を継承
2. `decide()`メソッドを実装
3. `trading_agent/lambda_function.py`の`create_agents()`に追加

### 3. トレーダー設計

#### BaseTrader（基底クラス）
- `execute_order()`: 注文実行メソッド（抽象メソッド）
- `get_balance()`: 残高取得メソッド
- `get_trader_type()`: トレーダータイプを返す

#### 実装トレーダー
- **RESTTrader**: REST API経由で注文を実行

#### トレーダーの拡張
新しいトレーダーを追加する場合:
1. `BaseTrader`を継承
2. 必要なメソッドを実装
3. `trading_agent/lambda_function.py`の`create_traders()`に追加

### 4. DynamoDBスキーマ

#### prices テーブル
- **パーティションキー**: timestamp (String)
- **用途**: 価格データの時系列保存

#### decisions テーブル
- **パーティションキー**: agent_id (String)
- **ソートキー**: timestamp (String)
- **用途**: エージェントの取引判断履歴

#### orders テーブル
- **パーティションキー**: order_id (String)
- **GSI**: agent-timestamp-index (agent_id, timestamp)
- **用途**: 注文履歴

#### performance テーブル
- **パーティションキー**: agent_id (String)
- **用途**: エージェントのパフォーマンス集計

#### simulations テーブル
- **パーティションキー**: simulation_id (String)
- **用途**: シミュレーション結果の保存

### 5. データフロー

```
EventBridge (5分ごと)
    ↓
price_fetcher Lambda
    ↓
CoinGecko API
    ↓
DynamoDB (prices)
    ↓
trading_agent Lambda
    ↓
各エージェントで判断
    ↓
Trader経由で注文実行（必要に応じて）
    ↓
DynamoDB (decisions, orders, performance)
    ↓
React Frontend (Server Actions経由)
```

### 6. コスト最適化

- **Lambda**: オンデマンド実行、最小メモリサイズ
- **DynamoDB**: PAY_PER_REQUEST（オンデマンド課金）
- **EventBridge**: 5分間隔（必要に応じて調整可能）

### 7. セキュリティ

- IAMロールで最小権限の原則
- APIキーは環境変数で管理（AWS Secrets Manager推奨）
- DynamoDBアクセスはIAMポリシーで制限

### 8. 拡張性

- エージェントとトレーダーはプラグイン形式で追加可能
- 設定は環境変数またはEventBridgeペイロードで管理
- モニタリングはCloudWatch Logsで実現

## 推奨事項

### Lambda関数設計

1. **共通コードの共有**
   - `shared/`ディレクトリを各Lambda関数のデプロイパッケージに含める
   - または、Lambda Layerとして共有

2. **エラーハンドリング**
   - 各Lambda関数で適切なエラーハンドリング
   - CloudWatch Logsに詳細ログを出力

3. **タイムアウト設定**
   - デフォルト300秒（必要に応じて調整）
   - 長時間処理はStep Functionsを検討

### DynamoDB設計

1. **クエリパターン**
   - 時系列データはタイムスタンプをソートキーに
   - 頻繁なクエリにはGSIを活用

2. **データ保持**
   - 古いデータは定期的にアーカイブ（S3など）
   - TTL属性で自動削除も可能

### 機械学習

1. **モデル管理**
   - 学習済みモデルはS3に保存
   - Lambda関数でS3からダウンロード（初回のみ）

2. **推論最適化**
   - TensorFlow Liteなど軽量モデルを検討
   - モデルサイズが大きい場合はLambda Layerを活用

### フロントエンド

1. **Server Actions**
   - Next.js App RouterのServer Actionsを使用
   - サーバーサイドでDynamoDBアクセス

2. **リアルタイム更新**
   - ポーリング（現在の実装）
   - または、WebSocket/Server-Sent Eventsでリアルタイム更新

## デプロイメント

### Lambda関数のデプロイ

```bash
# 各Lambda関数のディレクトリで
cd lambda/price_fetcher
zip -r deployment.zip . -x "*.pyc" "__pycache__/*"
# Terraformで自動デプロイ、またはAWS CLIで手動デプロイ
```

### Terraformデプロイ

```bash
cd infra
terraform init
terraform plan
terraform apply
```

## モニタリング

- CloudWatch Logs: Lambda関数のログ
- CloudWatch Metrics: Lambda実行回数、エラー率
- DynamoDB Metrics: 読み書きスループット


