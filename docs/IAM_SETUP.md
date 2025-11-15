# IAMユーザーセットアップガイド

auto-tradeプロジェクト用のIAMユーザーを作成・設定する手順です。

## 方法1: AWS CLIで作成（管理者権限が必要）

### ステップ1: IAMユーザーとポリシーを作成

```bash
chmod +x scripts/create_iam_user.sh
./scripts/create_iam_user.sh
```

### ステップ2: アクセスキーを作成して設定

```bash
chmod +x scripts/setup_aws_credentials.sh
./scripts/setup_aws_credentials.sh
```

### ステップ3: 新しいプロファイルを使用

```bash
export AWS_PROFILE=auto-trade
cd infra
terraform apply
```

## 方法2: AWSコンソールで手動作成（推奨）

### ステップ1: IAMユーザーを作成

1. AWSコンソール → IAM → ユーザー → 「ユーザーを追加」
2. ユーザー名: `auto-trade-dev-user`
3. 「プログラムによるアクセス」を選択

### ステップ2: ポリシーを作成

1. IAM → ポリシー → 「ポリシーを作成」
2. JSONタブを選択し、以下のポリシーを貼り付け:

```json
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
```

3. ポリシー名: `auto-trade-terraform-policy`
4. 作成後、ユーザーにポリシーをアタッチ

### ステップ3: アクセスキーを作成

1. 作成したユーザーを選択
2. 「セキュリティ認証情報」タブ
3. 「アクセスキーを作成」
4. アクセスキーIDとシークレットアクセスキーを保存

### ステップ4: AWS CLIで設定

```bash
aws configure --profile auto-trade
# Access Key ID: [上記で取得したキー]
# Secret Access Key: [上記で取得したキー]
# Default region: ap-northeast-1
# Default output format: json
```

### ステップ5: プロファイルを使用

```bash
export AWS_PROFILE=auto-trade
cd infra
terraform apply
```

## 確認

新しいプロファイルが正しく設定されているか確認:

```bash
aws sts get-caller-identity --profile auto-trade
```

出力に `auto-trade-dev-user` が表示されれば成功です。


