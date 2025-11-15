#!/bin/bash
# 新しいIAMユーザーのアクセスキーを設定するスクリプト

USER_NAME="auto-trade-dev-user"
PROFILE_NAME="auto-trade"

echo "Creating access key for user: $USER_NAME"
OUTPUT=$(aws iam create-access-key --user-name "$USER_NAME" --output json)

ACCESS_KEY_ID=$(echo $OUTPUT | jq -r '.AccessKey.AccessKeyId')
SECRET_ACCESS_KEY=$(echo $OUTPUT | jq -r '.AccessKey.SecretAccessKey')

if [ -z "$ACCESS_KEY_ID" ] || [ -z "$SECRET_ACCESS_KEY" ]; then
  echo "Error: Failed to create access key"
  exit 1
fi

echo ""
echo "=========================================="
echo "Access Key created successfully!"
echo "=========================================="
echo "Access Key ID: $ACCESS_KEY_ID"
echo "Secret Access Key: $SECRET_ACCESS_KEY"
echo ""
echo "⚠️  IMPORTANT: Save these credentials securely!"
echo "   The Secret Access Key will only be shown once."
echo ""
echo "Configuring AWS CLI profile: $PROFILE_NAME"
echo ""

# AWS CLIでプロファイルを設定
aws configure set aws_access_key_id "$ACCESS_KEY_ID" --profile "$PROFILE_NAME"
aws configure set aws_secret_access_key "$SECRET_ACCESS_KEY" --profile "$PROFILE_NAME"
aws configure set region "ap-northeast-1" --profile "$PROFILE_NAME"

echo "AWS CLI profile '$PROFILE_NAME' configured!"
echo ""
echo "To use this profile:"
echo "  export AWS_PROFILE=$PROFILE_NAME"
echo "  cd infra && terraform apply"
echo "=========================================="


