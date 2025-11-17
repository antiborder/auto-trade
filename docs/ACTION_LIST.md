# アクションリスト

## 📋 現在の状況

✅ **完了済み**
- `GateIOTestTrader`クラスの実装（Testnet用）
- `GateIOLiveTrader`クラスの実装（本番環境用）
- Terraform変数の追加（`gateio_test_api_key`, `gateio_test_api_secret`, `gateio_api_key`, `gateio_api_secret`）
- Lambda関数の環境変数更新（`GATEIO_TEST_API_KEY`, `GATEIO_TEST_API_SECRET`）
- Lambda関数のコード更新（`GateIOTestTrader`を使用）

## 🚀 次のステップ

### 1. 変更をデプロイ（必須）

```bash
# プロジェクトルートで実行
make apply
```

このコマンドは以下を実行します：
- Terraformの初期化
- Lambda関数のパッケージ化（Dockerイメージビルド含む）
- Terraformの適用（環境変数の更新含む）

**注意**: 初回デプロイには数分かかる場合があります。

---

### 2. デプロイ後の動作確認（必須）

#### 2.1 Lambda関数のログを確認

```bash
# trading_agent Lambda関数の最新ログを確認
export AWS_PROFILE=auto-trade
aws logs tail /aws/lambda/auto-trade-trading-agent --follow --since 10m
```

**確認ポイント**:
- ✅ `GATEIO_TEST_API_KEY exists: True`
- ✅ `GATEIO_TEST_API_SECRET exists: True`
- ✅ `Response status: 200`（残高取得が成功）
- ✅ `Balance saved: USDT=..., BTC=...`（残高がDynamoDBに保存されている）

#### 2.2 DynamoDBテーブルの確認

```bash
# balanceテーブルに最新データが保存されているか確認
aws dynamodb scan \
  --table-name auto-trade-balance \
  --limit 5 \
  --region ap-northeast-1 \
  --profile auto-trade
```

**確認ポイント**:
- ✅ 最新のタイムスタンプでデータが存在する
- ✅ `usdt_balance`と`btc_balance`が正しく保存されている

#### 2.3 フロントエンドの確認

```bash
# フロントエンドを起動（別ターミナル）
cd frontend
npm run dev
```

ブラウザで `http://localhost:3000` にアクセスして以下を確認：
- ✅ 価格チャートに最新データが表示される
- ✅ 残高チャートに最新データが表示される（最近20分以内のデータ）
- ✅ Agent Performanceセクションが表示される（データがない場合は空でもOK）

---

### 3. 問題が発生した場合のトラブルシューティング

#### 3.1 署名エラー（401 Unauthorized）が発生する場合

```bash
# Lambdaログを確認
aws logs tail /aws/lambda/auto-trade-trading-agent --since 30m | grep -i "signature\|401"
```

**対処法**:
- APIキーとシークレットが正しく設定されているか確認
- `terraform.tfvars`の値が正しいか確認
- Gate.io TestnetのAPIキーが有効か確認

#### 3.2 残高データがDynamoDBに保存されない場合

```bash
# Lambdaログを確認
aws logs tail /aws/lambda/auto-trade-trading-agent --since 30m | grep -i "balance\|dynamodb"
```

**対処法**:
- IAMロールに`balance`テーブルへの`PutItem`権限があるか確認
- Terraformの`infra/lambda.tf`で`balance`テーブルがリソースリストに含まれているか確認

#### 3.3 フロントエンドにデータが表示されない場合

```bash
# ブラウザのコンソールでエラーを確認
# または、フロントエンドのログを確認
cd frontend
npm run dev
# ブラウザの開発者ツール（F12）でコンソールタブを確認
```

**対処法**:
- AWS認証情報が正しく設定されているか確認
- 環境変数（`PRICES_TABLE`, `BALANCE_TABLE`など）が正しく設定されているか確認

---

### 4. 本番環境への切り替え準備（将来のタスク）

本番環境で`GateIOLiveTrader`を使用する場合は、以下を実行：

#### 4.1 Lambda関数のコードを更新

`lambda/trading_agent/lambda_function.py`を編集：

```python
# 変更前
from shared.traders.gateio_trader import GateIOTestTrader
gateio_test_api_key = os.getenv('GATEIO_TEST_API_KEY')
gateio_test_api_secret = os.getenv('GATEIO_TEST_API_SECRET')
gateio_trader = GateIOTestTrader(...)

# 変更後
from shared.traders.gateio_trader import GateIOLiveTrader
gateio_api_key = os.getenv('GATEIO_API_KEY')
gateio_api_secret = os.getenv('GATEIO_API_SECRET')
gateio_trader = GateIOLiveTrader(
    trader_id='gateio-live-trader-1',
    api_key=gateio_api_key,
    api_secret=gateio_api_secret
)
```

#### 4.2 Terraformの環境変数を更新

`infra/lambda.tf`を編集：

```terraform
environment {
  variables = {
    # ... 他の変数 ...
    GATEIO_API_KEY    = var.gateio_api_key      # テスト用から本番用に変更
    GATEIO_API_SECRET = var.gateio_api_secret   # テスト用から本番用に変更
    # GATEIO_TESTNET は削除（GateIOLiveTraderは常に本番環境）
  }
}
```

#### 4.3 デプロイ

```bash
make apply
```

**⚠️ 警告**: 本番環境への切り替えは、十分なテストを行った後に実行してください。

---

### 5. 定期的な確認タスク

#### 5.1 毎日確認すべき項目

- [ ] Lambda関数が正常に実行されているか（CloudWatch Logsで確認）
- [ ] 価格データが定期的に取得されているか（DynamoDBの`prices`テーブルを確認）
- [ ] 残高データが定期的に更新されているか（DynamoDBの`balance`テーブルを確認）
- [ ] エラーが発生していないか（Lambdaログで確認）

#### 5.2 週次確認タスク

- [ ] 取引エージェントのパフォーマンスを確認（フロントエンドのAgent Performanceセクション）
- [ ] 注文履歴を確認（DynamoDBの`orders`テーブル）
- [ ] コストを確認（AWS Cost Explorer）

---

### 6. 緊急時の対応

#### 6.1 Lambda関数が実行されない場合

```bash
# EventBridgeルールの状態を確認
aws events describe-rule --name auto-trade-trading-agent-schedule --profile auto-trade

# ルールが無効になっている場合は有効化
aws events enable-rule --name auto-trade-trading-agent-schedule --profile auto-trade
```

#### 6.2 誤った注文が実行された場合（本番環境）

1. **即座にLambda関数を無効化**:
   ```bash
   aws events disable-rule --name auto-trade-trading-agent-schedule --profile auto-trade
   ```

2. **ログを確認して原因を特定**

3. **必要に応じて手動で注文をキャンセル**（Gate.ioのWebインターフェースから）

---

## 📝 チェックリスト

デプロイ前:
- [ ] `terraform.tfvars`に正しいAPIキーが設定されている
- [ ] コードの変更がコミットされている（推奨）
- [ ] テスト環境で動作確認が完了している

デプロイ後:
- [ ] Lambda関数のログにエラーがない
- [ ] DynamoDBにデータが保存されている
- [ ] フロントエンドにデータが表示されている
- [ ] 残高チャートに最新データが表示されている

---

## 🔗 関連ドキュメント

- [デプロイメントガイド](./DEPLOYMENT.md)
- [アーキテクチャ設計](./ARCHITECTURE.md)
- [IAM設定ガイド](./IAM_SETUP.md)
- [シークレット管理](./SECRETS_MANAGEMENT.md)

---

## 📞 サポート

問題が解決しない場合は、以下を確認：
1. AWS CloudWatch Logsで詳細なエラーログを確認
2. Terraformの状態を確認（`terraform plan`）
3. IAMロールの権限を確認

