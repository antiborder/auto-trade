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
│   ├── price_fetcher/        # 価格取得関数（ZIPデプロイ）
│   ├── trading_agent/        # 取引エージェント関数（Dockerイメージ）
│   └── requirements.txt     # 共通依存関係
├── infra/                     # Terraform定義
│   ├── lambda.tf             # Lambda関数定義
│   ├── dynamodb.tf           # DynamoDBテーブル定義
│   ├── eventbridge.tf        # EventBridgeルール定義
│   ├── s3.tf                 # S3バケット定義（Lambdaデプロイ用）
│   ├── ecr.tf                # ECRリポジトリ定義
│   ├── main.tf               # プロバイダー設定
│   ├── variables.tf          # 変数定義
│   └── outputs.tf            # 出力定義
├── ml/                        # 機械学習
│   ├── train/                # 学習スクリプト
│   └── models/               # 学習済みモデル
├── frontend/                  # Reactアプリ（Next.js）
│   ├── app/                  # Next.js App Router
│   ├── components/           # Reactコンポーネント
│   └── server-actions/       # DynamoDBアクセス
├── shared/                    # 共通コード
│   ├── agents/               # エージェントロジック
│   ├── traders/              # トレーダー実装
│   ├── models/               # データモデル
│   └── dynamodb/             # DynamoDBクライアント
├── simulation/                # シミュレーション
│   ├── engine/               # シミュレーションエンジン
│   └── api/                  # シミュレーションAPI
├── scripts/                   # デプロイスクリプト
│   ├── deploy_lambda.sh      # Lambdaパッケージ化スクリプト
│   ├── build_and_push_trading_agent.sh  # Dockerイメージビルド
│   ├── create_iam_user.sh    # IAMユーザー作成
│   └── setup_aws_credentials.sh  # AWS認証情報設定
├── docs/                      # ドキュメント
│   ├── IAM_SETUP.md          # IAM設定ガイド
│   └── complete_iam_policy.json  # IAMポリシー
└── Makefile                   # デプロイ自動化
```

## セットアップ

### 前提条件

- Python 3.11+
- Node.js 18+
- Terraform 1.5+
- AWS CLI設定済み
- Docker（trading_agentのコンテナイメージビルド用）
- Make（デプロイ自動化用）

### インストール

```bash
# フロントエンド依存関係
cd frontend && npm install
```

**注意**: Lambda関数の依存関係は`make deploy-lambda`または`make apply`実行時に自動的にインストールされます。

## デプロイ

### Makefileを使用した自動デプロイ（推奨）

プロジェクトルートで以下のコマンドを実行します：

```bash
# すべてをデプロイ（Terraform init + Lambdaデプロイ + Terraform apply）
make apply

# 個別のステップを実行する場合
make init              # Terraformを初期化
make deploy-lambda      # Lambda関数をパッケージ化（ZIP + Dockerイメージ）
make plan              # Terraformの実行計画を表示
make apply             # すべてをデプロイ
```

**利用可能なコマンド:**

```bash
make help              # すべてのコマンドを表示
make init              # Terraformを初期化
make package-lambda    # Lambda関数のZIPパッケージを作成
make build-trading-agent  # trading_agentのDockerイメージをビルドしてECRにプッシュ
make deploy-lambda      # Lambda関数をデプロイ（パッケージ作成 + Dockerイメージビルド）
make plan              # Terraformの実行計画を表示
make apply             # すべてをデプロイ（推奨）
make destroy           # インフラストラクチャを削除（注意）
make clean             # ビルド成果物をクリーンアップ
make clean-all         # すべてのビルド成果物とPythonパッケージを削除
make validate          # Terraformの設定を検証
make fmt               # Terraformの設定ファイルをフォーマット
make outputs           # Terraformの出力を表示
make status            # デプロイメントの状態を確認
```

### 手動デプロイ

Makefileを使用しない場合の手動デプロイ手順は`DEPLOYMENT.md`を参照してください。

### IAM設定

デプロイ前にIAMユーザーとポリシーの設定が必要です。詳細は`docs/IAM_SETUP.md`を参照してください。

```bash
# IAMユーザーを作成（管理者権限が必要）
./scripts/create_iam_user.sh

# AWS認証情報を設定
./scripts/setup_aws_credentials.sh
```

## 機械学習モデルの学習と評価

### 1. 仮想環境のセットアップ

```bash
# プロジェクトルートで仮想環境を作成
python3 -m venv venv

# 仮想環境をアクティベート
source venv/bin/activate  # macOS/Linux
# または
# venv\Scripts\activate  # Windows

# 必要なパッケージをインストール
pip install pandas numpy tensorflow scikit-learn matplotlib
```

### 2. テストデータの生成

Bitcoin価格のテストデータを生成します。実際のBitcoin価格の特徴（ランダムウォーク、ボラティリティ、トレンド）を模倣した時系列データを生成します。

```bash
# 基本的なデータ生成（365日分、1時間ごと）
python scripts/generate_test_data.py \
  --output data/btc_prices.csv \
  --days 365 \
  --realistic

# カスタムパラメータで生成
python scripts/generate_test_data.py \
  --output data/btc_prices.csv \
  --start-date 2023-01-01 \
  --days 365 \
  --initial-price 30000.0 \
  --volatility 0.02 \
  --trend 0.0001 \
  --realistic
```

**パラメータ説明:**
- `--output`: 出力CSVファイルのパス
- `--start-date`: 開始日（YYYY-MM-DD形式）
- `--days`: 生成する日数
- `--initial-price`: 初期価格（USD）
- `--volatility`: ボラティリティ（1日の変動率の標準偏差）
- `--trend`: 1日あたりのトレンド（上昇率）
- `--realistic`: 現実的な特徴（急激な価格変動イベントなど）を追加

**生成されるデータ:**
- `timestamp`: タイムスタンプ（1時間ごと）
- `price`: Bitcoin価格（USD）

### 3. LSTMモデルの学習

生成したテストデータを使用してLSTMモデルを学習します。

```bash
cd ml/train

# 基本的な学習（デフォルト: 50エポック、バッチサイズ32）
python train_lstm.py \
  --data ../../data/btc_prices.csv \
  --output ../../ml/models/lstm_model.h5

# カスタムパラメータで学習
python train_lstm.py \
  --data ../../data/btc_prices.csv \
  --output ../../ml/models/lstm_model.h5 \
  --epochs 100 \
  --batch-size 32
```

**パラメータ説明:**
- `--data`: 学習データのCSVファイルパス
- `--output`: 学習済みモデルの保存先パス
- `--epochs`: エポック数（デフォルト: 50）
- `--batch-size`: バッチサイズ（デフォルト: 32）

**学習プロセス:**
1. 価格データを読み込み
2. 時系列データをシーケンスに変換（シーケンス長: 60）
3. データを正規化（MinMaxScaler）
4. 訓練データ（80%）と検証データ（20%）に分割
5. LSTMモデルを構築（3層、各50ユニット、Dropout 0.2）
6. モデルを学習
7. 学習済みモデルとスケーラー情報を保存

**生成されるファイル:**
- `ml/models/lstm_model.h5`: 学習済みモデル
- `ml/models/lstm_model_scaler.json`: スケーラー情報（正規化パラメータ）

### 4. 学習結果の評価

学習済みモデルの性能を評価し、可視化します。

```bash
cd ml/train

# モデルを評価
python evaluate_model.py \
  --model ../../ml/models/lstm_model.h5 \
  --data ../../data/btc_prices.csv \
  --output ../../ml/models/evaluation
```

**評価内容:**
1. **モデル構造の確認**: レイヤー構成、パラメータ数
2. **予測精度の評価**:
   - MSE (Mean Squared Error): 平均二乗誤差
   - MAE (Mean Absolute Error): 平均絶対誤差
   - RMSE (Root Mean Squared Error): 平方根平均二乗誤差
   - Direction Accuracy: 方向性精度（価格上昇/下降の予測精度）
3. **過学習チェック**: 訓練データとテストデータの性能比較
4. **可視化**:
   - 予測値 vs 実際の値の比較グラフ
   - 散布図（予測値 vs 実際の値）
   - 残差プロット
   - 誤差の分布

**生成されるファイル:**
- `ml/models/evaluation/model_evaluation.png`: 評価結果の可視化グラフ
- `ml/models/evaluation/metrics.json`: 詳細メトリクス（JSON形式）

**評価結果の見方:**
- **MSE/MAE/RMSE**: 値が小さいほど予測精度が高い
- **Direction Accuracy**: 価格の上昇/下降を正しく予測できた割合（高いほど良い）
- **Overfitting Ratio**: テストMAE / 訓練MAE
  - < 1.2: 良好な汎化性能
  - 1.2 - 1.5: 許容範囲
  - > 1.5: 過学習の可能性

### 5. モデルの改善

評価結果に基づいてモデルを改善する場合:

1. **エポック数を増やす**: より多くの学習で精度向上を目指す
2. **学習率の調整**: `train_lstm.py`の`optimizer`パラメータを調整
3. **モデル構造の変更**: レイヤー数、ユニット数を調整
4. **データの前処理**: 特徴量エンジニアリング、異常値処理
5. **ハイパーパラメータチューニング**: バッチサイズ、ドロップアウト率など

### 6. 学習済みモデルのデプロイ

学習済みモデルをAWS Lambdaで使用する場合:

```bash
# S3バケットにアップロード
aws s3 cp ml/models/lstm_model.h5 s3://your-bucket/models/lstm_model.h5
aws s3 cp ml/models/lstm_model_scaler.json s3://your-bucket/models/lstm_model_scaler.json
```

Lambda関数の環境変数にモデルパスを設定:
```
MODEL_S3_BUCKET=your-bucket
MODEL_S3_KEY=models/lstm_model.h5
```

## 使用方法

### 1. 初期セットアップ

```bash
# IAMユーザーとポリシーを設定（初回のみ）
./scripts/create_iam_user.sh
./scripts/setup_aws_credentials.sh

# すべてをデプロイ
make apply
```

### 2. 機械学習モデルの学習（オプション）

```bash
# テストデータを生成
python scripts/generate_test_data.py --output data/btc_prices.csv --days 365 --realistic

# モデルを学習
cd ml/train
python train_lstm.py --data ../../data/btc_prices.csv --output ../../ml/models/lstm_model.h5
```

### 3. フロントエンドの起動

```bash
cd frontend
npm run dev
```

ブラウザで `http://localhost:3000` にアクセスしてモニタリング画面を表示します。

### 4. デプロイメントの状態確認

```bash
make status
```

### 5. シミュレーション実行

フロントエンドのシミュレーションページ（`/simulation`）から過去データを使用した取引シミュレーションを実行できます。

## トラブルシューティング

### Lambda関数が実行されない

- EventBridgeルールが有効になっているか確認: `make status`
- Lambda関数のログを確認: AWS CloudWatch Logs
- IAMロールの権限を確認: `docs/IAM_SETUP.md`

### Dockerイメージのビルドエラー

- Dockerが起動しているか確認
- `docker buildx`が利用可能か確認
- ECRへのアクセス権限を確認

### DynamoDBへのデータ保存エラー

- Lambda関数の環境変数（`PRICES_TABLE`など）が正しく設定されているか確認
- IAMロールにDynamoDBへの書き込み権限があるか確認

### 詳細なドキュメント

- **アーキテクチャ**: `ARCHITECTURE.md`
- **デプロイメント**: `DEPLOYMENT.md`
- **IAM設定**: `docs/IAM_SETUP.md`

## ライセンス

MIT


