# Lambda関数用のIAMロール
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# DynamoDBアクセス権限
resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "${var.project_name}-lambda-dynamodb-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.prices.arn,
          aws_dynamodb_table.decisions.arn,
          aws_dynamodb_table.orders.arn,
          aws_dynamodb_table.performance.arn,
          aws_dynamodb_table.simulations.arn,
          aws_dynamodb_table.balance.arn
        ]
      }
    ]
  })
}

# CloudWatch Logs権限
resource "aws_iam_role_policy" "lambda_logs" {
  name = "${var.project_name}-lambda-logs-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# ECRアクセス権限（Lambda関数がECRからイメージを取得するため）
resource "aws_iam_role_policy" "lambda_ecr" {
  name = "${var.project_name}-lambda-ecr-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda関数用のS3オブジェクト（price_fetcher）
resource "aws_s3_object" "price_fetcher_code" {
  bucket = aws_s3_bucket.lambda_deployments.id
  key    = "price_fetcher/deployment.zip"
  source = "${path.module}/../lambda/price_fetcher/deployment.zip"
  etag   = filemd5("${path.module}/../lambda/price_fetcher/deployment.zip")
}

# 価格取得Lambda関数
resource "aws_lambda_function" "price_fetcher" {
  s3_bucket        = aws_s3_bucket.lambda_deployments.id
  s3_key           = aws_s3_object.price_fetcher_code.key
  function_name    = "${var.project_name}-price-fetcher"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = var.lambda_runtime
  timeout         = var.lambda_timeout
  memory_size     = var.lambda_memory_size

  environment {
    variables = {
      PRICES_TABLE = aws_dynamodb_table.prices.name
    }
  }

  source_code_hash = filebase64sha256("${path.module}/../lambda/price_fetcher/deployment.zip")
}

# 取引エージェントLambda関数（コンテナイメージ方式）
resource "aws_lambda_function" "trading_agent" {
  function_name = "${var.project_name}-trading-agent"
  role          = aws_iam_role.lambda_role.arn
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_size

  package_type = "Image"
  image_uri    = "${aws_ecr_repository.trading_agent.repository_url}:latest"

  environment {
    variables = {
      PRICES_TABLE      = aws_dynamodb_table.prices.name
      DECISIONS_TABLE   = aws_dynamodb_table.decisions.name
      ORDERS_TABLE      = aws_dynamodb_table.orders.name
      PERFORMANCE_TABLE = aws_dynamodb_table.performance.name
      BALANCE_TABLE     = aws_dynamodb_table.balance.name
      GATEIO_TEST_API_KEY    = var.gateio_test_api_key
      GATEIO_TEST_API_SECRET = var.gateio_test_api_secret
      GATEIO_LIVE_API_KEY    = var.gateio_live_api_key
      GATEIO_LIVE_API_SECRET = var.gateio_live_api_secret
      GATEIO_TESTNET         = "true"
    }
  }

  # イメージが更新されたときに再デプロイするためのトリガー
  # 実際のデプロイはDockerイメージをプッシュした後に行う
  depends_on = [aws_ecr_repository.trading_agent]
}


