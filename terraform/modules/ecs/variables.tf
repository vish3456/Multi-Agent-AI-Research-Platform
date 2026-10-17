variable "project_name" {
  type        = string
  description = "Project name prefix"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
}

variable "vpc_id" {
  type        = string
}

variable "private_subnet_ids" {
  type        = list(string)
}

variable "alb_security_group_id" {
  type        = string
}

variable "app_target_group_arn" {
  type        = string
}

variable "red_team_target_group_arn" {
  type        = string
}

variable "execution_role_arn" {
  type        = string
}

variable "task_role_arn" {
  type        = string
}

variable "app_image" {
  type        = string
}

variable "tensorzero_image" {
  type        = string
}

variable "pyrit_image" {
  type        = string
}

variable "app_log_group" {
  type        = string
}

variable "tensorzero_log_group" {
  type        = string
}

variable "pyrit_log_group" {
  type        = string
}

variable "secrets_arn" {
  type        = string
}

variable "redis_url" {
  type        = string
}

variable "database_url" {
  type        = string
  sensitive   = true
}

variable "guardrail_id" {
  type        = string
}

variable "guardrail_version" {
  type        = string
}

variable "app_port" {
  type        = number
  default     = 8000
}

variable "red_team_port" {
  type        = number
  default     = 8001
}
