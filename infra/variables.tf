variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "auto-trade"
}

variable "lambda_runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.11"
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 300
}

variable "lambda_memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 512
}

variable "bybit_api_key" {
  description = "Bybit API Key (optional, for trading agent)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "bybit_api_secret" {
  description = "Bybit API Secret (optional, for trading agent)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "bybit_testnet" {
  description = "Use Bybit testnet (true/false)"
  type        = bool
  default     = true
}


