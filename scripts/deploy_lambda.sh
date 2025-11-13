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
        if [ -f "../requirements.txt" ]; then
            pip install -r ../requirements.txt -t .
        fi
        
        # sharedディレクトリをコピー
        cp -r "../../$SHARED_DIR" .
        
        # デプロイパッケージを作成
        zip -r deployment.zip . -x "*.pyc" "__pycache__/*" "*.git*" "*.md"
        
        echo "Created deployment.zip for $func_name"
        cd - > /dev/null
    fi
done

echo "All Lambda functions packaged successfully!"


