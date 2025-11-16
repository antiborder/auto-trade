.PHONY: help init deploy-lambda build-trading-agent deploy clean

# デフォルトのターゲット
.DEFAULT_GOAL := help

# 変数定義
AWS_REGION ?= ap-northeast-1
PROJECT_NAME ?= auto-trade
ECR_REPO ?= $(PROJECT_NAME)-trading-agent
IMAGE_TAG ?= latest
TERRAFORM_DIR = infra
LAMBDA_DIR = lambda
SCRIPTS_DIR = scripts

help: ## このヘルプメッセージを表示
	@echo "利用可能なコマンド:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

init: ## Terraformを初期化
	@echo "🔧 Terraformを初期化中..."
	cd $(TERRAFORM_DIR) && terraform init

package-lambda: ## Lambda関数のZIPパッケージを作成（price_fetcher用）
	@echo "📦 Lambda関数のパッケージを作成中..."
	@chmod +x $(SCRIPTS_DIR)/deploy_lambda.sh
	@$(SCRIPTS_DIR)/deploy_lambda.sh

build-trading-agent: ## trading_agentのDockerイメージをビルドしてECRにプッシュ
	@echo "🐳 trading_agentのDockerイメージをビルド中..."
	@chmod +x $(SCRIPTS_DIR)/build_and_push_trading_agent.sh
	@AWS_PROFILE=auto-trade AWS_REGION=$(AWS_REGION) IMAGE_TAG=$(IMAGE_TAG) $(SCRIPTS_DIR)/build_and_push_trading_agent.sh

deploy-lambda: package-lambda build-trading-agent ## Lambda関数をデプロイ（パッケージ作成 + Dockerイメージビルド）

plan: init ## Terraformの実行計画を表示
	@echo "📋 Terraformの実行計画を表示中..."
	cd $(TERRAFORM_DIR) && terraform plan

apply: init deploy-lambda ## すべてをデプロイ（Terraform init + Lambdaデプロイ + Terraform apply）
	@echo "🚀 インフラストラクチャをデプロイ中..."
	cd $(TERRAFORM_DIR) && terraform apply -auto-approve
	@echo "✅ デプロイが完了しました！"

destroy: ## インフラストラクチャを削除（注意: すべてのリソースが削除されます）
	@echo "⚠️  インフラストラクチャを削除中..."
	cd $(TERRAFORM_DIR) && terraform destroy

clean: ## ビルド成果物をクリーンアップ
	@echo "🧹 ビルド成果物をクリーンアップ中..."
	@find $(LAMBDA_DIR) -name "deployment.zip" -delete
	@find $(LAMBDA_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find $(LAMBDA_DIR) -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
	@find $(LAMBDA_DIR) -name "six.py" -delete 2>/dev/null || true
	@echo "✅ クリーンアップが完了しました"

clean-all: clean ## すべてのビルド成果物とPythonパッケージを削除
	@echo "🧹 すべてのビルド成果物をクリーンアップ中..."
	@for dir in $(LAMBDA_DIR)/price_fetcher $(LAMBDA_DIR)/trading_agent; do \
		if [ -d "$$dir" ]; then \
			cd $$dir && \
			rm -rf bin boto3 botocore certifi charset_normalizer dateutil idna jmespath requests s3transfer urllib3 *.dist-info six.py python_dateutil-*.dist-info six-*.dist-info shared 2>/dev/null || true && \
			cd - > /dev/null; \
		fi \
	done
	@echo "✅ 完全なクリーンアップが完了しました"

validate: ## Terraformの設定を検証
	@echo "✔️  Terraformの設定を検証中..."
	cd $(TERRAFORM_DIR) && terraform validate

fmt: ## Terraformの設定ファイルをフォーマット
	@echo "📝 Terraformの設定ファイルをフォーマット中..."
	cd $(TERRAFORM_DIR) && terraform fmt

outputs: ## Terraformの出力を表示
	@echo "📤 Terraformの出力:"
	cd $(TERRAFORM_DIR) && terraform output

status: ## デプロイメントの状態を確認
	@echo "📊 デプロイメントの状態:"
	@echo ""
	@echo "Lambda関数:"
	@aws lambda list-functions --query 'Functions[?contains(FunctionName, `$(PROJECT_NAME)`)].{Name:FunctionName, Runtime:Runtime, LastModified:LastModified}' --output table 2>/dev/null || echo "  Lambda関数を取得できませんでした"
	@echo ""
	@echo "EventBridgeルール:"
	@aws events list-rules --name-prefix $(PROJECT_NAME) --query 'Rules[*].{Name:Name, ScheduleExpression:ScheduleExpression, State:State}' --output table 2>/dev/null || echo "  EventBridgeルールを取得できませんでした"
	@echo ""
	@echo "DynamoDBテーブル:"
	@aws dynamodb list-tables --query 'TableNames[?contains(@, `$(PROJECT_NAME)`)]' --output table 2>/dev/null || echo "  DynamoDBテーブルを取得できませんでした"

