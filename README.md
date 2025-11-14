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

1. 機械学習モデルの学習（上記の手順を参照）
2. 学習済みモデルをS3にアップロード
3. Lambda関数をデプロイ
4. EventBridgeルールを有効化
5. Reactアプリでモニタリング

## ライセンス

MIT


