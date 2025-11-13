# 価格取得用EventBridgeルール（5分ごと）
resource "aws_cloudwatch_event_rule" "price_fetcher_schedule" {
  name                = "${var.project_name}-price-fetcher-schedule"
  description         = "Trigger price fetcher every 5 minutes"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "price_fetcher_target" {
  rule      = aws_cloudwatch_event_rule.price_fetcher_schedule.name
  target_id = "PriceFetcherTarget"
  arn       = aws_lambda_function.price_fetcher.arn
}

resource "aws_lambda_permission" "price_fetcher_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.price_fetcher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.price_fetcher_schedule.arn
}

# 取引エージェント用EventBridgeルール（5分ごと）
resource "aws_cloudwatch_event_rule" "trading_agent_schedule" {
  name                = "${var.project_name}-trading-agent-schedule"
  description         = "Trigger trading agent every 5 minutes"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "trading_agent_target" {
  rule      = aws_cloudwatch_event_rule.trading_agent_schedule.name
  target_id = "TradingAgentTarget"
  arn       = aws_lambda_function.trading_agent.arn
}

resource "aws_lambda_permission" "trading_agent_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.trading_agent.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.trading_agent_schedule.arn
}


