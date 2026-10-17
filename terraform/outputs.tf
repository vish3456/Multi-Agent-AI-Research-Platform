output "alb_dns_name" {
  description = "Application Load Balancer DNS entry point"
  value       = module.alb.alb_dns_name
}

output "ecs_cluster_name" {
  description = "ECS Cluster Name"
  value       = module.ecs.cluster_name
}

output "app_ecr_repo" {
  description = "ECR Repository for main application"
  value       = module.ecr.app_repository_url
}

output "tensorzero_ecr_repo" {
  description = "ECR Repository for TensorZero sidecar"
  value       = module.ecr.tensorzero_repository_url
}

output "pyrit_ecr_repo" {
  description = "ECR Repository for PyRIT Red Team"
  value       = module.ecr.pyrit_repository_url
}

output "bedrock_guardrail_id" {
  description = "Bedrock Guardrail Identifier"
  value       = module.bedrock.guardrail_id
}

output "secrets_manager_arn" {
  description = "Secrets Manager Secret ARN"
  value       = module.secrets.secret_arn
}
