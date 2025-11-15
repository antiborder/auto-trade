# 機密情報の管理方法

## 概要

APIキーなどの機密情報を安全に管理する方法について説明します。

## 方法の比較

### 1. `terraform.tfvars`（現在の方法）

**メリット:**
- Terraformの標準的な方法
- インフラ設定と一緒に管理できる
- `.gitignore`に追加すればGitにコミットされない

**デメリット:**
- ローカルファイルに平文で保存される
- ファイルを誤って共有するリスク
- チーム間で共有する際に安全な方法が必要

**使用方法:**
```bash
# terraform.tfvars を作成（.gitignoreに含まれている）
cat > infra/terraform.tfvars << EOF
bybit_api_key    = "YOUR_API_KEY"
bybit_api_secret = "YOUR_API_SECRET"
bybit_testnet    = true
EOF

# デプロイ
cd infra
terraform apply
```

### 2. `config.json`（以前の方法）

**メリット:**
- Lambda関数内で直接使用できる
- JSON形式で構造化された設定

**デメリット:**
- デプロイ時にZIPに含まれる可能性がある
- ローカルファイルに平文で保存される
- `.gitignore`に追加する必要がある

**使用方法:**
```json
{
  "bybit_api_key": "YOUR_API_KEY",
  "bybit_api_secret": "YOUR_API_SECRET",
  "bybit_testnet": true
}
```

### 3. AWS Secrets Manager（推奨・最も安全）

**メリット:**
- AWSが管理する安全なストレージ
- 暗号化されて保存される
- IAMでアクセス制御可能
- ローテーション機能あり
- 監査ログが記録される

**デメリット:**
- 追加のAWSコスト（月額約$0.40/シークレット）
- 実装がやや複雑

**使用方法:**
```bash
# シークレットを作成
aws secretsmanager create-secret \
  --name auto-trade/bybit-credentials \
  --secret-string '{"api_key":"YOUR_API_KEY","api_secret":"YOUR_API_SECRET","testnet":true}'

# Terraformで参照
# infra/secrets.tf に追加
resource "aws_secretsmanager_secret" "bybit_credentials" {
  name = "${var.project_name}/bybit-credentials"
}

# Lambda関数で使用
# lambda/trading_agent/lambda_function.py で取得
```

## 推奨事項

### 開発環境
- **`terraform.tfvars`を使用**（`.gitignore`に追加済み）
- ローカル開発用の設定ファイルとして使用

### 本番環境
- **AWS Secrets Managerを使用**（推奨）
- より安全で、監査可能

## セキュリティチェックリスト

- [x] `.gitignore`に`*.tfvars`を追加
- [x] `.gitignore`に`**/config.json`を追加
- [ ] `terraform.tfvars`をGitにコミットしていないことを確認
- [ ] `config.json`をGitにコミットしていないことを確認
- [ ] 本番環境ではSecrets Managerを使用することを検討

## 現在の設定

現在は`terraform.tfvars`を使用しています。これは開発環境では問題ありませんが、本番環境ではSecrets Managerへの移行を推奨します。

