#!/bin/bash
# IAMポリシーを更新するスクリプト（管理者権限が必要）

set -e

USER_NAME="${1:-auto-trade-dev-user}"
POLICY_NAME="AutoTradePolicy"
POLICY_FILE="docs/complete_iam_policy.json"

echo "IAMポリシーを更新します..."
echo "ユーザー: $USER_NAME"
echo "ポリシー名: $POLICY_NAME"
echo ""

# ポリシーファイルの存在確認
if [ ! -f "$POLICY_FILE" ]; then
    echo "❌ エラー: $POLICY_FILE が見つかりません"
    exit 1
fi

# ポリシーを適用
echo "ポリシーを適用中..."
aws iam put-user-policy \
    --user-name "$USER_NAME" \
    --policy-name "$POLICY_NAME" \
    --policy-document "file://$POLICY_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ ポリシーを更新しました"
    echo ""
    echo "追加された権限:"
    echo "  - logs:DescribeLogStreams"
    echo "  - logs:GetLogEvents"
    echo "  - logs:FilterLogEvents"
    echo "  - logs:ListTagsLogGroup"
else
    echo ""
    echo "❌ ポリシーの更新に失敗しました"
    echo "管理者権限が必要です。AWSコンソールから手動で更新してください。"
    exit 1
fi

