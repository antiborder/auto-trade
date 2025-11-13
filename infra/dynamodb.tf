# 価格データテーブル
resource "aws_dynamodb_table" "prices" {
  name           = "${var.project_name}-prices"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "timestamp"

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = {
    Name        = "${var.project_name}-prices"
    Environment = "production"
  }
}

# 取引判断テーブル
resource "aws_dynamodb_table" "decisions" {
  name           = "${var.project_name}-decisions"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "agent_id"
  range_key      = "timestamp"

  attribute {
    name = "agent_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = {
    Name        = "${var.project_name}-decisions"
    Environment = "production"
  }
}

# 注文テーブル
resource "aws_dynamodb_table" "orders" {
  name           = "${var.project_name}-orders"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "order_id"

  attribute {
    name = "order_id"
    type = "S"
  }

  attribute {
    name = "agent_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  global_secondary_index {
    name     = "agent-timestamp-index"
    hash_key = "agent_id"
    range_key = "timestamp"
  }

  tags = {
    Name        = "${var.project_name}-orders"
    Environment = "production"
  }
}

# パフォーマンステーブル
resource "aws_dynamodb_table" "performance" {
  name           = "${var.project_name}-performance"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "agent_id"

  attribute {
    name = "agent_id"
    type = "S"
  }

  tags = {
    Name        = "${var.project_name}-performance"
    Environment = "production"
  }
}

# シミュレーションテーブル
resource "aws_dynamodb_table" "simulations" {
  name           = "${var.project_name}-simulations"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "simulation_id"

  attribute {
    name = "simulation_id"
    type = "S"
  }

  tags = {
    Name        = "${var.project_name}-simulations"
    Environment = "production"
  }
}


