terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
  
  # 開発環境ではローカルバックエンドを使用
  # 本番環境ではS3バックエンドを使用することを推奨
  # backend "s3" {
  #   bucket = "auto-trade-terraform-state"
  #   key    = "terraform.tfstate"
  #   region = "ap-northeast-1"
  # }
}

provider "aws" {
  region = var.aws_region
}


