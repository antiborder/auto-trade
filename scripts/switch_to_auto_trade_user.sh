#!/bin/bash
# auto-trade-dev-userに切り替えるスクリプト

PROFILE_NAME="auto-trade"

echo "=========================================="
echo "auto-trade-dev-userに切り替えます"
echo "=========================================="
echo ""

# 方法1: 既存のアクセスキーがある場合
if [ -n "$AUTO_TRADE_ACCESS_KEY_ID" ] && [ -n "$AUTO_TRADE_SECRET_ACCESS_KEY" ]; then
    echo "環境変数から認証情報を設定します..."
    aws configure set aws_access_key_id "$AUTO_TRADE_ACCESS_KEY_ID" --profile "$PROFILE_NAME"
    aws configure set aws_secret_access_key "$AUTO_TRADE_SECRET_ACCESS_KEY" --profile "$PROFILE_NAME"
    aws configure set region "ap-northeast-1" --profile "$PROFILE_NAME"
    echo "✅ 認証情報を設定しました"
else
    echo "⚠️  環境変数 AUTO_TRADE_ACCESS_KEY_ID と AUTO_TRADE_SECRET_ACCESS_KEY が設定されていません"
    echo ""
    echo "以下のいずれかの方法で設定してください:"
    echo ""
    echo "方法1: 環境変数を使用"
    echo "  export AUTO_TRADE_ACCESS_KEY_ID='your-access-key-id'"
    echo "  export AUTO_TRADE_SECRET_ACCESS_KEY='your-secret-access-key'"
    echo "  ./scripts/switch_to_auto_trade_user.sh"
    echo ""
    echo "方法2: 手動で設定"
    echo "  aws configure --profile auto-trade"
    echo "  # Access Key ID: [auto-trade-dev-userのアクセスキー]"
    echo "  # Secret Access Key: [auto-trade-dev-userのシークレットキー]"
    echo "  # Default region: ap-northeast-1"
    echo ""
    echo "方法3: アクセスキーを新規作成（管理者権限が必要）"
    echo "  aws iam create-access-key --user-name auto-trade-dev-user"
    exit 1
fi

echo ""
echo "認証情報を確認中..."
aws sts get-caller-identity --profile "$PROFILE_NAME"

echo ""
echo "=========================================="
echo "✅ 設定完了！"
echo ""
echo "使用方法:"
echo "  export AWS_PROFILE=$PROFILE_NAME"
echo "  または"
echo "  コマンドに --profile $PROFILE_NAME を追加"
echo "=========================================="

