# ECRリポジトリ（Lambdaコンテナイメージ用）
resource "aws_ecr_repository" "trading_agent" {
  name                 = "${var.project_name}-trading-agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "${var.project_name}-trading-agent"
    Environment = "production"
  }
}

# ECRライフサイクルポリシー（古いイメージを自動削除）
resource "aws_ecr_lifecycle_policy" "trading_agent" {
  repository = aws_ecr_repository.trading_agent.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}


