#!/bin/bash
# Lambda関数のデプロイスクリプト

set -e

LAMBDA_DIR="lambda"
SHARED_DIR="shared"

# 各Lambda関数をデプロイ
for func_dir in "$LAMBDA_DIR"/*/; do
    if [ -f "$func_dir/lambda_function.py" ]; then
        func_name=$(basename "$func_dir")
        echo "Deploying $func_name..."
        
        cd "$func_dir"
        
        # 依存関係をインストール
        # 関数固有のrequirements.txtを優先、なければ共通のrequirements.txtを使用
        if [ -f "requirements.txt" ]; then
            python3 -m pip install -r requirements.txt -t .
        elif [ -f "../requirements.txt" ]; then
            python3 -m pip install -r ../requirements.txt -t .
        fi
        
        # sharedディレクトリをコピー（price_fetcherは使用しないので除外）
        if [ "$func_name" != "price_fetcher" ]; then
            cp -r "../../$SHARED_DIR" .
        fi
        
        # trading_agentの場合は、TensorFlow関連を除外（Layerから読み込むため）
        if [ "$func_name" = "trading_agent" ]; then
            find . -type d -name "tensorflow" -exec rm -rf {} + 2>/dev/null || true
            find . -type d -name "numpy" -exec rm -rf {} + 2>/dev/null || true
            find . -type d -name "*tensorflow*" -exec rm -rf {} + 2>/dev/null || true
            find . -type d -name "*numpy*" -exec rm -rf {} + 2>/dev/null || true
            find . -name "*tensorflow*.dist-info" -exec rm -rf {} + 2>/dev/null || true
            find . -name "*numpy*.dist-info" -exec rm -rf {} + 2>/dev/null || true
        fi
        
        # デプロイパッケージを作成
        zip -r deployment.zip . -x "*.pyc" "__pycache__/*" "*.git*" "*.md"
        
        echo "Created deployment.zip for $func_name"
        cd - > /dev/null
    fi
done

echo "All Lambda functions packaged successfully!"


