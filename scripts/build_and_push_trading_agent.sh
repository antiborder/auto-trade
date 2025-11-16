#!/bin/bash
# trading_agent Lambda関数のDockerイメージをビルドしてECRにプッシュするスクリプト

set -e

# 設定
AWS_REGION="${AWS_REGION:-ap-northeast-1}"
PROJECT_NAME="auto-trade"
ECR_REPO="${PROJECT_NAME}-trading-agent"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# AWSプロファイルを確認（auto-tradeプロファイルをデフォルトとして使用）
if [ -z "$AWS_PROFILE" ]; then
    export AWS_PROFILE=auto-trade
    echo "Using AWS_PROFILE=auto-trade (auto-trade-dev-user)"
else
    echo "Using AWS_PROFILE=$AWS_PROFILE"
fi

# ECRリポジトリのURIを取得
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

echo "Building Docker image for trading_agent..."
echo "ECR Repository: ${ECR_URI}"
echo "Image Tag: ${IMAGE_TAG}"

# 作業ディレクトリに移動
cd "$(dirname "$0")/../lambda/trading_agent"

# sharedディレクトリをコピー（Dockerfileで使用するため）
if [ ! -d "shared" ]; then
    echo "Copying shared directory..."
    cp -r ../../shared .
fi

# Dockerイメージをビルド（Lambdaはx86_64アーキテクチャをサポート）
echo "Building Docker image for x86_64 (Lambda compatible)..."
docker buildx build --platform linux/amd64 -t ${ECR_REPO}:${IMAGE_TAG} --load .

# ECRにログイン
echo "Logging in to ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# イメージにタグを付ける
echo "Tagging image..."
docker tag ${ECR_REPO}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}

# ECRにプッシュ
echo "Pushing image to ECR..."
docker push ${ECR_URI}:${IMAGE_TAG}

echo "✅ Successfully pushed ${ECR_URI}:${IMAGE_TAG}"
echo ""
echo "Next steps:"
echo "1. Run 'terraform apply' to update the Lambda function"
echo "2. Or update the Lambda function manually:"
echo "   aws lambda update-function-code --function-name ${PROJECT_NAME}-trading-agent --image-uri ${ECR_URI}:${IMAGE_TAG}"

