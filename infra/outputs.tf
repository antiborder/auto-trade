output "dynamodb_tables" {
  description = "DynamoDB table names"
  value = {
    prices      = aws_dynamodb_table.prices.name
    decisions   = aws_dynamodb_table.decisions.name
    orders      = aws_dynamodb_table.orders.name
    performance = aws_dynamodb_table.performance.name
    simulations = aws_dynamodb_table.simulations.name
  }
}

output "lambda_functions" {
  description = "Lambda function ARNs"
  value = {
    price_fetcher = aws_lambda_function.price_fetcher.arn
    trading_agent = aws_lambda_function.trading_agent.arn
  }
}

output "eventbridge_rules" {
  description = "EventBridge rule names"
  value = {
    price_fetcher = aws_cloudwatch_event_rule.price_fetcher_schedule.name
    trading_agent = aws_cloudwatch_event_rule.trading_agent_schedule.name
  }
}


