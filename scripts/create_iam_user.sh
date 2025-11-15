#!/bin/bash
# auto-tradeプロジェクト用のIAMユーザーとポリシーを作成するスクリプト
# 注意: このスクリプトを実行するには管理者権限が必要です

USER_NAME="auto-trade-dev-user"
POLICY_NAME="auto-trade-terraform-policy"

echo "Creating IAM user: $USER_NAME"

# IAMユーザーを作成
aws iam create-user --user-name "$USER_NAME"

# ポリシードキュメントを作成
cat > /tmp/auto-trade-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "events:PutRule",
        "events:DeleteRule",
        "events:DescribeRule",
        "events:PutTargets",
        "events:RemoveTargets",
        "events:ListTargetsByRule"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:ListRolePolicies",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:PassRole"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:ListFunctions"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:ListTables",
        "dynamodb:UpdateTable"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups"
      ],
      "Resource": "*"
    }
  ]
}
EOF

echo "Creating IAM policy: $POLICY_NAME"
aws iam create-policy \
  --policy-name "$POLICY_NAME" \
  --policy-document file:///tmp/auto-trade-policy.json \
  --description "Policy for auto-trade Terraform operations"

# ポリシーARNを取得
POLICY_ARN=$(aws iam list-policies --query "Policies[?PolicyName=='$POLICY_NAME'].Arn" --output text)

if [ -z "$POLICY_ARN" ]; then
  echo "Error: Failed to get policy ARN"
  exit 1
fi

echo "Attaching policy to user: $USER_NAME"
aws iam attach-user-policy \
  --user-name "$USER_NAME" \
  --policy-arn "$POLICY_ARN"

echo ""
echo "=========================================="
echo "IAM User created successfully!"
echo "=========================================="
echo "User Name: $USER_NAME"
echo "Policy ARN: $POLICY_ARN"
echo ""
echo "Next steps:"
echo "1. Create access keys for this user:"
echo "   aws iam create-access-key --user-name $USER_NAME"
echo ""
echo "2. Configure AWS CLI with the new credentials:"
echo "   aws configure --profile auto-trade"
echo ""
echo "3. Use the new profile with Terraform:"
echo "   export AWS_PROFILE=auto-trade"
echo "   cd infra && terraform apply"
echo "=========================================="


