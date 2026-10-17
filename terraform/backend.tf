# S3 backend for remote state storage and DynamoDB state locking
# Note: Uncomment and configure bucket and dynamodb table once provisioned in AWS.
# terraform {
#   backend "s3" {
#     bucket         = "multi-agent-research-tfstate"
#     key            = "infrastructure/terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "terraform-locks"
#     encrypt        = true
#   }
# }
