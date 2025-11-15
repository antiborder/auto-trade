# Lambda関数用のS3バケット
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "lambda_deployments" {
  bucket = "${var.project_name}-lambda-deployments-${random_id.bucket_suffix.hex}"

  # ACL関連の属性を無視（権限エラーを回避）
  lifecycle {
    ignore_changes = [acl, grant]
  }
}

# ACLを無効化（AWSのベストプラクティス、権限エラーを回避）
resource "aws_s3_bucket_ownership_controls" "lambda_deployments" {
  bucket = aws_s3_bucket.lambda_deployments.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "lambda_deployments" {
  bucket = aws_s3_bucket.lambda_deployments.id

  block_public_acls       = true
  block_public_policy      = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "lambda_deployments" {
  bucket = aws_s3_bucket.lambda_deployments.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3バケットへのアップロード権限をIAMロールに追加
resource "aws_iam_role_policy" "lambda_s3" {
  name = "${var.project_name}-lambda-s3-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.lambda_deployments.arn}/*"
      }
    ]
  })
}

